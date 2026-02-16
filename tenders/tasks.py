"""
Celery tasks for tender management.
Handles scheduled scraping, probability updates, and notifications.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

# Try to import celery, but make it optional for serverless deployments
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Create a dummy decorator that just returns the function
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def scrape_tender_source(self, source_id: int):
    """
    Scrape a single tender source.
    
    Args:
        source_id: ID of the TenderSource to scrape
    """
    from .models import TenderSource
    from .services import TenderService
    
    try:
        source = TenderSource.objects.get(id=source_id)
        
        if source.status not in ['ACTIVE', 'PAUSED']:
            logger.info(f"Skipping disabled source: {source.name}")
            return {'status': 'skipped', 'reason': 'source_disabled'}
        
        new_count, updated_count, message = TenderService.run_scrape(source)
        
        return {
            'status': 'success',
            'source': source.name,
            'new_tenders': new_count,
            'updated_tenders': updated_count,
            'message': message,
        }
        
    except TenderSource.DoesNotExist:
        logger.error(f"TenderSource {source_id} not found")
        return {'status': 'error', 'reason': 'source_not_found'}
        
    except Exception as e:
        logger.exception(f"Error scraping source {source_id}")
        self.retry(exc=e)


@shared_task
def scrape_all_sources():
    """
    Scrape all active tender sources that are due for a scrape.
    Should be scheduled to run hourly via Celery Beat.
    """
    from .models import TenderSource
    
    now = timezone.now()
    
    # Get sources due for scraping
    sources = TenderSource.objects.filter(
        status='ACTIVE',
    ).filter(
        # Never scraped, or next scrape time has passed
        models.Q(next_scrape_at__isnull=True) |
        models.Q(next_scrape_at__lte=now)
    )
    
    logger.info(f"Found {sources.count()} sources due for scraping")
    
    results = []
    for source in sources:
        # Queue each source as a separate task
        task = scrape_tender_source.delay(source.id)
        results.append({
            'source_id': source.id,
            'source_name': source.name,
            'task_id': task.id,
        })
    
    return {'queued': len(results), 'sources': results}


@shared_task
def update_probabilities():
    """
    Update probability and expected revenue for all pending applications.
    Should be scheduled to run daily.
    """
    from .services import TenderService
    
    updated = TenderService.update_all_probabilities()
    
    return {
        'status': 'success',
        'applications_updated': updated,
    }


@shared_task
def send_closing_soon_notifications():
    """
    Send notifications for tenders closing soon.
    Should be scheduled to run daily.
    """
    from .models import Tender, TenderNotificationRule
    
    # Get rules for closing soon notifications
    rules = TenderNotificationRule.objects.filter(
        trigger='CLOSING_SOON',
        is_active=True,
    )
    
    sent_count = 0
    
    for rule in rules:
        if not rule.can_trigger():
            continue
        
        days_before = rule.trigger_config.get('days_before', 7)
        today = date.today()
        target_date = today + timedelta(days=days_before)
        
        # Get tenders closing on the target date
        closing_tenders = Tender.objects.filter(
            closing_date=target_date,
            status__in=['DISCOVERED', 'REVIEWING', 'APPLICABLE'],
        )
        
        if closing_tenders.exists():
            # Send notification
            sent = _send_notification(
                rule=rule,
                subject=rule.subject_template or f"Tenders closing in {days_before} days",
                context={
                    'tenders': closing_tenders,
                    'days': days_before,
                    'date': target_date,
                }
            )
            
            if sent:
                rule.mark_triggered()
                sent_count += len(closing_tenders)
    
    return {'notifications_sent': sent_count}


@shared_task
def send_probability_drop_notifications():
    """
    Send notifications when application probability drops below threshold.
    Should be scheduled to run daily after update_probabilities.
    """
    from .models import TenderApplication, TenderNotificationRule
    
    rules = TenderNotificationRule.objects.filter(
        trigger='PROBABILITY_DROP',
        is_active=True,
    )
    
    sent_count = 0
    
    for rule in rules:
        if not rule.can_trigger():
            continue
        
        threshold = Decimal(str(rule.trigger_config.get('threshold', 0.3)))
        
        # Get applications that just dropped below threshold
        applications = TenderApplication.objects.filter(
            status__in=['SUBMITTED', 'ACKNOWLEDGED', 'UNDER_EVALUATION'],
            current_probability__lt=threshold,
            current_probability__gt=0,
        ).select_related('tender')
        
        if applications.exists():
            sent = _send_notification(
                rule=rule,
                subject=rule.subject_template or "Tender applications below probability threshold",
                context={
                    'applications': applications,
                    'threshold': threshold,
                }
            )
            
            if sent:
                rule.mark_triggered()
                sent_count += applications.count()
    
    return {'notifications_sent': sent_count}


@shared_task
def send_new_tender_notifications():
    """
    Send notifications for newly discovered tenders matching criteria.
    Should be scheduled to run after each scrape.
    """
    from .models import Tender, TenderNotificationRule
    
    # Get tenders discovered in the last hour
    one_hour_ago = timezone.now() - timedelta(hours=1)
    
    new_tenders = Tender.objects.filter(
        created_at__gte=one_hour_ago,
        status='DISCOVERED',
    )
    
    if not new_tenders.exists():
        return {'notifications_sent': 0}
    
    rules = TenderNotificationRule.objects.filter(
        trigger='NEW_TENDER',
        is_active=True,
    )
    
    sent_count = 0
    
    for rule in rules:
        if not rule.can_trigger():
            continue
        
        # Filter tenders matching criteria
        criteria = rule.trigger_config.get('criteria', {})
        matching = new_tenders
        
        if criteria.get('funder'):
            matching = matching.filter(funder__icontains=criteria['funder'])
        if criteria.get('region'):
            matching = matching.filter(region__icontains=criteria['region'])
        if criteria.get('min_value'):
            matching = matching.filter(estimated_value__gte=criteria['min_value'])
        
        if matching.exists():
            sent = _send_notification(
                rule=rule,
                subject=rule.subject_template or f"New tenders discovered: {matching.count()}",
                context={
                    'tenders': matching,
                    'criteria': criteria,
                }
            )
            
            if sent:
                rule.mark_triggered()
                sent_count += matching.count()
    
    return {'notifications_sent': sent_count}


@shared_task
def send_no_update_notifications():
    """
    Send notifications for applications with no update for X days.
    """
    from .models import TenderApplication, TenderNotificationRule
    
    rules = TenderNotificationRule.objects.filter(
        trigger='NO_UPDATE',
        is_active=True,
    )
    
    sent_count = 0
    
    for rule in rules:
        if not rule.can_trigger():
            continue
        
        days = rule.trigger_config.get('days', 14)
        threshold_date = timezone.now() - timedelta(days=days)
        
        # Get applications with no updates
        stale_applications = TenderApplication.objects.filter(
            status__in=['SUBMITTED', 'ACKNOWLEDGED', 'UNDER_EVALUATION'],
            updated_at__lt=threshold_date,
        ).select_related('tender')
        
        if stale_applications.exists():
            sent = _send_notification(
                rule=rule,
                subject=rule.subject_template or f"Tender applications with no updates for {days} days",
                context={
                    'applications': stale_applications,
                    'days': days,
                }
            )
            
            if sent:
                rule.mark_triggered()
                sent_count += stale_applications.count()
    
    return {'notifications_sent': sent_count}


def _send_notification(rule, subject: str, context: dict) -> bool:
    """
    Send notification via the configured channel.
    
    Args:
        rule: TenderNotificationRule instance
        subject: Email/notification subject
        context: Template context
        
    Returns:
        True if sent successfully
    """
    try:
        if rule.channel == 'EMAIL':
            return _send_email_notification(rule, subject, context)
        elif rule.channel == 'SLACK':
            return _send_slack_notification(rule, subject, context)
        elif rule.channel == 'TEAMS':
            return _send_teams_notification(rule, subject, context)
        else:
            logger.warning(f"Unsupported notification channel: {rule.channel}")
            return False
            
    except Exception as e:
        logger.exception(f"Failed to send notification: {str(e)}")
        return False


def _send_email_notification(rule, subject: str, context: dict) -> bool:
    """Send email notification."""
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Get recipient emails
    recipients = []
    for recipient in rule.recipients:
        if isinstance(recipient, str) and '@' in recipient:
            recipients.append(recipient)
        else:
            # Assume it's a user ID
            try:
                user = User.objects.get(id=recipient)
                if user.email:
                    recipients.append(user.email)
            except User.DoesNotExist:
                pass
    
    if not recipients:
        logger.warning(f"No valid recipients for rule: {rule.name}")
        return False
    
    # Render email body
    body = rule.body_template
    if not body:
        try:
            body = render_to_string(
                f'tenders/emails/{rule.trigger.lower()}.html',
                context
            )
        except Exception:
            body = f"Notification: {subject}\n\nPlease check the tender management system for details."
    
    # Send email
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )
    
    logger.info(f"Sent email notification to {len(recipients)} recipients")
    return True


def _send_slack_notification(rule, subject: str, context: dict) -> bool:
    """Send Slack notification."""
    import requests
    
    webhook_url = rule.trigger_config.get('slack_webhook_url')
    if not webhook_url:
        logger.warning("No Slack webhook URL configured")
        return False
    
    # Format message
    message = {
        'text': subject,
        'blocks': [
            {
                'type': 'header',
                'text': {'type': 'plain_text', 'text': subject}
            },
            {
                'type': 'section',
                'text': {'type': 'mrkdwn', 'text': rule.body_template or 'Check the tender system for details.'}
            }
        ]
    }
    
    response = requests.post(webhook_url, json=message, timeout=10)
    response.raise_for_status()
    
    logger.info("Sent Slack notification")
    return True


def _send_teams_notification(rule, subject: str, context: dict) -> bool:
    """Send Microsoft Teams notification."""
    import requests
    
    webhook_url = rule.trigger_config.get('teams_webhook_url')
    if not webhook_url:
        logger.warning("No Teams webhook URL configured")
        return False
    
    # Format adaptive card
    message = {
        '@type': 'MessageCard',
        '@context': 'http://schema.org/extensions',
        'summary': subject,
        'themeColor': '0076D7',
        'title': subject,
        'text': rule.body_template or 'Check the tender system for details.',
    }
    
    response = requests.post(webhook_url, json=message, timeout=10)
    response.raise_for_status()
    
    logger.info("Sent Teams notification")
    return True


# Import models for Q filter (needed in scrape_all_sources)
from django.db import models
