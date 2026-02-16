"""
Task Hub Views

Central dashboard for all users to view and manage their tasks.
Provides unified task management across all business processes.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView, View
from django.http import JsonResponse
from django.db.models import Count, Q, Case, When, Value, IntegerField
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse
from datetime import date, timedelta
import json

from .tasks import Task, TaskCategory, TaskStatus, TaskPriority, TaskComment


class TaskHubView(LoginRequiredMixin, TemplateView):
    """
    Main Task Hub - User's central dashboard for all tasks
    """
    template_name = 'tasks/task_hub.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        
        # Get user's tasks
        user_tasks = Task.objects.filter(
            Q(assigned_to=user) | Q(assigned_role__in=self._get_user_roles())
        ).exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        
        # Task counts for header cards
        context['overdue_count'] = user_tasks.filter(
            due_date__lt=today,
            status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        ).count()
        
        context['urgent_count'] = user_tasks.filter(
            priority__in=[TaskPriority.URGENT, TaskPriority.HIGH]
        ).count()
        
        context['today_count'] = user_tasks.filter(due_date=today).count()
        
        context['completed_today'] = Task.objects.filter(
            Q(assigned_to=user) | Q(completed_by=user),
            completed_at__date=today
        ).count()
        
        # Category choices for filter dropdown
        context['categories'] = TaskCategory.choices
        
        # Quick stats
        context['today'] = today
        
        return context
    
    def _get_user_roles(self):
        """Get user's role codes"""
        # This would integrate with the UserRole model
        return []


class TaskListAPIView(LoginRequiredMixin, View):
    """
    API endpoint for loading tasks via AJAX
    """
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        # Build queryset
        queryset = Task.objects.filter(
            Q(assigned_to=user) | Q(created_by=user)
        )
        
        # Apply filters
        category = request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        priority = request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        status = request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        else:
            # Default: show open tasks
            queryset = queryset.exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        
        # Order and limit
        queryset = queryset.order_by('-priority', 'due_date', '-created_at')[:50]
        
        # Build response
        tasks = []
        for task in queryset:
            tasks.append({
                'id': task.id,
                'title': task.title,
                'description': task.description[:200] if task.description else '',
                'category': task.category,
                'category_display': task.get_category_display(),
                'priority': task.priority,
                'priority_display': task.get_priority_display(),
                'status': task.status,
                'status_display': task.get_status_display(),
                'due_date': str(task.due_date) if task.due_date else None,
                'due_date_display': task.due_date.strftime('%b %d, %Y') if task.due_date else None,
                'is_overdue': task.due_date and task.due_date < today and task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED],
                'completed_at': str(task.completed_at) if task.completed_at else None,
                'completed_at_display': task.completed_at.strftime('%b %d, %Y') if task.completed_at else None,
                'related_object_display': str(task.content_object) if task.content_object else None,
            })
        
        return JsonResponse({'tasks': tasks})


class TaskListView(LoginRequiredMixin, ListView):
    """
    Full task list with filtering
    """
    model = Task
    template_name = 'tasks/task_list.html'
    context_object_name = 'tasks'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        queryset = Task.objects.filter(
            Q(assigned_to=user) | Q(created_by=user)
        )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        else:
            # Default: exclude completed/cancelled
            queryset = queryset.exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by priority
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by date range
        date_filter = self.request.GET.get('date')
        today = timezone.now().date()
        if date_filter == 'overdue':
            queryset = queryset.filter(due_date__lt=today)
        elif date_filter == 'today':
            queryset = queryset.filter(due_date=today)
        elif date_filter == 'week':
            queryset = queryset.filter(due_date__range=[today, today + timedelta(days=7)])
        elif date_filter == 'month':
            queryset = queryset.filter(due_date__range=[today, today + timedelta(days=30)])
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset.order_by('-priority', 'due_date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = TaskCategory.choices
        context['statuses'] = TaskStatus.choices
        context['priorities'] = TaskPriority.choices
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_priority'] = self.request.GET.get('priority', '')
        context['selected_date'] = self.request.GET.get('date', '')
        context['search'] = self.request.GET.get('search', '')
        return context


class TaskDetailView(LoginRequiredMixin, DetailView):
    """
    Task detail view
    """
    model = Task
    template_name = 'tasks/task_detail.html'
    context_object_name = 'task'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = self.object.comments.select_related('user').order_by('created_at')
        return context


@login_required
def task_update_status(request, pk):
    """Update task status via AJAX or form POST"""
    task = get_object_or_404(Task, pk=pk)
    
    # Check permission (assigned to user or creator)
    if task.assigned_to != request.user and task.created_by != request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        messages.error(request, 'You do not have permission to update this task.')
        return redirect('core:task_list')
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        if new_status in dict(TaskStatus.choices):
            task.status = new_status
            
            if new_status == TaskStatus.COMPLETED:
                task.completed_at = timezone.now()
                task.completed_by = request.user
            
            task.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'status': new_status,
                    'status_display': dict(TaskStatus.choices)[new_status]
                })
            
            messages.success(request, f'Task status updated to {dict(TaskStatus.choices)[new_status]}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
            messages.error(request, 'Invalid status')
    
    return redirect('core:task_detail', pk=pk)


@login_required
def task_quick_complete(request, pk):
    """Quick complete task from list"""
    task = get_object_or_404(Task, pk=pk)
    
    if task.assigned_to != request.user and task.created_by != request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        messages.error(request, 'Permission denied')
        return redirect('core:task_list')
    
    task.mark_complete(request.user)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'status': task.status, 'message': 'Task completed'})
    
    messages.success(request, f'Task "{task.title}" marked as complete')
    return redirect(request.META.get('HTTP_REFERER', 'core:task_hub'))


@login_required
def task_snooze(request, pk):
    """Snooze task by pushing due date forward"""
    task = get_object_or_404(Task, pk=pk)
    
    if task.assigned_to != request.user and task.created_by != request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        messages.error(request, 'Permission denied')
        return redirect('core:task_hub')
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
            days = int(data.get('days', 1))
        except (json.JSONDecodeError, ValueError):
            days = 1
        
        # Update due date
        if task.due_date:
            task.due_date = task.due_date + timedelta(days=days)
        else:
            task.due_date = timezone.now().date() + timedelta(days=days)
        task.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'new_due_date': str(task.due_date),
                'message': f'Task snoozed for {days} day(s)'
            })
        
        messages.success(request, f'Task snoozed for {days} day(s)')
    
    return redirect(request.META.get('HTTP_REFERER', 'core:task_hub'))


@login_required
def task_add_comment(request, pk):
    """Add comment to task"""
    task = get_object_or_404(Task, pk=pk)
    
    if request.method == 'POST':
        comment_text = request.POST.get('comment', '').strip()
        
        if comment_text:
            TaskComment.objects.create(
                task=task,
                user=request.user,
                comment=comment_text
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'comment': {
                        'user': request.user.get_full_name() or request.user.email,
                        'comment': comment_text,
                        'created_at': timezone.now().isoformat()
                    }
                })
            
            messages.success(request, 'Comment added')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Comment cannot be empty'}, status=400)
            messages.error(request, 'Comment cannot be empty')
    
    return redirect('core:task_detail', pk=pk)


class TaskCreateView(LoginRequiredMixin, View):
    """Create a new task"""
    
    def get(self, request):
        context = {
            'categories': TaskCategory.choices,
            'priorities': TaskPriority.choices,
        }
        return render(request, 'tasks/task_create.html', context)
    
    def post(self, request):
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', TaskCategory.ACTION)
        priority = request.POST.get('priority', TaskPriority.MEDIUM)
        due_date = request.POST.get('due_date')
        due_time = request.POST.get('due_time')
        notes = request.POST.get('notes', '').strip()
        
        if not title:
            messages.error(request, 'Task title is required')
            return redirect('core:task_create')
        
        task = Task.objects.create(
            title=title,
            description=description,
            category=category,
            priority=priority,
            due_date=due_date if due_date else None,
            due_time=due_time if due_time else None,
            notes=notes,
            assigned_to=request.user,
            created_by=request.user
        )
        
        messages.success(request, f'Task "{task.title}" created successfully')
        return redirect('core:task_hub')


# =====================================================
# ROLE-BASED DASHBOARDS
# =====================================================

class LearnerDashboardView(LoginRequiredMixin, TemplateView):
    """
    Simplified dashboard for learners
    Shows: My courses, upcoming assessments, marks, materials
    """
    template_name = 'dashboard/learner_home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        
        # Get learner profile
        from learners.models import Learner
        from academics.models import Enrollment
        from assessments.models import AssessmentResult, AssessmentActivity
        
        learner = Learner.objects.filter(user=user).first()
        context['learner'] = learner
        
        if learner:
            # Active enrollments
            enrollments = Enrollment.objects.filter(
                learner=learner,
                status__in=['ACTIVE', 'ENROLLED']
            ).select_related('qualification', 'campus', 'cohort')
            context['enrollments'] = enrollments
            
            # Upcoming assessments
            upcoming = AssessmentActivity.objects.filter(
                module__qualification__enrollments__learner=learner,
                due_date__gte=today,
                is_active=True
            ).order_by('due_date')[:5]
            context['upcoming_assessments'] = upcoming
            
            # Recent marks
            recent_results = AssessmentResult.objects.filter(
                enrollment__learner=learner
            ).select_related('activity').order_by('-assessment_date')[:5]
            context['recent_results'] = recent_results
            
            # Tasks for learner
            tasks = Task.objects.filter(
                Q(assigned_to=user) |
                Q(category__in=[TaskCategory.DOCUMENT_UPLOAD, TaskCategory.ASSESSMENT_DUE])
            ).exclude(status=TaskStatus.COMPLETED)[:5]
            context['tasks'] = tasks
            
            # Progress stats
            all_results = AssessmentResult.objects.filter(enrollment__learner=learner)
            total = all_results.count()
            competent = all_results.filter(result='C').count()
            context['progress'] = {
                'total_assessments': total,
                'competent': competent,
                'pass_rate': round(competent/total*100, 1) if total > 0 else 0
            }
        
        return context


class FacilitatorDashboardView(LoginRequiredMixin, TemplateView):
    """
    Simplified dashboard for facilitators
    Shows: My classes, pending marking, attendance, learner progress
    """
    template_name = 'dashboard/facilitator_home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        
        from logistics.models import Cohort, ScheduleSession, Attendance
        from academics.models import Enrollment
        from assessments.models import AssessmentResult
        
        # My cohorts
        cohorts = Cohort.objects.filter(
            Q(facilitator=user),
            status__in=['ACTIVE', 'OPEN']
        ).select_related('qualification', 'campus')
        context['cohorts'] = cohorts
        
        # Total learners
        total_learners = Enrollment.objects.filter(
            cohort__in=cohorts,
            status__in=['ACTIVE', 'ENROLLED']
        ).count()
        context['total_learners'] = total_learners
        
        # Pending assessments to mark
        pending_marking = AssessmentResult.objects.filter(
            Q(assessor=user) | Q(enrollment__cohort__facilitator=user),
            status='SUBMITTED'
        ).count()
        context['pending_marking'] = pending_marking
        
        # Pending moderation
        pending_moderation = AssessmentResult.objects.filter(
            enrollment__cohort__facilitator=user,
            status='PENDING_MOD'
        ).count()
        context['pending_moderation'] = pending_moderation
        
        # Today's sessions
        todays_sessions = ScheduleSession.objects.filter(
            facilitator=user,
            date=today,
            is_cancelled=False
        ).select_related('cohort', 'module', 'venue')
        context['todays_sessions'] = todays_sessions
        
        # Attendance to capture
        sessions_needing_attendance = ScheduleSession.objects.filter(
            facilitator=user,
            date__lte=today,
            is_cancelled=False
        ).exclude(
            attendance_records__isnull=False
        ).count()
        context['sessions_needing_attendance'] = sessions_needing_attendance
        
        # Tasks
        tasks = Task.objects.filter(
            Q(assigned_to=user) |
            Q(category__in=[TaskCategory.ASSESSMENT_MARK, TaskCategory.ASSESSMENT_MODERATE, TaskCategory.ATTENDANCE_CAPTURE])
        ).exclude(status=TaskStatus.COMPLETED)[:10]
        context['tasks'] = tasks
        
        # At-risk learners
        at_risk = Enrollment.objects.filter(
            cohort__in=cohorts
        ).annotate(
            nyc_count=Count('assessmentresult', filter=Q(assessmentresult__result='NYC'))
        ).filter(nyc_count__gte=2)[:5]
        context['at_risk_learners'] = at_risk
        
        return context


class AdminDashboardView(LoginRequiredMixin, TemplateView):
    """
    Admin/Staff dashboard
    Shows: KPIs, pending tasks, system alerts
    """
    template_name = 'dashboard/admin_home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        
        from learners.models import Learner
        from academics.models import Enrollment
        from finance.models import Invoice, Payment
        
        # KPIs
        context['kpis'] = {
            'total_learners': Learner.objects.filter(is_deleted=False).count(),
            'active_enrollments': Enrollment.objects.filter(status__in=['ACTIVE', 'ENROLLED']).count(),
            'pending_invoices': Invoice.objects.filter(status__in=['SENT', 'PARTIAL']).count(),
            'overdue_invoices': Invoice.objects.filter(status='OVERDUE').count(),
        }
        
        # Tasks by category
        tasks = Task.objects.exclude(status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        context['task_summary'] = tasks.values('category').annotate(count=Count('id')).order_by('-count')[:10]
        
        # My tasks
        my_tasks = tasks.filter(assigned_to=user).order_by('-priority', 'due_date')[:10]
        context['my_tasks'] = my_tasks
        
        # Recent activity
        context['recent_enrollments'] = Enrollment.objects.select_related(
            'learner', 'qualification'
        ).order_by('-created_at')[:5]
        
        context['recent_payments'] = Payment.objects.filter(
            status='COMPLETED'
        ).select_related('invoice').order_by('-payment_date')[:5]
        
        return context


class StakeholderDashboardView(LoginRequiredMixin, TemplateView):
    """
    Stakeholder dashboard (SETA, Corporate, QCTO)
    Shows: Project progress, deliverables, reports
    """
    template_name = 'dashboard/stakeholder_home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        from corporate.models import GrantProject, GrantClaim
        from academics.models import Enrollment
        
        # Get projects for this stakeholder
        # This would be filtered by corporate client relationship
        projects = GrantProject.objects.filter(
            status__in=['ACTIVE', 'CONTRACTED', 'REPORTING']
        ).select_related('client', 'seta')
        
        context['projects'] = projects
        
        # Overall stats
        context['stats'] = {
            'total_projects': projects.count(),
            'total_target_learners': sum(p.target_learners or 0 for p in projects),
            'total_enrolled': sum(p.enrolled_learners or 0 for p in projects),
            'total_completed': sum(p.completed_learners or 0 for p in projects),
        }
        
        # Pending claims
        pending_claims = GrantClaim.objects.filter(
            project__in=projects,
            status__in=['DRAFT', 'SUBMITTED', 'UNDER_REVIEW']
        ).select_related('project')
        context['pending_claims'] = pending_claims
        
        return context
