from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.db.models import Count, Sum, Q, Max, Prefetch
from django.db import models
from django.utils import timezone
from django.urls import reverse_lazy
from django.http import JsonResponse
from datetime import date, datetime

from learners.models import Learner
from .models import (
    CorporateClient, CorporateContact, CorporateEmployee,
    ServiceCategory, ServiceOffering, ClientServiceSubscription,
    HostEmployer, HostMentor, WorkplacePlacement,
    TradeTestVenue, LegacyTradeTestBooking, LegacyTradeTestResult,
    # CRM Models
    LeadSource, CorporateOpportunity, CorporateActivity, ServiceProposal, ProposalLineItem,
    # Service Delivery Models
    ServiceDeliveryProject, ProjectMilestone, MilestoneTask, ProjectDocument,
    # WSP/ATR Models
    WSPYear, WSPSubmission, WSPPlannedTraining, ATRSubmission, ATRCompletedTraining,
    WSPATREvidence, WSPATREvidenceCategory, WSPATRChecklist,
    # Committee Models
    Committee, CommitteeMember, CommitteeMeeting, MeetingAgendaItem, MeetingActionItem,
    # Service Delivery
    AnnualServiceDelivery, ServiceDeliveryActivity, EmployeeQualification,
    # WSP/ATR Service Enhancement Models
    TrainingCommittee, TrainingCommitteeMember, TrainingCommitteeMeeting,
    TCMeetingAgendaItem, TCMeetingAttendance, TCMeetingActionItem, MeetingMinutes,
    WSPATRServiceYear, WSPATREmployeeData, WSPATRTrainingData, WSPATRPivotalData,
    MeetingTemplate, WSPATRDocument, WSPATRDocumentTemplate,
    EmployeeIDP, IDPTrainingNeed,
    # Employment Equity Models
    ClientEmployeeSnapshot, OccupationalLevelData,
    EEServiceYear, EEPlan, EEAnalysis, EEBarrier, EENumericalGoal,
    EEIncomeDifferential, EEDocument,
    # B-BBEE Models
    BBBEEScorecard, BBBEEServiceYear, BBBEEDocument,
    OwnershipStructure, Shareholder, ManagementControlProfile,
    SkillsDevelopmentElement, ESDElement, ESDSupplier,
    SEDElement, SEDContribution, TransformationPlan
)
from learners.models import SETA
from core.models import User


# =============================================================================
# CORPORATE DASHBOARD
# =============================================================================

@login_required
def corporate_dashboard(request):
    """Main corporate management dashboard with overview of all services."""
    
    # Client statistics
    total_clients = CorporateClient.objects.count()
    active_clients = CorporateClient.objects.filter(status='ACTIVE').count()
    
    # Service subscription statistics
    active_subscriptions = ClientServiceSubscription.objects.filter(status='ACTIVE').count()
    pending_subscriptions = ClientServiceSubscription.objects.filter(status='PENDING').count()
    
    # Host employer statistics
    total_host_employers = HostEmployer.objects.count()
    approved_host_employers = HostEmployer.objects.filter(status='APPROVED').count()
    total_capacity = HostEmployer.objects.filter(status='APPROVED').aggregate(
        total=Sum('max_placement_capacity')
    )['total'] or 0
    
    # Active placements
    active_placements = WorkplacePlacement.objects.filter(status='ACTIVE').count()
    
    # Trade test statistics
    pending_bookings = LegacyTradeTestBooking.objects.filter(status='PENDING').count()
    upcoming_tests = LegacyTradeTestBooking.objects.filter(
        status='CONFIRMED',
        scheduled_date__gte=timezone.now().date()
    ).count()
    
    # Recent activities
    recent_subscriptions = ClientServiceSubscription.objects.select_related(
        'client', 'service'
    ).order_by('-created_at')[:5]
    
    recent_placements = WorkplacePlacement.objects.select_related(
        'host', 'learner'
    ).order_by('-created_at')[:5]
    
    recent_bookings = LegacyTradeTestBooking.objects.select_related(
        'learner', 'venue'
    ).order_by('-created_at')[:5]
    
    # Service category breakdown
    service_categories = ServiceCategory.objects.filter(is_active=True)
    category_stats = []
    for category in service_categories:
        count = ClientServiceSubscription.objects.filter(
            service__category=category,
            status='ACTIVE'
        ).count()
        category_stats.append({'code': category.code, 'name': category.name, 'count': count})
    
    context = {
        'total_clients': total_clients,
        'active_clients': active_clients,
        'active_subscriptions': active_subscriptions,
        'pending_subscriptions': pending_subscriptions,
        'total_host_employers': total_host_employers,
        'approved_host_employers': approved_host_employers,
        'total_capacity': total_capacity,
        'active_placements': active_placements,
        'pending_bookings': pending_bookings,
        'upcoming_tests': upcoming_tests,
        'recent_subscriptions': recent_subscriptions,
        'recent_placements': recent_placements,
        'recent_bookings': recent_bookings,
        'category_stats': category_stats,
    }
    
    return render(request, 'corporate/dashboard.html', context)


# =============================================================================
# CORPORATE CLIENTS
# =============================================================================

class CorporateClientListView(LoginRequiredMixin, ListView):
    """List all corporate clients."""
    model = CorporateClient
    template_name = 'corporate/client_list.html'
    context_object_name = 'clients'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = CorporateClient.objects.annotate(
            service_count=Count('service_subscriptions', filter=Q(service_subscriptions__status='ACTIVE'))
        ).order_by('-created_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(status='ACTIVE')
        elif status == 'inactive':
            queryset = queryset.filter(status='INACTIVE')
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(company_name__icontains=search) |
                Q(registration_number__icontains=search) |
                Q(seta_number__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['search'] = self.request.GET.get('search', '')
        return context


class CorporateClientDetailView(LoginRequiredMixin, DetailView):
    """View detailed client profile with all services."""
    model = CorporateClient
    template_name = 'corporate/client_detail.html'
    context_object_name = 'client'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        client = self.object
        
        # Get contacts
        context['contacts'] = client.contacts.all()
        
        # Get service subscriptions by category
        subscriptions = client.service_subscriptions.select_related('service').all()
        context['subscriptions'] = subscriptions
        context['active_subscriptions'] = subscriptions.filter(status='ACTIVE')
        
        # Get host employers linked to this client (through employer link)
        context['host_employers'] = HostEmployer.objects.filter(employer__isnull=False)
        
        # Get placements
        context['placements'] = WorkplacePlacement.objects.select_related('learner', 'host')[:10]
        
        return context


class CorporateClientCreateView(LoginRequiredMixin, CreateView):
    """Create a new corporate client."""
    model = CorporateClient
    template_name = 'corporate/client_form.html'
    fields = [
        'company_name', 'trading_name', 'registration_number', 'vat_number',
        'seta', 'seta_number', 'industry', 'physical_address', 'postal_address',
        'phone', 'email', 'website', 'status', 'client_tier', 'employee_count', 
        'annual_revenue', 'notes'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get services grouped by category for the service selection
        context['service_categories'] = ServiceCategory.objects.prefetch_related(
            Prefetch('services', queryset=ServiceOffering.objects.filter(is_active=True))
        ).filter(is_active=True).order_by('display_order')
        return context
    
    def form_valid(self, form):
        from datetime import date
        from tenants.models import Campus
        
        # Set the campus from user's profile or default
        if hasattr(self.request.user, 'campus') and self.request.user.campus:
            form.instance.campus = self.request.user.campus
        else:
            # Fallback to first campus
            form.instance.campus = Campus.objects.first()
        
        response = super().form_valid(form)
        
        # Handle selected services
        selected_services = self.request.POST.getlist('services')
        if selected_services:
            for service_id in selected_services:
                try:
                    service = ServiceOffering.objects.get(pk=service_id)
                    ClientServiceSubscription.objects.create(
                        client=self.object,
                        service=service,
                        campus=self.object.campus,
                        start_date=date.today(),
                        status='PENDING',
                        agreed_price=service.base_price
                    )
                except ServiceOffering.DoesNotExist:
                    pass
            
            service_count = len(selected_services)
            messages.success(
                self.request, 
                f"Corporate client '{form.instance.company_name}' created successfully with {service_count} service(s)."
            )
        else:
            messages.success(self.request, f"Corporate client '{form.instance.company_name}' created successfully.")
        
        return response
    
    def get_success_url(self):
        return reverse_lazy('corporate:client_detail', kwargs={'pk': self.object.pk})


class CorporateClientUpdateView(LoginRequiredMixin, UpdateView):
    """Update a corporate client."""
    model = CorporateClient
    template_name = 'corporate/client_form.html'
    fields = [
        'company_name', 'trading_name', 'registration_number', 'vat_number',
        'seta', 'seta_number', 'industry', 'physical_address', 'postal_address',
        'phone', 'email', 'website', 'status', 'client_tier', 'employee_count',
        'annual_revenue', 'notes'
    ]
    
    def form_valid(self, form):
        messages.success(self.request, f"Corporate client '{form.instance.company_name}' updated successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('corporate:client_detail', kwargs={'pk': self.object.pk})


# =============================================================================
# SERVICE OFFERINGS
# =============================================================================

class ServiceOfferingListView(LoginRequiredMixin, ListView):
    """List all service offerings."""
    model = ServiceOffering
    template_name = 'corporate/service_list.html'
    context_object_name = 'services'
    
    def get_queryset(self):
        queryset = ServiceOffering.objects.select_related('category').annotate(
            subscription_count=Count('subscriptions', filter=Q(subscriptions__status='ACTIVE'))
        ).order_by('category__display_order', 'name')
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category__code=category)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ServiceCategory.objects.filter(is_active=True)
        context['selected_category'] = self.request.GET.get('category', '')
        return context


class ServiceOfferingDetailView(LoginRequiredMixin, DetailView):
    """View service offering details."""
    model = ServiceOffering
    template_name = 'corporate/service_detail.html'
    context_object_name = 'service'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subscriptions'] = self.object.subscriptions.select_related('client').all()
        return context


# =============================================================================
# SERVICE SUBSCRIPTIONS
# =============================================================================

@login_required
def add_subscription(request, client_pk):
    """Add a service subscription to a client."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    if request.method == 'POST':
        service_id = request.POST.get('service')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date') or None
        agreed_price = request.POST.get('agreed_price') or None
        notes = request.POST.get('notes', '')
        
        service = get_object_or_404(ServiceOffering, pk=service_id)
        
        # Get campus from request or client
        campus = getattr(request, 'campus', None) or client.campus
        
        subscription = ClientServiceSubscription.objects.create(
            client=client,
            service=service,
            start_date=start_date,
            end_date=end_date,
            agreed_price=agreed_price,
            notes=notes,
            status='PENDING',
            campus=campus
        )
        
        messages.success(request, f"Service '{service.name}' added to {client.company_name}.")
        return redirect('corporate:client_detail', pk=client_pk)
    
    services = ServiceOffering.objects.filter(is_active=True).select_related('category').order_by('category__display_order', 'name')
    
    return render(request, 'corporate/subscription_form.html', {
        'client': client,
        'services': services,
    })


@login_required
def update_subscription_status(request, pk):
    """Update subscription status."""
    subscription = get_object_or_404(ClientServiceSubscription, pk=pk)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [choice[0] for choice in ClientServiceSubscription.STATUS_CHOICES]
        if new_status in valid_statuses:
            subscription.status = new_status
            subscription.save()
            messages.success(request, f"Subscription status updated to {subscription.get_status_display()}.")
    
    return redirect('corporate:client_detail', pk=subscription.client.pk)


# =============================================================================
# HOST EMPLOYERS
# =============================================================================

class HostEmployerListView(LoginRequiredMixin, ListView):
    """List all host employers."""
    model = HostEmployer
    template_name = 'corporate/host_employer_list.html'
    context_object_name = 'host_employers'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = HostEmployer.objects.annotate(
            placement_count=Count('placements', filter=Q(placements__status='ACTIVE')),
            mentor_count=Count('mentors')
        ).order_by('-created_at')
        
        # Filter by approval status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(company_name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = HostEmployer.STATUS_CHOICES
        context['selected_status'] = self.request.GET.get('status', '')
        context['search'] = self.request.GET.get('search', '')
        return context


class HostEmployerDetailView(LoginRequiredMixin, DetailView):
    """View host employer details."""
    model = HostEmployer
    template_name = 'corporate/host_employer_detail.html'
    context_object_name = 'host_employer'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mentors'] = self.object.mentors.all()
        context['placements'] = self.object.placements.select_related('learner', 'mentor').all()
        context['active_placements'] = context['placements'].filter(status='ACTIVE')
        return context


class HostEmployerCreateView(LoginRequiredMixin, CreateView):
    """Create a new host employer."""
    model = HostEmployer
    template_name = 'corporate/host_employer_form.html'
    fields = [
        'company_name', 'trading_name', 'registration_number', 'physical_address',
        'contact_person', 'contact_email', 'contact_phone',
        'max_placement_capacity', 'seta', 'status', 'notes'
    ]
    
    def form_valid(self, form):
        messages.success(self.request, f"Host employer '{form.instance.company_name}' created successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('corporate:host_employer_detail', kwargs={'pk': self.object.pk})


class HostEmployerUpdateView(LoginRequiredMixin, UpdateView):
    """Update a host employer."""
    model = HostEmployer
    template_name = 'corporate/host_employer_form.html'
    fields = [
        'company_name', 'trading_name', 'registration_number', 'physical_address',
        'contact_person', 'contact_email', 'contact_phone',
        'max_placement_capacity', 'seta', 'status', 'notes'
    ]
    
    def form_valid(self, form):
        messages.success(self.request, f"Host employer '{form.instance.company_name}' updated successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('corporate:host_employer_detail', kwargs={'pk': self.object.pk})


# =============================================================================
# WORKPLACE PLACEMENTS
# =============================================================================

class WorkplacePlacementListView(LoginRequiredMixin, ListView):
    """List all workplace placements."""
    model = WorkplacePlacement
    template_name = 'corporate/placement_list.html'
    context_object_name = 'placements'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = WorkplacePlacement.objects.select_related(
            'host', 'learner', 'mentor'
        ).order_by('-created_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = WorkplacePlacement.STATUS_CHOICES
        context['selected_status'] = self.request.GET.get('status', '')
        return context


@login_required
def create_placement(request, host_employer_pk):
    """Create a new workplace placement."""
    host_employer = get_object_or_404(HostEmployer, pk=host_employer_pk)
    
    if request.method == 'POST':
        from learners.models import Learner
        from academics.models import Enrollment
        
        learner_id = request.POST.get('learner')
        enrollment_id = request.POST.get('enrollment')
        mentor_id = request.POST.get('mentor') or None
        start_date = request.POST.get('start_date')
        expected_end_date = request.POST.get('expected_end_date') or None
        notes = request.POST.get('notes', '')
        
        learner = get_object_or_404(Learner, pk=learner_id)
        enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
        mentor = HostMentor.objects.filter(pk=mentor_id).first() if mentor_id else None
        
        placement = WorkplacePlacement.objects.create(
            host=host_employer,
            learner=learner,
            enrollment=enrollment,
            mentor=mentor,
            start_date=start_date,
            expected_end_date=expected_end_date,
            notes=notes,
            status='PENDING'
        )
        
        messages.success(request, f"Placement for {learner} created at {host_employer.company_name}.")
        return redirect('corporate:host_employer_detail', pk=host_employer_pk)
    
    from learners.models import Learner
    from academics.models import Enrollment
    learners = Learner.objects.all()[:50]  # Limit for performance
    enrollments = Enrollment.objects.filter(status='ACTIVE')[:50]
    mentors = host_employer.mentors.filter(is_active=True)
    
    return render(request, 'corporate/placement_form.html', {
        'host_employer': host_employer,
        'learners': learners,
        'enrollments': enrollments,
        'mentors': mentors,
    })


# =============================================================================
# TRADE TESTS
# =============================================================================

class LegacyTradeTestVenueListView(LoginRequiredMixin, ListView):
    """List all trade test venues (legacy)."""
    model = TradeTestVenue
    template_name = 'corporate/trade_test_venue_list.html'
    context_object_name = 'venues'


class LegacyTradeTestBookingListView(LoginRequiredMixin, ListView):
    """List all trade test bookings."""
    model = LegacyTradeTestBooking
    template_name = 'corporate/trade_test_booking_list.html'
    context_object_name = 'bookings'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = LegacyTradeTestBooking.objects.select_related(
            'learner', 'venue', 'qualification'
        ).order_by('-scheduled_date')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by venue
        venue = self.request.GET.get('venue')
        if venue:
            queryset = queryset.filter(venue_id=venue)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = LegacyTradeTestBooking.STATUS_CHOICES
        context['selected_status'] = self.request.GET.get('status', '')
        context['venues'] = TradeTestVenue.objects.filter(is_active=True)
        context['selected_venue'] = self.request.GET.get('venue', '')
        return context


class LegacyTradeTestBookingDetailView(LoginRequiredMixin, DetailView):
    """View trade test booking details."""
    model = LegacyTradeTestBooking
    template_name = 'corporate/trade_test_booking_detail.html'
    context_object_name = 'booking'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get results if exist
        context['results'] = self.object.results.all()
        return context


class LegacyTradeTestBookingCreateView(LoginRequiredMixin, CreateView):
    """Create a new trade test booking."""
    model = LegacyTradeTestBooking
    template_name = 'corporate/trade_test_booking_form.html'
    fields = ['learner', 'enrollment', 'qualification', 'venue', 'trade_code', 'scheduled_date', 'scheduled_time', 'notes']
    
    def form_valid(self, form):
        form.instance.status = 'PENDING'
        messages.success(self.request, f"Trade test booking created for {form.instance.learner}.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('corporate:trade_test_booking_detail', kwargs={'pk': self.object.pk})


@login_required
def record_legacy_trade_test_result(request, booking_pk):
    """Record result for a legacy trade test."""
    booking = get_object_or_404(LegacyTradeTestBooking, pk=booking_pk)
    
    if request.method == 'POST':
        result_status = request.POST.get('result')
        section = request.POST.get('section', 'FINAL')
        score = request.POST.get('score') or None
        certificate_number = request.POST.get('certificate_number', '')
        assessor_comments = request.POST.get('assessor_comments', '')
        
        result, created = LegacyTradeTestResult.objects.update_or_create(
            booking=booking,
            section=section,
            defaults={
                'result': result_status,
                'score': score,
                'test_date': booking.scheduled_date or timezone.now().date(),
                'result_date': timezone.now().date(),
                'certificate_number': certificate_number,
                'assessor_comments': assessor_comments,
            }
        )
        
        # Update booking status
        booking.status = 'COMPLETED'
        booking.save()
        
        messages.success(request, f"Trade test result recorded for {booking.learner}.")
        return redirect('corporate:trade_test_booking_detail', pk=booking_pk)
    
    return render(request, 'corporate/trade_test_result_form.html', {
        'booking': booking,
        'result_choices': LegacyTradeTestResult.RESULT_CHOICES,
        'section_choices': LegacyTradeTestResult.SECTION_CHOICES,
    })


# =============================================================================
# CRM PIPELINE DASHBOARD
# =============================================================================

@login_required
def crm_dashboard(request):
    """CRM pipeline dashboard with sales overview."""
    from decimal import Decimal
    
    # Pipeline stages overview
    stage_data = []
    for stage_code, stage_name in CorporateOpportunity.STAGE_CHOICES:
        opportunities = CorporateOpportunity.objects.filter(stage=stage_code)
        count = opportunities.count()
        total_value = opportunities.aggregate(total=Sum('estimated_value'))['total'] or Decimal('0.00')
        stage_data.append({
            'code': stage_code,
            'name': stage_name,
            'count': count,
            'total_value': total_value,
        })
    
    # Open opportunities
    open_opportunities = CorporateOpportunity.objects.exclude(
        stage__in=['CLOSED_WON', 'CLOSED_LOST']
    ).select_related('client', 'sales_owner').order_by('-estimated_value')[:10]
    
    # Total pipeline value
    total_pipeline_value = CorporateOpportunity.objects.exclude(
        stage__in=['CLOSED_WON', 'CLOSED_LOST']
    ).aggregate(total=Sum('estimated_value'))['total'] or Decimal('0.00')
    
    # Weighted pipeline value
    open_opps = CorporateOpportunity.objects.exclude(stage__in=['CLOSED_WON', 'CLOSED_LOST'])
    weighted_value = sum(
        (opp.estimated_value or Decimal('0.00')) * Decimal(opp.probability) / 100 
        for opp in open_opps
    )
    
    # Won this month
    from datetime import date
    first_of_month = date.today().replace(day=1)
    won_this_month = CorporateOpportunity.objects.filter(
        stage='CLOSED_WON',
        actual_close_date__gte=first_of_month
    ).aggregate(
        count=Count('id'),
        total=Sum('estimated_value')
    )
    
    # Lost this month
    lost_this_month = CorporateOpportunity.objects.filter(
        stage='CLOSED_LOST',
        actual_close_date__gte=first_of_month
    ).count()
    
    # Activities today
    today_activities = CorporateActivity.objects.filter(
        activity_date__date=timezone.now().date()
    ).count()
    
    # Pending follow-ups
    pending_followups = CorporateActivity.objects.filter(
        next_action_date__lte=timezone.now().date(),
        is_completed=False
    ).select_related('client', 'opportunity')[:10]
    
    # Recent activities
    recent_activities = CorporateActivity.objects.select_related(
        'client', 'opportunity', 'created_by'
    ).order_by('-activity_date')[:15]
    
    # Client health overview
    clients_at_risk = CorporateClient.objects.filter(
        status='ACTIVE',
        health_score__lt=50
    ).count()
    
    # Upsell opportunities (active clients without certain services)
    upsell_candidates = CorporateClient.objects.filter(
        status='ACTIVE'
    ).annotate(
        service_count=Count('service_subscriptions', filter=Q(service_subscriptions__status='ACTIVE'))
    ).filter(service_count__lt=3)[:5]
    
    # Service delivery projects
    active_projects = ServiceDeliveryProject.objects.filter(
        status__in=['SETUP', 'PLANNING', 'IN_PROGRESS']
    ).select_related('client', 'subscription__service').order_by('-created_at')[:10]
    
    projects_at_risk = ServiceDeliveryProject.objects.filter(
        status__in=['SETUP', 'PLANNING', 'IN_PROGRESS'],
        health__in=['AMBER', 'RED']
    ).count()
    
    context = {
        'stage_data': stage_data,
        'open_opportunities': open_opportunities,
        'total_pipeline_value': total_pipeline_value,
        'weighted_value': weighted_value,
        'won_this_month_count': won_this_month['count'] or 0,
        'won_this_month_value': won_this_month['total'] or Decimal('0.00'),
        'lost_this_month': lost_this_month,
        'today_activities': today_activities,
        'pending_followups': pending_followups,
        'recent_activities': recent_activities,
        'clients_at_risk': clients_at_risk,
        'upsell_candidates': upsell_candidates,
        'active_projects': active_projects,
        'projects_at_risk': projects_at_risk,
    }
    
    return render(request, 'corporate/crm_dashboard.html', context)


# =============================================================================
# OPPORTUNITIES
# =============================================================================

class OpportunityListView(LoginRequiredMixin, ListView):
    """List all opportunities with pipeline view."""
    model = CorporateOpportunity
    template_name = 'corporate/opportunity_list.html'
    context_object_name = 'opportunities'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = CorporateOpportunity.objects.select_related(
            'client', 'sales_owner', 'lead_source'
        ).order_by('-created_at')
        
        # Filter by stage
        stage = self.request.GET.get('stage')
        if stage:
            queryset = queryset.filter(stage=stage)
        
        # Filter by owner
        owner = self.request.GET.get('owner')
        if owner:
            queryset = queryset.filter(sales_owner_id=owner)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(reference_number__icontains=search) |
                Q(client__company_name__icontains=search) |
                Q(prospect_company_name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stage_choices'] = CorporateOpportunity.STAGE_CHOICES
        context['selected_stage'] = self.request.GET.get('stage', '')
        context['search'] = self.request.GET.get('search', '')
        
        # Get pipeline summary
        from django.contrib.auth import get_user_model
        User = get_user_model()
        context['sales_users'] = User.objects.filter(
            owned_opportunities__isnull=False
        ).distinct()
        context['selected_owner'] = self.request.GET.get('owner', '')
        return context


class OpportunityDetailView(LoginRequiredMixin, DetailView):
    """View opportunity details with activities and proposals."""
    model = CorporateOpportunity
    template_name = 'corporate/opportunity_detail.html'
    context_object_name = 'opportunity'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        opp = self.object
        
        # Activities
        context['activities'] = opp.activities.order_by('-activity_date')[:20]
        
        # Proposals
        context['proposals'] = opp.proposals.order_by('-proposal_date')
        
        # Proposed services
        context['proposed_services'] = opp.proposed_services.all()
        
        # If linked to client, get client info
        if opp.client:
            context['client_subscriptions'] = opp.client.service_subscriptions.filter(
                status='ACTIVE'
            ).select_related('service')
        
        return context


class OpportunityCreateView(LoginRequiredMixin, CreateView):
    """Create a new opportunity."""
    model = CorporateOpportunity
    template_name = 'corporate/opportunity_form.html'
    fields = [
        'client', 'prospect_company_name', 'prospect_contact_name', 'prospect_email', 'prospect_phone',
        'title', 'description', 'opportunity_type', 'stage', 'priority',
        'estimated_value', 'probability', 'expected_close_date',
        'lead_source', 'referral_source', 'notes'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['services'] = ServiceOffering.objects.filter(is_active=True)
        context['lead_sources'] = LeadSource.objects.filter(is_active=True)
        return context
    
    def form_valid(self, form):
        form.instance.sales_owner = self.request.user
        # Set campus from user or fallback to first campus
        if hasattr(self.request.user, 'campus') and self.request.user.campus:
            form.instance.campus = self.request.user.campus
        else:
            from tenants.models import Campus
            form.instance.campus = Campus.objects.first()
        response = super().form_valid(form)
        
        # Add proposed services
        services = self.request.POST.getlist('proposed_services')
        if services:
            self.object.proposed_services.set(services)
        
        messages.success(self.request, f"Opportunity '{form.instance.title}' created successfully.")
        return response
    
    def get_success_url(self):
        return reverse_lazy('corporate:opportunity_detail', kwargs={'pk': self.object.pk})


class OpportunityUpdateView(LoginRequiredMixin, UpdateView):
    """Update an opportunity."""
    model = CorporateOpportunity
    template_name = 'corporate/opportunity_form.html'
    fields = [
        'client', 'prospect_company_name', 'prospect_contact_name', 'prospect_email', 'prospect_phone',
        'title', 'description', 'opportunity_type', 'stage', 'priority',
        'estimated_value', 'probability', 'expected_close_date',
        'lead_source', 'referral_source', 'loss_reason', 'competitor', 'notes'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['services'] = ServiceOffering.objects.filter(is_active=True)
        context['lead_sources'] = LeadSource.objects.filter(is_active=True)
        context['selected_services'] = list(self.object.proposed_services.values_list('id', flat=True))
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Update proposed services
        services = self.request.POST.getlist('proposed_services')
        self.object.proposed_services.set(services)
        
        # If closing, set actual close date
        if form.instance.stage in ['CLOSED_WON', 'CLOSED_LOST'] and not form.instance.actual_close_date:
            form.instance.actual_close_date = timezone.now().date()
            form.instance.save()
        
        messages.success(self.request, f"Opportunity '{form.instance.title}' updated successfully.")
        return response
    
    def get_success_url(self):
        return reverse_lazy('corporate:opportunity_detail', kwargs={'pk': self.object.pk})


@login_required
def update_opportunity_stage(request, pk):
    """Quick stage update for opportunity."""
    opportunity = get_object_or_404(CorporateOpportunity, pk=pk)
    
    if request.method == 'POST':
        new_stage = request.POST.get('stage')
        valid_stages = [choice[0] for choice in CorporateOpportunity.STAGE_CHOICES]
        if new_stage in valid_stages:
            opportunity.stage = new_stage
            if new_stage in ['CLOSED_WON', 'CLOSED_LOST'] and not opportunity.actual_close_date:
                opportunity.actual_close_date = timezone.now().date()
            opportunity.save()
            messages.success(request, f"Opportunity stage updated to {opportunity.get_stage_display()}.")
    
    return redirect('corporate:opportunity_detail', pk=pk)


@login_required
def convert_opportunity(request, pk):
    """Convert won opportunity to subscription."""
    opportunity = get_object_or_404(CorporateOpportunity, pk=pk)
    
    if opportunity.stage != 'CLOSED_WON':
        messages.error(request, "Only won opportunities can be converted.")
        return redirect('corporate:opportunity_detail', pk=pk)
    
    if request.method == 'POST':
        # Create client if prospect
        if not opportunity.client and opportunity.prospect_company_name:
            client = CorporateClient.objects.create(
                company_name=opportunity.prospect_company_name,
                email=opportunity.prospect_email or '',
                phone=opportunity.prospect_phone or '',
                status='ACTIVE'
            )
            opportunity.client = client
            opportunity.save()
            
            # Create contact if we have info
            if opportunity.prospect_contact_name:
                names = opportunity.prospect_contact_name.split(' ', 1)
                CorporateContact.objects.create(
                    client=client,
                    first_name=names[0],
                    last_name=names[1] if len(names) > 1 else '',
                    email=opportunity.prospect_email or '',
                    phone=opportunity.prospect_phone or '',
                    role='OTHER',
                    is_primary=True
                )
        
        # Create subscriptions for proposed services
        services = opportunity.proposed_services.all()
        for service in services:
            ClientServiceSubscription.objects.create(
                client=opportunity.client,
                service=service,
                start_date=timezone.now().date(),
                status='PENDING',
                opportunity_source=opportunity,
                notes=f"Created from opportunity {opportunity.reference_number}"
            )
        
        messages.success(request, f"Opportunity converted. {services.count()} subscription(s) created.")
        return redirect('corporate:client_detail', pk=opportunity.client.pk)
    
    return render(request, 'corporate/opportunity_convert.html', {
        'opportunity': opportunity,
        'services': opportunity.proposed_services.all(),
    })


# =============================================================================
# ACTIVITIES
# =============================================================================

@login_required
def add_activity(request, opportunity_pk=None, client_pk=None):
    """Add an activity to an opportunity or client."""
    opportunity = None
    client = None
    
    if opportunity_pk:
        opportunity = get_object_or_404(CorporateOpportunity, pk=opportunity_pk)
        client = opportunity.client
    elif client_pk:
        client = get_object_or_404(CorporateClient, pk=client_pk)
    
    if request.method == 'POST':
        activity_type = request.POST.get('activity_type')
        subject = request.POST.get('subject')
        description = request.POST.get('description', '')
        activity_date = request.POST.get('activity_date')
        outcome = request.POST.get('outcome', '')
        outcome_notes = request.POST.get('outcome_notes', '')
        next_action = request.POST.get('next_action', '')
        next_action_date = request.POST.get('next_action_date') or None
        
        activity = CorporateActivity.objects.create(
            client=client,
            opportunity=opportunity,
            activity_type=activity_type,
            subject=subject,
            description=description,
            activity_date=activity_date,
            outcome=outcome,
            outcome_notes=outcome_notes,
            next_action=next_action,
            next_action_date=next_action_date,
        )
        
        messages.success(request, f"Activity '{subject}' logged successfully.")
        
        if opportunity:
            return redirect('corporate:opportunity_detail', pk=opportunity_pk)
        return redirect('corporate:client_detail', pk=client_pk)
    
    contacts = []
    if client:
        contacts = client.contacts.filter(is_active=True)
    
    return render(request, 'corporate/activity_form.html', {
        'opportunity': opportunity,
        'client': client,
        'activity_types': CorporateActivity.ACTIVITY_TYPE_CHOICES,
        'outcome_choices': CorporateActivity.OUTCOME_CHOICES,
        'contacts': contacts,
    })


@login_required
def complete_activity(request, pk):
    """Mark an activity as completed."""
    activity = get_object_or_404(CorporateActivity, pk=pk)
    activity.is_completed = True
    activity.completed_date = timezone.now().date()
    activity.save()
    messages.success(request, "Activity marked as completed.")
    
    if activity.opportunity:
        return redirect('corporate:opportunity_detail', pk=activity.opportunity.pk)
    if activity.client:
        return redirect('corporate:client_detail', pk=activity.client.pk)
    return redirect('corporate:crm_dashboard')


# =============================================================================
# CLIENT 360 VIEW
# =============================================================================

@login_required
def client_360_view(request, pk):
    """Comprehensive 360-degree view of a client."""
    client = get_object_or_404(CorporateClient, pk=pk)
    
    # Contacts
    contacts = client.contacts.all()
    
    # Service subscriptions grouped by category
    subscriptions = client.service_subscriptions.select_related('service__category').all()
    active_subscriptions = subscriptions.filter(status='ACTIVE')
    
    # Opportunities
    opportunities = client.opportunities.order_by('-created_at')
    open_opportunities = opportunities.exclude(stage__in=['CLOSED_WON', 'CLOSED_LOST'])
    
    # Calculate potential upsell services
    current_service_ids = active_subscriptions.values_list('service_id', flat=True)
    available_services = ServiceOffering.objects.filter(
        is_active=True
    ).exclude(id__in=current_service_ids)
    
    # Activities timeline
    activities = client.activities.order_by('-activity_date')[:20]
    
    # Delivery projects
    projects = ServiceDeliveryProject.objects.filter(client=client).select_related('subscription__service')
    active_projects = projects.filter(status__in=['SETUP', 'PLANNING', 'IN_PROGRESS'])
    
    # Financial summary
    from django.db.models import Sum
    total_subscription_value = active_subscriptions.aggregate(
        total=Sum('agreed_price')
    )['total'] or 0
    
    won_opportunity_value = opportunities.filter(stage='CLOSED_WON').aggregate(
        total=Sum('estimated_value')
    )['total'] or 0
    
    # Refresh health score
    client.calculate_health_score()
    
    # WSP/ATR Service Data - Check if client has WSP/ATR subscription
    wspatr_subscription = active_subscriptions.filter(service__service_type='WSP_ATR').first()
    wspatr_data = None
    
    if wspatr_subscription:
        # Get current financial year
        today = timezone.now().date()
        current_fy = today.year if today.month >= 5 else today.year - 1
        
        # Get WSP/ATR service year
        current_service_year = WSPATRServiceYear.objects.filter(
            client=client,
            financial_year=current_fy
        ).first()
        
        # Get Training Committee
        committee = TrainingCommittee.objects.filter(client=client).prefetch_related('members').first()
        
        # Get upcoming meetings
        upcoming_meetings = []
        if committee:
            upcoming_meetings = TrainingCommitteeMeeting.objects.filter(
                committee=committee,
                scheduled_date__gte=today
            ).order_by('scheduled_date')[:3]
        
        wspatr_data = {
            'subscription': wspatr_subscription,
            'service_year': current_service_year,
            'committee': committee,
            'committee_members_count': committee.members.filter(is_active=True).count() if committee else 0,
            'upcoming_meetings': upcoming_meetings,
            'next_meeting': upcoming_meetings[0] if upcoming_meetings else None,
        }
    
    # EE Service Data - Check if client has EE subscription
    ee_subscription = active_subscriptions.filter(service__service_type='EE_CONSULTING').first()
    ee_data = None
    
    if ee_subscription or EEServiceYear.objects.filter(client=client).exists():
        # Get current EE reporting year (Oct-Sep cycle)
        today = timezone.now().date()
        current_ee_year = today.year + 1 if today.month >= 10 else today.year
        
        # Get EE service year
        ee_service_year = EEServiceYear.objects.filter(
            client=client,
            reporting_year=current_ee_year
        ).first()
        
        # Get EE Plan
        active_plan = EEPlan.objects.filter(
            client=client,
            status='ACTIVE'
        ).first()
        
        ee_data = {
            'subscription': ee_subscription,
            'service_year': ee_service_year,
            'active_plan': active_plan,
        }
    
    # B-BBEE Service Data - Check if client has B-BBEE subscription
    bbbee_subscription = active_subscriptions.filter(service__service_type='BEE_CONSULTING').first()
    bbbee_data = None
    
    if bbbee_subscription or BBBEEServiceYear.objects.filter(client=client).exists():
        # Get current B-BBEE financial year
        today = timezone.now().date()
        year_end_month = getattr(client, 'financial_year_end_month', 2)
        current_bbbee_fy = today.year + 1 if today.month > year_end_month else today.year
        
        # Get B-BBEE service year
        bbbee_service_year = BBBEEServiceYear.objects.filter(
            client=client,
            financial_year=current_bbbee_fy
        ).first()
        
        bbbee_data = {
            'subscription': bbbee_subscription,
            'service_year': bbbee_service_year,
        }
    
    context = {
        'client': client,
        'contacts': contacts,
        'subscriptions': subscriptions,
        'active_subscriptions': active_subscriptions,
        'opportunities': opportunities,
        'open_opportunities': open_opportunities,
        'available_services': available_services,
        'activities': activities,
        'projects': projects,
        'active_projects': active_projects,
        'total_subscription_value': total_subscription_value,
        'won_opportunity_value': won_opportunity_value,
        'wspatr_data': wspatr_data,
        'ee_data': ee_data,
        'bbbee_data': bbbee_data,
    }
    
    return render(request, 'corporate/client_360.html', context)


# =============================================================================
# SERVICE DELIVERY PROJECTS
# =============================================================================

class DeliveryProjectListView(LoginRequiredMixin, ListView):
    """List all service delivery projects."""
    model = ServiceDeliveryProject
    template_name = 'corporate/delivery_project_list.html'
    context_object_name = 'projects'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = ServiceDeliveryProject.objects.select_related(
            'client', 'subscription__service', 'project_manager'
        ).order_by('-created_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by health
        health = self.request.GET.get('health')
        if health:
            queryset = queryset.filter(health=health)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = ServiceDeliveryProject.STATUS_CHOICES
        context['health_choices'] = ServiceDeliveryProject.HEALTH_CHOICES
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_health'] = self.request.GET.get('health', '')
        return context


class DeliveryProjectDetailView(LoginRequiredMixin, DetailView):
    """View delivery project details with milestones and tasks."""
    model = ServiceDeliveryProject
    template_name = 'corporate/delivery_project_detail.html'
    context_object_name = 'project'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        
        # Milestones with tasks
        milestones = project.milestones.prefetch_related('tasks').order_by('sequence')
        context['milestones'] = milestones
        
        # Overall progress
        total_milestones = milestones.count()
        completed_milestones = milestones.filter(status='COMPLETED').count()
        if total_milestones > 0:
            context['milestone_progress'] = int((completed_milestones / total_milestones) * 100)
        else:
            context['milestone_progress'] = 0
        
        # Documents
        context['documents'] = project.documents.order_by('-upload_date')
        
        # Team
        context['team_members'] = project.team_members.all()
        
        return context


@login_required
def create_delivery_project(request, subscription_pk):
    """Create a delivery project from a subscription."""
    subscription = get_object_or_404(ClientServiceSubscription, pk=subscription_pk)
    service_type = subscription.service.service_type
    
    # Check if project already exists - redirect to appropriate page
    if hasattr(subscription, 'delivery_project'):
        messages.warning(request, "A delivery project already exists for this subscription.")
        # Redirect based on service type
        if service_type == 'WSP_ATR':
            return redirect('corporate:wspatr_management', client_pk=subscription.client.pk)
        elif service_type == 'EE_CONSULTING':
            return redirect('corporate:ee_service_management', client_pk=subscription.client.pk)
        else:
            return redirect('corporate:delivery_project_detail', pk=subscription.delivery_project.pk)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        implementation_year = request.POST.get('implementation_year')
        planned_start = request.POST.get('planned_start_date')
        planned_end = request.POST.get('planned_end_date') or None
        project_manager_id = request.POST.get('project_manager') or None
        
        # Auto-generate name if not provided
        if not name:
            if implementation_year:
                name = f"{subscription.service.name} - {implementation_year}"
            else:
                name = f"Delivery: {subscription.service.name}"
        
        # Determine implementation year for service year records
        impl_year = int(implementation_year) if implementation_year else timezone.now().year
        
        project = ServiceDeliveryProject.objects.create(
            subscription=subscription,
            client=subscription.client,
            campus=subscription.campus,
            name=name,
            implementation_year=impl_year,
            planned_start_date=planned_start,
            planned_end_date=planned_end,
            project_manager_id=project_manager_id,
            status='SETUP'
        )
        
        # Create milestones from template if available
        from .models import ServiceDeliveryTemplate, WSPATRServiceYear, EEServiceYear
        from tenants.models import Campus
        template = ServiceDeliveryTemplate.objects.filter(
            service_type=service_type,
            is_active=True
        ).first()
        
        if template:
            template.create_project_milestones(project)
        
        # Get campus with fallback
        campus = subscription.campus or subscription.client.campus or Campus.objects.first()
        
        # Auto-create service year records based on service type
        if service_type == 'WSP_ATR':
            # WSP/ATR: Financial year is May-April, deadline is 30 April
            from datetime import date
            wspatr_year, created = WSPATRServiceYear.objects.get_or_create(
                client=subscription.client,
                financial_year=impl_year,
                defaults={
                    'subscription': subscription,
                    'campus': campus,
                    'status': 'NOT_STARTED',
                    'assigned_consultant': request.user if request.user.is_staff else None,
                }
            )
            if created:
                messages.success(request, f"WSP/ATR Service Year {impl_year}/{impl_year+1} created.")
            # Redirect to WSP/ATR Management
            return redirect('corporate:wspatr_management', client_pk=subscription.client.pk)
        
        elif service_type == 'EE_CONSULTING':
            # EE: Reporting year is Oct-Sept, deadline is 15 January
            from datetime import date
            ee_year, created = EEServiceYear.objects.get_or_create(
                client=subscription.client,
                reporting_year=impl_year,
                defaults={
                    'subscription': subscription,
                    'campus': campus,
                    'status': 'NOT_STARTED',
                    'assigned_consultant': request.user if request.user.is_staff else None,
                }
            )
            if created:
                messages.success(request, f"EE Service Year {impl_year} created.")
            # Redirect to EE Service Management
            return redirect('corporate:ee_service_management', client_pk=subscription.client.pk)
        
        else:
            # Generic project - redirect to project detail
            if template:
                messages.success(request, f"Project created with {template.milestones.count()} milestones.")
            else:
                messages.success(request, "Project created. Add milestones to track progress.")
            return redirect('corporate:delivery_project_detail', pk=project.pk)
    
    return render(request, 'corporate/delivery_project_form.html', {
        'subscription': subscription,
    })


@login_required
def update_milestone_status(request, pk):
    """Update milestone status."""
    milestone = get_object_or_404(ProjectMilestone, pk=pk)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [choice[0] for choice in ProjectMilestone.STATUS_CHOICES]
        if new_status in valid_statuses:
            milestone.status = new_status
            if new_status == 'COMPLETED' and not milestone.actual_end_date:
                milestone.actual_end_date = timezone.now().date()
            if new_status == 'IN_PROGRESS' and not milestone.actual_start_date:
                milestone.actual_start_date = timezone.now().date()
            milestone.save()
            
            # Update project progress
            milestone.project.update_progress()
            
            messages.success(request, f"Milestone '{milestone.name}' updated to {milestone.get_status_display()}.")
    
    return redirect('corporate:delivery_project_detail', pk=milestone.project.pk)


@login_required
def add_milestone(request, project_pk):
    """Add a milestone to a delivery project."""
    project = get_object_or_404(ServiceDeliveryProject, pk=project_pk)
    
    if request.method == 'POST':
        name = request.POST.get('milestone_name')
        planned_end = request.POST.get('planned_end_date') or None
        weight = request.POST.get('weight') or 0
        
        # Get next sequence number
        max_sequence = project.milestones.aggregate(max_seq=models.Max('sequence'))['max_seq'] or 0
        
        milestone = ProjectMilestone.objects.create(
            project=project,
            name=name,
            sequence=max_sequence + 1,
            planned_end_date=planned_end,
            weight=weight,
            status='NOT_STARTED'
        )
        
        messages.success(request, f"Milestone '{name}' added successfully.")
    
    return redirect('corporate:delivery_project_detail', pk=project_pk)


# =============================================================================
# PROPOSALS
# =============================================================================

class ProposalListView(LoginRequiredMixin, ListView):
    """List all service proposals."""
    model = ServiceProposal
    template_name = 'corporate/proposal_list.html'
    context_object_name = 'proposals'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = ServiceProposal.objects.select_related(
            'client', 'opportunity', 'created_by'
        ).order_by('-created_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(proposal_number__icontains=search) |
                Q(title__icontains=search) |
                Q(client__company_name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['selected_status'] = self.request.GET.get('status', '')
        context['search'] = self.request.GET.get('search', '')
        
        # Stats
        from decimal import Decimal
        proposals = ServiceProposal.objects.all()
        context['stats'] = {
            'draft_count': proposals.filter(status='DRAFT').count(),
            'draft_value': proposals.filter(status='DRAFT').aggregate(total=Sum('total_value'))['total'] or Decimal('0'),
            'sent_count': proposals.filter(status='SENT').count(),
            'sent_value': proposals.filter(status='SENT').aggregate(total=Sum('total_value'))['total'] or Decimal('0'),
            'accepted_count': proposals.filter(status='ACCEPTED').count(),
            'accepted_value': proposals.filter(status='ACCEPTED').aggregate(total=Sum('total_value'))['total'] or Decimal('0'),
            'rejected_count': proposals.filter(status='REJECTED').count(),
        }
        
        # Win rate
        total_closed = context['stats']['accepted_count'] + context['stats']['rejected_count']
        if total_closed > 0:
            context['stats']['win_rate'] = (context['stats']['accepted_count'] / total_closed) * 100
        else:
            context['stats']['win_rate'] = 0
        
        return context


class ProposalDetailView(LoginRequiredMixin, DetailView):
    """View proposal details with line items."""
    model = ServiceProposal
    template_name = 'corporate/proposal_detail.html'
    context_object_name = 'proposal'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['line_items'] = self.object.line_items.select_related('service').order_by('id')
        return context


class ProposalCreateView(LoginRequiredMixin, CreateView):
    """Create a new proposal."""
    model = ServiceProposal
    template_name = 'corporate/proposal_form.html'
    fields = ['client', 'opportunity', 'title', 'introduction', 'valid_until', 'discount_percentage', 'tax_percentage', 'terms_conditions']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['clients'] = CorporateClient.objects.filter(status='ACTIVE').order_by('company_name')
        context['opportunities'] = CorporateOpportunity.objects.exclude(
            stage__in=['CLOSED_WON', 'CLOSED_LOST']
        ).order_by('-created_at')
        context['services'] = ServiceOffering.objects.filter(is_active=True).order_by('name')
        context['contacts'] = CorporateContact.objects.filter(is_active=True)
        return context
    
    def form_valid(self, form):
        import json
        from decimal import Decimal
        
        form.instance.created_by = self.request.user
        form.instance.status = 'DRAFT'
        
        response = super().form_valid(form)
        
        # Process line items from JSON
        line_items_json = self.request.POST.get('line_items_json', '[]')
        try:
            items = json.loads(line_items_json)
            for item in items:
                service_id = item.get('service_id')
                if service_id and service_id != 'custom':
                    service = ServiceOffering.objects.filter(pk=service_id).first()
                else:
                    service = None
                
                ProposalLineItem.objects.create(
                    proposal=self.object,
                    service=service,
                    custom_service_name=item.get('custom_name', ''),
                    description=item.get('description', ''),
                    quantity=int(item.get('quantity', 1)),
                    unit_price=Decimal(str(item.get('unit_price', 0)))
                )
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Recalculate totals
        self.object.calculate_totals()
        
        messages.success(self.request, f"Proposal '{form.instance.title}' created successfully.")
        return response
    
    def get_success_url(self):
        return reverse_lazy('corporate:proposal_detail', kwargs={'pk': self.object.pk})


class ProposalUpdateView(LoginRequiredMixin, UpdateView):
    """Update a proposal."""
    model = ServiceProposal
    template_name = 'corporate/proposal_form.html'
    fields = ['client', 'opportunity', 'title', 'introduction', 'valid_until', 'discount_percentage', 'tax_percentage', 'terms_conditions']
    
    def get_queryset(self):
        # Only allow editing draft proposals
        return ServiceProposal.objects.filter(status='DRAFT')
    
    def get_context_data(self, **kwargs):
        import json
        context = super().get_context_data(**kwargs)
        context['clients'] = CorporateClient.objects.filter(status='ACTIVE').order_by('company_name')
        context['opportunities'] = CorporateOpportunity.objects.exclude(
            stage__in=['CLOSED_WON', 'CLOSED_LOST']
        ).order_by('-created_at')
        context['services'] = ServiceOffering.objects.filter(is_active=True).order_by('name')
        context['contacts'] = CorporateContact.objects.filter(is_active=True)
        
        # Existing line items as JSON for Alpine.js
        existing_items = []
        for item in self.object.line_items.all():
            existing_items.append({
                'service_id': str(item.service_id) if item.service_id else 'custom',
                'custom_name': item.custom_service_name or '',
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'description': item.description or ''
            })
        context['existing_items'] = json.dumps(existing_items)
        
        return context
    
    def form_valid(self, form):
        import json
        from decimal import Decimal
        
        response = super().form_valid(form)
        
        # Clear existing line items and recreate
        self.object.line_items.all().delete()
        
        # Process line items from JSON
        line_items_json = self.request.POST.get('line_items_json', '[]')
        try:
            items = json.loads(line_items_json)
            for item in items:
                service_id = item.get('service_id')
                if service_id and service_id != 'custom':
                    service = ServiceOffering.objects.filter(pk=service_id).first()
                else:
                    service = None
                
                ProposalLineItem.objects.create(
                    proposal=self.object,
                    service=service,
                    custom_service_name=item.get('custom_name', ''),
                    description=item.get('description', ''),
                    quantity=int(item.get('quantity', 1)),
                    unit_price=Decimal(str(item.get('unit_price', 0)))
                )
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Recalculate totals
        self.object.calculate_totals()
        
        messages.success(self.request, f"Proposal '{form.instance.title}' updated successfully.")
        return response
    
    def get_success_url(self):
        return reverse_lazy('corporate:proposal_detail', kwargs={'pk': self.object.pk})


@login_required
def update_proposal_status(request, pk):
    """Update proposal status."""
    proposal = get_object_or_404(ServiceProposal, pk=pk)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [choice[0] for choice in ServiceProposal.STATUS_CHOICES]
        if new_status in valid_statuses:
            proposal.status = new_status
            
            if new_status == 'SENT' and not proposal.sent_date:
                proposal.sent_date = timezone.now().date()
            
            if new_status in ['ACCEPTED', 'REJECTED']:
                proposal.response_date = timezone.now().date()
                
                # If accepted and linked to opportunity, update opportunity
                if new_status == 'ACCEPTED' and proposal.opportunity:
                    proposal.opportunity.stage = 'CLOSED_WON'
                    proposal.opportunity.actual_close_date = timezone.now().date()
                    proposal.opportunity.save()
            
            proposal.save()
            messages.success(request, f"Proposal status updated to {proposal.get_status_display()}.")
    
    return redirect('corporate:proposal_detail', pk=pk)


# =============================================================================
# WSP/ATR PROJECT MANAGEMENT
# =============================================================================

from .models import (
    WSPYear, WSPSubmission, WSPPlannedTraining, ATRSubmission, ATRCompletedTraining,
    WSPATREvidenceCategory, WSPATRChecklist, WSPATREvidence,
    EmployeeQualification, MeetingAgendaItem, MeetingActionItem,
    AnnualServiceDelivery, ServiceDeliveryActivity, ServiceDeliveryEvidence,
    EmployeeDatabaseUpload, Committee, CommitteeMeeting, CommitteeMember,
    CorporateEmployee
)


@login_required
def wsp_atr_dashboard(request):
    """WSP/ATR Project Management Dashboard with submission tracking and progress."""
    
    # Get current WSP year
    current_year = WSPYear.objects.filter(is_current=True).first()
    
    # Get all WSP years for filtering
    wsp_years = WSPYear.objects.all()
    
    # Selected year from query param or current
    selected_year_id = request.GET.get('year')
    if selected_year_id:
        selected_year = WSPYear.objects.filter(id=selected_year_id).first() or current_year
    else:
        selected_year = current_year
    
    # Get client filter
    client_id = request.GET.get('client')
    
    # Base queryset for WSP submissions
    wsp_submissions = WSPSubmission.objects.select_related('client', 'wsp_year')
    atr_submissions = ATRSubmission.objects.select_related('client', 'reporting_year')
    
    if selected_year:
        wsp_submissions = wsp_submissions.filter(wsp_year=selected_year)
        atr_submissions = atr_submissions.filter(reporting_year=selected_year)
    
    if client_id:
        wsp_submissions = wsp_submissions.filter(client_id=client_id)
        atr_submissions = atr_submissions.filter(client_id=client_id)
    
    # Statistics
    wsp_stats = {
        'total': wsp_submissions.count(),
        'draft': wsp_submissions.filter(status='DRAFT').count(),
        'in_progress': wsp_submissions.filter(status='IN_PROGRESS').count(),
        'submitted': wsp_submissions.filter(status='SUBMITTED').count(),
        'accepted': wsp_submissions.filter(status='ACCEPTED').count(),
        'rejected': wsp_submissions.filter(status='REJECTED').count(),
    }
    
    atr_stats = {
        'total': atr_submissions.count(),
        'draft': atr_submissions.filter(status='DRAFT').count(),
        'in_progress': atr_submissions.filter(status='IN_PROGRESS').count(),
        'submitted': atr_submissions.filter(status='SUBMITTED').count(),
        'accepted': atr_submissions.filter(status='ACCEPTED').count(),
        'rejected': atr_submissions.filter(status='REJECTED').count(),
    }
    
    # Service delivery progress
    service_deliveries = AnnualServiceDelivery.objects.select_related(
        'client', 'wsp_year', 'wsp', 'atr'
    )
    if selected_year:
        service_deliveries = service_deliveries.filter(wsp_year=selected_year)
    if client_id:
        service_deliveries = service_deliveries.filter(client_id=client_id)
    
    # Upcoming deadlines
    today = timezone.now().date()
    upcoming_activities = ServiceDeliveryActivity.objects.filter(
        status__in=['PLANNED', 'IN_PROGRESS'],
        planned_end__gte=today,
        planned_end__lte=today + timezone.timedelta(days=30)
    ).select_related('service_delivery__client').order_by('planned_end')[:10]
    
    # Overdue activities
    overdue_activities = ServiceDeliveryActivity.objects.filter(
        status__in=['PLANNED', 'IN_PROGRESS'],
        planned_end__lt=today
    ).select_related('service_delivery__client').order_by('planned_end')[:10]
    
    # Checklist progress by client
    checklist_progress = []
    for delivery in service_deliveries[:10]:
        wsp_items = WSPATRChecklist.objects.filter(wsp=delivery.wsp) if delivery.wsp else WSPATRChecklist.objects.none()
        atr_items = WSPATRChecklist.objects.filter(atr=delivery.atr) if delivery.atr else WSPATRChecklist.objects.none()
        
        total_items = wsp_items.count() + atr_items.count()
        completed_items = wsp_items.filter(status='APPROVED').count() + atr_items.filter(status='APPROVED').count()
        
        checklist_progress.append({
            'client': delivery.client,
            'wsp_year': delivery.wsp_year,
            'total': total_items,
            'completed': completed_items,
            'progress': (completed_items / total_items * 100) if total_items > 0 else 0
        })
    
    # Clients for filter
    clients = CorporateClient.objects.filter(status='ACTIVE').order_by('company_name')
    
    context = {
        'current_year': current_year,
        'selected_year': selected_year,
        'wsp_years': wsp_years,
        'wsp_submissions': wsp_submissions[:20],
        'atr_submissions': atr_submissions[:20],
        'wsp_stats': wsp_stats,
        'atr_stats': atr_stats,
        'service_deliveries': service_deliveries[:20],
        'upcoming_activities': upcoming_activities,
        'overdue_activities': overdue_activities,
        'checklist_progress': checklist_progress,
        'clients': clients,
        'selected_client_id': client_id,
    }
    
    return render(request, 'corporate/wsp_atr/dashboard.html', context)


@login_required
def wsp_detail(request, pk):
    """WSP Submission detail view with checklist and evidence."""
    wsp = get_object_or_404(
        WSPSubmission.objects.select_related('client', 'wsp_year'),
        pk=pk
    )
    
    # Get planned training
    planned_training = wsp.planned_training.all()
    
    # Get checklist items grouped by category
    checklist_items = WSPATRChecklist.objects.filter(wsp=wsp).select_related('category', 'assigned_to')
    categories = WSPATREvidenceCategory.objects.filter(
        applies_to__in=['WSP', 'BOTH'],
        is_active=True
    )
    
    checklist_by_category = {}
    for category in categories:
        items = checklist_items.filter(category=category)
        checklist_by_category[category] = {
            'items': items,
            'total': items.count(),
            'completed': items.filter(status='APPROVED').count()
        }
    
    # Get evidence files
    evidence_files = WSPATREvidence.objects.filter(wsp=wsp)
    
    # Get service delivery
    service_delivery = AnnualServiceDelivery.objects.filter(wsp=wsp).first()
    
    context = {
        'wsp': wsp,
        'planned_training': planned_training,
        'checklist_by_category': checklist_by_category,
        'evidence_files': evidence_files,
        'service_delivery': service_delivery,
    }
    
    return render(request, 'corporate/wsp_atr/wsp_detail.html', context)


@login_required
def atr_detail(request, pk):
    """ATR Submission detail view with checklist and evidence."""
    atr = get_object_or_404(
        ATRSubmission.objects.select_related('client', 'reporting_year', 'wsp'),
        pk=pk
    )
    
    # Get completed training
    completed_training = atr.completed_training.all()
    
    # Get checklist items grouped by category
    checklist_items = WSPATRChecklist.objects.filter(atr=atr).select_related('category', 'assigned_to')
    categories = WSPATREvidenceCategory.objects.filter(
        applies_to__in=['ATR', 'BOTH'],
        is_active=True
    )
    
    checklist_by_category = {}
    for category in categories:
        items = checklist_items.filter(category=category)
        checklist_by_category[category] = {
            'items': items,
            'total': items.count(),
            'completed': items.filter(status='APPROVED').count()
        }
    
    # Get evidence files
    evidence_files = WSPATREvidence.objects.filter(atr=atr)
    
    # Variance analysis (planned vs actual) if WSP linked
    variance_data = []
    if atr.wsp:
        for planned in atr.wsp.planned_training.all():
            actual = completed_training.filter(
                intervention_type=planned.intervention_type,
                training_description=planned.training_description
            ).first()
            
            variance_data.append({
                'intervention': planned.training_description,
                'type': planned.get_intervention_type_display(),
                'planned_learners': planned.total_learners,
                'actual_learners': actual.total_learners if actual else 0,
                'planned_cost': planned.estimated_cost,
                'actual_cost': actual.actual_cost if actual else 0,
            })
    
    # Get service delivery
    service_delivery = AnnualServiceDelivery.objects.filter(atr=atr).first()
    
    context = {
        'atr': atr,
        'completed_training': completed_training,
        'checklist_by_category': checklist_by_category,
        'evidence_files': evidence_files,
        'variance_data': variance_data,
        'service_delivery': service_delivery,
    }
    
    return render(request, 'corporate/wsp_atr/atr_detail.html', context)


@login_required
def service_delivery_detail(request, pk):
    """Annual Service Delivery detail with activities and evidence."""
    delivery = get_object_or_404(
        AnnualServiceDelivery.objects.select_related('client', 'wsp_year', 'wsp', 'atr'),
        pk=pk
    )
    
    # Get activities grouped by status
    activities = delivery.activities.all().order_by('planned_start')
    
    activities_by_status = {
        'planned': activities.filter(status='PLANNED'),
        'in_progress': activities.filter(status='IN_PROGRESS'),
        'completed': activities.filter(status='COMPLETED'),
        'delayed': activities.filter(status='DELAYED'),
    }
    
    # Calculate overall progress
    total_weight = activities.count()
    if total_weight > 0:
        completed_weight = activities.filter(status='COMPLETED').count()
        overall_progress = (completed_weight / total_weight) * 100
    else:
        overall_progress = 0
    
    # Activity types breakdown
    activity_types = ServiceDeliveryActivity.ACTIVITY_TYPE_CHOICES
    type_breakdown = []
    for type_code, type_name in activity_types:
        type_activities = activities.filter(activity_type=type_code)
        if type_activities.exists():
            type_breakdown.append({
                'type': type_name,
                'total': type_activities.count(),
                'completed': type_activities.filter(status='COMPLETED').count(),
            })
    
    # Upcoming deadlines
    today = timezone.now().date()
    upcoming = activities.filter(
        status__in=['PLANNED', 'IN_PROGRESS'],
        planned_end__gte=today
    ).order_by('planned_end')[:5]
    
    # Overdue
    overdue = activities.filter(
        status__in=['PLANNED', 'IN_PROGRESS'],
        planned_end__lt=today
    ).order_by('planned_end')
    
    context = {
        'delivery': delivery,
        'activities': activities,
        'activities_by_status': activities_by_status,
        'overall_progress': overall_progress,
        'type_breakdown': type_breakdown,
        'upcoming': upcoming,
        'overdue': overdue,
    }
    
    return render(request, 'corporate/wsp_atr/service_delivery_detail.html', context)


@login_required
def committee_meetings(request, client_pk):
    """Committee meetings list for a client."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    # Get committees for this client
    committees = Committee.objects.filter(client=client)
    
    # Get selected committee
    committee_id = request.GET.get('committee')
    selected_committee = None
    if committee_id:
        selected_committee = committees.filter(id=committee_id).first()
    
    # Get meetings
    meetings = CommitteeMeeting.objects.select_related('committee').prefetch_related(
        'attendees', 'agenda_items', 'action_items'
    )
    
    if selected_committee:
        meetings = meetings.filter(committee=selected_committee)
    else:
        meetings = meetings.filter(committee__in=committees)
    
    meetings = meetings.order_by('-meeting_date')
    
    # Upcoming meetings
    today = timezone.now().date()
    upcoming = meetings.filter(meeting_date__gte=today)
    past = meetings.filter(meeting_date__lt=today)
    
    # Action items summary
    action_items = MeetingActionItem.objects.filter(
        meeting__committee__in=committees
    )
    open_actions = action_items.filter(status__in=['OPEN', 'IN_PROGRESS']).count()
    overdue_actions = action_items.filter(
        status__in=['OPEN', 'IN_PROGRESS'],
        due_date__lt=today
    ).count()
    
    context = {
        'client': client,
        'committees': committees,
        'selected_committee': selected_committee,
        'upcoming_meetings': upcoming[:10],
        'past_meetings': past[:20],
        'open_actions': open_actions,
        'overdue_actions': overdue_actions,
    }
    
    return render(request, 'corporate/wsp_atr/committee_meetings.html', context)


@login_required
def meeting_detail(request, pk):
    """Committee meeting detail with agenda, minutes, and action items."""
    meeting = get_object_or_404(
        CommitteeMeeting.objects.select_related('committee', 'committee__client').prefetch_related(
            'attendees', 'agenda_items', 'action_items'
        ),
        pk=pk
    )
    
    # Get agenda items
    agenda_items = meeting.agenda_items.all().order_by('sequence')
    
    # Get action items
    action_items = meeting.action_items.all().order_by('due_date')
    
    # Get committee members for attendance
    committee_members = meeting.committee.members.filter(is_active=True)
    
    context = {
        'meeting': meeting,
        'agenda_items': agenda_items,
        'action_items': action_items,
        'committee_members': committee_members,
    }
    
    return render(request, 'corporate/wsp_atr/meeting_detail.html', context)


@login_required
def employee_database(request, client_pk):
    """Employee database with qualifications for WSP/ATR."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    # Get employees
    employees = CorporateEmployee.objects.filter(
        client=client,
        is_current=True
    ).select_related('learner').prefetch_related('qualifications')
    
    # Search
    search = request.GET.get('search', '')
    if search:
        employees = employees.filter(
            Q(learner__first_name__icontains=search) |
            Q(learner__last_name__icontains=search) |
            Q(learner__sa_id_number__icontains=search) |
            Q(job_title__icontains=search)
        )
    
    # Filter by qualification type
    qual_type = request.GET.get('qual_type')
    if qual_type:
        employees = employees.filter(qualifications__qualification_type=qual_type).distinct()
    
    # Statistics
    total_employees = employees.count()
    with_qualifications_count = employees.filter(qualifications__isnull=False).distinct().count()
    total_qualifications = EmployeeQualification.objects.filter(employee__client=client).count()
    
    # Qualification types breakdown
    qual_breakdown = EmployeeQualification.objects.filter(
        employee__client=client,
        employee__is_current=True
    ).values('qualification_type').annotate(count=Count('id'))
    
    # Recent uploads
    recent_uploads = EmployeeDatabaseUpload.objects.filter(client=client).order_by('-created_at')[:5]
    
    context = {
        'client': client,
        'employees': employees,
        'total_employees': total_employees,
        'with_qualifications_count': with_qualifications_count,
        'total_qualifications': total_qualifications,
        'expiring_count': 0,
        'expired_count': 0,
        'qual_breakdown': qual_breakdown,
        'recent_uploads': recent_uploads,
        'search': search,
        'qual_type': qual_type,
        'qual_type_choices': EmployeeQualification.QUALIFICATION_TYPE_CHOICES,
    }
    
    return render(request, 'corporate/wsp_atr/employee_database.html', context)


@login_required
def evidence_upload(request, submission_type, pk):
    """Evidence upload page for WSP or ATR."""
    if submission_type == 'wsp':
        submission = get_object_or_404(WSPSubmission.objects.select_related('client'), pk=pk)
    else:
        submission = get_object_or_404(ATRSubmission.objects.select_related('client'), pk=pk)
    
    # Get evidence categories
    categories = WSPATREvidenceCategory.objects.filter(
        is_active=True
    )
    if submission_type == 'wsp':
        categories = categories.filter(applies_to__in=['WSP', 'BOTH'])
        evidence_files = WSPATREvidence.objects.filter(wsp=submission)
    else:
        categories = categories.filter(applies_to__in=['ATR', 'BOTH'])
        evidence_files = WSPATREvidence.objects.filter(atr=submission)
    
    # Group evidence by type
    evidence_by_type = {}
    for evidence_type, type_name in WSPATREvidence.EVIDENCE_TYPE_CHOICES:
        files = evidence_files.filter(evidence_type=evidence_type)
        if files.exists():
            evidence_by_type[type_name] = files
    
    if request.method == 'POST':
        # Handle file upload
        evidence_type = request.POST.get('evidence_type')
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        reference_number = request.POST.get('reference_number', '')
        evidence_date = request.POST.get('evidence_date')
        file = request.FILES.get('file')
        
        if file and evidence_type and name:
            evidence = WSPATREvidence(
                evidence_type=evidence_type,
                name=name,
                description=description,
                reference_number=reference_number,
                file=file,
                created_by=request.user
            )
            
            if evidence_date:
                evidence.evidence_date = evidence_date
            
            if submission_type == 'wsp':
                evidence.wsp = submission
            else:
                evidence.atr = submission
            
            evidence.save()
            messages.success(request, f"Evidence '{name}' uploaded successfully.")
            return redirect('corporate:evidence_upload', submission_type=submission_type, pk=pk)
    
    context = {
        'submission_type': submission_type,
        'submission': submission,
        'categories': categories,
        'evidence_files': evidence_files,
        'evidence_by_type': evidence_by_type,
        'evidence_type_choices': WSPATREvidence.EVIDENCE_TYPE_CHOICES,
    }
    
    return render(request, 'corporate/wsp_atr/evidence_upload.html', context)


@login_required
def activity_update(request, pk):
    """Update a service delivery activity status/progress."""
    activity = get_object_or_404(
        ServiceDeliveryActivity.objects.select_related('service_delivery'),
        pk=pk
    )
    
    if request.method == 'POST':
        status = request.POST.get('status')
        progress = request.POST.get('progress')
        notes = request.POST.get('notes', '')
        
        if status:
            activity.status = status
            if status == 'COMPLETED' and not activity.actual_end:
                activity.actual_end = timezone.now().date()
            if status == 'IN_PROGRESS' and not activity.actual_start:
                activity.actual_start = timezone.now().date()
        
        if progress:
            activity.progress = int(progress)
        
        if notes:
            activity.notes = notes
        
        activity.save()
        
        # Update service delivery overall progress
        delivery = activity.service_delivery
        total = delivery.activities.count()
        if total > 0:
            completed = delivery.activities.filter(status='COMPLETED').count()
            delivery.overall_progress = int((completed / total) * 100)
            delivery.save()
        
        messages.success(request, f"Activity '{activity.name}' updated.")
    
    return redirect('corporate:service_delivery_detail', pk=activity.service_delivery.pk)


# =============================================================================
# ADDITIONAL WSP/ATR VIEWS
# =============================================================================

@login_required
def meeting_create(request, client_pk):
    """Create a new committee meeting."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    # Get committees for this client
    committees = Committee.objects.filter(client=client)
    
    if request.method == 'POST':
        committee_id = request.POST.get('committee')
        committee = get_object_or_404(Committee, pk=committee_id, client=client)
        
        meeting = CommitteeMeeting.objects.create(
            committee=committee,
            title=request.POST.get('title'),
            meeting_date=request.POST.get('meeting_date'),
            location=request.POST.get('location', ''),
            meeting_type=request.POST.get('meeting_type', 'REGULAR'),
            created_by=request.user
        )
        
        # Add agenda items if provided
        agenda_items = request.POST.getlist('agenda_item')
        for i, item in enumerate(agenda_items):
            if item.strip():
                MeetingAgendaItem.objects.create(
                    meeting=meeting,
                    title=item,
                    sequence=i + 1
                )
        
        messages.success(request, f"Meeting '{meeting.title}' scheduled successfully.")
        return redirect('corporate:meeting_detail', pk=meeting.pk)
    
    context = {
        'client': client,
        'committees': committees,
    }
    return render(request, 'corporate/wsp_atr/meeting_create.html', context)


@login_required
def meeting_add_action_item(request, pk):
    """Add an action item to a meeting."""
    meeting = get_object_or_404(CommitteeMeeting, pk=pk)
    
    if request.method == 'POST':
        action = MeetingActionItem.objects.create(
            meeting=meeting,
            description=request.POST.get('description'),
            assigned_to_id=request.POST.get('assigned_to') or None,
            due_date=request.POST.get('due_date'),
            priority=request.POST.get('priority', 'MEDIUM')
        )
        messages.success(request, "Action item added.")
    
    return redirect('corporate:meeting_detail', pk=pk)


@login_required
def update_action_item_status(request, pk):
    """Update the status of an action item."""
    action = get_object_or_404(MeetingActionItem, pk=pk)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        if status:
            action.status = status
            if status == 'COMPLETED':
                action.completed_date = timezone.now().date()
        
        if notes:
            action.completion_notes = notes
        
        action.save()
        messages.success(request, "Action item updated.")
    
    return redirect('corporate:meeting_detail', pk=action.meeting.pk)


@login_required
def employee_add(request, client_pk):
    """Add a new employee to the database."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    if request.method == 'POST':
        id_number = request.POST.get('id_number', '')
        first_name = request.POST.get('first_name', '')
        surname = request.POST.get('surname', '')
        email = request.POST.get('email', '')
        phone = request.POST.get('phone', '')
        gender = request.POST.get('gender')
        population_group = request.POST.get('race')
        has_disability = request.POST.get('has_disability') == 'on'
        
        # Employment fields
        ofo_code = request.POST.get('ofo_code')
        occupational_level = request.POST.get('occupational_level')
        employment_type = request.POST.get('employment_type')
        job_title = request.POST.get('job_title')
        department = request.POST.get('department')
        employee_number = request.POST.get('employee_number', '')
        start_date_str = request.POST.get('start_date')
        
        # Parse start date
        start_date = timezone.now().date()
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except:
                pass
        
        # 1. Find or create Learner
        learner = Learner.objects.filter(sa_id_number=id_number).first()
        if not learner:
            # Basic learner creation
            # Try to derive DOB from SA ID
            dob = date(2000, 1, 1)
            
            if id_number and len(id_number) == 13:
                try:
                    year = int(id_number[0:2])
                    month = int(id_number[2:4])
                    day = int(id_number[4:6])
                    
                    # Determine century
                    current_year = timezone.now().year % 100
                    if year > current_year:
                        year += 1900
                    else:
                        year += 2000
                    
                    dob = date(year, month, day)
                except:
                    pass

            learner = Learner.objects.create(
                campus=client.campus,
                sa_id_number=id_number,
                first_name=first_name,
                last_name=surname,
                email=email,
                phone_mobile=phone,
                learner_number=f"EMP{timezone.now().strftime('%y%m%d%H%M%S')}",
                date_of_birth=dob,
                gender=gender or 'O',
                population_group=population_group or 'A',
                disability_status='9' if has_disability else 'N',
                citizenship='SA'
            )
        
        # 2. Check if already an employee of this client
        employee = CorporateEmployee.objects.filter(client=client, learner=learner).first()
        if employee:
            messages.warning(request, f"{first_name} {surname} is already an employee of this client.")
        else:
            # 3. Create CorporateEmployee
            CorporateEmployee.objects.create(
                client=client,
                learner=learner,
                employee_number=employee_number,
                job_title=job_title,
                department=department,
                ofo_code=ofo_code,
                occupational_level=occupational_level,
                employment_type=employment_type,
                start_date=start_date,
                is_current=True
            )
            messages.success(request, f"Employee {first_name} {surname} added successfully.")
            
        return redirect('corporate:employee_database', client_pk=client.pk)
    
    context = {
        'client': client,
    }
    return render(request, 'corporate/wsp_atr/employee_add.html', context)


@login_required
def employee_detail(request, pk):
    """Employee detail with qualifications."""
    employee = get_object_or_404(
        CorporateEmployee.objects.select_related('client', 'learner').prefetch_related('qualifications'),
        pk=pk
    )
    
    qualifications = employee.qualifications.all().order_by('-date_obtained')
    
    context = {
        'employee': employee,
        'qualifications': qualifications,
    }
    return render(request, 'corporate/wsp_atr/employee_detail.html', context)


@login_required
def add_employee_qualification(request, pk):
    """Add a qualification to an employee."""
    employee = get_object_or_404(CorporateEmployee, pk=pk)
    
    if request.method == 'POST':
        qualification = EmployeeQualification.objects.create(
            employee=employee,
            qualification_type=request.POST.get('qualification_type'),
            qualification_name=request.POST.get('qualification_name'),
            institution=request.POST.get('institution', ''),
            date_obtained=request.POST.get('date_obtained') or None,
            expiry_date=request.POST.get('expiry_date') or None,
            nqf_level=request.POST.get('nqf_level') or None,
            verification_status=request.POST.get('verification_status', 'PENDING')
        )
        
        # Handle file upload
        if 'certificate' in request.FILES:
            qualification.certificate_file = request.FILES['certificate']
            qualification.save()
        
        messages.success(request, f"Qualification '{qualification.qualification_name}' added.")
        return redirect('corporate:employee_detail', pk=employee.pk)
    
    return redirect('corporate:employee_detail', pk=employee.pk)


@login_required
def service_delivery_dashboard(request):
    """Service delivery overview across all clients."""
    # Get year filter
    year_id = request.GET.get('year')
    client_id = request.GET.get('client')
    
    deliveries = AnnualServiceDelivery.objects.select_related(
        'client', 'wsp_year', 'wsp', 'atr'
    ).prefetch_related('activities')
    
    if year_id:
        deliveries = deliveries.filter(wsp_year_id=year_id)
    
    if client_id:
        deliveries = deliveries.filter(client_id=client_id)
    
    # Statistics
    total_deliveries = deliveries.count()
    on_track = deliveries.filter(status='ON_TRACK').count()
    at_risk = deliveries.filter(status='AT_RISK').count()
    delayed = deliveries.filter(status='DELAYED').count()
    completed = deliveries.filter(status='COMPLETED').count()
    
    # Overall progress calculation
    if total_deliveries > 0:
        avg_progress = sum([d.overall_progress for d in deliveries]) / total_deliveries
    else:
        avg_progress = 0
    
    # Upcoming deadlines
    today = timezone.now().date()
    upcoming_activities = ServiceDeliveryActivity.objects.filter(
        status__in=['PLANNED', 'IN_PROGRESS'],
        planned_end__gte=today,
        planned_end__lte=today + timezone.timedelta(days=14)
    ).select_related('service_delivery__client').order_by('planned_end')[:10]
    
    # WSP Years for filter
    wsp_years = WSPYear.objects.all().order_by('-year')
    clients = CorporateClient.objects.filter(status='ACTIVE').order_by('company_name')
    
    context = {
        'deliveries': deliveries[:20],
        'total_deliveries': total_deliveries,
        'on_track': on_track,
        'at_risk': at_risk,
        'delayed': delayed,
        'completed': completed,
        'avg_progress': avg_progress,
        'upcoming_activities': upcoming_activities,
        'wsp_years': wsp_years,
        'clients': clients,
        'selected_year_id': year_id,
        'selected_client_id': client_id,
    }
    return render(request, 'corporate/wsp_atr/service_delivery_dashboard.html', context)


@login_required
def evidence_review(request, pk):
    """Review an evidence submission."""
    evidence = get_object_or_404(WSPATREvidence, pk=pk)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        notes = request.POST.get('review_notes', '')
        
        if status in ['APPROVED', 'REJECTED']:
            evidence.status = status
            evidence.review_notes = notes
            evidence.reviewed_by = request.user
            evidence.reviewed_at = timezone.now()
            evidence.save()
            
            messages.success(request, f"Evidence {status.lower()}.")
    
    # Redirect back to the appropriate page
    if evidence.wsp:
        return redirect('corporate:wsp_detail', pk=evidence.wsp.pk)
    elif evidence.atr:
        return redirect('corporate:atr_detail', pk=evidence.atr.pk)
    else:
        return redirect('corporate:wsp_atr_dashboard')


@login_required
def evidence_delete(request, pk):
    """Delete an evidence submission."""
    evidence = get_object_or_404(WSPATREvidence, pk=pk)
    
    # Only allow deletion of pending evidence
    if evidence.status == 'PENDING':
        wsp_pk = evidence.wsp.pk if evidence.wsp else None
        atr_pk = evidence.atr.pk if evidence.atr else None
        
        evidence.delete()
        messages.success(request, "Evidence deleted.")
        
        if wsp_pk:
            return redirect('corporate:wsp_detail', pk=wsp_pk)
        elif atr_pk:
            return redirect('corporate:atr_detail', pk=atr_pk)
    else:
        messages.error(request, "Only pending evidence can be deleted.")
    
    return redirect('corporate:wsp_atr_dashboard')


# =============================================================================
# WSP/ATR SERVICE MANAGEMENT (Simplified Flow)
# =============================================================================

@login_required
def wspatr_service_management(request, client_pk):
    """
    Unified WSP/ATR service management view.
    Handles all WSP/ATR service delivery from one place.
    Auto-creates current financial year's service record if none exists.
    """
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    # Determine current financial year (May-Apr for WSP/ATR cycle)
    today = timezone.now().date()
    if today.month >= 5:
        current_fy = today.year
    else:
        current_fy = today.year - 1
    
    # Get campus with fallback
    from tenants.models import Campus
    campus = client.campus or Campus.objects.first()
    
    # Get the WSP/ATR subscription (optional - for billing tracking)
    subscription = ClientServiceSubscription.objects.filter(
        client=client,
        service__service_type='WSP_ATR',
        status='ACTIVE'
    ).select_related('service').first()
    
    # Auto-create current year's service record if it doesn't exist
    current_year_record, created = WSPATRServiceYear.objects.get_or_create(
        client=client,
        financial_year=current_fy,
        defaults={
            'subscription': subscription,
            'campus': campus,
            'status': 'NOT_STARTED',
            'assigned_consultant': request.user if request.user.is_staff else None,
        }
    )
    if created:
        messages.success(request, f"Service year FY{current_fy}/{current_fy + 1} automatically created.")
    
    # Get Training Committee (if exists)
    committee = TrainingCommittee.objects.filter(client=client).prefetch_related(
        Prefetch('members', queryset=TrainingCommitteeMember.objects.select_related('contact'))
    ).first()
    
    # Get Service Years (using financial_year integer field)
    service_years = WSPATRServiceYear.objects.filter(client=client).order_by('-financial_year')
    
    # Determine which year to display
    selected_year = request.GET.get('year')
    if selected_year and selected_year.isdigit():
        current_year = service_years.filter(financial_year=int(selected_year)).first()
    else:
        # Use the auto-created/fetched current year
        current_year = current_year_record
    
    # Get all meetings for this client
    meetings = TrainingCommitteeMeeting.objects.filter(
        committee=committee,
        service_year=current_year
    ).order_by('scheduled_date') if committee and current_year else []
    
    # Separate upcoming and past meetings
    today = timezone.now().date()
    upcoming_meetings = [m for m in meetings if m.scheduled_date >= today] if meetings else []
    past_meetings = [m for m in meetings if m.scheduled_date < today] if meetings else []
    
    # Get employee data for current year
    employee_data = WSPATREmployeeData.objects.filter(
        service_year=current_year
    ).order_by('occupational_level') if current_year else []
    
    # Get training data for current year
    training_data = WSPATRTrainingData.objects.filter(
        service_year=current_year
    ).select_related('service_year', 'qualification') if current_year else []
    
    # Get pivotal data for current year
    pivotal_data = WSPATRPivotalData.objects.filter(
        service_year=current_year
    ) if current_year else []
    
    # Get documents for current year
    documents = WSPATRDocument.objects.filter(
        service_year=current_year
    ) if current_year else []

    # Categorize documents
    atr_docs = [d for d in documents if d.document_type in ['ATR_EVIDENCE', 'PIVOTAL_EVIDENCE', 'SIGNED_ATR']]
    hr_docs = [d for d in documents if d.document_type in ['EMPLOYEE_LIST', 'ORGANOGRAM', 'SKILLS_AUDIT']]
    committee_docs = [d for d in documents if d.document_type in ['COMMITTEE_MINUTES', 'COMMITTEE_ATTENDANCE']]
    compliance_docs = [d for d in documents if d.document_type not in [
        'ATR_EVIDENCE', 'PIVOTAL_EVIDENCE', 'SIGNED_ATR',
        'EMPLOYEE_LIST', 'ORGANOGRAM', 'SKILLS_AUDIT',
        'COMMITTEE_MINUTES', 'COMMITTEE_ATTENDANCE'
    ]]
    
    # Calculate section progress
    def calc_section_progress(docs):
        if not docs: return 0
        required = [d for d in docs if d.is_required]
        if not required: return 100 # If none required, it's "complete" in a sense, or just return 0
        uploaded = [d for d in required if d.file]
        return int((len(uploaded) / len(required)) * 100)

    section_progress = {
        'wsp': current_year.progress_percentage if current_year else 0,
        'atr': calc_section_progress(atr_docs),
        'hr': calc_section_progress(hr_docs),
        'compliance': calc_section_progress(compliance_docs),
    }

    # Enhance meetings with document status
    for meeting in past_meetings:
        meeting.has_minutes = any(d.document_type == 'COMMITTEE_MINUTES' and d.meeting_id == meeting.id and d.file for d in documents)
        meeting.has_attendance = any(d.document_type == 'COMMITTEE_ATTENDANCE' and d.meeting_id == meeting.id and d.file for d in documents)
    
    # Calculate statistics
    stats = {
        'total_employees': sum(ed.total_employees for ed in employee_data) if employee_data else 0,
        'total_training_interventions': len(training_data) if training_data else 0,
        'upcoming_meetings_count': len(upcoming_meetings),
        'committee_members': committee.members.count() if committee else 0,
    }
    
    # Get available SDFs (staff users who can be assigned)
    available_sdfs = User.objects.filter(is_staff=True, is_active=True).order_by('first_name', 'last_name')
    
    context = {
        'client': client,
        'subscription': subscription,
        'committee': committee,
        'service_years': service_years,
        'current_year': current_year,
        'upcoming_meetings': upcoming_meetings,
        'past_meetings': past_meetings,
        'employee_data': employee_data,
        'training_data': training_data,
        'pivotal_data': pivotal_data,
        'atr_docs': atr_docs,
        'hr_docs': hr_docs,
        'committee_docs': committee_docs,
        'compliance_docs': compliance_docs,
        'section_progress': section_progress,
        'stats': stats,
        'available_sdfs': available_sdfs,
        'doc_types': WSPATRDocument.DOCUMENT_TYPE_CHOICES,
    }
    
    return render(request, 'corporate/wspatr_management.html', context)


@login_required
def wspatr_meeting_detail(request, client_pk, meeting_pk):
    """View and manage a specific Training Committee meeting."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    meeting = get_object_or_404(
        TrainingCommitteeMeeting.objects.select_related('committee', 'template')
        .prefetch_related(
            'tc_agenda_items',
            Prefetch('tc_attendance_records', queryset=TCMeetingAttendance.objects.select_related('member__contact')),
            'tc_action_items',
        ),
        pk=meeting_pk,
        committee__client=client
    )
    
    context = {
        'client': client,
        'meeting': meeting,
        'agenda_items': meeting.tc_agenda_items.order_by('order'),
        'attendance_records': meeting.tc_attendance_records.all(),
        'action_items': meeting.tc_action_items.order_by('-created_at'),
    }
    
    return render(request, 'corporate/wspatr_meeting_detail.html', context)


@login_required
def wspatr_update_meeting(request, client_pk, meeting_pk):
    """Update meeting details (date, time, location, etc.)."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    meeting = get_object_or_404(TrainingCommitteeMeeting, pk=meeting_pk, committee__client=client)
    
    if request.method == 'POST':
        # Update meeting date/time
        scheduled_date = request.POST.get('scheduled_date')
        scheduled_time = request.POST.get('scheduled_time')
        duration = request.POST.get('duration_minutes')
        location = request.POST.get('location')
        meeting_type = request.POST.get('meeting_type')
        
        if scheduled_date:
            from datetime import datetime
            meeting.scheduled_date = datetime.strptime(scheduled_date, "%Y-%m-%d").date()
        
        if scheduled_time:
            from datetime import datetime
            meeting.scheduled_time = datetime.strptime(scheduled_time, "%H:%M").time()
        
        if duration:
            meeting.duration_minutes = int(duration)
        if location:
            meeting.location = location
        if meeting_type:
            meeting.meeting_type = meeting_type
        
        meeting.save()
        messages.success(request, "Meeting updated successfully.")
        
    return redirect('corporate:wspatr_meeting_detail', client_pk=client_pk, meeting_pk=meeting_pk)


@login_required
def wspatr_create_meeting(request, client_pk):
    """Create a new Training Committee meeting."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        scheduled_date = request.POST.get('scheduled_date')
        scheduled_time = request.POST.get('scheduled_time')
        location = request.POST.get('location', 'Online')
        meeting_type = request.POST.get('meeting_type', 'QUARTERLY')
        service_year_id = request.POST.get('service_year_id')
        
        # Get or create committee
        committee, created = TrainingCommittee.objects.get_or_create(
            client=client,
            defaults={'name': f"{client.company_name} Training Committee"}
        )
        
        service_year = get_object_or_404(WSPATRServiceYear, pk=service_year_id, client=client)
        
        from datetime import datetime
        date_obj = datetime.strptime(scheduled_date, "%Y-%m-%d").date()
        time_obj = datetime.strptime(scheduled_time, "%H:%M").time() if scheduled_time else None
        
        meeting = TrainingCommitteeMeeting.objects.create(
            committee=committee,
            service_year=service_year,
            title=title,
            scheduled_date=date_obj,
            scheduled_time=time_obj,
            location=location,
            meeting_type=meeting_type,
            status='SCHEDULED'
        )
        
        messages.success(request, f"Meeting '{title}' scheduled successfully.")
        return redirect('corporate:wspatr_management', client_pk=client.pk)
    
    return redirect('corporate:wspatr_management', client_pk=client.pk)


@login_required
def wspatr_record_attendance(request, client_pk, meeting_pk):
    """Record attendance for a meeting."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    meeting = get_object_or_404(TrainingCommitteeMeeting, pk=meeting_pk, committee__client=client)
    
    if request.method == 'POST':
        attendance_ids = request.POST.getlist('attendance')
        
        # Update all attendance records
        for record in meeting.tc_attendance_records.all():
            was_present = str(record.pk) in attendance_ids
            if record.attended != was_present:
                record.attended = was_present
                record.save()
        
        messages.success(request, "Attendance recorded successfully.")
    
    return redirect('corporate:wspatr_meeting_detail', client_pk=client_pk, meeting_pk=meeting_pk)


@login_required
def wspatr_add_action_item(request, client_pk, meeting_pk):
    """Add an action item from a meeting."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    meeting = get_object_or_404(TrainingCommitteeMeeting, pk=meeting_pk, committee__client=client)
    
    if request.method == 'POST':
        description = request.POST.get('description')
        assigned_to_id = request.POST.get('assigned_to')
        due_date = request.POST.get('due_date')
        
        if description:
            action_item = TCMeetingActionItem.objects.create(
                meeting=meeting,
                description=description,
                due_date=due_date if due_date else None,
            )
            
            if assigned_to_id:
                try:
                    assigned_to = TrainingCommitteeMember.objects.get(pk=assigned_to_id)
                    action_item.assigned_to = assigned_to
                    action_item.save()
                except TrainingCommitteeMember.DoesNotExist:
                    pass
            
            messages.success(request, "Action item added.")
    
    return redirect('corporate:wspatr_meeting_detail', client_pk=client_pk, meeting_pk=meeting_pk)


@login_required
def wspatr_update_action_item(request, client_pk, action_pk):
    """Update status of an action item."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    action_item = get_object_or_404(
        TCMeetingActionItem,
        pk=action_pk,
        meeting__committee__client=client
    )
    
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(TCMeetingActionItem.STATUS_CHOICES):
            action_item.status = status
            if status == 'COMPLETED':
                action_item.completed_at = timezone.now()
            action_item.save()
            messages.success(request, "Action item updated.")
    
    return redirect('corporate:wspatr_meeting_detail', 
                    client_pk=client_pk, 
                    meeting_pk=action_item.meeting.pk)


@login_required  
def wspatr_add_committee_member(request, client_pk):
    """Add a member to the Training Committee."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    # Get the subscription to inherit campus
    subscription = ClientServiceSubscription.objects.filter(
        client=client,
        service__service_type='WSP_ATR',
        status='ACTIVE'
    ).first()
    
    if not subscription:
        messages.error(request, "No active WSP/ATR subscription found.")
        return redirect('corporate:wspatr_management', client_pk=client_pk)
    
    committee, created = TrainingCommittee.objects.get_or_create(
        client=client,
        defaults={
            'name': f"{client.company_name} Training Committee",
            'campus': subscription.campus,
        }
    )
    
    if request.method == 'POST':
        member_type = request.POST.get('member_type')  # 'contact' or 'manual'
        member_id = request.POST.get('member_id')
        role = request.POST.get('role')
        name = request.POST.get('name', '')
        email = request.POST.get('email', '')
        department = request.POST.get('department', '')
        
        try:
            if member_type == 'contact' and member_id:
                contact = CorporateContact.objects.get(pk=member_id, client=client)
                TrainingCommitteeMember.objects.create(
                    committee=committee,
                    contact=contact,
                    role=role or 'EMPLOYER_REP',
                    department=department
                )
                messages.success(request, f"{contact.first_name} {contact.last_name} added to the committee.")
            elif member_type == 'manual' and name:
                # Manual entry without linking to a contact
                TrainingCommitteeMember.objects.create(
                    committee=committee,
                    name=name,
                    email=email,
                    role=role or 'EMPLOYER_REP',
                    department=department
                )
                messages.success(request, f"{name} added to the committee.")
            else:
                messages.error(request, "Please select a contact or enter member details manually.")
        except CorporateContact.DoesNotExist:
            messages.error(request, "Contact not found.")
    
    return redirect('corporate:wspatr_management', client_pk=client_pk)


@login_required
def wspatr_remove_committee_member(request, client_pk, member_pk):
    """Remove a member from the Training Committee."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    member = get_object_or_404(TrainingCommitteeMember, pk=member_pk, committee__client=client)
    
    member.is_active = False
    member.save()
    messages.success(request, "Committee member removed.")
    
    return redirect('corporate:wspatr_management', client_pk=client_pk)


@login_required
def wspatr_create_service_year(request, client_pk):
    """Create a new WSP/ATR service year - simplified, no subscription required."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    # Try to get the active WSP/ATR subscription (optional)
    subscription = ClientServiceSubscription.objects.filter(
        client=client,
        service__service_type='WSP_ATR',
        status='ACTIVE'
    ).first()
    
    if request.method == 'POST':
        financial_year = request.POST.get('financial_year')
        
        if financial_year:
            try:
                fy = int(financial_year)
                # Get campus from client or fallback
                from tenants.models import Campus
                campus = client.campus or Campus.objects.first()
                
                # Check if already exists
                existing = WSPATRServiceYear.objects.filter(
                    client=client,
                    financial_year=fy
                ).first()
                
                if existing:
                    messages.info(request, f"Service year FY{fy}/{fy + 1} already exists.")
                else:
                    # Create without requiring subscription - deadline auto-calculated in model.save()
                    WSPATRServiceYear.objects.create(
                        subscription=subscription,  # Can be None
                        client=client,
                        financial_year=fy,
                        campus=campus,
                        status='NOT_STARTED',
                    )
                    messages.success(request, f"Service year FY{fy}/{fy + 1} created.")
            except ValueError:
                messages.error(request, "Invalid financial year.")
    
    return redirect('corporate:wspatr_management', client_pk=client_pk)


@login_required
def wspatr_send_meeting_invite(request, client_pk, meeting_pk):
    """Send meeting invite to all committee members."""
    from .meeting_invites import MeetingInviteService
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    meeting = get_object_or_404(TrainingCommitteeMeeting, pk=meeting_pk, committee__client=client)
    
    try:
        service = MeetingInviteService()
        result = service.send_invites(meeting)
        
        if result.get('sent_count', 0) > 0:
            messages.success(request, f"Meeting invites sent to {result['sent_count']} members.")
        else:
            messages.warning(request, "No invites were sent. Check committee member email addresses.")
    except Exception as e:
        messages.error(request, f"Error sending invites: {str(e)}")
    
    return redirect('corporate:wspatr_meeting_detail', client_pk=client_pk, meeting_pk=meeting_pk)


@login_required
def wspatr_schedule_meetings(request, client_pk):
    """Manually schedule quarterly meetings for a client."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    # Get the active WSP/ATR subscription for this client
    subscription = ClientServiceSubscription.objects.filter(
        client=client,
        service__service_type='WSP_ATR',
        status='ACTIVE'
    ).first()
    
    if not subscription:
        messages.error(request, "No active WSP/ATR subscription found for this client.")
        return redirect('corporate:wspatr_management', client_pk=client_pk)
    
    # Get or create committee
    committee, _ = TrainingCommittee.objects.get_or_create(
        client=client,
        defaults={
            'name': f"{client.company_name} Training Committee",
            'campus': subscription.campus,
        }
    )
    
    # Determine current financial year (May-Apr for WSP/ATR cycle)
    today = timezone.now().date()
    if today.month >= 5:
        financial_year = today.year
    else:
        financial_year = today.year - 1
    
    # Get or create service year for current FY
    from datetime import date
    service_year, sy_created = WSPATRServiceYear.objects.get_or_create(
        client=client,
        financial_year=financial_year,
        defaults={
            'subscription': subscription,
            'status': 'NOT_STARTED',
        }
    )
    
    # Import the helper function and schedule meetings
    from .service_signals import schedule_quarterly_meetings
    
    # Only schedule if service year was just created or no meetings exist
    existing_meetings = TrainingCommitteeMeeting.objects.filter(
        committee=committee,
        service_year=service_year
    ).count()
    
    if existing_meetings == 0:
        schedule_quarterly_meetings(committee, service_year, financial_year)
        meetings_created = TrainingCommitteeMeeting.objects.filter(
            committee=committee,
            service_year=service_year
        ).count()
        messages.success(request, f"{meetings_created} quarterly meetings scheduled for FY{financial_year}/{financial_year + 1}.")
    else:
        messages.info(request, f"Meetings already scheduled for FY{financial_year}/{financial_year + 1}.")
    
    return redirect('corporate:wspatr_management', client_pk=client_pk)


# =============================================================================
# WSP/ATR CLIENTS DASHBOARD - Overview of all WSP/ATR clients
# =============================================================================

@login_required
def wspatr_clients_dashboard(request):
    """
    Dashboard showing all clients with WSP/ATR subscriptions and their progress.
    Helps administrators track all WSP/ATR work in one place.
    Supports filtering by SETA, SDF (consultant), and status.
    """
    # Determine current financial year
    today = timezone.now().date()
    current_fy = today.year if today.month >= 5 else today.year - 1
    
    # Get filter parameters
    selected_seta = request.GET.get('seta', '')
    selected_sdf = request.GET.get('sdf', '')
    selected_status = request.GET.get('status', '')
    
    # Base queryset for WSP/ATR subscriptions
    wspatr_subscriptions = ClientServiceSubscription.objects.filter(
        service__service_type='WSP_ATR',
        status='ACTIVE'
    ).select_related('client', 'client__seta', 'service', 'assigned_consultant').order_by('client__company_name')
    
    # Apply SETA filter
    if selected_seta:
        wspatr_subscriptions = wspatr_subscriptions.filter(client__seta_id=selected_seta)
    
    # Apply SDF (consultant) filter
    if selected_sdf:
        wspatr_subscriptions = wspatr_subscriptions.filter(assigned_consultant_id=selected_sdf)
    
    # Build client data with progress info
    clients_data = []
    for sub in wspatr_subscriptions:
        client = sub.client
        
        # Get service year for current FY
        service_year = WSPATRServiceYear.objects.filter(
            client=client,
            financial_year=current_fy
        ).first()
        
        # Get committee info
        committee = TrainingCommittee.objects.filter(client=client).first()
        committee_members = committee.members.filter(is_active=True).count() if committee else 0
        
        # Get next meeting
        next_meeting = None
        if committee:
            next_meeting = TrainingCommitteeMeeting.objects.filter(
                committee=committee,
                scheduled_date__gte=today
            ).order_by('scheduled_date').first()
        
        # Determine overall status/health
        health = 'grey'  # Not started
        if service_year:
            if service_year.status in ['COMPLETED', 'ACCEPTED']:
                health = 'green'
            elif service_year.status in ['SUBMITTED']:
                health = 'blue'
            elif service_year.status in ['DATA_COLLECTION', 'DRAFTING', 'INTERNAL_REVIEW', 'CLIENT_REVIEW']:
                health = 'yellow'
            elif service_year.is_overdue:
                health = 'red'
            else:
                health = 'yellow'
        
        # Get document progress
        doc_progress = 0
        if service_year:
            total_docs = service_year.documents.filter(is_required=True).count()
            uploaded_docs = service_year.documents.filter(is_required=True).exclude(file='').count()
            doc_progress = int((uploaded_docs / total_docs) * 100) if total_docs > 0 else 0
        
        clients_data.append({
            'client': client,
            'subscription': sub,
            'service_year': service_year,
            'committee': committee,
            'committee_members': committee_members,
            'next_meeting': next_meeting,
            'health': health,
            'progress': service_year.progress_percentage if service_year else 0,
            'doc_progress': doc_progress,
            'sdf': sub.assigned_consultant,
        })
    
    # Apply status filter after building data
    if selected_status:
        status_map = {
            'completed': 'green',
            'submitted': 'blue',
            'in_progress': 'yellow',
            'overdue': 'red',
            'not_started': 'grey',
        }
        filter_health = status_map.get(selected_status, '')
        if filter_health:
            clients_data = [c for c in clients_data if c['health'] == filter_health]
    
    # Calculate summary stats
    total_clients = len(clients_data)
    completed = sum(1 for c in clients_data if c['health'] == 'green')
    submitted = sum(1 for c in clients_data if c['health'] == 'blue')
    in_progress = sum(1 for c in clients_data if c['health'] == 'yellow')
    overdue = sum(1 for c in clients_data if c['health'] == 'red')
    not_started = sum(1 for c in clients_data if c['health'] == 'grey')
    
    # Get upcoming meetings across all clients (respecting filters)
    meeting_filter = {'scheduled_date__gte': today, 'scheduled_date__lte': today + timezone.timedelta(days=30)}
    if selected_seta:
        meeting_filter['committee__client__seta_id'] = selected_seta
    if selected_sdf:
        # Get clients assigned to this SDF
        sdf_client_ids = [c['client'].id for c in clients_data]
        meeting_filter['committee__client_id__in'] = sdf_client_ids
    
    upcoming_meetings = TrainingCommitteeMeeting.objects.filter(
        **meeting_filter
    ).select_related('committee__client').order_by('scheduled_date')[:10]
    
    # Get upcoming deadlines
    upcoming_deadlines = WSPATRServiceYear.objects.filter(
        financial_year=current_fy,
        status__in=['NOT_STARTED', 'DATA_COLLECTION', 'DRAFTING', 'INTERNAL_REVIEW', 'CLIENT_REVIEW'],
        submission_deadline__gte=today,
        submission_deadline__lte=today + timezone.timedelta(days=60)
    ).select_related('client').order_by('submission_deadline')[:10]
    
    # Get available filters
    setas = SETA.objects.filter(
        corporate_clients__service_subscriptions__service__service_type='WSP_ATR',
        corporate_clients__service_subscriptions__status='ACTIVE'
    ).distinct().order_by('name')
    
    sdfs = User.objects.filter(
        assigned_service_subscriptions__service__service_type='WSP_ATR',
        assigned_service_subscriptions__status='ACTIVE'
    ).distinct().order_by('first_name', 'last_name')
    
    context = {
        'clients_data': clients_data,
        'current_fy': current_fy,
        'total_clients': total_clients,
        'completed': completed,
        'submitted': submitted,
        'in_progress': in_progress,
        'overdue': overdue,
        'not_started': not_started,
        'upcoming_meetings': upcoming_meetings,
        'upcoming_deadlines': upcoming_deadlines,
        # Filters
        'setas': setas,
        'sdfs': sdfs,
        'selected_seta': selected_seta,
        'selected_sdf': selected_sdf,
        'selected_status': selected_status,
    }
    
    return render(request, 'corporate/wspatr_clients_dashboard.html', context)


# =============================================================================
# WSP/ATR DOCUMENT MANAGEMENT
# =============================================================================

@login_required
def wspatr_documents(request, client_pk, year_pk):
    """View and manage documents for a WSP/ATR service year."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(WSPATRServiceYear, pk=year_pk, client=client)
    
    # Get all documents grouped by status
    documents = service_year.documents.all().order_by('sort_order', 'document_type')
    
    required_docs = documents.filter(is_required=True)
    uploaded_docs = required_docs.exclude(file='').count()
    total_required = required_docs.count()
    
    # Calculate progress
    doc_progress = int((uploaded_docs / total_required) * 100) if total_required > 0 else 0
    
    context = {
        'client': client,
        'service_year': service_year,
        'documents': documents,
        'doc_progress': doc_progress,
        'uploaded_count': uploaded_docs,
        'total_required': total_required,
        'document_types': WSPATRDocument.DOCUMENT_TYPE_CHOICES,
    }
    
    return render(request, 'corporate/wspatr_documents.html', context)


@login_required
def wspatr_upload_document(request, client_pk, year_pk):
    """Upload a document for a WSP/ATR service year."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(WSPATRServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        doc_pk = request.POST.get('document_id')
        document_type = request.POST.get('document_type')
        meeting_id = request.POST.get('meeting_id')
        
        if doc_pk:
            # Update existing document
            document = get_object_or_404(WSPATRDocument, pk=doc_pk, service_year=service_year)
        else:
            # Create new document
            document = WSPATRDocument(
                service_year=service_year,
                document_type=document_type or 'OTHER',
                name=request.POST.get('name', ''),
                is_required=request.POST.get('is_required', 'true') == 'true',
                meeting_id=meeting_id if meeting_id else None
            )
        
        if 'file' in request.FILES:
            document.file = request.FILES['file']
            document.uploaded_by = request.user
            document.uploaded_at = timezone.now()
            document.status = 'UPLOADED'
        
        if request.POST.get('notes'):
            document.notes = request.POST.get('notes')
        
        document.save()
        
        # Update service year progress
        service_year.update_progress()
        
        messages.success(request, f"Document '{document.display_name}' uploaded successfully.")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'document_id': document.pk,
                'file_name': document.file_name,
                'status': document.status,
                'progress': service_year.progress_percentage,
            })
        
        return redirect('corporate:wspatr_management', client_pk=client_pk)
    
    return redirect('corporate:wspatr_management', client_pk=client_pk)


@login_required
def wspatr_delete_document(request, client_pk, year_pk, doc_pk):
    """Delete a document from a WSP/ATR service year."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(WSPATRServiceYear, pk=year_pk, client=client)
    document = get_object_or_404(WSPATRDocument, pk=doc_pk, service_year=service_year)
    
    if request.method == 'POST':
        doc_name = document.display_name
        
        # If it's a required document, just clear the file, don't delete the record
        if document.is_required:
            document.file = None
            document.file_name = ''
            document.file_size = None
            document.uploaded_at = None
            document.uploaded_by = None
            document.status = 'PENDING'
            document.save()
            messages.success(request, f"File removed from '{doc_name}'. Document requirement remains.")
        else:
            # Delete optional documents entirely
            document.delete()
            messages.success(request, f"Document '{doc_name}' deleted.")
        
        # Update service year progress
        service_year.update_progress()
    
    return redirect('corporate:wspatr_documents', client_pk=client_pk, year_pk=year_pk)


@login_required
def wspatr_add_document_requirement(request, client_pk, year_pk):
    """Add a new document requirement to a service year."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(WSPATRServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        document_type = request.POST.get('document_type', 'OTHER')
        name = request.POST.get('name', '')
        description = request.POST.get('description', '')
        is_required = request.POST.get('is_required', 'true') == 'true'
        
        document = WSPATRDocument.objects.create(
            service_year=service_year,
            document_type=document_type,
            name=name,
            description=description,
            is_required=is_required,
            status='PENDING'
        )
        
        messages.success(request, f"Document requirement '{document.display_name}' added.")
    
    return redirect('corporate:wspatr_documents', client_pk=client_pk, year_pk=year_pk)


@login_required
def wspatr_initialize_documents(request, client_pk, year_pk):
    """Initialize standard document requirements for a service year."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(WSPATRServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        # Check if there's a SETA-specific template
        template = WSPATRDocumentTemplate.objects.filter(
            seta=client.seta,
            is_active=True
        ).first()
        
        if not template:
            # Use default template
            template = WSPATRDocumentTemplate.objects.filter(
                seta__isnull=True,
                is_active=True
            ).first()
        
        if template:
            # Create documents from template
            docs = template.create_documents_for_service_year(service_year)
            messages.success(request, f"{len(docs)} document requirements initialized from template.")
        else:
            # Create standard document requirements
            standard_docs = [
                ('SDL_CERTIFICATE', 'SDL Certificate', True),
                ('COMPANY_REGISTRATION', 'Company Registration (CIPC)', True),
                ('BEE_CERTIFICATE', 'B-BBEE Certificate', True),
                ('EMPLOYEE_LIST', 'Employee List/Headcount', True),
                ('TRAINING_PLAN', 'Training Plan', True),
                ('TRAINING_BUDGET', 'Training Budget', True),
                ('COMMITTEE_MINUTES', 'Training Committee Minutes', True),
                ('COMMITTEE_ATTENDANCE', 'Training Committee Attendance Register', True),
                ('ORGANOGRAM', 'Company Organogram', False),
                ('SKILLS_AUDIT', 'Skills Audit Report', False),
            ]
            
            for idx, (doc_type, name, required) in enumerate(standard_docs):
                WSPATRDocument.objects.get_or_create(
                    service_year=service_year,
                    document_type=doc_type,
                    defaults={
                        'name': name,
                        'is_required': required,
                        'sort_order': idx,
                    }
                )
            
            messages.success(request, "Standard document requirements initialized.")
    
    return redirect('corporate:wspatr_documents', client_pk=client_pk, year_pk=year_pk)


@login_required
def wspatr_upload_approval_letter(request, client_pk, year_pk):
    """Upload the WSP approval letter received from SETA."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(WSPATRServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, "No file selected.")
            return redirect('corporate:wspatr_documents', client_pk=client_pk, year_pk=year_pk)
        
        # Get or create approval letter document
        approval_doc, created = WSPATRDocument.objects.get_or_create(
            service_year=service_year,
            document_type='APPROVAL_LETTER',
            defaults={
                'name': 'WSP Approval Letter from SETA',
                'is_required': False,
            }
        )
        
        approval_doc.file = request.FILES['file']
        approval_doc.uploaded_by = request.user
        approval_doc.uploaded_at = timezone.now()
        approval_doc.status = 'UPLOADED'
        approval_doc.notes = request.POST.get('notes', '')
        approval_doc.save()
        
        # Update service year status and outcome
        if request.POST.get('mark_approved') == 'true':
            service_year.status = 'ACCEPTED'
            service_year.outcome = 'APPROVED'
            service_year.outcome_date = timezone.now().date()
            service_year.seta_reference = request.POST.get('seta_reference', '')
            service_year.save()
        
        messages.success(request, "WSP Approval Letter uploaded successfully.")
    
    return redirect('corporate:wspatr_documents', client_pk=client_pk, year_pk=year_pk)


@login_required
def wspatr_update_status(request, client_pk, year_pk):
    """Update the status of a WSP/ATR service year."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(WSPATRServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status and new_status in dict(WSPATRServiceYear.STATUS_CHOICES):
            old_status = service_year.status
            service_year.status = new_status
            
            # Auto-set dates based on status
            if new_status == 'SUBMITTED' and not service_year.submitted_date:
                service_year.submitted_date = timezone.now().date()
            
            if new_status in ['ACCEPTED', 'COMPLETED']:
                service_year.outcome = 'APPROVED'
                if not service_year.outcome_date:
                    service_year.outcome_date = timezone.now().date()
            elif new_status == 'REJECTED':
                service_year.outcome = 'REJECTED'
                if not service_year.outcome_date:
                    service_year.outcome_date = timezone.now().date()
            
            # Update progress based on status
            status_progress = {
                'NOT_STARTED': 0,
                'DATA_COLLECTION': 20,
                'DRAFTING': 40,
                'INTERNAL_REVIEW': 60,
                'CLIENT_REVIEW': 70,
                'SUBMITTED': 90,
                'ACCEPTED': 100,
                'COMPLETED': 100,
                'REJECTED': 80,
            }
            service_year.progress_percentage = max(
                service_year.progress_percentage,
                status_progress.get(new_status, 0)
            )
            
            service_year.save()
            messages.success(request, f"Status updated from {old_status} to {new_status}.")
    
    # Redirect back to appropriate page
    next_url = request.POST.get('next', '')
    if next_url:
        return redirect(next_url)
    return redirect('corporate:wspatr_management', client_pk=client_pk)


@login_required
def wspatr_assign_sdf(request, client_pk):
    """Assign or change the SDF (Skills Development Facilitator) for a client's WSP/ATR subscription."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    subscription = ClientServiceSubscription.objects.filter(
        client=client,
        service__service_type='WSP_ATR',
        status='ACTIVE'
    ).first()
    
    if not subscription:
        messages.error(request, "No active WSP/ATR subscription found.")
        return redirect('corporate:client_360', pk=client_pk)
    
    if request.method == 'POST':
        sdf_id = request.POST.get('sdf_id')
        
        if sdf_id:
            sdf = get_object_or_404(User, pk=sdf_id)
            subscription.assigned_consultant = sdf
            subscription.save()
            
            # Also update current service year
            current_fy = timezone.now().year if timezone.now().month >= 5 else timezone.now().year - 1
            WSPATRServiceYear.objects.filter(
                subscription=subscription,
                financial_year=current_fy
            ).update(assigned_consultant=sdf)
            
            messages.success(request, f"SDF assigned: {sdf.get_full_name()}")
        else:
            subscription.assigned_consultant = None
            subscription.save()
            messages.success(request, "SDF assignment removed.")
    
    return redirect('corporate:wspatr_management', client_pk=client_pk)


# =============================================================================
# INDIVIDUAL DEVELOPMENT PLANS (IDP)
# =============================================================================

@login_required
def employee_idp_list(request, employee_pk):
    """List all IDPs for a specific employee."""
    employee = get_object_or_404(CorporateEmployee, pk=employee_pk)
    idps = employee.idps.all().order_by('-period_start')
    
    context = {
        'employee': employee,
        'idps': idps,
        'client': employee.client,
    }
    return render(request, 'corporate/idp/list.html', context)


@login_required
def employee_idp_detail(request, pk):
    """View details of a specific IDP."""
    idp = get_object_or_404(EmployeeIDP.objects.select_related('employee', 'manager'), pk=pk)
    training_needs = idp.training_needs.all().order_by('priority', 'target_date')
    
    context = {
        'idp': idp,
        'employee': idp.employee,
        'training_needs': training_needs,
        'client': idp.employee.client,
    }
    return render(request, 'corporate/idp/detail.html', context)


@login_required
def employee_idp_create(request, employee_pk):
    """Create a new IDP for an employee."""
    employee = get_object_or_404(CorporateEmployee, pk=employee_pk)
    
    if request.method == 'POST':
        period_start = request.POST.get('period_start')
        period_end = request.POST.get('period_end')
        career_goals = request.POST.get('career_goals', '')
        development_areas = request.POST.get('development_areas', '')
        service_year_id = request.POST.get('service_year_id')
        
        idp = EmployeeIDP.objects.create(
            employee=employee,
            period_start=period_start,
            period_end=period_end,
            career_goals=career_goals,
            development_areas=development_areas,
            service_year_id=service_year_id if service_year_id else None,
            status='DRAFT'
        )
        
        messages.success(request, f"IDP created for {employee.get_full_name()}.")
        return redirect('corporate:employee_idp_detail', pk=idp.pk)
    
    # Get available service years for the client
    service_years = WSPATRServiceYear.objects.filter(client=employee.client).order_by('-financial_year')
    
    context = {
        'employee': employee,
        'client': employee.client,
        'service_years': service_years,
    }
    return render(request, 'corporate/idp/form.html', context)


@login_required
def employee_idp_sign_off(request, pk):
    """Handle employee or manager sign-off for an IDP."""
    idp = get_object_or_404(EmployeeIDP, pk=pk)
    role = request.POST.get('role') # 'employee' or 'manager'
    
    if request.method == 'POST':
        today = timezone.now().date()
        if role == 'employee':
            idp.employee_sign_off_date = today
        elif role == 'manager':
            idp.manager_sign_off_date = today
            idp.status = 'APPROVED'
        
        idp.save()
        messages.success(request, f"{role.capitalize()} sign-off recorded.")
        
    return redirect('corporate:employee_idp_detail', pk=idp.pk)


@login_required
def idp_add_training_need(request, idp_pk):
    """Add a training need to an IDP."""
    idp = get_object_or_404(EmployeeIDP, pk=idp_pk)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        priority = request.POST.get('priority', 'MEDIUM')
        target_date = request.POST.get('target_date') or None
        is_wsp_planned = request.POST.get('is_wsp_planned') == 'on'
        
        IDPTrainingNeed.objects.create(
            idp=idp,
            title=title,
            description=description,
            priority=priority,
            target_date=target_date,
            is_wsp_planned=is_wsp_planned,
            status='IDENTIFIED'
        )
        
        messages.success(request, f"Training need '{title}' added to IDP.")
        
    return redirect('corporate:employee_idp_detail', pk=idp.pk)



@login_required
def sync_idp_to_wsp(request, service_year_pk):
    """
    Sync training needs from IDPs to the WSP submission.
    Aggregates demographics from individual employees into WSPPlannedTraining.
    """
    from django.db.models import Sum, F
    service_year = get_object_or_404(WSPATRServiceYear, pk=service_year_pk)
    wsp = service_year.wsp_submission
    
    if not wsp:
        messages.error(request, "No WSP submission linked to this service year.")
        return redirect('corporate:wspatr_management', pk=service_year.pk)
    
    # Get all training needs from IDPs linked to this service year that are marked for WSP
    training_needs = IDPTrainingNeed.objects.filter(
        idp__service_year=service_year,
        is_wsp_planned=True,
        idp__status='APPROVED'  # Only pull from approved IDPs
    ).select_related('idp__employee')
    
    if not training_needs.exists():
        messages.warning(request, "No approved IDP training needs found for this service year.")
        return redirect('corporate:wspatr_management', pk=service_year.pk)
    
    # Clear existing planned training to avoid duplicates? 
    # For this implementation, we'll reset the counts and re-aggregate
    wsp.planned_training.all().update(
        african_male=0, african_female=0,
        coloured_male=0, coloured_female=0,
        indian_male=0, indian_female=0,
        white_male=0, white_female=0,
        disabled_male=0, disabled_female=0
    )
    
    synced_count = 0
    for need in training_needs:
        # Find or create a WSPPlannedTraining record for this intervention/qualification
        planned, created = WSPPlannedTraining.objects.get_or_create(
            wsp=wsp,
            intervention_type=need.intervention_type,
            qualification=need.qualification,
            defaults={'training_description': need.title if not need.qualification else need.qualification.title}
        )
        
        # Update demographics based on the employee
        emp = need.idp.employee
        learner = emp.learner
        
        # Map race/gender to WSP fields
        if learner.population_group == 'A' and learner.gender == 'M': planned.african_male += 1
        elif learner.population_group == 'A' and learner.gender == 'F': planned.african_female += 1
        elif learner.population_group == 'C' and learner.gender == 'M': planned.coloured_male += 1
        elif learner.population_group == 'C' and learner.gender == 'F': planned.coloured_female += 1
        elif learner.population_group == 'I' and learner.gender == 'M': planned.indian_male += 1
        elif learner.population_group == 'I' and learner.gender == 'F': planned.indian_female += 1
        elif learner.population_group == 'W' and learner.gender == 'M': planned.white_male += 1
        elif learner.population_group == 'W' and learner.gender == 'F': planned.white_female += 1
        
        # Disability
        if learner.disability_status != 'N':
            if learner.gender == 'M': planned.disabled_male += 1
            else: planned.disabled_female += 1
            
        planned.save()
        synced_count += 1
        
    # Update WSP totals
    wsp.total_learners_planned = wsp.planned_training.aggregate(
        total=Sum(F('african_male') + F('african_female') + F('coloured_male') + F('coloured_female') + 
                  F('indian_male') + F('indian_female') + F('white_male') + F('white_female'))
    )['total'] or 0
    wsp.save()
    
    messages.success(request, f"Successfully synced {synced_count} training needs from IDPs to WSP.")
    return redirect('corporate:wspatr_management', pk=service_year.pk)


# =============================================================================
# MENTOR INVITATION & MANAGEMENT VIEWS
# =============================================================================

from .models import MentorInvitation, PlacementInvoice


@login_required
def mentor_invitation_list(request, host_employer_pk):
    """List all mentor invitations for a host employer."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    invitations = MentorInvitation.objects.filter(host=host).select_related(
        'invited_by', 'created_mentor'
    )
    
    context = {
        'host': host,
        'invitations': invitations,
    }
    return render(request, 'corporate/workplace/mentor_invitation_list.html', context)


@login_required
def mentor_invitation_create(request, host_employer_pk):
    """Create and send a mentor invitation."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    
    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        days_valid = int(request.POST.get('days_valid', 14))
        
        if not email:
            messages.error(request, "Email is required.")
            return redirect('corporate:mentor_invitation_create', host_employer_pk=host.pk)
        
        # Check if there's already a pending invitation for this email
        existing = MentorInvitation.objects.filter(
            host=host, email=email, status='PENDING'
        ).first()
        if existing:
            messages.warning(request, f"A pending invitation already exists for {email}.")
            return redirect('corporate:mentor_invitation_list', host_employer_pk=host.pk)
        
        # Create the invitation
        invitation = MentorInvitation.create_invitation(
            host=host,
            invited_by=request.user,
            email=email,
            first_name=first_name,
            last_name=last_name,
            days_valid=days_valid
        )
        
        # Build registration URL
        registration_url = request.build_absolute_uri(
            reverse('mentor_registration', kwargs={'token': invitation.token})
        )
        
        messages.success(
            request, 
            f"Invitation created for {email}. Registration link: {registration_url}"
        )
        return redirect('corporate:mentor_invitation_list', host_employer_pk=host.pk)
    
    context = {
        'host': host,
    }
    return render(request, 'corporate/workplace/mentor_invitation_form.html', context)


@login_required
def mentor_invitation_resend(request, host_employer_pk, invitation_pk):
    """Resend a mentor invitation (creates new token/expiry)."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    invitation = get_object_or_404(MentorInvitation, pk=invitation_pk, host=host)
    
    if invitation.status != 'PENDING':
        messages.error(request, "Can only resend pending invitations.")
        return redirect('corporate:mentor_invitation_list', host_employer_pk=host.pk)
    
    # Cancel old and create new invitation
    invitation.status = 'CANCELLED'
    invitation.save()
    
    new_invitation = MentorInvitation.create_invitation(
        host=host,
        invited_by=request.user,
        email=invitation.email,
        first_name=invitation.first_name,
        last_name=invitation.last_name,
        days_valid=14
    )
    
    registration_url = request.build_absolute_uri(
        reverse('mentor_registration', kwargs={'token': new_invitation.token})
    )
    
    messages.success(request, f"New invitation sent. Registration link: {registration_url}")
    return redirect('corporate:mentor_invitation_list', host_employer_pk=host.pk)


@login_required
def mentor_list(request, host_employer_pk):
    """List all mentors for a host employer."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    mentors = HostMentor.objects.filter(host=host).select_related('user', 'approved_by')
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        mentors = mentors.filter(status=status)
    
    context = {
        'host': host,
        'mentors': mentors,
        'status_filter': status,
    }
    return render(request, 'corporate/workplace/mentor_list.html', context)


@login_required
def mentor_detail(request, host_employer_pk, mentor_pk):
    """View mentor details."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    mentor = get_object_or_404(HostMentor, pk=mentor_pk, host=host)
    
    # Get placements for this mentor
    placements = WorkplacePlacement.objects.filter(mentor=mentor).select_related(
        'learner', 'enrollment__qualification'
    )
    
    context = {
        'host': host,
        'mentor': mentor,
        'placements': placements,
    }
    return render(request, 'corporate/workplace/mentor_detail.html', context)


@login_required
def mentor_approve(request, host_employer_pk, mentor_pk):
    """Approve a mentor and activate their user account."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    mentor = get_object_or_404(HostMentor, pk=mentor_pk, host=host)
    
    if mentor.status == 'APPROVED':
        messages.info(request, f"{mentor.full_name} is already approved.")
        return redirect('corporate:mentor_detail', host_employer_pk=host.pk, mentor_pk=mentor.pk)
    
    if request.method == 'POST':
        mentor.approve(request.user)
        messages.success(
            request, 
            f"{mentor.full_name} has been approved. Their portal account is now active."
        )
        return redirect('corporate:mentor_detail', host_employer_pk=host.pk, mentor_pk=mentor.pk)
    
    context = {
        'host': host,
        'mentor': mentor,
    }
    return render(request, 'corporate/workplace/mentor_approve_confirm.html', context)


@login_required
def mentor_deactivate(request, host_employer_pk, mentor_pk):
    """Deactivate a mentor."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    mentor = get_object_or_404(HostMentor, pk=mentor_pk, host=host)
    
    if request.method == 'POST':
        mentor.status = 'INACTIVE'
        mentor.is_active = False
        mentor.save()
        
        if mentor.user:
            mentor.user.is_active = False
            mentor.user.save()
        
        messages.success(request, f"{mentor.full_name} has been deactivated.")
        return redirect('corporate:mentor_list', host_employer_pk=host.pk)
    
    return redirect('corporate:mentor_detail', host_employer_pk=host.pk, mentor_pk=mentor.pk)


# =============================================================================
# PLACEMENT INVOICE VIEWS
# =============================================================================

@login_required
def invoice_list(request, host_employer_pk):
    """List all invoices for placements at a host employer."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    invoices = PlacementInvoice.objects.filter(
        placement__host=host
    ).select_related('placement__learner', 'approved_by', 'rejected_by')
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)
    
    context = {
        'host': host,
        'invoices': invoices,
        'status_filter': status,
    }
    return render(request, 'corporate/workplace/invoice_list.html', context)


@login_required
def invoice_create(request, host_employer_pk, placement_pk):
    """Create a new invoice for a placement."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    placement = get_object_or_404(WorkplacePlacement, pk=placement_pk, host=host)
    
    if request.method == 'POST':
        invoice_number = request.POST.get('invoice_number')
        invoice_file = request.FILES.get('invoice_file')
        amount = request.POST.get('amount')
        invoice_date = request.POST.get('invoice_date')
        due_date = request.POST.get('due_date')
        description = request.POST.get('description', '')
        
        if not all([invoice_number, invoice_file, amount, invoice_date]):
            messages.error(request, "Invoice number, file, amount, and date are required.")
            return redirect('corporate:invoice_create', host_employer_pk=host.pk, placement_pk=placement.pk)
        
        invoice = PlacementInvoice.objects.create(
            placement=placement,
            invoice_number=invoice_number,
            invoice_file=invoice_file,
            amount=amount,
            invoice_date=invoice_date,
            due_date=due_date or None,
            description=description,
            status='PENDING'
        )
        
        messages.success(request, f"Invoice {invoice_number} created successfully.")
        return redirect('corporate:invoice_list', host_employer_pk=host.pk)
    
    context = {
        'host': host,
        'placement': placement,
    }
    return render(request, 'corporate/workplace/invoice_form.html', context)


@login_required
def invoice_detail(request, host_employer_pk, invoice_pk):
    """View invoice details."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    invoice = get_object_or_404(PlacementInvoice, pk=invoice_pk, placement__host=host)
    
    context = {
        'host': host,
        'invoice': invoice,
    }
    return render(request, 'corporate/workplace/invoice_detail.html', context)


@login_required
def invoice_approve(request, host_employer_pk, invoice_pk):
    """Approve an invoice. Admin can approve on behalf of client with screenshot."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    invoice = get_object_or_404(PlacementInvoice, pk=invoice_pk, placement__host=host)
    
    if invoice.status != 'PENDING':
        messages.error(request, "Only pending invoices can be approved.")
        return redirect('corporate:invoice_detail', host_employer_pk=host.pk, invoice_pk=invoice.pk)
    
    if request.method == 'POST':
        approval_method = request.POST.get('approval_method', 'CLIENT')
        screenshot = request.FILES.get('approval_screenshot')
        
        try:
            invoice.approve(
                user=request.user,
                method=approval_method,
                screenshot=screenshot
            )
            messages.success(request, f"Invoice {invoice.invoice_number} has been approved.")
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('corporate:invoice_approve', host_employer_pk=host.pk, invoice_pk=invoice.pk)
        
        return redirect('corporate:invoice_detail', host_employer_pk=host.pk, invoice_pk=invoice.pk)
    
    context = {
        'host': host,
        'invoice': invoice,
    }
    return render(request, 'corporate/workplace/invoice_approve.html', context)


@login_required
def invoice_reject(request, host_employer_pk, invoice_pk):
    """Reject an invoice with a reason."""
    host = get_object_or_404(HostEmployer, pk=host_employer_pk)
    invoice = get_object_or_404(PlacementInvoice, pk=invoice_pk, placement__host=host)
    
    if invoice.status != 'PENDING':
        messages.error(request, "Only pending invoices can be rejected.")
        return redirect('corporate:invoice_detail', host_employer_pk=host.pk, invoice_pk=invoice.pk)
    
    if request.method == 'POST':
        reason = request.POST.get('rejection_reason', '')
        if not reason:
            messages.error(request, "A rejection reason is required.")
            return redirect('corporate:invoice_reject', host_employer_pk=host.pk, invoice_pk=invoice.pk)
        
        invoice.reject(user=request.user, reason=reason)
        messages.success(request, f"Invoice {invoice.invoice_number} has been rejected.")
        return redirect('corporate:invoice_detail', host_employer_pk=host.pk, invoice_pk=invoice.pk)
    
    context = {
        'host': host,
        'invoice': invoice,
    }
    return render(request, 'corporate/workplace/invoice_reject.html', context)


# =============================================================================
# PUBLIC MENTOR REGISTRATION VIEW (No Login Required)
# =============================================================================

from django.views.generic import FormView
from django.contrib.auth.hashers import make_password


def mentor_registration(request, token):
    """
    Public view for mentor to complete registration.
    Validates token, allows mentor to fill profile and create password.
    Creates User (inactive) and HostMentor (pending) linked together.
    """
    try:
        invitation = MentorInvitation.objects.select_related('host').get(token=token)
    except MentorInvitation.DoesNotExist:
        return render(request, 'corporate/workplace/mentor_registration_invalid.html', {
            'error': 'Invalid invitation link.'
        })
    
    if not invitation.is_valid:
        if invitation.status == 'ACCEPTED':
            return render(request, 'corporate/workplace/mentor_registration_invalid.html', {
                'error': 'This invitation has already been used.'
            })
        elif invitation.status == 'CANCELLED':
            return render(request, 'corporate/workplace/mentor_registration_invalid.html', {
                'error': 'This invitation has been cancelled.'
            })
        else:
            return render(request, 'corporate/workplace/mentor_registration_invalid.html', {
                'error': 'This invitation has expired. Please contact HR for a new invitation.'
            })
    
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name', invitation.first_name)
        last_name = request.POST.get('last_name', invitation.last_name)
        email = invitation.email  # Email is fixed from invitation
        phone = request.POST.get('phone', '')
        id_number = request.POST.get('id_number', '')
        job_title = request.POST.get('job_title', '')
        department = request.POST.get('department', '')
        years_experience = request.POST.get('years_experience')
        trade = request.POST.get('trade', '')
        trade_certificate_number = request.POST.get('trade_certificate_number', '')
        
        # Password fields
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        
        # Document uploads
        cv_document = request.FILES.get('cv_document')
        red_seal_certificate = request.FILES.get('red_seal_certificate')
        id_copy = request.FILES.get('id_copy')
        
        # Validation
        errors = []
        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if not phone:
            errors.append("Phone number is required.")
        if not job_title:
            errors.append("Job title is required.")
        if not password:
            errors.append("Password is required.")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        elif password != password_confirm:
            errors.append("Passwords do not match.")
        
        # Check if email already has a user account
        if User.objects.filter(email=email).exists():
            errors.append("An account with this email already exists. Please contact HR.")
        
        if errors:
            context = {
                'invitation': invitation,
                'errors': errors,
                'form_data': request.POST,
            }
            return render(request, 'corporate/workplace/mentor_registration.html', context)
        
        # Create User account (inactive until approved)
        user = User.objects.create(
            email=email,
            username=email,
            first_name=first_name,
            last_name=last_name,
            password=make_password(password),
            is_active=False  # Will be activated when mentor is approved
        )
        
        # Create HostMentor profile
        mentor = HostMentor.objects.create(
            host=invitation.host,
            user=user,
            status='PENDING',
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            id_number=id_number,
            job_title=job_title,
            department=department,
            years_experience=int(years_experience) if years_experience else None,
            trade=trade,
            trade_certificate_number=trade_certificate_number,
        )
        
        # Handle document uploads
        if cv_document:
            mentor.cv_document = cv_document
            mentor.cv_uploaded_at = timezone.now()
        if red_seal_certificate:
            mentor.red_seal_certificate = red_seal_certificate
            mentor.red_seal_uploaded_at = timezone.now()
        if id_copy:
            mentor.id_copy = id_copy
            mentor.id_copy_uploaded_at = timezone.now()
        
        mentor.save()
        
        # Mark invitation as accepted
        invitation.mark_accepted(mentor)
        
        return render(request, 'corporate/workplace/mentor_registration_success.html', {
            'mentor': mentor,
            'host': invitation.host,
        })
    
    context = {
        'invitation': invitation,
        'form_data': {
            'first_name': invitation.first_name,
            'last_name': invitation.last_name,
        },
    }
    return render(request, 'corporate/workplace/mentor_registration.html', context)


# =============================================================================
# TASK MANAGEMENT (Deliverable Management for Account Managers/Service Admins)
# =============================================================================

@login_required
def add_milestone_task(request, milestone_pk):
    """Add a task to a project milestone."""
    milestone = get_object_or_404(ProjectMilestone, pk=milestone_pk)
    project = milestone.project
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        priority = request.POST.get('priority', 'MEDIUM')
        due_date = request.POST.get('due_date') or None
        assigned_to_id = request.POST.get('assigned_to')
        estimated_hours = request.POST.get('estimated_hours') or None
        client_visible = request.POST.get('client_visible') == 'on'
        requires_evidence = request.POST.get('requires_evidence') == 'on'
        
        if not title:
            messages.error(request, "Task title is required.")
            return redirect('corporate:delivery_project_detail', pk=project.pk)
        
        assigned_to = None
        if assigned_to_id:
            assigned_to = User.objects.filter(pk=assigned_to_id).first()
        
        from .models import MilestoneTask
        task = MilestoneTask.objects.create(
            milestone=milestone,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            assigned_to=assigned_to,
            estimated_hours=estimated_hours,
            client_visible=client_visible,
            requires_evidence=requires_evidence,
            status='TODO'
        )
        
        messages.success(request, f"Task '{title}' added to milestone '{milestone.name}'.")
    
    return redirect('corporate:delivery_project_detail', pk=project.pk)


@login_required
def edit_task(request, pk):
    """Edit an existing task."""
    task = get_object_or_404(MilestoneTask, pk=pk)
    project = task.milestone.project
    
    if request.method == 'POST':
        task.title = request.POST.get('title', task.title).strip()
        task.description = request.POST.get('description', '').strip()
        task.priority = request.POST.get('priority', task.priority)
        task.due_date = request.POST.get('due_date') or None
        task.estimated_hours = request.POST.get('estimated_hours') or None
        task.client_visible = request.POST.get('client_visible') == 'on'
        task.requires_evidence = request.POST.get('requires_evidence') == 'on'
        
        assigned_to_id = request.POST.get('assigned_to')
        if assigned_to_id:
            task.assigned_to = User.objects.filter(pk=assigned_to_id).first()
        else:
            task.assigned_to = None
        
        task.save()
        messages.success(request, f"Task '{task.title}' updated.")
    
    return redirect('corporate:delivery_project_detail', pk=project.pk)


@login_required
def delete_task(request, pk):
    """Delete a task."""
    task = get_object_or_404(MilestoneTask, pk=pk)
    project = task.milestone.project
    task_title = task.title
    
    if request.method == 'POST':
        task.delete()
        messages.success(request, f"Task '{task_title}' deleted.")
    
    return redirect('corporate:delivery_project_detail', pk=project.pk)


@login_required
def update_task_status(request, pk):
    """Update task status (quick status change)."""
    task = get_object_or_404(MilestoneTask, pk=pk)
    project = task.milestone.project
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [choice[0] for choice in MilestoneTask.STATUS_CHOICES]
        
        if new_status in valid_statuses:
            old_status = task.status
            task.status = new_status
            
            # Set completion tracking
            if new_status == 'DONE' and old_status != 'DONE':
                task.completed_date = timezone.now().date()
                task.completed_by = request.user
                task.completion_notes = request.POST.get('completion_notes', '')
            elif new_status != 'DONE':
                # Clear completion data if reverting from DONE
                task.completed_date = None
                task.completed_by = None
                task.completed_by_contact = None
            
            task.save()
            messages.success(request, f"Task '{task.title}' updated to {task.get_status_display()}.")
    
    return redirect('corporate:delivery_project_detail', pk=project.pk)


@login_required
def add_task_evidence(request, pk):
    """Add evidence file to a task."""
    task = get_object_or_404(MilestoneTask, pk=pk)
    project = task.milestone.project
    
    if request.method == 'POST':
        from .models import TaskEvidence
        
        name = request.POST.get('evidence_name', '').strip()
        description = request.POST.get('evidence_description', '').strip()
        file = request.FILES.get('evidence_file')
        
        if not file:
            messages.error(request, "Please select a file to upload.")
            return redirect('corporate:delivery_project_detail', pk=project.pk)
        
        if not name:
            # Use filename as name if not provided
            name = file.name
        
        try:
            evidence = TaskEvidence(
                task=task,
                name=name,
                description=description,
                file=file,
                uploaded_by=request.user
            )
            evidence.full_clean()  # Validate including file extension
            evidence.save()
            messages.success(request, f"Evidence '{name}' uploaded successfully.")
        except Exception as e:
            messages.error(request, f"Error uploading file: {str(e)}")
    
    return redirect('corporate:delivery_project_detail', pk=project.pk)


@login_required
def delete_task_evidence(request, pk):
    """Delete task evidence file."""
    from .models import TaskEvidence
    evidence = get_object_or_404(TaskEvidence, pk=pk)
    project = evidence.task.milestone.project
    evidence_name = evidence.name
    
    if request.method == 'POST':
        evidence.delete()
        messages.success(request, f"Evidence '{evidence_name}' deleted.")
    
    return redirect('corporate:delivery_project_detail', pk=project.pk)


# =============================================================================
# EMPLOYMENT EQUITY (EE) VIEWS
# =============================================================================

@login_required
def ee_clients_dashboard(request):
    """
    Dashboard showing all clients with EE Consulting subscriptions and their progress.
    Helps administrators track all EE work across all clients.
    Supports filtering by SETA, consultant, and status.
    """
    # Determine current EE reporting year (Oct-Sept cycle)
    today = timezone.now().date()
    # EE year is named by the end year of the cycle
    # If we're in Oct-Dec 2024, reporting year is 2025 (Oct 2024-Sept 2025)
    # If we're in Jan-Sept 2025, reporting year is 2025 (Oct 2024-Sept 2025)
    if today.month >= 10:
        current_ee_year = today.year + 1
    else:
        current_ee_year = today.year
    
    # Get filter parameters
    selected_seta = request.GET.get('seta', '')
    selected_consultant = request.GET.get('consultant', '')
    selected_status = request.GET.get('status', '')
    
    # Base queryset for EE Consulting subscriptions
    ee_subscriptions = ClientServiceSubscription.objects.filter(
        service__service_type='EE_CONSULTING',
        status='ACTIVE'
    ).select_related('client', 'client__seta', 'service', 'assigned_consultant').order_by('client__company_name')
    
    # Apply SETA filter
    if selected_seta:
        ee_subscriptions = ee_subscriptions.filter(client__seta_id=selected_seta)
    
    # Apply consultant filter
    if selected_consultant:
        ee_subscriptions = ee_subscriptions.filter(assigned_consultant_id=selected_consultant)
    
    # Build client data with progress info
    clients_data = []
    for sub in ee_subscriptions:
        client = sub.client
        
        # Get EE service year for current reporting year
        ee_service_year = EEServiceYear.objects.filter(
            client=client,
            reporting_year=current_ee_year
        ).first()
        
        # Get committee info (for EE or combined committee)
        committee = TrainingCommittee.objects.filter(
            client=client,
            is_ee_committee=True
        ).prefetch_related('members').first()
        
        # If no dedicated EE committee, check for combined committee
        if not committee:
            committee = TrainingCommittee.objects.filter(
                client=client,
                committee_function='COMBINED'
            ).prefetch_related('members').first()
        
        committee_members = 0
        if committee:
            committee_members = committee.members.filter(is_active=True, participates_in_ee=True).count()
        
        # Get next EE meeting
        next_meeting = None
        if committee:
            next_meeting = TrainingCommitteeMeeting.objects.filter(
                committee=committee,
                scheduled_date__gte=today,
                meeting_purpose__in=['EE', 'COMBINED']
            ).order_by('scheduled_date').first()
        
        # Determine overall status/health
        health = 'grey'  # Not started
        if ee_service_year:
            if ee_service_year.status in ['COMPLETED', 'ACCEPTED']:
                health = 'green'
            elif ee_service_year.status == 'SUBMITTED':
                health = 'blue'
            elif ee_service_year.status in ['DATA_COLLECTION', 'DRAFTING', 'INTERNAL_REVIEW', 'CLIENT_REVIEW']:
                health = 'yellow'
            elif ee_service_year.is_overdue:
                health = 'red'
            else:
                health = 'yellow'
        
        # Get EE plan status
        active_plan = EEPlan.objects.filter(
            client=client,
            status='ACTIVE',
            start_date__lte=today,
            end_date__gte=today
        ).first()
        
        plan_status = 'No Active Plan'
        if active_plan:
            # Check if plan is expiring soon (within 6 months)
            months_remaining = (active_plan.end_date - today).days / 30
            if months_remaining <= 6:
                plan_status = f'Expiring ({active_plan.end_date.strftime("%b %Y")})'
            else:
                plan_status = f'Valid until {active_plan.end_date.strftime("%b %Y")}'
        
        clients_data.append({
            'client': client,
            'subscription': sub,
            'ee_service_year': ee_service_year,
            'committee': committee,
            'committee_members': committee_members,
            'next_meeting': next_meeting,
            'health': health,
            'progress': ee_service_year.progress_percentage if ee_service_year else 0,
            'active_plan': active_plan,
            'plan_status': plan_status,
            'consultant': sub.assigned_consultant,
        })
    
    # Apply status filter after building data
    if selected_status:
        status_map = {
            'completed': 'green',
            'submitted': 'blue',
            'in_progress': 'yellow',
            'overdue': 'red',
            'not_started': 'grey',
        }
        filter_health = status_map.get(selected_status, '')
        if filter_health:
            clients_data = [c for c in clients_data if c['health'] == filter_health]
    
    # Calculate summary stats
    total_clients = len(clients_data)
    completed = sum(1 for c in clients_data if c['health'] == 'green')
    submitted = sum(1 for c in clients_data if c['health'] == 'blue')
    in_progress = sum(1 for c in clients_data if c['health'] == 'yellow')
    overdue = sum(1 for c in clients_data if c['health'] == 'red')
    not_started = sum(1 for c in clients_data if c['health'] == 'grey')
    
    # Get upcoming EE meetings across all clients
    meeting_filter = {
        'scheduled_date__gte': today,
        'scheduled_date__lte': today + timezone.timedelta(days=30),
        'meeting_purpose__in': ['EE', 'COMBINED']
    }
    if selected_seta:
        meeting_filter['committee__client__seta_id'] = selected_seta
    
    upcoming_meetings = TrainingCommitteeMeeting.objects.filter(
        **meeting_filter
    ).select_related('committee__client').order_by('scheduled_date')[:10]
    
    # Get upcoming EE submission deadlines
    upcoming_deadlines = EEServiceYear.objects.filter(
        reporting_year=current_ee_year,
        status__in=['NOT_STARTED', 'DATA_COLLECTION', 'DRAFTING', 'INTERNAL_REVIEW', 'CLIENT_REVIEW'],
        submission_deadline__gte=today,
        submission_deadline__lte=today + timezone.timedelta(days=60)
    ).select_related('client').order_by('submission_deadline')[:10]
    
    # Get available filters
    setas = SETA.objects.filter(
        corporate_clients__service_subscriptions__service__service_type='EE_CONSULTING',
        corporate_clients__service_subscriptions__status='ACTIVE'
    ).distinct().order_by('name')
    
    consultants = User.objects.filter(
        assigned_service_subscriptions__service__service_type='EE_CONSULTING',
        assigned_service_subscriptions__status='ACTIVE'
    ).distinct().order_by('first_name', 'last_name')
    
    context = {
        'clients_data': clients_data,
        'current_ee_year': current_ee_year,
        'total_clients': total_clients,
        'completed': completed,
        'submitted': submitted,
        'in_progress': in_progress,
        'overdue': overdue,
        'not_started': not_started,
        'upcoming_meetings': upcoming_meetings,
        'upcoming_deadlines': upcoming_deadlines,
        # Filters
        'setas': setas,
        'consultants': consultants,
        'selected_seta': selected_seta,
        'selected_consultant': selected_consultant,
        'selected_status': selected_status,
    }
    
    return render(request, 'corporate/ee_clients_dashboard.html', context)


@login_required
def ee_service_management(request, client_pk):
    """
    Unified EE service management view.
    Handles all Employment Equity service delivery from one place.
    Auto-creates current reporting year's service record if none exists.
    """
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    # Determine current EE reporting year (Oct-Sep cycle)
    # Jan 2026 = reporting year 2026 (Oct 2025 - Sep 2026, deadline Jan 2026)
    today = timezone.now().date()
    if today.month >= 10:
        current_ee_year = today.year + 1
    else:
        current_ee_year = today.year
    
    # Get campus with fallback
    from tenants.models import Campus
    campus = client.campus or Campus.objects.first()
    
    # Get the EE Consulting subscription (optional - for billing tracking)
    subscription = ClientServiceSubscription.objects.filter(
        client=client,
        service__service_type='EE_CONSULTING',
        status='ACTIVE'
    ).select_related('service').first()
    
    # Auto-create current year's service record if it doesn't exist
    current_year_record, created = EEServiceYear.objects.get_or_create(
        client=client,
        reporting_year=current_ee_year,
        defaults={
            'subscription': subscription,
            'campus': campus,
            'status': 'NOT_STARTED',
            'assigned_consultant': request.user if request.user.is_staff else None,
        }
    )
    if created:
        messages.success(request, f"EE Service Year {current_ee_year} automatically created.")
    
    # Get EE Committee or Combined Committee
    committee = TrainingCommittee.objects.filter(
        client=client,
        is_ee_committee=True
    ).prefetch_related(
        Prefetch('members', queryset=TrainingCommitteeMember.objects.filter(participates_in_ee=True).select_related('contact'))
    ).first()
    
    if not committee:
        committee = TrainingCommittee.objects.filter(
            client=client,
            committee_function='COMBINED'
        ).prefetch_related(
            Prefetch('members', queryset=TrainingCommitteeMember.objects.filter(participates_in_ee=True).select_related('contact'))
        ).first()
    
    # Get EE Service Years
    ee_service_years = EEServiceYear.objects.filter(client=client).order_by('-reporting_year')
    
    # Determine which year to display
    selected_year = request.GET.get('year')
    if selected_year and selected_year.isdigit():
        current_service_year = ee_service_years.filter(reporting_year=int(selected_year)).first()
    else:
        # Use the auto-created/fetched current year
        current_service_year = current_year_record
    
    # Get EE Plan information
    active_plan = EEPlan.objects.filter(
        client=client,
        status='ACTIVE',
        start_date__lte=today,
        end_date__gte=today
    ).first()
    
    all_plans = EEPlan.objects.filter(client=client).order_by('-start_date')
    
    # Get EE meetings (for committee with EE purpose)
    meetings = []
    if committee and current_service_year:
        meetings = TrainingCommitteeMeeting.objects.filter(
            committee=committee,
            meeting_purpose__in=['EE', 'COMBINED'],
            ee_service_year=current_service_year
        ).order_by('scheduled_date')
    
    upcoming_meetings = [m for m in meetings if m.scheduled_date >= today]
    past_meetings = [m for m in meetings if m.scheduled_date < today]
    
    # Get workforce analysis (from snapshots)
    workforce_data = None
    if current_service_year and current_service_year.employee_snapshot:
        snapshot = current_service_year.employee_snapshot
        workforce_data = {
            'snapshot': snapshot,
            'occupational_data': snapshot.occupational_data.all().order_by('occupational_level'),
            'snapshot_date': snapshot.snapshot_date,
            'total_employees': snapshot.total_employees,
        }
    
    # Get EE Analysis for current year
    ee_analysis = None
    if current_service_year:
        ee_analysis = EEAnalysis.objects.filter(service_year=current_service_year).first()
    
    # Get barriers
    barriers = []
    if ee_analysis:
        barriers = EEBarrier.objects.filter(analysis=ee_analysis).order_by('barrier_category', 'priority')
    
    # Get numerical goals
    numerical_goals = []
    if current_service_year and current_service_year.ee_plan:
        numerical_goals = EENumericalGoal.objects.filter(
            ee_plan=current_service_year.ee_plan
        ).order_by('occupational_level')
    
    # Get income differentials
    income_differentials = []
    if current_service_year:
        income_differentials = EEIncomeDifferential.objects.filter(
            service_year=current_service_year
        ).order_by('occupational_level')
    
    # Get EE documents
    documents = []
    if current_service_year:
        documents = EEDocument.objects.filter(service_year=current_service_year).order_by('document_type')
    
    # Categorize documents
    workforce_docs = [d for d in documents if d.document_type in ['WORKFORCE_PROFILE', 'EAP_DATA']]
    plan_docs = [d for d in documents if d.document_type in ['EE_PLAN', 'ANALYSIS_REPORT']]
    submission_docs = [d for d in documents if d.document_type in ['EEA2_FORM', 'EEA4_FORM', 'SUBMISSION_RECEIPT']]
    committee_docs = [d for d in documents if d.document_type in ['COMMITTEE_MINUTES', 'COMMITTEE_ATTENDANCE']]
    other_docs = [d for d in documents if d.document_type not in [
        'WORKFORCE_PROFILE', 'EAP_DATA', 'EE_PLAN', 'ANALYSIS_REPORT',
        'EEA2_FORM', 'EEA4_FORM', 'SUBMISSION_RECEIPT', 'COMMITTEE_MINUTES', 'COMMITTEE_ATTENDANCE'
    ]]
    
    # Calculate section progress
    def calc_section_progress(docs):
        if not docs:
            return 0
        required = [d for d in docs if d.is_required]
        if not required:
            return 100
        uploaded = [d for d in required if d.file]
        return int((len(uploaded) / len(required)) * 100)
    
    section_progress = {
        'workforce': calc_section_progress(workforce_docs),
        'plan': calc_section_progress(plan_docs),
        'submission': calc_section_progress(submission_docs),
        'committee': calc_section_progress(committee_docs),
    }
    
    # Calculate statistics
    stats = {
        'total_employees': workforce_data['total_employees'] if workforce_data else 0,
        'barriers_count': len(barriers),
        'goals_count': len(numerical_goals),
        'upcoming_meetings_count': len(upcoming_meetings),
        'committee_members': committee.members.filter(is_active=True, participates_in_ee=True).count() if committee else 0,
    }
    
    # Get available consultants
    available_consultants = User.objects.filter(is_staff=True, is_active=True).order_by('first_name', 'last_name')
    
    context = {
        'client': client,
        'subscription': subscription,
        'committee': committee,
        'ee_service_years': ee_service_years,
        'current_service_year': current_service_year,
        'active_plan': active_plan,
        'all_plans': all_plans,
        'upcoming_meetings': upcoming_meetings,
        'past_meetings': past_meetings,
        'workforce_data': workforce_data,
        'ee_analysis': ee_analysis,
        'barriers': barriers,
        'numerical_goals': numerical_goals,
        'income_differentials': income_differentials,
        'workforce_docs': workforce_docs,
        'plan_docs': plan_docs,
        'submission_docs': submission_docs,
        'committee_docs': committee_docs,
        'other_docs': other_docs,
        'section_progress': section_progress,
        'stats': stats,
        'available_consultants': available_consultants,
        'doc_types': EEDocument.DOCUMENT_TYPE_CHOICES if hasattr(EEDocument, 'DOCUMENT_TYPE_CHOICES') else [],
    }
    
    return render(request, 'corporate/ee_service_management.html', context)


@login_required
def ee_workforce_profile(request, client_pk, year_pk):
    """
    Detailed workforce profile view for EE reporting.
    Shows demographic breakdown by occupational level.
    """
    client = get_object_or_404(CorporateClient, pk=client_pk)
    ee_service_year = get_object_or_404(EEServiceYear, pk=year_pk, client=client)
    
    # Get workforce snapshot
    snapshot = ee_service_year.employee_snapshot
    occupational_data = []
    
    if snapshot:
        occupational_data = snapshot.occupational_data.all().order_by('occupational_level')
    
    # Get available snapshots for comparison
    available_snapshots = ClientEmployeeSnapshot.objects.filter(
        client=client
    ).order_by('-snapshot_date')[:10]
    
    # Calculate totals
    totals = {
        'african_male': 0, 'african_female': 0,
        'coloured_male': 0, 'coloured_female': 0,
        'indian_male': 0, 'indian_female': 0,
        'white_male': 0, 'white_female': 0,
        'foreign_male': 0, 'foreign_female': 0,
        'total': 0
    }
    
    for data in occupational_data:
        totals['african_male'] += data.african_male
        totals['african_female'] += data.african_female
        totals['coloured_male'] += data.coloured_male
        totals['coloured_female'] += data.coloured_female
        totals['indian_male'] += data.indian_male
        totals['indian_female'] += data.indian_female
        totals['white_male'] += data.white_male
        totals['white_female'] += data.white_female
        totals['foreign_male'] += data.foreign_male
        totals['foreign_female'] += data.foreign_female
        totals['total'] += data.total_employees
    
    # Calculate designated group percentages
    designated_total = (
        totals['african_male'] + totals['african_female'] +
        totals['coloured_male'] + totals['coloured_female'] +
        totals['indian_male'] + totals['indian_female']
    )
    female_total = (
        totals['african_female'] + totals['coloured_female'] +
        totals['indian_female'] + totals['white_female'] +
        totals['foreign_female']
    )
    
    percentages = {
        'designated': round((designated_total / totals['total']) * 100, 1) if totals['total'] > 0 else 0,
        'female': round((female_total / totals['total']) * 100, 1) if totals['total'] > 0 else 0,
    }
    
    context = {
        'client': client,
        'ee_service_year': ee_service_year,
        'snapshot': snapshot,
        'occupational_data': occupational_data,
        'available_snapshots': available_snapshots,
        'totals': totals,
        'percentages': percentages,
    }
    
    return render(request, 'corporate/ee_workforce_profile.html', context)


@login_required
def ee_numerical_goals(request, client_pk, year_pk):
    """
    Manage numerical goals for EE reporting.
    """
    client = get_object_or_404(CorporateClient, pk=client_pk)
    ee_service_year = get_object_or_404(EEServiceYear, pk=year_pk, client=client)
    
    # Get numerical goals grouped by occupational level (through the EE Plan)
    goals = []
    if ee_service_year.ee_plan:
        goals = EENumericalGoal.objects.filter(
            ee_plan=ee_service_year.ee_plan
        ).order_by('occupational_level')
    
    # Group goals by occupational level
    goals_by_level = {}
    for goal in goals:
        level = goal.get_occupational_level_display()
        if level not in goals_by_level:
            goals_by_level[level] = []
        goals_by_level[level].append(goal)
    
    # Get active EE plan for target ranges
    today = timezone.now().date()
    active_plan = EEPlan.objects.filter(
        client=client,
        status='ACTIVE',
        start_date__lte=today,
        end_date__gte=today
    ).first()
    
    # Calculate summary statistics
    total_targets = sum(g.total_target for g in goals) if goals else 0
    total_actual = sum(g.total_actual for g in goals) if goals else 0
    
    context = {
        'client': client,
        'ee_service_year': ee_service_year,
        'goals': goals,
        'goals_by_level': goals_by_level,
        'active_plan': active_plan,
        'total_targets': total_targets,
        'total_actual': total_actual,
        'total_goals': len(goals) if goals else 0,
        'occupational_levels': EENumericalGoal.OCCUPATIONAL_LEVEL_CHOICES if hasattr(EENumericalGoal, 'OCCUPATIONAL_LEVEL_CHOICES') else [],
    }
    
    return render(request, 'corporate/ee_numerical_goals.html', context)


@login_required
def ee_barriers_analysis(request, client_pk, year_pk):
    """
    View and manage barrier analysis for EE.
    """
    from tenants.models import Campus
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    ee_service_year = get_object_or_404(EEServiceYear, pk=year_pk, client=client)
    
    # Get campus for the analysis
    campus = client.campus if hasattr(client, 'campus') and client.campus else Campus.objects.first()
    
    # Get or create EE Analysis
    ee_analysis, created = EEAnalysis.objects.get_or_create(
        service_year=ee_service_year,
        defaults={
            'analysis_start_date': timezone.now().date(),
            'campus': campus
        }
    )
    
    # Get barriers grouped by category
    barriers = EEBarrier.objects.filter(service_year=ee_service_year).order_by('category', 'status')
    
    barriers_by_category = {}
    for barrier in barriers:
        category = barrier.get_category_display()
        if category not in barriers_by_category:
            barriers_by_category[category] = []
        barriers_by_category[category].append(barrier)
    
    # Calculate statistics
    total_barriers = barriers.count()
    high_priority = barriers.filter(status='IDENTIFIED').count()
    addressed = barriers.filter(status='ADDRESSED').count()
    in_progress = barriers.filter(status='IN_PROGRESS').count()
    
    context = {
        'client': client,
        'ee_service_year': ee_service_year,
        'ee_analysis': ee_analysis,
        'barriers': barriers,
        'barriers_by_category': barriers_by_category,
        'total_barriers': total_barriers,
        'high_priority': high_priority,
        'addressed': addressed,
        'in_progress': in_progress,
        'barrier_categories': EEBarrier.CATEGORY_CHOICES if hasattr(EEBarrier, 'CATEGORY_CHOICES') else [],
    }
    
    return render(request, 'corporate/ee_barriers_analysis.html', context)


@login_required
def ee_income_differential(request, client_pk, year_pk):
    """
    View and manage income differential analysis for EE.
    Required for EEA4 form submission.
    """
    client = get_object_or_404(CorporateClient, pk=client_pk)
    ee_service_year = get_object_or_404(EEServiceYear, pk=year_pk, client=client)
    
    # Get income differentials by occupational level
    differentials = EEIncomeDifferential.objects.filter(
        service_year=ee_service_year
    ).order_by('occupational_level')
    
    context = {
        'client': client,
        'ee_service_year': ee_service_year,
        'differentials': differentials,
        'total_levels': differentials.count(),
    }
    
    return render(request, 'corporate/ee_income_differential.html', context)


@login_required
def ee_documents(request, client_pk, year_pk):
    """
    View and manage EE documents for a service year.
    """
    client = get_object_or_404(CorporateClient, pk=client_pk)
    ee_service_year = get_object_or_404(EEServiceYear, pk=year_pk, client=client)
    
    # Get all documents
    documents = EEDocument.objects.filter(service_year=ee_service_year).order_by('document_type')
    
    # Calculate progress
    required_docs = documents.filter(is_required=True)
    uploaded_count = required_docs.exclude(file='').count()
    total_required = required_docs.count()
    doc_progress = int((uploaded_count / total_required) * 100) if total_required > 0 else 0
    
    context = {
        'client': client,
        'ee_service_year': ee_service_year,
        'documents': documents,
        'doc_progress': doc_progress,
        'uploaded_count': uploaded_count,
        'total_required': total_required,
        'document_types': EEDocument.DOCUMENT_TYPE_CHOICES if hasattr(EEDocument, 'DOCUMENT_TYPE_CHOICES') else [],
    }
    
    return render(request, 'corporate/ee_documents.html', context)


@login_required
def ee_upload_document(request, client_pk, year_pk):
    """Upload a document for an EE service year."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    ee_service_year = get_object_or_404(EEServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        doc_pk = request.POST.get('document_id')
        document_type = request.POST.get('document_type')
        meeting_id = request.POST.get('meeting_id')
        
        if doc_pk:
            # Update existing document
            document = get_object_or_404(EEDocument, pk=doc_pk, service_year=ee_service_year)
        else:
            # Create new document
            document = EEDocument(
                service_year=ee_service_year,
                document_type=document_type or 'OTHER',
                name=request.POST.get('name', ''),
                is_required=request.POST.get('is_required', 'true') == 'true',
                meeting_id=meeting_id if meeting_id else None
            )
        
        if 'file' in request.FILES:
            document.file = request.FILES['file']
            document.uploaded_by = request.user
            document.uploaded_at = timezone.now()
            document.status = 'UPLOADED'
        
        if request.POST.get('notes'):
            document.notes = request.POST.get('notes')
        
        document.save()
        
        # Update service year progress
        ee_service_year.update_progress()
        
        messages.success(request, f"Document '{document.display_name}' uploaded successfully.")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'document_id': document.id,
                'message': 'Document uploaded successfully'
            })
    
    return redirect('corporate:ee_documents', client_pk=client_pk, year_pk=year_pk)


@login_required
def ee_plan_management(request, client_pk):
    """
    View and manage EE Plans for a client.
    """
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    # Get all EE plans
    plans = EEPlan.objects.filter(client=client).order_by('-start_date')
    
    # Get active plan
    today = timezone.now().date()
    active_plan = plans.filter(
        status='ACTIVE',
        start_date__lte=today,
        end_date__gte=today
    ).first()
    
    # Determine if new plan is needed
    needs_new_plan = not active_plan
    
    context = {
        'client': client,
        'plans': plans,
        'active_plan': active_plan,
        'needs_new_plan': needs_new_plan,
    }
    
    return render(request, 'corporate/ee_plan_management.html', context)


@login_required
def ee_create_service_year(request, client_pk):
    """Create a new EE service year for a client."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    if request.method == 'POST':
        reporting_year = request.POST.get('reporting_year')
        
        if reporting_year:
            reporting_year = int(reporting_year)
            
            # Check if service year already exists
            existing = EEServiceYear.objects.filter(
                client=client,
                reporting_year=reporting_year
            ).exists()
            
            if existing:
                messages.error(request, f"EE Service Year {reporting_year} already exists for this client.")
            else:
                # Calculate submission deadline
                # Reporting year 2026 = Oct 2025 - Sept 2026, deadline Jan 15, 2027
                submission_deadline = date(reporting_year + 1, 1, 15)
                
                # Get EE subscription for this client
                subscription = ClientServiceSubscription.objects.filter(
                    client=client,
                    service__service_type='EE',
                    status='ACTIVE'
                ).first()
                
                # Get campus from client or fallback
                from tenants.models import Campus
                campus = client.campus or Campus.objects.first()
                
                ee_service_year = EEServiceYear.objects.create(
                    client=client,
                    campus=campus,
                    subscription=subscription,
                    reporting_year=reporting_year,
                    submission_deadline=submission_deadline,
                    status='NOT_STARTED'
                )
                
                messages.success(request, f"EE Service Year {reporting_year} created successfully.")
    
    return redirect('corporate:ee_service_management', client_pk=client_pk)


@login_required
def ee_create_plan(request, client_pk):
    """Create a new EE Plan for a client."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if start_date and end_date:
            from datetime import datetime
            start_date_parsed = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_parsed = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Calculate duration
            duration_years = (end_date_parsed - start_date_parsed).days // 365
            
            plan = EEPlan.objects.create(
                client=client,
                start_date=start_date_parsed,
                end_date=end_date_parsed,
                duration_years=duration_years,
                status='DRAFT',
                created_by=request.user
            )
            
            messages.success(request, f"EE Plan created successfully. Valid from {start_date_parsed} to {end_date_parsed}.")
    
    return redirect('corporate:ee_plan_management', client_pk=client_pk)


@login_required
def ee_add_barrier(request, client_pk, year_pk):
    """Add a barrier to the EE analysis."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    ee_service_year = get_object_or_404(EEServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        # Get or create analysis
        analysis, _ = EEAnalysis.objects.get_or_create(
            ee_service_year=ee_service_year,
            defaults={'analysis_date': timezone.now().date()}
        )
        
        barrier = EEBarrier.objects.create(
            analysis=analysis,
            barrier_category=request.POST.get('barrier_category', 'OTHER'),
            description=request.POST.get('description', ''),
            affected_group=request.POST.get('affected_group', ''),
            occupational_level=request.POST.get('occupational_level', ''),
            root_cause=request.POST.get('root_cause', ''),
            proposed_measure=request.POST.get('proposed_measure', ''),
            responsible_person=request.POST.get('responsible_person', ''),
            target_date=request.POST.get('target_date') or None,
            priority=request.POST.get('priority', 'MEDIUM'),
            status='IDENTIFIED',
            created_by=request.user
        )
        
        messages.success(request, "Barrier added successfully.")
    
    return redirect('corporate:ee_barriers_analysis', client_pk=client_pk, year_pk=year_pk)


@login_required
def ee_add_numerical_goal(request, client_pk, year_pk):
    """Add a numerical goal for EE."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    ee_service_year = get_object_or_404(EEServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        goal = EENumericalGoal.objects.create(
            ee_service_year=ee_service_year,
            occupational_level=request.POST.get('occupational_level'),
            designated_group=request.POST.get('designated_group'),
            current_count=int(request.POST.get('current_count', 0)),
            target_count=int(request.POST.get('target_count', 0)),
            target_year=int(request.POST.get('target_year', ee_service_year.reporting_year)),
            recruitment_target=int(request.POST.get('recruitment_target', 0)),
            promotion_target=int(request.POST.get('promotion_target', 0)),
            notes=request.POST.get('notes', ''),
            created_by=request.user
        )
        
        messages.success(request, "Numerical goal added successfully.")
    
    return redirect('corporate:ee_numerical_goals', client_pk=client_pk, year_pk=year_pk)


@login_required
def ee_add_income_differential(request, client_pk, year_pk):
    """Add income differential data for EE."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    ee_service_year = get_object_or_404(EEServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        from decimal import Decimal
        
        differential = EEIncomeDifferential.objects.create(
            ee_service_year=ee_service_year,
            occupational_level=request.POST.get('occupational_level'),
            job_category=request.POST.get('job_category', ''),
            male_employees=int(request.POST.get('male_employees', 0)),
            female_employees=int(request.POST.get('female_employees', 0)),
            avg_male_remuneration=Decimal(request.POST.get('avg_male_remuneration', '0')),
            avg_female_remuneration=Decimal(request.POST.get('avg_female_remuneration', '0')),
            differential_ratio=Decimal(request.POST.get('differential_ratio', '1.0')),
            is_justifiable=request.POST.get('is_justifiable') == 'true',
            justification=request.POST.get('justification', ''),
            remedial_action=request.POST.get('remedial_action', ''),
            created_by=request.user
        )
        
        messages.success(request, "Income differential added successfully.")
    
    return redirect('corporate:ee_income_differential', client_pk=client_pk, year_pk=year_pk)


@login_required
def ee_meeting_detail(request, client_pk, meeting_pk):
    """View and manage a specific EE Committee meeting."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    meeting = get_object_or_404(
        TrainingCommitteeMeeting.objects.select_related('committee', 'template', 'ee_service_year')
        .prefetch_related(
            'tc_agenda_items',
            Prefetch('tc_attendance_records', queryset=TCMeetingAttendance.objects.select_related('member__contact')),
            'tc_action_items',
        ),
        pk=meeting_pk,
        committee__client=client,
        meeting_purpose__in=['EE', 'COMBINED']
    )
    
    context = {
        'client': client,
        'meeting': meeting,
        'agenda_items': meeting.tc_agenda_items.order_by('order'),
        'attendance_records': meeting.tc_attendance_records.all(),
        'action_items': meeting.tc_action_items.order_by('-created_at'),
    }
    
    return render(request, 'corporate/ee_meeting_detail.html', context)


@login_required  
def ee_create_meeting(request, client_pk):
    """Create a new EE Committee meeting."""
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        scheduled_date = request.POST.get('scheduled_date')
        scheduled_time = request.POST.get('scheduled_time')
        location = request.POST.get('location', 'Online')
        meeting_type = request.POST.get('meeting_type', 'QUARTERLY')
        ee_service_year_id = request.POST.get('ee_service_year_id')
        template_id = request.POST.get('template_id')
        
        # Get or create EE committee
        committee = TrainingCommittee.objects.filter(
            client=client,
            is_ee_committee=True
        ).first()
        
        if not committee:
            committee = TrainingCommittee.objects.filter(
                client=client,
                committee_function='COMBINED'
            ).first()
        
        if not committee:
            # Create new EE committee
            committee = TrainingCommittee.objects.create(
                client=client,
                name=f"{client.company_name} EE Committee",
                committee_function='EE_ONLY',
                is_ee_committee=True,
                created_by=request.user
            )
        
        # Parse date and time
        from datetime import datetime
        meeting_date = datetime.strptime(scheduled_date, "%Y-%m-%d").date()
        meeting_time = datetime.strptime(scheduled_time, "%H:%M").time() if scheduled_time else None
        
        # Get template if specified
        template = None
        agenda_text = ''
        if template_id:
            template = MeetingTemplate.objects.filter(id=template_id, meeting_purpose__in=['EE', 'COMBINED']).first()
            if template:
                agenda_text = template.default_agenda
        
        # Get EE service year
        ee_service_year = None
        if ee_service_year_id:
            ee_service_year = EEServiceYear.objects.filter(id=ee_service_year_id, client=client).first()
        
        meeting = TrainingCommitteeMeeting.objects.create(
            committee=committee,
            title=title or f"EE Committee Meeting - {meeting_date.strftime('%B %Y')}",
            scheduled_date=meeting_date,
            scheduled_time=meeting_time,
            location=location,
            meeting_type=meeting_type,
            meeting_purpose='EE',
            ee_service_year=ee_service_year,
            template=template,
            agenda=agenda_text,
            status='SCHEDULED',
            created_by=request.user
        )
        
        messages.success(request, f"Meeting scheduled for {meeting_date.strftime('%d %B %Y')}.")
        return redirect('corporate:ee_meeting_detail', client_pk=client_pk, meeting_pk=meeting.pk)
    
    # GET request - show form
    ee_service_years = EEServiceYear.objects.filter(client=client).order_by('-reporting_year')
    templates = MeetingTemplate.objects.filter(is_active=True, meeting_purpose__in=['EE', 'COMBINED'])
    
    context = {
        'client': client,
        'ee_service_years': ee_service_years,
        'templates': templates,
    }
    
    return render(request, 'corporate/ee_create_meeting.html', context)


# =============================================================================
# B-BBEE SERVICE VIEWS
# =============================================================================

@login_required
def bbbee_clients_dashboard(request):
    """
    Dashboard showing all B-BBEE Consulting clients.
    Overview of B-BBEE service status across clients.
    """
    from .models import BBBEEServiceYear, BBBEEScorecard
    
    # Get all clients with active B-BBEE subscriptions
    bbbee_clients = CorporateClient.objects.filter(
        service_subscriptions__service__service_type='BEE_CONSULTING',
        service_subscriptions__status='ACTIVE'
    ).distinct().prefetch_related(
        'service_subscriptions',
        'bbbee_service_years'
    )
    
    # Calculate dashboard statistics
    today = timezone.now().date()
    
    # Get current financial year (assume most common is Feb year-end)
    if today.month >= 3:
        current_fy = today.year + 1
    else:
        current_fy = today.year
    
    # Service year statistics
    total_service_years = BBBEEServiceYear.objects.count()
    in_progress = BBBEEServiceYear.objects.filter(
        status__in=['DATA_COLLECTION', 'OWNERSHIP_ANALYSIS', 'MANAGEMENT_ANALYSIS',
                    'SKILLS_DEV_ANALYSIS', 'ESD_ANALYSIS', 'SED_ANALYSIS',
                    'INTERNAL_REVIEW', 'CLIENT_REVIEW']
    ).count()
    verification_pending = BBBEEServiceYear.objects.filter(
        status__in=['VERIFICATION_SCHEDULED', 'VERIFICATION_IN_PROGRESS']
    ).count()
    completed = BBBEEServiceYear.objects.filter(
        status__in=['VERIFIED', 'CERTIFICATE_ISSUED', 'COMPLETED']
    ).count()
    
    # Expiring certificates (within 60 days)
    from datetime import timedelta
    expiring_soon = BBBEEServiceYear.objects.filter(
        certificate_expiry_date__lte=today + timedelta(days=60),
        certificate_expiry_date__gte=today
    ).count()
    
    # Upcoming verification deadlines
    upcoming_deadlines = BBBEEServiceYear.objects.filter(
        target_verification_date__gte=today,
        target_verification_date__lte=today + timedelta(days=30),
        status__in=['DATA_COLLECTION', 'OWNERSHIP_ANALYSIS', 'MANAGEMENT_ANALYSIS',
                    'SKILLS_DEV_ANALYSIS', 'ESD_ANALYSIS', 'SED_ANALYSIS',
                    'INTERNAL_REVIEW', 'CLIENT_REVIEW']
    ).select_related('client').order_by('target_verification_date')[:10]
    
    # By enterprise type
    enterprise_counts = BBBEEServiceYear.objects.filter(
        financial_year=current_fy
    ).values('enterprise_type').annotate(count=Count('id'))
    
    # By B-BBEE level (from latest completed years)
    level_distribution = BBBEEServiceYear.objects.filter(
        status__in=['VERIFIED', 'CERTIFICATE_ISSUED', 'COMPLETED']
    ).values('outcome').annotate(count=Count('id'))
    
    context = {
        'clients': bbbee_clients,
        'total_clients': bbbee_clients.count(),
        'total_service_years': total_service_years,
        'in_progress': in_progress,
        'verification_pending': verification_pending,
        'completed': completed,
        'expiring_soon': expiring_soon,
        'upcoming_deadlines': upcoming_deadlines,
        'enterprise_counts': {ec['enterprise_type']: ec['count'] for ec in enterprise_counts},
        'level_distribution': {ld['outcome']: ld['count'] for ld in level_distribution},
        'current_fy': current_fy,
    }
    
    return render(request, 'corporate/bbbee_clients_dashboard.html', context)


@login_required
def bbbee_service_management(request, client_pk):
    """
    B-BBEE Service Management page for a specific client.
    Shows B-BBEE verification status, scorecard elements, and key information.
    Auto-creates current financial year's service record if none exists.
    """
    from .models import (
        BBBEEServiceYear, BBBEEDocument, BBBEEScorecard,
        OwnershipStructure, ManagementControlProfile, SkillsDevelopmentElement,
        ESDElement, SEDElement, TransformationPlan
    )
    from .services import BBBEESyncService
    from tenants.models import Campus
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    # Determine current financial year (based on client's year-end)
    today = timezone.now().date()
    year_end_month = getattr(client, 'financial_year_end_month', 2)
    
    if today.month > year_end_month:
        current_fy = today.year + 1
    else:
        current_fy = today.year
    
    # Get campus with fallback
    campus = client.campus or Campus.objects.first()
    
    # Get the B-BBEE Consulting subscription (optional - for billing tracking)
    subscription = ClientServiceSubscription.objects.filter(
        client=client,
        service__service_type='BEE_CONSULTING',
        status='ACTIVE'
    ).select_related('service').first()
    
    # Auto-create current year's service record if it doesn't exist
    current_year_record, created = BBBEEServiceYear.objects.get_or_create(
        client=client,
        financial_year=current_fy,
        defaults={
            'subscription': subscription,
            'campus': campus,
            'year_end_month': year_end_month,
            'status': 'NOT_STARTED',
        }
    )
    if created:
        messages.success(request, f"B-BBEE Service Year FY{current_fy} automatically created.")
    
    # Get B-BBEE Committee (or combined committee with B-BBEE function)
    committee = TrainingCommittee.objects.filter(
        client=client,
        is_bbbee_committee=True
    ).prefetch_related('members').first()
    
    if not committee:
        # Check for combined committees that include B-BBEE
        committee = TrainingCommittee.objects.filter(
            client=client,
            committee_function__in=['ALL', 'TRAINING_BBBEE', 'EE_BBBEE']
        ).prefetch_related('members').first()
    
    # Get B-BBEE Service Years
    bbbee_service_years = BBBEEServiceYear.objects.filter(
        client=client
    ).select_related(
        'scorecard', 'employee_snapshot', 'wspatr_service_year', 'ee_service_year'
    ).order_by('-financial_year')
    
    # Determine which year to display
    selected_year = request.GET.get('year')
    if selected_year and selected_year.isdigit():
        current_service_year = bbbee_service_years.filter(financial_year=int(selected_year)).first()
    else:
        # Use the auto-created/fetched current year
        current_service_year = current_year_record
    
    # Get enterprise type info
    enterprise_info = None
    if current_service_year:
        enterprise_info = BBBEESyncService.get_verification_requirements(
            current_service_year.enterprise_type
        )
    
    # Get scorecard element data
    ownership_data = None
    management_data = None
    skills_data = None
    esd_data = None
    sed_data = None
    
    if current_service_year:
        try:
            ownership_data = current_service_year.ownership_structure
        except OwnershipStructure.DoesNotExist:
            pass
        
        try:
            management_data = current_service_year.management_profile
        except ManagementControlProfile.DoesNotExist:
            pass
        
        try:
            skills_data = current_service_year.skills_development
        except SkillsDevelopmentElement.DoesNotExist:
            pass
        
        try:
            esd_data = current_service_year.esd_element
        except ESDElement.DoesNotExist:
            pass
        
        try:
            sed_data = current_service_year.sed_element
        except SEDElement.DoesNotExist:
            pass
    
    # Get documents
    documents = []
    if current_service_year:
        documents = BBBEEDocument.objects.filter(
            service_year=current_service_year
        ).order_by('document_type')
    
    # Categorize documents
    ownership_docs = [d for d in documents if d.document_type in [
        'SHARE_CERTIFICATES', 'SHAREHOLDERS_AGREEMENT', 'OWNERSHIP_PROOF'
    ]]
    management_docs = [d for d in documents if d.document_type in [
        'BOARD_COMPOSITION', 'EXEC_DEMOGRAPHICS', 'PAYROLL_SUMMARY', 'ORGANOGRAM'
    ]]
    skills_docs = [d for d in documents if d.document_type in [
        'SKILLS_DEV_SPEND', 'LEARNERSHIPS_PROOF'
    ]]
    esd_docs = [d for d in documents if d.document_type in [
        'ESD_CONTRIBUTIONS', 'PREFERENTIAL_PROCUREMENT', 'SUPPLIER_DECLARATIONS'
    ]]
    sed_docs = [d for d in documents if d.document_type in [
        'SED_CONTRIBUTIONS'
    ]]
    verification_docs = [d for d in documents if d.document_type in [
        'VERIFICATION_REPORT', 'BBBEE_CERTIFICATE', 'SWORN_AFFIDAVIT'
    ]]
    company_docs = [d for d in documents if d.document_type in [
        'CIPC_REGISTRATION', 'ANNUAL_FINANCIAL_STATEMENTS', 'MANAGEMENT_ACCOUNTS',
        'TAX_CLEARANCE', 'DIRECTORS_RESOLUTION'
    ]]
    
    # Get transformation plan
    transformation_plan = TransformationPlan.objects.filter(
        client=client,
        status__in=['DRAFT', 'ACTIVE']
    ).order_by('-start_date').first()
    
    # Get latest scorecard
    latest_scorecard = BBBEEScorecard.objects.filter(
        client=client
    ).order_by('-verification_date').first()
    
    # Calculate scores summary
    scores_summary = None
    if current_service_year:
        total_score = BBBEESyncService.calculate_total_score(current_service_year)
        level_info = BBBEESyncService.determine_level_from_score(
            total_score, 
            current_service_year.enterprise_type
        )
        scores_summary = {
            'ownership': ownership_data.calculated_score if ownership_data else 0,
            'management': management_data.calculated_score if management_data else 0,
            'skills': skills_data.calculated_score if skills_data else 0,
            'esd': esd_data.calculated_score if esd_data else 0,
            'sed': sed_data.calculated_score if sed_data else 0,
            'total': total_score,
            'projected_level': level_info[1],
            'recognition': level_info[2],
        }
    
    # Calculate section progress
    def calc_section_progress(docs):
        if not docs:
            return 0
        required = [d for d in docs if d.is_required]
        if not required:
            return 100
        uploaded = [d for d in required if d.file]
        return int((len(uploaded) / len(required)) * 100)
    
    section_progress = {
        'ownership': calc_section_progress(ownership_docs),
        'management': calc_section_progress(management_docs),
        'skills': calc_section_progress(skills_docs),
        'esd': calc_section_progress(esd_docs),
        'sed': calc_section_progress(sed_docs),
        'verification': calc_section_progress(verification_docs),
        'company': calc_section_progress(company_docs),
    }
    
    # Get available consultants
    available_consultants = User.objects.filter(is_staff=True, is_active=True).order_by('first_name', 'last_name')
    
    context = {
        'client': client,
        'subscription': subscription,
        'committee': committee,
        'bbbee_service_years': bbbee_service_years,
        'current_service_year': current_service_year,
        'enterprise_info': enterprise_info,
        'ownership_data': ownership_data,
        'management_data': management_data,
        'skills_data': skills_data,
        'esd_data': esd_data,
        'sed_data': sed_data,
        'ownership_docs': ownership_docs,
        'management_docs': management_docs,
        'skills_docs': skills_docs,
        'esd_docs': esd_docs,
        'sed_docs': sed_docs,
        'verification_docs': verification_docs,
        'company_docs': company_docs,
        'section_progress': section_progress,
        'transformation_plan': transformation_plan,
        'latest_scorecard': latest_scorecard,
        'scores_summary': scores_summary,
        'available_consultants': available_consultants,
        'doc_types': BBBEEDocument.DOCUMENT_TYPE_CHOICES,
    }
    
    return render(request, 'corporate/bbbee_service_management.html', context)


@login_required
def bbbee_create_service_year(request, client_pk):
    """
    Create a new B-BBEE service year for a client.
    """
    from .models import BBBEEServiceYear
    from .services import BBBEESyncService
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    if request.method == 'POST':
        financial_year = request.POST.get('financial_year')
        year_end_month = request.POST.get('year_end_month')
        annual_turnover = request.POST.get('annual_turnover')
        auto_link = request.POST.get('auto_link') == 'on'
        
        if not financial_year:
            messages.error(request, "Financial year is required.")
            return redirect('corporate:bbbee_service_management', client_pk=client_pk)
        
        # Get subscription
        subscription = ClientServiceSubscription.objects.filter(
            client=client,
            service__service_type='BEE_CONSULTING',
            status='ACTIVE'
        ).first()
        
        if not subscription:
            messages.error(request, "No active B-BBEE Consulting subscription found.")
            return redirect('corporate:bbbee_service_management', client_pk=client_pk)
        
        # Check for existing year
        existing = BBBEEServiceYear.objects.filter(
            client=client,
            financial_year=int(financial_year)
        ).exists()
        
        if existing:
            messages.error(request, f"A B-BBEE service year for FY{financial_year} already exists.")
            return redirect('corporate:bbbee_service_management', client_pk=client_pk)
        
        try:
            from decimal import Decimal
            turnover = Decimal(annual_turnover) if annual_turnover else None
            
            service_year = BBBEESyncService.create_bbbee_service_year(
                subscription=subscription,
                financial_year=int(financial_year),
                year_end_month=int(year_end_month) if year_end_month else None,
                auto_link=auto_link,
                auto_sync=auto_link
            )
            
            # Update turnover if provided
            if turnover:
                service_year.annual_turnover = turnover
                service_year.enterprise_type = BBBEESyncService.determine_enterprise_type(turnover)
                service_year.save(update_fields=['annual_turnover', 'enterprise_type'])
            
            # Create all element records
            BBBEESyncService.create_all_elements(service_year)
            
            messages.success(request, f"B-BBEE Service Year FY{financial_year} created successfully.")
        except Exception as e:
            messages.error(request, f"Error creating service year: {str(e)}")
        
        return redirect('corporate:bbbee_service_management', client_pk=client_pk)
    
    # GET request - redirect back
    return redirect('corporate:bbbee_service_management', client_pk=client_pk)


@login_required
def bbbee_ownership(request, client_pk, year_pk):
    """
    B-BBEE Ownership element detail view.
    """
    from .models import BBBEEServiceYear, OwnershipStructure, Shareholder
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(BBBEEServiceYear, pk=year_pk, client=client)
    
    # Get or create ownership structure
    ownership, created = OwnershipStructure.objects.get_or_create(
        service_year=service_year
    )
    
    shareholders = Shareholder.objects.filter(
        ownership_structure=ownership
    ).order_by('-voting_rights_percentage')
    
    context = {
        'client': client,
        'service_year': service_year,
        'ownership': ownership,
        'shareholders': shareholders,
    }
    
    return render(request, 'corporate/bbbee_ownership.html', context)


@login_required
def bbbee_management_control(request, client_pk, year_pk):
    """
    B-BBEE Management Control element detail view.
    """
    from .models import BBBEEServiceYear, ManagementControlProfile
    from .services import BBBEESyncService
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(BBBEEServiceYear, pk=year_pk, client=client)
    
    # Get or create management profile
    management, created = ManagementControlProfile.objects.get_or_create(
        service_year=service_year
    )
    
    # Check if we can sync from EE data
    can_sync = bool(service_year.employee_snapshot or 
                    (service_year.ee_service_year and service_year.ee_service_year.employee_snapshot))
    
    if request.method == 'POST' and request.POST.get('action') == 'sync':
        # Sync from employee snapshot
        BBBEESyncService.sync_management_control_from_snapshot(service_year)
        messages.success(request, "Management Control data synced from employee demographics.")
        return redirect('corporate:bbbee_management_control', client_pk=client_pk, year_pk=year_pk)
    
    context = {
        'client': client,
        'service_year': service_year,
        'management': management,
        'can_sync': can_sync,
        'linked_snapshot': service_year.employee_snapshot,
        'linked_ee_year': service_year.ee_service_year,
    }
    
    return render(request, 'corporate/bbbee_management_control.html', context)


@login_required
def bbbee_skills_development(request, client_pk, year_pk):
    """
    B-BBEE Skills Development element detail view.
    """
    from .models import BBBEEServiceYear, SkillsDevelopmentElement
    from .services import BBBEESyncService
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(BBBEEServiceYear, pk=year_pk, client=client)
    
    # Get or create skills development element
    skills, created = SkillsDevelopmentElement.objects.get_or_create(
        service_year=service_year
    )
    
    # Check if we can sync from WSP/ATR
    can_sync = bool(service_year.wspatr_service_year)
    
    if request.method == 'POST' and request.POST.get('action') == 'sync':
        # Sync from WSP/ATR
        BBBEESyncService.sync_skills_development_from_wspatr(service_year)
        messages.success(request, "Skills Development data synced from WSP/ATR.")
        return redirect('corporate:bbbee_skills_development', client_pk=client_pk, year_pk=year_pk)
    
    context = {
        'client': client,
        'service_year': service_year,
        'skills': skills,
        'can_sync': can_sync,
        'linked_wspatr_year': service_year.wspatr_service_year,
    }
    
    return render(request, 'corporate/bbbee_skills_development.html', context)


@login_required
def bbbee_esd(request, client_pk, year_pk):
    """
    B-BBEE Enterprise & Supplier Development element detail view.
    """
    from .models import BBBEEServiceYear, ESDElement, ESDSupplier
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(BBBEEServiceYear, pk=year_pk, client=client)
    
    # Get or create ESD element
    esd, created = ESDElement.objects.get_or_create(
        service_year=service_year
    )
    
    # Get suppliers by type
    preferential_suppliers = ESDSupplier.objects.filter(
        esd_element=esd,
        supplier_type='PREFERENTIAL'
    ).order_by('-annual_spend')
    
    supplier_dev_beneficiaries = ESDSupplier.objects.filter(
        esd_element=esd,
        supplier_type='SUPPLIER_DEV'
    ).order_by('supplier_name')
    
    enterprise_dev_beneficiaries = ESDSupplier.objects.filter(
        esd_element=esd,
        supplier_type='ENTERPRISE_DEV'
    ).order_by('supplier_name')
    
    context = {
        'client': client,
        'service_year': service_year,
        'esd': esd,
        'preferential_suppliers': preferential_suppliers,
        'supplier_dev_beneficiaries': supplier_dev_beneficiaries,
        'enterprise_dev_beneficiaries': enterprise_dev_beneficiaries,
    }
    
    return render(request, 'corporate/bbbee_esd.html', context)


@login_required
def bbbee_sed(request, client_pk, year_pk):
    """
    B-BBEE Socio-Economic Development element detail view.
    """
    from .models import BBBEEServiceYear, SEDElement, SEDContribution
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(BBBEEServiceYear, pk=year_pk, client=client)
    
    # Get or create SED element
    sed, created = SEDElement.objects.get_or_create(
        service_year=service_year
    )
    
    contributions = SEDContribution.objects.filter(
        sed_element=sed
    ).order_by('-contribution_date')
    
    context = {
        'client': client,
        'service_year': service_year,
        'sed': sed,
        'contributions': contributions,
    }
    
    return render(request, 'corporate/bbbee_sed.html', context)


@login_required
def bbbee_documents(request, client_pk, year_pk):
    """
    B-BBEE Documents management view.
    """
    from .models import BBBEEServiceYear, BBBEEDocument
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(BBBEEServiceYear, pk=year_pk, client=client)
    
    documents = BBBEEDocument.objects.filter(
        service_year=service_year
    ).order_by('document_type')
    
    # Group by category
    document_groups = {
        'Company Documents': [d for d in documents if d.document_type in [
            'CIPC_REGISTRATION', 'ANNUAL_FINANCIAL_STATEMENTS', 'MANAGEMENT_ACCOUNTS',
            'TAX_CLEARANCE', 'DIRECTORS_RESOLUTION', 'ORGANOGRAM'
        ]],
        'Ownership': [d for d in documents if d.document_type in [
            'SHARE_CERTIFICATES', 'SHAREHOLDERS_AGREEMENT', 'OWNERSHIP_PROOF'
        ]],
        'Management Control': [d for d in documents if d.document_type in [
            'BOARD_COMPOSITION', 'EXEC_DEMOGRAPHICS', 'PAYROLL_SUMMARY'
        ]],
        'Skills Development': [d for d in documents if d.document_type in [
            'SKILLS_DEV_SPEND', 'LEARNERSHIPS_PROOF'
        ]],
        'Enterprise & Supplier Development': [d for d in documents if d.document_type in [
            'ESD_CONTRIBUTIONS', 'PREFERENTIAL_PROCUREMENT', 'SUPPLIER_DECLARATIONS'
        ]],
        'Socio-Economic Development': [d for d in documents if d.document_type in [
            'SED_CONTRIBUTIONS'
        ]],
        'Verification': [d for d in documents if d.document_type in [
            'VERIFICATION_REPORT', 'BBBEE_CERTIFICATE', 'SWORN_AFFIDAVIT'
        ]],
        'Other': [d for d in documents if d.document_type in [
            'TRANSFORMATION_PLAN', 'OTHER'
        ]],
    }
    
    context = {
        'client': client,
        'service_year': service_year,
        'document_groups': document_groups,
        'doc_types': BBBEEDocument.DOCUMENT_TYPE_CHOICES,
    }
    
    return render(request, 'corporate/bbbee_documents.html', context)


@login_required
def bbbee_upload_document(request, client_pk, year_pk):
    """
    Upload a B-BBEE document.
    """
    from .models import BBBEEServiceYear, BBBEEDocument
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(BBBEEServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        document_type = request.POST.get('document_type')
        name = request.POST.get('name', '')
        description = request.POST.get('description', '')
        file = request.FILES.get('file')
        
        if not document_type:
            messages.error(request, "Document type is required.")
            return redirect('corporate:bbbee_documents', client_pk=client_pk, year_pk=year_pk)
        
        if not file:
            messages.error(request, "Please select a file to upload.")
            return redirect('corporate:bbbee_documents', client_pk=client_pk, year_pk=year_pk)
        
        # Create or update document
        document, created = BBBEEDocument.objects.update_or_create(
            service_year=service_year,
            document_type=document_type,
            defaults={
                'name': name,
                'description': description,
                'file': file,
                'file_name': file.name,
                'file_size': file.size,
                'status': 'UPLOADED',
                'uploaded_at': timezone.now(),
                'uploaded_by': request.user,
            }
        )
        
        messages.success(request, f"Document '{document.get_document_type_display()}' uploaded successfully.")
        return redirect('corporate:bbbee_documents', client_pk=client_pk, year_pk=year_pk)
    
    return redirect('corporate:bbbee_documents', client_pk=client_pk, year_pk=year_pk)


@login_required
def bbbee_scorecard_summary(request, client_pk, year_pk):
    """
    B-BBEE Scorecard summary view showing all element scores.
    """
    from .models import (
        BBBEEServiceYear, OwnershipStructure, ManagementControlProfile,
        SkillsDevelopmentElement, ESDElement, SEDElement
    )
    from .services import BBBEESyncService
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(BBBEEServiceYear, pk=year_pk, client=client)
    
    # Get all elements
    elements = {}
    try:
        elements['ownership'] = service_year.ownership_structure
    except OwnershipStructure.DoesNotExist:
        elements['ownership'] = None
    
    try:
        elements['management'] = service_year.management_profile
    except ManagementControlProfile.DoesNotExist:
        elements['management'] = None
    
    try:
        elements['skills'] = service_year.skills_development
    except SkillsDevelopmentElement.DoesNotExist:
        elements['skills'] = None
    
    try:
        elements['esd'] = service_year.esd_element
    except ESDElement.DoesNotExist:
        elements['esd'] = None
    
    try:
        elements['sed'] = service_year.sed_element
    except SEDElement.DoesNotExist:
        elements['sed'] = None
    
    # Calculate total and determine level
    total_score = BBBEESyncService.calculate_total_score(service_year)
    level_info = BBBEESyncService.determine_level_from_score(
        total_score,
        service_year.enterprise_type
    )
    
    # Scorecard weights (Generic)
    weights = {
        'ownership': 25,
        'management': 19,
        'skills': 20,
        'esd': 40,
        'sed': 5,
        'total': 109
    }
    
    context = {
        'client': client,
        'service_year': service_year,
        'elements': elements,
        'total_score': total_score,
        'level_code': level_info[0],
        'level_display': level_info[1],
        'recognition_percentage': level_info[2],
        'weights': weights,
        'enterprise_info': BBBEESyncService.get_verification_requirements(service_year.enterprise_type),
    }
    
    return render(request, 'corporate/bbbee_scorecard_summary.html', context)


@login_required
def bbbee_update_status(request, client_pk, year_pk):
    """
    Update B-BBEE service year status.
    """
    from .models import BBBEEServiceYear
    
    client = get_object_or_404(CorporateClient, pk=client_pk)
    service_year = get_object_or_404(BBBEEServiceYear, pk=year_pk, client=client)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        if new_status and new_status in dict(BBBEEServiceYear.STATUS_CHOICES):
            service_year.status = new_status
            if notes:
                service_year.notes = notes
            service_year.save(update_fields=['status', 'notes'])
            messages.success(request, f"Status updated to {service_year.get_status_display()}.")
        else:
            messages.error(request, "Invalid status.")
    
    return redirect('corporate:bbbee_service_management', client_pk=client_pk)


# =============================================================================
# CLIENT ONBOARDING WIZARD
# =============================================================================

from .models import ClientOnboarding, ServiceOnboarding, PortalInvitation


@login_required
def client_onboarding_wizard(request, pk):
    """
    Main onboarding wizard view. Displays the current step and handles step progression.
    """
    client = get_object_or_404(CorporateClient, pk=pk)
    
    # Get or create onboarding record
    onboarding, created = ClientOnboarding.objects.get_or_create(
        client=client,
        defaults={
            'account_manager': client.account_manager or request.user,
            'started_by': request.user,
        }
    )
    
    # If legacy or complete, redirect to 360 view
    if onboarding.is_complete and not request.GET.get('review'):
        messages.info(request, "Onboarding already complete.")
        return redirect('corporate:client_360', pk=pk)
    
    # Get step data
    steps = [
        {'number': 1, 'code': 'COMPANY_VERIFY', 'name': 'Company Verification', 'icon': 'building'},
        {'number': 2, 'code': 'SERVICES', 'name': 'Services Configuration', 'icon': 'cog'},
        {'number': 3, 'code': 'CONTACTS', 'name': 'Contacts & Portal Access', 'icon': 'users'},
        {'number': 4, 'code': 'DOCUMENTS', 'name': 'Document Initialization', 'icon': 'document'},
        {'number': 5, 'code': 'KICKOFF', 'name': 'Kickoff Meeting', 'icon': 'calendar'},
    ]
    
    # Mark steps as complete
    for step in steps:
        step['completed'] = onboarding.get_step_status(step['code']).get('completed', False)
        step['current'] = onboarding.current_step == step['code']
    
    # Get current step number
    current_step_number = onboarding.current_step_number
    
    context = {
        'client': client,
        'onboarding': onboarding,
        'steps': steps,
        'current_step': current_step_number,
        'current_step_code': onboarding.current_step,
    }
    
    # Render step-specific content
    if onboarding.current_step == 'COMPANY_VERIFY':
        context['setas'] = SETA.objects.all()
    elif onboarding.current_step == 'SERVICES':
        context['available_services'] = ServiceOffering.objects.filter(is_active=True)
        context['subscriptions'] = client.service_subscriptions.select_related('service').all()
    elif onboarding.current_step == 'CONTACTS':
        context['contacts'] = client.contacts.all()
        context['invitations'] = client.portal_invitations.filter(status='PENDING')
        context['role_choices'] = PortalInvitation.ROLE_CHOICES
        context['permission_choices'] = PortalInvitation.PERMISSION_TEMPLATE_CHOICES
    elif onboarding.current_step == 'DOCUMENTS':
        # Get document requirements based on subscribed services
        subscriptions = client.service_subscriptions.filter(status='ACTIVE').select_related('service')
        context['subscriptions'] = subscriptions
        context['core_documents'] = [
            {'name': 'Company Registration', 'code': 'COMPANY_REGISTRATION', 'required': True},
            {'name': 'Tax Clearance Certificate', 'code': 'TAX_CLEARANCE', 'required': True},
            {'name': 'B-BBEE Certificate', 'code': 'BEE_CERTIFICATE', 'required': False},
        ]
    elif onboarding.current_step == 'KICKOFF':
        context['contacts'] = client.contacts.all()
        context['meeting_templates'] = MeetingTemplate.objects.filter(is_active=True)
    
    return render(request, 'corporate/onboarding/wizard.html', context)


@login_required
def client_onboarding_step(request, pk, step):
    """
    Handle step-specific form submissions and step completion.
    """
    client = get_object_or_404(CorporateClient, pk=pk)
    onboarding = get_object_or_404(ClientOnboarding, client=client)
    
    step_mapping = {
        1: 'COMPANY_VERIFY',
        2: 'SERVICES',
        3: 'CONTACTS',
        4: 'DOCUMENTS',
        5: 'KICKOFF',
    }
    
    step_code = step_mapping.get(step)
    if not step_code:
        messages.error(request, "Invalid step.")
        return redirect('corporate:client_onboarding', pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'next')
        
        if action == 'save':
            # Handle step-specific save logic
            if step == 1:
                _handle_company_verify_save(request, client)
            elif step == 2:
                _handle_services_save(request, client, onboarding)
            elif step == 3:
                _handle_contacts_save(request, client)
            elif step == 4:
                _handle_documents_save(request, client)
            elif step == 5:
                _handle_kickoff_save(request, client, onboarding)
            
            messages.success(request, "Progress saved.")
            
        elif action == 'complete':
            # Complete this step and move to next
            if step == 1:
                _handle_company_verify_save(request, client)
            elif step == 2:
                _handle_services_save(request, client, onboarding)
            elif step == 3:
                _handle_contacts_save(request, client)
            elif step == 4:
                _handle_documents_save(request, client)
            elif step == 5:
                _handle_kickoff_save(request, client, onboarding)
            
            onboarding.complete_step(step_code, request.user)
            
            if onboarding.is_complete:
                messages.success(request, f"🎉 Onboarding complete for {client.company_name}!")
                return redirect('corporate:client_360', pk=pk)
            else:
                messages.success(request, f"Step {step} completed.")
        
        elif action == 'back' and step > 1:
            # Go back to previous step
            prev_step_code = step_mapping.get(step - 1)
            onboarding.current_step = prev_step_code
            onboarding.save()
    
    return redirect('corporate:client_onboarding', pk=pk)


def _handle_company_verify_save(request, client):
    """Handle company verification step save."""
    client.company_name = request.POST.get('company_name', client.company_name)
    client.trading_name = request.POST.get('trading_name', client.trading_name)
    client.registration_number = request.POST.get('registration_number', client.registration_number)
    client.vat_number = request.POST.get('vat_number', client.vat_number)
    client.physical_address = request.POST.get('physical_address', client.physical_address)
    client.postal_address = request.POST.get('postal_address', client.postal_address)
    client.industry = request.POST.get('industry', client.industry)
    client.sic_code = request.POST.get('sic_code', client.sic_code)
    
    seta_id = request.POST.get('seta')
    if seta_id:
        client.seta_id = seta_id
    
    client.seta_number = request.POST.get('seta_number', client.seta_number)
    client.employee_count = request.POST.get('employee_count') or client.employee_count
    
    account_manager_id = request.POST.get('account_manager')
    if account_manager_id:
        client.account_manager_id = account_manager_id
    
    client.save()


def _handle_services_save(request, client, onboarding):
    """Handle services configuration step save."""
    # Process service subscriptions from form
    service_ids = request.POST.getlist('services')
    
    for service_id in service_ids:
        service = ServiceOffering.objects.filter(id=service_id).first()
        if not service:
            continue
        
        # Check if subscription already exists
        existing = ClientServiceSubscription.objects.filter(
            client=client,
            service=service
        ).first()
        
        if not existing:
            # Create new subscription
            subscription = ClientServiceSubscription.objects.create(
                client=client,
                service=service,
                start_date=timezone.now().date(),
                status='ACTIVE',
                assigned_consultant=client.account_manager,
            )
            
            # Create service onboarding record
            ServiceOnboarding.objects.create(
                subscription=subscription,
                client_onboarding=onboarding,
                service_type=service.service_type,
                assigned_to=client.account_manager,
            )


def _handle_contacts_save(request, client):
    """Handle contacts step save."""
    # Create new contact if form submitted
    contact_name = request.POST.get('new_contact_name')
    contact_email = request.POST.get('new_contact_email')
    
    if contact_name and contact_email:
        contact, created = CorporateContact.objects.get_or_create(
            client=client,
            email=contact_email,
            defaults={
                'name': contact_name,
                'role': request.POST.get('new_contact_role', 'OTHER'),
                'phone': request.POST.get('new_contact_phone', ''),
            }
        )
        
        # Send invitation if requested
        if request.POST.get('send_invitation'):
            PortalInvitation.objects.create(
                client=client,
                email=contact_email,
                name=contact_name,
                role=request.POST.get('new_contact_role', 'OTHER'),
                permission_template=request.POST.get('permission_template', 'VIEW_ONLY'),
                invited_by=request.user,
            )


def _handle_documents_save(request, client):
    """Handle documents initialization step save."""
    # Documents are typically initialized via signals, but allow manual actions here
    pass


def _handle_kickoff_save(request, client, onboarding):
    """Handle kickoff meeting step save."""
    meeting_date = request.POST.get('meeting_date')
    meeting_time = request.POST.get('meeting_time')
    
    if meeting_date:
        # Get or create committee
        committee, _ = TrainingCommittee.objects.get_or_create(
            client=client,
            defaults={'name': f"{client.company_name} Training Committee"}
        )
        
        # Create kickoff meeting
        meeting = TrainingCommitteeMeeting.objects.create(
            committee=committee,
            meeting_type='TRAINING',
            title=f"Onboarding Kickoff - {client.company_name}",
            scheduled_date=meeting_date,
            scheduled_time=meeting_time or '10:00',
            duration_minutes=60,
            meeting_format=request.POST.get('meeting_format', 'VIRTUAL'),
            status='SCHEDULED',
        )
        
        onboarding.kickoff_meeting = meeting
        onboarding.save()


# =============================================================================
# SERVICE ONBOARDING WIZARD
# =============================================================================

@login_required
def service_onboarding_wizard(request, client_pk, pk):
    """
    Service-specific onboarding wizard view.
    """
    client = get_object_or_404(CorporateClient, pk=client_pk)
    subscription = get_object_or_404(ClientServiceSubscription, pk=pk, client=client)
    
    # Get or create service onboarding record
    onboarding, created = ServiceOnboarding.objects.get_or_create(
        subscription=subscription,
        defaults={
            'service_type': subscription.service.service_type,
            'assigned_to': subscription.assigned_consultant or client.account_manager,
        }
    )
    
    if created or not onboarding.step_data:
        onboarding.initialize_steps()
    
    # If complete, redirect to service management
    if onboarding.status == 'COMPLETE':
        messages.info(request, "Service onboarding already complete.")
        return redirect('corporate:client_360', pk=client_pk)
    
    # Build step list from step_data
    steps = []
    for i in range(1, onboarding.total_steps + 1):
        step_info = onboarding.step_data.get(str(i), {})
        steps.append({
            'number': i,
            'code': step_info.get('code', ''),
            'name': step_info.get('name', f'Step {i}'),
            'completed': step_info.get('completed', False),
            'current': onboarding.current_step == i,
        })
    
    context = {
        'client': client,
        'subscription': subscription,
        'onboarding': onboarding,
        'steps': steps,
        'current_step': onboarding.current_step,
        'service_type': onboarding.service_type,
    }
    
    # Add step-specific context based on service type and current step
    current_step_info = onboarding.step_data.get(str(onboarding.current_step), {})
    step_code = current_step_info.get('code', '')
    
    if onboarding.service_type == 'WSP_ATR':
        context.update(_get_wspatr_step_context(client, subscription, step_code))
    elif onboarding.service_type == 'EE':
        context.update(_get_ee_step_context(client, subscription, step_code))
    elif onboarding.service_type == 'BBBEE':
        context.update(_get_bbbee_step_context(client, subscription, step_code))
    
    return render(request, 'corporate/onboarding/service_wizard.html', context)


def _get_wspatr_step_context(client, subscription, step_code):
    """Get context for WSP/ATR onboarding steps."""
    context = {}
    
    if step_code == 'SETA_CONFIRMATION':
        context['setas'] = SETA.objects.all()
        context['current_seta'] = client.seta
    elif step_code == 'FINANCIAL_YEAR':
        today = timezone.now().date()
        current_fy = today.year if today.month >= 5 else today.year - 1
        context['current_fy'] = current_fy
        context['next_fy'] = current_fy + 1
    elif step_code == 'COMMITTEE':
        context['committee'] = TrainingCommittee.objects.filter(client=client).first()
        context['frequency_choices'] = TrainingCommittee.MEETING_FREQUENCY_CHOICES if hasattr(TrainingCommittee, 'MEETING_FREQUENCY_CHOICES') else []
    elif step_code == 'SDF_APPOINTMENT':
        context['contacts'] = client.contacts.all()
        context['sdf_contact'] = client.contacts.filter(role='SDF').first()
    elif step_code == 'WORKFORCE':
        context['occupational_levels'] = [
            ('TOP_MANAGEMENT', 'Top Management'),
            ('SENIOR_MANAGEMENT', 'Senior Management'),
            ('PROFESSIONAL', 'Professionally Qualified'),
            ('SKILLED_TECHNICAL', 'Skilled Technical'),
            ('SEMI_SKILLED', 'Semi-Skilled'),
            ('UNSKILLED', 'Unskilled'),
        ]
    elif step_code == 'DOCUMENTS':
        context['document_types'] = [
            ('SDL_CERTIFICATE', 'SDL Certificate', True),
            ('COMPANY_REGISTRATION', 'Company Registration', True),
            ('EMPLOYEE_LIST', 'Employee List', True),
            ('ORGANOGRAM', 'Organogram', False),
        ]
    
    return context


def _get_ee_step_context(client, subscription, step_code):
    """Get context for EE onboarding steps."""
    context = {}
    
    if step_code == 'REPORTING_PERIOD':
        today = timezone.now().date()
        current_year = today.year if today.month >= 10 else today.year
        context['current_year'] = current_year
    elif step_code == 'SENIOR_MANAGER':
        context['contacts'] = client.contacts.filter(role='EXEC')
    elif step_code == 'COMMITTEE':
        context['committee'] = TrainingCommittee.objects.filter(client=client, handles_ee=True).first()
    elif step_code == 'BARRIERS':
        context['barrier_types'] = EEBarrier.BARRIER_TYPE_CHOICES if hasattr(EEBarrier, 'BARRIER_TYPE_CHOICES') else []
    
    return context


def _get_bbbee_step_context(client, subscription, step_code):
    """Get context for B-BBEE onboarding steps."""
    context = {}
    
    if step_code == 'CLASSIFICATION':
        context['entity_types'] = [
            ('EME', 'Exempt Micro Enterprise (≤R10m)'),
            ('QSE', 'Qualifying Small Enterprise (R10-50m)'),
            ('GENERIC', 'Generic Enterprise (>R50m)'),
        ]
    elif step_code == 'OWNERSHIP':
        context['shareholder_types'] = [
            ('INDIVIDUAL', 'Individual'),
            ('COMPANY', 'Company'),
            ('TRUST', 'Trust'),
            ('ESOP', 'ESOP'),
        ]
    
    return context


@login_required
def service_onboarding_step(request, client_pk, pk, step):
    """
    Handle service onboarding step submissions.
    """
    client = get_object_or_404(CorporateClient, pk=client_pk)
    subscription = get_object_or_404(ClientServiceSubscription, pk=pk, client=client)
    onboarding = get_object_or_404(ServiceOnboarding, subscription=subscription)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'next')
        
        if action == 'complete':
            # Handle step-specific logic based on service type
            if onboarding.service_type == 'WSP_ATR':
                _handle_wspatr_step(request, client, subscription, onboarding, step)
            elif onboarding.service_type == 'EE':
                _handle_ee_step(request, client, subscription, onboarding, step)
            elif onboarding.service_type == 'BBBEE':
                _handle_bbbee_step(request, client, subscription, onboarding, step)
            
            onboarding.complete_step(step, request.user)
            
            if onboarding.status == 'COMPLETE':
                messages.success(request, f"🎉 {onboarding.get_service_type_display()} setup complete!")
                return redirect('corporate:client_360', pk=client_pk)
            else:
                messages.success(request, f"Step {step} completed.")
        
        elif action == 'back' and step > 1:
            onboarding.current_step = step - 1
            onboarding.save()
    
    return redirect('corporate:service_onboarding', client_pk=client_pk, pk=pk)


def _handle_wspatr_step(request, client, subscription, onboarding, step):
    """Handle WSP/ATR specific step logic."""
    step_info = onboarding.step_data.get(str(step), {})
    step_code = step_info.get('code', '')
    
    if step_code == 'SETA_CONFIRMATION':
        seta_id = request.POST.get('seta')
        if seta_id:
            client.seta_id = seta_id
            client.seta_number = request.POST.get('seta_number', '')
            client.save()
    
    elif step_code == 'FINANCIAL_YEAR':
        fy = request.POST.get('financial_year')
        if fy:
            WSPATRServiceYear.objects.get_or_create(
                client=client,
                financial_year=int(fy),
                defaults={
                    'subscription': subscription,
                    'status': 'NOT_STARTED'
                }
            )
    
    elif step_code == 'COMMITTEE':
        committee, created = TrainingCommittee.objects.get_or_create(
            client=client,
            defaults={'name': f"{client.company_name} Training Committee"}
        )
        frequency = request.POST.get('meeting_frequency')
        if frequency:
            committee.meeting_frequency = frequency
            committee.save()
    
    elif step_code == 'SDF_APPOINTMENT':
        sdf_contact_id = request.POST.get('sdf_contact')
        if sdf_contact_id:
            contact = CorporateContact.objects.filter(id=sdf_contact_id, client=client).first()
            if contact:
                contact.role = 'SDF'
                contact.save()
                
                # Add as committee member
                committee = TrainingCommittee.objects.filter(client=client).first()
                if committee:
                    TrainingCommitteeMember.objects.get_or_create(
                        committee=committee,
                        linked_contact=contact,
                        defaults={'role': 'SDF', 'is_training_committee': True}
                    )
    
    elif step_code == 'MEETINGS':
        # Schedule quarterly meetings
        committee = TrainingCommittee.objects.filter(client=client).first()
        if committee:
            today = timezone.now().date()
            current_fy = today.year if today.month >= 5 else today.year - 1
            
            # Get service year
            service_year = WSPATRServiceYear.objects.filter(
                client=client,
                financial_year=current_fy
            ).first()
            
            # Schedule 4 quarterly meetings
            quarters = [
                (f'{current_fy}-07-15', 'Q1 Committee Meeting'),
                (f'{current_fy}-10-15', 'Q2 Committee Meeting'),
                (f'{current_fy + 1}-01-15', 'Q3 Committee Meeting'),
                (f'{current_fy + 1}-04-01', 'Q4 Committee Meeting'),
            ]
            
            for i, (date_str, title) in enumerate(quarters, 1):
                meeting_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                TrainingCommitteeMeeting.objects.get_or_create(
                    committee=committee,
                    service_year=service_year,
                    sequence_number=i,
                    defaults={
                        'meeting_type': 'TRAINING',
                        'title': title,
                        'scheduled_date': meeting_date,
                        'scheduled_time': '10:00',
                        'duration_minutes': 60,
                        'status': 'SCHEDULED',
                    }
                )


def _handle_ee_step(request, client, subscription, onboarding, step):
    """Handle EE specific step logic."""
    step_info = onboarding.step_data.get(str(step), {})
    step_code = step_info.get('code', '')
    
    if step_code == 'REPORTING_PERIOD':
        year = request.POST.get('reporting_year')
        if year:
            from tenants.models import Campus
            campus = client.campus or Campus.objects.first()
            EEServiceYear.objects.get_or_create(
                client=client,
                reporting_year=int(year),
                defaults={
                    'subscription': subscription,
                    'status': 'NOT_STARTED',
                    'campus': campus
                }
            )
    
    elif step_code == 'COMMITTEE':
        committee, created = TrainingCommittee.objects.get_or_create(
            client=client,
            defaults={'name': f"{client.company_name} EE Committee"}
        )
        committee.handles_ee = True
        committee.save()
    
    elif step_code == 'EE_PLAN':
        plan_period = request.POST.get('plan_period', 5)
        existing_plan = EEPlan.objects.filter(client=client, status='ACTIVE').first()
        
        if not existing_plan:
            EEPlan.objects.create(
                client=client,
                name=f"{client.company_name} EE Plan",
                plan_period=int(plan_period),
                start_date=timezone.now().date(),
                status='DRAFT',
            )


def _handle_bbbee_step(request, client, subscription, onboarding, step):
    """Handle B-BBEE specific step logic."""
    step_info = onboarding.step_data.get(str(step), {})
    step_code = step_info.get('code', '')
    
    if step_code == 'CLASSIFICATION':
        entity_type = request.POST.get('entity_type')
        turnover = request.POST.get('turnover')
        
        if entity_type:
            from tenants.models import Campus
            campus = client.campus or Campus.objects.first()
            BBBEEServiceYear.objects.get_or_create(
                client=client,
                financial_year=timezone.now().year,
                defaults={
                    'subscription': subscription,
                    'enterprise_type': entity_type,
                    'turnover': turnover or 0,
                    'status': 'NOT_STARTED',
                    'campus': campus,
                }
            )
    
    elif step_code == 'OWNERSHIP':
        service_year = BBBEEServiceYear.objects.filter(client=client).first()
        if service_year:
            black_ownership = request.POST.get('black_ownership', 0)
            black_women_ownership = request.POST.get('black_women_ownership', 0)
            
            service_year.black_ownership_percentage = black_ownership
            service_year.black_women_ownership_percentage = black_women_ownership
            service_year.save()
            
            # Create ownership structure
            OwnershipStructure.objects.get_or_create(
                service_year=service_year,
                defaults={
                    'black_voting_percentage': black_ownership,
                    'black_economic_percentage': black_ownership,
                }
            )


# =============================================================================
# CLIENT 360 TABS (HTMX)
# =============================================================================

@login_required
def client_360_tab(request, pk, tab):
    """
    HTMX endpoint for lazy-loading Client 360 tabs.
    """
    client = get_object_or_404(CorporateClient, pk=pk)
    
    context = {'client': client}
    
    if tab == 'overview':
        # Onboarding progress
        onboarding = ClientOnboarding.objects.filter(client=client).first()
        context['onboarding'] = onboarding
        context['health_score'] = client.health_score
        
        # Key dates
        context['contract_end'] = client.contract_end_date
        context['renewal_date'] = client.service_subscriptions.filter(
            status='ACTIVE'
        ).order_by('renewal_date').first()
        
        template = 'corporate/client_360/tab_overview.html'
    
    elif tab == 'services':
        context['subscriptions'] = client.service_subscriptions.select_related(
            'service__category'
        ).all()
        context['service_onboardings'] = ServiceOnboarding.objects.filter(
            subscription__client=client
        ).select_related('subscription__service')
        template = 'corporate/client_360/tab_services.html'
    
    elif tab == 'projects':
        context['projects'] = ServiceDeliveryProject.objects.filter(
            client=client
        ).select_related('subscription__service').prefetch_related('milestones')
        template = 'corporate/client_360/tab_projects.html'
    
    elif tab == 'documents':
        # Collect documents from all services
        context['wspatr_docs'] = WSPATRDocument.objects.filter(
            service_year__client=client
        ).order_by('-created_at')[:20]
        context['ee_docs'] = EEDocument.objects.filter(
            service_year__client=client
        ).order_by('-created_at')[:20]
        context['bbbee_docs'] = BBBEEDocument.objects.filter(
            service_year__client=client
        ).order_by('-created_at')[:20]
        template = 'corporate/client_360/tab_documents.html'
    
    elif tab == 'contacts':
        context['contacts'] = client.contacts.all()
        context['invitations'] = client.portal_invitations.all()
        template = 'corporate/client_360/tab_contacts.html'
    
    elif tab == 'meetings':
        committee = TrainingCommittee.objects.filter(client=client).first()
        if committee:
            context['committee'] = committee
            context['meetings'] = TrainingCommitteeMeeting.objects.filter(
                committee=committee
            ).order_by('-scheduled_date')[:10]
        template = 'corporate/client_360/tab_meetings.html'
    
    elif tab == 'activity':
        context['activities'] = client.activities.order_by('-activity_date')[:30]
        template = 'corporate/client_360/tab_activity.html'
    
    elif tab == 'financials':
        from django.db.models import Sum
        context['total_value'] = client.service_subscriptions.filter(
            status='ACTIVE'
        ).aggregate(total=Sum('agreed_price'))['total'] or 0
        context['won_opportunities'] = client.opportunities.filter(
            stage='CLOSED_WON'
        ).aggregate(total=Sum('estimated_value'))['total'] or 0
        template = 'corporate/client_360/tab_financials.html'
    
    else:
        template = 'corporate/client_360/tab_overview.html'
    
    return render(request, template, context)


# =============================================================================
# PORTAL INVITATIONS
# =============================================================================

@login_required
def contact_invite(request, client_pk):
    """
    Send portal invitation to a contact.
    """
    client = get_object_or_404(CorporateClient, pk=client_pk)
    
    if request.method == 'POST':
        email = request.POST.get('email')
        name = request.POST.get('name')
        role = request.POST.get('role', 'OTHER')
        permission_template = request.POST.get('permission_template', 'VIEW_ONLY')
        personal_message = request.POST.get('personal_message', '')
        
        if email and name:
            invitation = PortalInvitation.objects.create(
                client=client,
                email=email,
                name=name,
                role=role,
                permission_template=permission_template,
                personal_message=personal_message,
                invited_by=request.user,
            )
            
            # TODO: Send invitation email
            # send_portal_invitation_email(invitation)
            
            messages.success(request, f"Invitation sent to {email}")
        else:
            messages.error(request, "Name and email are required.")
    
    return redirect('corporate:client_360', pk=client_pk)


def portal_invitation_accept(request, token):
    """
    Accept a portal invitation (public view).
    """
    invitation = get_object_or_404(PortalInvitation, token=token)
    
    if not invitation.is_valid:
        return render(request, 'corporate/invitation_invalid.html', {
            'invitation': invitation,
            'reason': 'expired' if invitation.status == 'EXPIRED' else 'invalid'
        })
    
    if request.method == 'POST':
        if request.user.is_authenticated:
            # Accept with current user
            try:
                contact = invitation.accept(request.user)
                messages.success(request, f"Welcome to {invitation.client.company_name}!")
                return redirect('portals:corporate_dashboard')
            except ValueError as e:
                messages.error(request, str(e))
        else:
            # Redirect to registration/login
            return redirect(f'/accounts/login/?next=/corporate/invitations/{token}/')
    
    return render(request, 'corporate/invitation_accept.html', {
        'invitation': invitation,
    })


@login_required
def portal_invitation_resend(request, pk):
    """
    Resend a portal invitation.
    """
    invitation = get_object_or_404(PortalInvitation, pk=pk)
    
    if request.method == 'POST':
        invitation.resend(request.user)
        # TODO: Send invitation email
        messages.success(request, f"Invitation resent to {invitation.email}")
    
    return redirect('corporate:client_360', pk=invitation.client.pk)


@login_required
def portal_invitation_revoke(request, pk):
    """
    Revoke a portal invitation.
    """
    invitation = get_object_or_404(PortalInvitation, pk=pk)
    
    if request.method == 'POST':
        invitation.revoke()
        messages.success(request, f"Invitation revoked for {invitation.email}")
    
    return redirect('corporate:client_360', pk=invitation.client.pk)


# =============================================================================
# CRM PIPELINE (KANBAN)
# =============================================================================

@login_required
def crm_pipeline(request):
    """
    CRM Pipeline Kanban board view.
    """
    stages = [
        ('IDENTIFIED', 'Identified'),
        ('QUALIFIED', 'Qualified'),
        ('NEEDS_ANALYSIS', 'Needs Analysis'),
        ('PROPOSAL', 'Proposal'),
        ('NEGOTIATION', 'Negotiation'),
        ('CLOSED_WON', 'Closed Won'),
        ('CLOSED_LOST', 'Closed Lost'),
    ]
    
    # Build pipeline data
    pipeline = []
    for stage_code, stage_name in stages:
        opportunities = CorporateOpportunity.objects.filter(
            stage=stage_code
        ).select_related('client', 'owner').order_by('-created_at')
        
        total_value = opportunities.aggregate(total=Sum('estimated_value'))['total'] or 0
        
        pipeline.append({
            'code': stage_code,
            'name': stage_name,
            'opportunities': opportunities,
            'count': opportunities.count(),
            'total_value': total_value,
        })
    
    # Filters
    owner_filter = request.GET.get('owner')
    service_filter = request.GET.get('service')
    
    context = {
        'pipeline': pipeline,
        'stages': stages,
        'users': User.objects.filter(is_active=True),
        'services': ServiceOffering.objects.filter(is_active=True),
        'owner_filter': owner_filter,
        'service_filter': service_filter,
    }
    
    return render(request, 'corporate/crm_pipeline.html', context)


@login_required
def crm_pipeline_update_stage(request):
    """
    HTMX endpoint to update opportunity stage via drag-drop.
    """
    if request.method == 'POST':
        opportunity_id = request.POST.get('opportunity_id')
        new_stage = request.POST.get('stage')
        
        opportunity = get_object_or_404(CorporateOpportunity, pk=opportunity_id)
        
        if new_stage and new_stage in dict(CorporateOpportunity.STAGE_CHOICES):
            old_stage = opportunity.stage
            opportunity.stage = new_stage
            opportunity.save()
            
            # Log activity
            CorporateActivity.objects.create(
                client=opportunity.client,
                opportunity=opportunity,
                activity_type='NOTE',
                subject=f"Stage changed: {old_stage} → {new_stage}",
                notes=f"Opportunity moved from {old_stage} to {new_stage}",
                activity_date=timezone.now(),
                performed_by=request.user,
            )
            
            if request.headers.get('HX-Request'):
                return JsonResponse({'success': True, 'message': 'Stage updated'})
        
        return JsonResponse({'success': False, 'message': 'Invalid stage'})
    
    return JsonResponse({'success': False, 'message': 'POST required'})
