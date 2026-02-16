"""
Utilization Service
Calculates and tracks resource utilization across campuses.
Provides real-time utilization metrics for venues, facilitators, assessors, and moderators.

Capacity Logic:
- Each facilitator can handle 30 learners at a time
- A facilitator is "occupied" when they have an active INSTITUTIONAL phase in progress
- Campus capacity = (total facilitators) × 30
- Available capacity = (available facilitators) × 30
"""
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import date, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal

# Maximum learners per facilitator
LEARNERS_PER_FACILITATOR = 30


def calculate_campus_utilization(campus_id: int, date_range_start: Optional[date] = None, date_range_end: Optional[date] = None) -> Dict[str, Any]:
    """
    Calculate overall utilization metrics for a campus.
    
    Capacity is calculated based on:
    - Total facilitators × 30 = Total learner capacity
    - Occupied facilitators (with active INSTITUTIONAL phase) × 30 = Utilized capacity
    - Available capacity = Total - Utilized
    
    Returns:
        Dict with capacity, venue_utilization, facilitator_utilization, and summary stats
    """
    from core.models import ResourceAllocationPeriod
    from logistics.models import Venue, ScheduleSession, Cohort, CohortImplementationPhase
    from tenants.models import Campus
    from academics.models import Enrollment, PersonnelRegistration
    
    if not date_range_start:
        date_range_start = date.today()
    if not date_range_end:
        date_range_end = date.today() + timedelta(days=90)  # Next 90 days
    
    try:
        campus = Campus.objects.get(pk=campus_id)
    except Campus.DoesNotExist:
        return {'error': 'Campus not found'}
    
    # Get all active venues for this campus
    venues = Venue.objects.filter(campus_id=campus_id, is_active=True)
    total_venue_capacity = venues.aggregate(total=Sum('capacity'))['total'] or 0
    
    # Get active cohorts at this campus
    active_cohorts = Cohort.objects.filter(
        campus_id=campus_id,
        status__in=['ACTIVE', 'OPEN']
    )
    
    # Get current learner count
    current_learners = Enrollment.objects.filter(
        cohort__in=active_cohorts,
        status__in=['ACTIVE', 'ENROLLED']
    ).count()
    
    # =========================================================================
    # FACILITATOR CAPACITY CALCULATION
    # Each facilitator can handle 30 learners
    # A facilitator is "occupied" when they have an active INSTITUTIONAL phase
    # =========================================================================
    
    # Get all facilitators allocated to this campus (from PersonnelRegistration)
    campus_facilitator_ids = list(PersonnelRegistration.objects.filter(
        campuses=campus,
        personnel_type='FACILITATOR',
        is_active=True
    ).values_list('user_id', flat=True).distinct())
    
    total_facilitators = len(campus_facilitator_ids)
    total_facilitator_capacity = total_facilitators * LEARNERS_PER_FACILITATOR
    
    # Find facilitators currently occupied with INSTITUTIONAL phases
    # A facilitator is occupied if they have a cohort with an INSTITUTIONAL phase 
    # that is IN_PROGRESS and the phase dates overlap with our date range
    occupied_facilitator_ids = set()
    
    # Get cohorts at this campus with facilitators
    cohorts_with_facilitators = Cohort.objects.filter(
        campus_id=campus_id,
        facilitator_id__in=campus_facilitator_ids,
        status__in=['ACTIVE', 'OPEN']
    ).select_related('facilitator')
    
    for cohort in cohorts_with_facilitators:
        # Check if this cohort has an active INSTITUTIONAL phase overlapping our period
        has_active_institutional = CohortImplementationPhase.objects.filter(
            cohort_implementation_plan__cohort=cohort,
            phase_type='INSTITUTIONAL',
            status='IN_PROGRESS'
        ).filter(
            # Phase overlaps with our date range (check actual dates first, then planned)
            Q(actual_start__lte=date_range_end, actual_end__gte=date_range_start) |
            Q(actual_start__isnull=True, planned_start__lte=date_range_end, planned_end__gte=date_range_start)
        ).exists()
        
        if has_active_institutional and cohort.facilitator_id:
            occupied_facilitator_ids.add(cohort.facilitator_id)
    
    occupied_facilitators = len(occupied_facilitator_ids)
    available_facilitators = total_facilitators - occupied_facilitators
    
    utilized_capacity = occupied_facilitators * LEARNERS_PER_FACILITATOR
    available_capacity = available_facilitators * LEARNERS_PER_FACILITATOR
    
    # Calculate capacity utilization percentage
    capacity_utilization_pct = (utilized_capacity / total_facilitator_capacity * 100) if total_facilitator_capacity > 0 else 0
    
    # Venue utilization (learners vs venue seats)
    venue_utilization_pct = (current_learners / total_venue_capacity * 100) if total_venue_capacity > 0 else 0
    
    # Get venue allocations for the period (from NOT resources)
    venue_allocations = ResourceAllocationPeriod.objects.filter(
        allocation_type='VENUE',
        venue__campus_id=campus_id,
        is_archived=False,
        start_date__lte=date_range_end,
        end_date__gte=date_range_start
    ).select_related('venue', 'training_notification')
    
    # Get facilitator allocations from NOT
    facilitator_allocations = ResourceAllocationPeriod.objects.filter(
        allocation_type='FACILITATOR',
        training_notification__delivery_campus_id=campus_id,
        is_archived=False,
        start_date__lte=date_range_end,
        end_date__gte=date_range_start
    ).select_related('user', 'training_notification')
    
    # Calculate scheduled sessions in period
    scheduled_sessions = ScheduleSession.objects.filter(
        cohort__campus_id=campus_id,
        date__gte=date_range_start,
        date__lte=date_range_end,
        is_cancelled=False
    ).count()
    
    return {
        'campus': {
            'id': campus.id,
            'name': campus.name,
            'code': campus.code
        },
        'period': {
            'start': date_range_start.isoformat(),
            'end': date_range_end.isoformat()
        },
        'capacity': {
            'total_learner_capacity': total_facilitator_capacity,
            'utilized_capacity': utilized_capacity,
            'available_capacity': available_capacity,
            'utilization_percentage': round(capacity_utilization_pct, 1),
            'status': 'HIGH' if capacity_utilization_pct >= 80 else ('MEDIUM' if capacity_utilization_pct >= 50 else 'LOW')
        },
        'facilitators': {
            'total_count': total_facilitators,
            'occupied_count': occupied_facilitators,
            'available_count': available_facilitators,
            'learners_per_facilitator': LEARNERS_PER_FACILITATOR,
            'not_allocations_in_period': facilitator_allocations.count()
        },
        'venues': {
            'total_count': venues.count(),
            'total_capacity': total_venue_capacity,
            'current_learners': current_learners,
            'utilization_percentage': round(venue_utilization_pct, 1),
            'allocations_in_period': venue_allocations.count()
        },
        'cohorts': {
            'active_count': active_cohorts.count()
        },
        'sessions': {
            'scheduled_in_period': scheduled_sessions
        }
    }


def calculate_facilitator_utilization(user_id: int, date_range_start: Optional[date] = None, date_range_end: Optional[date] = None) -> Dict[str, Any]:
    """
    Calculate utilization metrics for a specific facilitator.
    
    Returns:
        Dict with allocation details, session counts, and workload metrics
    """
    from core.models import ResourceAllocationPeriod, User
    from logistics.models import ScheduleSession, Cohort
    
    if not date_range_start:
        date_range_start = date.today()
    if not date_range_end:
        date_range_end = date.today() + timedelta(days=90)
    
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return {'error': 'User not found'}
    
    # Get all allocations for this user
    allocations = ResourceAllocationPeriod.objects.filter(
        user_id=user_id,
        is_archived=False,
        start_date__lte=date_range_end,
        end_date__gte=date_range_start
    ).select_related('training_notification', 'cohort')
    
    # Get scheduled sessions
    sessions = ScheduleSession.objects.filter(
        facilitator_id=user_id,
        date__gte=date_range_start,
        date__lte=date_range_end,
        is_cancelled=False
    )
    
    # Calculate working days in period (excluding weekends)
    total_days = 0
    current = date_range_start
    while current <= date_range_end:
        if current.weekday() < 5:  # Monday to Friday
            total_days += 1
        current += timedelta(days=1)
    
    # Count scheduled days
    scheduled_days = sessions.values('date').distinct().count()
    
    # Get active cohorts where user is facilitator
    active_cohorts = Cohort.objects.filter(
        facilitator_id=user_id,
        status__in=['ACTIVE', 'OPEN']
    )
    
    utilization_pct = (scheduled_days / total_days * 100) if total_days > 0 else 0
    
    allocation_details = []
    for alloc in allocations:
        allocation_details.append({
            'id': alloc.id,
            'type': alloc.get_allocation_type_display(),
            'not_reference': alloc.training_notification.reference_number if alloc.training_notification else None,
            'not_title': alloc.training_notification.title if alloc.training_notification else None,
            'start_date': alloc.start_date.isoformat(),
            'end_date': alloc.end_date.isoformat(),
            'cohort': alloc.cohort.code if alloc.cohort else None
        })
    
    return {
        'user': {
            'id': user.id,
            'name': user.get_full_name(),
            'email': user.email
        },
        'period': {
            'start': date_range_start.isoformat(),
            'end': date_range_end.isoformat(),
            'total_working_days': total_days
        },
        'sessions': {
            'total_count': sessions.count(),
            'scheduled_days': scheduled_days,
            'utilization_percentage': round(utilization_pct, 1)
        },
        'allocations': {
            'total_count': allocations.count(),
            'details': allocation_details
        },
        'cohorts': {
            'active_count': active_cohorts.count(),
            'cohort_codes': list(active_cohorts.values_list('code', flat=True))
        }
    }


def calculate_venue_utilization(venue_id: int, date_range_start: Optional[date] = None, date_range_end: Optional[date] = None) -> Dict[str, Any]:
    """
    Calculate utilization metrics for a specific venue.
    
    Returns:
        Dict with booking details, capacity metrics, and availability
    """
    from core.models import ResourceAllocationPeriod
    from logistics.models import Venue, ScheduleSession
    
    if not date_range_start:
        date_range_start = date.today()
    if not date_range_end:
        date_range_end = date.today() + timedelta(days=90)
    
    try:
        venue = Venue.objects.select_related('campus').get(pk=venue_id)
    except Venue.DoesNotExist:
        return {'error': 'Venue not found'}
    
    # Get allocations for this venue
    allocations = ResourceAllocationPeriod.objects.filter(
        venue_id=venue_id,
        is_archived=False,
        start_date__lte=date_range_end,
        end_date__gte=date_range_start
    ).select_related('training_notification')
    
    # Get scheduled sessions
    sessions = ScheduleSession.objects.filter(
        venue_id=venue_id,
        date__gte=date_range_start,
        date__lte=date_range_end,
        is_cancelled=False
    )
    
    # Calculate working days in period
    total_days = 0
    current = date_range_start
    while current <= date_range_end:
        if current.weekday() < 5:
            total_days += 1
        current += timedelta(days=1)
    
    # Count scheduled days
    scheduled_days = sessions.values('date').distinct().count()
    
    # Count morning and afternoon sessions
    am_sessions = sessions.filter(start_time__lt='12:00:00').count()
    pm_sessions = sessions.filter(start_time__gte='12:00:00').count()
    
    utilization_pct = (scheduled_days / total_days * 100) if total_days > 0 else 0
    
    allocation_details = []
    for alloc in allocations:
        allocation_details.append({
            'id': alloc.id,
            'not_reference': alloc.training_notification.reference_number if alloc.training_notification else None,
            'not_title': alloc.training_notification.title if alloc.training_notification else None,
            'start_date': alloc.start_date.isoformat(),
            'end_date': alloc.end_date.isoformat()
        })
    
    return {
        'venue': {
            'id': venue.id,
            'name': venue.name,
            'code': venue.code,
            'venue_type': venue.get_venue_type_display(),
            'capacity': venue.capacity,
            'campus': venue.campus.name if venue.campus else None
        },
        'period': {
            'start': date_range_start.isoformat(),
            'end': date_range_end.isoformat(),
            'total_working_days': total_days
        },
        'sessions': {
            'total_count': sessions.count(),
            'scheduled_days': scheduled_days,
            'am_sessions': am_sessions,
            'pm_sessions': pm_sessions,
            'utilization_percentage': round(utilization_pct, 1)
        },
        'allocations': {
            'total_count': allocations.count(),
            'details': allocation_details
        }
    }


def get_all_campuses_utilization(date_range_start: Optional[date] = None, date_range_end: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    Get utilization summary for all active campuses.
    Includes capacity metrics based on facilitators × 30 learners.
    """
    from tenants.models import Campus
    
    campuses = Campus.objects.filter(is_active=True).order_by('name')
    
    results = []
    for campus in campuses:
        util = calculate_campus_utilization(campus.id, date_range_start, date_range_end)
        if 'error' not in util:
            results.append({
                'campus_id': campus.id,
                'campus_name': campus.name,
                'campus_code': campus.code,
                # Capacity metrics (based on facilitators × 30)
                'total_learner_capacity': util['capacity']['total_learner_capacity'],
                'utilized_capacity': util['capacity']['utilized_capacity'],
                'available_capacity': util['capacity']['available_capacity'],
                'capacity_utilization': util['capacity']['utilization_percentage'],
                'capacity_status': util['capacity']['status'],
                # Facilitator metrics
                'total_facilitators': util['facilitators']['total_count'],
                'occupied_facilitators': util['facilitators']['occupied_count'],
                'available_facilitators': util['facilitators']['available_count'],
                # Venue metrics
                'venue_utilization': util['venues']['utilization_percentage'],
                'active_cohorts': util['cohorts']['active_count'],
                'current_learners': util['venues']['current_learners'],
                'venue_capacity': util['venues']['total_capacity']
            })
    
    return results


def get_resource_availability_summary(campus_id: int, date_range_start: Optional[date] = None, date_range_end: Optional[date] = None) -> Dict[str, Any]:
    """
    Get a summary of available resources for a campus in a date range.
    Useful for planning new NOTs.
    """
    from core.models import ResourceAllocationPeriod, UserRole
    from logistics.models import Venue
    from tenants.models import Campus
    
    if not date_range_start:
        date_range_start = date.today()
    if not date_range_end:
        date_range_end = date.today() + timedelta(days=90)
    
    try:
        campus = Campus.objects.get(pk=campus_id)
    except Campus.DoesNotExist:
        return {'error': 'Campus not found'}
    
    # Get all facilitators at this campus
    facilitator_roles = UserRole.objects.filter(
        role__code='FACILITATOR',
        is_active=True,
        campus_id=campus_id
    ).select_related('user')
    
    all_facilitators = set(r.user_id for r in facilitator_roles)
    
    # Get facilitators with allocations in the period
    allocated_facilitators = ResourceAllocationPeriod.objects.filter(
        allocation_type='FACILITATOR',
        user_id__in=all_facilitators,
        is_archived=False,
        start_date__lte=date_range_end,
        end_date__gte=date_range_start
    ).values('user_id').distinct()
    
    allocated_facilitator_ids = set(a['user_id'] for a in allocated_facilitators)
    available_facilitators = all_facilitators - allocated_facilitator_ids
    
    # Get venues at this campus
    venues = Venue.objects.filter(campus_id=campus_id, is_active=True)
    all_venue_ids = set(venues.values_list('id', flat=True))
    
    # Get venues with allocations in the period
    allocated_venues = ResourceAllocationPeriod.objects.filter(
        allocation_type='VENUE',
        venue_id__in=all_venue_ids,
        is_archived=False,
        start_date__lte=date_range_end,
        end_date__gte=date_range_start
    ).values('venue_id').distinct()
    
    allocated_venue_ids = set(a['venue_id'] for a in allocated_venues)
    available_venue_ids = all_venue_ids - allocated_venue_ids
    
    return {
        'campus': {
            'id': campus.id,
            'name': campus.name
        },
        'period': {
            'start': date_range_start.isoformat(),
            'end': date_range_end.isoformat()
        },
        'facilitators': {
            'total': len(all_facilitators),
            'allocated': len(allocated_facilitator_ids),
            'available': len(available_facilitators)
        },
        'venues': {
            'total': len(all_venue_ids),
            'allocated': len(allocated_venue_ids),
            'available': len(available_venue_ids),
            'available_capacity': venues.filter(id__in=available_venue_ids).aggregate(
                total=Sum('capacity')
            )['total'] or 0
        }
    }
