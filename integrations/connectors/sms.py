"""
SMS Gateway Connectors

Support for multiple SMS providers:
- BulkSMS (South African provider)
- Clickatell (Global provider)
"""
import logging
import base64
from typing import Any, Dict, List, Optional
from django.utils import timezone

from .base import (
    BaseConnector,
    ConnectorError,
    RateLimitError,
    MessageResult,
    MessageStatus,
    InboundMessage,
)


logger = logging.getLogger(__name__)


class BulkSMSConnector(BaseConnector):
    """
    BulkSMS connector for South African SMS delivery.
    
    API Documentation: https://www.bulksms.com/developer/
    """
    
    API_BASE = 'https://api.bulksms.com/v1'
    
    def __init__(self, connection: 'IntegrationConnection', sms_config: 'SMSConfig' = None):
        self.sms_config = sms_config
        super().__init__(connection)
    
    def _setup_session(self):
        """Set up session with Basic Auth."""
        username = self.connection.api_key
        password = self.connection.api_secret
        
        if username and password:
            credentials = base64.b64encode(f'{username}:{password}'.encode()).decode()
            self.session.headers.update({
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json',
            })
    
    @property
    def provider_name(self) -> str:
        return 'bulksms'
    
    def send_text(self, recipient: str, text: str, **kwargs) -> MessageResult:
        """
        Send an SMS message.
        
        Args:
            recipient: Phone number in international format
            text: Message text (max 160 chars for standard, 459 for long)
            sender_id: Optional sender ID override
        """
        recipient = self._clean_phone(recipient)
        
        payload = {
            'to': recipient,
            'body': text,
        }
        
        # Add sender ID if configured
        sender_id = kwargs.get('sender_id') or (self.sms_config.sender_id if self.sms_config else None)
        if sender_id:
            payload['from'] = sender_id
        
        # Routing group for optimal delivery
        if kwargs.get('routing_group'):
            payload['routingGroup'] = kwargs['routing_group']
        
        try:
            response = self._make_request(
                'POST',
                f'{self.API_BASE}/messages',
                json=payload
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                
                # BulkSMS returns a list of message results
                if isinstance(data, list) and data:
                    msg = data[0]
                    return MessageResult.success_result(
                        external_id=msg.get('id'),
                        status=MessageStatus.SENT,
                        metadata={
                            'credits_used': msg.get('creditCost'),
                            'status_code': msg.get('status', {}).get('id')
                        }
                    )
                elif isinstance(data, dict):
                    return MessageResult.success_result(
                        external_id=data.get('id'),
                        status=MessageStatus.SENT,
                        metadata=data
                    )
            
            # Handle errors
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    return MessageResult.failure_result(
                        error_code=str(error_data.get('type', 'UNKNOWN')),
                        error_message=error_data.get('detail', 'Unknown error')
                    )
            except:
                pass
            
            return MessageResult.failure_result(
                'HTTP_ERROR',
                f'HTTP {response.status_code}'
            )
            
        except RateLimitError:
            raise
        except Exception as e:
            logger.error(f"BulkSMS send error: {e}")
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def send_bulk(self, recipients: List[str], text: str, **kwargs) -> List[MessageResult]:
        """
        Send SMS to multiple recipients efficiently.
        
        Args:
            recipients: List of phone numbers
            text: Message text
        """
        cleaned = [self._clean_phone(r) for r in recipients]
        
        payload = {
            'to': cleaned,
            'body': text,
        }
        
        sender_id = kwargs.get('sender_id') or (self.sms_config.sender_id if self.sms_config else None)
        if sender_id:
            payload['from'] = sender_id
        
        try:
            response = self._make_request(
                'POST',
                f'{self.API_BASE}/messages',
                json=payload
            )
            
            results = []
            if response.status_code in (200, 201):
                data = response.json()
                if isinstance(data, list):
                    for msg in data:
                        if msg.get('status', {}).get('type') == 'ACCEPTED':
                            results.append(MessageResult.success_result(
                                external_id=msg.get('id'),
                                status=MessageStatus.SENT
                            ))
                        else:
                            status = msg.get('status', {})
                            results.append(MessageResult.failure_result(
                                error_code=str(status.get('id', 'UNKNOWN')),
                                error_message=status.get('subtype', 'Unknown error')
                            ))
            
            return results
            
        except Exception as e:
            logger.error(f"BulkSMS bulk send error: {e}")
            return [MessageResult.failure_result('SEND_ERROR', str(e))] * len(recipients)
    
    def send_media(self, recipient: str, media_type: str, media_url: str,
                   caption: str = None, **kwargs) -> MessageResult:
        """SMS doesn't support media. Send caption as text instead."""
        if caption:
            return self.send_text(recipient, f"{caption}\n{media_url}", **kwargs)
        return MessageResult.failure_result('UNSUPPORTED', 'SMS does not support media')
    
    def verify_webhook(self, request_body: bytes, signature: str) -> bool:
        """BulkSMS webhooks use basic URL token verification."""
        # BulkSMS uses a verification token in URL params
        return True  # Verification happens at URL level
    
    def parse_webhook(self, payload: Dict) -> List[InboundMessage]:
        """
        Parse BulkSMS delivery report webhook.
        
        BulkSMS sends delivery reports as:
        {
            "type": "delivery_report.status_update",
            "messageId": "...",
            "status": {...},
            "relatedSentMessageId": "..."
        }
        """
        messages = []
        
        event_type = payload.get('type', '')
        
        if event_type == 'delivery_report.status_update':
            # This is a status update, not an inbound message
            # We'll handle it separately in the service layer
            pass
        
        # BulkSMS inbound messages (if configured)
        if 'from' in payload and 'body' in payload:
            message = InboundMessage(
                external_id=payload.get('id'),
                sender_id=payload.get('from'),
                sender_name=None,
                sender_phone=payload.get('from'),
                message_type='text',
                content={'text': payload.get('body', '')},
                text=payload.get('body', ''),
                timestamp=timezone.now(),
                metadata=payload
            )
            messages.append(message)
        
        return messages
    
    def check_health(self) -> Dict[str, Any]:
        """Check BulkSMS API connectivity and credits."""
        try:
            response = self._make_request('GET', f'{self.API_BASE}/profile')
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'healthy': True,
                    'message': 'Connected to BulkSMS',
                    'details': {
                        'credits': data.get('credits', {}).get('balance'),
                        'username': data.get('username')
                    }
                }
            else:
                return {
                    'healthy': False,
                    'message': f'API returned {response.status_code}',
                    'details': {}
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'message': str(e),
                'details': {}
            }
    
    def get_credits(self) -> Optional[float]:
        """Get remaining SMS credits."""
        try:
            response = self._make_request('GET', f'{self.API_BASE}/profile')
            if response.status_code == 200:
                return response.json().get('credits', {}).get('balance')
            return None
        except Exception:
            return None
    
    def _clean_phone(self, phone: str) -> str:
        """Clean and format phone number for BulkSMS."""
        # Remove all non-digits except leading +
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        # Ensure international format
        if not cleaned.startswith('+'):
            # Assume South African number if no country code
            if cleaned.startswith('0'):
                cleaned = '+27' + cleaned[1:]
            else:
                cleaned = '+' + cleaned
        
        return cleaned


class ClickatellConnector(BaseConnector):
    """
    Clickatell connector for global SMS delivery.
    
    API Documentation: https://www.clickatell.com/developers/api-documentation/
    """
    
    API_BASE = 'https://platform.clickatell.com'
    
    def __init__(self, connection: 'IntegrationConnection', sms_config: 'SMSConfig' = None):
        self.sms_config = sms_config
        super().__init__(connection)
    
    def _setup_session(self):
        """Set up session with API key."""
        api_key = self.connection.api_key
        
        self.session.headers.update({
            'Authorization': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
    
    @property
    def provider_name(self) -> str:
        return 'clickatell'
    
    def send_text(self, recipient: str, text: str, **kwargs) -> MessageResult:
        """
        Send an SMS message.
        
        Args:
            recipient: Phone number in international format
            text: Message text
            from_: Optional sender ID
        """
        recipient = self._clean_phone(recipient)
        
        payload = {
            'content': text,
            'to': [recipient],
        }
        
        # Add sender ID if configured
        sender_id = kwargs.get('sender_id') or (self.sms_config.sender_id if self.sms_config else None)
        if sender_id:
            payload['from'] = sender_id
        
        try:
            response = self._make_request(
                'POST',
                f'{self.API_BASE}/v1/message',
                json=payload
            )
            
            if response.status_code == 202:
                data = response.json()
                messages = data.get('messages', [])
                
                if messages:
                    msg = messages[0]
                    if msg.get('accepted'):
                        return MessageResult.success_result(
                            external_id=msg.get('apiMessageId'),
                            status=MessageStatus.SENT,
                            metadata={'to': msg.get('to')}
                        )
                    else:
                        return MessageResult.failure_result(
                            error_code=str(msg.get('errorCode', 'UNKNOWN')),
                            error_message=msg.get('error', 'Unknown error')
                        )
            
            # Handle error response
            try:
                error_data = response.json()
                return MessageResult.failure_result(
                    error_code=str(error_data.get('errorCode', 'UNKNOWN')),
                    error_message=error_data.get('error', 'Unknown error')
                )
            except:
                return MessageResult.failure_result('HTTP_ERROR', f'HTTP {response.status_code}')
                
        except RateLimitError:
            raise
        except Exception as e:
            logger.error(f"Clickatell send error: {e}")
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def send_bulk(self, recipients: List[str], text: str, **kwargs) -> List[MessageResult]:
        """
        Send SMS to multiple recipients.
        
        Clickatell supports up to 1000 recipients per request.
        """
        cleaned = [self._clean_phone(r) for r in recipients]
        
        # Split into batches of 1000
        batch_size = 1000
        all_results = []
        
        for i in range(0, len(cleaned), batch_size):
            batch = cleaned[i:i + batch_size]
            
            payload = {
                'content': text,
                'to': batch,
            }
            
            sender_id = kwargs.get('sender_id') or (self.sms_config.sender_id if self.sms_config else None)
            if sender_id:
                payload['from'] = sender_id
            
            try:
                response = self._make_request(
                    'POST',
                    f'{self.API_BASE}/v1/message',
                    json=payload
                )
                
                if response.status_code == 202:
                    data = response.json()
                    for msg in data.get('messages', []):
                        if msg.get('accepted'):
                            all_results.append(MessageResult.success_result(
                                external_id=msg.get('apiMessageId'),
                                status=MessageStatus.SENT
                            ))
                        else:
                            all_results.append(MessageResult.failure_result(
                                error_code=str(msg.get('errorCode', 'UNKNOWN')),
                                error_message=msg.get('error', 'Unknown error')
                            ))
                else:
                    # All in batch failed
                    all_results.extend([
                        MessageResult.failure_result('HTTP_ERROR', f'HTTP {response.status_code}')
                        for _ in batch
                    ])
                    
            except Exception as e:
                all_results.extend([
                    MessageResult.failure_result('SEND_ERROR', str(e))
                    for _ in batch
                ])
        
        return all_results
    
    def send_media(self, recipient: str, media_type: str, media_url: str,
                   caption: str = None, **kwargs) -> MessageResult:
        """SMS doesn't support media. Send caption as text instead."""
        if caption:
            return self.send_text(recipient, f"{caption}\n{media_url}", **kwargs)
        return MessageResult.failure_result('UNSUPPORTED', 'SMS does not support media')
    
    def verify_webhook(self, request_body: bytes, signature: str) -> bool:
        """Clickatell webhooks are verified by IP whitelist or token."""
        return True  # Verification at URL level
    
    def parse_webhook(self, payload: Dict) -> List[InboundMessage]:
        """
        Parse Clickatell webhook payload.
        
        Clickatell can send:
        - Message status updates
        - Two-way SMS replies
        """
        messages = []
        
        # Inbound message (two-way SMS)
        if payload.get('event') == 'message':
            message = InboundMessage(
                external_id=payload.get('messageId'),
                sender_id=payload.get('fromNumber'),
                sender_name=None,
                sender_phone=payload.get('fromNumber'),
                message_type='text',
                content={'text': payload.get('content', '')},
                text=payload.get('content', ''),
                timestamp=timezone.now(),
                metadata={
                    'to_number': payload.get('toNumber'),
                    'channel': payload.get('channel')
                }
            )
            messages.append(message)
        
        return messages
    
    def check_health(self) -> Dict[str, Any]:
        """Check Clickatell API connectivity and balance."""
        try:
            response = self._make_request('GET', f'{self.API_BASE}/v1/balance')
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'healthy': True,
                    'message': 'Connected to Clickatell',
                    'details': {
                        'balance': data.get('balance')
                    }
                }
            else:
                return {
                    'healthy': False,
                    'message': f'API returned {response.status_code}',
                    'details': {}
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'message': str(e),
                'details': {}
            }
    
    def get_balance(self) -> Optional[float]:
        """Get remaining account balance."""
        try:
            response = self._make_request('GET', f'{self.API_BASE}/v1/balance')
            if response.status_code == 200:
                return response.json().get('balance')
            return None
        except Exception:
            return None
    
    def _clean_phone(self, phone: str) -> str:
        """Clean and format phone number for Clickatell."""
        # Remove all non-digits
        cleaned = ''.join(c for c in phone if c.isdigit())
        
        # Ensure international format without +
        if cleaned.startswith('0'):
            # Assume South African if starts with 0
            cleaned = '27' + cleaned[1:]
        
        return cleaned


# Factory function to get appropriate SMS connector
def get_sms_connector(sms_config: 'SMSConfig') -> BaseConnector:
    """
    Get the appropriate SMS connector based on configuration.
    
    Args:
        sms_config: SMSConfig instance with gateway provider info
        
    Returns:
        Configured SMS connector instance
    """
    from integrations.models import IntegrationConnection
    
    # Get the integration connection for this SMS config
    connection = IntegrationConnection.objects.filter(
        provider=sms_config.provider,
        brand=sms_config.brand,
        is_active=True
    ).first()
    
    if not connection:
        raise ConnectorError(f"No active connection found for {sms_config.provider}")
    
    if sms_config.provider == 'bulksms':
        return BulkSMSConnector(connection, sms_config)
    elif sms_config.provider == 'clickatell':
        return ClickatellConnector(connection, sms_config)
    else:
        raise ConnectorError(f"Unknown SMS provider: {sms_config.provider}")
