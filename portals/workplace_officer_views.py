"""
Workplace Officer Portal Views

Portal views for SkillsFlow workplace officers to monitor their assigned learners,
manage disciplinary processes, verify stipends, conduct workplace visits,
and provide support to learners.
"""
import json
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from corporate.models import (
    WorkplacePlacement,
    CorporateClient,
    HostMentor,
)
from learners.models import (
    Learner,
    WorkplaceAttendance,
    WorkplaceLogbookEntry,
    WorkplaceModuleCompletion,
    StipendCalculation,
    DisciplinaryRecord,
    DisciplinaryAction,
    LearnerSupportNote,
)
from core.models import (
    User,
    WorkplaceOfficerProfile,
    MessageThread,
    Message,
    ThreadParticipant,
    Notification,
)


def get_officer_context(user):
    """
    Get the WorkplaceOfficerProfile for the current user.
    Superusers can access as any officer (returns first available profile for demo).
    """
    # Superusers can access officer portal - return first available profile for demo
    if user.is_superuser:
        profile = WorkplaceOfficerProfile.objects.select_related(
            'user'
        ).filter(is_active=True).first()
        if profile:
            return profile
        # If no profiles exist, create one for the superuser
        profile, _ = WorkplaceOfficerProfile.objects.get_or_create(
            user=user,
            defaults={'is_active': True}
        )
        return profile
    
    try:
        profile = WorkplaceOfficerProfile.objects.select_related(
            'user'
        ).get(user=user, is_active=True)
        return profile
    except WorkplaceOfficerProfile.DoesNotExist:
        # Check if user has workplace officer role
        if user.role == 'WORKPLACE_OFFICER':
            # Create profile on-the-fly
            profile, _ = WorkplaceOfficerProfile.objects.get_or_create(
                user=user,
                defaults={'is_active': True}
            )
            return profile
        return None


@login_required
def officer_dashboard(request):
    """
    Workplace officer dashboard showing assigned learners, alerts, and pending tasks.
    """
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    # Get active placements assigned to this officer
    placements = WorkplacePlacement.objects.filter(
        workplace_officer=request.user,
        status='ACTIVE'
    ).select_related('learner', 'host', 'enrollment', 'enrollment__qualification', 'lead_employer')
    
    # Count metrics
    total_learners = placements.count()
    
    # Pending logbooks requiring facilitator sign-off
    pending_logbooks = WorkplaceLogbookEntry.objects.filter(
        placement__workplace_officer=request.user,
        facilitator_signed=False,
        mentor_signed=True
    ).count()
    
    # Active disciplinary cases
    active_disciplinary = DisciplinaryRecord.objects.filter(
        placement__workplace_officer=request.user,
        status__in=['OPEN', 'INVESTIGATION', 'HEARING_SCHEDULED']
    ).count()
    
    # Pending stipend verifications
    today = timezone.now().date()
    current_month = today.month
    current_year = today.year
    
    pending_stipends = StipendCalculation.objects.filter(
        placement__workplace_officer=request.user,
        month=current_month,
        year=current_year,
        status__in=['CALCULATED', 'PENDING_APPROVAL']
    ).count()
    
    # Recent support notes
    recent_notes = LearnerSupportNote.objects.filter(
        created_by=request.user
    ).select_related('learner', 'placement').order_by('-created_at')[:5]
    
    # Upcoming visits
    upcoming_visits = profile.workplace_visits.filter(
        visit_date__gte=today,
        status='SCHEDULED'
    ).order_by('visit_date')[:5] if hasattr(profile, 'workplace_visits') else []
    
    # Unread messages (messages where user hasn't marked as read)
    user_id_str = str(request.user.id)
    unread_messages = Message.objects.filter(
        thread__participants__user=request.user
    ).exclude(sender=request.user).exclude(
        read_by__has_key=user_id_str
    ).count()
    
    # Pending disputes requiring review
    from learners.models import StipendDispute
    pending_disputes = StipendDispute.objects.filter(
        status__in=['PENDING', 'UNDER_REVIEW', 'ESCALATED']
    ).count()
    
    overdue_disputes = [d for d in StipendDispute.objects.filter(
        status='PENDING'
    ) if d.is_overdue]
    overdue_dispute_count = len(overdue_disputes)
    
    # Notifications
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:10]
    
    # Attendance alerts - learners with too many absences
    month_start = today.replace(day=1)
    absence_alerts = []
    for placement in placements:
        absences = WorkplaceAttendance.objects.filter(
            placement=placement,
            date__gte=month_start,
            attendance_type__in=['ABSENT', 'UNPAID']
        ).count()
        
        if absences >= 3:
            absence_alerts.append({
                'placement': placement,
                'absences': absences,
            })
    
    # Get stats for template
    stats = {
        'total_placements': total_learners,
        'pending_visits': len(upcoming_visits) if upcoming_visits else 0,
        'pending_stipends': pending_stipends,
        'open_disciplinary': active_disciplinary,
        'pending_disputes': pending_disputes,
        'overdue_disputes': overdue_dispute_count,
    }
    
    # Get pending stipend objects for the template (not just count)
    pending_stipends_qs = StipendCalculation.objects.filter(
        placement__workplace_officer=request.user,
        month=current_month,
        year=current_year,
        status__in=['CALCULATED', 'PENDING_APPROVAL']
    ).select_related('placement', 'placement__learner')[:5]
    
    # Get open disciplinary cases
    open_cases = DisciplinaryRecord.objects.filter(
        placement__workplace_officer=request.user,
        status__in=['OPEN', 'INVESTIGATION', 'HEARING_SCHEDULED']
    ).select_related('placement', 'placement__learner')[:5]
    
    context = {
        'profile': profile,
        'recent_placements': placements[:10],
        'placements': placements[:10],
        'total_learners': total_learners,
        'pending_logbooks': pending_logbooks,
        'active_disciplinary': active_disciplinary,
        'pending_stipends': pending_stipends_qs,
        'recent_notes': recent_notes,
        'upcoming_visits': upcoming_visits,
        'unread_messages': unread_messages,
        'notifications': notifications,
        'absence_alerts': absence_alerts,
        'alerts': absence_alerts,  # Alias for template
        'open_cases': open_cases,
        'stats': stats,
        'today': today,
    }
    
    return render(request, 'portals/workplace_officer/dashboard.html', context)


@login_required
def placement_list(request):
    """List all placements assigned to this workplace officer."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    placements = WorkplacePlacement.objects.filter(
        workplace_officer=request.user
    ).select_related(
        'learner', 'host', 'host__employer', 'enrollment', 'enrollment__qualification', 'lead_employer', 'campus'
    ).order_by('status', 'learner__last_name')
    
    # Filters
    status_filter = request.GET.get('status', 'all')
    employer_filter = request.GET.get('employer')
    search = request.GET.get('q', '')
    
    if status_filter != 'all':
        placements = placements.filter(status=status_filter.upper())
    
    if employer_filter:
        placements = placements.filter(
            Q(host__employer_id=employer_filter) |
            Q(lead_employer_id=employer_filter)
        )
    
    if search:
        placements = placements.filter(
            Q(learner__first_name__icontains=search) |
            Q(learner__last_name__icontains=search) |
            Q(learner__learner_number__icontains=search)
        )
    
    # Get unique host employers for filter dropdown
    from corporate.models import HostEmployer
    host_employers = HostEmployer.objects.filter(
        placements__workplace_officer=request.user
    ).distinct()
    
    # Get unique lead employers for filter dropdown
    lead_employers = CorporateClient.objects.filter(
        lead_employer_placements__workplace_officer=request.user
    ).distinct()
    
    paginator = Paginator(placements, 25)
    page = request.GET.get('page', 1)
    placements = paginator.get_page(page)
    
    context = {
        'profile': profile,
        'placements': placements,
        'status_filter': status_filter,
        'employer_filter': employer_filter,
        'search': search,
        'host_employers': host_employers,
        'lead_employers': lead_employers,
    }
    
    return render(request, 'portals/workplace_officer/placements.html', context)


@login_required
def placement_detail(request, placement_id):
    """View comprehensive details about a specific placement."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    placement = get_object_or_404(
        WorkplacePlacement.objects.select_related(
            'learner', 'host', 'host__employer',
            'enrollment', 'enrollment__qualification', 'lead_employer', 'campus', 'leave_policy'
        ),
        id=placement_id,
        workplace_officer=request.user
    )
    
    learner = placement.learner
    
    # Get current month attendance
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    current_attendance = WorkplaceAttendance.objects.filter(
        placement=placement,
        date__gte=month_start
    ).order_by('-date')
    
    # Attendance summary
    attendance_summary = current_attendance.values('attendance_type').annotate(
        count=Count('id')
    )
    summary_dict = {s['attendance_type']: s['count'] for s in attendance_summary}
    
    # Logbook entries
    logbooks = WorkplaceLogbookEntry.objects.filter(
        placement=placement
    ).order_by('-year', '-month')[:6]
    
    # Module completions
    modules = WorkplaceModuleCompletion.objects.filter(
        placement=placement
    ).order_by('-completion_date')
    
    # Stipend history
    stipends = StipendCalculation.objects.filter(
        placement=placement
    ).order_by('-year', '-month')[:6]
    
    # Disciplinary records
    disciplinary = DisciplinaryRecord.objects.filter(
        learner=learner,
        placement=placement
    ).order_by('-opened_date')
    
    # Support notes
    support_notes = LearnerSupportNote.objects.filter(
        learner=learner,
        placement=placement
    ).order_by('-created_at')[:10]
    
    context = {
        'profile': profile,
        'placement': placement,
        'learner': learner,
        'current_attendance': current_attendance,
        'attendance_summary': summary_dict,
        'logbooks': logbooks,
        'modules': modules,
        'stipends': stipends,
        'disciplinary_records': disciplinary,
        'support_notes': support_notes,
        'today': today,
    }
    
    return render(request, 'portals/workplace_officer/placement_detail.html', context)


# Disciplinary Management

@login_required
def disciplinary_list(request):
    """List all disciplinary records for assigned placements."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    records = DisciplinaryRecord.objects.filter(
        placement__workplace_officer=request.user
    ).select_related(
        'learner', 'placement', 'placement__host__employer'
    ).order_by('-opened_date')
    
    # Filter by status
    status_filter = request.GET.get('status', 'active')
    if status_filter == 'active':
        records = records.filter(status__in=['OPEN', 'INVESTIGATION', 'HEARING_SCHEDULED'])
    elif status_filter != 'all':
        records = records.filter(status=status_filter.upper())
    
    paginator = Paginator(records, 20)
    page = request.GET.get('page', 1)
    records = paginator.get_page(page)
    
    # Get all placements for new case modal
    my_placements = WorkplacePlacement.objects.filter(
        workplace_officer=request.user,
        status='ACTIVE'
    ).select_related('learner', 'host')
    
    context = {
        'profile': profile,
        'records': records,
        'status_filter': status_filter,
        'my_placements': my_placements,
    }
    
    return render(request, 'portals/workplace_officer/disciplinary.html', context)


@login_required
def disciplinary_detail(request, record_id):
    """View a specific disciplinary record with all actions."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    record = get_object_or_404(
        DisciplinaryRecord.objects.select_related(
            'learner', 'placement', 'placement__host__employer',
            'opened_by', 'closed_by'
        ),
        id=record_id,
        placement__workplace_officer=request.user
    )
    
    actions = record.actions.select_related('issued_by').order_by('action_date')
    
    context = {
        'profile': profile,
        'record': record,
        'actions': actions,
        'action_types': DisciplinaryAction.ACTION_TYPES,
    }
    
    return render(request, 'portals/workplace_officer/disciplinary_detail.html', context)


@login_required
def disciplinary_create(request, placement_id):
    """Create a new disciplinary record."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    placement = get_object_or_404(
        WorkplacePlacement,
        id=placement_id,
        workplace_officer=request.user
    )
    
    if request.method == 'POST':
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        
        incident_date = data.get('incident_date')
        incident_type = data.get('incident_type')
        description = data.get('description', '')
        
        try:
            incident_date = date.fromisoformat(incident_date)
        except (ValueError, TypeError):
            incident_date = timezone.now().date()
        
        record = DisciplinaryRecord.objects.create(
            learner=placement.learner,
            placement=placement,
            opened_date=timezone.now().date(),
            incident_date=incident_date,
            incident_type=incident_type,
            description=description,
            status='OPEN',
            opened_by=request.user,
            campus=placement.campus,
        )
        
        # Notify relevant parties
        from core.services.notifications import NotificationService
        NotificationService.trigger_disciplinary_notice(
            record=record,
            action_type='CASE_OPENED',
            notify_learner=True
        )
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'record_id': record.id,
            })
        
        messages.success(request, "Disciplinary record created.")
        return redirect('portal:officer_disciplinary_detail', record_id=record.id)
    
    context = {
        'profile': profile,
        'placement': placement,
        'incident_types': DisciplinaryRecord.INCIDENT_TYPES,
    }
    
    return render(request, 'portals/workplace_officer/disciplinary_create.html', context)


@login_required
@require_POST
def disciplinary_action(request, record_id):
    """Add a disciplinary action to a record."""
    profile = get_officer_context(request.user)
    if not profile:
        return JsonResponse({'error': 'No officer access'}, status=403)
    
    record = get_object_or_404(
        DisciplinaryRecord,
        id=record_id,
        placement__workplace_officer=request.user
    )
    
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    
    action_type = data.get('action_type')
    action_date = data.get('action_date')
    notes = data.get('notes', '')
    
    try:
        action_date = date.fromisoformat(action_date)
    except (ValueError, TypeError):
        action_date = timezone.now().date()
    
    action = DisciplinaryAction.objects.create(
        disciplinary_record=record,
        action_type=action_type,
        action_date=action_date,
        notes=notes,
        issued_by=request.user,
        campus=record.campus,
    )
    
    # Update record status based on action
    if action_type == 'DISMISSAL':
        record.status = 'CLOSED'
        record.outcome = 'DISMISSED'
        record.date_closed = timezone.now().date()
        record.closed_by = request.user
        
        # Update placement status
        record.placement.status = 'TERMINATED'
        record.placement.actual_end_date = action_date
        record.placement.save()
        
    elif action_type == 'FINAL_WARNING':
        record.status = 'FINAL_WARNING_ISSUED'
    
    record.save()
    
    # Notify learner
    from core.services.notifications import NotificationService
    NotificationService.trigger_disciplinary_notice(
        record=record,
        action_type=action_type,
        notify_learner=True
    )
    
    if request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'action_id': action.id,
        })
    
    messages.success(request, f"Disciplinary action recorded: {action.get_action_type_display()}")
    return redirect('portal:officer_disciplinary_detail', record_id=record_id)


# Stipend Management

@login_required
def stipend_list(request):
    """List stipend calculations for review and verification."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    # Default to current month
    today = timezone.now().date()
    month_param = request.GET.get('month')
    year_param = request.GET.get('year')
    month = int(month_param) if month_param else today.month
    year = int(year_param) if year_param else today.year
    
    stipends = StipendCalculation.objects.filter(
        placement__workplace_officer=request.user,
        month=month,
        year=year
    ).select_related(
        'placement', 'placement__learner', 'placement__host__employer'
    ).order_by('status', 'placement__learner__last_name')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        stipends = stipends.filter(status=status_filter.upper())
    
    # Summary stats
    totals = stipends.aggregate(
        total_gross=Sum('gross_amount'),
        total_net=Sum('net_amount'),
        count=Count('id')
    )
    
    context = {
        'profile': profile,
        'stipends': stipends,
        'month': month,
        'year': year,
        'status_filter': status_filter,
        'totals': totals,
        'month_name': date(year, month, 1).strftime('%B %Y'),
    }
    
    return render(request, 'portals/workplace_officer/stipends.html', context)


@login_required
def stipend_detail(request, stipend_id):
    """View detailed stipend calculation breakdown."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    stipend = get_object_or_404(
        StipendCalculation.objects.select_related(
            'placement', 'placement__learner', 'placement__host__employer',
            'placement__leave_policy', 'approved_by'
        ),
        id=stipend_id,
        placement__workplace_officer=request.user
    )
    
    # Update verification statistics from attendance records
    stipend.update_verification_stats()
    
    # Get attendance records for this period
    month_start = date(stipend.year, stipend.month, 1)
    _, days_in_month = monthrange(stipend.year, stipend.month)
    month_end = date(stipend.year, stipend.month, days_in_month)
    
    attendance = WorkplaceAttendance.objects.filter(
        placement=stipend.placement,
        date__gte=month_start,
        date__lte=month_end
    ).select_related('placement__learner').order_by('date')
    
    context = {
        'profile': profile,
        'stipend': stipend,
        'attendance': attendance,
        'month_start': month_start,
        'month_end': month_end,
        'verification_percentage': stipend.verification_percentage,
        'can_finalize': stipend.can_finalize,
    }
    
    return render(request, 'portals/workplace_officer/stipend_detail.html', context)


@login_required
@require_POST
def stipend_verify(request, stipend_id):
    """Verify and approve a stipend calculation."""
    profile = get_officer_context(request.user)
    if not profile:
        return JsonResponse({'error': 'No officer access'}, status=403)
    
    stipend = get_object_or_404(
        StipendCalculation,
        id=stipend_id,
        placement__workplace_officer=request.user
    )
    
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    action = data.get('action', 'approve')
    notes = data.get('notes', '')
    
    if action == 'approve':
        # Update verification statistics before approving
        stipend.update_verification_stats()
        
        # Check if attendance is fully verified
        if not stipend.can_finalize:
            return JsonResponse({
                'error': f'Cannot approve: Only {stipend.verification_percentage}% of attendance records are verified. All attendance must be verified by both mentor and facilitator before approval.',
                'verification_percentage': stipend.verification_percentage,
                'dual_verified': stipend.dual_verified_records,
                'total_records': stipend.total_attendance_records,
            }, status=400)
        
        stipend.status = 'APPROVED'
        stipend.approved_by = request.user
        stipend.approved_at = timezone.now()
        stipend.notes = notes
        stipend.save()
        
        # Notify learner
        from core.services.notifications import NotificationService
        NotificationService.trigger_stipend_ready(stipend)
        
        return JsonResponse({'success': True, 'status': 'APPROVED'})
    
    elif action == 'recalculate':
        # Trigger recalculation
        from learners.services import StipendCalculator
        calculator = StipendCalculator(
            stipend.placement,
            stipend.month,
            stipend.year
        )
        new_stipend = calculator.calculate(save=True)
        
        # Update verification stats for new stipend
        new_stipend.update_verification_stats()
        
        return JsonResponse({
            'success': True,
            'stipend_id': new_stipend.id,
            'net_amount': str(new_stipend.net_amount),
            'verification_percentage': new_stipend.verification_percentage,
        })
    
    return JsonResponse({'error': 'Invalid action'}, status=400)


@login_required
def stipend_calculate_all(request):
    """Calculate stipends for all active placements for a month."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    if request.method == 'POST':
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        
        month = int(data.get('month', timezone.now().month))
        year = int(data.get('year', timezone.now().year))
        
        placements = WorkplacePlacement.objects.filter(
            workplace_officer=request.user,
            status='ACTIVE'
        )
        
        from learners.services import StipendCalculator
        calculations = StipendCalculator.calculate_for_period(
            placements, month, year, save=True
        )
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'calculated': len(calculations),
            })
        
        messages.success(request, f"Calculated stipends for {len(calculations)} placements.")
        return redirect('portal:officer_stipend_list')
    
    context = {
        'profile': profile,
        'today': timezone.now().date(),
    }
    
    return render(request, 'portals/workplace_officer/stipend_calculate.html', context)


# Support Notes

@login_required
def support_note_create(request, placement_id):
    """Create a support note for a learner."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    placement = get_object_or_404(
        WorkplacePlacement,
        id=placement_id,
        workplace_officer=request.user
    )
    
    if request.method == 'POST':
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        
        note_type = data.get('note_type', 'GENERAL')
        title = data.get('title', '')
        content = data.get('content', '')
        follow_up_date = data.get('follow_up_date')
        is_confidential = data.get('is_confidential', False)
        
        try:
            follow_up_date = date.fromisoformat(follow_up_date) if follow_up_date else None
        except ValueError:
            follow_up_date = None
        
        note = LearnerSupportNote.objects.create(
            learner=placement.learner,
            placement=placement,
            note_type=note_type,
            title=title,
            content=content,
            follow_up_required=bool(follow_up_date),
            follow_up_date=follow_up_date,
            is_confidential=is_confidential,
            created_by=request.user,
            campus=placement.campus,
        )
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'note_id': note.id,
            })
        
        messages.success(request, "Support note recorded.")
        return redirect('portal:officer_placement_detail', placement_id=placement_id)
    
    context = {
        'profile': profile,
        'placement': placement,
        'note_types': LearnerSupportNote.NOTE_TYPES,
    }
    
    return render(request, 'portals/workplace_officer/support_note_create.html', context)


@login_required
def support_note_list(request):
    """List all support notes created by this officer."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    notes = LearnerSupportNote.objects.filter(
        created_by=request.user
    ).select_related(
        'learner', 'placement', 'placement__host__employer'
    ).order_by('-created_at')
    
    # Filter for follow-ups
    filter_type = request.GET.get('filter', 'all')
    if filter_type == 'follow_up':
        notes = notes.filter(
            follow_up_required=True,
            follow_up_completed=False
        )
    elif filter_type == 'confidential':
        notes = notes.filter(is_confidential=True)
    
    paginator = Paginator(notes, 20)
    page = request.GET.get('page', 1)
    notes = paginator.get_page(page)
    
    # Get placements for new note modal
    my_placements = WorkplacePlacement.objects.filter(
        workplace_officer=request.user,
        status='ACTIVE'
    ).select_related('learner', 'host')
    
    context = {
        'profile': profile,
        'notes': notes,
        'filter_type': filter_type,
        'my_placements': my_placements,
    }
    
    return render(request, 'portals/workplace_officer/support_note_list.html', context)


# Logbook Review

@login_required
def logbook_list(request):
    """List logbook entries requiring facilitator review."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    logbooks = WorkplaceLogbookEntry.objects.filter(
        placement__workplace_officer=request.user
    ).select_related(
        'placement', 'placement__learner', 'placement__host__employer'
    ).order_by('-year', '-month')
    
    # Filter by status
    status_filter = request.GET.get('status', 'pending')
    if status_filter == 'pending':
        logbooks = logbooks.filter(
            mentor_signed=True,
            facilitator_signed=False
        )
    elif status_filter == 'approved':
        logbooks = logbooks.filter(facilitator_signed=True)
    
    paginator = Paginator(logbooks, 20)
    page = request.GET.get('page', 1)
    logbooks = paginator.get_page(page)
    
    context = {
        'profile': profile,
        'logbooks': logbooks,
        'status_filter': status_filter,
    }
    
    return render(request, 'portals/workplace_officer/logbook_list.html', context)


@login_required
@require_POST
def logbook_sign(request, logbook_id):
    """Sign off on a logbook as facilitator."""
    profile = get_officer_context(request.user)
    if not profile:
        return JsonResponse({'error': 'No officer access'}, status=403)
    
    logbook = get_object_or_404(
        WorkplaceLogbookEntry,
        id=logbook_id,
        placement__workplace_officer=request.user
    )
    
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    action = data.get('action', 'approve')
    comments = data.get('comments', '')
    
    if action == 'approve':
        logbook.facilitator_signed = True
        logbook.facilitator_signed_date = timezone.now()
        logbook.facilitator_comments = comments
        logbook.facilitator = request.user
        
        if logbook.mentor_signed:
            logbook.status = 'APPROVED'
        
        logbook.save()
        
        # Notify learner
        from core.services.notifications import NotificationService
        NotificationService.send_notification(
            user=logbook.placement.learner.user,
            title="Logbook Fully Approved",
            message=f"Your logbook for {logbook.month_end_date.strftime('%B %Y')} has been fully approved.",
            notification_type='LOGBOOK',
            related_object=logbook,
            campus=logbook.placement.campus
        )
        
        return JsonResponse({'success': True, 'status': 'APPROVED'})
    
    elif action == 'reject':
        logbook.status = 'RETURNED'
        logbook.facilitator_comments = comments
        logbook.save()
        
        return JsonResponse({'success': True, 'status': 'RETURNED'})
    
    return JsonResponse({'error': 'Invalid action'}, status=400)


# Messages

@login_required
def messages_inbox(request):
    """View message threads for the workplace officer."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    threads = MessageThread.objects.filter(
        participants__user=request.user
    ).select_related('related_placement').order_by('-updated_at')
    
    user_id_str = str(request.user.id)
    for thread in threads:
        thread.unread_count = Message.objects.filter(
            thread=thread
        ).exclude(sender=request.user).exclude(
            read_by__has_key=user_id_str
        ).count()
    
    context = {
        'profile': profile,
        'threads': threads,
    }
    
    return render(request, 'portals/workplace_officer/messages.html', context)


@login_required
def message_thread(request, thread_id):
    """View and respond to a message thread."""
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    thread = get_object_or_404(
        MessageThread,
        id=thread_id,
        participants__user=request.user
    )
    
    # Mark as read using the model's method
    user_id_str = str(request.user.id)
    unread_msgs = Message.objects.filter(
        thread=thread
    ).exclude(sender=request.user).exclude(
        read_by__has_key=user_id_str
    )
    for msg in unread_msgs:
        msg.mark_read_by(request.user)
    
    if request.method == 'POST':
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        content = data.get('content', '').strip()
        
        if content:
            message = Message.objects.create(
                thread=thread,
                sender=request.user,
                content=content,
            )
            
            thread.updated_at = timezone.now()
            thread.save()
            
            # Notify recipients
            from core.services.notifications import NotificationService
            for participant in thread.participants.exclude(user=request.user):
                NotificationService.trigger_message_received(
                    message=message,
                    recipient=participant.user
                )
            
            if request.content_type == 'application/json':
                return JsonResponse({'success': True, 'message_id': message.id})
            
            return redirect('portal:officer_thread', thread_id=thread_id)
    
    messages_list = Message.objects.filter(thread=thread).order_by('created_at')
    participants = thread.participants.select_related('user')
    
    context = {
        'profile': profile,
        'thread': thread,
        'messages': messages_list,
        'participants': participants,
    }
    
    return render(request, 'portals/workplace_officer/message_thread.html', context)


# =====================================================
# DIGITAL SIGNATURE CAPTURE FOR WORKPLACE OFFICERS
# =====================================================

@login_required
def officer_signature(request):
    """
    Digital signature capture for workplace officers.
    Signatures are locked after first capture and can only be modified by admin.
    """
    profile = get_officer_context(request.user)
    if not profile:
        return HttpResponseForbidden("You don't have workplace officer access.")
    
    context = {
        'profile': profile,
        'signature_locked': profile.signature_locked,
        'has_signature': bool(profile.signature),
    }
    
    if profile.signature:
        context['signature_url'] = profile.signature.url
        context['signature_captured_at'] = profile.signature_captured_at
    
    if request.method == 'POST':
        from core.services.signature_service import SignatureService
        
        # Check if already locked
        if profile.signature_locked:
            messages.error(request, 'Your signature is locked and cannot be changed. Contact admin for assistance.')
            return redirect('portals:officer_signature')
        
        # Get signature data
        signature_data = request.POST.get('signature_data', '')
        consent_given = request.POST.get('popia_consent') == 'on'
        
        if not signature_data:
            messages.error(request, 'Please provide your signature.')
            return redirect('portals:officer_signature')
        
        if not consent_given:
            messages.error(request, 'You must accept the POPIA consent to proceed.')
            return redirect('portals:officer_signature')
        
        # Capture signature
        service = SignatureService()
        success, message = service.capture_signature_for_officer(
            officer=profile,
            base64_data=signature_data,
            request=request,
            consent_given=consent_given
        )
        
        if success:
            messages.success(request, 'Your digital signature has been captured and locked successfully.')
        else:
            messages.error(request, message)
        
        return redirect('portals:officer_signature')
    
    return render(request, 'portals/workplace_officer/signature.html', context)


@login_required
def officer_signature_api(request):
    """
    API endpoint for officer signature capture (AJAX).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    from core.services.signature_service import SignatureService
    
    profile = get_officer_context(request.user)
    if not profile:
        return JsonResponse({'error': 'Workplace officer profile not found'}, status=403)
    
    try:
        data = json.loads(request.body)
        signature_data = data.get('signature_data', '')
        consent_given = data.get('popia_consent', False)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    service = SignatureService()
    success, message = service.capture_signature_for_officer(
        officer=profile,
        base64_data=signature_data,
        request=request,
        consent_given=consent_given
    )
    
    if success:
        return JsonResponse({
            'success': True,
            'message': message,
            'signature_url': profile.signature.url if profile.signature else None,
            'locked': profile.signature_locked
        })
    else:
        return JsonResponse({'success': False, 'error': message}, status=400)
