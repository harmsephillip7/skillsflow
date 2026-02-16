"""
SharePoint Integration Service

Provides seamless integration with Microsoft SharePoint for document storage.
Uses Microsoft Graph API for file operations with authentication via app credentials.

Configuration required in settings.py:
    SHAREPOINT_TENANT_ID = 'your-tenant-id'
    SHAREPOINT_CLIENT_ID = 'your-client-id'
    SHAREPOINT_CLIENT_SECRET = 'your-client-secret'
    SHAREPOINT_SITE_NAME = 'your-site-name'  # e.g., 'SkillsFlow'
    SHAREPOINT_BASE_FOLDER = '/SkillsFlow/Documents'  # Base folder for all uploads
"""
import hashlib
import logging
import mimetypes
from datetime import datetime
from typing import BinaryIO, Dict, List, Optional, Tuple
from urllib.parse import quote

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


class SharePointError(Exception):
    """Base exception for SharePoint operations."""
    pass


class SharePointAuthError(SharePointError):
    """Authentication error with SharePoint."""
    pass


class SharePointNotFoundError(SharePointError):
    """Requested resource not found in SharePoint."""
    pass


class SharePointService:
    """
    Service for interacting with SharePoint via Microsoft Graph API.
    
    Usage:
        service = SharePointService()
        
        # Upload a file
        result = service.upload_file(
            folder_path='/Placements/2025/AcmeCorp/L001234',
            file=request.FILES['document'],
            metadata={'learner_id': 'L001234', 'document_type': 'LOGBOOK'}
        )
        
        # Download a file
        file_content = service.download_file(item_id='abc123')
        
        # Get file info
        metadata = service.get_file_metadata(item_id='abc123')
    """
    
    # Cache keys
    TOKEN_CACHE_KEY = 'sharepoint_access_token'
    SITE_ID_CACHE_KEY = 'sharepoint_site_id'
    DRIVE_ID_CACHE_KEY = 'sharepoint_drive_id'
    
    def __init__(self):
        """Initialize SharePoint service with credentials from settings."""
        self.tenant_id = getattr(settings, 'SHAREPOINT_TENANT_ID', None)
        self.client_id = getattr(settings, 'SHAREPOINT_CLIENT_ID', None)
        self.client_secret = getattr(settings, 'SHAREPOINT_CLIENT_SECRET', None)
        self.site_name = getattr(settings, 'SHAREPOINT_SITE_NAME', 'SkillsFlow')
        self.base_folder = getattr(settings, 'SHAREPOINT_BASE_FOLDER', '/Documents')
        
        self._access_token = None
        self._site_id = None
        self._drive_id = None
    
    @property
    def is_configured(self) -> bool:
        """Check if SharePoint integration is properly configured."""
        return all([
            self.tenant_id,
            self.client_id,
            self.client_secret,
        ])
    
    def _get_access_token(self) -> str:
        """
        Get or refresh the access token for Microsoft Graph API.
        Uses client credentials flow for app-only authentication.
        """
        if not self.is_configured:
            raise SharePointAuthError(
                "SharePoint is not configured. Please set SHAREPOINT_TENANT_ID, "
                "SHAREPOINT_CLIENT_ID, and SHAREPOINT_CLIENT_SECRET in settings."
            )
        
        # Try cache first
        cached_token = cache.get(self.TOKEN_CACHE_KEY)
        if cached_token:
            return cached_token
        
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required for SharePoint integration")
        
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://graph.microsoft.com/.default',
        }
        
        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600) - 60  # Buffer
            
            # Cache the token
            cache.set(self.TOKEN_CACHE_KEY, access_token, expires_in)
            
            return access_token
            
        except requests.RequestException as e:
            logger.error(f"SharePoint authentication failed: {e}")
            raise SharePointAuthError(f"Authentication failed: {e}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Graph API requests."""
        return {
            'Authorization': f'Bearer {self._get_access_token()}',
            'Content-Type': 'application/json',
        }
    
    def _get_site_id(self) -> str:
        """Get the SharePoint site ID."""
        cached_id = cache.get(self.SITE_ID_CACHE_KEY)
        if cached_id:
            return cached_id
        
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required")
        
        # Get site by name
        url = f"https://graph.microsoft.com/v1.0/sites/root:/sites/{self.site_name}"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            site_id = response.json()['id']
            cache.set(self.SITE_ID_CACHE_KEY, site_id, 86400)  # Cache for 24 hours
            
            return site_id
            
        except requests.RequestException as e:
            logger.error(f"Failed to get SharePoint site ID: {e}")
            raise SharePointError(f"Failed to get site ID: {e}")
    
    def _get_drive_id(self) -> str:
        """Get the default document library drive ID."""
        cached_id = cache.get(self.DRIVE_ID_CACHE_KEY)
        if cached_id:
            return cached_id
        
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required")
        
        site_id = self._get_site_id()
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            drive_id = response.json()['id']
            cache.set(self.DRIVE_ID_CACHE_KEY, drive_id, 86400)
            
            return drive_id
            
        except requests.RequestException as e:
            logger.error(f"Failed to get SharePoint drive ID: {e}")
            raise SharePointError(f"Failed to get drive ID: {e}")
    
    def _ensure_folder_exists(self, folder_path: str) -> str:
        """
        Ensure a folder path exists, creating folders as needed.
        Returns the folder item ID.
        """
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required")
        
        drive_id = self._get_drive_id()
        full_path = f"{self.base_folder}/{folder_path}".replace('//', '/')
        
        # Try to get the folder
        encoded_path = quote(full_path, safe='')
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            
            if response.status_code == 200:
                return response.json()['id']
            
            # Folder doesn't exist, create it
            if response.status_code == 404:
                return self._create_folder_path(full_path)
            
            response.raise_for_status()
            
        except requests.RequestException as e:
            logger.error(f"Failed to check/create folder: {e}")
            raise SharePointError(f"Folder operation failed: {e}")
    
    def _create_folder_path(self, path: str) -> str:
        """Create folder path recursively."""
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required")
        
        drive_id = self._get_drive_id()
        parts = path.strip('/').split('/')
        current_path = ''
        folder_id = None
        
        for part in parts:
            parent_path = current_path if current_path else 'root'
            current_path = f"{current_path}/{part}" if current_path else part
            
            # Check if folder exists
            encoded_path = quote(current_path, safe='')
            check_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}"
            
            check_response = requests.get(check_url, headers=self._get_headers())
            
            if check_response.status_code == 200:
                folder_id = check_response.json()['id']
                continue
            
            # Create folder
            if parent_path == 'root':
                create_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
            else:
                encoded_parent = quote(parent_path, safe='')
                create_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_parent}:/children"
            
            create_data = {
                'name': part,
                'folder': {},
                '@microsoft.graph.conflictBehavior': 'fail'
            }
            
            headers = self._get_headers()
            create_response = requests.post(create_url, headers=headers, json=create_data)
            
            if create_response.status_code in [200, 201]:
                folder_id = create_response.json()['id']
            elif create_response.status_code == 409:
                # Folder already exists (race condition)
                check_response = requests.get(check_url, headers=self._get_headers())
                folder_id = check_response.json()['id']
            else:
                create_response.raise_for_status()
        
        return folder_id
    
    def upload_file(
        self,
        folder_path: str,
        file: BinaryIO,
        filename: str = None,
        metadata: Dict = None
    ) -> Dict:
        """
        Upload a file to SharePoint.
        
        Args:
            folder_path: Relative path within the base folder (e.g., 'Placements/2025/AcmeCorp')
            file: File object to upload
            filename: Optional filename override
            metadata: Optional metadata dict to store with the file
            
        Returns:
            Dict with: item_id, web_url, drive_id, site_id, file_size
        """
        if not self.is_configured:
            raise SharePointError("SharePoint is not configured")
        
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required")
        
        # Get file info
        if hasattr(file, 'name'):
            original_filename = filename or file.name
        else:
            original_filename = filename or 'document'
        
        # Ensure folder exists
        self._ensure_folder_exists(folder_path)
        
        # Read file content
        if hasattr(file, 'read'):
            content = file.read()
            if hasattr(file, 'seek'):
                file.seek(0)
        else:
            content = file
        
        file_size = len(content)
        
        # Build upload URL
        drive_id = self._get_drive_id()
        full_path = f"{self.base_folder}/{folder_path}/{original_filename}".replace('//', '/')
        encoded_path = quote(full_path, safe='')
        
        if file_size < 4 * 1024 * 1024:  # Less than 4MB, use simple upload
            upload_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}:/content"
            
            headers = {
                'Authorization': f'Bearer {self._get_access_token()}',
                'Content-Type': 'application/octet-stream',
            }
            
            response = requests.put(upload_url, headers=headers, data=content)
            
        else:
            # Large file upload session (not implemented yet)
            raise SharePointError("Files larger than 4MB require upload session (not yet implemented)")
        
        try:
            response.raise_for_status()
            result = response.json()
            
            return {
                'item_id': result['id'],
                'web_url': result.get('webUrl', ''),
                'drive_id': drive_id,
                'site_id': self._get_site_id(),
                'file_size': result.get('size', file_size),
                'created_at': result.get('createdDateTime'),
                'mime_type': result.get('file', {}).get('mimeType', ''),
            }
            
        except requests.RequestException as e:
            logger.error(f"SharePoint upload failed: {e}")
            raise SharePointError(f"Upload failed: {e}")
    
    def download_file(self, item_id: str) -> bytes:
        """
        Download a file from SharePoint.
        
        Args:
            item_id: The SharePoint item ID
            
        Returns:
            File content as bytes
        """
        if not self.is_configured:
            raise SharePointError("SharePoint is not configured")
        
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required")
        
        drive_id = self._get_drive_id()
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.content
            
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response.status_code == 404:
                raise SharePointNotFoundError(f"File not found: {item_id}")
            logger.error(f"SharePoint download failed: {e}")
            raise SharePointError(f"Download failed: {e}")
    
    def get_file_metadata(self, item_id: str) -> Dict:
        """
        Get metadata for a file.
        
        Args:
            item_id: The SharePoint item ID
            
        Returns:
            Dict with file metadata
        """
        if not self.is_configured:
            raise SharePointError("SharePoint is not configured")
        
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required")
        
        drive_id = self._get_drive_id()
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            result = response.json()
            return {
                'id': result['id'],
                'name': result['name'],
                'size': result.get('size', 0),
                'mime_type': result.get('file', {}).get('mimeType', ''),
                'web_url': result.get('webUrl', ''),
                'created_at': result.get('createdDateTime'),
                'modified_at': result.get('lastModifiedDateTime'),
                'created_by': result.get('createdBy', {}).get('user', {}).get('displayName', ''),
            }
            
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response.status_code == 404:
                raise SharePointNotFoundError(f"File not found: {item_id}")
            logger.error(f"SharePoint metadata fetch failed: {e}")
            raise SharePointError(f"Metadata fetch failed: {e}")
    
    def delete_file(self, item_id: str) -> bool:
        """
        Delete a file from SharePoint.
        
        Args:
            item_id: The SharePoint item ID
            
        Returns:
            True if deleted successfully
        """
        if not self.is_configured:
            raise SharePointError("SharePoint is not configured")
        
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required")
        
        drive_id = self._get_drive_id()
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}"
        
        try:
            response = requests.delete(url, headers=self._get_headers())
            
            if response.status_code == 204:
                return True
            if response.status_code == 404:
                return True  # Already deleted
                
            response.raise_for_status()
            return True
            
        except requests.RequestException as e:
            logger.error(f"SharePoint delete failed: {e}")
            raise SharePointError(f"Delete failed: {e}")
    
    def generate_preview_url(self, item_id: str) -> str:
        """
        Generate a preview URL for embedding document preview in the app.
        
        Args:
            item_id: The SharePoint item ID
            
        Returns:
            Preview embed URL
        """
        if not self.is_configured:
            raise SharePointError("SharePoint is not configured")
        
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required")
        
        drive_id = self._get_drive_id()
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/preview"
        
        try:
            response = requests.post(url, headers=self._get_headers())
            response.raise_for_status()
            
            return response.json().get('getUrl', '')
            
        except requests.RequestException as e:
            logger.error(f"SharePoint preview URL generation failed: {e}")
            return ''
    
    def search_files(self, query: str, folder_path: str = None) -> List[Dict]:
        """
        Search for files in SharePoint.
        
        Args:
            query: Search query string
            folder_path: Optional folder to search within
            
        Returns:
            List of matching file metadata dicts
        """
        if not self.is_configured:
            raise SharePointError("SharePoint is not configured")
        
        try:
            import requests
        except ImportError:
            raise SharePointError("requests library is required")
        
        drive_id = self._get_drive_id()
        
        if folder_path:
            full_path = f"{self.base_folder}/{folder_path}".replace('//', '/')
            encoded_path = quote(full_path, safe='')
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}:/search(q='{quote(query)}')"
        else:
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/search(q='{quote(query)}')"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            results = []
            for item in response.json().get('value', []):
                if 'file' in item:  # Only files, not folders
                    results.append({
                        'id': item['id'],
                        'name': item['name'],
                        'size': item.get('size', 0),
                        'web_url': item.get('webUrl', ''),
                        'modified_at': item.get('lastModifiedDateTime'),
                    })
            
            return results
            
        except requests.RequestException as e:
            logger.error(f"SharePoint search failed: {e}")
            raise SharePointError(f"Search failed: {e}")
    
    def get_folder_structure(
        self,
        learner_number: str,
        client_name: str,
        year: int = None
    ) -> str:
        """
        Get the standard folder path for a learner's documents.
        
        Structure: /Placements/{Year}/{ClientName}/{LearnerNumber}/
        
        Args:
            learner_number: The learner's reference number
            client_name: The client/employer name (sanitized)
            year: Year (defaults to current year)
            
        Returns:
            Folder path string
        """
        if year is None:
            year = datetime.now().year
        
        # Sanitize names for folder path
        safe_client = ''.join(c for c in client_name if c.isalnum() or c in ' -_')[:50]
        safe_learner = ''.join(c for c in learner_number if c.isalnum() or c in '-_')
        
        return f"Placements/{year}/{safe_client}/{safe_learner}"


# Singleton instance
_sharepoint_service = None


def get_sharepoint_service() -> SharePointService:
    """Get the singleton SharePoint service instance."""
    global _sharepoint_service
    if _sharepoint_service is None:
        _sharepoint_service = SharePointService()
    return _sharepoint_service
