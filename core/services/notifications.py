"""
Notification Service

Handles sending notifications via multiple channels (in-app, email, SMS).
Integrates with Django signals to trigger notifications on model events.

Configuration in settings.py:
    EMAIL_HOST, EMAIL_PORT, etc. - Standard Django email settings
    SMS_GATEWAY_URL = 'https://api.sms-provider.com/send'  # Optional SMS provider
    SMS_API_KEY = 'your-api-key'
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from core.models import User, Notification, NotificationPreference

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for creating and sending notifications across multiple channels.
    
    Usage:
        service = NotificationService()
        
        # Send a notification
        service.send_notification(
            user=user,
            notification_type='LOGBOOK_UNSIGNED',
            title='Logbook needs signature',
            message='Your December 2025 logbook is awaiting your signature.',
            link='/portal/student/logbooks/123/'
        )
        
        # Send batch notifications
        service.send_batch_notifications(
            users=[user1, user2],
            notification_type='ATTENDANCE_REMINDER',
            title='Submit attendance',
            message='Please submit your weekly attendance.'
        )
    """
    
    def __init__(self):
        """Initialize notification service."""
        self.email_enabled = getattr(settings, 'EMAIL_HOST', None) is not None
        self.sms_enabled = getattr(settings, 'SMS_GATEWAY_URL', None) is not None
        self.sms_gateway_url = getattr(settings, 'SMS_GATEWAY_URL', None)
        self.sms_api_key = getattr(settings, 'SMS_API_KEY', None)
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@skillsflow.co.za')
    
    def get_user_preferences(self, user: User, notification_type: str) -> Dict[str, bool]:
        """
        Get user's notification preferences for a specific type.
        
        Returns:
            Dict with 'in_app', 'email', 'sms' boolean flags
        """
        defaults = {
            'in_app': True,
            'email': True,
            'sms': False,
        }
        
        try:
            pref = NotificationPreference.objects.get(
                user=user,
                notification_type=notification_type
            )
            return {
                'in_app': pref.in_app_enabled,
                'email': pref.email_enabled,
                'sms': pref.sms_enabled,
            }
        except NotificationPreference.DoesNotExist:
            return defaults
    
    def create_notification(
        self,
        user: User,
        notification_type: str,
        title: str,
        message: str,
        link: str = '',
        priority: str = 'NORMAL'
    ) -> Notification:
        """
        Create an in-app notification record.
        
        Returns:
            The created Notification instance
        """
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            priority=priority,
            title=title,
            message=message,
            link=link,
        )
        return notification
    
    def send_email(
        self,
        user: User,
        subject: str,
        template_name: str = None,
        context: Dict = None,
        plain_message: str = None
    ) -> bool:
        """
        Send an email notification.
        
        Args:
            user: User to send to
            subject: Email subject
            template_name: Optional email template (e.g., 'notifications/email/logbook_reminder.html')
            context: Context dict for template rendering
            plain_message: Plain text message if not using template
            
        Returns:
            True if sent successfully
        """
        if not self.email_enabled:
            logger.warning("Email not configured, skipping email notification")
            return False
        
        if not user.email:
            logger.warning(f"User {user.id} has no email address")
            return False
        
        try:
            if template_name and context:
                html_message = render_to_string(template_name, context)
                text_message = strip_tags(html_message)
            else:
                html_message = None
                text_message = plain_message or subject
            
            send_mail(
                subject=subject,
                message=text_message,
                from_email=self.from_email,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email sent to {user.email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {user.email}: {e}")
            return False
    
    def send_sms(self, user: User, message: str) -> bool:
        """
        Send an SMS notification.
        
        Args:
            user: User to send to (must have phone number)
            message: SMS message text (max 160 chars recommended)
            
        Returns:
            True if sent successfully
        """
        if not self.sms_enabled:
            logger.debug("SMS not configured, skipping SMS notification")
            return False
        
        phone = getattr(user, 'phone', None)
        if not phone:
            logger.warning(f"User {user.id} has no phone number")
            return False
        
        try:
            import requests
            
            # This is a generic SMS API pattern - adjust for your provider
            response = requests.post(
                self.sms_gateway_url,
                headers={
                    'Authorization': f'Bearer {self.sms_api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'to': phone,
                    'message': message[:160],  # Truncate to SMS length
                },
                timeout=10
            )
            
            response.raise_for_status()
            logger.info(f"SMS sent to {phone}")
            return True
            
        except ImportError:
            logger.error("requests library required for SMS")
            return False
        except Exception as e:
            logger.error(f"Failed to send SMS to {phone}: {e}")
            return False
    
    def send_notification(
        self,
        user: User,
        notification_type: str,
        title: str,
        message: str,
        link: str = '',
        priority: str = 'NORMAL',
        email_template: str = None,
        email_context: Dict = None,
        sms_message: str = None
    ) -> Notification:
        """
        Send a notification to a user via all configured and preferred channels.
        
        Args:
            user: User to notify
            notification_type: Type of notification (must match NOTIFICATION_TYPE_CHOICES)
            title: Notification title
            message: Full notification message
            link: Optional URL to link to
            priority: Priority level (LOW, NORMAL, HIGH, URGENT)
            email_template: Optional email template name
            email_context: Optional email template context
            sms_message: Optional shorter message for SMS
            
        Returns:
            The created Notification instance
        """
        prefs = self.get_user_preferences(user, notification_type)
        
        # Always create in-app notification if enabled
        notification = None
        if prefs['in_app']:
            notification = self.create_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                link=link,
                priority=priority
            )
        
        # Send email if enabled and preferred
        if prefs['email'] and self.email_enabled:
            email_sent = self.send_email(
                user=user,
                subject=title,
                template_name=email_template,
                context=email_context or {'title': title, 'message': message, 'link': link},
                plain_message=message
            )
            if notification and email_sent:
                notification.email_sent = True
                notification.email_sent_at = timezone.now()
                notification.save(update_fields=['email_sent', 'email_sent_at'])
        
        # Send SMS if enabled and preferred
        if prefs['sms'] and self.sms_enabled:
            sms_sent = self.send_sms(user, sms_message or message)
            if notification and sms_sent:
                notification.sms_sent = True
                notification.sms_sent_at = timezone.now()
                notification.save(update_fields=['sms_sent', 'sms_sent_at'])
        
        return notification
    
    def send_batch_notifications(
        self,
        users: List[User],
        notification_type: str,
        title: str,
        message: str,
        link: str = '',
        priority: str = 'NORMAL'
    ) -> List[Notification]:
        """
        Send the same notification to multiple users.
        
        Returns:
            List of created Notification instances
        """
        notifications = []
        for user in users:
            notification = self.send_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                link=link,
                priority=priority
            )
            if notification:
                notifications.append(notification)
        return notifications
    
    def get_unread_count(self, user: User) -> int:
        """Get count of unread notifications for a user."""
        return Notification.objects.filter(user=user, is_read=False).count()
    
    def get_recent_notifications(
        self,
        user: User,
        limit: int = 10,
        unread_only: bool = False
    ) -> List[Notification]:
        """Get recent notifications for a user."""
        qs = Notification.objects.filter(user=user)
        if unread_only:
            qs = qs.filter(is_read=False)
        return list(qs.order_by('-created_at')[:limit])
    
    def mark_all_read(self, user: User) -> int:
        """Mark all notifications as read for a user. Returns count updated."""
        return Notification.objects.filter(
            user=user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )


# Singleton instance
_notification_service = None


def get_notification_service() -> NotificationService:
    """Get the singleton notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# =============================================================================
# Notification Helper Functions
# =============================================================================

def notify_logbook_unsigned(learner_user: User, logbook_entry, days_overdue: int = 0):
    """Notify learner that their logbook needs signing."""
    service = get_notification_service()
    
    message = f"Your logbook for {logbook_entry.period_display} is awaiting your signature."
    if days_overdue > 0:
        message += f" It is {days_overdue} days overdue."
    
    service.send_notification(
        user=learner_user,
        notification_type='LOGBOOK_UNSIGNED',
        title='Logbook Requires Your Signature',
        message=message,
        link=f'/portal/student/logbooks/{logbook_entry.id}/',
        priority='HIGH' if days_overdue > 7 else 'NORMAL'
    )


def notify_logbook_signed(recipient_user: User, logbook_entry, signed_by: str):
    """Notify that a logbook has been signed."""
    service = get_notification_service()
    
    service.send_notification(
        user=recipient_user,
        notification_type='LOGBOOK_SIGNED',
        title='Logbook Signed',
        message=f"The logbook for {logbook_entry.period_display} has been signed by {signed_by}.",
        link=f'/portal/student/logbooks/{logbook_entry.id}/'
    )


def notify_disciplinary_action(learner_user: User, action):
    """Notify learner of disciplinary action."""
    service = get_notification_service()
    
    service.send_notification(
        user=learner_user,
        notification_type='DISCIPLINARY_ACTION',
        title=f'Disciplinary Notice: {action.get_step_display()}',
        message=f"A {action.get_step_display()} has been issued. Please review the details.",
        link=f'/portal/student/disciplinary/{action.record.id}/',
        priority='URGENT'
    )


def notify_disciplinary_review_due(officer_user: User, record, days_until: int):
    """Notify workplace officer of upcoming disciplinary review."""
    service = get_notification_service()
    
    service.send_notification(
        user=officer_user,
        notification_type='DISCIPLINARY_REVIEW_DUE',
        title='Disciplinary Review Due Soon',
        message=f"Disciplinary case {record.case_number} has a review due in {days_until} days.",
        link=f'/portal/workplace-officer/disciplinary/{record.id}/',
        priority='HIGH' if days_until <= 3 else 'NORMAL'
    )


def notify_stipend_calculated(learner_user: User, stipend):
    """Notify learner that their stipend has been calculated."""
    service = get_notification_service()
    
    service.send_notification(
        user=learner_user,
        notification_type='STIPEND_CALCULATED',
        title='Stipend Calculated',
        message=f"Your stipend for {stipend.period_display} has been calculated: R{stipend.net_amount:,.2f}",
        link=f'/portal/student/stipends/{stipend.id}/'
    )


def notify_stipend_approved(learner_user: User, stipend):
    """Notify learner that their stipend has been approved."""
    service = get_notification_service()
    
    service.send_notification(
        user=learner_user,
        notification_type='STIPEND_APPROVED',
        title='Stipend Approved',
        message=f"Your stipend for {stipend.period_display} (R{stipend.net_amount:,.2f}) has been approved for payment.",
        link=f'/portal/student/stipends/{stipend.id}/'
    )


def notify_placement_visit_scheduled(learner_user: User, visit):
    """Notify learner of scheduled placement visit."""
    service = get_notification_service()
    
    service.send_notification(
        user=learner_user,
        notification_type='PLACEMENT_VISIT_SCHEDULED',
        title='Workplace Visit Scheduled',
        message=f"A workplace visit has been scheduled for {visit.visit_date.strftime('%d %B %Y')}.",
        link=f'/portal/student/placement/visits/{visit.id}/'
    )


def notify_new_message(recipient_user: User, thread, sender_name: str):
    """Notify user of new message in thread."""
    service = get_notification_service()
    
    service.send_notification(
        user=recipient_user,
        notification_type='NEW_MESSAGE',
        title=f'New message from {sender_name}',
        message=f"You have a new message in: {thread.subject}",
        link=f'/portal/messages/thread/{thread.id}/'
    )


def notify_wm_completed(facilitator_user: User, completion, learner_name: str):
    """Notify facilitator that a workplace module has been completed."""
    service = get_notification_service()
    
    service.send_notification(
        user=facilitator_user,
        notification_type='WM_COMPLETED',
        title='Workplace Module Completed',
        message=f"{learner_name} has completed workplace module: {completion.module_name}",
        link=f'/portal/facilitator/wbl/modules/{completion.id}/'
    )
