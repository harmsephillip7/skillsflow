"""
Meta Platform Connector

Unified connector for Meta's Cloud API:
- WhatsApp Business
- Facebook Messenger
- Instagram Direct Messages
"""
import hmac
import hashlib
import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.conf import settings

from .base import (
    BaseConnector, 
    ConnectorError, 
    RateLimitError,
    MessageResult, 
    MessageStatus,
    InboundMessage,
    Contact
)


logger = logging.getLogger(__name__)


class MetaConnector(BaseConnector):
    """
    Base connector for Meta platforms.
    Handles common authentication and API patterns.
    """
    
    GRAPH_API_VERSION = 'v18.0'
    GRAPH_API_BASE = f'https://graph.facebook.com/{GRAPH_API_VERSION}'
    
    def __init__(self, connection: 'IntegrationConnection', channel: 'SocialChannel' = None):
        self.channel = channel
        super().__init__(connection)
    
    def _setup_session(self):
        """Set up session with Meta access token."""
        access_token = self.connection.access_token
        if not access_token:
            access_token = self.connection.api_key
        
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        })
    
    @property
    def provider_name(self) -> str:
        return 'meta'
    
    def verify_webhook(self, request_body: bytes, signature: str) -> bool:
        """
        Verify Meta webhook signature using app secret.
        
        Meta sends signature as: sha256=<hash>
        """
        app_secret = self.connection.api_secret
        if not app_secret:
            logger.warning("No app secret configured for Meta webhook verification")
            return False
        
        expected_signature = hmac.new(
            app_secret.encode('utf-8'),
            request_body,
            hashlib.sha256
        ).hexdigest()
        
        # Remove 'sha256=' prefix if present
        if signature.startswith('sha256='):
            signature = signature[7:]
        
        return hmac.compare_digest(expected_signature, signature)
    
    def check_health(self) -> Dict[str, Any]:
        """Check Meta API connectivity."""
        try:
            response = self._make_request('GET', f'{self.GRAPH_API_BASE}/me')
            if response.status_code == 200:
                return {
                    'healthy': True,
                    'message': 'Connected to Meta API',
                    'details': response.json()
                }
            else:
                return {
                    'healthy': False,
                    'message': f'API returned {response.status_code}',
                    'details': response.json()
                }
        except Exception as e:
            return {
                'healthy': False,
                'message': str(e),
                'details': {}
            }
    
    def refresh_token(self) -> bool:
        """
        Refresh Meta access token.
        Meta long-lived tokens last 60 days and can be refreshed.
        """
        try:
            app_id = self.connection.client_id
            app_secret = self.connection.client_secret
            current_token = self.connection.access_token
            
            response = self._make_request(
                'GET',
                f'{self.GRAPH_API_BASE}/oauth/access_token',
                params={
                    'grant_type': 'fb_exchange_token',
                    'client_id': app_id,
                    'client_secret': app_secret,
                    'fb_exchange_token': current_token,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.connection.access_token = data['access_token']
                expires_in = data.get('expires_in', 5184000)  # 60 days default
                self.connection.token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
                self.connection.save()
                
                # Update session header
                self.session.headers['Authorization'] = f"Bearer {data['access_token']}"
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to refresh Meta token: {e}")
            return False


class WhatsAppConnector(MetaConnector):
    """
    WhatsApp Business Cloud API connector.
    
    Handles:
    - Sending text, media, and template messages
    - Parsing incoming webhooks
    - Message status updates
    """
    
    def __init__(self, connection: 'IntegrationConnection', channel: 'SocialChannel'):
        super().__init__(connection, channel)
        self.phone_number_id = channel.external_id
        self.waba_id = channel.whatsapp_business_account_id
    
    @property
    def provider_name(self) -> str:
        return 'whatsapp'
    
    @property
    def messages_endpoint(self) -> str:
        return f'{self.GRAPH_API_BASE}/{self.phone_number_id}/messages'
    
    def send_text(self, recipient: str, text: str, **kwargs) -> MessageResult:
        """
        Send a text message via WhatsApp.
        
        Args:
            recipient: Phone number in international format (e.g., +27821234567)
            text: Message text
            preview_url: Enable URL preview (default: True)
        """
        # Clean phone number
        recipient = self._clean_phone(recipient)
        
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': recipient,
            'type': 'text',
            'text': {
                'preview_url': kwargs.get('preview_url', True),
                'body': text
            }
        }
        
        try:
            response = self._make_request('POST', self.messages_endpoint, json=payload)
            data = response.json()
            
            if response.status_code == 200 and 'messages' in data:
                message_id = data['messages'][0]['id']
                result = MessageResult.success_result(
                    external_id=message_id,
                    status=MessageStatus.SENT,
                    metadata={'wamid': message_id}
                )
            else:
                error = data.get('error', {})
                result = MessageResult.failure_result(
                    error_code=str(error.get('code', 'UNKNOWN')),
                    error_message=error.get('message', 'Unknown error'),
                    metadata=data
                )
            
            self._log_send(recipient, 'text', result)
            return result
            
        except RateLimitError:
            raise
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def send_media(self, recipient: str, media_type: str, media_url: str,
                   caption: str = None, filename: str = None, **kwargs) -> MessageResult:
        """
        Send a media message (image, video, audio, document).
        
        Args:
            recipient: Phone number
            media_type: image, video, audio, document, sticker
            media_url: Public URL to the media file
            caption: Caption for image/video
            filename: Filename for documents
        """
        recipient = self._clean_phone(recipient)
        
        media_object = {'link': media_url}
        
        if media_type in ('image', 'video') and caption:
            media_object['caption'] = caption
        
        if media_type == 'document' and filename:
            media_object['filename'] = filename
        
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': recipient,
            'type': media_type,
            media_type: media_object
        }
        
        try:
            response = self._make_request('POST', self.messages_endpoint, json=payload)
            data = response.json()
            
            if response.status_code == 200 and 'messages' in data:
                message_id = data['messages'][0]['id']
                result = MessageResult.success_result(
                    external_id=message_id,
                    status=MessageStatus.SENT
                )
            else:
                error = data.get('error', {})
                result = MessageResult.failure_result(
                    error_code=str(error.get('code', 'UNKNOWN')),
                    error_message=error.get('message', 'Unknown error')
                )
            
            self._log_send(recipient, media_type, result)
            return result
            
        except Exception as e:
            logger.error(f"WhatsApp media send error: {e}")
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def send_template(self, recipient: str, template_name: str,
                      template_vars: Dict = None, language: str = 'en',
                      header_params: List = None, button_params: List = None,
                      **kwargs) -> MessageResult:
        """
        Send a WhatsApp template message.
        
        Required for initiating conversations outside 24-hour window.
        
        Args:
            recipient: Phone number
            template_name: Approved template name
            template_vars: Dict of template variables {1: 'value1', 2: 'value2'}
            language: Template language code
            header_params: Header component parameters
            button_params: Button component parameters
        """
        recipient = self._clean_phone(recipient)
        
        components = []
        
        # Header parameters
        if header_params:
            components.append({
                'type': 'header',
                'parameters': header_params
            })
        
        # Body parameters
        if template_vars:
            body_params = [
                {'type': 'text', 'text': str(v)}
                for k, v in sorted(template_vars.items())
            ]
            components.append({
                'type': 'body',
                'parameters': body_params
            })
        
        # Button parameters
        if button_params:
            for i, param in enumerate(button_params):
                components.append({
                    'type': 'button',
                    'sub_type': param.get('sub_type', 'quick_reply'),
                    'index': str(i),
                    'parameters': param.get('parameters', [])
                })
        
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': recipient,
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': language},
                'components': components
            }
        }
        
        try:
            response = self._make_request('POST', self.messages_endpoint, json=payload)
            data = response.json()
            
            if response.status_code == 200 and 'messages' in data:
                message_id = data['messages'][0]['id']
                result = MessageResult.success_result(
                    external_id=message_id,
                    status=MessageStatus.SENT,
                    metadata={'template': template_name}
                )
            else:
                error = data.get('error', {})
                result = MessageResult.failure_result(
                    error_code=str(error.get('code', 'UNKNOWN')),
                    error_message=error.get('message', 'Unknown error')
                )
            
            self._log_send(recipient, f'template:{template_name}', result)
            return result
            
        except Exception as e:
            logger.error(f"WhatsApp template send error: {e}")
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def send_interactive(self, recipient: str, interactive_type: str,
                         body: str, buttons: List = None, sections: List = None,
                         header: str = None, footer: str = None, **kwargs) -> MessageResult:
        """
        Send an interactive message (buttons or list).
        
        Args:
            recipient: Phone number
            interactive_type: 'button' or 'list'
            body: Message body text
            buttons: List of button objects (for button type)
            sections: List of section objects (for list type)
            header: Optional header text
            footer: Optional footer text
        """
        recipient = self._clean_phone(recipient)
        
        interactive = {
            'type': interactive_type,
            'body': {'text': body}
        }
        
        if header:
            interactive['header'] = {'type': 'text', 'text': header}
        
        if footer:
            interactive['footer'] = {'text': footer}
        
        if interactive_type == 'button' and buttons:
            interactive['action'] = {
                'buttons': [
                    {
                        'type': 'reply',
                        'reply': {'id': btn['id'], 'title': btn['title']}
                    }
                    for btn in buttons[:3]  # Max 3 buttons
                ]
            }
        elif interactive_type == 'list' and sections:
            interactive['action'] = {
                'button': kwargs.get('button_text', 'Options'),
                'sections': sections
            }
        
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': recipient,
            'type': 'interactive',
            'interactive': interactive
        }
        
        try:
            response = self._make_request('POST', self.messages_endpoint, json=payload)
            data = response.json()
            
            if response.status_code == 200 and 'messages' in data:
                message_id = data['messages'][0]['id']
                return MessageResult.success_result(external_id=message_id, status=MessageStatus.SENT)
            else:
                error = data.get('error', {})
                return MessageResult.failure_result(
                    error_code=str(error.get('code', 'UNKNOWN')),
                    error_message=error.get('message', 'Unknown error')
                )
                
        except Exception as e:
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        payload = {
            'messaging_product': 'whatsapp',
            'status': 'read',
            'message_id': message_id
        }
        
        try:
            response = self._make_request('POST', self.messages_endpoint, json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to mark message as read: {e}")
            return False
    
    def parse_webhook(self, payload: Dict) -> List[InboundMessage]:
        """
        Parse WhatsApp webhook payload.
        
        WhatsApp webhook structure:
        {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "WABA_ID",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "...", "display_phone_number": "..."},
                        "contacts": [{"profile": {"name": "..."}, "wa_id": "..."}],
                        "messages": [{...}],
                        "statuses": [{...}]  # For delivery receipts
                    },
                    "field": "messages"
                }]
            }]
        }
        """
        messages = []
        
        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                
                # Get contact info
                contacts = {
                    c['wa_id']: c.get('profile', {}).get('name', '')
                    for c in value.get('contacts', [])
                }
                
                # Parse messages
                for msg in value.get('messages', []):
                    sender_id = msg.get('from')
                    sender_name = contacts.get(sender_id, '')
                    
                    message = self._parse_message(msg, sender_id, sender_name)
                    if message:
                        messages.append(message)
        
        return messages
    
    def _parse_message(self, msg: Dict, sender_id: str, sender_name: str) -> Optional[InboundMessage]:
        """Parse a single WhatsApp message."""
        msg_type = msg.get('type', 'text')
        msg_id = msg.get('id')
        timestamp = timezone.datetime.fromtimestamp(
            int(msg.get('timestamp', 0)),
            tz=timezone.utc
        )
        
        content = {}
        text = None
        media_url = None
        media_mime_type = None
        media_filename = None
        
        if msg_type == 'text':
            text = msg.get('text', {}).get('body', '')
            content = {'text': text}
            
        elif msg_type in ('image', 'video', 'audio', 'document', 'sticker'):
            media_data = msg.get(msg_type, {})
            content = media_data
            text = media_data.get('caption', '')
            media_url = media_data.get('id')  # Media ID, needs to be downloaded
            media_mime_type = media_data.get('mime_type')
            media_filename = media_data.get('filename')
            
        elif msg_type == 'location':
            loc = msg.get('location', {})
            content = loc
            text = f"📍 Location: {loc.get('name', '')} ({loc.get('latitude')}, {loc.get('longitude')})"
            
        elif msg_type == 'contacts':
            contacts = msg.get('contacts', [])
            content = {'contacts': contacts}
            text = f"📇 Shared {len(contacts)} contact(s)"
            
        elif msg_type == 'interactive':
            interactive = msg.get('interactive', {})
            interactive_type = interactive.get('type')
            
            if interactive_type == 'button_reply':
                reply = interactive.get('button_reply', {})
                text = reply.get('title', '')
                content = {'button_id': reply.get('id'), 'button_title': text}
            elif interactive_type == 'list_reply':
                reply = interactive.get('list_reply', {})
                text = reply.get('title', '')
                content = {'list_id': reply.get('id'), 'list_title': text}
                
        elif msg_type == 'reaction':
            reaction = msg.get('reaction', {})
            content = reaction
            text = f"Reacted with {reaction.get('emoji', '')}"
            
        else:
            content = msg
            text = f"[{msg_type} message]"
        
        return InboundMessage(
            external_id=msg_id,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_phone=f"+{sender_id}",
            message_type=msg_type,
            content=content,
            text=text,
            timestamp=timestamp,
            metadata={'context': msg.get('context', {})},
            media_url=media_url,
            media_mime_type=media_mime_type,
            media_filename=media_filename,
            in_reply_to=msg.get('context', {}).get('id')
        )
    
    def _clean_phone(self, phone: str) -> str:
        """Clean phone number to digits only."""
        return ''.join(c for c in phone if c.isdigit())
    
    def get_media_url(self, media_id: str) -> Optional[str]:
        """Get temporary download URL for media."""
        try:
            response = self._make_request('GET', f'{self.GRAPH_API_BASE}/{media_id}')
            if response.status_code == 200:
                return response.json().get('url')
            return None
        except Exception as e:
            logger.error(f"Failed to get media URL: {e}")
            return None


class FacebookConnector(MetaConnector):
    """
    Facebook Messenger connector.
    
    Uses Meta Graph API to send messages via Facebook Pages.
    """
    
    def __init__(self, connection: 'IntegrationConnection', channel: 'SocialChannel'):
        super().__init__(connection, channel)
        self.page_id = channel.external_id
    
    @property
    def provider_name(self) -> str:
        return 'facebook'
    
    @property
    def messages_endpoint(self) -> str:
        return f'{self.GRAPH_API_BASE}/{self.page_id}/messages'
    
    def send_text(self, recipient: str, text: str, **kwargs) -> MessageResult:
        """
        Send a text message via Facebook Messenger.
        
        Args:
            recipient: Facebook PSID (Page-Scoped User ID)
            text: Message text
        """
        payload = {
            'recipient': {'id': recipient},
            'message': {'text': text},
            'messaging_type': kwargs.get('messaging_type', 'RESPONSE')
        }
        
        # Add message tag for messages outside 24-hour window
        if 'tag' in kwargs:
            payload['tag'] = kwargs['tag']
        
        try:
            response = self._make_request('POST', self.messages_endpoint, json=payload)
            data = response.json()
            
            if 'message_id' in data:
                return MessageResult.success_result(
                    external_id=data['message_id'],
                    status=MessageStatus.SENT
                )
            else:
                error = data.get('error', {})
                return MessageResult.failure_result(
                    error_code=str(error.get('code', 'UNKNOWN')),
                    error_message=error.get('message', 'Unknown error')
                )
                
        except Exception as e:
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def send_media(self, recipient: str, media_type: str, media_url: str,
                   caption: str = None, **kwargs) -> MessageResult:
        """Send a media message via Facebook Messenger."""
        
        attachment_type = {
            'image': 'image',
            'video': 'video',
            'audio': 'audio',
            'document': 'file'
        }.get(media_type, 'file')
        
        payload = {
            'recipient': {'id': recipient},
            'message': {
                'attachment': {
                    'type': attachment_type,
                    'payload': {'url': media_url, 'is_reusable': True}
                }
            },
            'messaging_type': 'RESPONSE'
        }
        
        try:
            response = self._make_request('POST', self.messages_endpoint, json=payload)
            data = response.json()
            
            if 'message_id' in data:
                return MessageResult.success_result(
                    external_id=data['message_id'],
                    status=MessageStatus.SENT
                )
            else:
                error = data.get('error', {})
                return MessageResult.failure_result(
                    error_code=str(error.get('code', 'UNKNOWN')),
                    error_message=error.get('message', 'Unknown error')
                )
                
        except Exception as e:
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def parse_webhook(self, payload: Dict) -> List[InboundMessage]:
        """Parse Facebook Messenger webhook payload."""
        messages = []
        
        for entry in payload.get('entry', []):
            for messaging in entry.get('messaging', []):
                sender_id = messaging.get('sender', {}).get('id')
                
                if 'message' in messaging:
                    msg = messaging['message']
                    
                    # Determine message type
                    if 'attachments' in msg:
                        for attachment in msg['attachments']:
                            att_type = attachment.get('type', 'file')
                            message = InboundMessage(
                                external_id=msg.get('mid'),
                                sender_id=sender_id,
                                sender_name=None,  # Need to fetch separately
                                sender_phone=None,
                                message_type=att_type,
                                content=attachment.get('payload', {}),
                                text=msg.get('text', ''),
                                timestamp=timezone.datetime.fromtimestamp(
                                    messaging.get('timestamp', 0) / 1000,
                                    tz=timezone.utc
                                ),
                                metadata={},
                                media_url=attachment.get('payload', {}).get('url')
                            )
                            messages.append(message)
                    else:
                        message = InboundMessage(
                            external_id=msg.get('mid'),
                            sender_id=sender_id,
                            sender_name=None,
                            sender_phone=None,
                            message_type='text',
                            content={'text': msg.get('text', '')},
                            text=msg.get('text', ''),
                            timestamp=timezone.datetime.fromtimestamp(
                                messaging.get('timestamp', 0) / 1000,
                                tz=timezone.utc
                            ),
                            metadata={'quick_reply': msg.get('quick_reply')}
                        )
                        messages.append(message)
        
        return messages


class InstagramConnector(MetaConnector):
    """
    Instagram Direct Messages connector.
    
    Uses Meta Graph API for Instagram Business accounts.
    """
    
    def __init__(self, connection: 'IntegrationConnection', channel: 'SocialChannel'):
        super().__init__(connection, channel)
        self.ig_user_id = channel.external_id
    
    @property
    def provider_name(self) -> str:
        return 'instagram'
    
    @property
    def messages_endpoint(self) -> str:
        return f'{self.GRAPH_API_BASE}/{self.ig_user_id}/messages'
    
    def send_text(self, recipient: str, text: str, **kwargs) -> MessageResult:
        """
        Send a text message via Instagram DM.
        
        Args:
            recipient: Instagram-scoped user ID (IGSID)
            text: Message text
        """
        payload = {
            'recipient': {'id': recipient},
            'message': {'text': text}
        }
        
        try:
            response = self._make_request('POST', self.messages_endpoint, json=payload)
            data = response.json()
            
            if 'message_id' in data:
                return MessageResult.success_result(
                    external_id=data['message_id'],
                    status=MessageStatus.SENT
                )
            else:
                error = data.get('error', {})
                return MessageResult.failure_result(
                    error_code=str(error.get('code', 'UNKNOWN')),
                    error_message=error.get('message', 'Unknown error')
                )
                
        except Exception as e:
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def send_media(self, recipient: str, media_type: str, media_url: str,
                   caption: str = None, **kwargs) -> MessageResult:
        """Send a media message via Instagram DM."""
        
        # Instagram DM only supports images
        if media_type != 'image':
            return MessageResult.failure_result(
                'UNSUPPORTED_MEDIA',
                f'Instagram DM only supports images, not {media_type}'
            )
        
        payload = {
            'recipient': {'id': recipient},
            'message': {
                'attachment': {
                    'type': 'image',
                    'payload': {'url': media_url}
                }
            }
        }
        
        try:
            response = self._make_request('POST', self.messages_endpoint, json=payload)
            data = response.json()
            
            if 'message_id' in data:
                return MessageResult.success_result(
                    external_id=data['message_id'],
                    status=MessageStatus.SENT
                )
            else:
                error = data.get('error', {})
                return MessageResult.failure_result(
                    error_code=str(error.get('code', 'UNKNOWN')),
                    error_message=error.get('message', 'Unknown error')
                )
                
        except Exception as e:
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def parse_webhook(self, payload: Dict) -> List[InboundMessage]:
        """Parse Instagram DM webhook payload."""
        messages = []
        
        for entry in payload.get('entry', []):
            for messaging in entry.get('messaging', []):
                sender_id = messaging.get('sender', {}).get('id')
                
                if 'message' in messaging:
                    msg = messaging['message']
                    
                    message = InboundMessage(
                        external_id=msg.get('mid'),
                        sender_id=sender_id,
                        sender_name=None,
                        sender_phone=None,
                        message_type='text' if 'text' in msg else 'media',
                        content=msg,
                        text=msg.get('text', ''),
                        timestamp=timezone.datetime.fromtimestamp(
                            messaging.get('timestamp', 0) / 1000,
                            tz=timezone.utc
                        ),
                        metadata={}
                    )
                    messages.append(message)
        
        return messages


class MetaAnalyticsConnector(MetaConnector):
    """
    Meta Analytics Connector for Facebook and Instagram Insights.
    
    Fetches page/account insights, post metrics, and audience data
    for marketing analytics dashboard.
    
    Required Permissions:
    - pages_read_engagement
    - pages_read_user_content
    - instagram_basic
    - instagram_manage_insights
    """
    
    def __init__(self, connection: 'IntegrationConnection', brand_account: 'BrandSocialAccount' = None):
        super().__init__(connection)
        self.brand_account = brand_account
        self.page_id = brand_account.facebook_page_id if brand_account else None
        self.ig_user_id = brand_account.instagram_business_id if brand_account else None
    
    @property
    def provider_name(self) -> str:
        return 'meta_analytics'
    
    # ========================================================================
    # FACEBOOK PAGE INSIGHTS
    # ========================================================================
    
    def get_page_insights(self, date_from: str, date_to: str) -> Dict[str, Any]:
        """
        Get Facebook Page insights for a date range.
        
        Args:
            date_from: Start date in YYYY-MM-DD format
            date_to: End date in YYYY-MM-DD format
            
        Returns:
            Dict with aggregated page metrics
        """
        if not self.page_id:
            return {'error': 'No Facebook Page ID configured'}
        
        # Page-level metrics
        metrics = [
            'page_impressions',
            'page_impressions_unique',  # reach
            'page_engaged_users',
            'page_post_engagements',
            'page_fan_adds',
            'page_fan_removes',
            'page_fans',  # total followers
            'page_views_total',
            'page_actions_post_reactions_total',
            'page_consumptions_unique',
            'page_negative_feedback_unique',
            'page_website_clicks_logged_in_unique',
        ]
        
        try:
            response = self._make_request(
                'GET',
                f'{self.GRAPH_API_BASE}/{self.page_id}/insights',
                params={
                    'metric': ','.join(metrics),
                    'period': 'day',
                    'since': date_from,
                    'until': date_to,
                }
            )
            
            if response.status_code == 200:
                return self._parse_insights_response(response.json())
            else:
                logger.error(f"Failed to get page insights: {response.text}")
                return {'error': response.json()}
                
        except Exception as e:
            logger.error(f"Error fetching page insights: {e}")
            return {'error': str(e)}
    
    def get_page_daily_metrics(self, date: str) -> Dict[str, Any]:
        """Get single day metrics for a Facebook Page."""
        from datetime import datetime, timedelta
        
        dt = datetime.strptime(date, '%Y-%m-%d')
        next_day = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
        
        insights = self.get_page_insights(date, next_day)
        
        # Get page fan count (total followers)
        try:
            response = self._make_request(
                'GET',
                f'{self.GRAPH_API_BASE}/{self.page_id}',
                params={'fields': 'fan_count,followers_count'}
            )
            if response.status_code == 200:
                data = response.json()
                insights['followers'] = data.get('followers_count', data.get('fan_count', 0))
        except Exception:
            pass
        
        return insights
    
    def get_page_posts(self, since: str = None, limit: int = 100) -> List[Dict]:
        """
        Get published posts from a Facebook Page.
        
        Args:
            since: Unix timestamp or YYYY-MM-DD date to fetch posts from
            limit: Maximum number of posts to return
        """
        if not self.page_id:
            return []
        
        fields = [
            'id', 'message', 'created_time', 'permalink_url',
            'full_picture', 'type', 'status_type', 'shares',
            'insights.metric(post_impressions,post_impressions_unique,post_engaged_users,'
            'post_clicks,post_reactions_by_type_total)'
        ]
        
        try:
            response = self._make_request(
                'GET',
                f'{self.GRAPH_API_BASE}/{self.page_id}/posts',
                params={
                    'fields': ','.join(fields),
                    'limit': limit,
                    'since': since,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_posts(data.get('data', []), platform='FACEBOOK')
            else:
                logger.error(f"Failed to get page posts: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching page posts: {e}")
            return []
    
    # ========================================================================
    # INSTAGRAM INSIGHTS
    # ========================================================================
    
    def get_instagram_insights(self, date_from: str, date_to: str) -> Dict[str, Any]:
        """
        Get Instagram account insights for a date range.
        
        Args:
            date_from: Start date in YYYY-MM-DD format
            date_to: End date in YYYY-MM-DD format
        """
        if not self.ig_user_id:
            return {'error': 'No Instagram Business ID configured'}
        
        # IG account metrics (limited compared to FB)
        metrics = [
            'impressions',
            'reach',
            'profile_views',
            'website_clicks',
            'email_contacts',
            'get_directions_clicks',
            'phone_call_clicks',
            'text_message_clicks',
            'follower_count',
        ]
        
        try:
            response = self._make_request(
                'GET',
                f'{self.GRAPH_API_BASE}/{self.ig_user_id}/insights',
                params={
                    'metric': ','.join(metrics),
                    'period': 'day',
                    'since': date_from,
                    'until': date_to,
                }
            )
            
            if response.status_code == 200:
                return self._parse_insights_response(response.json())
            else:
                logger.error(f"Failed to get IG insights: {response.text}")
                return {'error': response.json()}
                
        except Exception as e:
            logger.error(f"Error fetching IG insights: {e}")
            return {'error': str(e)}
    
    def get_instagram_daily_metrics(self, date: str) -> Dict[str, Any]:
        """Get single day metrics for Instagram account."""
        from datetime import datetime, timedelta
        
        dt = datetime.strptime(date, '%Y-%m-%d')
        next_day = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
        
        insights = self.get_instagram_insights(date, next_day)
        
        # Get followers count
        try:
            response = self._make_request(
                'GET',
                f'{self.GRAPH_API_BASE}/{self.ig_user_id}',
                params={'fields': 'followers_count,media_count'}
            )
            if response.status_code == 200:
                data = response.json()
                insights['followers'] = data.get('followers_count', 0)
                insights['media_count'] = data.get('media_count', 0)
        except Exception:
            pass
        
        return insights
    
    def get_instagram_media(self, since: str = None, limit: int = 100) -> List[Dict]:
        """
        Get published media from Instagram account.
        
        Args:
            since: Unix timestamp to fetch media from
            limit: Maximum number of media items to return
        """
        if not self.ig_user_id:
            return []
        
        fields = [
            'id', 'caption', 'media_type', 'media_url', 'thumbnail_url',
            'permalink', 'timestamp', 'like_count', 'comments_count',
            'insights.metric(impressions,reach,engagement,saved,video_views)'
        ]
        
        try:
            response = self._make_request(
                'GET',
                f'{self.GRAPH_API_BASE}/{self.ig_user_id}/media',
                params={
                    'fields': ','.join(fields),
                    'limit': limit,
                    'since': since,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_ig_media(data.get('data', []))
            else:
                logger.error(f"Failed to get IG media: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching IG media: {e}")
            return []
    
    def get_instagram_stories(self) -> List[Dict]:
        """Get active Instagram stories (last 24 hours)."""
        if not self.ig_user_id:
            return []
        
        fields = [
            'id', 'media_type', 'media_url', 'timestamp',
            'insights.metric(impressions,reach,replies,exits)'
        ]
        
        try:
            response = self._make_request(
                'GET',
                f'{self.GRAPH_API_BASE}/{self.ig_user_id}/stories',
                params={'fields': ','.join(fields)}
            )
            
            if response.status_code == 200:
                return response.json().get('data', [])
            return []
            
        except Exception as e:
            logger.error(f"Error fetching IG stories: {e}")
            return []
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _parse_insights_response(self, data: Dict) -> Dict[str, Any]:
        """Parse Meta insights API response into flattened dict."""
        result = {}
        
        for item in data.get('data', []):
            name = item.get('name')
            values = item.get('values', [])
            
            if values:
                # For daily data, aggregate
                if len(values) == 1:
                    result[name] = values[0].get('value', 0)
                else:
                    # Multiple days - return as list or sum
                    result[name] = sum(v.get('value', 0) for v in values if isinstance(v.get('value'), (int, float)))
        
        return result
    
    def _parse_posts(self, posts: List[Dict], platform: str) -> List[Dict]:
        """Parse Facebook posts into standardized format."""
        parsed = []
        
        for post in posts:
            insights = {}
            if 'insights' in post:
                for item in post['insights'].get('data', []):
                    insights[item['name']] = item['values'][0]['value'] if item.get('values') else 0
            
            reactions = insights.get('post_reactions_by_type_total', {})
            
            parsed.append({
                'platform': platform,
                'platform_post_id': post.get('id'),
                'post_type': self._map_fb_post_type(post.get('type', 'status')),
                'caption': post.get('message', ''),
                'media_url': post.get('full_picture', ''),
                'permalink': post.get('permalink_url', ''),
                'published_at': post.get('created_time'),
                'impressions': insights.get('post_impressions', 0),
                'reach': insights.get('post_impressions_unique', 0),
                'likes': sum(reactions.values()) if isinstance(reactions, dict) else 0,
                'comments': 0,  # Need separate API call
                'shares': post.get('shares', {}).get('count', 0),
                'link_clicks': insights.get('post_clicks', 0),
                'engagement_total': insights.get('post_engaged_users', 0),
                'raw_data': post,
            })
        
        return parsed
    
    def _parse_ig_media(self, media_items: List[Dict]) -> List[Dict]:
        """Parse Instagram media into standardized format."""
        parsed = []
        
        for media in media_items:
            insights = {}
            if 'insights' in media:
                for item in media['insights'].get('data', []):
                    insights[item['name']] = item['values'][0]['value'] if item.get('values') else 0
            
            parsed.append({
                'platform': 'INSTAGRAM',
                'platform_post_id': media.get('id'),
                'post_type': self._map_ig_media_type(media.get('media_type', 'IMAGE')),
                'caption': media.get('caption', ''),
                'media_url': media.get('media_url', ''),
                'thumbnail_url': media.get('thumbnail_url', ''),
                'permalink': media.get('permalink', ''),
                'published_at': media.get('timestamp'),
                'impressions': insights.get('impressions', 0),
                'reach': insights.get('reach', 0),
                'likes': media.get('like_count', 0),
                'comments': media.get('comments_count', 0),
                'saves': insights.get('saved', 0),
                'video_views': insights.get('video_views', 0),
                'engagement_total': insights.get('engagement', 0),
                'raw_data': media,
            })
        
        return parsed
    
    def _map_fb_post_type(self, fb_type: str) -> str:
        """Map Facebook post type to standard type."""
        mapping = {
            'link': 'POST',
            'status': 'POST',
            'photo': 'POST',
            'video': 'VIDEO',
            'added_video': 'VIDEO',
            'album': 'CAROUSEL',
            'live': 'LIVE',
        }
        return mapping.get(fb_type.lower(), 'POST')
    
    def _map_ig_media_type(self, ig_type: str) -> str:
        """Map Instagram media type to standard type."""
        mapping = {
            'IMAGE': 'POST',
            'VIDEO': 'REEL',
            'CAROUSEL_ALBUM': 'CAROUSEL',
            'STORY': 'STORY',
        }
        return mapping.get(ig_type.upper(), 'POST')
