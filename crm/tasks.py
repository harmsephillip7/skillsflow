"""
CRM Celery Tasks

Automated tasks for CRM operations including:
- Scheduled communication sending
- Lead scoring updates
- Follow-up reminders
- Pipeline automation
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(name='crm.tasks.process_scheduled_communications')
def process_scheduled_communications():
    """
    Process and send scheduled communications that are due.
    This task should run every 15-30 minutes via Celery Beat.
    """
    from crm.models import CommunicationCycle, LeadActivity, AgentNotification
    from crm.services.nurture import NurtureService
    
    now = timezone.now()
    
    # Get communications scheduled for now or earlier
    pending_communications = CommunicationCycle.objects.filter(
        status='SCHEDULED',
        scheduled_at__lte=now,
        is_active=True,
        lead__nurture_active=True,
        lead__unsubscribed=False
    ).select_related('lead', 'template')[:100]  # Process 100 at a time
    
    sent_count = 0
    failed_count = 0
    
    for cycle in pending_communications:
        lead = cycle.lead
        template = cycle.template
        
        if not template:
            logger.warning(f"No template for communication cycle {cycle.pk}")
            cycle.status = 'FAILED'
            cycle.error_message = 'No template configured'
            cycle.save()
            failed_count += 1
            continue
        
        try:
            # Check if lead is still eligible
            if lead.status in ['ENROLLED', 'LOST', 'ALUMNI']:
                cycle.status = 'CANCELLED'
                cycle.error_message = f'Lead status is {lead.status}'
                cycle.save()
                continue
            
            # Send the communication
            success, result = NurtureService.send_communication(lead, template)
            
            if success:
                cycle.status = 'SENT'
                cycle.sent_at = now
                cycle.save()
                sent_count += 1
                
                logger.info(f"Sent scheduled communication to lead {lead.pk} via {result}")
                
            else:
                cycle.status = 'FAILED'
                cycle.error_message = result
                cycle.retry_count += 1
                
                # Schedule retry if under max retries
                if cycle.retry_count < 3:
                    cycle.status = 'SCHEDULED'
                    cycle.scheduled_at = now + timedelta(hours=1)  # Retry in 1 hour
                    
                cycle.save()
                failed_count += 1
                
                logger.error(f"Failed to send communication to lead {lead.pk}: {result}")
                
        except Exception as e:
            logger.exception(f"Error processing communication cycle {cycle.pk}")
            cycle.status = 'FAILED'
            cycle.error_message = str(e)[:500]
            cycle.save()
            failed_count += 1
    
    return {
        'processed': len(pending_communications),
        'sent': sent_count,
        'failed': failed_count
    }


@shared_task(name='crm.tasks.update_lead_scores')
def update_lead_scores():
    """
    Update engagement scores for all active leads.
    This task should run daily.
    """
    from crm.models import Lead, LeadActivity
    from crm.services.scoring import LeadScoringService
    
    # Get active leads
    active_leads = Lead.objects.exclude(
        status__in=['ENROLLED', 'LOST', 'ALUMNI']
    ).filter(
        created_at__gte=timezone.now() - timedelta(days=180)  # Last 6 months
    )
    
    updated_count = 0
    
    for lead in active_leads.iterator(chunk_size=100):
        try:
            old_score = lead.engagement_score
            new_score = LeadScoringService.calculate_engagement_score(lead)
            
            if new_score != old_score:
                lead.engagement_score = new_score
                lead.save(update_fields=['engagement_score', 'updated_at'])
                updated_count += 1
                
        except Exception as e:
            logger.error(f"Error updating score for lead {lead.pk}: {str(e)}")
    
    return {'updated': updated_count}


@shared_task(name='crm.tasks.send_followup_reminders')
def send_followup_reminders():
    """
    Send notifications to sales agents about follow-ups due today or overdue.
    This task should run every morning.
    """
    from crm.models import Lead, AgentNotification
    from django.db.models import Count
    from collections import defaultdict
    
    today = timezone.now().date()
    
    # Get leads with follow-ups due today or overdue
    leads_to_notify = Lead.objects.filter(
        next_follow_up__date__lte=today,
        status__in=['NEW', 'CONTACTED', 'QUALIFIED', 'PROPOSAL', 'NEGOTIATION'],
        assigned_to__isnull=False
    ).select_related('assigned_to')
    
    # Group by agent
    agent_leads = defaultdict(list)
    for lead in leads_to_notify:
        agent_leads[lead.assigned_to].append(lead)
    
    notifications_created = 0
    
    for agent, leads in agent_leads.items():
        overdue = [l for l in leads if l.next_follow_up.date() < today]
        due_today = [l for l in leads if l.next_follow_up.date() == today]
        
        if overdue or due_today:
            message = []
            if overdue:
                message.append(f"{len(overdue)} overdue follow-ups")
            if due_today:
                message.append(f"{len(due_today)} follow-ups due today")
            
            # Check if we already sent this notification today
            existing = AgentNotification.objects.filter(
                agent=agent,
                notification_type='FOLLOW_UP',
                created_at__date=today
            ).exists()
            
            if not existing:
                AgentNotification.objects.create(
                    agent=agent,
                    notification_type='FOLLOW_UP',
                    title='Follow-up Reminder',
                    message=', '.join(message),
                    priority='HIGH' if overdue else 'MEDIUM',
                    data={
                        'overdue_count': len(overdue),
                        'today_count': len(due_today),
                        'lead_ids': [l.pk for l in leads[:10]]
                    }
                )
                notifications_created += 1
    
    return {'notifications_sent': notifications_created}


@shared_task(name='crm.tasks.process_pipeline_automation')
def process_pipeline_automation():
    """
    Process pipeline stage automation rules.
    Moves leads to next stage if conditions are met.
    """
    from crm.models import Lead, LeadPipelineMembership, PipelineStage
    from crm.services.pipeline import PipelineService
    
    now = timezone.now()
    
    # Get leads in pipelines with auto-progression rules
    memberships = LeadPipelineMembership.objects.filter(
        status='ACTIVE'
    ).select_related('lead', 'current_stage', 'pipeline')
    
    auto_moved = 0
    
    for membership in memberships:
        stage = membership.current_stage
        
        if not stage or not stage.auto_progress_days:
            continue
        
        # Check if lead has been in stage long enough
        time_in_stage = now - membership.stage_entered_at
        if time_in_stage.days >= stage.auto_progress_days:
            # Check if stage requirements are met
            if stage.check_requirements_met(membership.lead):
                next_stage = stage.get_next_stage()
                if next_stage:
                    try:
                        PipelineService().move_to_stage(
                            membership.lead,
                            next_stage,
                            user=None,  # System automation
                            notes=f'Auto-progressed after {stage.auto_progress_days} days'
                        )
                        auto_moved += 1
                    except Exception as e:
                        logger.error(f"Error auto-progressing lead {membership.lead.pk}: {str(e)}")
    
    return {'auto_moved': auto_moved}


@shared_task(name='crm.tasks.check_stale_leads')
def check_stale_leads():
    """
    Identify and flag leads with no activity for extended periods.
    Creates notifications for stale leads.
    """
    from crm.models import Lead, LeadActivity, AgentNotification
    from collections import defaultdict
    
    now = timezone.now()
    stale_threshold = now - timedelta(days=14)  # No activity in 14 days
    
    # Find leads with no recent activity
    stale_leads = Lead.objects.filter(
        status__in=['NEW', 'CONTACTED', 'QUALIFIED'],
        assigned_to__isnull=False
    ).exclude(
        activities__created_at__gte=stale_threshold
    ).distinct().select_related('assigned_to')
    
    # Group by agent
    agent_stale = defaultdict(list)
    for lead in stale_leads:
        agent_stale[lead.assigned_to].append(lead)
    
    notifications_created = 0
    today = now.date()
    
    for agent, leads in agent_stale.items():
        # Check if notification already sent this week
        week_ago = today - timedelta(days=7)
        existing = AgentNotification.objects.filter(
            agent=agent,
            notification_type='STALE_LEADS',
            created_at__date__gte=week_ago
        ).exists()
        
        if not existing and leads:
            AgentNotification.objects.create(
                agent=agent,
                notification_type='STALE_LEADS',
                title='Stale Leads Alert',
                message=f'You have {len(leads)} leads with no activity in 14+ days',
                priority='MEDIUM',
                data={
                    'lead_count': len(leads),
                    'lead_ids': [l.pk for l in leads[:20]]
                }
            )
            notifications_created += 1
    
    return {'stale_leads_flagged': len(stale_leads), 'notifications': notifications_created}
