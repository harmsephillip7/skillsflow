"""
Bulk verification view for mentors to efficiently verify multiple attendance records.
"""
import json
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render
from django.db import transaction
from django.utils import timezone

from corporate.models import WorkplacePlacement
from learners.models import WorkplaceAttendance


@login_required
def attendance_bulk_verify(request):
    """
    Bulk verification page for reviewing and approving multiple attendance records.
    """
    mentor = get_mentor_context(request.user)
    if not mentor:
        return HttpResponseForbidden("You don't have mentor access.")
    
    # Get filter parameters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    learner_filter = request.GET.get('learner')
    status_filter = request.GET.get('status', 'unverified')
    
    # Default date range: last 7 days
    if not date_from:
        date_from = (timezone.now().date() - timedelta(days=7)).isoformat()
    if not date_to:
        date_to = timezone.now().date().isoformat()
    
    # Build query
    attendance_qs = WorkplaceAttendance.objects.filter(
        placement__mentor=mentor,
        date__gte=date_from,
        date__lte=date_to
    ).select_related(
        'placement__learner',
        'placement__enrollment__qualification'
    ).order_by('-date', 'placement__learner__last_name')
    
    # Filter by verification status
    if status_filter == 'unverified':
        attendance_qs = attendance_qs.filter(mentor_verified=False)
    elif status_filter == 'verified':
        attendance_qs = attendance_qs.filter(mentor_verified=True)
    elif status_filter == 'with_gps':
        attendance_qs = attendance_qs.exclude(gps_latitude__isnull=True)
    elif status_filter == 'with_photo':
        attendance_qs = attendance_qs.exclude(photo='')
    
    # Filter by learner
    if learner_filter:
        attendance_qs = attendance_qs.filter(placement__learner__id=learner_filter)
    
    attendance_records = attendance_qs
    
    # Get list of learners for filter dropdown
    placements = WorkplacePlacement.objects.filter(
        mentor=mentor,
        status='ACTIVE'
    ).select_related('learner').order_by('learner__last_name')
    
    # Calculate summary stats
    total_records = attendance_records.count()
    unverified_count = attendance_records.filter(mentor_verified=False).count()
    verified_count = attendance_records.filter(mentor_verified=True).count()
    with_gps = attendance_records.exclude(gps_latitude__isnull=True).count()
    with_photo = attendance_records.exclude(photo='').count()
    
    context = {
        'mentor': mentor,
        'attendance_records': attendance_records,
        'placements': placements,
        'date_from': date_from,
        'date_to': date_to,
        'learner_filter': learner_filter,
        'status_filter': status_filter,
        'stats': {
            'total': total_records,
            'unverified': unverified_count,
            'verified': verified_count,
            'with_gps': with_gps,
            'with_photo': with_photo,
        }
    }
    
    return render(request, 'portals/mentor/attendance_bulk_verify.html', context)


@login_required
def attendance_bulk_verify_submit(request):
    """
    Process bulk verification of attendance records.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    mentor = get_mentor_context(request.user)
    if not mentor:
        return JsonResponse({'error': 'No mentor access'}, status=403)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    record_ids = data.get('record_ids', [])
    action = data.get('action', 'verify')  # verify or reject
    rejection_note = data.get('rejection_note', '')
    
    if not record_ids:
        return JsonResponse({'error': 'No records selected'}, status=400)
    
    # Verify mentor owns these records
    attendance_records = WorkplaceAttendance.objects.filter(
        id__in=record_ids,
        placement__mentor=mentor
    )
    
    if attendance_records.count() != len(record_ids):
        return JsonResponse({'error': 'Invalid record selection'}, status=403)
    
    with transaction.atomic():
        if action == 'verify':
            # Bulk verify
            updated = attendance_records.update(
                mentor_verified=True,
                mentor_verified_at=timezone.now(),
                mentor_verified_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'action': 'verified',
                'count': updated,
                'message': f'{updated} record(s) verified successfully'
            })
        
        elif action == 'reject':
            # Add rejection note and unverify
            for record in attendance_records:
                record.mentor_verified = False
                record.mentor_verified_at = None
                record.mentor_verified_by = None
                if rejection_note:
                    record.notes = (record.notes or '') + f"\n[REJECTED by mentor: {rejection_note}]"
                record.save()
            
            return JsonResponse({
                'success': True,
                'action': 'rejected',
                'count': attendance_records.count(),
                'message': f'{attendance_records.count()} record(s) marked for review'
            })
        
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)


def get_mentor_context(user):
    """
    Get the HostMentor profile for the current user.
    """
    from corporate.models import HostMentor
    
    if user.is_superuser:
        mentor = HostMentor.objects.select_related(
            'host', 'user'
        ).filter(is_active=True).first()
        if mentor:
            return mentor
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
