"""
Nurture Service

Handles automated communication cycles, scheduling, and lead engagement.
"""
from typing import Optional, List, Dict, Any, Tuple
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
import logging

from crm.models import (
    Lead, LeadActivity, Pipeline, PipelineStage, StageBlueprint,
    CommunicationCycle, LeadEngagement, AgentNotification
)
from crm.communication_models import MessageTemplate, Message, Conversation
from core.models import User

logger = logging.getLogger(__name__)


class NurtureService:
    """
    Service for managing automated lead nurture communications.
    Handles scheduling, sending, and tracking of communications.
    """
    
    @classmethod
    def schedule_next_communication(
        cls, 
        lead: Lead, 
        stage: PipelineStage = None
    ) -> Optional[CommunicationCycle]:
        """
        Schedule the next communication for a lead based on their stage.
        """
        if not lead.nurture_active:
            return None
        
        if not stage:
            stage = lead.current_stage
        
        if not stage:
            return None
        
        # Get frequency from stage or pipeline
        frequency_days = stage.effective_communication_frequency
        
        # Find the template to use
        template = None
        try:
            blueprint = stage.blueprint
            template = blueprint.default_template
            if not template and blueprint.communication_templates.exists():
                template = blueprint.communication_templates.first()
        except StageBlueprint.DoesNotExist:
            pass
        
        # Calculate next scheduled time
        scheduled_at = timezone.now() + timedelta(days=frequency_days)
        
        # Cancel any existing scheduled communications
        CommunicationCycle.objects.filter(
            lead=lead,
            status='SCHEDULED'
        ).update(status='CANCELLED')
        
        # Create new scheduled communication
        cycle = CommunicationCycle.objects.create(
            lead=lead,
            template=template,
            scheduled_at=scheduled_at,
            frequency_days=frequency_days,
            status='SCHEDULED',
            is_active=True
        )
        
        # Update lead's next scheduled communication
        lead.next_scheduled_communication = scheduled_at
        lead.save(update_fields=['next_scheduled_communication', 'updated_at'])
        
        return cycle
    
    @classmethod
    def send_communication(
        cls, 
        lead: Lead, 
        template: MessageTemplate,
        user: User = None
    ) -> Tuple[bool, str]:
        """
        Send a communication to a lead using their preferred channel.
        Returns (success, message_or_error).
        """
        # Get contact channels in order of preference
        channels = lead.get_contact_channels()
        
        sent = False
        error = None
        channel_used = None
        
        for channel in channels:
            contact = lead.get_contact_for_channel(channel)
            if not contact:
                continue
            
            try:
                if channel == 'WHATSAPP':
                    sent, error = cls._send_whatsapp(lead, template, contact)
                elif channel == 'EMAIL':
                    sent, error = cls._send_email(lead, template, contact)
                elif channel == 'SMS':
                    sent, error = cls._send_sms(lead, template, contact)
                
                if sent:
                    channel_used = channel
                    break
                    
            except Exception as e:
                logger.error(f"Failed to send {channel} to lead {lead.pk}: {str(e)}")
                error = str(e)
                continue
        
        if sent:
            # Log activity
            LeadActivity.objects.create(
                lead=lead,
                activity_type='COMMUNICATION_SENT',
                description=f'Automated {channel_used} sent: {template.name}',
                is_automated=True,
                automation_source='nurture_service',
                created_by=user
            )
            
            # Schedule next communication
            cls.schedule_next_communication(lead)
        
        return sent, error if not sent else channel_used
    
    @classmethod
    def _send_whatsapp(cls, lead: Lead, template: MessageTemplate, contact: str) -> Tuple[bool, Optional[str]]:
        """
        Send WhatsApp message to lead.
        """
        from crm.services.messaging import MessagingService
        
        # Prepare template context
        context = cls._build_template_context(lead)
        
        try:
            result = MessagingService.send_whatsapp_template(
                phone_number=contact,
                template=template,
                context=context,
                lead=lead
            )
            return result.get('success', False), result.get('error')
        except Exception as e:
            logger.error(f"WhatsApp send failed: {str(e)}")
            return False, str(e)
    
    @classmethod
    def _send_email(cls, lead: Lead, template: MessageTemplate, contact: str) -> Tuple[bool, Optional[str]]:
        """
        Send email to lead.
        """
        from django.core.mail import send_mail
        from django.template import Template, Context
        
        # Prepare template context
        context = cls._build_template_context(lead)
        
        try:
            # Render template
            subject = template.email_subject or f"Update from {lead.campus.brand.name}"
            body_template = Template(template.body)
            body = body_template.render(Context(context))
            
            html_body = None
            if template.email_html_template:
                html_template = Template(template.email_html_template)
                html_body = html_template.render(Context(context))
            
            send_mail(
                subject=subject,
                message=body,
                from_email=None,  # Use default
                recipient_list=[contact],
                html_message=html_body,
                fail_silently=False
            )
            return True, None
        except Exception as e:
            logger.error(f"Email send failed: {str(e)}")
            return False, str(e)
    
    @classmethod
    def _send_sms(cls, lead: Lead, template: MessageTemplate, contact: str) -> Tuple[bool, Optional[str]]:
        """
        Send SMS to lead.
        """
        from crm.services.messaging import MessagingService
        
        context = cls._build_template_context(lead)
        
        try:
            result = MessagingService.send_sms(
                phone_number=contact,
                message=template.render(context),
                lead=lead
            )
            return result.get('success', False), result.get('error')
        except Exception as e:
            logger.error(f"SMS send failed: {str(e)}")
            return False, str(e)
    
    @classmethod
    def _build_template_context(cls, lead: Lead) -> Dict[str, Any]:
        """
        Build context dictionary for template rendering.
        """
        context = {
            'first_name': lead.first_name,
            'last_name': lead.last_name,
            'full_name': lead.get_full_name(),
            'email': lead.email,
            'phone': lead.phone,
            'brand_name': lead.campus.brand.name if lead.campus else '',
            'campus_name': lead.campus.name if lead.campus else '',
        }
        
        if lead.qualification_interest:
            context['qualification_name'] = lead.qualification_interest.name
            context['qualification_code'] = lead.qualification_interest.code
        
        if lead.current_stage:
            context['stage_name'] = lead.current_stage.name
        
        if lead.assigned_to:
            context['agent_name'] = lead.assigned_to.get_full_name()
            context['agent_email'] = lead.assigned_to.email
        
        return context
    
    @classmethod
    def process_due_communications(cls, limit: int = 100) -> Dict[str, int]:
        """
        Process all scheduled communications that are due.
        Called by a periodic task (e.g., Celery beat).
        """
        results = {
            'processed': 0,
            'sent': 0,
            'failed': 0,
            'skipped': 0
        }
        
        due_communications = CommunicationCycle.objects.filter(
            status='SCHEDULED',
            scheduled_at__lte=timezone.now(),
            is_active=True,
            lead__nurture_active=True
        ).select_related('lead', 'template')[:limit]
        
        for cycle in due_communications:
            results['processed'] += 1
            
            if not cycle.template:
                cycle.status = 'SKIPPED'
                cycle.error_message = 'No template configured'
                cycle.save()
                results['skipped'] += 1
                continue
            
            if cycle.lead.unsubscribed:
                cycle.status = 'SKIPPED'
                cycle.error_message = 'Lead unsubscribed'
                cycle.save()
                results['skipped'] += 1
                continue
            
            try:
                sent, error = cls.send_communication(cycle.lead, cycle.template)
                
                if sent:
                    cycle.status = 'SENT'
                    cycle.sent_at = timezone.now()
                    cycle.channel_used = error  # In success case, error contains channel used
                    results['sent'] += 1
                else:
                    cycle.retry_count += 1
                    if cycle.retry_count >= 3:
                        cycle.status = 'FAILED'
                        cycle.error_message = error or 'Max retries exceeded'
                        results['failed'] += 1
                    else:
                        # Reschedule for retry
                        cycle.scheduled_at = timezone.now() + timedelta(hours=1)
                        cycle.error_message = error or 'Unknown error'
                
                cycle.save()
                
            except Exception as e:
                logger.error(f"Error processing communication {cycle.pk}: {str(e)}")
                cycle.status = 'FAILED'
                cycle.error_message = str(e)
                cycle.save()
                results['failed'] += 1
        
        return results
    
    @classmethod
    def pause_nurture(cls, lead: Lead, reason: str = '') -> None:
        """
        Pause nurture communications for a lead.
        """
        lead.nurture_active = False
        lead.save(update_fields=['nurture_active', 'updated_at'])
        
        # Cancel scheduled communications
        CommunicationCycle.objects.filter(
            lead=lead,
            status='SCHEDULED'
        ).update(
            status='CANCELLED',
            pause_reason=reason,
            paused_at=timezone.now()
        )
    
    @classmethod
    def resume_nurture(cls, lead: Lead) -> None:
        """
        Resume nurture communications for a lead.
        """
        lead.nurture_active = True
        lead.save(update_fields=['nurture_active', 'updated_at'])
        
        # Schedule next communication
        cls.schedule_next_communication(lead)
    
    @classmethod
    def record_engagement(
        cls, 
        lead: Lead, 
        event_type: str,
        metadata: Dict[str, Any] = None,
        source_ip: str = None,
        user_agent: str = None
    ) -> LeadEngagement:
        """
        Record an engagement event and notify the agent.
        """
        engagement = LeadEngagement.objects.create(
            lead=lead,
            event_type=event_type,
            metadata=metadata or {},
            source_ip=source_ip,
            user_agent=user_agent
        )
        
        # Notify agent
        if lead.assigned_to:
            cls.notify_agent_of_engagement(lead, engagement)
        
        return engagement
    
    @classmethod
    def notify_agent_of_engagement(cls, lead: Lead, engagement: LeadEngagement) -> None:
        """
        Create in-app notification for agent about lead engagement.
        """
        event_messages = {
            'QUOTE_VIEWED': f'{lead.get_full_name()} viewed your quote',
            'QUOTE_ACCEPTED': f'{lead.get_full_name()} accepted your quote! 🎉',
            'EMAIL_OPENED': f'{lead.get_full_name()} opened your email',
            'EMAIL_CLICKED': f'{lead.get_full_name()} clicked a link in your email',
            'WHATSAPP_READ': f'{lead.get_full_name()} read your WhatsApp message',
            'WEBSITE_VISIT': f'{lead.get_full_name()} visited the website',
            'FORM_SUBMITTED': f'{lead.get_full_name()} submitted a form',
            'DOCUMENT_UPLOADED': f'{lead.get_full_name()} uploaded a document',
        }
        
        priority_events = ['QUOTE_VIEWED', 'QUOTE_ACCEPTED', 'EMAIL_CLICKED', 'FORM_SUBMITTED']
        
        AgentNotification.objects.create(
            agent=lead.assigned_to,
            notification_type='ENGAGEMENT',
            priority='HIGH' if engagement.event_type in priority_events else 'NORMAL',
            title=event_messages.get(engagement.event_type, f'New engagement from {lead.get_full_name()}'),
            message=f'{engagement.get_event_type_display()} at {engagement.event_timestamp.strftime("%H:%M")}',
            lead=lead,
            engagement=engagement,
            action_url=f'/crm/leads/{lead.pk}/',
            action_label='View Lead'
        )
        
        # Mark engagement as notified
        engagement.agent_notified = True
        engagement.agent_notified_at = timezone.now()
        engagement.save(update_fields=['agent_notified', 'agent_notified_at'])
    
    @classmethod
    def get_communication_history(cls, lead: Lead, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get communication history for a lead.
        """
        cycles = CommunicationCycle.objects.filter(
            lead=lead
        ).select_related('template').order_by('-scheduled_at')[:limit]
        
        history = []
        for cycle in cycles:
            history.append({
                'id': cycle.pk,
                'scheduled_at': cycle.scheduled_at,
                'sent_at': cycle.sent_at,
                'status': cycle.status,
                'template_name': cycle.template.name if cycle.template else 'N/A',
                'channel': cycle.channel_used,
                'error': cycle.error_message
            })
        
        return history
    
    @classmethod
    def get_engagement_summary(cls, lead: Lead) -> Dict[str, Any]:
        """
        Get engagement summary for a lead.
        """
        engagements = LeadEngagement.objects.filter(lead=lead)
        
        summary = {
            'total_engagements': engagements.count(),
            'engagement_score': lead.engagement_score,
            'last_engagement': lead.last_engagement_at,
            'by_type': {},
            'recent': []
        }
        
        # Count by type
        for event_type, _ in LeadEngagement.EVENT_TYPES:
            count = engagements.filter(event_type=event_type).count()
            if count > 0:
                summary['by_type'][event_type] = count
        
        # Recent engagements
        recent = engagements.order_by('-event_timestamp')[:5]
        for eng in recent:
            summary['recent'].append({
                'type': eng.event_type,
                'display': eng.get_event_type_display(),
                'timestamp': eng.event_timestamp,
                'score': eng.score_value
            })
        
        return summary
