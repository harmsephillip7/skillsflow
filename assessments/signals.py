"""
Assessment Signals
Handles notifications and automations triggered by assessment events.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from .models import AssessmentResult, AssessmentSchedule


@receiver(post_save, sender=AssessmentResult)
def notify_parent_on_result(sender, instance, created, **kwargs):
    """
    Send email notification to parent/guardian when assessment result is finalized.
    Only sends if parent has enabled notifications for this type.
    """
    # Only notify on finalized results
    if instance.status != 'FINALIZED':
        return
    
    # Check if we've already notified (avoid duplicate emails on updates)
    if hasattr(instance, '_notification_sent'):
        return
    
    try:
        from learners.models import Guardian, GuardianPortalAccess, GuardianNotificationPreference
        
        learner = instance.enrollment.learner
        
        # Get guardians for this learner
        guardians = Guardian.objects.filter(learner=learner)
        
        for guardian in guardians:
            # Check notification preferences
            try:
                prefs = GuardianNotificationPreference.objects.get(guardian=guardian)
                
                # Determine which notification type
                if instance.result == 'C' and not prefs.notify_assessment_completed:
                    continue
                if instance.result == 'NYC' and not prefs.notify_nyc_result:
                    continue
                    
            except GuardianNotificationPreference.DoesNotExist:
                # Default: send notifications
                pass
            
            # Get or create portal access for login link
            portal_access, _ = GuardianPortalAccess.objects.get_or_create(
                guardian=guardian,
                defaults={'is_active': True}
            )
            
            # Send email
            _send_result_notification(
                guardian=guardian,
                learner=learner,
                result=instance,
                portal_access=portal_access
            )
            
    except Exception as e:
        # Log but don't fail the save
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send parent notification: {e}")


def _send_result_notification(guardian, learner, result, portal_access):
    """Send assessment result notification email to guardian."""
    from django.urls import reverse
    
    subject = f"Assessment Result: {learner.first_name} - {result.activity.title}"
    
    context = {
        'guardian': guardian,
        'learner': learner,
        'result': result,
        'activity': result.activity,
        'is_competent': result.result == 'C',
        'access_code': portal_access.access_code,
        'portal_url': settings.SITE_URL + '/portal/parent/login/' if hasattr(settings, 'SITE_URL') else '',
    }
    
    # Render email templates
    html_message = render_to_string('emails/assessment_result_notification.html', context)
    plain_message = render_to_string('emails/assessment_result_notification.txt', context)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[guardian.email],
        html_message=html_message,
        fail_silently=True
    )


@receiver(post_save, sender=AssessmentSchedule)
def notify_parent_on_schedule_change(sender, instance, created, **kwargs):
    """
    Send email notification when assessment schedule changes.
    """
    # Only notify on reschedules, not new schedules
    if created:
        return
    
    # Check if date changed (via audit trail in model)
    if not instance.rescheduled_from:
        return
    
    try:
        from learners.models import Guardian, GuardianNotificationPreference
        from academics.models import Enrollment
        
        # Get all learners in the cohort
        enrollments = Enrollment.objects.filter(
            cohort=instance.cohort,
            status__in=['ENROLLED', 'ACTIVE']
        )
        
        for enrollment in enrollments:
            learner = enrollment.learner
            guardians = Guardian.objects.filter(learner=learner)
            
            for guardian in guardians:
                # Check notification preferences
                try:
                    prefs = GuardianNotificationPreference.objects.get(guardian=guardian)
                    if not prefs.notify_schedule_changed:
                        continue
                except GuardianNotificationPreference.DoesNotExist:
                    pass
                
                # Send notification
                _send_schedule_change_notification(
                    guardian=guardian,
                    learner=learner,
                    schedule=instance
                )
                
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send schedule change notification: {e}")


def _send_schedule_change_notification(guardian, learner, schedule):
    """Send schedule change notification email."""
    subject = f"Schedule Change: {schedule.activity.title} - {learner.first_name}"
    
    context = {
        'guardian': guardian,
        'learner': learner,
        'schedule': schedule,
        'activity': schedule.activity,
        'old_date': schedule.rescheduled_from,
        'new_date': schedule.scheduled_date,
    }
    
    html_message = render_to_string('emails/schedule_change_notification.html', context)
    plain_message = render_to_string('emails/schedule_change_notification.txt', context)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[guardian.email],
        html_message=html_message,
        fail_silently=True
    )


# Weekly digest signal (triggered by Celery beat)
def send_weekly_progress_digest():
    """
    Send weekly progress digest to all guardians who have it enabled.
    Should be called by Celery beat task.
    """
    from learners.models import Guardian, GuardianNotificationPreference
    from academics.models import Enrollment
    from .models import AssessmentResult
    
    # Get all guardians with weekly digest enabled
    prefs = GuardianNotificationPreference.objects.filter(notify_weekly_progress=True)
    
    for pref in prefs:
        guardian = pref.guardian
        learner = guardian.learner
        
        # Get active enrollment
        enrollment = Enrollment.objects.filter(
            learner=learner,
            status__in=['ENROLLED', 'ACTIVE']
        ).first()
        
        if not enrollment:
            continue
        
        # Get this week's results
        week_ago = timezone.now().date() - timezone.timedelta(days=7)
        recent_results = AssessmentResult.objects.filter(
            enrollment=enrollment,
            assessment_date__gte=week_ago,
            status='FINALIZED'
        ).select_related('activity')
        
        # Get upcoming assessments
        upcoming = AssessmentSchedule.objects.filter(
            cohort=enrollment.cohort,
            scheduled_date__gte=timezone.now().date(),
            status='SCHEDULED'
        ).select_related('activity').order_by('scheduled_date')[:5]
        
        if not recent_results.exists() and not upcoming.exists():
            continue
        
        # Calculate progress
        total_activities = enrollment.qualification.modules.aggregate(
            total=models.Count('assessment_activities')
        )['total'] or 0
        completed = AssessmentResult.objects.filter(
            enrollment=enrollment,
            result='C',
            status='FINALIZED'
        ).values('activity').distinct().count()
        
        context = {
            'guardian': guardian,
            'learner': learner,
            'enrollment': enrollment,
            'recent_results': recent_results,
            'upcoming_assessments': upcoming,
            'progress_percentage': round((completed / total_activities * 100) if total_activities else 0, 1),
            'competent_count': completed,
            'total_count': total_activities,
        }
        
        html_message = render_to_string('emails/weekly_progress_digest.html', context)
        plain_message = render_to_string('emails/weekly_progress_digest.txt', context)
        
        send_mail(
            subject=f"Weekly Progress Report: {learner.first_name}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[guardian.email],
            html_message=html_message,
            fail_silently=True
        )
