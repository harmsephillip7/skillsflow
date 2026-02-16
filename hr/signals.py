"""
HR Signals for SkillsFlow ERP
Handles automatic position history tracking and other HR-related signals.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(pre_save, sender='hr.StaffProfile')
def track_position_change(sender, instance, **kwargs):
    """
    Track position changes and create history records automatically.
    When a staff member's position or department changes, create a history entry.
    """
    from .models import StaffProfile, StaffPositionHistory
    
    if not instance.pk:
        # New staff profile - will create history in post_save
        return
    
    try:
        old_instance = StaffProfile.objects.get(pk=instance.pk)
    except StaffProfile.DoesNotExist:
        return
    
    # Check if position or department changed
    position_changed = old_instance.position_id != instance.position_id
    department_changed = old_instance.department_id != instance.department_id
    
    if position_changed or department_changed:
        # Close the current history record
        current_history = StaffPositionHistory.objects.filter(
            staff=instance,
            end_date__isnull=True,
            is_deleted=False
        ).first()
        
        if current_history:
            current_history.end_date = timezone.now().date()
            current_history.save()
        
        # Store flag to create new history in post_save
        instance._create_position_history = True
        instance._position_change_detected = True


@receiver(post_save, sender='hr.StaffProfile')
def create_position_history(sender, instance, created, **kwargs):
    """
    Create position history record for new staff or position changes.
    """
    from .models import StaffPositionHistory
    
    # Create history for new staff profile
    if created and instance.position and instance.department:
        StaffPositionHistory.objects.create(
            staff=instance,
            position=instance.position,
            department=instance.department,
            start_date=instance.date_joined,
            change_reason='HIRE',
            salary_at_time=instance.current_salary,
            created_by=instance.created_by
        )
        return
    
    # Create history for position/department change
    if getattr(instance, '_create_position_history', False) and instance.position and instance.department:
        # Determine change reason based on what changed
        change_reason = 'TRANSFER'  # Default
        
        StaffPositionHistory.objects.create(
            staff=instance,
            position=instance.position,
            department=instance.department,
            start_date=timezone.now().date(),
            change_reason=change_reason,
            salary_at_time=instance.current_salary,
            created_by=instance.updated_by
        )
        
        # Clean up the flag
        instance._create_position_history = False
        instance._position_change_detected = False
