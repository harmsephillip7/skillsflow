"""
Trade Tests Signals

Handles automated notifications and workflow actions:
- Email/SMS when schedule date is set
- Auto-create next attempt booking on NOT_YET_COMPETENT
- Notify on competent result
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import TradeTestBooking, TradeTestResult


@receiver(pre_save, sender=TradeTestBooking)
def track_schedule_change(sender, instance, **kwargs):
    """Track if scheduled_date is being set for first time"""
    if instance.pk:
        try:
            old_instance = TradeTestBooking.objects.get(pk=instance.pk)
            instance._schedule_was_none = old_instance.scheduled_date is None
            instance._old_scheduled_date = old_instance.scheduled_date
        except TradeTestBooking.DoesNotExist:
            instance._schedule_was_none = True
            instance._old_scheduled_date = None
    else:
        instance._schedule_was_none = True
        instance._old_scheduled_date = None


@receiver(post_save, sender=TradeTestBooking)
def notify_schedule_set(sender, instance, created, **kwargs):
    """
    Send notification when scheduled_date is set.
    """
    # Check if schedule was just set (was None, now has value)
    schedule_just_set = (
        getattr(instance, '_schedule_was_none', False) and 
        instance.scheduled_date is not None
    )
    
    if schedule_just_set:
        # Update application status
        if instance.application:
            instance.application.status = 'SCHEDULED'
            instance.application.save(update_fields=['status'])
        
        # Send notification to learner
        send_schedule_notification(instance)


@receiver(post_save, sender=TradeTestResult)
def handle_result_saved(sender, instance, created, **kwargs):
    """
    Handle trade test result:
    - On NOT_YET_COMPETENT: Create next attempt booking if attempts remaining
    - On COMPETENT: Send success notification
    """
    if not created:
        return
    
    # Only process FINAL section results for workflow
    if instance.section != 'FINAL':
        return
    
    booking = instance.booking
    
    if instance.result == 'NOT_YET_COMPETENT':
        # Check if can retry (attempt < 3)
        if booking.attempt_number < 3:
            # Create next attempt booking with blank date
            next_booking = booking.create_next_attempt()
            
            if next_booking:
                # Link the result to next booking
                instance.next_attempt_booking = next_booking
                instance.save(update_fields=['next_attempt_booking'])
                
                # Update booking status
                booking.status = 'COMPLETED'
                booking.save(update_fields=['status'])
                
                # Send notification about next attempt
                send_next_attempt_notification(instance, next_booking)
        else:
            # Final attempt failed
            booking.status = 'COMPLETED'
            booking.save(update_fields=['status'])
            
            # Update application status
            if booking.application:
                booking.application.status = 'COMPLETED'
                booking.application.save(update_fields=['status'])
            
            send_final_attempt_failed_notification(instance)
    
    elif instance.result == 'COMPETENT':
        # Update booking status
        booking.status = 'COMPLETED'
        booking.save(update_fields=['status'])
        
        # Update application status
        if booking.application:
            booking.application.status = 'COMPLETED'
            booking.application.save(update_fields=['status'])
        
        # Send success notification
        send_success_notification(instance)


def send_schedule_notification(booking):
    """
    Send email/SMS notification when trade test is scheduled.
    """
    learner = booking.learner
    
    # Create system notification
    try:
        from core.models import Notification
        
        Notification.objects.create(
            recipient=learner.user if learner.user else None,
            title='Trade Test Scheduled',
            message=f'Your trade test for {booking.trade.name} has been scheduled for '
                    f'{booking.scheduled_date.strftime("%d %B %Y")} at {booking.centre.name}.',
            notification_type='TRADE_TEST',
            link=f'/trade-tests/bookings/{booking.pk}/',
        )
    except Exception:
        pass  # Notification model may not exist or be different
    
    # TODO: Integrate with SMS/Email service
    # send_sms(learner.phone_mobile, message)
    # send_email(learner.email, subject, message)


def send_next_attempt_notification(result, next_booking):
    """
    Send notification about next attempt being created.
    """
    learner = result.booking.learner
    attempt_num = next_booking.attempt_number
    
    try:
        from core.models import Notification
        
        Notification.objects.create(
            recipient=learner.user if learner.user else None,
            title=f'Trade Test Attempt {attempt_num} Created',
            message=f'Your attempt {attempt_num} for {result.booking.trade.name} has been '
                    f'registered. You will be notified when the test date is confirmed.',
            notification_type='TRADE_TEST',
            link=f'/trade-tests/bookings/{next_booking.pk}/',
        )
    except Exception:
        pass


def send_final_attempt_failed_notification(result):
    """
    Send notification when all 3 attempts have been exhausted.
    """
    learner = result.booking.learner
    
    try:
        from core.models import Notification
        
        Notification.objects.create(
            recipient=learner.user if learner.user else None,
            title='Trade Test - All Attempts Used',
            message=f'You have used all 3 attempts for {result.booking.trade.name}. '
                    f'Please contact the training centre for guidance on next steps.',
            notification_type='TRADE_TEST',
            link=f'/trade-tests/applications/{result.booking.application.pk}/',
        )
    except Exception:
        pass


def send_success_notification(result):
    """
    Send notification on successful trade test completion.
    """
    learner = result.booking.learner
    
    try:
        from core.models import Notification
        
        Notification.objects.create(
            recipient=learner.user if learner.user else None,
            title='Trade Test Passed!',
            message=f'Congratulations! You have passed your trade test for '
                    f'{result.booking.trade.name}. Your assessment report will be '
                    f'available shortly.',
            notification_type='TRADE_TEST',
            link=f'/trade-tests/bookings/{result.booking.pk}/',
        )
    except Exception:
        pass
