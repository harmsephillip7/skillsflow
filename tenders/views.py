"""
Views for Tender Management module.
"""

import json
from datetime import date, timedelta
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Sum, Count, Q, Avg
from django.core.paginator import Paginator
from django.utils import timezone

from .models import (
    Tender, TenderApplication, TenderSource, TenderSegment,
    TenderQualification, TenderDocument, TenderNote, TenderNotificationRule
)
from .services import TenderService


def superuser_or_permission(permission_name):
    """Decorator that allows access if user is superuser OR has specific permission."""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser or request.user.has_perm(permission_name):
                return view_func(request, *args, **kwargs)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return wrapper
    return decorator


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def tender_dashboard(request):
    """Main tender management dashboard with pipeline overview."""
    
    # Get filter parameters
    segment_id = request.GET.get('segment')
    funder = request.GET.get('funder', '')
    region = request.GET.get('region', '')
    status = request.GET.get('status', '')
    
    # Base queryset
    tenders = Tender.objects.all()
    
    # Apply filters
    if segment_id:
        tenders = tenders.filter(segment_id=segment_id)
    if funder:
        tenders = tenders.filter(funder__icontains=funder)
    if region:
        tenders = tenders.filter(region__icontains=region)
    if status:
        tenders = tenders.filter(status=status)
    
    # Pipeline summary
    pipeline = TenderService.get_pipeline_summary(
        segment=segment_id,
        funder=funder if funder else None,
        region=region if region else None,
    )
    
    # Revenue forecast
    forecast = TenderService.get_revenue_forecast(months_ahead=6)
    
    # Closing soon (next 7 days)
    today = date.today()
    closing_soon = Tender.objects.filter(
        status__in=['DISCOVERED', 'REVIEWING', 'APPLICABLE'],
        closing_date__gte=today,
        closing_date__lte=today + timedelta(days=7)
    ).order_by('closing_date')[:5]
    
    # Recent activity
    recent_notes = TenderNote.objects.select_related(
        'tender', 'created_by'
    ).order_by('-created_at')[:10]
    
    # Segment performance
    segment_stats = TenderService.get_segment_performance()
    
    # Get filter options
    segments = TenderSegment.objects.all()
    funders = Tender.objects.values_list('funder', flat=True).distinct()
    regions = Tender.objects.values_list('region', flat=True).distinct()
    
    context = {
        'tenders': tenders[:20],
        'pipeline': pipeline,
        'forecast': forecast,
        'forecast_json': json.dumps([
            {
                'month': f['month'],
                'expected_revenue': float(f['expected_revenue']),
                'application_count': f['application_count'],
            }
            for f in forecast
        ]),
        'closing_soon': closing_soon,
        'recent_notes': recent_notes,
        'segment_stats': segment_stats,
        'segments': segments,
        'funders': [f for f in funders if f],
        'regions': [r for r in regions if r],
        'status_choices': Tender.STATUS_CHOICES,
        'selected_segment': segment_id,
        'selected_funder': funder,
        'selected_region': region,
        'selected_status': status,
    }
    
    return render(request, 'tenders/dashboard.html', context)


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def tender_list(request):
    """List all tenders with filtering and pagination."""
    
    tenders = Tender.objects.select_related('source', 'segment', 'assigned_to')
    
    # Search
    search = request.GET.get('q', '')
    if search:
        tenders = tenders.filter(
            Q(reference_number__icontains=search) |
            Q(title__icontains=search) |
            Q(funder__icontains=search)
        )
    
    # Filters
    status = request.GET.get('status', '')
    if status:
        tenders = tenders.filter(status=status)
    
    segment_id = request.GET.get('segment', '')
    if segment_id:
        tenders = tenders.filter(segment_id=segment_id)
    
    source_id = request.GET.get('source', '')
    if source_id:
        tenders = tenders.filter(source_id=source_id)
    
    # Sorting
    sort = request.GET.get('sort', '-closing_date')
    tenders = tenders.order_by(sort)
    
    # Pagination
    paginator = Paginator(tenders, 25)
    page = request.GET.get('page', 1)
    tenders = paginator.get_page(page)
    
    context = {
        'tenders': tenders,
        'search': search,
        'selected_status': status,
        'selected_segment': segment_id,
        'selected_source': source_id,
        'segments': TenderSegment.objects.all(),
        'sources': TenderSource.objects.filter(status='ACTIVE'),
        'status_choices': Tender.STATUS_CHOICES,
    }
    
    return render(request, 'tenders/tender_list.html', context)


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def tender_create(request):
    """Manually create a new tender."""
    
    if request.method == 'POST':
        # Parse form data
        tender = Tender(
            reference_number=request.POST.get('reference_number'),
            title=request.POST.get('title'),
            description=request.POST.get('description', ''),
            funder=request.POST.get('funder', ''),
            funder_type=request.POST.get('funder_type', ''),
            region=request.POST.get('region', ''),
            source_url=request.POST.get('source_url', ''),
            requirements_summary=request.POST.get('requirements_summary', ''),
            eligibility_notes=request.POST.get('eligibility_notes', ''),
            notes=request.POST.get('notes', ''),
            priority=request.POST.get('priority', 'MEDIUM'),
            status='DISCOVERED',
            created_by=request.user,
        )
        
        # Parse dates
        if request.POST.get('published_date'):
            tender.published_date = date.fromisoformat(request.POST.get('published_date'))
        if request.POST.get('opening_date'):
            tender.opening_date = date.fromisoformat(request.POST.get('opening_date'))
        if request.POST.get('closing_date'):
            tender.closing_date = date.fromisoformat(request.POST.get('closing_date'))
        if request.POST.get('expected_award_date'):
            tender.expected_award_date = date.fromisoformat(request.POST.get('expected_award_date'))
        
        # Parse value
        if request.POST.get('estimated_value'):
            tender.estimated_value = Decimal(request.POST.get('estimated_value'))
        
        # Set segment
        segment_id = request.POST.get('segment')
        if segment_id:
            tender.segment_id = int(segment_id)
        
        # Set SETA if provided
        seta_id = request.POST.get('seta')
        if seta_id:
            tender.seta_id = int(seta_id)
        
        # Set assigned to
        assigned_to_id = request.POST.get('assigned_to')
        if assigned_to_id:
            tender.assigned_to_id = int(assigned_to_id)
        
        tender.save()
        
        # Create a note marking this as manually entered
        TenderNote.objects.create(
            tender=tender,
            note_type='SYSTEM',
            content='Tender manually entered by user',
            created_by=request.user,
        )
        
        messages.success(request, f"Tender '{tender.reference_number}' created successfully")
        return redirect('tenders:tender_detail', pk=tender.pk)
    
    # GET - show form
    from core.models import User
    from learners.models import SETA
    
    context = {
        'segments': TenderSegment.objects.filter(is_deleted=False),
        'setas': SETA.objects.filter(is_active=True).order_by('name'),
        'staff': User.objects.filter(is_active=True, is_staff=True).order_by('first_name', 'last_name'),
        'priority_choices': Tender.PRIORITY_CHOICES,
        'funder_types': [
            ('SETA', 'SETA'),
            ('GOVERNMENT', 'Government'),
            ('PRIVATE', 'Private Sector'),
            ('NGO', 'NGO / Non-Profit'),
            ('INTERNATIONAL', 'International'),
        ],
    }
    
    return render(request, 'tenders/tender_create.html', context)


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def tender_edit(request, pk):
    """Edit an existing tender."""
    
    tender = get_object_or_404(Tender, pk=pk)
    
    if request.method == 'POST':
        # Update fields
        tender.reference_number = request.POST.get('reference_number', tender.reference_number)
        tender.title = request.POST.get('title', tender.title)
        tender.description = request.POST.get('description', '')
        tender.funder = request.POST.get('funder', '')
        tender.funder_type = request.POST.get('funder_type', '')
        tender.region = request.POST.get('region', '')
        tender.source_url = request.POST.get('source_url', '')
        tender.requirements_summary = request.POST.get('requirements_summary', '')
        tender.eligibility_notes = request.POST.get('eligibility_notes', '')
        tender.notes = request.POST.get('notes', '')
        tender.priority = request.POST.get('priority', 'MEDIUM')
        
        # Parse dates
        tender.published_date = date.fromisoformat(request.POST.get('published_date')) if request.POST.get('published_date') else None
        tender.opening_date = date.fromisoformat(request.POST.get('opening_date')) if request.POST.get('opening_date') else None
        tender.closing_date = date.fromisoformat(request.POST.get('closing_date')) if request.POST.get('closing_date') else None
        tender.expected_award_date = date.fromisoformat(request.POST.get('expected_award_date')) if request.POST.get('expected_award_date') else None
        
        # Parse value
        tender.estimated_value = Decimal(request.POST.get('estimated_value')) if request.POST.get('estimated_value') else None
        
        # Set segment
        segment_id = request.POST.get('segment')
        tender.segment_id = int(segment_id) if segment_id else None
        
        # Set SETA
        seta_id = request.POST.get('seta')
        tender.seta_id = int(seta_id) if seta_id else None
        
        # Set assigned to
        assigned_to_id = request.POST.get('assigned_to')
        tender.assigned_to_id = int(assigned_to_id) if assigned_to_id else None
        
        tender.save()
        
        messages.success(request, f"Tender '{tender.reference_number}' updated successfully")
        return redirect('tenders:tender_detail', pk=tender.pk)
    
    # GET - show form
    from core.models import User
    from learners.models import SETA
    
    context = {
        'tender': tender,
        'segments': TenderSegment.objects.filter(is_active=True),
        'setas': SETA.objects.filter(is_active=True).order_by('name'),
        'staff': User.objects.filter(is_active=True, is_staff=True).order_by('first_name', 'last_name'),
        'priority_choices': Tender.PRIORITY_CHOICES,
        'funder_types': [
            ('SETA', 'SETA'),
            ('GOVERNMENT', 'Government'),
            ('PRIVATE', 'Private Sector'),
            ('NGO', 'NGO / Non-Profit'),
            ('INTERNATIONAL', 'International'),
        ],
    }
    
    return render(request, 'tenders/tender_edit.html', context)


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def tender_detail(request, pk):
    """View tender details and manage applications."""
    
    tender = get_object_or_404(
        Tender.objects.select_related('source', 'segment', 'assigned_to', 'seta'),
        pk=pk
    )
    
    applications = tender.applications.select_related('created_by').order_by('-created_at')
    qualifications = tender.qualifications.select_related('qualification')
    documents = tender.documents.order_by('category', 'name')
    timeline = tender.timeline_notes.select_related('created_by').order_by('-created_at')
    
    context = {
        'tender': tender,
        'applications': applications,
        'qualifications': qualifications,
        'documents': documents,
        'timeline': timeline,
        'status_choices': Tender.STATUS_CHOICES,
    }
    
    return render(request, 'tenders/tender_detail.html', context)


@login_required
@superuser_or_permission('tenders.can_apply_tenders')
@require_POST
def tender_update_status(request, pk):
    """Update tender status."""
    
    tender = get_object_or_404(Tender, pk=pk)
    new_status = request.POST.get('status')
    
    if new_status not in dict(Tender.STATUS_CHOICES):
        messages.error(request, "Invalid status")
        return redirect('tenders:tender_detail', pk=pk)
    
    old_status = tender.status
    tender.status = new_status
    tender.save(update_fields=['status'])
    
    # Create note
    TenderNote.objects.create(
        tender=tender,
        note_type='STATUS_CHANGE',
        content=f"Status changed from {old_status} to {new_status}",
        old_status=old_status,
        new_status=new_status,
        created_by=request.user,
    )
    
    messages.success(request, f"Status updated to {tender.get_status_display()}")
    return redirect('tenders:tender_detail', pk=pk)


@login_required
@superuser_or_permission('tenders.can_apply_tenders')
@require_POST
def create_application(request, tender_pk):
    """Create a new tender application."""
    
    tender = get_object_or_404(Tender, pk=tender_pk)
    
    application = TenderApplication.objects.create(
        tender=tender,
        status='PREPARING',
        preparation_started_at=timezone.now(),
        created_by=request.user,
    )
    
    # Create note
    TenderNote.objects.create(
        tender=tender,
        application=application,
        note_type='SYSTEM',
        content="Application preparation started",
        created_by=request.user,
    )
    
    messages.success(request, "Application created. Add qualifications and details.")
    return redirect('tenders:application_detail', pk=application.pk)


@login_required
@superuser_or_permission('tenders.can_apply_tenders')
def application_detail(request, pk):
    """View and edit application details."""
    
    application = get_object_or_404(
        TenderApplication.objects.select_related('tender', 'tender__segment'),
        pk=pk
    )
    
    if request.method == 'POST':
        # Update application fields
        application.total_learners = int(request.POST.get('total_learners', 0))
        application.total_amount = Decimal(request.POST.get('total_amount', '0'))
        application.funder_contact_name = request.POST.get('funder_contact_name', '')
        application.funder_contact_email = request.POST.get('funder_contact_email', '')
        application.funder_contact_phone = request.POST.get('funder_contact_phone', '')
        application.notes = request.POST.get('notes', '')
        
        # Handle probability override
        override = request.POST.get('probability_override', '').strip()
        if override:
            application.probability_override = Decimal(override)
        else:
            application.probability_override = None
        
        application.update_probability()
        application.save()
        
        messages.success(request, "Application updated")
        return redirect('tenders:application_detail', pk=pk)
    
    documents = application.documents.order_by('category')
    timeline = application.timeline_notes.select_related('created_by').order_by('-created_at')
    
    context = {
        'application': application,
        'tender': application.tender,
        'documents': documents,
        'timeline': timeline,
        'status_choices': TenderApplication.STATUS_CHOICES,
    }
    
    return render(request, 'tenders/application_detail.html', context)


@login_required
@superuser_or_permission('tenders.can_apply_tenders')
@require_POST
def application_submit(request, pk):
    """Mark application as submitted."""
    
    application = get_object_or_404(TenderApplication, pk=pk)
    application.mark_submitted()
    
    TenderNote.objects.create(
        tender=application.tender,
        application=application,
        note_type='STATUS_CHANGE',
        content="Application submitted",
        old_status='PREPARING',
        new_status='SUBMITTED',
        created_by=request.user,
    )
    
    messages.success(request, "Application marked as submitted")
    return redirect('tenders:application_detail', pk=pk)


@login_required
@superuser_or_permission('tenders.can_apply_tenders')
@require_POST
def application_acknowledge(request, pk):
    """Mark application as acknowledged."""
    
    application = get_object_or_404(TenderApplication, pk=pk)
    reference = request.POST.get('reference', '')
    
    application.mark_acknowledged(reference=reference)
    
    TenderNote.objects.create(
        tender=application.tender,
        application=application,
        note_type='STATUS_CHANGE',
        content=f"Acknowledgement received. Reference: {reference}" if reference else "Acknowledgement received",
        old_status=application.status,
        new_status='ACKNOWLEDGED',
        created_by=request.user,
    )
    
    messages.success(request, "Acknowledgement recorded")
    return redirect('tenders:application_detail', pk=pk)


@login_required
@superuser_or_permission('tenders.can_apply_tenders')
@require_POST
def application_approve(request, pk):
    """Mark application as approved."""
    
    application = get_object_or_404(TenderApplication, pk=pk)
    
    approved_learners = request.POST.get('approved_learners')
    approved_amount = request.POST.get('approved_amount')
    
    application.mark_approved(
        approved_learners=int(approved_learners) if approved_learners else None,
        approved_amount=Decimal(approved_amount) if approved_amount else None,
    )
    
    TenderNote.objects.create(
        tender=application.tender,
        application=application,
        note_type='STATUS_CHANGE',
        content=f"Application approved! Learners: {application.approved_learners}, Amount: R{application.approved_amount:,.2f}",
        old_status=application.status,
        new_status='APPROVED',
        created_by=request.user,
    )
    
    messages.success(request, "Application approved!")
    return redirect('tenders:application_detail', pk=pk)


@login_required
@superuser_or_permission('tenders.can_apply_tenders')
@require_POST
def application_reject(request, pk):
    """Mark application as rejected."""
    
    application = get_object_or_404(TenderApplication, pk=pk)
    reason = request.POST.get('reason', '')
    
    application.mark_rejected(reason=reason)
    
    TenderNote.objects.create(
        tender=application.tender,
        application=application,
        note_type='STATUS_CHANGE',
        content=f"Application rejected. Reason: {reason}" if reason else "Application rejected",
        old_status=application.status,
        new_status='REJECTED',
        created_by=request.user,
    )
    
    messages.success(request, "Application marked as rejected")
    return redirect('tenders:application_detail', pk=pk)


# ========== Source Management ==========

@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def source_list(request):
    """List and manage tender sources."""
    
    sources = TenderSource.objects.annotate(
        tender_count=Count('tenders')
    ).order_by('name')
    
    context = {
        'sources': sources,
    }
    
    return render(request, 'tenders/source_list.html', context)


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def source_detail(request, pk):
    """View and edit source configuration."""
    
    source = get_object_or_404(TenderSource, pk=pk)
    
    if request.method == 'POST':
        # Update source
        source.name = request.POST.get('name', source.name)
        source.base_url = request.POST.get('base_url', source.base_url)
        source.scraper_type = request.POST.get('scraper_type', source.scraper_type)
        source.scrape_frequency_hours = int(request.POST.get('scrape_frequency_hours', 24))
        source.status = request.POST.get('status', source.status)
        
        # Parse JSON config
        config_str = request.POST.get('scrape_config', '{}')
        try:
            source.scrape_config = json.loads(config_str)
        except json.JSONDecodeError:
            messages.error(request, "Invalid JSON in scrape configuration")
            return redirect('tenders:source_detail', pk=pk)
        
        source.save()
        messages.success(request, "Source updated")
        return redirect('tenders:source_detail', pk=pk)
    
    recent_tenders = source.tenders.order_by('-discovered_at')[:10]
    
    context = {
        'source': source,
        'recent_tenders': recent_tenders,
        'scraper_types': TenderSource.SCRAPER_TYPE_CHOICES,
        'status_choices': TenderSource.STATUS_CHOICES,
        'config_json': json.dumps(source.scrape_config, indent=2),
    }
    
    return render(request, 'tenders/source_detail.html', context)


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def source_create(request):
    """Create a new tender source."""
    
    if request.method == 'POST':
        source = TenderSource(
            name=request.POST.get('name'),
            slug=request.POST.get('slug'),
            base_url=request.POST.get('base_url'),
            scraper_type=request.POST.get('scraper_type', 'BEAUTIFULSOUP'),
            scrape_frequency_hours=int(request.POST.get('scrape_frequency_hours', 24)),
            created_by=request.user,
        )
        
        # Parse JSON config
        config_str = request.POST.get('scrape_config', '{}')
        try:
            source.scrape_config = json.loads(config_str)
        except json.JSONDecodeError:
            source.scrape_config = {}
        
        source.save()
        messages.success(request, f"Source '{source.name}' created")
        return redirect('tenders:source_detail', pk=source.pk)
    
    context = {
        'scraper_types': TenderSource.SCRAPER_TYPE_CHOICES,
    }
    
    return render(request, 'tenders/source_create.html', context)


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
@require_POST
def source_test(request, pk):
    """Test connection to a tender source."""
    
    source = get_object_or_404(TenderSource, pk=pk)
    
    from .services import get_scraper
    scraper = get_scraper(source)
    
    success = scraper.test_connection()
    
    return JsonResponse({
        'success': success,
        'message': scraper.get_status_message(),
        'errors': scraper.errors,
        'warnings': scraper.warnings,
    })


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
@require_POST
def source_scrape(request, pk):
    """Trigger a scrape for a tender source."""
    
    source = get_object_or_404(TenderSource, pk=pk)
    
    new_count, updated_count, message = TenderService.run_scrape(source)
    
    return JsonResponse({
        'success': not bool(source.status == 'ERROR'),
        'new_tenders': new_count,
        'updated_tenders': updated_count,
        'message': message,
    })


# ========== Segment Management ==========

@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def segment_list(request):
    """List and manage segments."""
    
    segments = TenderSegment.objects.annotate(
        tender_count=Count('tenders'),
        application_count=Count('tenders__applications'),
    ).order_by('segment_type', 'name')
    
    context = {
        'segments': segments,
    }
    
    return render(request, 'tenders/segment_list.html', context)


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def segment_create(request):
    """Create a new tender segment."""
    
    if request.method == 'POST':
        segment = TenderSegment(
            name=request.POST.get('name'),
            segment_type=request.POST.get('segment_type', 'GOVERNMENT'),
            decay_model=request.POST.get('decay_model', 'LINEAR'),
            initial_probability=Decimal(request.POST.get('initial_probability', '70')),
            decay_rate=Decimal(request.POST.get('decay_rate', '1.5')),
            floor_probability=Decimal(request.POST.get('floor_probability', '5')),
            expected_response_days=int(request.POST.get('expected_response_days', 90)),
            description=request.POST.get('description', ''),
            is_active=request.POST.get('is_active') == 'on',
        )
        segment.save()
        messages.success(request, f"Segment '{segment.name}' created")
        return redirect('tenders:segment_detail', pk=segment.pk)
    
    context = {
        'segment_types': TenderSegment.SEGMENT_TYPE_CHOICES,
        'decay_models': TenderSegment.DECAY_MODEL_CHOICES,
    }
    
    return render(request, 'tenders/segment_create.html', context)


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
def segment_detail(request, pk):
    """View and edit segment configuration."""
    
    segment = get_object_or_404(TenderSegment, pk=pk)
    
    if request.method == 'POST':
        segment.name = request.POST.get('name', segment.name)
        segment.segment_type = request.POST.get('segment_type', segment.segment_type)
        segment.decay_model = request.POST.get('decay_model', segment.decay_model)
        segment.initial_probability = Decimal(request.POST.get('initial_probability', '0.7'))
        segment.decay_rate = Decimal(request.POST.get('decay_rate', '0.015'))
        segment.floor_probability = Decimal(request.POST.get('floor_probability', '0.05'))
        segment.expected_response_days = int(request.POST.get('expected_response_days', 90))
        
        segment.save()
        messages.success(request, "Segment updated")
        return redirect('tenders:segment_detail', pk=pk)
    
    # Generate probability curve data for chart
    probability_curve = []
    for day in range(0, 181, 7):  # Every week for 6 months
        prob = segment.calculate_probability(day)
        probability_curve.append({'day': day, 'probability': float(prob)})
    
    context = {
        'segment': segment,
        'segment_types': TenderSegment.SEGMENT_TYPE_CHOICES,
        'decay_models': TenderSegment.DECAY_MODEL_CHOICES,
        'probability_curve': json.dumps(probability_curve),
    }
    
    return render(request, 'tenders/segment_detail.html', context)


# ========== Analytics ==========

@login_required
@superuser_or_permission('tenders.can_view_tender_analytics')
def analytics(request):
    """Tender analytics and reporting."""
    
    # Date range filter
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = date.fromisoformat(start_date)
    else:
        start_date = date.today() - timedelta(days=365)
    
    if end_date:
        end_date = date.fromisoformat(end_date)
    else:
        end_date = date.today()
    
    # Overall stats
    total_tenders = Tender.objects.filter(
        discovered_at__date__range=(start_date, end_date)
    ).count()
    
    total_applications = TenderApplication.objects.filter(
        created_at__date__range=(start_date, end_date)
    ).count()
    
    total_submitted = TenderApplication.objects.filter(
        submitted_at__date__range=(start_date, end_date)
    ).aggregate(
        count=Count('id'),
        total_value=Sum('total_amount'),
    )
    
    total_approved = TenderApplication.objects.filter(
        status='APPROVED',
        decision_at__date__range=(start_date, end_date)
    ).aggregate(
        count=Count('id'),
        total_value=Sum('approved_amount'),
    )
    
    # Conversion rates
    if total_applications > 0:
        submit_rate = (total_submitted['count'] or 0) / total_applications * 100
    else:
        submit_rate = 0
    
    if total_submitted['count']:
        success_rate = (total_approved['count'] or 0) / total_submitted['count'] * 100
    else:
        success_rate = 0
    
    # By segment
    segment_stats = TenderService.get_segment_performance()
    
    # By source
    source_stats = TenderSource.objects.annotate(
        tender_count=Count('tenders', filter=Q(
            tenders__discovered_at__date__range=(start_date, end_date)
        ))
    ).filter(tender_count__gt=0).order_by('-tender_count')[:10]
    
    # Monthly trend
    from django.db.models.functions import TruncMonth
    monthly_trend = (
        TenderApplication.objects
        .filter(submitted_at__date__range=(start_date, end_date))
        .annotate(month=TruncMonth('submitted_at'))
        .values('month')
        .annotate(
            count=Count('id'),
            total=Sum('total_amount'),
            expected=Sum('expected_revenue'),
        )
        .order_by('month')
    )
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'total_tenders': total_tenders,
        'total_applications': total_applications,
        'total_submitted': total_submitted,
        'total_approved': total_approved,
        'submit_rate': submit_rate,
        'success_rate': success_rate,
        'segment_stats': segment_stats,
        'source_stats': source_stats,
        'monthly_trend': list(monthly_trend),
        'monthly_trend_json': json.dumps([
            {
                'month': m['month'].isoformat() if m['month'] else '',
                'count': m['count'],
                'total': float(m['total'] or 0),
                'expected': float(m['expected'] or 0),
            }
            for m in monthly_trend
        ]),
    }
    
    return render(request, 'tenders/analytics.html', context)


# ========== API endpoints ==========

@login_required
@require_http_methods(['GET'])
def api_pipeline_data(request):
    """API endpoint for pipeline data (for charts)."""
    
    pipeline = TenderService.get_pipeline_summary()
    forecast = TenderService.get_revenue_forecast()
    
    return JsonResponse({
        'pipeline': pipeline,
        'forecast': [
            {
                'month': f['month'],
                'expected_revenue': float(f['expected_revenue']),
                'application_count': f['application_count'],
                'avg_probability': float(f['avg_probability']),
            }
            for f in forecast
        ],
    })


@login_required
@require_http_methods(['GET'])
def api_probability_curve(request, segment_id):
    """API endpoint for segment probability curve."""
    
    segment = get_object_or_404(TenderSegment, id=segment_id)
    
    curve = []
    for day in range(0, 181):
        prob = segment.calculate_probability(day)
        curve.append({'day': day, 'probability': float(prob)})
    
    return JsonResponse({
        'segment': segment.name,
        'decay_model': segment.decay_model,
        'curve': curve,
    })


@login_required
@require_POST
def api_add_note(request, tender_pk):
    """API endpoint to add a note to a tender."""
    
    tender = get_object_or_404(Tender, pk=tender_pk)
    
    data = json.loads(request.body)
    
    note = TenderNote.objects.create(
        tender=tender,
        note_type=data.get('note_type', 'COMMENT'),
        content=data.get('content', ''),
        created_by=request.user,
    )
    
    return JsonResponse({
        'id': note.id,
        'note_type': note.note_type,
        'content': note.content,
        'created_at': note.created_at.isoformat(),
        'created_by': str(note.created_by),
    })


# ========== Additional Views for Template Compatibility ==========

@login_required
@superuser_or_permission('tenders.can_manage_tenders')
@require_POST
def add_note(request, pk):
    """Form-based endpoint to add a note to a tender."""
    
    tender = get_object_or_404(Tender, pk=pk)
    content = request.POST.get('content', '').strip()
    
    if content:
        TenderNote.objects.create(
            tender=tender,
            note_type='COMMENT',
            content=content,
            created_by=request.user,
        )
        messages.success(request, "Note added successfully.")
    else:
        messages.error(request, "Note content cannot be empty.")
    
    return redirect('tenders:tender_detail', pk=pk)


@login_required
@superuser_or_permission('tenders.can_manage_tenders')
@require_POST
def toggle_source(request, pk):
    """Toggle a tender source between active and paused states."""
    
    source = get_object_or_404(TenderSource, pk=pk)
    
    if source.status == 'ACTIVE':
        source.status = 'PAUSED'
        messages.success(request, f"Source '{source.name}' has been paused.")
    else:
        source.status = 'ACTIVE'
        messages.success(request, f"Source '{source.name}' has been activated.")
    
    source.save(update_fields=['status'])
    
    return redirect('tenders:source_detail', pk=pk)
