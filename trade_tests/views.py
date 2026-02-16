"""
Trade Tests Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.http import JsonResponse
from django.db.models import Count, Q, Avg
from django.utils import timezone
from django.urls import reverse, reverse_lazy

from .models import (
    Trade,
    TradeTestCentre,
    TradeTestCentreCapability,
    TradeTestApplication,
    ARPLToolkitAssessment,
    TradeTestBooking,
    TradeTestResult,
)
from .forms import (
    TradeTestApplicationForm,
    InternalApplicationForm,
    ExternalApplicationForm,
    ScheduleBookingForm,
    BulkScheduleForm,
    TradeTestResultForm,
    ARPLAssessmentForm,
    TradeTestCentreForm,
)


# =============================================================================
# DASHBOARD
# =============================================================================

@login_required
def dashboard(request):
    """Trade tests dashboard with pipeline stats"""
    
    # Applications by status
    applications = TradeTestApplication.objects.all()
    application_stats = {
        'total': applications.count(),
        'draft': applications.filter(status='DRAFT').count(),
        'submitted': applications.filter(status='SUBMITTED_TO_NAMB').count(),
        'awaiting_schedule': applications.filter(status='AWAITING_SCHEDULE').count(),
        'scheduled': applications.filter(status='SCHEDULED').count(),
        'in_progress': applications.filter(status='IN_PROGRESS').count(),
        'completed': applications.filter(status='COMPLETED').count(),
    }
    
    # Applications by source
    source_stats = {
        'internal': applications.filter(candidate_source='INTERNAL').count(),
        'external': applications.filter(candidate_source='EXTERNAL').count(),
        'arpl': applications.filter(candidate_source='ARPL').count(),
    }
    
    # Bookings awaiting schedule
    awaiting_schedule = TradeTestBooking.objects.filter(
        status='AWAITING_SCHEDULE',
        scheduled_date__isnull=True
    ).select_related('learner', 'trade', 'application')[:10]
    
    # Upcoming scheduled tests
    upcoming_tests = TradeTestBooking.objects.filter(
        status__in=['CONFIRMED', 'SUBMITTED'],
        scheduled_date__gte=timezone.now().date()
    ).select_related('learner', 'trade', 'centre').order_by('scheduled_date')[:10]
    
    # Recent results
    recent_results = TradeTestResult.objects.filter(
        section='FINAL'
    ).select_related(
        'booking__learner', 'booking__trade', 'booking__application'
    ).order_by('-test_date')[:10]
    
    # Pass rate calculation
    final_results = TradeTestResult.objects.filter(section='FINAL')
    total_final = final_results.count()
    passed_count = final_results.filter(result='COMPETENT').count()
    pass_rate = (passed_count / total_final * 100) if total_final > 0 else 0
    
    # Centre stats
    centres = TradeTestCentre.objects.filter(is_active=True).annotate(
        booking_count=Count('bookings', filter=Q(bookings__status='CONFIRMED'))
    )
    
    # Build stats object to match template expectations
    stats = {
        'total_applications': application_stats['total'],
        'pending': application_stats['draft'] + application_stats['submitted'] + application_stats['awaiting_schedule'],
        'scheduled': application_stats['scheduled'],
        'completed': application_stats['completed'],
        'by_source': {
            'internal': source_stats['internal'],
            'external': source_stats['external'],
            'arpl': source_stats['arpl'],
        },
        'by_status': application_stats,
    }
    
    context = {
        'stats': stats,
        'application_stats': application_stats,
        'source_stats': source_stats,
        'awaiting_schedule': awaiting_schedule,
        'upcoming_tests': upcoming_tests,
        'recent_results': recent_results,
        'pass_rate': round(pass_rate, 1),
        'total_tested': total_final,
        'total_passed': passed_count,
        'centres': centres,
    }
    
    return render(request, 'trade_tests/dashboard.html', context)


# =============================================================================
# APPLICATIONS
# =============================================================================

class ApplicationListView(LoginRequiredMixin, ListView):
    model = TradeTestApplication
    template_name = 'trade_tests/application_list.html'
    context_object_name = 'applications'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = TradeTestApplication.objects.select_related(
            'learner', 'trade', 'centre', 'enrollment'
        ).order_by('-created_at')
        
        # Filters
        status = self.request.GET.get('status')
        source = self.request.GET.get('source')
        trade = self.request.GET.get('trade')
        centre = self.request.GET.get('centre')
        search = self.request.GET.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        if source:
            queryset = queryset.filter(candidate_source=source)
        if trade:
            queryset = queryset.filter(trade_id=trade)
        if centre:
            queryset = queryset.filter(centre_id=centre)
        if search:
            queryset = queryset.filter(
                Q(reference_number__icontains=search) |
                Q(learner__first_name__icontains=search) |
                Q(learner__last_name__icontains=search) |
                Q(learner__sa_id_number__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = TradeTestApplication.STATUS_CHOICES
        context['source_choices'] = TradeTestApplication.CANDIDATE_SOURCE_CHOICES
        context['trades'] = Trade.objects.filter(is_active=True)
        context['centres'] = TradeTestCentre.objects.filter(is_active=True)
        return context


@login_required
def application_create(request, source=None):
    """
    Create trade test application.
    For external/ARPL, redirects to learner creation first if needed.
    """
    # Check for redirect from learner creation
    learner_id = request.GET.get('learner_id')
    source = source or request.GET.get('source', 'INTERNAL')
    
    if request.method == 'POST':
        if source == 'INTERNAL':
            form = InternalApplicationForm(request.POST)
            if form.is_valid():
                application = form.save(commit=False)
                application.candidate_source = 'INTERNAL'
                enrollment = form.cleaned_data['enrollment']
                application.learner = enrollment.learner
                
                # Auto-populate trade from qualification
                if enrollment.qualification:
                    trade = Trade.objects.filter(
                        qualification=enrollment.qualification
                    ).first()
                    if trade:
                        application.trade = trade
                
                application.status = 'SUBMITTED'
                application.save()
                
                messages.success(request, f'Application {application.reference_number} created successfully.')
                return redirect('trade_tests:application_detail', pk=application.pk)
        else:
            form = ExternalApplicationForm(request.POST)
            if form.is_valid():
                application = form.save(commit=False)
                application.candidate_source = source
                application.status = 'SUBMITTED'
                application.save()
                
                # Create ARPL assessment if ARPL candidate
                if source == 'ARPL':
                    ARPLToolkitAssessment.objects.create(
                        application=application,
                        centre=application.centre
                    )
                
                messages.success(request, f'Application {application.reference_number} created successfully.')
                return redirect('trade_tests:application_detail', pk=application.pk)
    else:
        if source == 'INTERNAL':
            form = InternalApplicationForm()
            # Filter enrollments for trade test ready status
            from academics.models import Enrollment
            form.fields['enrollment'].queryset = Enrollment.objects.filter(
                status__in=['ACTIVE', 'COMPLETED']
            ).select_related('learner', 'qualification')
        else:
            form = ExternalApplicationForm()
            # Pre-select learner if coming from learner creation
            if learner_id:
                form.fields['learner'].initial = learner_id
    
    context = {
        'form': form,
        'source': source,
        'source_display': dict(TradeTestApplication.CANDIDATE_SOURCE_CHOICES).get(source, source),
    }
    
    return render(request, 'trade_tests/application_form.html', context)


class ApplicationDetailView(LoginRequiredMixin, DetailView):
    model = TradeTestApplication
    template_name = 'trade_tests/application_detail.html'
    context_object_name = 'application'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object
        
        # Get all bookings with results
        context['bookings'] = application.bookings.select_related(
            'centre'
        ).prefetch_related('results').order_by('attempt_number')
        
        # ARPL assessment if exists
        context['arpl_assessment'] = getattr(application, 'arpl_assessment', None)
        
        return context


class ApplicationUpdateView(LoginRequiredMixin, UpdateView):
    model = TradeTestApplication
    form_class = TradeTestApplicationForm
    template_name = 'trade_tests/application_form.html'
    
    def get_success_url(self):
        return reverse('trade_tests:application_detail', kwargs={'pk': self.object.pk})


@login_required
def submit_to_namb(request, pk):
    """Submit application to NAMB"""
    application = get_object_or_404(TradeTestApplication, pk=pk)
    
    if request.method == 'POST':
        application.status = 'SUBMITTED_TO_NAMB'
        application.namb_submission_date = timezone.now().date()
        application.save()
        
        # Create first booking
        booking = TradeTestBooking.objects.create(
            application=application,
            attempt_number=1,
            learner=application.learner,
            trade=application.trade,
            centre=application.centre,
            status='AWAITING_SCHEDULE'
        )
        
        messages.success(request, f'Application submitted to NAMB. Booking {booking.booking_reference} created.')
        return redirect('trade_tests:application_detail', pk=pk)
    
    return render(request, 'trade_tests/submit_confirm.html', {'application': application})


# =============================================================================
# BOOKINGS
# =============================================================================

class BookingListView(LoginRequiredMixin, ListView):
    model = TradeTestBooking
    template_name = 'trade_tests/booking_list.html'
    context_object_name = 'bookings'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = TradeTestBooking.objects.select_related(
            'learner', 'trade', 'centre', 'application'
        ).order_by('-created_at')
        
        # Filters
        status = self.request.GET.get('status')
        centre = self.request.GET.get('centre')
        trade = self.request.GET.get('trade')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if status:
            queryset = queryset.filter(status=status)
        if centre:
            queryset = queryset.filter(centre_id=centre)
        if trade:
            queryset = queryset.filter(trade_id=trade)
        if date_from:
            queryset = queryset.filter(scheduled_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(scheduled_date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = TradeTestBooking.STATUS_CHOICES
        context['centres'] = TradeTestCentre.objects.filter(is_active=True)
        context['trades'] = Trade.objects.filter(is_active=True)
        return context


class BookingDetailView(LoginRequiredMixin, DetailView):
    model = TradeTestBooking
    template_name = 'trade_tests/booking_detail.html'
    context_object_name = 'booking'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking = self.object
        
        context['results'] = booking.results.all()
        context['result_form'] = TradeTestResultForm(booking=booking)
        context['schedule_form'] = ScheduleBookingForm(instance=booking)
        
        # Previous attempts
        if booking.previous_attempt:
            context['previous_attempts'] = TradeTestBooking.objects.filter(
                application=booking.application,
                attempt_number__lt=booking.attempt_number
            ).select_related('centre').prefetch_related('results')
        
        return context


@login_required
def schedule_booking(request, pk):
    """Enter schedule date for a booking"""
    booking = get_object_or_404(TradeTestBooking, pk=pk)
    
    if request.method == 'POST':
        form = ScheduleBookingForm(request.POST, instance=booking)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.status = 'CONFIRMED'
            booking.save()
            
            # Update application status
            booking.application.status = 'SCHEDULED'
            booking.application.save(update_fields=['status'])
            
            messages.success(request, f'Booking scheduled for {booking.scheduled_date}.')
            return redirect('trade_tests:booking_detail', pk=pk)
    else:
        form = ScheduleBookingForm(instance=booking)
    
    return render(request, 'trade_tests/schedule_booking.html', {
        'booking': booking,
        'form': form
    })


@login_required
def record_result(request, pk):
    """Record trade test result"""
    booking = get_object_or_404(TradeTestBooking, pk=pk)
    
    if request.method == 'POST':
        form = TradeTestResultForm(request.POST, request.FILES, booking=booking)
        if form.is_valid():
            result = form.save(commit=False)
            result.booking = booking
            result.save()
            
            messages.success(request, f'Result recorded: {result.get_result_display()}')
            return redirect('trade_tests:booking_detail', pk=pk)
    else:
        form = TradeTestResultForm(booking=booking)
    
    return render(request, 'trade_tests/record_result.html', {
        'booking': booking,
        'form': form
    })


@login_required
def bulk_schedule_entry(request):
    """Bulk schedule entry for multiple bookings"""
    pending_bookings = TradeTestBooking.objects.filter(
        status='AWAITING_SCHEDULE',
        scheduled_date__isnull=True
    ).select_related('learner', 'trade', 'centre')
    
    if request.method == 'POST':
        form = BulkScheduleForm(request.POST, pending_bookings=pending_bookings)
        if form.is_valid():
            booking_ids = form.cleaned_data['bookings']
            scheduled_date = form.cleaned_data['scheduled_date']
            scheduled_time = form.cleaned_data.get('scheduled_time')
            namb_reference = form.cleaned_data.get('namb_reference', '')
            
            updated = TradeTestBooking.objects.filter(
                pk__in=booking_ids
            ).update(
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                namb_reference=namb_reference,
                status='CONFIRMED'
            )
            
            messages.success(request, f'{updated} bookings scheduled for {scheduled_date}.')
            return redirect('trade_tests:bulk_schedule')
    else:
        form = BulkScheduleForm(pending_bookings=pending_bookings)
    
    return render(request, 'trade_tests/bulk_schedule.html', {
        'form': form,
        'pending_bookings': pending_bookings
    })


# =============================================================================
# CENTRES
# =============================================================================

class CentreListView(LoginRequiredMixin, ListView):
    model = TradeTestCentre
    template_name = 'trade_tests/centre_list.html'
    context_object_name = 'centres'
    
    def get_queryset(self):
        return TradeTestCentre.objects.annotate(
            capability_count=Count('capabilities'),
            booking_count=Count('bookings')
        ).order_by('name')


class CentreDetailView(LoginRequiredMixin, DetailView):
    model = TradeTestCentre
    template_name = 'trade_tests/centre_detail.html'
    context_object_name = 'centre'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        centre = self.object
        
        context['capabilities'] = centre.capabilities.select_related('trade')
        context['upcoming_bookings'] = centre.bookings.filter(
            scheduled_date__gte=timezone.now().date(),
            status='CONFIRMED'
        ).select_related('learner', 'trade')[:20]
        
        return context


class CentreCreateView(LoginRequiredMixin, CreateView):
    model = TradeTestCentre
    form_class = TradeTestCentreForm
    template_name = 'trade_tests/centre_form.html'
    success_url = reverse_lazy('trade_tests:centre_list')


class CentreUpdateView(LoginRequiredMixin, UpdateView):
    model = TradeTestCentre
    form_class = TradeTestCentreForm
    template_name = 'trade_tests/centre_form.html'
    
    def get_success_url(self):
        return reverse('trade_tests:centre_detail', kwargs={'pk': self.object.pk})


# =============================================================================
# TRADES
# =============================================================================

class TradeListView(LoginRequiredMixin, ListView):
    model = Trade
    template_name = 'trade_tests/trade_list.html'
    context_object_name = 'trades'
    
    def get_queryset(self):
        return Trade.objects.filter(is_active=True).select_related(
            'qualification', 'seta'
        ).annotate(
            application_count=Count('applications'),
            centre_count=Count('centre_capabilities')
        )


class TradeDetailView(LoginRequiredMixin, DetailView):
    model = Trade
    template_name = 'trade_tests/trade_detail.html'
    context_object_name = 'trade'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trade = self.object
        
        context['centres'] = TradeTestCentreCapability.objects.filter(
            trade=trade, is_active=True
        ).select_related('centre')
        
        # Pass rate for this trade
        results = TradeTestResult.objects.filter(
            booking__trade=trade,
            section='FINAL'
        )
        total = results.count()
        passed = results.filter(result='COMPETENT').count()
        context['pass_rate'] = (passed / total * 100) if total > 0 else 0
        context['total_tested'] = total
        
        return context


# =============================================================================
# ARPL
# =============================================================================

class ARPLListView(LoginRequiredMixin, ListView):
    model = ARPLToolkitAssessment
    template_name = 'trade_tests/arpl_list.html'
    context_object_name = 'assessments'
    
    def get_queryset(self):
        return ARPLToolkitAssessment.objects.select_related(
            'application__learner', 'application__trade', 'centre'
        ).order_by('-created_at')


class ARPLDetailView(LoginRequiredMixin, DetailView):
    model = ARPLToolkitAssessment
    template_name = 'trade_tests/arpl_detail.html'
    context_object_name = 'assessment'


@login_required
def arpl_assess(request, pk):
    """Record ARPL toolkit assessment result"""
    assessment = get_object_or_404(ARPLToolkitAssessment, pk=pk)
    
    if request.method == 'POST':
        form = ARPLAssessmentForm(request.POST, instance=assessment)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.assessor = request.user
            assessment.save()
            
            messages.success(request, 'ARPL assessment updated.')
            return redirect('trade_tests:arpl_detail', pk=pk)
    else:
        form = ARPLAssessmentForm(instance=assessment)
    
    return render(request, 'trade_tests/arpl_assess.html', {
        'assessment': assessment,
        'form': form
    })


# =============================================================================
# CANDIDATE HISTORY
# =============================================================================

@login_required
def candidate_history(request, learner_id):
    """View all trade test history for a learner"""
    from learners.models import Learner
    
    learner = get_object_or_404(Learner, pk=learner_id)
    
    applications = TradeTestApplication.objects.filter(
        learner=learner
    ).select_related('trade', 'centre').prefetch_related(
        'bookings__results'
    ).order_by('-application_date')
    
    return render(request, 'trade_tests/candidate_history.html', {
        'learner': learner,
        'applications': applications
    })


# =============================================================================
# REPORTS
# =============================================================================

@login_required
def reports_dashboard(request):
    """Reports dashboard"""
    return render(request, 'trade_tests/reports.html')


@login_required
def pass_rate_report(request):
    """Pass rate report by trade/centre"""
    # By trade
    trade_stats = Trade.objects.annotate(
        total_tests=Count('bookings__results', filter=Q(bookings__results__section='FINAL')),
        passed=Count('bookings__results', filter=Q(
            bookings__results__section='FINAL',
            bookings__results__result='COMPETENT'
        ))
    ).filter(total_tests__gt=0)
    
    # By centre
    centre_stats = TradeTestCentre.objects.annotate(
        total_tests=Count('bookings__results', filter=Q(bookings__results__section='FINAL')),
        passed=Count('bookings__results', filter=Q(
            bookings__results__section='FINAL',
            bookings__results__result='COMPETENT'
        ))
    ).filter(total_tests__gt=0)
    
    return render(request, 'trade_tests/pass_rate_report.html', {
        'trade_stats': trade_stats,
        'centre_stats': centre_stats
    })


# =============================================================================
# API ENDPOINTS
# =============================================================================

@login_required
def api_trades_for_qualification(request, qualification_id):
    """Get trades linked to a qualification"""
    trades = Trade.objects.filter(
        qualification_id=qualification_id,
        is_active=True
    ).values('id', 'namb_code', 'name')
    
    return JsonResponse(list(trades), safe=False)


@login_required
def api_centres_for_trade(request, trade_id):
    """Get centres that offer a specific trade"""
    capabilities = TradeTestCentreCapability.objects.filter(
        trade_id=trade_id,
        is_active=True
    ).select_related('centre').values(
        'centre__id', 'centre__name', 'centre__city',
        'next_available_date', 'max_candidates_per_session'
    )
    
    return JsonResponse(list(capabilities), safe=False)


# =============================================================================
# APPEALS
# =============================================================================

from .models import TradeTestAppeal

class AppealListView(LoginRequiredMixin, ListView):
    """List all trade test appeals"""
    model = TradeTestAppeal
    template_name = 'trade_tests/appeal_list.html'
    context_object_name = 'appeals'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = TradeTestAppeal.objects.select_related(
            'result__booking__learner',
            'result__booking__trade'
        ).order_by('-created_at')
        
        # Filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = TradeTestAppeal.STATUS_CHOICES
        return context
