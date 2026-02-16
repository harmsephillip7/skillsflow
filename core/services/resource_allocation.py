"""
Resource Allocation Service
Handles availability checking, conflict detection, and allocation management
for NOT resource requirements (facilitators, assessors, moderators, venues).
"""
from django.db import transaction
from django.utils import timezone
from datetime import date
from typing import Optional, List, Dict, Any, Tuple
from core.models import (
    ResourceAllocationPeriod, NOTResourceRequirement, TrainingNotification, User
)
from logistics.models import Venue


def check_resource_availability(
    allocation_type: str,
    start_date: date,
    end_date: date,
    user: Optional[User] = None,
    venue: Optional[Venue] = None,
    exclude_not_id: Optional[int] = None
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Check if a resource (user or venue) is available for a given period.
    
    Args:
        allocation_type: Type of allocation (FACILITATOR, ASSESSOR, MODERATOR, VENUE)
        start_date: Start of the allocation period
        end_date: End of the allocation period
        user: User to check (for human resources)
        venue: Venue to check (for venue resources)
        exclude_not_id: NOT ID to exclude from conflict check (for updates)
    
    Returns:
        Tuple of (is_available: bool, conflicts: List of conflict details)
    """
    is_available, conflicts = ResourceAllocationPeriod.check_availability(
        allocation_type=allocation_type,
        start_date=start_date,
        end_date=end_date,
        user=user,
        venue=venue,
        exclude_not_id=exclude_not_id
    )
    
    # Format conflicts for API response
    conflict_details = []
    for conflict in conflicts:
        conflict_details.append({
            'id': conflict.id,
            'not_reference': conflict.training_notification.reference_number,
            'not_title': conflict.training_notification.title,
            'not_id': conflict.training_notification.id,
            'start_date': conflict.start_date.isoformat(),
            'end_date': conflict.end_date.isoformat(),
            'resource_name': (
                conflict.user.get_full_name() if conflict.user 
                else (conflict.venue.name if conflict.venue else 'Unknown')
            ),
            'allocation_type': conflict.get_allocation_type_display(),
        })
    
    return is_available, conflict_details


def create_resource_allocation(
    resource_requirement: NOTResourceRequirement,
    start_date: date,
    end_date: date,
    user: Optional[User] = None,
    venue: Optional[Venue] = None,
    notes: str = '',
    force: bool = False
) -> Tuple[ResourceAllocationPeriod, List[Dict[str, Any]]]:
    """
    Create a resource allocation period for a NOT resource requirement.
    
    Args:
        resource_requirement: The NOTResourceRequirement being allocated
        start_date: Start of allocation period
        end_date: End of allocation period
        user: User being allocated (for human resources)
        venue: Venue being allocated (for venue resources)
        notes: Optional notes
        force: If True, create allocation even if conflicts exist (with warning)
    
    Returns:
        Tuple of (allocation: ResourceAllocationPeriod, conflicts: List)
    
    Raises:
        ValueError: If allocation_type doesn't match resource or required fields missing
    """
    # Determine allocation type from resource type
    resource_type = resource_requirement.resource_type
    if resource_type in ('FACILITATOR', 'ASSESSOR', 'MODERATOR'):
        allocation_type = resource_type
        if not user:
            raise ValueError(f'{resource_type} allocation requires a user')
    elif resource_type == 'VENUE':
        allocation_type = 'VENUE'
        if not venue:
            raise ValueError('Venue allocation requires a venue')
    else:
        raise ValueError(f'Resource type {resource_type} does not support allocation periods')
    
    # Check for conflicts
    is_available, conflicts = check_resource_availability(
        allocation_type=allocation_type,
        start_date=start_date,
        end_date=end_date,
        user=user,
        venue=venue,
        exclude_not_id=resource_requirement.training_notification_id
    )
    
    if not is_available and not force:
        raise ValueError(f'Resource has conflicts. Use force=True to override.')
    
    # Create the allocation
    allocation = ResourceAllocationPeriod.objects.create(
        resource_requirement=resource_requirement,
        training_notification=resource_requirement.training_notification,
        allocation_type=allocation_type,
        user=user,
        venue=venue,
        start_date=start_date,
        end_date=end_date,
        notes=notes
    )
    
    return allocation, conflicts


def update_resource_allocation(
    allocation: ResourceAllocationPeriod,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user: Optional[User] = None,
    venue: Optional[Venue] = None,
    notes: Optional[str] = None,
    force: bool = False
) -> Tuple[ResourceAllocationPeriod, List[Dict[str, Any]]]:
    """
    Update an existing resource allocation.
    
    Returns:
        Tuple of (allocation: ResourceAllocationPeriod, conflicts: List)
    """
    new_start = start_date or allocation.start_date
    new_end = end_date or allocation.end_date
    new_user = user if user is not None else allocation.user
    new_venue = venue if venue is not None else allocation.venue
    
    # Check for conflicts with new values
    is_available, conflicts = check_resource_availability(
        allocation_type=allocation.allocation_type,
        start_date=new_start,
        end_date=new_end,
        user=new_user,
        venue=new_venue,
        exclude_not_id=allocation.training_notification_id
    )
    
    # Also exclude the current allocation
    conflicts = [c for c in conflicts if c.get('id') != allocation.id]
    is_available = len(conflicts) == 0
    
    if not is_available and not force:
        raise ValueError(f'Resource has conflicts. Use force=True to override.')
    
    # Update the allocation
    allocation.start_date = new_start
    allocation.end_date = new_end
    if user is not None:
        allocation.user = new_user
    if venue is not None:
        allocation.venue = new_venue
    if notes is not None:
        allocation.notes = notes
    
    allocation.save()
    
    return allocation, conflicts


def remove_resource_allocation(resource_requirement: NOTResourceRequirement) -> int:
    """
    Remove all allocation periods for a resource requirement.
    Called when a resource is deallocated or status changes from ALLOCATED.
    
    Returns:
        Number of allocations deleted
    """
    deleted_count, _ = ResourceAllocationPeriod.objects.filter(
        resource_requirement=resource_requirement
    ).delete()
    return deleted_count


def get_user_allocations(
    user: User,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    include_archived: bool = False
) -> List[ResourceAllocationPeriod]:
    """
    Get all allocations for a user within a date range.
    """
    allocations = ResourceAllocationPeriod.objects.filter(user=user)
    
    if not include_archived:
        allocations = allocations.filter(is_archived=False)
    
    if start_date:
        allocations = allocations.filter(end_date__gte=start_date)
    if end_date:
        allocations = allocations.filter(start_date__lte=end_date)
    
    return allocations.select_related(
        'training_notification', 'resource_requirement', 'venue', 'cohort'
    ).order_by('start_date')


def get_venue_allocations(
    venue: Venue,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    include_archived: bool = False
) -> List[ResourceAllocationPeriod]:
    """
    Get all allocations for a venue within a date range.
    """
    allocations = ResourceAllocationPeriod.objects.filter(venue=venue)
    
    if not include_archived:
        allocations = allocations.filter(is_archived=False)
    
    if start_date:
        allocations = allocations.filter(end_date__gte=start_date)
    if end_date:
        allocations = allocations.filter(start_date__lte=end_date)
    
    return allocations.select_related(
        'training_notification', 'resource_requirement', 'user', 'cohort'
    ).order_by('start_date')


def get_not_allocations(
    training_notification: TrainingNotification,
    include_archived: bool = False
) -> List[ResourceAllocationPeriod]:
    """
    Get all allocations for a training notification.
    """
    allocations = ResourceAllocationPeriod.objects.filter(
        training_notification=training_notification
    )
    
    if not include_archived:
        allocations = allocations.filter(is_archived=False)
    
    return allocations.select_related(
        'resource_requirement', 'user', 'venue', 'cohort'
    ).order_by('allocation_type', 'start_date')


def sync_allocation_with_requirement(
    resource_requirement: NOTResourceRequirement,
    force: bool = False
) -> Tuple[Optional[ResourceAllocationPeriod], List[Dict[str, Any]]]:
    """
    Sync allocation period with resource requirement status.
    Creates allocation if status is ALLOCATED, removes if not.
    
    Returns:
        Tuple of (allocation or None, conflicts list)
    """
    not_obj = resource_requirement.training_notification
    
    # Get project dates
    start_date = not_obj.planned_start_date or not_obj.created_at.date()
    end_date = not_obj.planned_end_date or (not_obj.planned_start_date and 
        not_obj.planned_start_date.replace(year=not_obj.planned_start_date.year + 3))
    
    if not end_date:
        # Default to 3 years from start
        from datetime import timedelta
        end_date = start_date + timedelta(days=365 * 3)
    
    if resource_requirement.status == 'ALLOCATED':
        # Check if resource type supports allocations
        if resource_requirement.resource_type not in ('FACILITATOR', 'ASSESSOR', 'MODERATOR', 'VENUE'):
            return None, []
        
        # Check if allocation already exists
        existing = ResourceAllocationPeriod.objects.filter(
            resource_requirement=resource_requirement,
            is_archived=False
        ).first()
        
        if existing:
            # Update existing allocation
            return update_resource_allocation(
                allocation=existing,
                start_date=start_date,
                end_date=end_date,
                user=resource_requirement.assigned_user,
                force=force
            )
        else:
            # Create new allocation
            user = resource_requirement.assigned_user if resource_requirement.resource_type in ('FACILITATOR', 'ASSESSOR', 'MODERATOR') else None
            venue = None
            
            # For venue, we'd need to look up the venue somehow
            # This might need to be passed separately
            
            return create_resource_allocation(
                resource_requirement=resource_requirement,
                start_date=start_date,
                end_date=end_date,
                user=user,
                venue=venue,
                force=force
            )
    else:
        # Remove allocation if status is not ALLOCATED
        remove_resource_allocation(resource_requirement)
        return None, []
