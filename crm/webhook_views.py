"""
CRM Webhook Views

Handles incoming webhooks from:
- Meta (WhatsApp, Facebook, Instagram)
- SMS providers (BulkSMS, Clickatell)
- Microsoft 365 (email notifications)
"""
import json
import logging
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import transaction

from integrations.models import IntegrationConnection
from integrations.connectors import (
    WhatsAppConnector,
    FacebookConnector,
    InstagramConnector,
    BulkSMSConnector,
    ClickatellConnector,
    MicrosoftGraphConnector,
    MessageStatus,
)

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class MetaWebhookView(View):
    """
    Unified webhook handler for all Meta platforms.
    
    Handles:
    - WhatsApp message/status webhooks
    - Facebook Messenger webhooks
    - Instagram DM webhooks
    
    Meta sends webhooks to a single endpoint per app.
    """
    
    def get(self, request):
        """
        Handle webhook verification (subscribe flow).
        
        Meta sends:
        - hub.mode: 'subscribe'
        - hub.verify_token: your configured token
        - hub.challenge: string to echo back
        """
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        # Get expected token from settings or connection
        from django.conf import settings
        expected_token = getattr(settings, 'META_WEBHOOK_VERIFY_TOKEN', None)
        
        if not expected_token:
            # Try to get from any active Meta connection
            connection = IntegrationConnection.objects.filter(
                provider__in=['whatsapp', 'facebook', 'instagram'],
                is_active=True
            ).first()
            if connection:
                expected_token = connection.webhook_secret
        
        if mode == 'subscribe' and token == expected_token:
            logger.info("Meta webhook verification successful")
            return HttpResponse(challenge, content_type='text/plain')
        
        logger.warning(f"Meta webhook verification failed: mode={mode}, token_match={token == expected_token}")
        return HttpResponse('Verification failed', status=403)
    
    def post(self, request):
        """
        Handle incoming webhook events.
        
        Payload structure varies by platform but includes:
        - object: 'whatsapp_business_account', 'page', 'instagram'
        - entry: list of events
        """
        try:
            signature = request.headers.get('X-Hub-Signature-256', '')
            body = request.body
            
            # Parse payload
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in Meta webhook")
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
            
            # Determine platform
            obj_type = payload.get('object', '')
            
            if obj_type == 'whatsapp_business_account':
                self._handle_whatsapp(payload, body, signature)
            elif obj_type == 'page':
                self._handle_facebook(payload, body, signature)
            elif obj_type == 'instagram':
                self._handle_instagram(payload, body, signature)
            else:
                logger.warning(f"Unknown Meta webhook object type: {obj_type}")
            
            # Always return 200 quickly to acknowledge receipt
            return HttpResponse('OK')
            
        except Exception as e:
            logger.error(f"Error processing Meta webhook: {e}", exc_info=True)
            # Still return 200 to prevent retries
            return HttpResponse('OK')
    
    def _handle_whatsapp(self, payload, body, signature):
        """Process Facebook Messenger webhook events."""

        from integrations.services.whatsapp_webhooks import WhatsAppWebhookService

        service = WhatsAppWebhookService()
        service.process_payload(payload, body, signature)


    
    def _handle_facebook(self, payload, body, signature):
        """Process Facebook Messenger webhook events."""
        from crm.communication_models import SocialChannel
        
        for entry in payload.get('entry', []):
            page_id = entry.get('id')
            
            channel = SocialChannel.objects.filter(
                platform='facebook',
                external_id=page_id,
                is_active=True
            ).first()
            
            if not channel:
                logger.warning(f"No channel found for Facebook page_id: {page_id}")
                continue
            
            connection = IntegrationConnection.objects.filter(
                provider='facebook',
                is_active=True
            ).first()
            
            if connection:
                connector = FacebookConnector(connection, channel)
                if signature and not connector.verify_webhook(body, signature):
                    logger.warning("Facebook webhook signature verification failed")
                    continue
                
                messages = connector.parse_webhook(payload)
                
                for msg in messages:
                    self._process_inbound_message(channel, msg, 'facebook')
    
    def _handle_instagram(self, payload, body, signature):
        """Process Instagram DM webhook events."""
        from crm.communication_models import SocialChannel
        
        for entry in payload.get('entry', []):
            ig_user_id = entry.get('id')
            
            channel = SocialChannel.objects.filter(
                platform='instagram',
                external_id=ig_user_id,
                is_active=True
            ).first()
            
            if not channel:
                logger.warning(f"No channel found for Instagram user_id: {ig_user_id}")
                continue
            
            connection = IntegrationConnection.objects.filter(
                provider='instagram',
                is_active=True
            ).first()
            
            if connection:
                connector = InstagramConnector(connection, channel)
                messages = connector.parse_webhook(payload)
                
                for msg in messages:
                    self._process_inbound_message(channel, msg, 'instagram')
    
    @transaction.atomic
    def _process_inbound_message(self, channel, inbound_msg, platform):
        """
        Process an inbound message and update conversation.
        
        Args:
            channel: SocialChannel instance
            inbound_msg: InboundMessage dataclass from connector
            platform: Platform identifier
        """
        from crm.communication_models import Conversation, Message
        from crm.models import Lead
        
        # Find or create conversation
        conversation = Conversation.objects.filter(
            channel=platform,
            social_channel=channel,
            contact_identifier=inbound_msg.sender_id
        ).first()
        
        # Try to find associated lead
        lead = None
        if inbound_msg.sender_phone:
            lead = Lead.objects.filter(phone=inbound_msg.sender_phone).first()
        if not lead and inbound_msg.sender_email:
            lead = Lead.objects.filter(email=inbound_msg.sender_email).first()
        
        if not conversation:
            conversation = Conversation.objects.create(
                brand=channel.brand,
                campus=channel.campus,
                channel=platform,
                social_channel=channel,
                contact_identifier=inbound_msg.sender_id,
                contact_name=inbound_msg.sender_name or '',
                contact_phone=inbound_msg.sender_phone,
                contact_email=inbound_msg.sender_email,
                lead=lead,
                status='open',
                window_expires_at=timezone.now() + timezone.timedelta(hours=24) if platform == 'whatsapp' else None
            )
        else:
            # Update conversation
            conversation.contact_name = inbound_msg.sender_name or conversation.contact_name
            conversation.contact_phone = inbound_msg.sender_phone or conversation.contact_phone
            
            # Reopen if closed
            if conversation.status == 'closed':
                conversation.status = 'open'
            
            # Reset 24-hour window for WhatsApp
            if platform == 'whatsapp':
                conversation.window_expires_at = timezone.now() + timezone.timedelta(hours=24)
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            external_id=inbound_msg.external_id,
            direction='inbound',
            message_type=inbound_msg.message_type,
            content=inbound_msg.content,
            text=inbound_msg.text or '',
            sender_name=inbound_msg.sender_name,
            sender_identifier=inbound_msg.sender_id,
            media_url=inbound_msg.media_url,
            media_type=inbound_msg.media_mime_type,
            media_filename=inbound_msg.media_filename,
            status='delivered',
            delivered_at=timezone.now(),
            metadata=inbound_msg.metadata or {}
        )
        
        # Update conversation stats
        conversation.last_message_at = timezone.now()
        conversation.message_count = (conversation.message_count or 0) + 1
        conversation.unread_count = (conversation.unread_count or 0) + 1
        conversation.save()
        
        # Trigger automation rules
        self._check_automation_rules(conversation, message)
        
        logger.info(f"Processed inbound {platform} message: {inbound_msg.external_id}")
    
    def _process_status_update(self, status_data, platform):
        """
        Update message delivery status.
        
        WhatsApp status structure:
        {
            "id": "wamid.xxx",
            "status": "sent|delivered|read|failed",
            "timestamp": "...",
            "recipient_id": "...",
            "errors": [...]  # if failed
        }
        """
        from crm.communication_models import Message
        
        message_id = status_data.get('id')
        status = status_data.get('status', '').lower()
        
        message = Message.objects.filter(external_id=message_id).first()
        if not message:
            return
        
        # Map status
        status_map = {
            'sent': 'sent',
            'delivered': 'delivered',
            'read': 'read',
            'failed': 'failed',
        }
        
        new_status = status_map.get(status)
        if not new_status:
            return
        
        # Update message
        message.status = new_status
        
        if new_status == 'delivered':
            message.delivered_at = timezone.now()
        elif new_status == 'read':
            message.read_at = timezone.now()
        elif new_status == 'failed':
            errors = status_data.get('errors', [])
            if errors:
                message.error_code = str(errors[0].get('code', ''))
                message.error_message = errors[0].get('title', 'Unknown error')
            message.failed_at = timezone.now()
        
        message.save()
        
        logger.info(f"Updated message {message_id} status to {new_status}")
    
    def _check_automation_rules(self, conversation, message):
        """
        Check and execute automation rules for new messages.
        
        Runs matching automation rules based on triggers.
        """
        from crm.communication_models import AutomationRule, AutomationExecution
        
        # Get active rules for this brand/channel
        rules = AutomationRule.objects.filter(
            brand=conversation.brand,
            is_active=True,
            trigger_type__in=['new_message', 'keyword']
        )
        
        for rule in rules:
            should_execute = False
            
            if rule.trigger_type == 'new_message':
                # Check channel filter
                if rule.trigger_config.get('channels'):
                    should_execute = conversation.channel in rule.trigger_config['channels']
                else:
                    should_execute = True
            
            elif rule.trigger_type == 'keyword':
                keywords = rule.trigger_config.get('keywords', [])
                text_lower = (message.text or '').lower()
                should_execute = any(kw.lower() in text_lower for kw in keywords)
            
            if should_execute:
                self._execute_automation(rule, conversation, message)
    
    def _execute_automation(self, rule, conversation, message):
        """Execute a single automation rule."""
        from crm.communication_models import AutomationExecution
        
        execution = AutomationExecution.objects.create(
            rule=rule,
            conversation=conversation,
            triggered_message=message,
            status='executing'
        )
        
        try:
            actions = rule.action_config.get('actions', [])
            
            for action in actions:
                action_type = action.get('type')
                
                if action_type == 'assign_to':
                    # Assign conversation to agent
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    
                    agent_id = action.get('agent_id')
                    if agent_id:
                        agent = User.objects.filter(id=agent_id).first()
                        if agent:
                            conversation.assigned_to = agent
                            conversation.save()
                
                elif action_type == 'add_tag':
                    # Add tag to conversation
                    from crm.communication_models import ConversationTag
                    
                    tag_name = action.get('tag')
                    if tag_name:
                        tag, _ = ConversationTag.objects.get_or_create(
                            brand=conversation.brand,
                            name=tag_name
                        )
                        conversation.tags.add(tag)
                
                elif action_type == 'send_template':
                    # Send template message
                    template_id = action.get('template_id')
                    if template_id:
                        from crm.services.messaging import send_template_message
                        send_template_message(conversation, template_id)
                
                elif action_type == 'create_lead':
                    # Create lead from conversation if not exists
                    if not conversation.lead:
                        from crm.models import Lead
                        lead = Lead.objects.create(
                            brand=conversation.brand,
                            campus=conversation.campus,
                            first_name=conversation.contact_name or 'Unknown',
                            phone=conversation.contact_phone,
                            email=conversation.contact_email,
                            source=f'{conversation.channel}_inbound',
                            status='new'
                        )
                        conversation.lead = lead
                        conversation.save()
            
            execution.status = 'completed'
            execution.completed_at = timezone.now()
            execution.save()
            
        except Exception as e:
            logger.error(f"Automation execution error: {e}")
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.save()


@method_decorator(csrf_exempt, name='dispatch')
class SMSWebhookView(View):
    """
    Webhook handler for SMS provider callbacks.
    
    Handles delivery reports and inbound messages from:
    - BulkSMS
    - Clickatell
    """
    
    def post(self, request, provider):
        """
        Handle SMS webhook callback.
        
        Args:
            provider: 'bulksms' or 'clickatell'
        """
        try:
            payload = json.loads(request.body)
            
            if provider == 'bulksms':
                self._handle_bulksms(payload)
            elif provider == 'clickatell':
                self._handle_clickatell(payload)
            else:
                logger.warning(f"Unknown SMS provider: {provider}")
            
            return HttpResponse('OK')
            
        except Exception as e:
            logger.error(f"Error processing SMS webhook: {e}", exc_info=True)
            return HttpResponse('OK')
    
    def _handle_bulksms(self, payload):
        """Process BulkSMS webhook."""
        from crm.communication_models import Message, SMSConfig
        
        event_type = payload.get('type', '')
        
        if event_type == 'delivery_report.status_update':
            # Delivery report
            message_id = payload.get('relatedSentMessageId')
            status_data = payload.get('status', {})
            status_type = status_data.get('type', '').lower()
            
            message = Message.objects.filter(external_id=message_id).first()
            if message:
                if status_type == 'delivered':
                    message.status = 'delivered'
                    message.delivered_at = timezone.now()
                elif status_type in ('failed', 'rejected'):
                    message.status = 'failed'
                    message.failed_at = timezone.now()
                    message.error_message = status_data.get('subtype', 'Delivery failed')
                
                message.save()
        
        elif 'from' in payload and 'body' in payload:
            # Inbound message
            self._process_inbound_sms(payload, 'bulksms')
    
    def _handle_clickatell(self, payload):
        """Process Clickatell webhook."""
        from crm.communication_models import Message
        
        event = payload.get('event', '')
        
        if event in ('message_received', 'message'):
            # Inbound message
            self._process_inbound_sms(payload, 'clickatell')
        
        elif 'statusCode' in payload:
            # Delivery report
            message_id = payload.get('apiMessageId')
            status_code = payload.get('statusCode', 0)
            
            message = Message.objects.filter(external_id=message_id).first()
            if message:
                # Clickatell status codes: 003=delivered, 004-011=failed
                if status_code == 3:
                    message.status = 'delivered'
                    message.delivered_at = timezone.now()
                elif status_code >= 4:
                    message.status = 'failed'
                    message.failed_at = timezone.now()
                    message.error_message = payload.get('description', 'Delivery failed')
                
                message.save()
    
    @transaction.atomic
    def _process_inbound_sms(self, payload, provider):
        """Process inbound SMS message."""
        from crm.communication_models import SMSConfig, Conversation, Message
        from crm.models import Lead
        
        # Extract sender info based on provider
        if provider == 'bulksms':
            sender = payload.get('from', '')
            text = payload.get('body', '')
            recipient = payload.get('to', '')
            message_id = payload.get('id')
        else:  # clickatell
            sender = payload.get('fromNumber', '')
            text = payload.get('content', '')
            recipient = payload.get('toNumber', '')
            message_id = payload.get('messageId')
        
        # Find SMS config by recipient number
        sms_config = SMSConfig.objects.filter(
            is_active=True,
            provider=provider
        ).first()
        
        if not sms_config:
            logger.warning(f"No SMS config found for {provider}")
            return
        
        # Find or create conversation
        conversation = Conversation.objects.filter(
            channel='sms',
            contact_identifier=sender,
            brand=sms_config.brand
        ).first()
        
        # Try to find lead
        lead = Lead.objects.filter(phone__contains=sender[-10:]).first()
        
        if not conversation:
            conversation = Conversation.objects.create(
                brand=sms_config.brand,
                channel='sms',
                sms_config=sms_config,
                contact_identifier=sender,
                contact_phone=sender,
                lead=lead,
                status='open'
            )
        else:
            if conversation.status == 'closed':
                conversation.status = 'open'
        
        # Create message
        Message.objects.create(
            conversation=conversation,
            external_id=message_id,
            direction='inbound',
            message_type='text',
            content={'text': text},
            text=text,
            sender_identifier=sender,
            status='delivered',
            delivered_at=timezone.now()
        )
        
        # Update conversation
        conversation.last_message_at = timezone.now()
        conversation.message_count = (conversation.message_count or 0) + 1
        conversation.unread_count = (conversation.unread_count or 0) + 1
        conversation.save()
        
        logger.info(f"Processed inbound SMS from {sender}")


@method_decorator(csrf_exempt, name='dispatch')
class MicrosoftWebhookView(View):
    """
    Webhook handler for Microsoft Graph subscriptions.
    
    Handles email notification webhooks.
    """
    
    def post(self, request):
        """
        Handle Microsoft Graph webhook notification.
        
        Microsoft sends:
        - Validation request with validationToken
        - Change notifications with value array
        """
        try:
            # Check for validation request
            validation_token = request.GET.get('validationToken')
            if validation_token:
                # Echo back the token for subscription validation
                return HttpResponse(validation_token, content_type='text/plain')
            
            payload = json.loads(request.body)
            
            # Verify client state
            for notification in payload.get('value', []):
                client_state = notification.get('clientState')
                
                # Verify against connection
                connection = IntegrationConnection.objects.filter(
                    provider='microsoft365',
                    webhook_secret=client_state,
                    is_active=True
                ).first()
                
                if not connection:
                    logger.warning("Microsoft webhook client state mismatch")
                    continue
                
                # Process notification
                self._process_notification(notification, connection)
            
            return HttpResponse('OK')
            
        except Exception as e:
            logger.error(f"Error processing Microsoft webhook: {e}", exc_info=True)
            return HttpResponse('OK')
    
    def _process_notification(self, notification, connection):
        """
        Process a single notification.
        
        For mail, we need to fetch the actual message content.
        """
        from crm.communication_models import EmailAccount
        from integrations.connectors import MicrosoftGraphConnector, EmailSyncService
        
        resource = notification.get('resource', '')
        change_type = notification.get('changeType', '')
        
        # Extract user ID from resource path
        # e.g., "users/{user-id}/messages/{message-id}"
        parts = resource.split('/')
        
        if 'users' in parts and 'messages' in parts:
            user_index = parts.index('users')
            if user_index + 1 < len(parts):
                user_id = parts[user_index + 1]
                
                # Find email account
                email_account = EmailAccount.objects.filter(
                    external_id=user_id,
                    is_active=True
                ).first()
                
                if email_account:
                    # Trigger sync for this account
                    sync_service = EmailSyncService()
                    sync_service.sync_account(email_account)


@method_decorator(csrf_exempt, name='dispatch')
class EngagementTrackingView(View):
    """
    Track lead engagement events.
    
    Handles:
    - Email open tracking (via tracking pixel)
    - Link click tracking
    - Quote view tracking
    """
    
    def get(self, request, tracking_type):
        """
        Handle engagement tracking via GET request (e.g., tracking pixel).
        
        tracking_type: 'email-open', 'link-click', 'quote-view'
        """
        token = request.GET.get('token')
        if not token:
            return self._return_pixel()
        
        try:
            if tracking_type == 'email-open':
                self._track_email_open(token, request)
            elif tracking_type == 'link-click':
                redirect_url = request.GET.get('url', '/')
                self._track_link_click(token, request)
                from django.shortcuts import redirect
                return redirect(redirect_url)
        except Exception as e:
            logger.error(f"Error tracking engagement: {e}")
        
        return self._return_pixel()
    
    def _return_pixel(self):
        """Return a 1x1 transparent pixel."""
        import base64
        # 1x1 transparent GIF
        pixel = base64.b64decode(
            b'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
        )
        return HttpResponse(pixel, content_type='image/gif')
    
    def _track_email_open(self, token, request):
        """Track email open event."""
        from crm.models import Lead, LeadEngagement, LeadActivity, AgentNotification
        from crm.services.nurture import NurtureService
        
        # Token format: lead_id:campaign_id:timestamp_hash
        try:
            parts = token.split(':')
            if len(parts) < 2:
                return
            
            lead_id = int(parts[0])
            lead = Lead.objects.filter(pk=lead_id).first()
            
            if lead:
                # Record engagement
                NurtureService.record_engagement(
                    lead=lead,
                    engagement_type='EMAIL_OPEN',
                    channel='email',
                    metadata={
                        'token': token,
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'ip': self._get_client_ip(request),
                    }
                )
                
                # Notify agent
                NurtureService.notify_agent_of_engagement(
                    lead=lead,
                    engagement_type='email_open',
                    message=f'{lead.get_full_name()} opened your email'
                )
                
                logger.info(f"Tracked email open for lead {lead_id}")
        
        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid email tracking token: {token}")
    
    def _track_link_click(self, token, request):
        """Track link click event."""
        from crm.models import Lead
        from crm.services.nurture import NurtureService
        
        try:
            parts = token.split(':')
            if len(parts) < 2:
                return
            
            lead_id = int(parts[0])
            lead = Lead.objects.filter(pk=lead_id).first()
            
            if lead:
                NurtureService.record_engagement(
                    lead=lead,
                    engagement_type='LINK_CLICK',
                    channel='email',
                    metadata={
                        'token': token,
                        'url': request.GET.get('url', ''),
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'ip': self._get_client_ip(request),
                    }
                )
                
                NurtureService.notify_agent_of_engagement(
                    lead=lead,
                    engagement_type='link_click',
                    message=f'{lead.get_full_name()} clicked a link in your email'
                )
                
                logger.info(f"Tracked link click for lead {lead_id}")
        
        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid link tracking token: {token}")
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


@method_decorator(csrf_exempt, name='dispatch')
class QuoteViewTrackingView(View):
    """
    Track when a lead views their quote.
    
    This is triggered when the public quote page loads.
    """
    
    def post(self, request):
        """
        Record quote view event.
        
        Expected JSON:
        {
            "token": "quote-public-token",
            "event": "view"|"download"
        }
        """
        try:
            data = json.loads(request.body)
            token = data.get('token')
            event_type = data.get('event', 'view')
            
            if not token:
                return JsonResponse({'error': 'Missing token'}, status=400)
            
            from finance.models import Quote
            from crm.models import LeadEngagement, LeadActivity, AgentNotification
            from crm.services.nurture import NurtureService
            
            quote = Quote.objects.filter(public_token=token).first()
            if not quote:
                return JsonResponse({'error': 'Invalid token'}, status=404)
            
            # Update quote view timestamp
            if not quote.viewed_at:
                quote.viewed_at = timezone.now()
                quote.save(update_fields=['viewed_at'])
            
            # Record engagement for the lead
            if quote.lead:
                engagement_type = 'QUOTE_VIEW' if event_type == 'view' else 'QUOTE_DOWNLOAD'
                
                NurtureService.record_engagement(
                    lead=quote.lead,
                    engagement_type=engagement_type,
                    channel='web',
                    metadata={
                        'quote_id': str(quote.pk),
                        'quote_number': quote.quote_number,
                        'quote_total': str(quote.total_amount),
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'ip': self._get_client_ip(request),
                    }
                )
                
                # High-priority notification for quote views
                message = (
                    f'{quote.lead.get_full_name()} viewed quote {quote.quote_number} '
                    f'(R{quote.total_amount:,.0f})'
                )
                NurtureService.notify_agent_of_engagement(
                    lead=quote.lead,
                    engagement_type='quote_viewed',
                    message=message,
                    priority='high'
                )
                
                # Log activity
                LeadActivity.objects.create(
                    lead=quote.lead,
                    activity_type='QUOTE_VIEWED',
                    description=f'Quote {quote.quote_number} was viewed',
                    created_by=None
                )
                
                logger.info(f"Tracked quote view for quote {quote.quote_number}")
            
            return JsonResponse({'status': 'ok'})
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error tracking quote view: {e}", exc_info=True)
            return JsonResponse({'error': 'Server error'}, status=500)
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# URL configuration helper
def get_webhook_urls():
    """
    Return URL patterns for CRM webhooks.
    
    Add to your urls.py:
        path('webhooks/', include(get_webhook_urls()))
    """
    from django.urls import path
    
    return [
        path('meta/', MetaWebhookView.as_view(), name='meta_webhook'),
        path('sms/<str:provider>/', SMSWebhookView.as_view(), name='sms_webhook'),
        path('microsoft/', MicrosoftWebhookView.as_view(), name='microsoft_webhook'),
        path('track/<str:tracking_type>/', EngagementTrackingView.as_view(), name='engagement_tracking'),
        path('quote-view/', QuoteViewTrackingView.as_view(), name='quote_view_tracking'),
    ]
