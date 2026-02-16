"""
CRM Messaging Services

Unified messaging service for sending messages across all channels:
- WhatsApp
- Facebook Messenger
- Instagram DM
- SMS
- Email
"""
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from django.utils import timezone
from django.db import transaction
from django.conf import settings

if TYPE_CHECKING:
    from crm.communication_models import Conversation, Message, MessageTemplate
    from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class MessagingService:
    """
    Unified messaging service for sending across all channels.
    
    Handles:
    - Channel selection and connector instantiation
    - Message creation and status tracking
    - Template variable substitution
    - 24-hour window enforcement for WhatsApp
    """
    
    def __init__(self, conversation: 'Conversation'):
        self.conversation = conversation
        self.connector = None
        self._setup_connector()
    
    def _setup_connector(self):
        """Set up the appropriate connector for the conversation channel."""
        from integrations.models import IntegrationConnection
        from integrations.connectors import (
            WhatsAppConnector,
            FacebookConnector,
            InstagramConnector,
            BulkSMSConnector,
            ClickatellConnector,
            MicrosoftGraphConnector,
        )
        
        channel = self.conversation.channel
        
        if channel == 'whatsapp':
            if not self.conversation.social_channel:
                raise ValueError("WhatsApp conversation missing social channel")
            
            connection = IntegrationConnection.objects.filter(
                provider='whatsapp',
                is_active=True
            ).first()
            
            if connection:
                self.connector = WhatsAppConnector(connection, self.conversation.social_channel)
        
        elif channel == 'facebook':
            if not self.conversation.social_channel:
                raise ValueError("Facebook conversation missing social channel")
            
            connection = IntegrationConnection.objects.filter(
                provider='facebook',
                is_active=True
            ).first()
            
            if connection:
                self.connector = FacebookConnector(connection, self.conversation.social_channel)
        
        elif channel == 'instagram':
            if not self.conversation.social_channel:
                raise ValueError("Instagram conversation missing social channel")
            
            connection = IntegrationConnection.objects.filter(
                provider='instagram',
                is_active=True
            ).first()
            
            if connection:
                self.connector = InstagramConnector(connection, self.conversation.social_channel)
        
        elif channel == 'sms':
            if not self.conversation.sms_config:
                raise ValueError("SMS conversation missing SMS config")
            
            sms_config = self.conversation.sms_config
            connection = IntegrationConnection.objects.filter(
                provider=sms_config.provider,
                is_active=True
            ).first()
            
            if connection:
                if sms_config.provider == 'bulksms':
                    self.connector = BulkSMSConnector(connection, sms_config)
                elif sms_config.provider == 'clickatell':
                    self.connector = ClickatellConnector(connection, sms_config)
        
        elif channel == 'email':
            if not self.conversation.email_account:
                raise ValueError("Email conversation missing email account")
            
            connection = IntegrationConnection.objects.filter(
                provider='microsoft365',
                is_active=True
            ).first()
            
            if connection:
                self.connector = MicrosoftGraphConnector(connection, self.conversation.email_account)
    
    def can_send_message(self) -> tuple[bool, str]:
        """
        Check if we can send a message in this conversation.
        
        Returns:
            Tuple of (can_send, reason)
        """
        if not self.connector:
            return False, "No connector available for this channel"
        
        # Check WhatsApp 24-hour window
        if self.conversation.channel == 'whatsapp':
            if self.conversation.window_expires_at:
                if self.conversation.window_expires_at < timezone.now():
                    return False, "WhatsApp 24-hour window expired. Use a template message."
        
        return True, "OK"
    
    def can_send_template(self) -> tuple[bool, str]:
        """Check if we can send a template message."""
        if not self.connector:
            return False, "No connector available"
        
        # Templates only supported on WhatsApp
        if self.conversation.channel != 'whatsapp':
            return False, "Template messages only supported on WhatsApp"
        
        return True, "OK"
    
    @transaction.atomic
    def send_text(self, text: str, sender: 'User' = None, **kwargs) -> 'Message':
        """
        Send a text message.
        
        Args:
            text: Message text
            sender: User sending the message
            **kwargs: Additional options passed to connector
            
        Returns:
            Created Message object
        """
        from crm.communication_models import Message
        
        can_send, reason = self.can_send_message()
        if not can_send:
            raise ValueError(reason)
        
        # Get recipient identifier
        recipient = self._get_recipient()
        
        # Create pending message
        message = Message.objects.create(
            conversation=self.conversation,
            direction='outbound',
            message_type='text',
            content={'text': text},
            text=text,
            sender_name=sender.get_full_name() if sender else 'System',
            sender_identifier=self._get_sender_identifier(),
            status='pending'
        )
        
        try:
            # Send via connector
            result = self.connector.send_text(recipient, text, **kwargs)
            
            if result.success:
                message.external_id = result.external_id
                message.status = result.status.value if result.status else 'sent'
                message.sent_at = timezone.now()
            else:
                message.status = 'failed'
                message.error_code = result.error_code
                message.error_message = result.error_message
                message.failed_at = timezone.now()
            
            message.save()
            
            # Update conversation
            self._update_conversation_on_send()
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            message.status = 'failed'
            message.error_message = str(e)
            message.failed_at = timezone.now()
            message.save()
            raise
        
        return message
    
    @transaction.atomic
    def send_media(self, media_type: str, media_url: str, 
                   caption: str = None, filename: str = None,
                   sender: 'User' = None, **kwargs) -> 'Message':
        """
        Send a media message.
        
        Args:
            media_type: Type of media (image, video, audio, document)
            media_url: URL to the media file
            caption: Optional caption
            filename: Filename for documents
            sender: User sending the message
        """
        from crm.communication_models import Message
        
        can_send, reason = self.can_send_message()
        if not can_send:
            raise ValueError(reason)
        
        recipient = self._get_recipient()
        
        # Create pending message
        message = Message.objects.create(
            conversation=self.conversation,
            direction='outbound',
            message_type=media_type,
            content={
                'media_url': media_url,
                'caption': caption,
                'filename': filename
            },
            text=caption or '',
            media_url=media_url,
            media_type=media_type,
            media_filename=filename,
            sender_name=sender.get_full_name() if sender else 'System',
            sender_identifier=self._get_sender_identifier(),
            status='pending'
        )
        
        try:
            result = self.connector.send_media(
                recipient, media_type, media_url,
                caption=caption, filename=filename, **kwargs
            )
            
            if result.success:
                message.external_id = result.external_id
                message.status = result.status.value if result.status else 'sent'
                message.sent_at = timezone.now()
            else:
                message.status = 'failed'
                message.error_code = result.error_code
                message.error_message = result.error_message
                message.failed_at = timezone.now()
            
            message.save()
            self._update_conversation_on_send()
            
        except Exception as e:
            logger.error(f"Error sending media: {e}")
            message.status = 'failed'
            message.error_message = str(e)
            message.failed_at = timezone.now()
            message.save()
            raise
        
        return message
    
    @transaction.atomic
    def send_template(self, template: 'MessageTemplate', 
                      variables: Dict[str, str] = None,
                      sender: 'User' = None, **kwargs) -> 'Message':
        """
        Send a template message.
        
        Args:
            template: MessageTemplate to send
            variables: Variable substitutions
            sender: User sending the message
        """
        from crm.communication_models import Message
        
        can_send, reason = self.can_send_template()
        if not can_send:
            raise ValueError(reason)
        
        recipient = self._get_recipient()
        variables = variables or {}
        
        # Substitute variables in content
        rendered_content = template.content
        for key, value in variables.items():
            rendered_content = rendered_content.replace(f'{{{{{key}}}}}', str(value))
        
        # Build template variables for WhatsApp
        template_vars = {}
        for i, (key, value) in enumerate(variables.items(), start=1):
            template_vars[i] = value
        
        # Create pending message
        message = Message.objects.create(
            conversation=self.conversation,
            direction='outbound',
            message_type='template',
            template=template,
            content={
                'template_name': template.template_id,
                'variables': variables,
                'rendered': rendered_content
            },
            text=rendered_content,
            sender_name=sender.get_full_name() if sender else 'System',
            sender_identifier=self._get_sender_identifier(),
            status='pending'
        )
        
        try:
            result = self.connector.send_template(
                recipient,
                template.template_id,
                template_vars=template_vars,
                language=template.language,
                **kwargs
            )
            
            if result.success:
                message.external_id = result.external_id
                message.status = result.status.value if result.status else 'sent'
                message.sent_at = timezone.now()
            else:
                message.status = 'failed'
                message.error_code = result.error_code
                message.error_message = result.error_message
                message.failed_at = timezone.now()
            
            message.save()
            self._update_conversation_on_send()
            
        except Exception as e:
            logger.error(f"Error sending template: {e}")
            message.status = 'failed'
            message.error_message = str(e)
            message.failed_at = timezone.now()
            message.save()
            raise
        
        return message
    
    @transaction.atomic
    def send_email(self, subject: str, body: str, html_body: str = None,
                   sender: 'User' = None, cc: List[str] = None,
                   bcc: List[str] = None, **kwargs) -> 'Message':
        """
        Send an email message.
        
        Args:
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)
            sender: User sending
            cc: CC recipients
            bcc: BCC recipients
        """
        from crm.communication_models import Message
        
        if self.conversation.channel != 'email':
            raise ValueError("Not an email conversation")
        
        if not self.connector:
            raise ValueError("No email connector available")
        
        recipient = self.conversation.contact_email
        if not recipient:
            raise ValueError("No recipient email address")
        
        # Create pending message
        message = Message.objects.create(
            conversation=self.conversation,
            direction='outbound',
            message_type='email',
            content={
                'subject': subject,
                'body': body,
                'html_body': html_body,
                'cc': cc,
                'bcc': bcc
            },
            text=body[:500] if body else '',
            sender_name=sender.get_full_name() if sender else 'System',
            sender_identifier=self.conversation.email_account.email_address if self.conversation.email_account else '',
            status='pending'
        )
        
        try:
            result = self.connector.send_text(
                recipient, body,
                subject=subject,
                html_body=html_body,
                cc=cc or [],
                bcc=bcc or [],
                **kwargs
            )
            
            if result.success:
                message.external_id = result.external_id
                message.status = 'sent'
                message.sent_at = timezone.now()
            else:
                message.status = 'failed'
                message.error_code = result.error_code
                message.error_message = result.error_message
                message.failed_at = timezone.now()
            
            message.save()
            self._update_conversation_on_send()
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            message.status = 'failed'
            message.error_message = str(e)
            message.failed_at = timezone.now()
            message.save()
            raise
        
        return message
    
    def _get_recipient(self) -> str:
        """Get the recipient identifier for the current channel."""
        channel = self.conversation.channel
        
        if channel in ('whatsapp', 'sms'):
            return self.conversation.contact_phone or self.conversation.contact_identifier
        elif channel in ('facebook', 'instagram'):
            return self.conversation.contact_identifier
        elif channel == 'email':
            return self.conversation.contact_email
        
        return self.conversation.contact_identifier
    
    def _get_sender_identifier(self) -> str:
        """Get the sender identifier for the current channel."""
        channel = self.conversation.channel
        
        if channel == 'whatsapp' and self.conversation.social_channel:
            return self.conversation.social_channel.phone_number or ''
        elif channel in ('facebook', 'instagram') and self.conversation.social_channel:
            return self.conversation.social_channel.external_id or ''
        elif channel == 'sms' and self.conversation.sms_config:
            return self.conversation.sms_config.sender_id or ''
        elif channel == 'email' and self.conversation.email_account:
            return self.conversation.email_account.email_address
        
        return ''
    
    def _update_conversation_on_send(self):
        """Update conversation after sending a message."""
        self.conversation.last_message_at = timezone.now()
        self.conversation.message_count = (self.conversation.message_count or 0) + 1
        self.conversation.save()


def send_template_message(conversation: 'Conversation', template_id: int,
                          variables: Dict[str, str] = None) -> Optional['Message']:
    """
    Helper function to send a template message by template ID.
    
    Used by automation rules and campaigns.
    """
    from crm.communication_models import MessageTemplate
    
    try:
        template = MessageTemplate.objects.get(id=template_id)
        service = MessagingService(conversation)
        return service.send_template(template, variables)
    except MessageTemplate.DoesNotExist:
        logger.error(f"Template {template_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error sending template: {e}")
        return None


class BulkMessagingService:
    """
    Service for sending bulk messages to multiple recipients.
    
    Used by campaigns and broadcasts.
    """
    
    def __init__(self, brand, channel: str):
        """
        Initialize bulk messaging service.
        
        Args:
            brand: Brand to send from
            channel: Channel to use (sms, whatsapp, email)
        """
        self.brand = brand
        self.channel = channel
    
    def send_sms_broadcast(self, recipients: List[str], text: str,
                           sender_id: str = None) -> Dict[str, Any]:
        """
        Send SMS to multiple recipients.
        
        Args:
            recipients: List of phone numbers
            text: Message text
            sender_id: Optional sender ID override
            
        Returns:
            Dict with success count, failure count, and details
        """
        from crm.communication_models import SMSConfig
        from integrations.connectors import get_sms_connector
        
        sms_config = SMSConfig.objects.filter(
            brand=self.brand,
            is_active=True
        ).first()
        
        if not sms_config:
            raise ValueError("No SMS configuration found for brand")
        
        connector = get_sms_connector(sms_config)
        
        # Use bulk send if available
        results = connector.send_bulk(recipients, text, sender_id=sender_id)
        
        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count
        
        return {
            'total': len(recipients),
            'success': success_count,
            'failed': failure_count,
            'results': [
                {
                    'recipient': recipients[i],
                    'success': r.success,
                    'external_id': r.external_id,
                    'error': r.error_message
                }
                for i, r in enumerate(results)
            ]
        }
    
    def send_whatsapp_broadcast(self, recipients: List[str], 
                                template: 'MessageTemplate',
                                variables_list: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Send WhatsApp template messages to multiple recipients.
        
        WhatsApp only allows template messages for broadcast.
        
        Args:
            recipients: List of phone numbers
            template: MessageTemplate to send
            variables_list: List of variable dicts, one per recipient
        """
        from crm.communication_models import SocialChannel, Conversation, Message
        from integrations.models import IntegrationConnection
        from integrations.connectors import WhatsAppConnector
        
        # Get channel
        channel = SocialChannel.objects.filter(
            brand=self.brand,
            platform='whatsapp',
            is_active=True
        ).first()
        
        if not channel:
            raise ValueError("No WhatsApp channel found for brand")
        
        connection = IntegrationConnection.objects.filter(
            provider='whatsapp',
            is_active=True
        ).first()
        
        if not connection:
            raise ValueError("No WhatsApp connection configured")
        
        connector = WhatsAppConnector(connection, channel)
        
        results = []
        variables_list = variables_list or [{}] * len(recipients)
        
        for i, recipient in enumerate(recipients):
            variables = variables_list[i] if i < len(variables_list) else {}
            
            # Build template vars
            template_vars = {}
            for j, (key, value) in enumerate(variables.items(), start=1):
                template_vars[j] = value
            
            try:
                result = connector.send_template(
                    recipient,
                    template.template_id,
                    template_vars=template_vars,
                    language=template.language
                )
                
                results.append({
                    'recipient': recipient,
                    'success': result.success,
                    'external_id': result.external_id,
                    'error': result.error_message
                })
                
            except Exception as e:
                results.append({
                    'recipient': recipient,
                    'success': False,
                    'external_id': None,
                    'error': str(e)
                })
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'total': len(recipients),
            'success': success_count,
            'failed': len(results) - success_count,
            'results': results
        }
