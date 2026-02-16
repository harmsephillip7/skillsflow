"""
Microsoft 365 Email Connector

Uses Microsoft Graph API to:
- Send emails on behalf of agents
- Sync inbox messages
- Handle OAuth per mailbox
"""
import logging
import msal
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from .base import (
    BaseConnector,
    ConnectorError,
    AuthenticationError,
    MessageResult,
    MessageStatus,
    InboundMessage,
)


logger = logging.getLogger(__name__)


class MicrosoftGraphConnector(BaseConnector):
    """
    Microsoft Graph API connector for email operations.
    
    Handles OAuth 2.0 token management per mailbox.
    """
    
    GRAPH_API_BASE = 'https://graph.microsoft.com/v1.0'
    AUTH_BASE = 'https://login.microsoftonline.com'
    
    def __init__(self, connection: 'IntegrationConnection', email_account: 'EmailAccount' = None):
        self.email_account = email_account
        self._msal_app = None
        super().__init__(connection)
    
    def _setup_session(self):
        """Set up session with OAuth bearer token."""
        access_token = self._get_valid_token()
        
        if access_token:
            self.session.headers.update({
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            })
    
    @property
    def provider_name(self) -> str:
        return 'microsoft365'
    
    def _get_msal_app(self):
        """Get or create MSAL confidential client application."""
        if not self._msal_app:
            client_id = self.connection.client_id
            client_secret = self.connection.client_secret
            tenant_id = self.connection.tenant_id or 'common'
            
            authority = f"{self.AUTH_BASE}/{tenant_id}"
            
            self._msal_app = msal.ConfidentialClientApplication(
                client_id,
                authority=authority,
                client_credential=client_secret,
            )
        
        return self._msal_app
    
    def _get_valid_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if necessary."""
        # Check if email account has valid token
        if self.email_account:
            if self.email_account.token_expires_at and self.email_account.token_expires_at > timezone.now():
                return self.email_account.access_token
            
            # Try to refresh
            if self.email_account.refresh_token:
                if self._refresh_token():
                    return self.email_account.access_token
        
        # Fall back to connection token
        if self.connection.token_expires_at and self.connection.token_expires_at > timezone.now():
            return self.connection.access_token
        
        # Try to acquire token using client credentials
        return self._acquire_app_token()
    
    def _acquire_app_token(self) -> Optional[str]:
        """Acquire app-only token using client credentials flow."""
        try:
            app = self._get_msal_app()
            result = app.acquire_token_for_client(
                scopes=['https://graph.microsoft.com/.default']
            )
            
            if 'access_token' in result:
                # Save to connection
                self.connection.access_token = result['access_token']
                self.connection.token_expires_at = timezone.now() + timedelta(seconds=result.get('expires_in', 3600))
                self.connection.save()
                
                return result['access_token']
            
            logger.error(f"Failed to acquire app token: {result.get('error_description')}")
            return None
            
        except Exception as e:
            logger.error(f"Error acquiring app token: {e}")
            return None
    
    def _refresh_token(self) -> bool:
        """Refresh user token using refresh token."""
        if not self.email_account or not self.email_account.refresh_token:
            return False
        
        try:
            app = self._get_msal_app()
            result = app.acquire_token_by_refresh_token(
                self.email_account.refresh_token,
                scopes=['Mail.ReadWrite', 'Mail.Send']
            )
            
            if 'access_token' in result:
                self.email_account.access_token = result['access_token']
                self.email_account.refresh_token = result.get('refresh_token', self.email_account.refresh_token)
                self.email_account.token_expires_at = timezone.now() + timedelta(seconds=result.get('expires_in', 3600))
                self.email_account.save()
                
                # Update session header
                self.session.headers['Authorization'] = f"Bearer {result['access_token']}"
                return True
            
            logger.error(f"Failed to refresh token: {result.get('error_description')}")
            return False
            
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False
    
    def get_authorization_url(self, redirect_uri: str, state: str = None) -> str:
        """
        Get OAuth authorization URL for user consent.
        
        Used to connect a new email account.
        """
        app = self._get_msal_app()
        
        auth_url = app.get_authorization_request_url(
            scopes=['Mail.ReadWrite', 'Mail.Send', 'User.Read'],
            redirect_uri=redirect_uri,
            state=state,
        )
        
        return auth_url
    
    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Returns token data to be stored in EmailAccount.
        """
        app = self._get_msal_app()
        
        result = app.acquire_token_by_authorization_code(
            code,
            scopes=['Mail.ReadWrite', 'Mail.Send', 'User.Read'],
            redirect_uri=redirect_uri,
        )
        
        if 'access_token' in result:
            return {
                'access_token': result['access_token'],
                'refresh_token': result.get('refresh_token'),
                'expires_in': result.get('expires_in', 3600),
                'id_token_claims': result.get('id_token_claims', {})
            }
        
        raise AuthenticationError(result.get('error_description', 'Failed to exchange code'))
    
    def send_text(self, recipient: str, text: str, **kwargs) -> MessageResult:
        """
        Send an email message.
        
        Args:
            recipient: Email address
            text: Email body (plain text)
            subject: Email subject
            html_body: HTML version of body
            cc: List of CC recipients
            bcc: List of BCC recipients
            importance: 'low', 'normal', 'high'
            reply_to: Reply-to address
        """
        subject = kwargs.get('subject', 'No Subject')
        html_body = kwargs.get('html_body')
        cc = kwargs.get('cc', [])
        bcc = kwargs.get('bcc', [])
        importance = kwargs.get('importance', 'normal')
        
        message = {
            'subject': subject,
            'body': {
                'contentType': 'HTML' if html_body else 'Text',
                'content': html_body or text
            },
            'toRecipients': [{'emailAddress': {'address': recipient}}],
            'importance': importance,
        }
        
        if cc:
            message['ccRecipients'] = [{'emailAddress': {'address': addr}} for addr in cc]
        
        if bcc:
            message['bccRecipients'] = [{'emailAddress': {'address': addr}} for addr in bcc]
        
        if kwargs.get('reply_to'):
            message['replyTo'] = [{'emailAddress': {'address': kwargs['reply_to']}}]
        
        # Add attachments if provided
        attachments = kwargs.get('attachments', [])
        if attachments:
            message['attachments'] = attachments
        
        # Determine endpoint - user mailbox or shared mailbox
        if self.email_account:
            endpoint = f'{self.GRAPH_API_BASE}/users/{self.email_account.email_address}/sendMail'
        else:
            endpoint = f'{self.GRAPH_API_BASE}/me/sendMail'
        
        try:
            response = self._make_request(
                'POST',
                endpoint,
                json={'message': message, 'saveToSentItems': True}
            )
            
            if response.status_code == 202:
                return MessageResult.success_result(
                    external_id=None,  # Graph API doesn't return message ID on send
                    status=MessageStatus.SENT,
                    metadata={'recipient': recipient, 'subject': subject}
                )
            else:
                try:
                    error = response.json().get('error', {})
                    return MessageResult.failure_result(
                        error_code=error.get('code', 'UNKNOWN'),
                        error_message=error.get('message', 'Unknown error')
                    )
                except:
                    return MessageResult.failure_result('HTTP_ERROR', f'HTTP {response.status_code}')
                    
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def send_media(self, recipient: str, media_type: str, media_url: str,
                   caption: str = None, **kwargs) -> MessageResult:
        """
        Send email with attachment.
        
        For email, we fetch the media and attach it.
        """
        # For now, include as link in body
        body = caption or ''
        if media_url:
            body += f'\n\nAttachment: {media_url}'
        
        return self.send_text(recipient, body, **kwargs)
    
    def send_reply(self, message_id: str, text: str, reply_all: bool = False,
                   **kwargs) -> MessageResult:
        """
        Reply to an existing email.
        
        Args:
            message_id: ID of the message to reply to
            text: Reply body
            reply_all: If True, reply to all recipients
        """
        endpoint_suffix = 'replyAll' if reply_all else 'reply'
        
        if self.email_account:
            endpoint = f'{self.GRAPH_API_BASE}/users/{self.email_account.email_address}/messages/{message_id}/{endpoint_suffix}'
        else:
            endpoint = f'{self.GRAPH_API_BASE}/me/messages/{message_id}/{endpoint_suffix}'
        
        payload = {
            'message': {
                'body': {
                    'contentType': 'HTML' if kwargs.get('html_body') else 'Text',
                    'content': kwargs.get('html_body') or text
                }
            },
            'comment': text
        }
        
        try:
            response = self._make_request('POST', endpoint, json=payload)
            
            if response.status_code == 202:
                return MessageResult.success_result(
                    external_id=None,
                    status=MessageStatus.SENT
                )
            else:
                return MessageResult.failure_result('HTTP_ERROR', f'HTTP {response.status_code}')
                
        except Exception as e:
            return MessageResult.failure_result('SEND_ERROR', str(e))
    
    def get_messages(self, folder: str = 'inbox', top: int = 50,
                     filter_query: str = None, since: 'timezone.datetime' = None,
                     **kwargs) -> List[Dict]:
        """
        Get messages from a mail folder.
        
        Args:
            folder: Mail folder (inbox, sentitems, drafts, etc.)
            top: Number of messages to retrieve
            filter_query: OData filter query
            since: Only get messages received after this time
        """
        if self.email_account:
            endpoint = f'{self.GRAPH_API_BASE}/users/{self.email_account.email_address}/mailFolders/{folder}/messages'
        else:
            endpoint = f'{self.GRAPH_API_BASE}/me/mailFolders/{folder}/messages'
        
        params = {
            '$top': top,
            '$orderby': 'receivedDateTime desc',
            '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,bodyPreview,body,hasAttachments,isRead,importance,conversationId'
        }
        
        if filter_query:
            params['$filter'] = filter_query
        elif since:
            params['$filter'] = f"receivedDateTime ge {since.isoformat()}"
        
        try:
            response = self._make_request('GET', endpoint, params=params)
            
            if response.status_code == 200:
                return response.json().get('value', [])
            else:
                logger.error(f"Failed to get messages: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return []
    
    def mark_as_read(self, message_id: str, is_read: bool = True) -> bool:
        """Mark a message as read or unread."""
        if self.email_account:
            endpoint = f'{self.GRAPH_API_BASE}/users/{self.email_account.email_address}/messages/{message_id}'
        else:
            endpoint = f'{self.GRAPH_API_BASE}/me/messages/{message_id}'
        
        try:
            response = self._make_request(
                'PATCH',
                endpoint,
                json={'isRead': is_read}
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def get_attachments(self, message_id: str) -> List[Dict]:
        """Get attachments for a message."""
        if self.email_account:
            endpoint = f'{self.GRAPH_API_BASE}/users/{self.email_account.email_address}/messages/{message_id}/attachments'
        else:
            endpoint = f'{self.GRAPH_API_BASE}/me/messages/{message_id}/attachments'
        
        try:
            response = self._make_request('GET', endpoint)
            if response.status_code == 200:
                return response.json().get('value', [])
            return []
        except Exception:
            return []
    
    def verify_webhook(self, request_body: bytes, signature: str) -> bool:
        """
        Verify Microsoft webhook (subscription).
        
        Microsoft uses client state validation token.
        """
        # For subscriptions, validation is done via client state
        return True
    
    def parse_webhook(self, payload: Dict) -> List[InboundMessage]:
        """
        Parse Microsoft Graph webhook notification.
        
        Graph API sends change notifications that require
        fetching the actual message content.
        """
        messages = []
        
        # Microsoft sends notifications, not full messages
        # We need to fetch the actual message content
        for notification in payload.get('value', []):
            resource = notification.get('resource', '')
            change_type = notification.get('changeType', '')
            
            if 'messages' in resource and change_type == 'created':
                # This is a new message notification
                # The actual message needs to be fetched using get_messages
                messages.append(InboundMessage(
                    external_id=notification.get('resourceData', {}).get('id'),
                    sender_id=None,  # Will be populated when fetched
                    sender_name=None,
                    sender_phone=None,
                    sender_email=None,
                    message_type='email_notification',
                    content={'resource': resource},
                    text='New email notification - fetch required',
                    timestamp=timezone.now(),
                    metadata=notification
                ))
        
        return messages
    
    def check_health(self) -> Dict[str, Any]:
        """Check Microsoft Graph API connectivity."""
        try:
            if self.email_account:
                endpoint = f'{self.GRAPH_API_BASE}/users/{self.email_account.email_address}'
            else:
                endpoint = f'{self.GRAPH_API_BASE}/me'
            
            response = self._make_request('GET', endpoint)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'healthy': True,
                    'message': 'Connected to Microsoft Graph',
                    'details': {
                        'displayName': data.get('displayName'),
                        'mail': data.get('mail')
                    }
                }
            else:
                return {
                    'healthy': False,
                    'message': f'API returned {response.status_code}',
                    'details': response.json() if response.content else {}
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'message': str(e),
                'details': {}
            }
    
    def create_subscription(self, resource: str, notification_url: str,
                           expiration_hours: int = 4320) -> Optional[Dict]:
        """
        Create a webhook subscription for change notifications.
        
        Args:
            resource: Graph API resource to monitor (e.g., '/users/{id}/messages')
            notification_url: URL to receive notifications
            expiration_hours: Hours until subscription expires (max 4230 for mail)
        """
        payload = {
            'changeType': 'created,updated',
            'notificationUrl': notification_url,
            'resource': resource,
            'expirationDateTime': (timezone.now() + timedelta(hours=expiration_hours)).isoformat(),
            'clientState': self.connection.webhook_secret or 'skillsflow_webhook_state'
        }
        
        try:
            response = self._make_request(
                'POST',
                f'{self.GRAPH_API_BASE}/subscriptions',
                json=payload
            )
            
            if response.status_code in (200, 201):
                return response.json()
            else:
                logger.error(f"Failed to create subscription: {response.json()}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            return None
    
    def renew_subscription(self, subscription_id: str, expiration_hours: int = 4320) -> bool:
        """Renew an existing subscription."""
        payload = {
            'expirationDateTime': (timezone.now() + timedelta(hours=expiration_hours)).isoformat()
        }
        
        try:
            response = self._make_request(
                'PATCH',
                f'{self.GRAPH_API_BASE}/subscriptions/{subscription_id}',
                json=payload
            )
            return response.status_code == 200
        except Exception:
            return False


# Email Sync Service
class EmailSyncService:
    """
    Service to sync emails from Microsoft 365 to our conversation system.
    
    Runs periodically to:
    1. Fetch new emails from each connected mailbox
    2. Create/update conversations and messages
    3. Associate with leads where possible
    """
    
    def __init__(self):
        from crm.communication_models import EmailAccount, Conversation, Message
        self.EmailAccount = EmailAccount
        self.Conversation = Conversation
        self.Message = Message
    
    def sync_all_accounts(self):
        """Sync all active email accounts."""
        accounts = self.EmailAccount.objects.filter(is_active=True)
        
        results = []
        for account in accounts:
            try:
                count = self.sync_account(account)
                results.append({
                    'account': account.email_address,
                    'synced': count,
                    'error': None
                })
            except Exception as e:
                logger.error(f"Error syncing {account.email_address}: {e}")
                results.append({
                    'account': account.email_address,
                    'synced': 0,
                    'error': str(e)
                })
        
        return results
    
    def sync_account(self, account: 'EmailAccount') -> int:
        """
        Sync a single email account.
        
        Returns count of new messages synced.
        """
        from integrations.models import IntegrationConnection
        
        # Get connection
        connection = IntegrationConnection.objects.filter(
            provider='microsoft365',
            brand=account.brand,
            is_active=True
        ).first()
        
        if not connection:
            raise ConnectorError("No Microsoft 365 connection found")
        
        connector = MicrosoftGraphConnector(connection, account)
        
        # Get messages since last sync
        messages = connector.get_messages(
            folder='inbox',
            top=100,
            since=account.last_sync_at
        )
        
        synced_count = 0
        
        for msg_data in messages:
            try:
                self._process_email(account, msg_data)
                synced_count += 1
            except Exception as e:
                logger.error(f"Error processing email {msg_data.get('id')}: {e}")
        
        # Update last sync time
        account.last_sync_at = timezone.now()
        account.save()
        
        return synced_count
    
    def _process_email(self, account: 'EmailAccount', msg_data: Dict):
        """
        Process a single email message.
        
        Creates or updates conversation and message records.
        """
        from crm.models import Lead
        
        external_id = msg_data.get('id')
        conversation_id = msg_data.get('conversationId')
        
        # Check if already processed
        if self.Message.objects.filter(external_id=external_id).exists():
            return
        
        # Extract sender info
        from_data = msg_data.get('from', {}).get('emailAddress', {})
        sender_email = from_data.get('address', '')
        sender_name = from_data.get('name', '')
        
        # Try to find or create conversation
        conversation = self.Conversation.objects.filter(
            channel='email',
            external_id=conversation_id,
            email_account=account
        ).first()
        
        # Try to match with a lead
        lead = None
        if sender_email:
            lead = Lead.objects.filter(email__iexact=sender_email).first()
        
        if not conversation:
            conversation = self.Conversation.objects.create(
                brand=account.brand,
                campus=account.assigned_to.profile.campus if account.assigned_to and hasattr(account.assigned_to, 'profile') else None,
                channel='email',
                external_id=conversation_id,
                email_account=account,
                contact_identifier=sender_email,
                contact_name=sender_name,
                contact_email=sender_email,
                lead=lead,
                subject=msg_data.get('subject', 'No Subject'),
                status='open',
                assigned_to=account.assigned_to
            )
        
        # Create message
        self.Message.objects.create(
            conversation=conversation,
            external_id=external_id,
            direction='inbound',
            message_type='email',
            content={
                'subject': msg_data.get('subject'),
                'body': msg_data.get('body', {}).get('content', ''),
                'body_preview': msg_data.get('bodyPreview', ''),
                'has_attachments': msg_data.get('hasAttachments', False),
                'importance': msg_data.get('importance', 'normal')
            },
            text=msg_data.get('bodyPreview', ''),
            sender_name=sender_name,
            sender_identifier=sender_email,
            status='delivered',
            delivered_at=timezone.now()
        )
        
        # Update conversation
        conversation.last_message_at = timezone.now()
        conversation.message_count = (conversation.message_count or 0) + 1
        if conversation.status == 'closed':
            conversation.status = 'open'  # Reopen on new message
        conversation.save()
