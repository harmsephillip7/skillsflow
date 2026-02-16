"""
Notification of Training (NOT) Views
Handles creation, management, and notification of training projects.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import date, timedelta
import json

from .models import (
    TrainingNotification, NOTStakeholder, NOTResourceRequirement,
    NOTDeliverable, NOTMeetingMinutes, NOTNotificationLog, User, UserRole, Role,
    ResourceAllocationPeriod
)
from .services.resource_allocation import (
    check_resource_availability, create_resource_allocation, 
    remove_resource_allocation, sync_allocation_with_requirement
)

# Import system resources for linking
from academics.models import Qualification
from tenants.models import Campus
from corporate.models import CorporateClient
from logistics.models import Venue
from intakes.models import Contract


def get_system_resources():
    """Get common system resources for NOT forms"""
    return {
        'qualifications': Qualification.objects.filter(is_active=True).order_by('short_title'),
        'campuses': Campus.objects.filter(is_active=True).order_by('name'),
        'corporate_clients': CorporateClient.objects.filter(status='ACTIVE').order_by('company_name'),
        'venues': Venue.objects.filter(is_active=True).select_related('campus').order_by('campus__name', 'name'),
        'staff_users': User.objects.filter(is_active=True, is_staff=True).order_by('first_name', 'last_name'),
        'contracts': Contract.objects.filter(status__in=['DRAFT', 'ACTIVE']).order_by('-created_at'),
    }


def get_users_by_role(role_code, campus_id=None):
    """Get users with a specific role, optionally filtered by campus"""
    user_roles = UserRole.objects.filter(
        role__code=role_code,
        is_active=True,
        user__is_active=True
    ).select_related('user', 'campus')
    
    if campus_id:
        # Include users with no campus restriction OR specific campus match
        user_roles = user_roles.filter(
            Q(campus__isnull=True) | Q(campus_id=campus_id)
        )
    
    return User.objects.filter(
        id__in=user_roles.values_list('user_id', flat=True)
    ).distinct().order_by('first_name', 'last_name')


def get_campus_employees(campus_id):
    """Get all employees (users with any role) at a specific campus"""
    if not campus_id:
        return User.objects.none()
    
    # Get users who have any role at this campus
    user_roles = UserRole.objects.filter(
        is_active=True,
        user__is_active=True
    ).filter(
        Q(campus_id=campus_id) | Q(campus__isnull=True)  # Campus-specific or organization-wide
    ).select_related('user')
    
    return User.objects.filter(
        id__in=user_roles.values_list('user_id', flat=True)
    ).distinct().order_by('first_name', 'last_name')


def get_qualified_personnel(qualification_id, campus_id, personnel_type):
    """
    Get users registered as facilitator/assessor/moderator for a qualification at a campus.
    Falls back to all personnel of that type if no qualification-specific registrations found.
    """
    from academics.models import PersonnelRegistration
    from django.utils import timezone
    
    today = timezone.now().date()
    
    # Get active personnel registrations for this type
    registrations = PersonnelRegistration.objects.filter(
        personnel_type=personnel_type,
        is_active=True,
        expiry_date__gte=today
    ).select_related('user')
    
    # Filter by qualification if provided
    if qualification_id:
        qual_registrations = registrations.filter(qualifications__id=qualification_id)
        if qual_registrations.exists():
            registrations = qual_registrations
    
    # Get users with campus access if campus provided
    if campus_id:
        campus_user_ids = UserRole.objects.filter(
            is_active=True,
            user__is_active=True
        ).filter(
            Q(campus_id=campus_id) | Q(campus__isnull=True)
        ).values_list('user_id', flat=True)
        
        registrations = registrations.filter(user_id__in=campus_user_ids)
    
    return User.objects.filter(
        id__in=registrations.values_list('user_id', flat=True)
    ).distinct().order_by('first_name', 'last_name')


class NOTDashboardView(LoginRequiredMixin, View):
    """Dashboard view for Notification of Training overview"""
    
    def get(self, request):
        user = request.user
        today = date.today()
        
        # Base queryset for active projects
        active_projects = TrainingNotification.objects.filter(
            status__in=['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL', 'APPROVED', 'NOTIFICATIONS_SENT', 'IN_PROGRESS'],
            is_deleted=False
        )
        
        # Summary statistics
        stats = {
            'total_active': active_projects.count(),
            'pending_approval': TrainingNotification.objects.filter(status='PENDING_APPROVAL', is_deleted=False).count(),
            'in_planning': TrainingNotification.objects.filter(status__in=['PLANNING', 'IN_MEETING'], is_deleted=False).count(),
            'in_progress': TrainingNotification.objects.filter(status='IN_PROGRESS', is_deleted=False).count(),
            'with_shortages': TrainingNotification.objects.filter(
                resource_requirements__is_available=False,
                is_deleted=False
            ).distinct().count(),
            'total_contract_value': active_projects.aggregate(
                total=Sum('contract_value')
            )['total'] or 0,
            'total_learners': active_projects.aggregate(
                total=Sum('expected_learner_count')
            )['total'] or 0,
        }
        
        # Recent notifications
        recent_nots = TrainingNotification.objects.filter(
            is_deleted=False
        ).order_by('-created_at')[:10]
        
        # My assignments
        my_assignments = NOTStakeholder.objects.filter(
            user=user,
            training_notification__status__in=['PLANNING', 'IN_MEETING', 'APPROVED', 'IN_PROGRESS'],
            training_notification__is_deleted=False
        ).select_related('training_notification')[:5]
        
        # Upcoming meetings
        upcoming_meetings = TrainingNotification.objects.filter(
            planning_meeting_date__gte=timezone.now(),
            planning_meeting_completed=False,
            is_deleted=False
        ).order_by('planning_meeting_date')[:5]
        
        # Overdue deliverables
        overdue_deliverables = NOTDeliverable.objects.filter(
            due_date__lt=today,
            status__in=['PENDING', 'IN_PROGRESS'],
            training_notification__is_deleted=False
        ).select_related('training_notification')[:5]
        
        # Resource shortages requiring attention
        resource_shortages = NOTResourceRequirement.objects.filter(
            is_available=False,
            training_notification__status__in=['APPROVED', 'IN_PROGRESS'],
            training_notification__is_deleted=False
        ).select_related('training_notification')[:5]
        
        # Notifications by project type
        by_type = TrainingNotification.objects.filter(
            status__in=['APPROVED', 'IN_PROGRESS'],
            is_deleted=False
        ).values('project_type').annotate(count=Count('id')).order_by('-count')
        
        # Notifications by funder
        by_funder = TrainingNotification.objects.filter(
            status__in=['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL', 'APPROVED', 'IN_PROGRESS'],
            is_deleted=False
        ).values('funder').annotate(
            count=Count('id'),
            total_value=Sum('contract_value')
        ).order_by('-count')
        
        context = {
            'stats': stats,
            'recent_nots': recent_nots,
            'my_assignments': my_assignments,
            'upcoming_meetings': upcoming_meetings,
            'overdue_deliverables': overdue_deliverables,
            'resource_shortages': resource_shortages,
            'by_type': by_type,
            'by_funder': by_funder,
        }
        
        return render(request, 'not/dashboard.html', context)


class NOTListView(LoginRequiredMixin, ListView):
    """List all Training Notifications with filtering"""
    model = TrainingNotification
    template_name = 'not/list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = TrainingNotification.objects.filter(is_deleted=False)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by project type
        project_type = self.request.GET.get('type')
        if project_type:
            queryset = queryset.filter(project_type=project_type)
        
        # Filter by funder
        funder = self.request.GET.get('funder')
        if funder:
            queryset = queryset.filter(funder=funder)
        
        # Filter by priority
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Search
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(reference_number__icontains=search) |
                Q(title__icontains=search) |
                Q(client_name__icontains=search)
            )
        
        # My projects only
        if self.request.GET.get('my_projects'):
            queryset = queryset.filter(
                Q(created_by=self.request.user) |
                Q(stakeholders__user=self.request.user)
            ).distinct()
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = TrainingNotification.STATUS_CHOICES
        context['type_choices'] = TrainingNotification.PROJECT_TYPE_CHOICES
        context['funder_choices'] = TrainingNotification.FUNDER_CHOICES
        context['priority_choices'] = TrainingNotification.PRIORITY_CHOICES
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'type': self.request.GET.get('type', ''),
            'funder': self.request.GET.get('funder', ''),
            'priority': self.request.GET.get('priority', ''),
            'q': self.request.GET.get('q', ''),
            'my_projects': self.request.GET.get('my_projects', ''),
        }
        return context


class NOTDetailView(LoginRequiredMixin, DetailView):
    """Detailed view of a Training Notification"""
    model = TrainingNotification
    template_name = 'not/detail.html'
    context_object_name = 'notification'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.object
        
        # Related data
        context['stakeholders'] = obj.stakeholders.all().select_related('user')
        context['resources'] = obj.resource_requirements.all()
        context['deliverables'] = obj.deliverables.all().order_by('due_date')
        context['meetings'] = obj.meeting_minutes.all()
        context['notification_logs'] = obj.notification_logs.all()[:20]
        
        # Delivery team - filter resources by personnel types
        context['delivery_team'] = obj.resource_requirements.filter(
            resource_type__in=['FACILITATOR', 'ASSESSOR', 'MODERATOR']
        ).select_related('assigned_user')
        
        # Non-personnel resources
        context['other_resources'] = obj.resource_requirements.exclude(
            resource_type__in=['FACILITATOR', 'ASSESSOR', 'MODERATOR']
        )
        
        # Tranche data
        tranches = obj.tranches.filter(is_deleted=False).order_by('sequence_number', 'due_date')
        context['tranches'] = tranches
        context['tranches_paid'] = tranches.filter(status='PAID').count()
        context['tranches_submitted'] = tranches.filter(status__in=['SUBMITTED', 'APPROVED']).count()
        context['tranches_overdue'] = tranches.filter(due_date__lt=date.today()).exclude(status__in=['PAID', 'CANCELLED']).count()
        
        # Summary stats
        context['resource_shortages'] = obj.resource_requirements.filter(is_available=False).count()
        context['overdue_deliverables'] = obj.deliverables.filter(
            due_date__lt=date.today(),
            status__in=['PENDING', 'IN_PROGRESS']
        ).count()
        context['upcoming_deliverables'] = obj.deliverables.filter(
            due_date__gte=date.today(),
            due_date__lte=date.today() + timedelta(days=14),
            status__in=['PENDING', 'IN_PROGRESS']
        ).count()
        
        # Check if user is a stakeholder
        context['is_stakeholder'] = obj.stakeholders.filter(user=self.request.user).exists()
        context['user_role'] = obj.stakeholders.filter(user=self.request.user).first()
        
        return context


class NOTCreateView(LoginRequiredMixin, CreateView):
    """Create a new Training Notification"""
    model = TrainingNotification
    template_name = 'not/create.html'
    fields = [
        'title', 'project_type', 'funder', 'description', 'priority',
        'client_name', 'corporate_client', 'tender_reference', 'contract_value',
        'contract', 'qualification', 'program_description',
        'expected_learner_count', 'learner_source', 'recruitment_notes',
        'planned_start_date', 'planned_end_date', 'duration_months',
        'delivery_campus', 'delivery_mode', 'delivery_address',
        'facilitator', 'assessor', 'moderator',
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_system_resources())
        # Get all users with facilitator, assessor, moderator roles for initial load
        context['facilitators'] = get_users_by_role('FACILITATOR')
        context['assessors'] = get_users_by_role('ASSESSOR')
        context['moderators'] = get_users_by_role('MODERATOR')
        return context
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.status = 'DRAFT'
        response = super().form_valid(form)
        
        # Add creator as project lead
        NOTStakeholder.objects.create(
            training_notification=self.object,
            user=self.request.user,
            department='EXECUTIVE',
            role_in_project='PROJECT_LEAD',
            responsibilities='Overall project ownership and coordination',
            created_by=self.request.user
        )
        
        # Create NOTStakeholder records for assigned delivery team
        if self.object.facilitator:
            NOTStakeholder.objects.get_or_create(
                training_notification=self.object,
                user=self.object.facilitator,
                role_in_project='FACILITATOR',
                defaults={
                    'department': 'ACADEMIC',
                    'responsibilities': 'Primary facilitator for training delivery',
                    'created_by': self.request.user
                }
            )
        
        if self.object.assessor:
            NOTStakeholder.objects.get_or_create(
                training_notification=self.object,
                user=self.object.assessor,
                role_in_project='ASSESSOR',
                defaults={
                    'department': 'ACADEMIC',
                    'responsibilities': 'Primary assessor for learner assessments',
                    'created_by': self.request.user
                }
            )
        
        if self.object.moderator:
            NOTStakeholder.objects.get_or_create(
                training_notification=self.object,
                user=self.object.moderator,
                role_in_project='MODERATOR',
                defaults={
                    'department': 'ACADEMIC',
                    'responsibilities': 'Primary moderator for quality assurance',
                    'created_by': self.request.user
                }
            )
        
        messages.success(self.request, f'Training Notification {self.object.reference_number} created successfully!')
        return response
    
    def get_success_url(self):
        return f'/not/{self.object.pk}/'


class NOTUsersByCampusView(LoginRequiredMixin, View):
    """AJAX endpoint to get facilitators, assessors, moderators filtered by campus"""
    
    def get(self, request):
        campus_id = request.GET.get('campus_id')
        
        # Get users by role, filtered by campus if provided
        campus_filter = int(campus_id) if campus_id else None
        
        facilitators = get_users_by_role('FACILITATOR', campus_filter)
        assessors = get_users_by_role('ASSESSOR', campus_filter)
        moderators = get_users_by_role('MODERATOR', campus_filter)
        
        return JsonResponse({
            'facilitators': [
                {'id': u.id, 'name': u.get_full_name() or u.email}
                for u in facilitators
            ],
            'assessors': [
                {'id': u.id, 'name': u.get_full_name() or u.email}
                for u in assessors
            ],
            'moderators': [
                {'id': u.id, 'name': u.get_full_name() or u.email}
                for u in moderators
            ],
        })


class NOTUpdateView(LoginRequiredMixin, UpdateView):
    """Update a Training Notification"""
    model = TrainingNotification
    template_name = 'not/edit.html'
    fields = [
        'title', 'project_type', 'funder', 'description', 'priority',
        'client_name', 'corporate_client', 'tender_reference', 'contract_value',
        'contract', 'qualification', 'program_description',
        'expected_learner_count', 'learner_source', 'recruitment_notes',
        'planned_start_date', 'planned_end_date', 'duration_months',
        'delivery_campus', 'delivery_mode', 'delivery_address',
        'planning_meeting_date', 'planning_meeting_venue',
        'facilitator', 'assessor', 'moderator',
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_system_resources())
        # Add delivery team users
        context['facilitators'] = get_users_by_role('FACILITATOR')
        context['assessors'] = get_users_by_role('ASSESSOR')
        context['moderators'] = get_users_by_role('MODERATOR')
        return context
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, 'Training Notification updated successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return f'/not/{self.object.pk}/'


class NOTScheduleMeetingView(LoginRequiredMixin, View):
    """Schedule a planning meeting for a NOT"""
    
    def get(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        stakeholders = notification.stakeholders.all().select_related('user')
        all_users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        
        context = {
            'notification': notification,
            'stakeholders': stakeholders,
            'all_users': all_users,
        }
        return render(request, 'not/schedule_meeting.html', context)
    
    def post(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        meeting_date = request.POST.get('meeting_date')
        meeting_venue = request.POST.get('meeting_venue')
        invitees = request.POST.getlist('invitees')
        
        if meeting_date:
            notification.planning_meeting_date = meeting_date
            notification.planning_meeting_venue = meeting_venue
            notification.status = 'PLANNING'
            notification.updated_by = request.user
            notification.save()
            
            # Update stakeholder invitations
            for user_id in invitees:
                stakeholder, created = NOTStakeholder.objects.get_or_create(
                    training_notification=notification,
                    user_id=user_id,
                    defaults={
                        'department': 'EXTERNAL',
                        'role_in_project': 'OBSERVER',
                        'created_by': request.user
                    }
                )
                stakeholder.invited_to_meeting = True
                stakeholder.save()
            
            messages.success(request, 'Planning meeting scheduled successfully!')
        
        return redirect('not_detail', pk=pk)


class NOTAddStakeholderView(LoginRequiredMixin, View):
    """Add a stakeholder to a NOT"""
    
    def get(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        all_users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        
        context = {
            'notification': notification,
            'all_users': all_users,
            'department_choices': NOTStakeholder.DEPARTMENT_CHOICES,
            'role_choices': NOTStakeholder.ROLE_IN_PROJECT_CHOICES,
        }
        return render(request, 'not/add_stakeholder.html', context)
    
    def post(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        user_id = request.POST.get('user')
        department = request.POST.get('department')
        role = request.POST.get('role')
        responsibilities = request.POST.get('responsibilities', '')
        
        if user_id and department and role:
            stakeholder, created = NOTStakeholder.objects.get_or_create(
                training_notification=notification,
                user_id=user_id,
                role_in_project=role,
                defaults={
                    'department': department,
                    'responsibilities': responsibilities,
                    'created_by': request.user
                }
            )
            
            if created:
                messages.success(request, 'Stakeholder added successfully!')
            else:
                messages.info(request, 'Stakeholder already exists with this role.')
        
        return redirect('not_detail', pk=pk)


class NOTEditStakeholderView(LoginRequiredMixin, View):
    """Edit a stakeholder assignment"""
    
    def get(self, request, pk, stakeholder_pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        stakeholder = get_object_or_404(NOTStakeholder, pk=stakeholder_pk, training_notification=notification)
        all_users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        
        context = {
            'notification': notification,
            'stakeholder': stakeholder,
            'all_users': all_users,
            'department_choices': NOTStakeholder.DEPARTMENT_CHOICES,
            'role_choices': NOTStakeholder.ROLE_IN_PROJECT_CHOICES,
        }
        return render(request, 'not/edit_stakeholder.html', context)
    
    def post(self, request, pk, stakeholder_pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        stakeholder = get_object_or_404(NOTStakeholder, pk=stakeholder_pk, training_notification=notification)
        
        action = request.POST.get('action')
        
        if action == 'delete':
            stakeholder.delete()
            messages.success(request, 'Stakeholder removed successfully!')
            return redirect('not_detail', pk=pk)
        
        # Update stakeholder
        user_id = request.POST.get('user')
        if user_id:
            stakeholder.user_id = user_id
        stakeholder.department = request.POST.get('department', stakeholder.department)
        stakeholder.role_in_project = request.POST.get('role', stakeholder.role_in_project)
        stakeholder.responsibilities = request.POST.get('responsibilities', '')
        stakeholder.updated_by = request.user
        stakeholder.save()
        
        messages.success(request, 'Stakeholder updated successfully!')
        return redirect('not_detail', pk=pk)


class NOTEditDeliverableView(LoginRequiredMixin, View):
    """Edit a deliverable"""
    
    def get(self, request, pk, deliverable_pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        deliverable = get_object_or_404(NOTDeliverable, pk=deliverable_pk, training_notification=notification)
        
        # Get campus employees for assignment dropdown
        campus_id = notification.delivery_campus_id if notification.delivery_campus_id else None
        campus_employees = get_campus_employees(campus_id)
        
        context = {
            'notification': notification,
            'deliverable': deliverable,
            'campus_employees': campus_employees,
            'type_choices': NOTDeliverable.DELIVERABLE_TYPE_CHOICES,
            'department_choices': NOTStakeholder.DEPARTMENT_CHOICES,
            'status_choices': NOTDeliverable.STATUS_CHOICES,
        }
        return render(request, 'not/edit_deliverable.html', context)
    
    def post(self, request, pk, deliverable_pk):
        from .tasks import Task, TaskCategory, TaskStatus, TaskPriority
        from django.contrib.contenttypes.models import ContentType
        
        notification = get_object_or_404(TrainingNotification, pk=pk)
        deliverable = get_object_or_404(NOTDeliverable, pk=deliverable_pk, training_notification=notification)
        
        action = request.POST.get('action')
        
        if action == 'delete':
            # Also delete any linked tasks
            content_type = ContentType.objects.get_for_model(NOTDeliverable)
            Task.objects.filter(content_type=content_type, object_id=deliverable.pk).delete()
            deliverable.delete()
            messages.success(request, 'Deliverable removed successfully!')
            return redirect('not_detail', pk=pk)
        
        # Track if assignment changed
        old_assigned_to = deliverable.assigned_to_id
        
        # Update deliverable
        deliverable.title = request.POST.get('title', deliverable.title)
        deliverable.deliverable_type = request.POST.get('deliverable_type', deliverable.deliverable_type)
        deliverable.description = request.POST.get('description', '')
        deliverable.responsible_department = request.POST.get('responsible_department', '')
        deliverable.submit_to = request.POST.get('submit_to', '')
        deliverable.status = request.POST.get('status', deliverable.status)
        
        # Handle assignment to campus employee
        assigned_to_id = request.POST.get('assigned_to')
        deliverable.assigned_to_id = int(assigned_to_id) if assigned_to_id else None
        
        due_date = request.POST.get('due_date')
        if due_date:
            deliverable.due_date = due_date
        
        deliverable.updated_by = request.user
        deliverable.save()
        
        # Create or update task for assigned user
        if deliverable.assigned_to_id:
            content_type = ContentType.objects.get_for_model(NOTDeliverable)
            task, created = Task.objects.update_or_create(
                content_type=content_type,
                object_id=deliverable.pk,
                defaults={
                    'title': f'Deliverable: {deliverable.title}',
                    'description': f'Project: {notification.reference_number} - {notification.title}\n\n{deliverable.description}',
                    'category': TaskCategory.REPORT_DUE,
                    'assigned_to_id': deliverable.assigned_to_id,
                    'assigned_campus': notification.delivery_campus,
                    'due_date': deliverable.due_date,
                    'priority': TaskPriority.MEDIUM,
                    'status': TaskStatus.PENDING if deliverable.status in ['PENDING', 'IN_PROGRESS'] else TaskStatus.COMPLETED,
                    'action_url': f'/not/{notification.pk}/',
                    'action_label': 'View Project',
                    'is_auto_generated': True,
                    'source_event': 'deliverable_assigned',
                }
            )
            if created:
                task.created_by = request.user
                task.save()
        elif old_assigned_to and not deliverable.assigned_to_id:
            # Assignment removed - delete the task
            content_type = ContentType.objects.get_for_model(NOTDeliverable)
            Task.objects.filter(content_type=content_type, object_id=deliverable.pk).delete()
        
        messages.success(request, 'Deliverable updated successfully!')
        return redirect('not_detail', pk=pk)


class NOTAddDeliveryTeamView(LoginRequiredMixin, View):
    """Add a delivery team member (facilitator/assessor/moderator) to a NOT"""
    
    def get(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        # Get qualified personnel for each type based on qualification and campus
        qual_id = notification.qualification_id
        campus_id = notification.delivery_campus_id
        
        facilitators = get_qualified_personnel(qual_id, campus_id, 'FACILITATOR')
        assessors = get_qualified_personnel(qual_id, campus_id, 'ASSESSOR')
        moderators = get_qualified_personnel(qual_id, campus_id, 'MODERATOR')
        
        # Fallback to role-based if no qualified personnel found
        if not facilitators.exists():
            facilitators = get_users_by_role('FACILITATOR', campus_id)
        if not assessors.exists():
            assessors = get_users_by_role('ASSESSOR', campus_id)
        if not moderators.exists():
            moderators = get_users_by_role('MODERATOR', campus_id)
        
        context = {
            'notification': notification,
            'facilitators': facilitators,
            'assessors': assessors,
            'moderators': moderators,
            'type_choices': [
                ('FACILITATOR', 'Facilitator'),
                ('ASSESSOR', 'Assessor'),
                ('MODERATOR', 'Moderator'),
            ],
        }
        return render(request, 'not/add_delivery_team.html', context)
    
    def post(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        resource_type = request.POST.get('resource_type')
        user_id = request.POST.get('assigned_user')
        
        if not user_id:
            messages.error(request, 'Please select a person to assign.')
            return redirect('not_add_delivery_team', pk=pk)
        
        user = get_object_or_404(User, pk=user_id)
        
        # Check if this person is already assigned in this role
        existing = NOTResourceRequirement.objects.filter(
            training_notification=notification,
            resource_type=resource_type,
            assigned_user=user
        ).exists()
        
        if existing:
            messages.warning(request, f'{user.get_full_name()} is already assigned as {resource_type}.')
            return redirect('not_detail', pk=pk)
        
        resource = NOTResourceRequirement.objects.create(
            training_notification=notification,
            resource_type=resource_type,
            description=f'{resource_type.title()} - {user.get_full_name()}',
            quantity_required=1,
            quantity_available=1,
            is_available=True,
            status='ALLOCATED',
            assigned_user=user,
            created_by=request.user
        )
        
        # Also create a stakeholder record if not exists
        NOTStakeholder.objects.get_or_create(
            training_notification=notification,
            user=user,
            role_in_project=resource_type,
            defaults={
                'department': 'ACADEMIC',
                'responsibilities': f'{resource_type.title()} for training delivery',
                'created_by': request.user
            }
        )
        
        messages.success(request, f'{user.get_full_name()} added as {resource_type}!')
        return redirect('not_detail', pk=pk)


class NOTEditDeliveryTeamView(LoginRequiredMixin, View):
    """Edit a delivery team member assignment"""
    
    def get(self, request, pk, resource_pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        resource = get_object_or_404(
            NOTResourceRequirement, 
            pk=resource_pk, 
            training_notification=notification,
            resource_type__in=['FACILITATOR', 'ASSESSOR', 'MODERATOR']
        )
        
        # Get qualified personnel based on the resource type
        qual_id = notification.qualification_id
        campus_id = notification.delivery_campus_id
        
        personnel = get_qualified_personnel(qual_id, campus_id, resource.resource_type)
        if not personnel.exists():
            personnel = get_users_by_role(resource.resource_type, campus_id)
        
        context = {
            'notification': notification,
            'resource': resource,
            'personnel': personnel,
        }
        return render(request, 'not/edit_delivery_team.html', context)
    
    def post(self, request, pk, resource_pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        resource = get_object_or_404(
            NOTResourceRequirement, 
            pk=resource_pk, 
            training_notification=notification,
            resource_type__in=['FACILITATOR', 'ASSESSOR', 'MODERATOR']
        )
        
        action = request.POST.get('action')
        
        if action == 'delete':
            resource.delete()
            messages.success(request, 'Delivery team member removed!')
            return redirect('not_detail', pk=pk)
        
        user_id = request.POST.get('assigned_user')
        if user_id:
            user = get_object_or_404(User, pk=user_id)
            resource.assigned_user = user
            resource.description = f'{resource.resource_type.title()} - {user.get_full_name()}'
        else:
            resource.assigned_user = None
            resource.description = f'{resource.resource_type.title()} - Unassigned'
        
        resource.updated_by = request.user
        resource.save()
        
        messages.success(request, 'Delivery team member updated!')
        return redirect('not_detail', pk=pk)


class NOTAddResourceView(LoginRequiredMixin, View):
    """Add a resource requirement to a NOT with conflict checking for allocations"""
    
    def get(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        resources = get_system_resources()
        
        # Get personnel by role for human resource types
        campus_id = notification.delivery_campus_id
        qual_id = notification.qualification_id
        
        facilitators = get_qualified_personnel(qual_id, campus_id, 'FACILITATOR') if qual_id else get_users_by_role('FACILITATOR', campus_id)
        assessors = get_qualified_personnel(qual_id, campus_id, 'ASSESSOR') if qual_id else get_users_by_role('ASSESSOR', campus_id)
        moderators = get_qualified_personnel(qual_id, campus_id, 'MODERATOR') if qual_id else get_users_by_role('MODERATOR', campus_id)
        
        context = {
            'notification': notification,
            'type_choices': NOTResourceRequirement.RESOURCE_TYPE_CHOICES,
            'status_choices': NOTResourceRequirement.STATUS_CHOICES,
            'venues': resources['venues'],
            'staff_users': resources['staff_users'],
            'facilitators': facilitators,
            'assessors': assessors,
            'moderators': moderators,
        }
        return render(request, 'not/add_resource.html', context)
    
    def post(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        resource_type = request.POST.get('resource_type')
        status = request.POST.get('status', 'REQUIRED')
        assigned_user_id = request.POST.get('assigned_user')
        venue_id = request.POST.get('venue')
        force_allocation = request.POST.get('force_allocation') == 'true'
        
        # Check for conflicts before creating if status is ALLOCATED
        conflicts = []
        if status == 'ALLOCATED' and resource_type in ('FACILITATOR', 'ASSESSOR', 'MODERATOR', 'VENUE'):
            start_date = notification.planned_start_date or date.today()
            end_date = notification.planned_end_date or (start_date + timedelta(days=365 * 3))
            
            if resource_type in ('FACILITATOR', 'ASSESSOR', 'MODERATOR') and assigned_user_id:
                user = User.objects.filter(pk=assigned_user_id).first()
                if user:
                    is_available, conflicts = check_resource_availability(
                        allocation_type=resource_type,
                        start_date=start_date,
                        end_date=end_date,
                        user=user,
                        exclude_not_id=notification.pk
                    )
                    
                    if not is_available and not force_allocation:
                        # Return JSON with conflicts for modal display
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'has_conflicts': True,
                                'conflicts': conflicts,
                                'message': f'{resource_type.title()} has existing allocations that overlap with this project period.'
                            })
            
            elif resource_type == 'VENUE' and venue_id:
                venue = Venue.objects.filter(pk=venue_id).first()
                if venue:
                    is_available, conflicts = check_resource_availability(
                        allocation_type='VENUE',
                        start_date=start_date,
                        end_date=end_date,
                        venue=venue,
                        exclude_not_id=notification.pk
                    )
                    
                    if not is_available and not force_allocation:
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'has_conflicts': True,
                                'conflicts': conflicts,
                                'message': 'Venue has existing allocations that overlap with this project period.'
                            })
        
        # Create the resource requirement
        resource = NOTResourceRequirement.objects.create(
            training_notification=notification,
            resource_type=resource_type,
            description=request.POST.get('description'),
            quantity_required=int(request.POST.get('quantity_required', 1)),
            quantity_available=int(request.POST.get('quantity_available', 0)),
            estimated_cost=request.POST.get('estimated_cost') or None,
            supplier=request.POST.get('supplier', ''),
            procurement_notes=request.POST.get('procurement_notes', ''),
            assigned_user_id=assigned_user_id if assigned_user_id else None,
            status=status,
            created_by=request.user
        )
        
        # Set availability status
        resource.is_available = resource.quantity_available >= resource.quantity_required
        if status != 'ALLOCATED':
            resource.status = 'AVAILABLE' if resource.is_available else 'REQUIRED'
        resource.save()
        
        # Create allocation period if status is ALLOCATED
        if status == 'ALLOCATED' and resource_type in ('FACILITATOR', 'ASSESSOR', 'MODERATOR', 'VENUE'):
            start_date = notification.planned_start_date or date.today()
            end_date = notification.planned_end_date or (start_date + timedelta(days=365 * 3))
            
            user = User.objects.filter(pk=assigned_user_id).first() if assigned_user_id else None
            venue = Venue.objects.filter(pk=venue_id).first() if venue_id else None
            
            if user or venue:
                try:
                    allocation, _ = create_resource_allocation(
                        resource_requirement=resource,
                        start_date=start_date,
                        end_date=end_date,
                        user=user,
                        venue=venue,
                        force=True  # Already checked conflicts above
                    )
                    
                    # Send notification if there were conflicts and user forced
                    if conflicts and force_allocation:
                        self._send_conflict_notification(request.user, notification, resource, conflicts)
                        
                except Exception as e:
                    messages.warning(request, f'Resource created but allocation tracking failed: {str(e)}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Resource requirement added successfully!',
                'redirect_url': f'/not/{pk}/'
            })
        
        messages.success(request, 'Resource requirement added successfully!')
        return redirect('not_detail', pk=pk)
    
    def _send_conflict_notification(self, user, notification, resource, conflicts):
        """Send in-app notification when user overrides a resource conflict"""
        from .tasks import Task, TaskCategory, TaskStatus, TaskPriority
        from django.contrib.contenttypes.models import ContentType
        
        # Find the project manager or owner to notify
        stakeholders = notification.stakeholders.filter(
            role__in=['PROJECT_MANAGER', 'TRAINING_MANAGER', 'OWNER']
        ).select_related('user')
        
        conflict_summary = ', '.join([
            f"{c['not_reference']}" for c in conflicts[:3]
        ])
        if len(conflicts) > 3:
            conflict_summary += f' and {len(conflicts) - 3} more'
        
        for stakeholder in stakeholders:
            if stakeholder.user and stakeholder.user != user:
                content_type = ContentType.objects.get_for_model(NOTResourceRequirement)
                Task.objects.create(
                    title=f'Resource Conflict Override: {resource.get_resource_type_display()}',
                    description=(
                        f'{user.get_full_name()} allocated a resource despite existing conflicts.\n\n'
                        f'Project: {notification.reference_number} - {notification.title}\n'
                        f'Resource: {resource.description}\n'
                        f'Conflicting Projects: {conflict_summary}\n\n'
                        f'Please review the allocation and resolve any scheduling conflicts.'
                    ),
                    category=TaskCategory.OTHER,
                    assigned_to=stakeholder.user,
                    assigned_campus=notification.delivery_campus,
                    due_date=date.today() + timedelta(days=3),
                    priority=TaskPriority.HIGH,
                    status=TaskStatus.PENDING,
                    action_url=f'/not/{notification.pk}/',
                    action_label='View Project',
                    is_auto_generated=True,
                    source_event='resource_conflict_override',
                    content_type=content_type,
                    object_id=resource.pk,
                    created_by=user
                )


class NOTAddDeliverableView(LoginRequiredMixin, View):
    """Add a deliverable to a NOT"""
    
    def get(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        # Get campus employees for assignment dropdown
        campus_id = notification.delivery_campus_id if notification.delivery_campus_id else None
        campus_employees = get_campus_employees(campus_id)
        
        context = {
            'notification': notification,
            'campus_employees': campus_employees,
            'type_choices': NOTDeliverable.DELIVERABLE_TYPE_CHOICES,
            'department_choices': NOTStakeholder.DEPARTMENT_CHOICES,
            'recurrence_choices': NOTDeliverable.RECURRENCE_CHOICES,
        }
        return render(request, 'not/add_deliverable.html', context)
    
    def post(self, request, pk):
        from .tasks import Task, TaskCategory, TaskStatus, TaskPriority
        from django.contrib.contenttypes.models import ContentType
        
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        assigned_to_id = request.POST.get('assigned_to')
        is_recurring = request.POST.get('is_recurring') == 'on'
        recurrence_type = request.POST.get('recurrence_type', '') if is_recurring else ''
        recurrence_end_date = request.POST.get('recurrence_end_date') if is_recurring else None
        
        deliverable = NOTDeliverable.objects.create(
            training_notification=notification,
            title=request.POST.get('title'),
            deliverable_type=request.POST.get('deliverable_type'),
            description=request.POST.get('description', ''),
            assigned_to_id=int(assigned_to_id) if assigned_to_id else None,
            responsible_department=request.POST.get('responsible_department', ''),
            due_date=request.POST.get('due_date'),
            submit_to=request.POST.get('submit_to', ''),
            is_recurring=is_recurring,
            recurrence_type=recurrence_type,
            recurrence_end_date=recurrence_end_date if recurrence_end_date else None,
            created_by=request.user
        )
        
        # Create task for assigned user
        if deliverable.assigned_to_id:
            content_type = ContentType.objects.get_for_model(NOTDeliverable)
            Task.objects.create(
                title=f'Deliverable: {deliverable.title}',
                description=f'Project: {notification.reference_number} - {notification.title}\n\n{deliverable.description}',
                category=TaskCategory.REPORT_DUE,
                assigned_to_id=deliverable.assigned_to_id,
                assigned_campus=notification.delivery_campus,
                due_date=deliverable.due_date,
                priority=TaskPriority.MEDIUM,
                status=TaskStatus.PENDING,
                action_url=f'/not/{notification.pk}/',
                action_label='View Project',
                is_auto_generated=True,
                source_event='deliverable_assigned',
                content_type=content_type,
                object_id=deliverable.pk,
                created_by=request.user
            )
        
        # Generate recurring instances if this is a recurring deliverable
        recurring_count = 0
        if is_recurring and recurrence_type and recurrence_end_date:
            recurring_instances = deliverable.generate_recurring_instances()
            recurring_count = len(recurring_instances)
        
        if recurring_count > 0:
            messages.success(request, f'Deliverable added successfully! Created {recurring_count + 1} occurrences (including the first one).')
        else:
            messages.success(request, 'Deliverable added successfully!')
        return redirect('not_detail', pk=pk)


class NOTApproveView(LoginRequiredMixin, View):
    """Approve a Training Notification"""
    
    def post(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'approve':
            notification.status = 'APPROVED'
            notification.approved_by = request.user
            notification.approved_date = timezone.now()
            notification.approval_notes = notes
            notification.save()
            messages.success(request, f'{notification.reference_number} has been approved!')
        
        elif action == 'reject':
            notification.status = 'DRAFT'
            notification.approval_notes = f"Rejected: {notes}"
            notification.save()
            messages.warning(request, f'{notification.reference_number} has been sent back for revision.')
        
        return redirect('not_detail', pk=pk)


class NOTSendNotificationsView(LoginRequiredMixin, View):
    """Send notifications to all stakeholders"""
    
    def post(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        if notification.status != 'APPROVED':
            messages.error(request, 'Notification must be approved before sending notifications.')
            return redirect('not_detail', pk=pk)
        
        # Get all stakeholders
        stakeholders = notification.stakeholders.filter(notification_sent=False)
        sent_count = 0
        
        for stakeholder in stakeholders:
            # Create notification log
            NOTNotificationLog.objects.create(
                training_notification=notification,
                recipient=stakeholder.user,
                notification_type='ASSIGNMENT',
                subject=f'Training Project Assignment: {notification.title}',
                message=f"""
Dear {stakeholder.user.get_full_name()},

You have been assigned to the following training project:

Project: {notification.title}
Reference: {notification.reference_number}
Your Role: {stakeholder.get_role_in_project_display()}
Department: {stakeholder.get_department_display()}

Responsibilities:
{stakeholder.responsibilities or 'Please check the project details for your specific responsibilities.'}

Tasks Assigned:
{stakeholder.tasks_assigned or 'No specific tasks assigned yet.'}

Project Details:
- Type: {notification.get_project_type_display()}
- Expected Learners: {notification.expected_learner_count}
- Planned Start: {notification.planned_start_date or 'TBD'}
- Duration: {notification.duration_months or 'TBD'} months

Please log in to the system to review the full project details and confirm your participation.

Best regards,
SkillsFlow Training Management
                """.strip(),
                sent_via='EMAIL'
            )
            
            # Mark stakeholder as notified
            stakeholder.notification_sent = True
            stakeholder.notification_sent_date = timezone.now()
            stakeholder.save()
            sent_count += 1
        
        # Check for resource shortages and notify managers
        shortages = notification.resource_requirements.filter(is_available=False)
        for shortage in shortages:
            if not shortage.manager_notified:
                # Find relevant managers to notify (simplified - would need proper role lookup)
                managers = User.objects.filter(
                    is_staff=True,
                    is_active=True
                )[:3]  # Simplified for now
                
                for manager in managers:
                    NOTNotificationLog.objects.create(
                        training_notification=notification,
                        recipient=manager,
                        notification_type='RESOURCE_SHORTAGE',
                        subject=f'Resource Shortage Alert: {notification.title}',
                        message=f"""
RESOURCE SHORTAGE ALERT

Project: {notification.title} ({notification.reference_number})

The following resource has a shortage:

Resource: {shortage.get_resource_type_display()} - {shortage.description}
Required: {shortage.quantity_required}
Available: {shortage.quantity_available}
Shortage: {shortage.shortage_quantity}

Estimated Cost: R{shortage.estimated_cost or 'Not specified'}
Expected Availability: {shortage.expected_availability_date or 'Not specified'}

Please take action to address this shortage.

Best regards,
SkillsFlow Training Management
                        """.strip(),
                        sent_via='EMAIL'
                    )
                
                shortage.manager_notified = True
                shortage.manager_notified_date = timezone.now()
                shortage.save()
        
        # Update notification status
        notification.status = 'NOTIFICATIONS_SENT'
        notification.notifications_sent_date = timezone.now()
        notification.save()
        
        messages.success(request, f'Notifications sent to {sent_count} stakeholders!')
        return redirect('not_detail', pk=pk)


class NOTRecordMeetingView(LoginRequiredMixin, View):
    """Record meeting minutes for a NOT"""
    
    def get(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        stakeholders = notification.stakeholders.all().select_related('user')
        
        context = {
            'notification': notification,
            'stakeholders': stakeholders,
        }
        return render(request, 'not/record_meeting.html', context)
    
    def post(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        # Create meeting minutes
        meeting = NOTMeetingMinutes.objects.create(
            training_notification=notification,
            meeting_date=request.POST.get('meeting_date') or timezone.now(),
            meeting_type=request.POST.get('meeting_type', 'PLANNING'),
            agenda=request.POST.get('agenda', ''),
            minutes=request.POST.get('minutes', ''),
            decisions=request.POST.get('decisions', ''),
            action_items=request.POST.get('action_items', ''),
            next_meeting_date=request.POST.get('next_meeting_date') or None,
            created_by=request.user
        )
        
        # Add attendees
        attendee_ids = request.POST.getlist('attendees')
        meeting.attendees.set(attendee_ids)
        
        # Update stakeholder attendance
        for stakeholder in notification.stakeholders.all():
            if str(stakeholder.user_id) in attendee_ids:
                stakeholder.attended_meeting = True
                stakeholder.save()
        
        # Update notification status if this was the planning meeting
        if notification.status in ['PLANNING', 'IN_MEETING'] and request.POST.get('meeting_type') == 'PLANNING':
            notification.planning_meeting_completed = True
            notification.planning_meeting_notes = request.POST.get('minutes', '')
            notification.status = 'PENDING_APPROVAL'
            notification.save()
        
        messages.success(request, 'Meeting minutes recorded successfully!')
        return redirect('not_detail', pk=pk)


class NOTStartProjectView(LoginRequiredMixin, View):
    """Start the project - move to In Progress"""
    
    def post(self, request, pk):
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        if notification.status not in ['APPROVED', 'NOTIFICATIONS_SENT']:
            messages.error(request, 'Project must be approved before starting.')
            return redirect('not_detail', pk=pk)
        
        notification.status = 'IN_PROGRESS'
        notification.actual_start_date = date.today()
        notification.save()
        
        messages.success(request, f'Project {notification.reference_number} is now in progress!')
        return redirect('not_detail', pk=pk)


class NOTQuickStatsAPI(LoginRequiredMixin, View):
    """API endpoint for dashboard quick stats"""
    
    def get(self, request):
        stats = {
            'total_active': TrainingNotification.objects.filter(
                status__in=['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL', 'APPROVED', 'NOTIFICATIONS_SENT', 'IN_PROGRESS']
            ).count(),
            'pending_approval': TrainingNotification.objects.filter(status='PENDING_APPROVAL').count(),
            'with_shortages': TrainingNotification.objects.filter(
                resource_requirements__is_available=False
            ).distinct().count(),
            'overdue_deliverables': NOTDeliverable.objects.filter(
                due_date__lt=date.today(),
                status__in=['PENDING', 'IN_PROGRESS']
            ).count(),
        }
        return JsonResponse(stats)


class NOTTimelineView(LoginRequiredMixin, DetailView):
    """
    Timeline view for a Training Notification project.
    Shows all tranches with their dates, statuses, and linked tasks/actions.
    """
    model = TrainingNotification
    template_name = 'not/timeline.html'
    context_object_name = 'notification'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.object
        today = date.today()
        
        # Import tranche models
        from .models import TrancheSchedule, TrancheEvidenceRequirement
        from .tasks import Task
        from django.contrib.contenttypes.models import ContentType
        
        # Get all tranches for this project
        tranches = obj.tranches.filter(is_deleted=False).order_by('due_date', 'sequence_number')
        
        # Build timeline data
        timeline_items = []
        tranche_content_type = ContentType.objects.get_for_model(TrancheSchedule)
        
        for tranche in tranches:
            # Get evidence requirements
            requirements = tranche.evidence_requirements.all()
            requirements_fulfilled = requirements.filter(evidence__status='VERIFIED').distinct().count()
            requirements_total = requirements.count()
            
            # Get linked tasks for this tranche
            linked_tasks = Task.objects.filter(
                content_type=tranche_content_type,
                object_id=tranche.pk
            ).order_by('due_date', '-priority')
            
            # Determine timeline status
            if tranche.status == 'PAID':
                timeline_status = 'completed'
            elif tranche.status in ['CANCELLED']:
                timeline_status = 'cancelled'
            elif tranche.due_date and tranche.due_date < today and tranche.status not in ['PAID', 'CANCELLED']:
                timeline_status = 'overdue'
            elif tranche.status in ['EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE', 'PENDING_QC', 'QC_PASSED', 'SUBMITTED', 'APPROVED', 'INVOICED']:
                timeline_status = 'in_progress'
            else:
                timeline_status = 'upcoming'
            
            # Calculate days info
            if tranche.due_date:
                days_until = (tranche.due_date - today).days
                if days_until < 0:
                    days_label = f'{abs(days_until)} days overdue'
                elif days_until == 0:
                    days_label = 'Due today'
                elif days_until == 1:
                    days_label = 'Due tomorrow'
                elif days_until <= 7:
                    days_label = f'Due in {days_until} days'
                elif days_until <= 30:
                    days_label = f'Due in {days_until // 7} weeks'
                else:
                    days_label = f'Due in {days_until // 30} months'
            else:
                days_until = None
                days_label = 'No due date'
            
            timeline_items.append({
                'tranche': tranche,
                'timeline_status': timeline_status,
                'days_until': days_until,
                'days_label': days_label,
                'requirements': requirements,
                'requirements_fulfilled': requirements_fulfilled,
                'requirements_total': requirements_total,
                'requirements_percent': int((requirements_fulfilled / requirements_total * 100)) if requirements_total > 0 else 100,
                'linked_tasks': linked_tasks,
                'pending_tasks': linked_tasks.exclude(status__in=['completed', 'cancelled']).count(),
            })
        
        context['timeline_items'] = timeline_items
        context['today'] = today
        
        # Summary stats
        context['total_tranches'] = tranches.count()
        context['completed_tranches'] = tranches.filter(status='PAID').count()
        context['in_progress_tranches'] = tranches.filter(
            status__in=['EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE', 'PENDING_QC', 'QC_PASSED', 'SUBMITTED', 'APPROVED', 'INVOICED']
        ).count()
        context['overdue_tranches'] = tranches.filter(
            due_date__lt=today
        ).exclude(status__in=['PAID', 'CANCELLED']).count()
        
        # Financial summary
        from django.db.models import Sum
        total_value = tranches.aggregate(total=Sum('amount'))['total'] or 0
        paid_value = tranches.filter(status='PAID').aggregate(total=Sum('actual_amount_received'))['total'] or 0
        pending_value = tranches.exclude(status__in=['PAID', 'CANCELLED']).aggregate(total=Sum('amount'))['total'] or 0
        
        context['total_value'] = total_value
        context['paid_value'] = paid_value
        context['pending_value'] = pending_value
        
        # Project dates for timeline reference
        context['project_start'] = obj.actual_start_date or obj.planned_start_date
        context['project_end'] = obj.actual_end_date or obj.planned_end_date
        
        # Get all tasks for this NOT (not just tranche-linked)
        not_content_type = ContentType.objects.get_for_model(TrainingNotification)
        context['all_tasks'] = Task.objects.filter(
            Q(content_type=tranche_content_type, object_id__in=tranches.values_list('pk', flat=True)) |
            Q(content_type=not_content_type, object_id=obj.pk)
        ).order_by('due_date', '-priority')[:20]
        
        return context


class NOTIntakeCalendarView(LoginRequiredMixin, View):
    """
    3-year intake calendar view showing all NOT projects segmented by year.
    Shows capacity status, fill rate, and dropout tracking.
    """
    
    def get(self, request):
        from .models import NOTIntake
        
        current_year = date.today().year
        years = [current_year, current_year + 1, current_year + 2]
        selected_year = request.GET.get('year', str(current_year))
        
        try:
            selected_year = int(selected_year)
        except ValueError:
            selected_year = current_year
        
        # Get filter parameters
        status_filter = request.GET.get('status', '')
        project_type_filter = request.GET.get('type', '')
        funder_filter = request.GET.get('funder', '')
        
        # Base queryset - projects with planned_start_date in the selected year
        projects = TrainingNotification.objects.filter(
            is_deleted=False,
            planned_start_date__year=selected_year
        ).select_related('qualification', 'corporate_client', 'delivery_campus').prefetch_related('intakes')
        
        # Apply filters
        if status_filter:
            projects = projects.filter(status=status_filter)
        if project_type_filter:
            projects = projects.filter(project_type=project_type_filter)
        if funder_filter:
            projects = projects.filter(funder=funder_filter)
        
        # Group by month
        months_data = {}
        for month in range(1, 13):
            month_projects = projects.filter(planned_start_date__month=month).order_by('planned_start_date')
            months_data[month] = {
                'name': date(selected_year, month, 1).strftime('%B'),
                'short_name': date(selected_year, month, 1).strftime('%b'),
                'projects': month_projects,
                'count': month_projects.count(),
                'total_expected': sum(p.expected_learner_count for p in month_projects),
                'total_enrolled': sum(p.total_original_cohort_size for p in month_projects),
                'total_active': sum(p.total_active_learners for p in month_projects),
            }
        
        # Year summary stats
        year_stats = {
            'total_projects': projects.count(),
            'total_expected_learners': sum(p.expected_learner_count for p in projects),
            'total_enrolled': sum(p.total_original_cohort_size for p in projects),
            'total_active': sum(p.total_active_learners for p in projects),
            'total_dropouts': sum(p.total_dropouts for p in projects),
            'by_status': {},
            'by_type': {},
            'by_funder': {},
        }
        
        # Count by status
        for status_code, status_name in TrainingNotification.STATUS_CHOICES:
            count = projects.filter(status=status_code).count()
            if count > 0:
                year_stats['by_status'][status_code] = {'name': status_name, 'count': count}
        
        # Count by type
        for type_code, type_name in TrainingNotification.PROJECT_TYPE_CHOICES:
            count = projects.filter(project_type=type_code).count()
            if count > 0:
                year_stats['by_type'][type_code] = {'name': type_name, 'count': count}
        
        # Count by funder
        for funder_code, funder_name in TrainingNotification.FUNDER_CHOICES:
            count = projects.filter(funder=funder_code).count()
            if count > 0:
                year_stats['by_funder'][funder_code] = {'name': funder_name, 'count': count}
        
        # Calculate overall fill rate and dropout rate
        if year_stats['total_expected_learners'] > 0:
            year_stats['fill_rate'] = round((year_stats['total_enrolled'] / year_stats['total_expected_learners']) * 100, 1)
        else:
            year_stats['fill_rate'] = 0
        
        if year_stats['total_enrolled'] > 0:
            year_stats['dropout_rate'] = round((year_stats['total_dropouts'] / year_stats['total_enrolled']) * 100, 1)
            year_stats['retention_rate'] = 100 - year_stats['dropout_rate']
        else:
            year_stats['dropout_rate'] = 0
            year_stats['retention_rate'] = 100
        
        context = {
            'years': years,
            'selected_year': selected_year,
            'months_data': months_data,
            'year_stats': year_stats,
            'status_choices': TrainingNotification.STATUS_CHOICES,
            'type_choices': TrainingNotification.PROJECT_TYPE_CHOICES,
            'funder_choices': TrainingNotification.FUNDER_CHOICES,
            'current_filters': {
                'status': status_filter,
                'type': project_type_filter,
                'funder': funder_filter,
            },
        }
        
        return render(request, 'not/intakes.html', context)


class NOTAddIntakeView(LoginRequiredMixin, View):
    """Add a new intake/class to a Training Notification project"""
    
    def get(self, request, pk):
        from .models import NOTIntake
        from logistics.models import Cohort
        
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        # Get next intake number
        last_intake = notification.intakes.order_by('-intake_number').first()
        next_number = (last_intake.intake_number + 1) if last_intake else 1
        
        # Get available cohorts (matching qualification if set)
        cohorts = Cohort.objects.filter(status__in=['PLANNED', 'OPEN', 'ACTIVE'])
        if notification.qualification:
            cohorts = cohorts.filter(qualification=notification.qualification)
        
        context = {
            'notification': notification,
            'next_number': next_number,
            'cohorts': cohorts,
            'status_choices': NOTIntake.STATUS_CHOICES,
        }
        
        return render(request, 'not/add_intake.html', context)
    
    def post(self, request, pk):
        from .models import NOTIntake
        from logistics.models import Cohort
        
        notification = get_object_or_404(TrainingNotification, pk=pk)
        
        # Get form data
        intake_number = request.POST.get('intake_number')
        name = request.POST.get('name', '').strip()
        original_cohort_size = request.POST.get('original_cohort_size', 0)
        status = request.POST.get('status', 'PLANNED')
        intake_date = request.POST.get('intake_date') or None
        cohort_id = request.POST.get('cohort')
        notes = request.POST.get('notes', '')
        
        # Validate
        try:
            intake_number = int(intake_number)
            original_cohort_size = int(original_cohort_size)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid intake number or cohort size.')
            return redirect('not_add_intake', pk=pk)
        
        # Check for duplicate intake number
        if notification.intakes.filter(intake_number=intake_number).exists():
            messages.error(request, f'Intake #{intake_number} already exists for this project.')
            return redirect('not_add_intake', pk=pk)
        
        # Get cohort if specified
        cohort = None
        if cohort_id:
            try:
                cohort = Cohort.objects.get(pk=cohort_id)
            except Cohort.DoesNotExist:
                pass
        
        # Create intake
        intake = NOTIntake.objects.create(
            training_notification=notification,
            intake_number=intake_number,
            name=name,
            original_cohort_size=original_cohort_size,
            status=status,
            intake_date=intake_date,
            cohort=cohort,
            notes=notes,
            created_by=request.user
        )
        
        messages.success(request, f'Intake "{intake.name}" added successfully!')
        return redirect('not_detail', pk=pk)


class NOTIntakeUpdateView(LoginRequiredMixin, View):
    """Update an existing intake"""
    
    def get(self, request, pk, intake_pk):
        from .models import NOTIntake
        from logistics.models import Cohort
        
        notification = get_object_or_404(TrainingNotification, pk=pk)
        intake = get_object_or_404(NOTIntake, pk=intake_pk, training_notification=notification)
        
        # Get available cohorts
        cohorts = Cohort.objects.filter(status__in=['PLANNED', 'OPEN', 'ACTIVE'])
        if notification.qualification:
            cohorts = cohorts.filter(qualification=notification.qualification)
        
        context = {
            'notification': notification,
            'intake': intake,
            'cohorts': cohorts,
            'status_choices': NOTIntake.STATUS_CHOICES,
        }
        
        return render(request, 'not/edit_intake.html', context)
    
    def post(self, request, pk, intake_pk):
        from .models import NOTIntake
        from logistics.models import Cohort
        
        notification = get_object_or_404(TrainingNotification, pk=pk)
        intake = get_object_or_404(NOTIntake, pk=intake_pk, training_notification=notification)
        
        # Update fields
        intake.name = request.POST.get('name', intake.name).strip()
        intake.original_cohort_size = int(request.POST.get('original_cohort_size', intake.original_cohort_size))
        intake.status = request.POST.get('status', intake.status)
        intake.intake_date = request.POST.get('intake_date') or None
        intake.notes = request.POST.get('notes', intake.notes)
        
        # Update cohort
        cohort_id = request.POST.get('cohort')
        if cohort_id:
            try:
                intake.cohort = Cohort.objects.get(pk=cohort_id)
            except Cohort.DoesNotExist:
                pass
        else:
            intake.cohort = None
        
        intake.updated_by = request.user
        intake.save()
        
        messages.success(request, f'Intake "{intake.name}" updated successfully!')
        return redirect('not_detail', pk=pk)


class NOTIntakeDeleteView(LoginRequiredMixin, View):
    """Delete an intake"""
    
    def post(self, request, pk, intake_pk):
        from .models import NOTIntake
        
        notification = get_object_or_404(TrainingNotification, pk=pk)
        intake = get_object_or_404(NOTIntake, pk=intake_pk, training_notification=notification)
        
        intake_name = intake.name
        intake.delete()
        
        messages.success(request, f'Intake "{intake_name}" deleted successfully!')
        return redirect('not_detail', pk=pk)


# ============================================================================
# NOT CREATE WIZARD - Multi-step project creation
# ============================================================================

class NOTCreateWizardView(LoginRequiredMixin, View):
    """
    Multi-step wizard for creating a Training Notification project.
    
    Steps:
    1. Basic Info - Project details, client, qualification, dates
    2. Deliverables - Milestones and invoicing percentages
    3. Resources - Required resources and availability
    4. Stakeholders - Team assignments
    5. Review - Summary and confirmation
    """
    
    WIZARD_STEPS = [
        {'number': 1, 'name': 'basic', 'title': 'Basic Information', 'icon': 'clipboard-document-list'},
        {'number': 2, 'name': 'deliverables', 'title': 'Deliverables', 'icon': 'document-check'},
        {'number': 3, 'name': 'resources', 'title': 'Resources', 'icon': 'cube'},
        {'number': 4, 'name': 'stakeholders', 'title': 'Stakeholders', 'icon': 'user-group'},
        {'number': 5, 'name': 'review', 'title': 'Review & Create', 'icon': 'check-circle'},
    ]
    
    def get_wizard_data(self, request):
        """Get wizard data from session"""
        return request.session.get('not_wizard_data', {})
    
    def save_wizard_data(self, request, data):
        """Save wizard data to session"""
        request.session['not_wizard_data'] = data
        request.session.modified = True
    
    def clear_wizard_data(self, request):
        """Clear wizard data from session"""
        if 'not_wizard_data' in request.session:
            del request.session['not_wizard_data']
            request.session.modified = True
    
    def get(self, request, step=1):
        step = int(step)
        if step < 1 or step > 5:
            step = 1
        
        wizard_data = self.get_wizard_data(request)
        
        # Get resources for dropdowns
        resources = get_system_resources()
        
        # Delivery mode choices (inline on model)
        delivery_mode_choices = [
            ('ON_CAMPUS', 'On Campus'),
            ('OFF_SITE', 'Off-Site (Client Premises)'),
            ('ONLINE', 'Online/Virtual'),
            ('BLENDED', 'Blended Learning'),
            ('WORKPLACE', 'Workplace-Based'),
        ]
        
        context = {
            'current_step': step,
            'steps': self.WIZARD_STEPS,
            'wizard_data': wizard_data,
            'project_types': TrainingNotification.PROJECT_TYPE_CHOICES,
            'funder_choices': TrainingNotification.FUNDER_CHOICES,
            'priority_choices': TrainingNotification.PRIORITY_CHOICES,
            'status_choices': TrainingNotification.STATUS_CHOICES,
            'delivery_mode_choices': delivery_mode_choices,
            'deliverable_types': NOTDeliverable.DELIVERABLE_TYPE_CHOICES,
            'deliverable_status_choices': NOTDeliverable.STATUS_CHOICES,
            'resource_types': NOTResourceRequirement.RESOURCE_TYPE_CHOICES,
            'resource_status_choices': NOTResourceRequirement.STATUS_CHOICES,
            'department_choices': NOTStakeholder.DEPARTMENT_CHOICES,
            'role_choices': NOTStakeholder.ROLE_IN_PROJECT_CHOICES,
            **resources,
        }
        
        # Add step-specific data
        if step == 2:
            # Pre-populate default deliverables if none exist
            if 'deliverables' not in wizard_data:
                wizard_data['deliverables'] = self._get_default_deliverables(wizard_data)
                self.save_wizard_data(request, wizard_data)
                context['wizard_data'] = wizard_data
        
        return render(request, 'not/wizard/create_wizard.html', context)
    
    def post(self, request, step=1):
        step = int(step)
        wizard_data = self.get_wizard_data(request)
        action = request.POST.get('action', 'next')
        
        if action == 'cancel':
            self.clear_wizard_data(request)
            messages.info(request, 'Project creation cancelled.')
            return redirect('not_list')
        
        # Save current step data
        if step == 1:
            wizard_data = self._save_step1(request, wizard_data)
        elif step == 2:
            wizard_data = self._save_step2(request, wizard_data)
        elif step == 3:
            wizard_data = self._save_step3(request, wizard_data)
        elif step == 4:
            wizard_data = self._save_step4(request, wizard_data)
        elif step == 5:
            if action == 'create':
                # Final step - create the NOT and all related objects
                return self._create_not(request, wizard_data)
        
        self.save_wizard_data(request, wizard_data)
        
        # Navigate
        if action == 'back' and step > 1:
            return redirect('not_wizard_step', step=step - 1)
        elif action == 'next' and step < 5:
            return redirect('not_wizard_step', step=step + 1)
        elif action == 'save_draft':
            return self._save_as_draft(request, wizard_data)
        
        return redirect('not_wizard_step', step=step)
    
    def _save_step1(self, request, data):
        """Save basic information step"""
        data['basic'] = {
            'title': request.POST.get('title', ''),
            'project_type': request.POST.get('project_type', ''),
            'funder': request.POST.get('funder', ''),
            'priority': request.POST.get('priority', 'MEDIUM'),
            'client_name': request.POST.get('client_name', ''),
            'corporate_client_id': request.POST.get('corporate_client', ''),
            'tender_reference': request.POST.get('tender_reference', ''),
            'contract_value': request.POST.get('contract_value', ''),
            'qualification_id': request.POST.get('qualification', ''),
            'program_description': request.POST.get('program_description', ''),
            'expected_learner_count': request.POST.get('expected_learner_count', ''),
            'learner_source': request.POST.get('learner_source', ''),
            'recruitment_notes': request.POST.get('recruitment_notes', ''),
            'planned_start_date': request.POST.get('planned_start_date', ''),
            'planned_end_date': request.POST.get('planned_end_date', ''),
            'duration_months': request.POST.get('duration_months', ''),
            'delivery_campus_id': request.POST.get('delivery_campus', ''),
            'delivery_mode': request.POST.get('delivery_mode', ''),
            'delivery_address': request.POST.get('delivery_address', ''),
            'description': request.POST.get('description', ''),
        }
        return data
    
    def _save_step2(self, request, data):
        """Save deliverables step"""
        deliverables = []
        
        # Parse deliverables from form
        titles = request.POST.getlist('deliverable_title[]')
        types = request.POST.getlist('deliverable_type[]')
        percentages = request.POST.getlist('deliverable_percentage[]')
        due_dates = request.POST.getlist('deliverable_due_date[]')
        descriptions = request.POST.getlist('deliverable_description[]')
        
        for i in range(len(titles)):
            if titles[i].strip():
                deliverables.append({
                    'title': titles[i].strip(),
                    'deliverable_type': types[i] if i < len(types) else 'MILESTONE',
                    'percentage': percentages[i] if i < len(percentages) else '0',
                    'due_date': due_dates[i] if i < len(due_dates) else '',
                    'description': descriptions[i] if i < len(descriptions) else '',
                })
        
        data['deliverables'] = deliverables
        return data
    
    def _save_step3(self, request, data):
        """Save resources step"""
        resources = []
        
        # Parse resources from form
        types = request.POST.getlist('resource_type[]')
        descriptions = request.POST.getlist('resource_description[]')
        quantities = request.POST.getlist('resource_quantity[]')
        costs = request.POST.getlist('resource_cost[]')
        
        for i in range(len(types)):
            if types[i] and descriptions[i].strip():
                resources.append({
                    'resource_type': types[i],
                    'description': descriptions[i].strip(),
                    'quantity_required': quantities[i] if i < len(quantities) else '1',
                    'estimated_cost': costs[i] if i < len(costs) else '',
                })
        
        data['resources'] = resources
        return data
    
    def _save_step4(self, request, data):
        """Save stakeholders step"""
        stakeholders = []
        
        # Parse stakeholders from form
        user_ids = request.POST.getlist('stakeholder_user[]')
        departments = request.POST.getlist('stakeholder_department[]')
        roles = request.POST.getlist('stakeholder_role[]')
        responsibilities = request.POST.getlist('stakeholder_responsibilities[]')
        
        for i in range(len(user_ids)):
            if user_ids[i]:
                stakeholders.append({
                    'user_id': user_ids[i],
                    'department': departments[i] if i < len(departments) else '',
                    'role_in_project': roles[i] if i < len(roles) else '',
                    'responsibilities': responsibilities[i] if i < len(responsibilities) else '',
                })
        
        data['stakeholders'] = stakeholders
        return data
    
    def _get_default_deliverables(self, data):
        """Get default deliverables based on project type"""
        project_type = data.get('basic', {}).get('project_type', '')
        start_date = data.get('basic', {}).get('planned_start_date', '')
        
        defaults = [
            {'title': 'Learner Registration', 'deliverable_type': 'REGISTRATION', 'percentage': '20', 'due_date': '', 'description': 'Complete learner enrollment and registration with SETA'},
            {'title': 'Induction & Commencement', 'deliverable_type': 'MILESTONE', 'percentage': '10', 'due_date': '', 'description': 'Project kickoff and learner induction'},
            {'title': 'Mid-term Assessment', 'deliverable_type': 'ASSESSMENT', 'percentage': '20', 'due_date': '', 'description': 'Formative assessments and progress review'},
            {'title': 'Final Assessment', 'deliverable_type': 'ASSESSMENT', 'percentage': '25', 'due_date': '', 'description': 'Summative assessments completion'},
            {'title': 'Moderation', 'deliverable_type': 'MODERATION', 'percentage': '10', 'due_date': '', 'description': 'Internal and external moderation'},
            {'title': 'Certification', 'deliverable_type': 'CERTIFICATION', 'percentage': '15', 'due_date': '', 'description': 'Certificate issuance and project closeout'},
        ]
        
        return defaults
    
    def _create_not(self, request, data):
        """Create the Training Notification and all related objects"""
        from django.db import transaction
        from decimal import Decimal
        
        try:
            with transaction.atomic():
                basic = data.get('basic', {})
                
                # Create the main NOT
                not_obj = TrainingNotification(
                    title=basic.get('title', ''),
                    project_type=basic.get('project_type', ''),
                    funder=basic.get('funder', ''),
                    priority=basic.get('priority', 'MEDIUM'),
                    status='DRAFT',
                    client_name=basic.get('client_name', ''),
                    tender_reference=basic.get('tender_reference', ''),
                    program_description=basic.get('program_description', ''),
                    learner_source=basic.get('learner_source', ''),
                    recruitment_notes=basic.get('recruitment_notes', ''),
                    delivery_mode=basic.get('delivery_mode', ''),
                    delivery_address=basic.get('delivery_address', ''),
                    description=basic.get('description', ''),
                    created_by=request.user,
                )
                
                # Handle foreign keys
                if basic.get('corporate_client_id'):
                    not_obj.corporate_client_id = basic['corporate_client_id']
                if basic.get('qualification_id'):
                    not_obj.qualification_id = basic['qualification_id']
                if basic.get('delivery_campus_id'):
                    not_obj.delivery_campus_id = basic['delivery_campus_id']
                
                # Handle numeric fields
                if basic.get('contract_value'):
                    not_obj.contract_value = Decimal(basic['contract_value'])
                if basic.get('expected_learner_count'):
                    not_obj.expected_learner_count = int(basic['expected_learner_count'])
                if basic.get('duration_months'):
                    not_obj.duration_months = int(basic['duration_months'])
                
                # Handle date fields
                if basic.get('planned_start_date'):
                    not_obj.planned_start_date = basic['planned_start_date']
                if basic.get('planned_end_date'):
                    not_obj.planned_end_date = basic['planned_end_date']
                
                not_obj.save()
                
                # Create deliverables
                for d in data.get('deliverables', []):
                    deliverable = NOTDeliverable(
                        training_notification=not_obj,
                        title=d.get('title', ''),
                        deliverable_type=d.get('deliverable_type', 'MILESTONE'),
                        description=d.get('description', ''),
                        status='PENDING',
                        created_by=request.user,
                    )
                    if d.get('due_date'):
                        deliverable.due_date = d['due_date']
                    else:
                        # Default to planned end date if no specific due date
                        deliverable.due_date = basic.get('planned_end_date') or timezone.now().date()
                    deliverable.save()
                
                # Create resource requirements
                for r in data.get('resources', []):
                    resource = NOTResourceRequirement(
                        training_notification=not_obj,
                        resource_type=r.get('resource_type', 'OTHER'),
                        description=r.get('description', ''),
                        status='REQUIRED',
                        created_by=request.user,
                    )
                    if r.get('quantity_required'):
                        resource.quantity_required = int(r['quantity_required'])
                    if r.get('estimated_cost'):
                        resource.estimated_cost = Decimal(r['estimated_cost'])
                    resource.save()
                
                # Create stakeholders
                for s in data.get('stakeholders', []):
                    if s.get('user_id'):
                        stakeholder = NOTStakeholder(
                            training_notification=not_obj,
                            user_id=s['user_id'],
                            department=s.get('department', 'ACADEMIC'),
                            role_in_project=s.get('role_in_project', 'SUPPORT'),
                            responsibilities=s.get('responsibilities', ''),
                            created_by=request.user,
                        )
                        stakeholder.save()
                
                # Clear wizard data
                self.clear_wizard_data(request)
                
                messages.success(request, f'Project "{not_obj.title}" created successfully with {len(data.get("deliverables", []))} deliverables!')
                return redirect('not_detail', pk=not_obj.pk)
        
        except Exception as e:
            messages.error(request, f'Error creating project: {str(e)}')
            return redirect('not_wizard_step', step=5)
    
    def _save_as_draft(self, request, data):
        """Save the current state as a draft NOT"""
        basic = data.get('basic', {})
        
        if not basic.get('title'):
            messages.error(request, 'Please provide a project title to save as draft.')
            return redirect('not_wizard_step', step=1)
        
        # Create minimal NOT in draft status
        not_obj = TrainingNotification(
            title=basic.get('title', 'Untitled Draft'),
            project_type=basic.get('project_type', ''),
            funder=basic.get('funder', ''),
            status='DRAFT',
            description=f"Draft saved from wizard. Data: {data}",
            created_by=request.user,
        )
        not_obj.save()
        
        self.clear_wizard_data(request)
        messages.success(request, f'Draft "{not_obj.title}" saved. You can continue editing later.')
        return redirect('not_detail', pk=not_obj.pk)


class NOTWizardStartView(LoginRequiredMixin, View):
    """Start a new wizard, clearing any previous session data"""
    
    def get(self, request):
        # Clear any existing wizard data
        if 'not_wizard_data' in request.session:
            del request.session['not_wizard_data']
            request.session.modified = True
        return redirect('not_wizard_step', step=1)


# =============================================================================
# NOT PROJECT LEARNER TRACKING VIEWS
# =============================================================================

class NOTLearnersView(LoginRequiredMixin, View):
    """View all learners linked to a project via NOTIntake → Cohort → Enrollment"""
    
    def get(self, request, pk):
        training_notification = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        from core.services.learner_progress import LearnerProgressService, DocumentComplianceService
        
        progress_service = LearnerProgressService(training_notification)
        compliance_service = DocumentComplianceService(training_notification)
        
        # Get filter parameters
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        compliance_filter = request.GET.get('compliance', '')
        
        # Get enrollments with optional filters
        enrollments = progress_service.get_project_learners(include_progress=False)
        
        if search:
            enrollments = enrollments.filter(
                Q(learner__user__first_name__icontains=search) |
                Q(learner__user__last_name__icontains=search) |
                Q(learner__user__email__icontains=search) |
                Q(learner__id_number__icontains=search)
            )
        
        if status_filter:
            enrollments = enrollments.filter(status=status_filter)
        
        # Get summary stats
        progress_summary = progress_service.get_progress_summary()
        assessment_summary = progress_service.get_assessment_summary()
        compliance_summary = compliance_service.get_project_document_compliance()
        
        # Build learner list with progress
        learners_data = []
        for enrollment in enrollments:
            learner_compliance = compliance_service.get_learner_document_status(enrollment.learner)
            progress_detail = progress_service.get_learner_progress_detail(enrollment)
            
            learners_data.append({
                'enrollment': enrollment,
                'learner': enrollment.learner,
                'progress': progress_detail,
                'compliance': learner_compliance,
            })
        
        context = {
            'training_notification': training_notification,
            'not': training_notification,  # Alias for template compatibility
            'learners': learners_data,
            'progress_summary': progress_summary,
            'assessment_summary': assessment_summary,
            'compliance_summary': compliance_summary,
            'search': search,
            'status_filter': status_filter,
            'compliance_filter': compliance_filter,
            'status_choices': [
                ('ENROLLED', 'Enrolled'),
                ('ACTIVE', 'Active'),
                ('IN_PROGRESS', 'In Progress'),
                ('COMPLETED', 'Completed'),
                ('DROPPED', 'Dropped'),
                ('WITHDRAWN', 'Withdrawn'),
            ],
        }
        
        return render(request, 'not/learners.html', context)


class NOTLearnerDetailView(LoginRequiredMixin, View):
    """Detailed view of a specific learner's progress within a project"""
    
    def get(self, request, pk, learner_pk):
        from learners.models import Learner
        from core.services.learner_progress import LearnerProgressService, DocumentComplianceService
        from core.models_not_documents import NOTLearnerDocument
        from academics.models import Enrollment
        
        training_notification = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        learner = get_object_or_404(Learner, pk=learner_pk)
        
        progress_service = LearnerProgressService(training_notification)
        compliance_service = DocumentComplianceService(training_notification)
        
        # Get enrollment for this learner in this project
        enrollments = progress_service.get_project_learners(include_progress=False)
        enrollment = enrollments.filter(learner=learner).first()
        
        if not enrollment:
            messages.error(request, 'This learner is not enrolled in this project.')
            return redirect('not_learners', pk=pk)
        
        # Get detailed progress
        progress_detail = progress_service.get_learner_progress_detail(enrollment)
        
        # Get document compliance
        document_status = compliance_service.get_learner_document_status(learner)
        
        # Get all documents for this learner
        documents = NOTLearnerDocument.objects.filter(
            training_notification=training_notification,
            learner=learner
        ).select_related('document_type', 'verified_by')
        
        context = {
            'training_notification': training_notification,
            'not': training_notification,
            'learner': learner,
            'enrollment': enrollment,
            'progress': progress_detail,
            'document_status': document_status,
            'documents': documents,
        }
        
        return render(request, 'not/learner_detail.html', context)


class NOTLearnerDocumentsView(LoginRequiredMixin, View):
    """Manage documents for a specific learner in a project"""
    
    def get(self, request, pk, learner_pk):
        from learners.models import Learner
        from core.models_not_documents import NOTLearnerDocument, NOTLearnerDocumentType
        from core.services.learner_progress import DocumentComplianceService
        
        training_notification = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        learner = get_object_or_404(Learner, pk=learner_pk)
        
        # Get all document types applicable to this project
        document_types = NOTLearnerDocumentType.get_all_for_project(training_notification)
        
        # Get existing documents
        existing_docs = NOTLearnerDocument.objects.filter(
            training_notification=training_notification,
            learner=learner
        ).select_related('document_type', 'verified_by')
        
        existing_by_type = {doc.document_type_id: doc for doc in existing_docs}
        
        # Build document list with status
        documents = []
        for doc_type in document_types:
            existing = existing_by_type.get(doc_type.id)
            documents.append({
                'type': doc_type,
                'document': existing,
                'is_required': doc_type.is_required_for_project(training_notification),
                'status': existing.status if existing else 'PENDING',
            })
        
        # Get compliance summary
        compliance_service = DocumentComplianceService(training_notification)
        document_status = compliance_service.get_learner_document_status(learner)
        
        context = {
            'training_notification': training_notification,
            'not': training_notification,
            'learner': learner,
            'documents': documents,
            'document_status': document_status,
        }
        
        return render(request, 'not/learner_documents.html', context)
    
    def post(self, request, pk, learner_pk):
        from learners.models import Learner
        from core.models_not_documents import NOTLearnerDocument, NOTLearnerDocumentType
        
        training_notification = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        learner = get_object_or_404(Learner, pk=learner_pk)
        
        document_type_id = request.POST.get('document_type')
        uploaded_file = request.FILES.get('file')
        
        if not document_type_id or not uploaded_file:
            messages.error(request, 'Please select a document type and upload a file.')
            return redirect('not_learner_documents', pk=pk, learner_pk=learner_pk)
        
        document_type = get_object_or_404(NOTLearnerDocumentType, pk=document_type_id)
        
        # Check file type
        file_ext = uploaded_file.name.split('.')[-1].lower()
        accepted_types = [ext.strip().lstrip('.').lower() for ext in document_type.accepted_file_types.split(',')]
        
        if file_ext not in accepted_types:
            messages.error(request, f'Invalid file type. Accepted types: {document_type.accepted_file_types}')
            return redirect('not_learner_documents', pk=pk, learner_pk=learner_pk)
        
        # Check file size
        if uploaded_file.size > document_type.max_file_size_mb * 1024 * 1024:
            messages.error(request, f'File too large. Maximum size: {document_type.max_file_size_mb}MB')
            return redirect('not_learner_documents', pk=pk, learner_pk=learner_pk)
        
        # Create or update document
        document, created = NOTLearnerDocument.objects.update_or_create(
            training_notification=training_notification,
            learner=learner,
            document_type=document_type,
            defaults={
                'file': uploaded_file,
                'status': 'UPLOADED',
                'reference_number': request.POST.get('reference_number', ''),
                'issue_date': request.POST.get('issue_date') or None,
                'expiry_date': request.POST.get('expiry_date') or None,
                'notes': request.POST.get('notes', ''),
                'created_by': request.user,
            }
        )
        
        messages.success(request, f'Document "{document_type.name}" uploaded successfully.')
        return redirect('not_learner_documents', pk=pk, learner_pk=learner_pk)


class NOTVerifyDocumentView(LoginRequiredMixin, View):
    """Verify or reject a learner document"""
    
    def post(self, request, pk, document_pk):
        from core.models_not_documents import NOTLearnerDocument
        
        training_notification = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        document = get_object_or_404(
            NOTLearnerDocument, 
            pk=document_pk,
            training_notification=training_notification
        )
        
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'verify':
            document.verify(request.user, notes)
            messages.success(request, 'Document verified successfully.')
        elif action == 'reject':
            reason = request.POST.get('reason', '')
            if not reason:
                messages.error(request, 'Please provide a rejection reason.')
                return redirect('not_learner_documents', pk=pk, learner_pk=document.learner.pk)
            document.reject(request.user, reason)
            messages.warning(request, 'Document rejected.')
        
        return redirect('not_learner_documents', pk=pk, learner_pk=document.learner.pk)


class NOTProjectDocumentsView(LoginRequiredMixin, View):
    """Manage project-level documents"""
    
    def get(self, request, pk):
        from core.models_not_documents import NOTProjectDocument
        
        training_notification = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        # Get all project documents grouped by type
        documents = NOTProjectDocument.objects.filter(
            training_notification=training_notification
        ).select_related('reviewed_by', 'created_by').order_by('document_type', '-version')
        
        # Group by document type
        docs_by_type = {}
        for doc in documents:
            if doc.document_type not in docs_by_type:
                docs_by_type[doc.document_type] = []
            docs_by_type[doc.document_type].append(doc)
        
        context = {
            'training_notification': training_notification,
            'not': training_notification,
            'documents': documents,
            'documents_by_type': docs_by_type,
            'document_types': NOTProjectDocument.DOCUMENT_TYPE_CHOICES,
        }
        
        return render(request, 'not/project_documents.html', context)
    
    def post(self, request, pk):
        from core.models_not_documents import NOTProjectDocument
        
        training_notification = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            messages.error(request, 'Please upload a file.')
            return redirect('not_project_documents', pk=pk)
        
        document = NOTProjectDocument.objects.create(
            training_notification=training_notification,
            document_type=request.POST.get('document_type'),
            title=request.POST.get('title', uploaded_file.name),
            description=request.POST.get('description', ''),
            file=uploaded_file,
            reference_number=request.POST.get('reference_number', ''),
            issue_date=request.POST.get('issue_date') or None,
            expiry_date=request.POST.get('expiry_date') or None,
            status='PENDING_REVIEW',
            created_by=request.user,
        )
        
        messages.success(request, f'Document "{document.title}" uploaded successfully.')
        return redirect('not_project_documents', pk=pk)


class NOTDocumentTypeSettingsView(LoginRequiredMixin, View):
    """Manage document type settings (admin functionality)"""
    
    def get(self, request):
        from core.models_not_documents import NOTLearnerDocumentType
        
        # Get all document types
        active_types = NOTLearnerDocumentType.objects.filter(is_active=True).order_by('category', 'order', 'name')
        archived_types = NOTLearnerDocumentType.objects.filter(is_active=False).order_by('category', 'name')
        
        context = {
            'active_types': active_types,
            'archived_types': archived_types,
            'categories': NOTLearnerDocumentType.CATEGORY_CHOICES,
        }
        
        return render(request, 'not/document_type_settings.html', context)
    
    def post(self, request):
        from core.models_not_documents import NOTLearnerDocumentType
        
        action = request.POST.get('action')
        
        if action == 'create':
            doc_type = NOTLearnerDocumentType.objects.create(
                code=request.POST.get('code'),
                name=request.POST.get('name'),
                category=request.POST.get('category', 'OTHER'),
                description=request.POST.get('description', ''),
                is_required=request.POST.get('is_required') == 'on',
                has_expiry=request.POST.get('has_expiry') == 'on',
                default_validity_days=request.POST.get('default_validity_days') or None,
                expiry_warning_days=request.POST.get('expiry_warning_days', 30),
                accepted_file_types=request.POST.get('accepted_file_types', '.pdf,.doc,.docx,.jpg,.jpeg,.png'),
                max_file_size_mb=request.POST.get('max_file_size_mb', 10),
            )
            messages.success(request, f'Document type "{doc_type.name}" created successfully.')
        
        elif action == 'archive':
            doc_type_id = request.POST.get('document_type_id')
            doc_type = get_object_or_404(NOTLearnerDocumentType, pk=doc_type_id)
            doc_type.archive()
            messages.success(request, f'Document type "{doc_type.name}" archived.')
        
        elif action == 'restore':
            doc_type_id = request.POST.get('document_type_id')
            doc_type = get_object_or_404(NOTLearnerDocumentType, pk=doc_type_id)
            doc_type.restore()
            messages.success(request, f'Document type "{doc_type.name}" restored.')
        
        elif action == 'update':
            doc_type_id = request.POST.get('document_type_id')
            doc_type = get_object_or_404(NOTLearnerDocumentType, pk=doc_type_id)
            
            doc_type.name = request.POST.get('name', doc_type.name)
            doc_type.category = request.POST.get('category', doc_type.category)
            doc_type.description = request.POST.get('description', doc_type.description)
            doc_type.is_required = request.POST.get('is_required') == 'on'
            doc_type.has_expiry = request.POST.get('has_expiry') == 'on'
            doc_type.default_validity_days = request.POST.get('default_validity_days') or None
            doc_type.expiry_warning_days = int(request.POST.get('expiry_warning_days', 30))
            doc_type.accepted_file_types = request.POST.get('accepted_file_types', doc_type.accepted_file_types)
            doc_type.max_file_size_mb = int(request.POST.get('max_file_size_mb', 10))
            doc_type.save()
            
            messages.success(request, f'Document type "{doc_type.name}" updated.')
        
        return redirect('not_document_type_settings')


class NOTExpiringDocumentsView(LoginRequiredMixin, View):
    """View and manage expiring documents across all projects"""
    
    def get(self, request):
        from core.models_not_documents import NOTLearnerDocument
        
        days_ahead = int(request.GET.get('days', 30))
        cutoff_date = date.today() + timedelta(days=days_ahead)
        
        # Get all expiring documents
        expiring_documents = NOTLearnerDocument.objects.filter(
            expiry_date__lte=cutoff_date,
            expiry_date__gte=date.today(),
            status='VERIFIED'
        ).select_related(
            'training_notification', 'learner', 'document_type'
        ).order_by('expiry_date')
        
        # Get expired documents
        expired_documents = NOTLearnerDocument.objects.filter(
            expiry_date__lt=date.today()
        ).exclude(status='EXPIRED').select_related(
            'training_notification', 'learner', 'document_type'
        ).order_by('expiry_date')
        
        context = {
            'expiring_documents': expiring_documents,
            'expired_documents': expired_documents,
            'days_ahead': days_ahead,
        }
        
        return render(request, 'not/expiring_documents.html', context)
    
    def post(self, request):
        """Create tasks for expiring documents"""
        from core.models_not_documents import NOTLearnerDocument
        from core.services.learner_progress import DocumentComplianceService
        
        # Get all projects
        projects = TrainingNotification.objects.filter(
            status='IN_PROGRESS',
            is_deleted=False
        )
        
        total_tasks = 0
        for project in projects:
            service = DocumentComplianceService(project)
            total_tasks += service.create_expiry_warning_tasks()
        
        messages.success(request, f'Created {total_tasks} expiry warning tasks.')
        return redirect('not_expiring_documents')


# =============================================================================
# Attendance Register Views
# =============================================================================

class NOTAttendanceRegisterView(LoginRequiredMixin, View):
    """
    View monthly attendance register for a NOT project.
    Shows attendance grid, verification status, and stipend calculations.
    """
    
    def get(self, request, pk, year, month):
        from datetime import date
        import calendar
        from learners.services.attendance_register import AttendanceRegisterService
        
        not_project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        # Validate month/year
        if month < 1 or month > 12:
            messages.error(request, 'Invalid month specified.')
            return redirect('not_detail', pk=pk)
        
        service = AttendanceRegisterService(not_project, year, month)
        data = service.get_register_data()
        
        # Calculate prev/next month for navigation
        if month == 1:
            prev_month = {'year': year - 1, 'month': 12, 'month_name': 'December'}
        else:
            prev_month = {'year': year, 'month': month - 1, 'month_name': calendar.month_name[month - 1]}
        
        if month == 12:
            next_month = {'year': year + 1, 'month': 1, 'month_name': 'January'}
        else:
            next_month = {'year': year, 'month': month + 1, 'month_name': calendar.month_name[month + 1]}
        
        # Don't show next month if it's in the future
        today = date.today()
        next_date = date(next_month['year'], next_month['month'], 1)
        if next_date > today:
            next_month = None
        
        context = {
            'register': data,
            'notification': not_project,
            'not_project': not_project,
            'year': year,
            'month': month,
            'prev_month': prev_month,
            'next_month': next_month,
        }
        
        return render(request, 'not/attendance_register.html', context)


class NOTAttendanceRegisterExportView(LoginRequiredMixin, View):
    """
    Export attendance register as PDF or Excel.
    """
    
    def get(self, request, pk, year, month, format):
        from django.http import HttpResponse
        from learners.services.attendance_register import AttendanceRegisterService
        
        not_project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        # Validate month/year
        if month < 1 or month > 12:
            messages.error(request, 'Invalid month specified.')
            return redirect('not_detail', pk=pk)
        
        service = AttendanceRegisterService(not_project, year, month)
        
        try:
            if format == 'pdf':
                content = service.generate_pdf()
                response = HttpResponse(content, content_type='application/pdf')
                filename = f"attendance_register_{not_project.reference_number}_{year}_{month:02d}.pdf"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
            elif format == 'excel':
                content = service.generate_excel()
                response = HttpResponse(
                    content, 
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                filename = f"attendance_register_{not_project.reference_number}_{year}_{month:02d}.xlsx"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
            else:
                messages.error(request, 'Invalid export format. Use "pdf" or "excel".')
                return redirect('not_attendance_register', pk=pk, year=year, month=month)
            
            return response
            
        except ImportError as e:
            messages.error(request, str(e))
            return redirect('not_attendance_register', pk=pk, year=year, month=month)


class NOTGenerateAttendanceDeliverableView(LoginRequiredMixin, View):
    """
    Generate attendance register and save as NOTDeliverable.
    Creates both PDF and Excel versions and attaches to deliverable.
    """
    
    def post(self, request, pk, year, month):
        from learners.services.attendance_register import AttendanceRegisterService
        import calendar
        
        not_project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        # Validate month/year
        if month < 1 or month > 12:
            messages.error(request, 'Invalid month specified.')
            return redirect('not_detail', pk=pk)
        
        service = AttendanceRegisterService(not_project, year, month)
        
        try:
            # Generate PDF
            pdf_content = service.generate_pdf()
            
            # Create deliverable
            deliverable = service.create_deliverable_record(pdf_content=pdf_content)
            
            month_name = calendar.month_name[month]
            messages.success(
                request, 
                f'Attendance register for {month_name} {year} created as project deliverable.'
            )
            
        except ImportError as e:
            messages.warning(
                request, 
                f'Could not generate PDF: {e}. Deliverable created without attachment.'
            )
            deliverable = service.create_deliverable_record()
        except Exception as e:
            messages.error(request, f'Error generating attendance register: {e}')
            return redirect('not_detail', pk=pk)
        
        return redirect('not_detail', pk=pk)


class NOTAttendanceRegisterSelectView(LoginRequiredMixin, View):
    """
    View to select month/year for attendance register generation.
    Shows available months based on project dates.
    """
    
    def get(self, request, pk):
        from datetime import date
        import calendar
        from learners.models import WorkplaceAttendance
        from corporate.models import WorkplacePlacement
        
        not_project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        # Calculate available months (from project start to current month)
        today = date.today()
        start_date = not_project.planned_start_date or not_project.created_at.date()
        
        # If start date is after today, use today's month
        if start_date > today:
            start_date = today
        
        # Get current year for quick access grid
        current_year = today.year
        current_month = today.month
        
        # Generate years list (from project start year to current year)
        years = list(range(start_date.year, current_year + 1))
        
        # Get learner count
        placements = WorkplacePlacement.objects.filter(
            training_notification=not_project,
            status__in=['ACTIVE', 'COMPLETED']
        )
        learner_count = placements.count()
        
        # Generate months for quick access grid with record counts
        months = []
        for m in range(1, 13):
            month_start = date(current_year, m, 1)
            if m == 12:
                month_end = date(current_year, 12, 31)
            else:
                month_end = date(current_year, m + 1, 1)
            
            # Count attendance records for this month
            record_count = WorkplaceAttendance.objects.filter(
                placement__in=placements,
                date__gte=month_start,
                date__lt=month_end
            ).count()
            
            months.append({
                'num': m,
                'short_name': calendar.month_abbr[m],
                'has_data': record_count > 0,
                'record_count': record_count,
            })
        
        # Get recent deliverables
        recent_deliverables = NOTDeliverable.objects.filter(
            training_notification=not_project,
            title__icontains='Attendance Register'
        ).order_by('-created_at')[:5]
        
        context = {
            'notification': not_project,
            'not_project': not_project,
            'current_year': current_year,
            'current_month': current_month,
            'years': years,
            'months': months,
            'learner_count': learner_count,
            'recent_deliverables': recent_deliverables,
        }
        
        return render(request, 'not/attendance_register_select.html', context)


class NOTSetupAttendanceDeliverables(LoginRequiredMixin, View):
    """
    Set up recurring monthly attendance register deliverables for a NOT project.
    """
    
    def post(self, request, pk):
        from learners.services.attendance_register import AttendanceRegisterService
        
        not_project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        try:
            parent_deliverable = AttendanceRegisterService.setup_recurring_deliverables(not_project)
            messages.success(
                request, 
                f'Monthly attendance register deliverables set up. {parent_deliverable.recurring_instances.count()} instances created.'
            )
        except Exception as e:
            messages.error(request, f'Error setting up deliverables: {e}')
        
        return redirect('not_detail', pk=pk)
