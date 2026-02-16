"""
Microsoft 365 Connector

Provides integration with Microsoft 365 services:
- Microsoft Graph API (Users, Groups, Calendar, Mail, Files)
- SharePoint Online
- Teams
- Outlook
- OneDrive

Uses OAuth 2.0 with Azure AD for authentication.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone
from django.conf import settings

from integrations.models import IntegrationConnection, IntegrationSyncLog
from integrations.services.base import BaseIntegrationClient, APIError, AuthenticationError
from integrations.services.oauth import OAuthMixin

logger = logging.getLogger(__name__)


class Microsoft365Connector(OAuthMixin, BaseIntegrationClient):
    """
    Connector for Microsoft 365 services via Microsoft Graph API.
    
    Supports:
    - User profile retrieval
    - Calendar events
    - Email (read/send)
    - SharePoint sites and lists
    - Teams channels and messages
    - OneDrive files
    
    Configuration:
    - Requires Azure AD App Registration
    - Uses delegated or application permissions
    """
    
    # OAuth URLs
    OAUTH_AUTHORIZE_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    OAUTH_TOKEN_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
    
    # Default scopes for common operations
    DEFAULT_SCOPES = [
        'offline_access',  # Required for refresh tokens
        'User.Read',
        'Calendars.ReadWrite',
        'Mail.ReadWrite',
        'Mail.Send',
        'Files.ReadWrite.All',
        'Sites.ReadWrite.All',
    ]
    
    # Graph API base URL
    GRAPH_API_URL = 'https://graph.microsoft.com/v1.0'
    GRAPH_API_BETA_URL = 'https://graph.microsoft.com/beta'
    
    # Rate limit headers (Graph uses different headers)
    RATE_LIMIT_REMAINING_HEADER = 'x-ms-ratelimit-remaining'
    RATE_LIMIT_RESET_HEADER = 'Retry-After'
    
    def _get_default_base_url(self) -> str:
        """Return Microsoft Graph API URL."""
        use_beta = self.connection.settings.get('use_beta_api', False) if self.connection.settings else False
        return self.GRAPH_API_BETA_URL if use_beta else self.GRAPH_API_URL
    
    def _get_headers(self) -> Dict[str, str]:
        """Return headers with Bearer token authentication."""
        # Ensure token is valid
        self.ensure_valid_token()
        
        return {
            'Authorization': f'Bearer {self.connection.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
    
    @classmethod
    def get_authorization_url_for_tenant(
        cls,
        tenant_id: str,
        client_id: str,
        redirect_uri: str,
        scopes: list = None,
        state: str = None,
    ) -> Tuple[str, str, Optional[str]]:
        """
        Generate authorization URL for a specific Azure AD tenant.
        
        Args:
            tenant_id: Azure AD tenant ID (or 'common' for multi-tenant)
            client_id: Azure AD application client ID
            redirect_uri: OAuth callback URL
            scopes: List of Microsoft Graph scopes
            state: Optional state parameter
            
        Returns:
            Tuple of (authorization_url, state, None)
        """
        auth_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize'
        
        # Create a temporary provider-like object
        class TempProvider:
            oauth_authorization_url = auth_url
            default_scopes = scopes or cls.DEFAULT_SCOPES
        
        return cls.get_authorization_url(
            TempProvider(),
            client_id,
            redirect_uri,
            scopes=scopes,
            state=state,
            use_pkce=True,  # Microsoft recommends PKCE
        )
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection by fetching current user profile.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            response = self._request('GET', '/me')
            user_data = response.json()
            
            display_name = user_data.get('displayName', 'Unknown')
            email = user_data.get('mail') or user_data.get('userPrincipalName', 'Unknown')
            
            return True, f"Connected as {display_name} ({email})"
            
        except AuthenticationError as e:
            return False, f"Authentication failed: {e}"
        except APIError as e:
            return False, f"API error: {e}"
        except Exception as e:
            return False, f"Connection failed: {e}"
    
    def sync(self, entity_type: str = None, full_sync: bool = False) -> IntegrationSyncLog:
        """
        Sync data with Microsoft 365.
        
        Args:
            entity_type: Type of entity to sync (users, calendar, mail, files)
            full_sync: Whether to do a full sync or incremental
            
        Returns:
            IntegrationSyncLog with results
        """
        if entity_type == 'calendar':
            return self._sync_calendar(full_sync)
        elif entity_type == 'mail':
            return self._sync_mail(full_sync)
        elif entity_type == 'files':
            return self._sync_files(full_sync)
        elif entity_type == 'users':
            return self._sync_users(full_sync)
        else:
            # Default: sync users
            return self._sync_users(full_sync)
    
    # User methods
    
    def get_current_user(self) -> Dict[str, Any]:
        """Get the current authenticated user's profile."""
        response = self._request('GET', '/me')
        return response.json()
    
    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get a specific user by ID or UPN."""
        response = self._request('GET', f'/users/{user_id}')
        return response.json()
    
    def list_users(self, top: int = 100, filter_query: str = None) -> List[Dict[str, Any]]:
        """
        List users in the organization.
        
        Args:
            top: Maximum number of users to return
            filter_query: OData filter query
            
        Returns:
            List of user dictionaries
        """
        params = {'$top': top}
        if filter_query:
            params['$filter'] = filter_query
        
        response = self._request('GET', '/users', params=params)
        data = response.json()
        
        users = data.get('value', [])
        
        # Handle pagination
        while '@odata.nextLink' in data and len(users) < top:
            next_url = data['@odata.nextLink']
            # Extract endpoint from full URL
            endpoint = next_url.replace(self.base_url, '')
            response = self._request('GET', endpoint)
            data = response.json()
            users.extend(data.get('value', []))
        
        return users[:top]
    
    def _sync_users(self, full_sync: bool = False) -> IntegrationSyncLog:
        """Sync users from Microsoft 365."""
        self.start_sync_log('users', direction='INBOUND')
        
        try:
            users = self.list_users(top=500)
            
            processed = 0
            failed = 0
            
            for user in users:
                try:
                    user_id = user.get('id')
                    if user_id:
                        self.create_or_update_mapping(
                            entity_type='user',
                            internal_id=user.get('mail') or user.get('userPrincipalName'),
                            external_id=user_id,
                            external_data=user,
                        )
                        processed += 1
                except Exception as e:
                    logger.warning(f"Failed to sync user: {e}")
                    failed += 1
            
            return self.complete_sync_log(
                status='SUCCESS' if failed == 0 else 'PARTIAL',
                records_total=len(users),
                records_processed=processed,
                records_failed=failed,
            )
            
        except Exception as e:
            return self.complete_sync_log(
                status='FAILED',
                error_message=str(e),
            )
    
    # Calendar methods
    
    def list_calendars(self) -> List[Dict[str, Any]]:
        """List user's calendars."""
        response = self._request('GET', '/me/calendars')
        return response.json().get('value', [])
    
    def get_calendar_events(
        self,
        calendar_id: str = None,
        start_datetime: datetime = None,
        end_datetime: datetime = None,
        top: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get calendar events.
        
        Args:
            calendar_id: Specific calendar ID (None for default)
            start_datetime: Start of time range
            end_datetime: End of time range
            top: Maximum events to return
            
        Returns:
            List of event dictionaries
        """
        # Default to next 30 days
        if not start_datetime:
            start_datetime = timezone.now()
        if not end_datetime:
            end_datetime = start_datetime + timedelta(days=30)
        
        endpoint = f'/me/calendars/{calendar_id}/events' if calendar_id else '/me/events'
        
        params = {
            '$top': top,
            '$orderby': 'start/dateTime',
            '$filter': f"start/dateTime ge '{start_datetime.isoformat()}' and end/dateTime le '{end_datetime.isoformat()}'",
        }
        
        response = self._request('GET', endpoint, params=params)
        return response.json().get('value', [])
    
    def create_calendar_event(
        self,
        subject: str,
        start: datetime,
        end: datetime,
        body: str = None,
        attendees: List[str] = None,
        location: str = None,
        is_online_meeting: bool = False,
        calendar_id: str = None,
    ) -> Dict[str, Any]:
        """
        Create a calendar event.
        
        Args:
            subject: Event title
            start: Start datetime
            end: End datetime
            body: Event description
            attendees: List of email addresses
            location: Location string
            is_online_meeting: Whether to create a Teams meeting
            calendar_id: Specific calendar ID
            
        Returns:
            Created event data
        """
        event_data = {
            'subject': subject,
            'start': {
                'dateTime': start.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end.isoformat(),
                'timeZone': 'UTC',
            },
        }
        
        if body:
            event_data['body'] = {
                'contentType': 'HTML',
                'content': body,
            }
        
        if attendees:
            event_data['attendees'] = [
                {
                    'emailAddress': {'address': email},
                    'type': 'required',
                }
                for email in attendees
            ]
        
        if location:
            event_data['location'] = {'displayName': location}
        
        if is_online_meeting:
            event_data['isOnlineMeeting'] = True
            event_data['onlineMeetingProvider'] = 'teamsForBusiness'
        
        endpoint = f'/me/calendars/{calendar_id}/events' if calendar_id else '/me/events'
        response = self._request('POST', endpoint, json_data=event_data)
        
        return response.json()
    
    def _sync_calendar(self, full_sync: bool = False) -> IntegrationSyncLog:
        """Sync calendar events."""
        self.start_sync_log('calendar', direction='BIDIRECTIONAL')
        
        try:
            events = self.get_calendar_events(top=200)
            
            processed = 0
            failed = 0
            
            for event in events:
                try:
                    event_id = event.get('id')
                    if event_id:
                        self.create_or_update_mapping(
                            entity_type='calendar_event',
                            internal_id=event.get('iCalUId') or event_id,
                            external_id=event_id,
                            external_data=event,
                        )
                        processed += 1
                except Exception as e:
                    logger.warning(f"Failed to sync event: {e}")
                    failed += 1
            
            return self.complete_sync_log(
                status='SUCCESS' if failed == 0 else 'PARTIAL',
                records_total=len(events),
                records_processed=processed,
                records_failed=failed,
            )
            
        except Exception as e:
            return self.complete_sync_log(
                status='FAILED',
                error_message=str(e),
            )
    
    # Mail methods
    
    def get_messages(
        self,
        folder: str = 'inbox',
        top: int = 50,
        filter_query: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Get email messages.
        
        Args:
            folder: Mail folder (inbox, sentitems, drafts, etc.)
            top: Maximum messages to return
            filter_query: OData filter
            
        Returns:
            List of message dictionaries
        """
        params = {
            '$top': top,
            '$orderby': 'receivedDateTime desc',
        }
        if filter_query:
            params['$filter'] = filter_query
        
        response = self._request('GET', f'/me/mailFolders/{folder}/messages', params=params)
        return response.json().get('value', [])
    
    def send_mail(
        self,
        to: List[str],
        subject: str,
        body: str,
        body_type: str = 'HTML',
        cc: List[str] = None,
        bcc: List[str] = None,
        attachments: List[Dict] = None,
        save_to_sent: bool = True,
    ) -> bool:
        """
        Send an email.
        
        Args:
            to: List of recipient email addresses
            subject: Email subject
            body: Email body content
            body_type: 'HTML' or 'Text'
            cc: CC recipients
            bcc: BCC recipients
            attachments: List of attachment dicts with name, contentBytes
            save_to_sent: Whether to save to Sent Items
            
        Returns:
            True if sent successfully
        """
        message = {
            'subject': subject,
            'body': {
                'contentType': body_type,
                'content': body,
            },
            'toRecipients': [{'emailAddress': {'address': addr}} for addr in to],
        }
        
        if cc:
            message['ccRecipients'] = [{'emailAddress': {'address': addr}} for addr in cc]
        if bcc:
            message['bccRecipients'] = [{'emailAddress': {'address': addr}} for addr in bcc]
        if attachments:
            message['attachments'] = attachments
        
        data = {
            'message': message,
            'saveToSentItems': save_to_sent,
        }
        
        self._request('POST', '/me/sendMail', json_data=data)
        return True
    
    def _sync_mail(self, full_sync: bool = False) -> IntegrationSyncLog:
        """Sync recent emails."""
        self.start_sync_log('mail', direction='INBOUND')
        
        try:
            messages = self.get_messages(top=100)
            
            return self.complete_sync_log(
                status='SUCCESS',
                records_total=len(messages),
                records_processed=len(messages),
            )
            
        except Exception as e:
            return self.complete_sync_log(
                status='FAILED',
                error_message=str(e),
            )
    
    # SharePoint methods
    
    def get_sharepoint_sites(self, search: str = None) -> List[Dict[str, Any]]:
        """
        List SharePoint sites.
        
        Args:
            search: Search query to filter sites
            
        Returns:
            List of site dictionaries
        """
        if search:
            response = self._request('GET', f'/sites?search={search}')
        else:
            response = self._request('GET', '/sites?search=*')
        
        return response.json().get('value', [])
    
    def get_sharepoint_lists(self, site_id: str) -> List[Dict[str, Any]]:
        """Get lists in a SharePoint site."""
        response = self._request('GET', f'/sites/{site_id}/lists')
        return response.json().get('value', [])
    
    def get_list_items(
        self,
        site_id: str,
        list_id: str,
        expand: List[str] = None,
        top: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get items from a SharePoint list.
        
        Args:
            site_id: SharePoint site ID
            list_id: List ID
            expand: Fields to expand
            top: Maximum items
            
        Returns:
            List of item dictionaries
        """
        params = {'$top': top}
        if expand:
            params['$expand'] = ','.join(expand)
        
        response = self._request(
            'GET',
            f'/sites/{site_id}/lists/{list_id}/items',
            params=params,
        )
        return response.json().get('value', [])
    
    def create_list_item(
        self,
        site_id: str,
        list_id: str,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create an item in a SharePoint list.
        
        Args:
            site_id: SharePoint site ID
            list_id: List ID
            fields: Field values for the item
            
        Returns:
            Created item data
        """
        data = {'fields': fields}
        response = self._request(
            'POST',
            f'/sites/{site_id}/lists/{list_id}/items',
            json_data=data,
        )
        return response.json()
    
    # OneDrive/Files methods
    
    def get_drive_items(
        self,
        folder_path: str = 'root',
        top: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List items in OneDrive folder.
        
        Args:
            folder_path: Path relative to root, or 'root'
            top: Maximum items
            
        Returns:
            List of drive item dictionaries
        """
        if folder_path == 'root':
            endpoint = '/me/drive/root/children'
        else:
            endpoint = f'/me/drive/root:/{folder_path}:/children'
        
        response = self._request('GET', endpoint, params={'$top': top})
        return response.json().get('value', [])
    
    def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        folder_path: str = '',
    ) -> Dict[str, Any]:
        """
        Upload a file to OneDrive.
        
        Args:
            file_content: File content as bytes
            file_name: Name for the file
            folder_path: Destination folder path
            
        Returns:
            Created file data
        """
        if folder_path:
            endpoint = f'/me/drive/root:/{folder_path}/{file_name}:/content'
        else:
            endpoint = f'/me/drive/root:/{file_name}:/content'
        
        response = self._request(
            'PUT',
            endpoint,
            data=file_content,
            headers={'Content-Type': 'application/octet-stream'},
        )
        return response.json()
    
    def download_file(self, item_id: str) -> bytes:
        """
        Download a file from OneDrive.
        
        Args:
            item_id: Drive item ID
            
        Returns:
            File content as bytes
        """
        response = self._request('GET', f'/me/drive/items/{item_id}/content')
        return response.content
    
    def _sync_files(self, full_sync: bool = False) -> IntegrationSyncLog:
        """Sync OneDrive files."""
        self.start_sync_log('files', direction='INBOUND')
        
        try:
            items = self.get_drive_items(top=200)
            
            processed = 0
            
            for item in items:
                item_id = item.get('id')
                if item_id:
                    self.create_or_update_mapping(
                        entity_type='file',
                        internal_id=item.get('name'),
                        external_id=item_id,
                        external_data=item,
                    )
                    processed += 1
            
            return self.complete_sync_log(
                status='SUCCESS',
                records_total=len(items),
                records_processed=processed,
            )
            
        except Exception as e:
            return self.complete_sync_log(
                status='FAILED',
                error_message=str(e),
            )
    
    # Teams methods
    
    def list_teams(self) -> List[Dict[str, Any]]:
        """List teams the user is a member of."""
        response = self._request('GET', '/me/joinedTeams')
        return response.json().get('value', [])
    
    def get_team_channels(self, team_id: str) -> List[Dict[str, Any]]:
        """List channels in a team."""
        response = self._request('GET', f'/teams/{team_id}/channels')
        return response.json().get('value', [])
    
    def send_channel_message(
        self,
        team_id: str,
        channel_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """
        Send a message to a Teams channel.
        
        Args:
            team_id: Team ID
            channel_id: Channel ID
            message: Message content (HTML supported)
            
        Returns:
            Created message data
        """
        data = {
            'body': {
                'contentType': 'html',
                'content': message,
            },
        }
        
        response = self._request(
            'POST',
            f'/teams/{team_id}/channels/{channel_id}/messages',
            json_data=data,
        )
        return response.json()
    
    def create_online_meeting(
        self,
        subject: str,
        start: datetime,
        end: datetime,
        attendees: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an online Teams meeting.
        
        Args:
            subject: Meeting subject
            start: Start datetime
            end: End datetime
            attendees: List of attendee email addresses
            
        Returns:
            Created meeting data with join URL
        """
        data = {
            'subject': subject,
            'startDateTime': start.isoformat(),
            'endDateTime': end.isoformat(),
        }
        
        if attendees:
            data['participants'] = {
                'attendees': [
                    {'emailAddress': {'address': email}}
                    for email in attendees
                ],
            }
        
        response = self._request('POST', '/me/onlineMeetings', json_data=data)
        return response.json()
