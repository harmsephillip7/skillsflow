"""
Corporate Portal Views - Client Access to Services & Deliverables

Views for corporate clients to:
- See their active service subscriptions
- Track service delivery progress and milestones
- View learner progress (for training services)
- Access meeting minutes and documents
- View upcoming deadlines and reminders
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView, ListView
from django.db.models import Count, Q, Avg, Sum, Case, When, Value, IntegerField
from django.utils import timezone
from django.http import JsonResponse, Http404
from datetime import date, timedelta, datetime

from corporate.models import (
    CorporateClient, CorporateContact, CorporateEmployee,
    ClientServiceSubscription, ServiceDeliveryProject, ProjectMilestone, MilestoneTask,
    ProjectDocument, DeadlineReminder, CommitteeMeeting, Committee,
    ServiceOffering, GrantProject, GrantClaim
)
from learners.models import Learner
from academics.models import Enrollment


class CorporatePortalMixin:
    """
    Mixin to get the corporate client for the current user.
    Super admins can view any client by passing ?client_id=X in the URL.
    """
    def get_corporate_client(self):
        """
        Get the CorporateClient linked to the current user.
        Super admins can view any client via URL parameter.
        """
        user = self.request.user
        
        # Super admin can view any client
        if user.is_superuser:
            # Check for client_id in URL
            client_id = self.request.GET.get('client_id')
            if client_id:
                try:
                    return CorporateClient.objects.get(pk=client_id)
                except CorporateClient.DoesNotExist:
                    pass
            # Default to first active client with subscriptions for demo
            return CorporateClient.objects.filter(
                status='ACTIVE',
                service_subscriptions__isnull=False
            ).distinct().first()
        
        # Regular users - check for linked contact
        contact = CorporateContact.objects.filter(user=user, is_active=True).first()
        if contact:
            return contact.client
        return None
    
    def get_corporate_contact(self):
        """Get the CorporateContact record for the current user."""
        user = self.request.user
        
        # Super admin - return None (they're not a contact)
        if user.is_superuser:
            return None
            
        return CorporateContact.objects.filter(user=user, is_active=True).first()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add admin context for client switcher
        if self.request.user.is_superuser:
            context['is_admin_view'] = True
            context['all_clients'] = CorporateClient.objects.filter(
                status='ACTIVE'
            ).order_by('company_name')[:20]
            context['selected_client_id'] = self.request.GET.get('client_id')
        
        return context


class CorporatePortalDashboardView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    Corporate Client Dashboard - Overview of all services and progress.
    
    Shows:
    - Active services summary with progress
    - Upcoming deadlines
    - Recent activity
    - Quick stats on learners (for training services)
    """
    template_name = 'portals/corporate/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        contact = self.get_corporate_contact()
        
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        context['contact'] = contact
        context['today'] = date.today()
        
        # Active service subscriptions
        active_subscriptions = ClientServiceSubscription.objects.filter(
            client=client,
            status='ACTIVE'
        ).select_related('service', 'service__category', 'assigned_consultant')
        
        # Get delivery projects for active subscriptions
        subscription_data = []
        for subscription in active_subscriptions:
            project = getattr(subscription, 'delivery_project', None)
            if not project:
                # Try to find linked project
                project = ServiceDeliveryProject.objects.filter(
                    subscription=subscription
                ).first()
            
            subscription_data.append({
                'subscription': subscription,
                'project': project,
                'progress': project.progress_percentage if project else 0,
                'health': project.health if project else 'GREEN',
                'milestones_total': project.milestones.count() if project else 0,
                'milestones_completed': project.milestones.filter(status='COMPLETED').count() if project else 0,
            })
        
        context['subscriptions'] = subscription_data
        context['active_services_count'] = len(subscription_data)
        
        # Overall progress
        total_progress = sum(s['progress'] for s in subscription_data)
        context['overall_progress'] = round(total_progress / len(subscription_data)) if subscription_data else 0
        
        # Upcoming deadlines (next 30 days)
        upcoming_deadlines = DeadlineReminder.objects.filter(
            client=client,
            deadline_date__gte=date.today(),
            deadline_date__lte=date.today() + timedelta(days=30),
            is_completed=False
        ).order_by('deadline_date')[:5]
        context['upcoming_deadlines'] = upcoming_deadlines
        
        # Overdue items
        overdue_count = DeadlineReminder.objects.filter(
            client=client,
            deadline_date__lt=date.today(),
            is_completed=False
        ).count()
        context['overdue_count'] = overdue_count
        
        # Learner statistics (for training-related services)
        employees = CorporateEmployee.objects.filter(client=client, is_current=True)
        linked_learners = employees.filter(learner__isnull=False)
        
        # Get enrollment stats
        learner_ids = linked_learners.values_list('learner_id', flat=True)
        enrollments = Enrollment.objects.filter(learner_id__in=learner_ids)
        
        context['learner_stats'] = {
            'total_employees': employees.count(),
            'in_training': linked_learners.count(),
            'active_enrollments': enrollments.filter(status__in=['ACTIVE', 'ENROLLED']).count(),
            'completed': enrollments.filter(status='COMPLETED').count(),
        }
        
        # Active grant projects
        grant_projects = GrantProject.objects.filter(
            client=client,
            status__in=['APPROVED', 'CONTRACTED', 'ACTIVE', 'REPORTING']
        ).order_by('-start_date')[:3]
        context['grant_projects'] = grant_projects
        
        # Recent meetings
        committees = Committee.objects.filter(client=client, is_active=True)
        recent_meetings = CommitteeMeeting.objects.filter(
            committee__in=committees
        ).order_by('-meeting_date')[:3]
        context['recent_meetings'] = recent_meetings
        
        # Recent documents
        delivery_projects = ServiceDeliveryProject.objects.filter(client=client)
        recent_documents = ProjectDocument.objects.filter(
            project__in=delivery_projects
        ).order_by('-upload_date')[:5]
        context['recent_documents'] = recent_documents
        
        return context


class CorporateServiceListView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    List all services for the corporate client.
    """
    template_name = 'portals/corporate/services.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        
        # Filter by status
        status_filter = self.request.GET.get('status', 'all')
        context['status_filter'] = status_filter
        
        # Get all subscriptions
        subscriptions = ClientServiceSubscription.objects.filter(
            client=client
        ).select_related('service', 'service__category', 'assigned_consultant')
        
        if status_filter != 'all':
            subscriptions = subscriptions.filter(status=status_filter)
        
        # Build subscription data with project info
        subscription_data = []
        for subscription in subscriptions:
            project = ServiceDeliveryProject.objects.filter(
                subscription=subscription
            ).first()
            
            subscription_data.append({
                'subscription': subscription,
                'project': project,
                'progress': project.progress_percentage if project else 0,
                'health': project.health if project else 'GREEN',
                'milestones': project.milestones.all().order_by('sequence') if project else [],
            })
        
        context['subscriptions'] = subscription_data
        
        # Status counts
        all_subs = ClientServiceSubscription.objects.filter(client=client)
        context['status_counts'] = {
            'all': all_subs.count(),
            'ACTIVE': all_subs.filter(status='ACTIVE').count(),
            'PENDING': all_subs.filter(status='PENDING').count(),
            'ON_HOLD': all_subs.filter(status='ON_HOLD').count(),
            'COMPLETED': all_subs.filter(status='EXPIRED').count(),
        }
        
        return context


class CorporateServiceDetailView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    Detailed view of a single service subscription with deliverables.
    """
    template_name = 'portals/corporate/service_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        
        subscription_id = self.kwargs.get('subscription_id')
        subscription = get_object_or_404(
            ClientServiceSubscription,
            pk=subscription_id,
            client=client
        )
        context['subscription'] = subscription
        
        # Get delivery project
        project = ServiceDeliveryProject.objects.filter(
            subscription=subscription
        ).first()
        context['project'] = project
        
        if project:
            # Get milestones with tasks
            milestones = project.milestones.all().order_by('sequence')
            milestone_data = []
            
            for milestone in milestones:
                tasks = milestone.tasks.all().order_by('priority', 'due_date')
                documents = milestone.documents.all().order_by('-upload_date')
                
                milestone_data.append({
                    'milestone': milestone,
                    'tasks': tasks,
                    'tasks_total': tasks.count(),
                    'tasks_done': tasks.filter(status='DONE').count(),
                    'documents': documents,
                })
            
            context['milestones'] = milestone_data
            
            # Project documents (not linked to specific milestone)
            context['project_documents'] = project.documents.filter(
                milestone__isnull=True
            ).order_by('-upload_date')
            
            # Project team
            context['team_members'] = project.team_members.all()
        
        # Get deadlines for this service
        context['deadlines'] = DeadlineReminder.objects.filter(
            client=client,
            is_completed=False
        ).order_by('deadline_date')[:5]
        
        # For training services, get learner progress
        if subscription.service.service_type in ['LEARNERSHIP', 'APPRENTICESHIP', 'SKILLS_PROGRAMME', 'INTERNSHIP']:
            context['is_training_service'] = True
            context['learners'] = self._get_service_learners(client, subscription)
        
        return context
    
    def _get_service_learners(self, client, subscription):
        """Get learners linked to this training service."""
        employees = CorporateEmployee.objects.filter(
            client=client,
            is_current=True,
            learner__isnull=False
        ).select_related('learner')
        
        learner_data = []
        for emp in employees:
            # Get enrollment progress
            enrollment = Enrollment.objects.filter(
                learner=emp.learner,
                status__in=['ACTIVE', 'ENROLLED', 'REGISTERED']
            ).first()
            
            if enrollment:
                # Calculate progress
                from assessments.models import AssessmentResult, AssessmentActivity
                from academics.models import Module
                
                modules = Module.objects.filter(
                    qualification=enrollment.qualification,
                    is_active=True
                )
                activities = AssessmentActivity.objects.filter(
                    module__in=modules,
                    is_active=True
                )
                
                total = activities.count()
                completed = AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    result='C',
                    status='FINALIZED'
                ).values('activity').distinct().count()
                
                progress = round(completed / total * 100) if total > 0 else 0
                
                learner_data.append({
                    'employee': emp,
                    'learner': emp.learner,
                    'enrollment': enrollment,
                    'progress': progress,
                    'completed_activities': completed,
                    'total_activities': total,
                })
        
        return learner_data


class CorporateLearnerListView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    List all learners/employees in training.
    """
    template_name = 'portals/corporate/learners.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        
        # Get all employees linked to learners
        employees = CorporateEmployee.objects.filter(
            client=client,
            is_current=True
        ).select_related('learner')
        
        # Filter options
        status_filter = self.request.GET.get('status', 'all')
        context['status_filter'] = status_filter
        
        learner_data = []
        for emp in employees:
            if emp.learner:
                # Get all enrollments for this learner
                enrollments = Enrollment.objects.filter(
                    learner=emp.learner
                ).select_related('qualification', 'cohort')
                
                active_enrollment = enrollments.filter(
                    status__in=['ACTIVE', 'ENROLLED', 'REGISTERED']
                ).first()
                
                # Calculate progress for active enrollment
                progress = 0
                if active_enrollment:
                    from assessments.models import AssessmentResult, AssessmentActivity
                    from academics.models import Module
                    
                    modules = Module.objects.filter(
                        qualification=active_enrollment.qualification,
                        is_active=True
                    )
                    activities = AssessmentActivity.objects.filter(
                        module__in=modules,
                        is_active=True
                    )
                    
                    total = activities.count()
                    completed = AssessmentResult.objects.filter(
                        enrollment=active_enrollment,
                        result='C',
                        status='FINALIZED'
                    ).values('activity').distinct().count()
                    
                    progress = round(completed / total * 100) if total > 0 else 0
                
                learner_info = {
                    'employee': emp,
                    'learner': emp.learner,
                    'enrollments': enrollments,
                    'active_enrollment': active_enrollment,
                    'progress': progress,
                    'status': 'active' if active_enrollment else 'not_enrolled',
                    'completed_count': enrollments.filter(status='COMPLETED').count(),
                }
                
                # Apply filter
                if status_filter == 'all':
                    learner_data.append(learner_info)
                elif status_filter == 'active' and active_enrollment:
                    learner_data.append(learner_info)
                elif status_filter == 'completed' and enrollments.filter(status='COMPLETED').exists():
                    learner_data.append(learner_info)
                elif status_filter == 'not_enrolled' and not active_enrollment:
                    learner_data.append(learner_info)
            else:
                # Employee not linked to learner
                if status_filter in ['all', 'not_enrolled']:
                    learner_data.append({
                        'employee': emp,
                        'learner': None,
                        'enrollments': [],
                        'active_enrollment': None,
                        'progress': 0,
                        'status': 'not_linked',
                        'completed_count': 0,
                    })
        
        context['learners'] = learner_data
        
        # Stats
        context['stats'] = {
            'total_employees': employees.count(),
            'linked_learners': employees.filter(learner__isnull=False).count(),
            'in_training': len([l for l in learner_data if l.get('active_enrollment')]),
            'completed': len([l for l in learner_data if l.get('completed_count', 0) > 0]),
        }
        
        return context


class CorporateLearnerDetailView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    Detailed view of a single learner's progress.
    """
    template_name = 'portals/corporate/learner_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        
        learner_id = self.kwargs.get('learner_id')
        
        # Verify this learner is linked to this client
        employee = get_object_or_404(
            CorporateEmployee,
            client=client,
            learner_id=learner_id,
            is_current=True
        )
        
        context['employee'] = employee
        context['learner'] = employee.learner
        
        # Get all enrollments
        enrollments = Enrollment.objects.filter(
            learner=employee.learner
        ).select_related('qualification', 'campus', 'cohort').order_by('-enrollment_date')
        
        enrollment_data = []
        for enrollment in enrollments:
            from assessments.models import AssessmentResult, AssessmentActivity
            from academics.models import Module
            
            modules = Module.objects.filter(
                qualification=enrollment.qualification,
                is_active=True
            ).order_by('sequence_order')
            
            activities = AssessmentActivity.objects.filter(
                module__in=modules,
                is_active=True
            )
            
            total = activities.count()
            completed = AssessmentResult.objects.filter(
                enrollment=enrollment,
                result='C',
                status='FINALIZED'
            ).values('activity').distinct().count()
            
            progress = round(completed / total * 100) if total > 0 else 0
            
            # Get module breakdown
            module_data = []
            for module in modules:
                mod_activities = activities.filter(module=module)
                mod_completed = AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    activity__module=module,
                    result='C',
                    status='FINALIZED'
                ).values('activity').distinct().count()
                
                module_data.append({
                    'module': module,
                    'total': mod_activities.count(),
                    'completed': mod_completed,
                    'progress': round(mod_completed / mod_activities.count() * 100) if mod_activities.count() > 0 else 0,
                })
            
            enrollment_data.append({
                'enrollment': enrollment,
                'total_activities': total,
                'completed_activities': completed,
                'progress': progress,
                'modules': module_data,
            })
        
        context['enrollments'] = enrollment_data
        
        return context


class CorporateDeadlinesView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    View all deadlines and reminders.
    """
    template_name = 'portals/corporate/deadlines.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        context['today'] = date.today()
        
        # Get filter
        filter_type = self.request.GET.get('filter', 'upcoming')
        context['filter_type'] = filter_type
        
        deadlines = DeadlineReminder.objects.filter(client=client)
        
        if filter_type == 'upcoming':
            deadlines = deadlines.filter(
                deadline_date__gte=date.today(),
                is_completed=False
            ).order_by('deadline_date')
        elif filter_type == 'overdue':
            deadlines = deadlines.filter(
                deadline_date__lt=date.today(),
                is_completed=False
            ).order_by('deadline_date')
        elif filter_type == 'completed':
            deadlines = deadlines.filter(is_completed=True).order_by('-completed_date')
        else:
            deadlines = deadlines.order_by('deadline_date')
        
        context['deadlines'] = deadlines
        
        # Counts
        all_deadlines = DeadlineReminder.objects.filter(client=client)
        context['counts'] = {
            'upcoming': all_deadlines.filter(deadline_date__gte=date.today(), is_completed=False).count(),
            'overdue': all_deadlines.filter(deadline_date__lt=date.today(), is_completed=False).count(),
            'completed': all_deadlines.filter(is_completed=True).count(),
        }
        
        return context


class CorporateMeetingsView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    View all committee meetings and minutes.
    """
    template_name = 'portals/corporate/meetings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        
        # Get committees
        committees = Committee.objects.filter(client=client, is_active=True)
        context['committees'] = committees
        
        # Get selected committee
        committee_id = self.request.GET.get('committee')
        if committee_id:
            selected_committee = get_object_or_404(Committee, pk=committee_id, client=client)
            meetings = CommitteeMeeting.objects.filter(committee=selected_committee)
        else:
            selected_committee = None
            meetings = CommitteeMeeting.objects.filter(committee__in=committees)
        
        context['selected_committee'] = selected_committee
        context['meetings'] = meetings.order_by('-meeting_date')
        
        # Upcoming meetings
        context['upcoming_meetings'] = meetings.filter(
            meeting_date__gte=date.today()
        ).order_by('meeting_date')[:5]
        
        # Past meetings with minutes
        context['past_meetings'] = meetings.filter(
            meeting_date__lt=date.today()
        ).exclude(minutes='').order_by('-meeting_date')[:10]
        
        return context


class CorporateMeetingDetailView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    View details of a specific meeting including minutes.
    """
    template_name = 'portals/corporate/meeting_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        
        meeting_id = self.kwargs.get('meeting_id')
        meeting = get_object_or_404(
            CommitteeMeeting,
            pk=meeting_id,
            committee__client=client
        )
        
        context['meeting'] = meeting
        context['committee'] = meeting.committee
        context['attendees'] = meeting.attendees.all()
        
        return context


class CorporateDocumentsView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    View all project documents.
    """
    template_name = 'portals/corporate/documents.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        
        # Get all projects
        projects = ServiceDeliveryProject.objects.filter(client=client)
        
        # Filter by project
        project_id = self.request.GET.get('project')
        if project_id:
            selected_project = get_object_or_404(ServiceDeliveryProject, pk=project_id, client=client)
            documents = ProjectDocument.objects.filter(project=selected_project)
        else:
            selected_project = None
            documents = ProjectDocument.objects.filter(project__in=projects)
        
        context['selected_project'] = selected_project
        context['projects'] = projects
        
        # Filter by type
        doc_type = self.request.GET.get('type')
        if doc_type:
            documents = documents.filter(document_type=doc_type)
        context['doc_type_filter'] = doc_type
        
        context['documents'] = documents.order_by('-upload_date')
        
        # Document type choices for filter
        context['document_types'] = ProjectDocument.DOCUMENT_TYPE_CHOICES
        
        return context


class CorporateGrantsView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    View grant projects and claims.
    """
    template_name = 'portals/corporate/grants.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        
        # Get all grant projects
        grants = GrantProject.objects.filter(client=client).select_related('seta').order_by('-start_date')
        
        grant_data = []
        for grant in grants:
            claims = grant.claims.all().order_by('claim_type')
            
            grant_data.append({
                'grant': grant,
                'claims': claims,
                'total_claimed': sum(c.claim_amount for c in claims),
                'total_received': sum(c.approved_amount or 0 for c in claims if c.status == 'PAID'),
                'progress': round(grant.completed_learners / grant.target_learners * 100) if grant.target_learners else 0,
            })
        
        context['grants'] = grant_data
        
        # Summary stats
        active_grants = grants.filter(status__in=['APPROVED', 'CONTRACTED', 'ACTIVE'])
        context['stats'] = {
            'total_grants': grants.count(),
            'active_grants': active_grants.count(),
            'total_approved': sum(g.approved_amount or 0 for g in grants),
            'total_received': sum(g.received_amount or 0 for g in grants),
        }
        
        return context


class CorporateGrantDetailView(LoginRequiredMixin, CorporatePortalMixin, TemplateView):
    """
    Detailed view of a grant project.
    """
    template_name = 'portals/corporate/grant_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        client = self.get_corporate_client()
        if not client:
            context['no_client'] = True
            return context
        
        context['client'] = client
        
        grant_id = self.kwargs.get('grant_id')
        grant = get_object_or_404(GrantProject, pk=grant_id, client=client)
        
        context['grant'] = grant
        context['claims'] = grant.claims.all().order_by('claim_type')
        
        # Progress
        context['progress'] = round(grant.completed_learners / grant.target_learners * 100) if grant.target_learners else 0
        
        # Financial summary
        context['financial'] = {
            'approved': grant.approved_amount or 0,
            'claimed': grant.claimed_amount or 0,
            'received': grant.received_amount or 0,
            'outstanding': (grant.approved_amount or 0) - (grant.received_amount or 0),
        }
        
        return context


# =============================================================================
# SDF Task Management Views
# =============================================================================

@login_required
def mark_task_complete(request, pk):
    """
    SDF marks a task as complete.
    Requires can_complete_deliverables permission.
    """
    from corporate.models import MilestoneTask
    from django.contrib import messages
    
    task = get_object_or_404(MilestoneTask, pk=pk)
    project = task.milestone.project
    client = project.client
    
    # Get the contact for this user
    contact = CorporateContact.objects.filter(user=request.user, is_active=True).first()
    
    # Check permission
    if not contact or contact.client != client:
        messages.error(request, "You do not have access to this task.")
        return redirect('portals:corporate_dashboard')
    
    if not contact.can_complete_deliverables:
        messages.error(request, "You do not have permission to mark tasks as complete.")
        return redirect('portals:corporate_service_detail', subscription_id=project.subscription.pk)
    
    # Check if task is client-visible
    if not task.client_visible:
        messages.error(request, "This task is not available for client completion.")
        return redirect('portals:corporate_service_detail', subscription_id=project.subscription.pk)
    
    # Check if evidence required and uploaded
    if task.requires_evidence and not task.evidence.exists():
        messages.error(request, "Please upload evidence before marking this task as complete.")
        return redirect('portals:corporate_service_detail', subscription_id=project.subscription.pk)
    
    if request.method == 'POST':
        completion_notes = request.POST.get('completion_notes', '').strip()
        
        task.status = 'DONE'
        task.completed_date = timezone.now().date()
        task.completed_by_contact = contact
        task.completion_notes = completion_notes
        task.save()
        
        messages.success(request, f"Task '{task.title}' marked as complete.")
    
    return redirect('portals:corporate_service_detail', subscription_id=project.subscription.pk)


@login_required
def upload_task_evidence(request, pk):
    """
    SDF uploads evidence for a task.
    Requires can_upload_evidence permission.
    """
    from corporate.models import MilestoneTask, TaskEvidence
    from django.contrib import messages
    
    task = get_object_or_404(MilestoneTask, pk=pk)
    project = task.milestone.project
    client = project.client
    
    # Get the contact for this user
    contact = CorporateContact.objects.filter(user=request.user, is_active=True).first()
    
    # Check permission
    if not contact or contact.client != client:
        messages.error(request, "You do not have access to this task.")
        return redirect('portals:corporate_dashboard')
    
    if not contact.can_upload_evidence:
        messages.error(request, "You do not have permission to upload evidence.")
        return redirect('portals:corporate_service_detail', subscription_id=project.subscription.pk)
    
    # Check if task is client-visible
    if not task.client_visible:
        messages.error(request, "This task is not available for client uploads.")
        return redirect('portals:corporate_service_detail', subscription_id=project.subscription.pk)
    
    if request.method == 'POST':
        name = request.POST.get('evidence_name', '').strip()
        description = request.POST.get('evidence_description', '').strip()
        file = request.FILES.get('evidence_file')
        
        if not file:
            messages.error(request, "Please select a file to upload.")
            return redirect('portals:corporate_service_detail', subscription_id=project.subscription.pk)
        
        if not name:
            name = file.name
        
        try:
            evidence = TaskEvidence(
                task=task,
                name=name,
                description=description,
                file=file,
                uploaded_by_contact=contact
            )
            evidence.full_clean()  # Validate including file extension
            evidence.save()
            messages.success(request, f"Evidence '{name}' uploaded successfully.")
        except Exception as e:
            messages.error(request, f"Error uploading file: {str(e)}")
    
    return redirect('portals:corporate_service_detail', subscription_id=project.subscription.pk)

