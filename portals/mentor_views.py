"""
Mentor Portal Views

Portal views for host employer mentors to manage their assigned learners,
submit attendance records, review logbook entries, and communicate with
workplace officers and facilitators.
"""
import json
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from corporate.models import (
    HostMentor,
    WorkplacePlacement,
    CorporateClient,
)
from learners.models import (
    Learner,
    WorkplaceAttendance,
    WorkplaceLogbookEntry,
    WorkplaceModuleCompletion,
    DisciplinaryRecord,
    DisciplinaryAction,
    LearnerSupportNote,
)
from core.models import (
    MessageThread,
    Message,
    ThreadParticipant,
    Notification,
)


def get_mentor_context(user):
    """
    Get the HostMentor profile for the current user.
    Superusers can access as any mentor (returns first available mentor for demo).
    """
    # Superusers can access mentor portal - return first available mentor for demo
    if user.is_superuser:
        mentor = HostMentor.objects.select_related(
            'host', 'user'
        ).filter(is_active=True).first()
        if mentor:
            return mentor
        # If no mentors exist, create a dummy context dict for superusers
        return type('SuperuserMentor', (), {
            'id': 0,
            'user': user,
            'host': None,
            'is_superuser_view': True,
            '__str__': lambda self: 'Admin View',
        })()
    
    try:
        mentor = HostMentor.objects.select_related(
            'host', 'user'
        ).get(user=user, is_active=True)
        return mentor
    except HostMentor.DoesNotExist:
        return None


@login_required
def mentor_dashboard(request):
    """
    Mentor dashboard showing assigned learners, pending tasks, and notifications.
    """
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    # Get today's date for date calculations
    today = timezone.now().date()
    
    # Get active placements for this mentor
    placements = WorkplacePlacement.objects.filter(
        mentor=mentor,
        status='ACTIVE'
    ).select_related('learner', 'enrollment', 'enrollment__qualification')

    # Count pending logbook entries requiring review
    pending_logbooks = WorkplaceLogbookEntry.objects.filter(
        placement__mentor=mentor,
        mentor_signed=False,
        learner_signed=True
    ).count()
    
    # Count unverified attendance records (last 7 days)
    seven_days_ago = today - timedelta(days=7)
    unverified_attendance = WorkplaceAttendance.objects.filter(
        placement__mentor=mentor,
        date__gte=seven_days_ago,
        mentor_verified=False
    ).count()

    # Get recent attendance entries
    first_of_month = today.replace(day=1)
    recent_attendance = WorkplaceAttendance.objects.filter(
        placement__mentor=mentor,
        date__gte=first_of_month
    ).order_by('-date')[:10]

    # Get unread messages count (messages where user hasn't marked as read in read_by JSONField)
    user_id_str = str(request.user.id)
    unread_messages = Message.objects.filter(
        thread__participants__user=request.user
    ).exclude(sender=request.user).exclude(
        read_by__has_key=user_id_str
    ).count()
    
    # Get recent notifications
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # Calculate attendance stats for current month
    attendance_stats = WorkplaceAttendance.objects.filter(
        placement__mentor=mentor,
        date__gte=first_of_month
    ).values('attendance_type').annotate(count=Count('id'))
    
    stats = {item['attendance_type']: item['count'] for item in attendance_stats}
    
    context = {
        'mentor': mentor,
        'placements': placements,
        'pending_logbooks': pending_logbooks,
        'unverified_attendance': unverified_attendance,
        'recent_attendance': recent_attendance,
        'unread_messages': unread_messages,
        'notifications': notifications,
        'attendance_stats': stats,
        'today': today,
    }
    
    return render(request, 'portals/mentor/dashboard.html', context)


@login_required
def learner_list(request):
    """List all learners assigned to this mentor."""
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    placements = WorkplacePlacement.objects.filter(
        mentor=mentor
    ).select_related(
        'learner', 'enrollment', 'enrollment__qualification', 'campus'
    ).order_by('-status', 'learner__last_name')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        placements = placements.filter(status=status_filter.upper())
    
    context = {
        'mentor': mentor,
        'placements': placements,
        'status_filter': status_filter,
    }
    
    return render(request, 'portals/mentor/learner_list.html', context)


@login_required
def learner_detail(request, placement_id):
    """View detailed information about a specific learner placement."""
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    placement = get_object_or_404(
        WorkplacePlacement.objects.select_related(
            'learner', 'enrollment', 'enrollment__qualification', 'campus', 'workplace_officer', 'lead_employer'
        ),
        id=placement_id,
        mentor=mentor
    )
    
    learner = placement.learner
    
    # Get recent attendance
    recent_attendance = WorkplaceAttendance.objects.filter(
        placement=placement
    ).order_by('-date')[:30]
    
    # Get logbook entries
    logbook_entries = WorkplaceLogbookEntry.objects.filter(
        placement=placement
    ).order_by('-year', '-month')
    
    # Get module completions
    module_completions = WorkplaceModuleCompletion.objects.filter(
        placement=placement
    ).order_by('-completion_date')
    
    # Get disciplinary records
    disciplinary = DisciplinaryRecord.objects.filter(
        learner=learner,
        placement=placement
    ).order_by('-date_opened')
    
    context = {
        'mentor': mentor,
        'placement': placement,
        'learner': learner,
        'recent_attendance': recent_attendance,
        'logbook_entries': logbook_entries,
        'module_completions': module_completions,
        'disciplinary_records': disciplinary,
    }
    
    return render(request, 'portals/mentor/learner_detail.html', context)


@login_required
def attendance_entry(request, placement_id):
    """
    Enter or view attendance for a specific learner placement.
    Supports bulk entry for a date range.
    """
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    placement = get_object_or_404(
        WorkplacePlacement,
        id=placement_id,
        mentor=mentor
    )

    if request.method == 'POST':
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

        entries = data.get('entries', [])
        created_count = 0
        updated_count = 0
        
        for entry in entries:
            try:
                entry_date = date.fromisoformat(entry['date'])
                attendance_type = entry['type']
                time_in = entry.get('time_in') or None
                time_out = entry.get('time_out') or None
                hours = entry.get('hours_worked') or None
                notes = entry.get('notes', '')
                
                obj, created = WorkplaceAttendance.objects.update_or_create(
                    placement=placement,
                    date=entry_date,
                    defaults={
                        'attendance_type': attendance_type,
                        'time_in': time_in,
                        'time_out': time_out,
                        'hours_worked': hours,
                        'notes': notes,
                        'recorded_by': request.user,
                        'campus': placement.campus,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                    
            except (KeyError, ValueError) as e:
                continue
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'created': created_count,
                'updated': updated_count,
            })
        
        messages.success(request, f"Saved {created_count + updated_count} attendance entries.")
        return redirect('portal:mentor_attendance_entry', placement_id=placement_id)
    
    # GET - display attendance form
    # Default to current week
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Get date range from query params
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    if start_date:
        try:
            week_start = date.fromisoformat(start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            week_end = date.fromisoformat(end_date)
        except ValueError:
            pass
    
    # Get existing attendance for this range
    existing = WorkplaceAttendance.objects.filter(
        placement=placement,
        date__gte=week_start,
        date__lte=week_end
    )
    
    existing_dict = {a.date.isoformat(): a for a in existing}
    
    # Build date range for display
    date_range = []
    current = week_start
    while current <= week_end:
        attendance = existing_dict.get(current.isoformat())
        date_range.append({
            'date': current,
            'is_weekend': current.weekday() >= 5,
            'attendance': attendance,
        })
        current += timedelta(days=1)
    
    context = {
        'mentor': mentor,
        'placement': placement,
        'date_range': date_range,
        'week_start': week_start,
        'week_end': week_end,
        'attendance_types': WorkplaceAttendance.ATTENDANCE_TYPES,
    }
    
    return render(request, 'portals/mentor/attendance_entry.html', context)


@login_required
def attendance_calendar(request, placement_id):
    """
    View attendance in a calendar format for a specific placement.
    """
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    placement = get_object_or_404(
        WorkplacePlacement,
        id=placement_id,
        mentor=mentor
    )

    # Get month from query params or default to current
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # Get attendance for this month
    attendance = WorkplaceAttendance.objects.filter(
        placement=placement,
        date__year=year,
        date__month=month
    )
    
    attendance_dict = {a.date.day: a for a in attendance}
    
    # Build calendar data
    _, days_in_month = monthrange(year, month)
    first_day = date(year, month, 1)
    
    calendar_weeks = []
    week = [None] * first_day.weekday()  # Padding for first week
    
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        week.append({
            'day': day,
            'date': d,
            'is_weekend': d.weekday() >= 5,
            'attendance': attendance_dict.get(day),
        })
        
        if len(week) == 7:
            calendar_weeks.append(week)
            week = []
    
    if week:
        week.extend([None] * (7 - len(week)))  # Padding for last week
        calendar_weeks.append(week)
    
    # Navigation
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    context = {
        'mentor': mentor,
        'placement': placement,
        'calendar_weeks': calendar_weeks,
        'year': year,
        'month': month,
        'month_name': date(year, month, 1).strftime('%B'),
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
    }
    
    return render(request, 'portals/mentor/attendance_calendar.html', context)


@login_required
def logbook_list(request):
    """List all logbook entries requiring mentor review."""
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    logbooks = WorkplaceLogbookEntry.objects.filter(
        placement__mentor=mentor
    ).select_related(
        'placement', 'placement__learner', 'placement__enrollment', 'placement__enrollment__qualification'
    ).order_by('-year', '-month')
    
    # Filter by status
    status_filter = request.GET.get('status', 'pending')
    if status_filter == 'pending':
        logbooks = logbooks.filter(mentor_signed=False, learner_signed=True)
    elif status_filter == 'approved':
        logbooks = logbooks.filter(mentor_signed=True)
    
    paginator = Paginator(logbooks, 20)
    page = request.GET.get('page', 1)
    logbooks = paginator.get_page(page)
    
    context = {
        'mentor': mentor,
        'logbooks': logbooks,
        'status_filter': status_filter,
    }
    
    return render(request, 'portals/mentor/logbook_list.html', context)


@login_required
def logbook_detail(request, logbook_id):
    """View and review a specific logbook entry."""
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    logbook = get_object_or_404(
        WorkplaceLogbookEntry.objects.select_related(
            'placement', 'placement__learner', 'placement__enrollment', 'placement__enrollment__qualification'
        ),
        id=logbook_id,
        placement__mentor=mentor
    )
    
    # Get related module completions for this period
    month_start = logbook.month_start_date
    month_end = logbook.month_end_date
    modules = WorkplaceModuleCompletion.objects.filter(
        placement=logbook.placement,
        completed_date__lte=month_end,
        completed_date__gte=month_start
    )
    
    # Get attendance summary for this period
    attendance = WorkplaceAttendance.objects.filter(
        placement=logbook.placement,
        date__gte=month_start,
        date__lte=month_end
    )
    
    attendance_summary = {}
    for record in attendance:
        att_type = record.get_attendance_type_display()
        attendance_summary[att_type] = attendance_summary.get(att_type, 0) + 1
    
    context = {
        'mentor': mentor,
        'logbook': logbook,
        'modules': modules,
        'attendance': attendance,
        'attendance_summary': attendance_summary,
    }
    
    return render(request, 'portals/mentor/logbook_detail.html', context)


@login_required
@require_POST
def logbook_sign(request, logbook_id):
    """Sign off on a logbook entry."""
    mentor = get_mentor_context(request.user)
    if not mentor:
        return JsonResponse({'error': 'No mentor access'}, status=403)
    
    logbook = get_object_or_404(
        WorkplaceLogbookEntry,
        id=logbook_id,
        placement__mentor=mentor
    )
    
    data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    
    action = data.get('action', 'approve')
    comments = data.get('comments', '')
    
    if action == 'approve':
        logbook.mentor_signed = True
        logbook.mentor_signed_date = timezone.now()
        logbook.mentor_comments = comments
        
        # If facilitator has already signed, mark as approved
        if logbook.facilitator_signed:
            logbook.status = 'APPROVED'
        
        logbook.save()
        
        # Send notification to learner
        from core.services.notifications import NotificationService
        NotificationService.send_notification(
            user=logbook.placement.learner.user,
            title="Logbook Approved by Mentor",
            message=f"Your logbook for {logbook.month_end_date.strftime('%B %Y')} has been approved by your mentor.",
            notification_type='LOGBOOK',
            related_object=logbook,
            campus=logbook.placement.campus
        )
        
        return JsonResponse({'success': True, 'status': logbook.status})
    
    elif action == 'reject':
        logbook.status = 'RETURNED'
        logbook.mentor_comments = comments
        logbook.save()
        
        # Send notification to learner
        from core.services.notifications import NotificationService
        NotificationService.send_notification(
            user=logbook.placement.learner.user,
            title="Logbook Returned for Revision",
            message=f"Your logbook for {logbook.month_end_date.strftime('%B %Y')} has been returned. Please review mentor comments.",
            notification_type='LOGBOOK',
            related_object=logbook,
            campus=logbook.placement.campus
        )
        
        return JsonResponse({'success': True, 'status': 'RETURNED'})
    
    return JsonResponse({'error': 'Invalid action'}, status=400)


@login_required
def module_completions(request, placement_id):
    """View and add module completions for a learner."""
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    placement = get_object_or_404(
        WorkplacePlacement.objects.select_related('learner', 'enrollment', 'enrollment__qualification'),
        id=placement_id,
        mentor=mentor
    )

    if request.method == 'POST':
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST

        module_code = data.get('module_code')
        module_name = data.get('module_name')
        completion_date = data.get('completion_date')
        notes = data.get('notes', '')
        
        try:
            completion_date = date.fromisoformat(completion_date)
        except (ValueError, TypeError):
            completion_date = timezone.now().date()
        
        completion = WorkplaceModuleCompletion.objects.create(
            placement=placement,
            module_code=module_code,
            module_name=module_name,
            completion_date=completion_date,
            mentor_verified=True,
            mentor_verified_date=timezone.now(),
            notes=notes,
            campus=placement.campus,
        )
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'id': completion.id,
            })
        
        messages.success(request, f"Module completion recorded: {module_name}")
        return redirect('portal:mentor_modules', placement_id=placement_id)
    
    # GET - list completions
    completions = WorkplaceModuleCompletion.objects.filter(
        placement=placement
    ).order_by('-completion_date')
    
    context = {
        'mentor': mentor,
        'placement': placement,
        'completions': completions,
    }
    
    return render(request, 'portals/mentor/module_completions.html', context)


@login_required
def messages_inbox(request):
    """View message threads for the mentor."""
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    threads = MessageThread.objects.filter(
        participants__user=request.user
    ).select_related().order_by('-updated_at')
    
    # Mark unread count per thread
    user_id_str = str(request.user.id)
    for thread in threads:
        thread.unread_count = Message.objects.filter(
            thread=thread
        ).exclude(sender=request.user).exclude(
            read_by__has_key=user_id_str
        ).count()
    
    context = {
        'mentor': mentor,
        'threads': threads,
    }
    
    return render(request, 'portals/mentor/messages_inbox.html', context)


@login_required
def message_thread(request, thread_id):
    """View a specific message thread."""
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    thread = get_object_or_404(
        MessageThread,
        id=thread_id,
        participants__user=request.user
    )
    
    # Mark messages as read using the model's method
    user_id_str = str(request.user.id)
    unread_messages = Message.objects.filter(
        thread=thread
    ).exclude(sender=request.user).exclude(
        read_by__has_key=user_id_str
    )
    for msg in unread_messages:
        msg.mark_read_by(request.user)
    
    if request.method == 'POST':
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        content = data.get('content', '').strip()
        
        if content:
            message = Message.objects.create(
                thread=thread,
                sender=request.user,
                content=content,
                campus=mentor.employer.campus if hasattr(mentor.employer, 'campus') else None,
            )
            
            thread.updated_at = timezone.now()
            thread.save()
            
            # Notify other participants
            from core.services.notifications import NotificationService
            for participant in thread.participants.exclude(user=request.user):
                NotificationService.trigger_message_received(
                    message=message,
                    recipient=participant.user
                )
            
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message_id': message.id,
                })
            
            return redirect('portal:mentor_thread', thread_id=thread_id)
    
    messages_list = Message.objects.filter(thread=thread).order_by('created_at')
    participants = thread.participants.select_related('user')
    
    context = {
        'mentor': mentor,
        'thread': thread,
        'messages': messages_list,
        'participants': participants,
    }
    
    return render(request, 'portals/mentor/message_thread.html', context)


@login_required
def new_message(request, placement_id=None):
    """Start a new message thread."""
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    placement = None
    if placement_id:
        placement = get_object_or_404(
            WorkplacePlacement,
            id=placement_id,
            mentor=mentor
        )

    if request.method == 'POST':
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        
        subject = data.get('subject', '')
        content = data.get('content', '').strip()
        recipient_ids = data.get('recipients', [])
        
        if not content:
            if request.content_type == 'application/json':
                return JsonResponse({'error': 'Content is required'}, status=400)
            messages.error(request, "Message content is required.")
            return redirect('portal:mentor_new_message')
        
        with transaction.atomic():
            # Create thread
            thread = MessageThread.objects.create(
                subject=subject or "New conversation",
                thread_type='GENERAL',
                related_placement=placement,
            )
            
            # Add mentor as participant
            ThreadParticipant.objects.create(
                thread=thread,
                user=request.user,
                role='MENTOR'
            )
            
            # Add other participants
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            for user_id in recipient_ids:
                try:
                    user = User.objects.get(id=user_id)
                    ThreadParticipant.objects.get_or_create(
                        thread=thread,
                        user=user,
                        defaults={'role': 'PARTICIPANT'}
                    )
                except User.DoesNotExist:
                    continue
            
            # Create first message
            message = Message.objects.create(
                thread=thread,
                sender=request.user,
                content=content,
            )
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'thread_id': thread.id,
            })
        
        return redirect('portal:mentor_thread', thread_id=thread.id)
    
    # GET - show form with potential recipients
    potential_recipients = []
    
    if placement:
        # Learner
        if placement.learner.user:
            potential_recipients.append({
                'id': placement.learner.user.id,
                'name': placement.learner.get_full_name(),
                'role': 'Learner',
            })
        
        # Workplace officer
        if placement.workplace_officer:
            potential_recipients.append({
                'id': placement.workplace_officer.id,
                'name': placement.workplace_officer.get_full_name(),
                'role': 'Workplace Officer',
            })
        
        # Facilitator - would need to look up from programme allocation
    
    context = {
        'mentor': mentor,
        'placement': placement,
        'potential_recipients': potential_recipients,
    }
    
    return render(request, 'portals/mentor/new_message.html', context)


# API Endpoints for offline sync

@login_required
def api_attendance_sync(request):
    """
    Sync attendance data from offline storage.
    Accepts batch of attendance entries and returns sync status.
    """
    mentor = get_mentor_context(request.user)
    if not mentor:
        return JsonResponse({'error': 'No mentor access'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    entries = data.get('entries', [])
    results = []
    
    for entry in entries:
        try:
            placement = WorkplacePlacement.objects.get(
                id=entry['placement_id'],
                mentor=mentor
            )

            entry_date = date.fromisoformat(entry['date'])
            
            obj, created = WorkplaceAttendance.objects.update_or_create(
                placement=placement,
                date=entry_date,
                defaults={
                    'attendance_type': entry['type'],
                    'time_in': entry.get('time_in'),
                    'time_out': entry.get('time_out'),
                    'hours_worked': entry.get('hours_worked'),
                    'notes': entry.get('notes', ''),
                    'recorded_by': request.user,
                    'campus': placement.campus,
                }
            )
            
            results.append({
                'client_id': entry.get('client_id'),
                'server_id': obj.id,
                'status': 'created' if created else 'updated',
            })
            
        except (WorkplacePlacement.DoesNotExist, KeyError, ValueError) as e:
            results.append({
                'client_id': entry.get('client_id'),
                'status': 'error',
                'error': str(e),
            })
    
    return JsonResponse({
        'success': True,
        'results': results,
        'synced_at': timezone.now().isoformat(),
    })


@login_required
def api_placements(request):
    """Get placements data for offline caching."""
    mentor = get_mentor_context(request.user)
    if not mentor:
        return JsonResponse({'error': 'No mentor access'}, status=403)
    
    placements = WorkplacePlacement.objects.filter(
        mentor=mentor,
        status='ACTIVE'
    ).select_related('learner', 'enrollment', 'enrollment__qualification')

    data = []
    for p in placements:
        data.append({
            'id': p.id,
            'learner': {
                'id': p.learner.id,
                'learner_number': p.learner.learner_number,
                'name': p.learner.get_full_name(),
            },
            'programme': {
                'id': p.enrollment.qualification.id,
                'name': str(p.enrollment.qualification),
            } if p.enrollment and p.enrollment.qualification else None,
            'start_date': p.start_date.isoformat() if p.start_date else None,
            'end_date': p.end_date.isoformat() if p.end_date else None,
        })
    
    return JsonResponse({
        'placements': data,
        'fetched_at': timezone.now().isoformat(),
    })


# =====================================================
# DIGITAL SIGNATURE CAPTURE FOR MENTORS
# =====================================================

@login_required
def mentor_signature(request):
    """
    Digital signature capture for mentors.
    Signatures are locked after first capture and can only be modified by admin.
    """
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    # Handle superuser view
    if getattr(mentor, 'is_superuser_view', False):
        messages.warning(request, 'Signature capture not available in admin view mode.')
        return redirect('portals:mentor_dashboard')
    
    context = {
        'mentor': mentor,
        'signature_locked': mentor.signature_locked,
        'has_signature': bool(mentor.signature),
    }
    
    if mentor.signature:
        context['signature_url'] = mentor.signature.url
        context['signature_captured_at'] = mentor.signature_captured_at
    
    if request.method == 'POST':
        from core.services.signature_service import SignatureService
        
        # Check if already locked
        if mentor.signature_locked:
            messages.error(request, 'Your signature is locked and cannot be changed. Contact admin for assistance.')
            return redirect('portals:mentor_signature')
        
        # Get signature data
        signature_data = request.POST.get('signature_data', '')
        consent_given = request.POST.get('popia_consent') == 'on'
        
        if not signature_data:
            messages.error(request, 'Please provide your signature.')
            return redirect('portals:mentor_signature')
        
        if not consent_given:
            messages.error(request, 'You must accept the POPIA consent to proceed.')
            return redirect('portals:mentor_signature')
        
        # Capture signature
        service = SignatureService()
        success, message = service.capture_signature_for_mentor(
            mentor=mentor,
            base64_data=signature_data,
            request=request,
            consent_given=consent_given
        )
        
        if success:
            messages.success(request, 'Your digital signature has been captured and locked successfully.')
        else:
            messages.error(request, message)
        
        return redirect('portals:mentor_signature')
    
    return render(request, 'portals/mentor/signature.html', context)


@login_required
def mentor_signature_api(request):
    """
    API endpoint for mentor signature capture (AJAX).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    from core.services.signature_service import SignatureService
    
    mentor = get_mentor_context(request.user)
    if not mentor or getattr(mentor, 'is_superuser_view', False):
        return JsonResponse({'error': 'No mentor access'}, status=403)
    
    try:
        data = json.loads(request.body)
        signature_data = data.get('signature_data', '')
        consent_given = data.get('popia_consent', False)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    service = SignatureService()
    success, message = service.capture_signature_for_mentor(
        mentor=mentor,
        base64_data=signature_data,
        request=request,
        consent_given=consent_given
    )
    
    if success:
        return JsonResponse({
            'success': True,
            'message': message,
            'signature_url': mentor.signature.url if mentor.signature else None,
            'locked': mentor.signature_locked
        })
    else:
        return JsonResponse({'success': False, 'error': message}, status=400)
