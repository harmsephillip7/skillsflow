"""
Projects Section Views
Comprehensive project management with deliverables, finance scheduling, 
invoices, payments, and evidence tracking from start to completion.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Sum, Avg, F, Case, When, Value, CharField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import json

from .models import (
    TrainingNotification, NOTStakeholder, NOTResourceRequirement,
    NOTDeliverable, NOTMeetingMinutes, NOTIntake, TrancheSchedule,
    TrancheEvidenceRequirement, TrancheEvidence, TrancheSubmission,
    ExternalModerationRequest, TrainingClass, LearnerClassAssignment,
    NOTDeliverableEvidence, NOTDeliverableEvidenceRequirement
)
from academics.models import Qualification, Enrollment
from tenants.models import Campus
from corporate.models import CorporateClient
from finance.models import (
    Invoice, Payment, ProjectBillingSchedule, ScheduledInvoice,
    FunderCollectionMetrics, BillingScheduleTemplate
)


class ProjectsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Main Projects Dashboard
    Overview of all projects with comprehensive statistics and filtering
    """
    template_name = 'projects/dashboard.html'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        
        # Get filter parameters
        status_filter = self.request.GET.get('status', '')
        funding_filter = self.request.GET.get('funding', '')
        qualification_filter = self.request.GET.get('qualification', '')
        
        # Base queryset
        projects = TrainingNotification.objects.filter(is_deleted=False)
        
        # Apply filters
        if status_filter:
            projects = projects.filter(status=status_filter)
        if funding_filter:
            projects = projects.filter(funder=funding_filter)
        if qualification_filter:
            projects = projects.filter(qualification_id=qualification_filter)
        
        # Summary statistics
        all_projects = TrainingNotification.objects.filter(is_deleted=False)
        context['summary'] = {
            'total_projects': all_projects.count(),
            'active_projects': all_projects.filter(
                status__in=['APPROVED', 'IN_PROGRESS', 'NOTIFICATIONS_SENT']
            ).count(),
            'in_planning': all_projects.filter(
                status__in=['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL']
            ).count(),
            'completed': all_projects.filter(status='COMPLETED').count(),
            'total_contract_value': all_projects.aggregate(
                total=Coalesce(Sum('contract_value'), Decimal('0'))
            )['total'],
            'total_learners': all_projects.aggregate(
                total=Coalesce(Sum('expected_learner_count'), 0)
            )['total'],
        }
        
        # Projects by status for pie chart
        status_counts = all_projects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        context['status_distribution'] = list(status_counts)
        
        # Financial summary
        tranches = TrancheSchedule.objects.filter(
            training_notification__is_deleted=False
        )
        context['financial_summary'] = {
            'total_scheduled': tranches.aggregate(
                total=Coalesce(Sum('amount'), Decimal('0'))
            )['total'],
            'total_received': tranches.aggregate(
                total=Coalesce(Sum('actual_amount_received'), Decimal('0'))
            )['total'],
            'pending_claims': tranches.filter(
                status__in=['SCHEDULED', 'EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE', 'PENDING_QC', 'QC_PASSED']
            ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total'],
            'submitted_awaiting': tranches.filter(
                status__in=['SUBMITTED', 'QUERY']
            ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total'],
        }
        
        # Upcoming deliverables
        context['upcoming_deliverables'] = NOTDeliverable.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS'],
            due_date__gte=today,
            due_date__lte=today + timedelta(days=30),
            training_notification__is_deleted=False
        ).select_related('training_notification').order_by('due_date')[:10]
        
        # Overdue deliverables
        context['overdue_deliverables'] = NOTDeliverable.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS'],
            due_date__lt=today,
            training_notification__is_deleted=False
        ).select_related('training_notification').order_by('due_date')[:10]
        
        # Pending moderation requests
        context['pending_moderations'] = ExternalModerationRequest.objects.filter(
            status__in=['SUBMITTED', 'ACKNOWLEDGED', 'SCHEDULED'],
            training_notification__is_deleted=False
        ).select_related('training_notification').order_by('-days_waiting')[:5]
        
        # Projects list with annotations
        context['projects'] = projects.select_related(
            'qualification', 'delivery_campus', 'corporate_client'
        ).annotate(
            deliverable_count=Count('deliverables'),
            completed_deliverables=Count('deliverables', filter=Q(deliverables__status='COMPLETED')),
            tranche_count=Count('tranches'),
            total_tranche_value=Coalesce(Sum('tranches__amount'), Decimal('0')),
            received_amount=Coalesce(Sum('tranches__actual_amount_received'), Decimal('0')),
        ).order_by('-created_at')[:50]
        
        # Filter options
        context['qualifications'] = Qualification.objects.filter(is_active=True).order_by('short_title')
        context['status_choices'] = TrainingNotification.STATUS_CHOICES
        context['funding_choices'] = TrainingNotification.FUNDER_CHOICES
        
        # Current filters
        context['current_status'] = status_filter
        context['current_funding'] = funding_filter
        context['current_qualification'] = qualification_filter
        
        return context


class ProjectDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Comprehensive Project Detail View
    Shows complete project lifecycle with all related data
    """
    model = TrainingNotification
    template_name = 'projects/detail.html'
    context_object_name = 'project'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        today = date.today()
        
        # Project phases for timeline
        context['phases'] = self._get_project_phases(project)
        
        # Stakeholders
        context['stakeholders'] = NOTStakeholder.objects.filter(
            training_notification=project
        ).select_related('user').order_by('department', 'role_in_project')
        
        # Resource requirements
        context['resources'] = NOTResourceRequirement.objects.filter(
            training_notification=project
        ).order_by('resource_type')
        
        # Intakes
        context['intakes'] = NOTIntake.objects.filter(
            training_notification=project
        ).order_by('intake_number')
        
        # Training classes with facilitators
        context['training_classes'] = TrainingClass.objects.filter(
            training_notification=project
        ).select_related('facilitator__user').annotate(
            learner_count=Count('learner_assignments', filter=Q(learner_assignments__is_active=True))
        ).order_by('group_number')
        
        # Deliverables by status
        deliverables = NOTDeliverable.objects.filter(
            training_notification=project
        ).order_by('due_date')
        
        context['deliverables'] = deliverables
        context['deliverable_stats'] = {
            'total': deliverables.count(),
            'completed': deliverables.filter(status='COMPLETED').count(),
            'in_progress': deliverables.filter(status='IN_PROGRESS').count(),
            'pending': deliverables.filter(status='PENDING').count(),
            'overdue': deliverables.filter(status__in=['PENDING', 'IN_PROGRESS'], due_date__lt=today).count(),
        }
        
        # Financial - Tranche schedules
        tranches = TrancheSchedule.objects.filter(
            training_notification=project
        ).prefetch_related('evidence_requirements', 'evidence_requirements__evidences').order_by('sequence_number')
        
        context['tranches'] = tranches
        context['financial_summary'] = self._get_financial_summary(project, tranches)
        
        # Invoices linked to project tranches
        context['invoices'] = Invoice.objects.filter(
            tranche__training_notification=project
        ).select_related('tranche').order_by('-invoice_date')
        
        # Payments
        context['payments'] = Payment.objects.filter(
            invoice__tranche__training_notification=project
        ).select_related('invoice').order_by('-payment_date')
        
        # External moderation requests
        context['moderation_requests'] = ExternalModerationRequest.objects.filter(
            training_notification=project
        ).order_by('-created_at')
        
        # Meeting history
        context['meetings'] = NOTMeetingMinutes.objects.filter(
            training_notification=project
        ).order_by('-meeting_date')
        
        # Learner statistics
        context['learner_stats'] = self._get_learner_stats(project)
        
        # Evidence completion overview
        context['evidence_overview'] = self._get_evidence_overview(tranches)
        
        # Billing Schedule and Collection Metrics
        context['today'] = today
        context.update(self._get_billing_context(project))
        
        # Attendance context for quick links
        context.update(self._get_attendance_context(project, today))
        
        return context
    
    def _get_attendance_context(self, project, today):
        """Get attendance tab context data"""
        from corporate.models import WorkplacePlacement
        from learners.models import WorkplaceAttendance, StipendCalculation
        import calendar
        
        attendance_context = {}
        
        # Current and previous month
        attendance_context['current_year'] = today.year
        attendance_context['current_month'] = today.month
        attendance_context['current_month_name'] = calendar.month_name[today.month]
        
        # Previous month
        if today.month == 1:
            attendance_context['prev_year'] = today.year - 1
            attendance_context['prev_month'] = 12
        else:
            attendance_context['prev_year'] = today.year
            attendance_context['prev_month'] = today.month - 1
        attendance_context['prev_month_name'] = calendar.month_name[attendance_context['prev_month']]
        
        # Get attendance summary
        placements = WorkplacePlacement.objects.filter(
            training_notification=project,
            status__in=['ACTIVE', 'COMPLETED']
        )
        
        total_placements = placements.count()
        
        if total_placements > 0:
            placement_ids = placements.values_list('id', flat=True)
            total_records = WorkplaceAttendance.objects.filter(
                placement_id__in=placement_ids
            ).count()
            
            verified_records = WorkplaceAttendance.objects.filter(
                placement_id__in=placement_ids,
                mentor_verified=True,
                facilitator_verified=True
            ).count()
            
            verified_pct = (verified_records / total_records * 100) if total_records > 0 else 0
            
            stipends_calculated = StipendCalculation.objects.filter(
                placement_id__in=placement_ids
            ).count()
            
            attendance_context['attendance_summary'] = {
                'total_placements': total_placements,
                'total_records': total_records,
                'verified_pct': verified_pct,
                'stipends_calculated': stipends_calculated,
            }
        else:
            attendance_context['attendance_summary'] = None
        
        return attendance_context
    
    def _get_billing_context(self, project):
        """Get billing schedule and collection metrics context"""
        from finance.models import ProjectBillingSchedule, ScheduledInvoice, FunderCollectionMetrics
        
        billing_context = {}
        
        # Get billing schedule
        try:
            billing_schedule = ProjectBillingSchedule.objects.get(training_notification=project)
            billing_context['billing_schedule'] = billing_schedule
            
            # Get scheduled invoices
            scheduled_invoices = ScheduledInvoice.objects.filter(
                billing_schedule=billing_schedule
            ).select_related('invoice').order_by('period_number')
            billing_context['scheduled_invoices'] = scheduled_invoices
        except ProjectBillingSchedule.DoesNotExist:
            billing_context['billing_schedule'] = None
            billing_context['scheduled_invoices'] = []
        
        # Get collection metrics for this project (lifetime)
        try:
            collection_metrics = FunderCollectionMetrics.objects.filter(
                training_notification=project,
                period_type='LIFETIME'
            ).order_by('-calculated_at').first()
            billing_context['collection_metrics'] = collection_metrics
        except FunderCollectionMetrics.DoesNotExist:
            billing_context['collection_metrics'] = None
        
        # Get funder comparison metrics
        if project.funder:
            funder_metrics = FunderCollectionMetrics.objects.filter(
                entity_type='FUNDER_TYPE',
                funder_type=project.funder,
                period_type='LIFETIME'
            ).order_by('-calculated_at').first()
            
            if funder_metrics:
                # Get aggregate stats for this funder type
                all_funder_metrics = FunderCollectionMetrics.objects.filter(
                    entity_type='PROJECT',
                    funder_type=project.funder,
                    period_type='LIFETIME'
                )
                
                if all_funder_metrics.exists():
                    from django.db.models import Avg
                    agg = all_funder_metrics.aggregate(
                        avg_collection=Avg('collection_rate'),
                        avg_persistency=Avg('persistency_rate'),
                    )
                    good_count = all_funder_metrics.filter(is_good_business=True).count()
                    total_count = all_funder_metrics.count()
                    
                    billing_context['funder_comparison'] = {
                        'avg_collection_rate': agg['avg_collection'] or 0,
                        'avg_persistency': agg['avg_persistency'] or 0,
                        'total_projects': total_count,
                        'good_business_pct': (good_count / total_count * 100) if total_count > 0 else 0,
                    }
        
        return billing_context
    
    def _get_project_phases(self, project):
        """Get project lifecycle phases with completion status"""
        phases = [
            {
                'name': 'Planning',
                'icon': 'clipboard-list',
                'statuses': ['DRAFT', 'PLANNING'],
                'completed': project.status not in ['DRAFT', 'PLANNING'],
                'current': project.status in ['DRAFT', 'PLANNING'],
            },
            {
                'name': 'Approval',
                'icon': 'check-circle',
                'statuses': ['IN_MEETING', 'PENDING_APPROVAL'],
                'completed': project.status not in ['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL'],
                'current': project.status in ['IN_MEETING', 'PENDING_APPROVAL'],
            },
            {
                'name': 'Notification',
                'icon': 'mail',
                'statuses': ['APPROVED', 'NOTIFICATIONS_SENT'],
                'completed': project.status in ['IN_PROGRESS', 'COMPLETED'],
                'current': project.status in ['APPROVED', 'NOTIFICATIONS_SENT'],
            },
            {
                'name': 'In Progress',
                'icon': 'play-circle',
                'statuses': ['IN_PROGRESS'],
                'completed': project.status == 'COMPLETED',
                'current': project.status == 'IN_PROGRESS',
            },
            {
                'name': 'Completed',
                'icon': 'trophy',
                'statuses': ['COMPLETED'],
                'completed': project.status == 'COMPLETED',
                'current': project.status == 'COMPLETED',
            },
        ]
        return phases
    
    def _get_financial_summary(self, project, tranches):
        """Calculate financial summary for the project"""
        total_scheduled = sum(t.amount or Decimal('0') for t in tranches)
        total_received = sum(t.actual_amount_received or Decimal('0') for t in tranches)
        
        # Status breakdown
        status_amounts = {}
        for tranche in tranches:
            status = tranche.status
            if status not in status_amounts:
                status_amounts[status] = Decimal('0')
            status_amounts[status] += tranche.amount or Decimal('0')
        
        return {
            'contract_value': project.contract_value or Decimal('0'),
            'total_scheduled': total_scheduled,
            'total_received': total_received,
            'outstanding': total_scheduled - total_received,
            'collection_rate': round((float(total_received) / float(total_scheduled) * 100) if total_scheduled > 0 else 0, 1),
            'status_breakdown': status_amounts,
        }
    
    def _get_learner_stats(self, project):
        """Get learner statistics for the project"""
        # Get enrollments through the project's linked cohort
        if project.cohort:
            enrollments = Enrollment.objects.filter(cohort=project.cohort)
        else:
            enrollments = Enrollment.objects.none()
        
        return {
            'expected': project.expected_learner_count or 0,
            'enrolled': enrollments.count(),
            'active': enrollments.filter(status='ACTIVE').count(),
            'completed': enrollments.filter(status='COMPLETED').count(),
            'withdrawn': enrollments.filter(status='WITHDRAWN').count(),
        }
    
    def _get_evidence_overview(self, tranches):
        """Get evidence completion overview across all tranches"""
        total_requirements = 0
        verified_count = 0
        pending_count = 0
        
        for tranche in tranches:
            for req in tranche.evidence_requirements.all():
                total_requirements += 1
                for evidence in req.evidences.all():
                    if evidence.status == 'VERIFIED':
                        verified_count += 1
                    elif evidence.status == 'PENDING':
                        pending_count += 1
        
        return {
            'total_requirements': total_requirements,
            'verified': verified_count,
            'pending': pending_count,
            'completion_rate': round((verified_count / total_requirements * 100) if total_requirements > 0 else 0, 1),
        }


class ProjectTimelineView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Visual timeline view of project lifecycle
    """
    model = TrainingNotification
    template_name = 'projects/timeline.html'
    context_object_name = 'project'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        
        # Build timeline events
        events = []
        
        # Project created
        events.append({
            'date': project.created_at,
            'type': 'milestone',
            'title': 'Project Created',
            'description': f'Project "{project.title}" was created',
            'icon': 'plus-circle',
            'color': 'blue',
        })
        
        # Deliverables
        for deliverable in project.deliverables.all():
            events.append({
                'date': deliverable.due_date,
                'type': 'deliverable',
                'title': deliverable.title,
                'description': f'{deliverable.get_deliverable_type_display()} - {deliverable.get_status_display()}',
                'icon': 'clipboard-check',
                'color': 'green' if deliverable.status == 'COMPLETED' else ('yellow' if deliverable.status == 'IN_PROGRESS' else 'gray'),
                'status': deliverable.status,
            })
        
        # Tranche payments
        for tranche in project.tranches.all():
            events.append({
                'date': tranche.due_date,
                'type': 'payment',
                'title': tranche.name,
                'description': f'R{tranche.amount:,.2f} - {tranche.get_status_display()}',
                'icon': 'currency-dollar',
                'color': 'green' if tranche.status == 'PAID' else ('blue' if tranche.status == 'SUBMITTED' else 'gray'),
                'status': tranche.status,
            })
        
        # Moderation requests
        for mod in project.moderation_requests.all():
            if mod.scheduled_date:
                events.append({
                    'date': mod.scheduled_date,
                    'type': 'moderation',
                    'title': f'External Moderation - {mod.etqa_name}',
                    'description': mod.get_status_display(),
                    'icon': 'badge-check',
                    'color': 'purple',
                })
        
        # Sort by date
        events.sort(key=lambda x: x['date'] if x['date'] else timezone.now().date())
        
        context['timeline_events'] = events
        return context


class ProjectFinanceView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Detailed financial view for a project
    """
    model = TrainingNotification
    template_name = 'projects/finance.html'
    context_object_name = 'project'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        
        # Tranches with full details
        tranches = TrancheSchedule.objects.filter(
            training_notification=project
        ).prefetch_related(
            'evidence_requirements__evidences',
            'submissions',
            'comments'
        ).order_by('sequence_number')
        
        context['tranches'] = tranches
        
        # All invoices
        context['invoices'] = Invoice.objects.filter(
            tranche__training_notification=project
        ).select_related('tranche').order_by('-invoice_date')
        
        # All payments
        context['payments'] = Payment.objects.filter(
            invoice__tranche__training_notification=project
        ).select_related('invoice').order_by('-payment_date')
        
        # Financial metrics
        total_contract = project.contract_value or Decimal('0')
        total_scheduled = tranches.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        total_received = tranches.aggregate(t=Sum('actual_amount_received'))['t'] or Decimal('0')
        total_invoiced = context['invoices'].aggregate(t=Sum('total_amount'))['t'] or Decimal('0')
        total_paid = context['payments'].filter(status='COMPLETED').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        
        context['metrics'] = {
            'contract_value': total_contract,
            'scheduled': total_scheduled,
            'received': total_received,
            'invoiced': total_invoiced,
            'paid': total_paid,
            'outstanding': total_scheduled - total_received,
            'variance': total_contract - total_scheduled,
        }
        
        # Cashflow projection (next 6 months)
        from calendar import month_name
        today = date.today()
        cashflow = []
        for i in range(6):
            month_date = today.replace(day=1) + timedelta(days=32 * i)
            month_date = month_date.replace(day=1)
            month_end = (month_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            expected = tranches.filter(
                due_date__gte=month_date,
                due_date__lte=month_end,
                status__in=['SCHEDULED', 'EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE', 'PENDING_QC', 'QC_PASSED', 'SUBMITTED']
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            
            cashflow.append({
                'month': month_name[month_date.month],
                'year': month_date.year,
                'expected': expected,
            })
        
        context['cashflow'] = cashflow
        
        return context


class ProjectDeliverablesView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Detailed deliverables view with evidence tracking
    """
    model = TrainingNotification
    template_name = 'projects/deliverables.html'
    context_object_name = 'project'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        today = date.today()
        
        # Deliverables grouped by type
        deliverables = NOTDeliverable.objects.filter(
            training_notification=project
        ).select_related('assigned_to__user').order_by('due_date')
        
        # Group by type
        by_type = {}
        for d in deliverables:
            dtype = d.deliverable_type
            if dtype not in by_type:
                by_type[dtype] = []
            by_type[dtype].append(d)
        
        context['deliverables_by_type'] = by_type
        context['deliverables'] = deliverables
        
        # Statistics
        context['stats'] = {
            'total': deliverables.count(),
            'completed': deliverables.filter(status='COMPLETED').count(),
            'in_progress': deliverables.filter(status='IN_PROGRESS').count(),
            'pending': deliverables.filter(status='PENDING').count(),
            'overdue': deliverables.filter(
                status__in=['PENDING', 'IN_PROGRESS'],
                due_date__lt=today
            ).count(),
        }
        
        return context


class ProjectLearnersView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Learner management view for a project
    """
    model = TrainingNotification
    template_name = 'projects/learners.html'
    context_object_name = 'project'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        
        # Get all enrollments for this project (through cohort)
        if project.cohort:
            enrollments = Enrollment.objects.filter(
                cohort=project.cohort
            ).select_related('learner', 'qualification', 'cohort').order_by('learner__last_name')
        else:
            enrollments = Enrollment.objects.none()
        
        context['enrollments'] = enrollments
        
        # Statistics
        context['stats'] = {
            'expected': project.expected_learner_count or 0,
            'enrolled': enrollments.count(),
            'active': enrollments.filter(status='ACTIVE').count(),
            'completed': enrollments.filter(status='COMPLETED').count(),
            'withdrawn': enrollments.filter(status='WITHDRAWN').count(),
        }
        
        # Training classes
        context['classes'] = TrainingClass.objects.filter(
            training_notification=project
        ).select_related('facilitator__user').annotate(
            learner_count=Count('learner_assignments', filter=Q(learner_assignments__is_active=True))
        ).order_by('group_number')
        
        return context


# API Views for AJAX operations

def project_stats_api(request, pk):
    """API endpoint for project statistics"""
    project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
    
    tranches = project.tranches.all()
    deliverables = project.deliverables.all()
    
    data = {
        'financial': {
            'contract_value': float(project.contract_value or 0),
            'total_scheduled': float(sum(t.amount or 0 for t in tranches)),
            'total_received': float(sum(t.actual_amount_received or 0 for t in tranches)),
        },
        'deliverables': {
            'total': deliverables.count(),
            'completed': deliverables.filter(status='COMPLETED').count(),
            'overdue': deliverables.filter(status__in=['PENDING', 'IN_PROGRESS'], due_date__lt=date.today()).count(),
        },
        'learners': {
            'expected': project.expected_learner_count or 0,
        }
    }
    
    return JsonResponse(data)


# =====================================================
# DELIVERABLE EVIDENCE MANAGEMENT
# =====================================================

class DeliverableEvidenceUploadView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Handle evidence file uploads for a deliverable.
    Supports multiple file uploads via AJAX.
    """
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, pk, deliverable_pk):
        """Handle file upload via AJAX"""
        project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        deliverable = get_object_or_404(NOTDeliverable, pk=deliverable_pk, training_notification=project)
        
        files = request.FILES.getlist('files')
        if not files:
            return JsonResponse({'success': False, 'error': 'No files provided'}, status=400)
        
        uploaded = []
        errors = []
        
        for file in files:
            try:
                # Create evidence record
                evidence = NOTDeliverableEvidence(
                    deliverable=deliverable,
                    file=file,
                    title=file.name,
                    original_filename=file.name,
                    file_size=file.size,
                    created_by=request.user
                )
                evidence.full_clean()  # Validate file
                evidence.save()
                
                uploaded.append({
                    'id': evidence.pk,
                    'title': evidence.title,
                    'filename': evidence.original_filename,
                    'size': evidence.file_size_display,
                    'status': evidence.status,
                    'url': evidence.file.url,
                    'is_image': evidence.is_image,
                })
            except Exception as e:
                errors.append({
                    'filename': file.name,
                    'error': str(e)
                })
        
        return JsonResponse({
            'success': len(uploaded) > 0,
            'uploaded': uploaded,
            'errors': errors,
            'evidence_count': deliverable.evidence_count,
        })


class DeliverableEvidenceDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Delete an evidence file from a deliverable"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, pk, evidence_pk):
        """Handle evidence deletion via AJAX"""
        project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        evidence = get_object_or_404(
            NOTDeliverableEvidence, 
            pk=evidence_pk, 
            deliverable__training_notification=project
        )
        deliverable = evidence.deliverable
        
        # Only allow deletion of pending evidence
        if evidence.status == 'VERIFIED':
            return JsonResponse({
                'success': False, 
                'error': 'Cannot delete verified evidence'
            }, status=400)
        
        # Delete the file and record
        evidence.file.delete(save=False)
        evidence.delete()
        
        return JsonResponse({
            'success': True,
            'evidence_count': deliverable.evidence_count,
        })


class DeliverableEvidenceVerifyView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Verify or reject an evidence file (QC workflow)"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, pk, evidence_pk):
        """Handle evidence verification via AJAX"""
        project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        evidence = get_object_or_404(
            NOTDeliverableEvidence, 
            pk=evidence_pk, 
            deliverable__training_notification=project
        )
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST
        
        action = data.get('action')
        notes = data.get('notes', '')
        
        if action == 'verify':
            evidence.status = 'VERIFIED'
            evidence.verified_by = request.user
            evidence.verified_at = timezone.now()
            evidence.verification_notes = notes
            evidence.save()
            
            return JsonResponse({
                'success': True,
                'status': 'VERIFIED',
                'status_display': 'Verified',
                'verified_by': request.user.get_full_name(),
                'verified_at': evidence.verified_at.strftime('%d %b %Y %H:%M'),
            })
        
        elif action == 'reject':
            evidence.status = 'REJECTED'
            evidence.verified_by = request.user
            evidence.verified_at = timezone.now()
            evidence.rejection_reason = notes
            evidence.save()
            
            return JsonResponse({
                'success': True,
                'status': 'REJECTED',
                'status_display': 'Rejected',
                'rejection_reason': notes,
            })
        
        elif action == 'needs_revision':
            evidence.status = 'NEEDS_REVISION'
            evidence.verified_by = request.user
            evidence.verified_at = timezone.now()
            evidence.verification_notes = notes
            evidence.save()
            
            return JsonResponse({
                'success': True,
                'status': 'NEEDS_REVISION',
                'status_display': 'Needs Revision',
                'notes': notes,
            })
        
        return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)


class DeliverableEvidenceListView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Get evidence list for a deliverable via AJAX"""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request, pk, deliverable_pk):
        project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        deliverable = get_object_or_404(NOTDeliverable, pk=deliverable_pk, training_notification=project)
        
        evidence_list = []
        for e in deliverable.evidence_files.all():
            evidence_list.append({
                'id': e.pk,
                'title': e.title,
                'filename': e.original_filename,
                'size': e.file_size_display,
                'status': e.status,
                'status_display': e.get_status_display(),
                'url': e.file.url,
                'is_image': e.is_image,
                'is_pdf': e.is_pdf,
                'uploaded_at': e.created_at.strftime('%d %b %Y %H:%M'),
                'uploaded_by': e.created_by.get_full_name() if e.created_by else 'Unknown',
                'verified_by': e.verified_by.get_full_name() if e.verified_by else None,
                'verified_at': e.verified_at.strftime('%d %b %Y %H:%M') if e.verified_at else None,
            })
        
        # Get QC requirements for this deliverable type
        requirements = []
        for req in NOTDeliverableEvidenceRequirement.objects.filter(deliverable_type=deliverable.deliverable_type):
            fulfilled = deliverable.evidence_files.filter(requirement=req, status='VERIFIED').exists()
            requirements.append({
                'id': req.pk,
                'name': req.name,
                'description': req.description,
                'is_mandatory': req.is_mandatory,
                'acceptance_criteria': req.acceptance_criteria,
                'fulfilled': fulfilled,
            })
        
        return JsonResponse({
            'success': True,
            'deliverable': {
                'id': deliverable.pk,
                'title': deliverable.title,
                'status': deliverable.status,
            },
            'evidence': evidence_list,
            'requirements': requirements,
            'stats': {
                'total': deliverable.evidence_count,
                'verified': deliverable.verified_evidence_count,
                'pending': deliverable.pending_evidence_count,
            }
        })


# =====================================================
# PROJECT FINANCE & BILLING VIEWS
# =====================================================

class ProjectBillingScheduleView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    View and manage billing schedule for a project.
    Includes scheduled invoices, payment tracking, and collection metrics.
    """
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request, pk):
        """Get billing schedule and invoices for a project."""
        project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        # Get or create billing schedule
        try:
            billing_schedule = project.project_billing_schedule
        except ProjectBillingSchedule.DoesNotExist:
            # Create billing schedule if it doesn't exist
            from finance.services.invoice_generation import InvoiceGenerationService
            billing_schedule = InvoiceGenerationService.create_billing_schedule_for_not(project)
        
        # If browser request (not AJAX), render template
        if 'application/json' not in request.headers.get('Accept', ''):
            return render(request, 'projects/billing_schedule.html', {'project': project})
        
        # Get scheduled invoices
        scheduled_invoices = billing_schedule.scheduled_invoices.all().order_by('period_number')
        
        # Get collection metrics
        try:
            quarterly_metrics = FunderCollectionMetrics.objects.filter(
                entity_type='PROJECT',
                period_type='QUARTERLY',
                training_notification=project
            ).latest('period_end')
        except FunderCollectionMetrics.DoesNotExist:
            quarterly_metrics = None
        
        try:
            lifetime_metrics = FunderCollectionMetrics.objects.filter(
                entity_type='PROJECT',
                period_type='LIFETIME',
                training_notification=project
            ).latest('period_end')
        except FunderCollectionMetrics.DoesNotExist:
            lifetime_metrics = None
        
        # Build response data
        data = {
            'success': True,
            'project': {
                'id': project.pk,
                'reference_number': project.reference_number,
                'title': project.title,
                'contract_value': float(project.contract_value or 0),
                'planned_start_date': project.planned_start_date.isoformat() if project.planned_start_date else None,
                'planned_end_date': project.planned_end_date.isoformat() if project.planned_end_date else None,
                'funder': project.funder,
                'funder_display': project.get_funder_display() if project.funder else None,
            },
            'billing_schedule': {
                'id': billing_schedule.pk,
                'schedule_type': billing_schedule.schedule_type,
                'schedule_type_display': billing_schedule.get_schedule_type_display(),
                'invoice_type': billing_schedule.invoice_type,
                'invoice_type_display': billing_schedule.get_invoice_type_display(),
                'total_contract_value': float(billing_schedule.total_contract_value),
                'amount_per_period': float(billing_schedule.amount_per_period or 0),
                'billing_start_date': billing_schedule.billing_start_date.isoformat() if billing_schedule.billing_start_date else None,
                'billing_end_date': billing_schedule.billing_end_date.isoformat() if billing_schedule.billing_end_date else None,
                'billing_day_of_month': billing_schedule.billing_day_of_month,
                'payment_terms_days': billing_schedule.payment_terms_days,
                'next_invoice_date': billing_schedule.next_invoice_date.isoformat() if billing_schedule.next_invoice_date else None,
                'auto_generate': billing_schedule.auto_generate,
                'auto_convert_on_payment': billing_schedule.auto_convert_on_payment,
                'periods_count': billing_schedule.calculate_periods() if billing_schedule.billing_end_date else 0,
            },
            'scheduled_invoices': [
                {
                    'id': si.pk,
                    'period_number': si.period_number,
                    'scheduled_date': si.scheduled_date.isoformat(),
                    'due_date': si.due_date.isoformat(),
                    'amount': float(si.amount),
                    'status': si.status,
                    'status_display': si.get_status_display(),
                    'invoice_number': si.invoice.invoice_number if si.invoice else None,
                    'invoice_id': si.invoice.pk if si.invoice else None,
                    'deliverable_title': si.deliverable.title if si.deliverable else None,
                }
                for si in scheduled_invoices
            ],
            'choices': {
                'schedule_types': [
                    {'value': 'MONTHLY', 'label': 'Monthly'},
                    {'value': 'QUARTERLY', 'label': 'Quarterly'},
                    {'value': 'DELIVERABLE', 'label': 'Based on Deliverables'},
                    {'value': 'ANNUALLY', 'label': 'Annually'},
                    {'value': 'UPFRONT', 'label': 'Upfront (Full Payment)'},
                    {'value': 'MANUAL', 'label': 'Manual Override'},
                ],
                'invoice_types': [
                    {'value': 'PROFORMA', 'label': 'Pro Forma'},
                    {'value': 'TAX', 'label': 'Tax Invoice'},
                ],
            },
            'metrics': {
                'quarterly': {
                    'collection_rate': float(quarterly_metrics.collection_rate) if quarterly_metrics else 0,
                    'persistency_rate': float(quarterly_metrics.persistency_rate) if quarterly_metrics else 0,
                    'average_days_to_payment': float(quarterly_metrics.average_days_to_payment) if quarterly_metrics and quarterly_metrics.average_days_to_payment else None,
                    'risk_rating': quarterly_metrics.risk_rating if quarterly_metrics else 'MEDIUM',
                    'is_good_business': quarterly_metrics.is_good_business if quarterly_metrics else None,
                } if quarterly_metrics else None,
                'lifetime': {
                    'total_invoiced': float(lifetime_metrics.total_invoiced) if lifetime_metrics else 0,
                    'total_collected': float(lifetime_metrics.total_collected) if lifetime_metrics else 0,
                    'total_outstanding': float(lifetime_metrics.total_outstanding) if lifetime_metrics else 0,
                    'collection_rate': float(lifetime_metrics.collection_rate) if lifetime_metrics else 0,
                    'invoices_issued': lifetime_metrics.invoices_issued if lifetime_metrics else 0,
                    'invoices_paid_on_time': lifetime_metrics.invoices_paid_on_time if lifetime_metrics else 0,
                    'invoices_outstanding': lifetime_metrics.invoices_outstanding if lifetime_metrics else 0,
                    'aging': {
                        'current': float(lifetime_metrics.aging_current) if lifetime_metrics else 0,
                        '30_days': float(lifetime_metrics.aging_30_days) if lifetime_metrics else 0,
                        '60_days': float(lifetime_metrics.aging_60_days) if lifetime_metrics else 0,
                        '90_days': float(lifetime_metrics.aging_90_days) if lifetime_metrics else 0,
                        'over_90': float(lifetime_metrics.aging_over_90) if lifetime_metrics else 0,
                    }
                } if lifetime_metrics else None,
            }
        }
        
        return JsonResponse(data)
    
    def post(self, request, pk):
        """Update billing schedule settings."""
        project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST
        
        # Get or create billing schedule
        try:
            billing_schedule = project.project_billing_schedule
        except ProjectBillingSchedule.DoesNotExist:
            from finance.services.invoice_generation import InvoiceGenerationService
            billing_schedule = InvoiceGenerationService.create_billing_schedule_for_not(project)
        
        regenerate_invoices = False
        
        # Update fields
        if 'schedule_type' in data:
            if billing_schedule.schedule_type != data['schedule_type']:
                regenerate_invoices = True
            billing_schedule.schedule_type = data['schedule_type']
        if 'invoice_type' in data:
            billing_schedule.invoice_type = data['invoice_type']
        if 'auto_generate' in data:
            billing_schedule.auto_generate = data.get('auto_generate') in ['true', 'True', True, '1', 1]
        if 'total_contract_value' in data:
            new_value = Decimal(str(data['total_contract_value']))
            if billing_schedule.total_contract_value != new_value:
                regenerate_invoices = True
            billing_schedule.total_contract_value = new_value
        if 'amount_per_period' in data:
            billing_schedule.amount_per_period = Decimal(str(data['amount_per_period']))
        if 'billing_start_date' in data and data['billing_start_date']:
            from datetime import datetime
            new_date = datetime.strptime(data['billing_start_date'], '%Y-%m-%d').date()
            if billing_schedule.billing_start_date != new_date:
                regenerate_invoices = True
            billing_schedule.billing_start_date = new_date
        if 'billing_end_date' in data and data['billing_end_date']:
            from datetime import datetime
            new_date = datetime.strptime(data['billing_end_date'], '%Y-%m-%d').date()
            if billing_schedule.billing_end_date != new_date:
                regenerate_invoices = True
            billing_schedule.billing_end_date = new_date
        if 'billing_day_of_month' in data:
            billing_schedule.billing_day_of_month = int(data['billing_day_of_month'])
        if 'payment_terms_days' in data:
            billing_schedule.payment_terms_days = int(data['payment_terms_days'])
        
        # Recalculate amount per period if total changed
        if billing_schedule.total_contract_value and billing_schedule.schedule_type != 'MANUAL':
            periods = billing_schedule.calculate_periods()
            if periods > 0:
                billing_schedule.amount_per_period = billing_schedule.total_contract_value / periods
        
        billing_schedule.save()
        
        # Regenerate scheduled invoices if key fields changed
        if regenerate_invoices or 'regenerate' in data:
            from finance.services.invoice_generation import InvoiceGenerationService
            InvoiceGenerationService.generate_scheduled_invoices(billing_schedule)
        
        return JsonResponse({'success': True, 'message': 'Billing schedule updated'})


class GenerateInvoiceView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Generate invoice for a scheduled invoice."""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, pk, scheduled_pk):
        """Generate invoice for a specific scheduled invoice."""
        project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        scheduled = get_object_or_404(
            ScheduledInvoice,
            pk=scheduled_pk,
            billing_schedule__training_notification=project
        )
        
        if scheduled.invoice:
            return JsonResponse({
                'success': False,
                'error': 'Invoice already generated'
            }, status=400)
        
        from finance.services.invoice_generation import InvoiceGenerationService
        try:
            invoice = InvoiceGenerationService.generate_invoice_for_scheduled(scheduled)
            return JsonResponse({
                'success': True,
                'invoice': {
                    'id': invoice.pk,
                    'invoice_number': invoice.invoice_number,
                    'total': float(invoice.total),
                    'status': invoice.status,
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class RecalculateMetricsView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Recalculate collection metrics for a project."""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, pk):
        """Recalculate metrics for project."""
        project = get_object_or_404(TrainingNotification, pk=pk, is_deleted=False)
        
        from finance.services.invoice_generation import CollectionMetricsService
        try:
            quarterly = CollectionMetricsService.calculate_project_metrics(project, 'QUARTERLY')
            lifetime = CollectionMetricsService.calculate_project_metrics(project, 'LIFETIME')
            
            return JsonResponse({
                'success': True,
                'quarterly': {
                    'collection_rate': float(quarterly.collection_rate),
                    'risk_rating': quarterly.risk_rating,
                },
                'lifetime': {
                    'collection_rate': float(lifetime.collection_rate),
                    'total_collected': float(lifetime.total_collected),
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class FunderMetricsView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Get collection metrics by funder type for comparison."""
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get(self, request):
        """Get metrics for all funder types."""
        funder_types = ['PRIVATE', 'SETA', 'CORPORATE', 'CORPORATE_DG', 'MUNICIPALITY', 'GOVERNMENT']
        
        metrics_data = []
        for funder_type in funder_types:
            try:
                metrics = FunderCollectionMetrics.objects.filter(
                    entity_type='FUNDER_TYPE',
                    period_type='QUARTERLY',
                    funder_type=funder_type
                ).latest('period_end')
                
                metrics_data.append({
                    'funder_type': funder_type,
                    'funder_display': dict(TrainingNotification.FUNDER_CHOICES).get(funder_type, funder_type),
                    'collection_rate': float(metrics.collection_rate),
                    'persistency_rate': float(metrics.persistency_rate),
                    'average_days_to_payment': float(metrics.average_days_to_payment) if metrics.average_days_to_payment else None,
                    'risk_rating': metrics.risk_rating,
                    'is_good_business': metrics.is_good_business,
                    'total_invoiced': float(metrics.total_invoiced),
                    'total_collected': float(metrics.total_collected),
                })
            except FunderCollectionMetrics.DoesNotExist:
                metrics_data.append({
                    'funder_type': funder_type,
                    'funder_display': dict(TrainingNotification.FUNDER_CHOICES).get(funder_type, funder_type),
                    'collection_rate': 0,
                    'persistency_rate': 0,
                    'average_days_to_payment': None,
                    'risk_rating': 'MEDIUM',
                    'is_good_business': None,
                    'total_invoiced': 0,
                    'total_collected': 0,
                })
        
        return JsonResponse({
            'success': True,
            'metrics': metrics_data
        })
