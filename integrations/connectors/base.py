"""
Base Connector Class

Abstract base class for all channel connectors with common interface
for sending messages, handling webhooks, and managing connections.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import requests
from django.utils import timezone


logger = logging.getLogger(__name__)


class ConnectorError(Exception):
    """Base exception for connector errors."""
    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class RateLimitError(ConnectorError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message, code='RATE_LIMITED')
        self.retry_after = retry_after


class AuthenticationError(ConnectorError):
    """Raised when authentication fails."""
    def __init__(self, message: str):
        super().__init__(message, code='AUTH_FAILED')


class MessageStatus(Enum):
    """Standard message status across all connectors."""
    PENDING = 'pending'
    QUEUED = 'queued'
    SENT = 'sent'
    DELIVERED = 'delivered'
    READ = 'read'
    FAILED = 'failed'


@dataclass
class MessageResult:
    """Standard result from sending a message."""
    success: bool
    external_id: Optional[str] = None
    status: MessageStatus = MessageStatus.PENDING
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict] = None
    
    @classmethod
    def success_result(cls, external_id: str, status: MessageStatus = MessageStatus.SENT, metadata: dict = None):
        return cls(success=True, external_id=external_id, status=status, metadata=metadata)
    
    @classmethod
    def failure_result(cls, error_code: str, error_message: str, metadata: dict = None):
        return cls(success=False, error_code=error_code, error_message=error_message, 
                   status=MessageStatus.FAILED, metadata=metadata)


@dataclass
class InboundMessage:
    """Parsed inbound message from any channel."""
    external_id: str
    sender_id: str
    sender_name: Optional[str]
    sender_phone: Optional[str]
    message_type: str  # text, image, video, audio, document, location, etc.
    content: Dict[str, Any]
    text: Optional[str]
    timestamp: timezone.datetime
    metadata: Dict[str, Any]
    
    # For threading (email, etc.)
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    
    # Media
    media_url: Optional[str] = None
    media_mime_type: Optional[str] = None
    media_filename: Optional[str] = None


@dataclass
class Contact:
    """Contact information from a channel."""
    external_id: str
    phone: Optional[str]
    email: Optional[str]
    name: Optional[str]
    profile_pic_url: Optional[str] = None
    metadata: Optional[Dict] = None


class BaseConnector(ABC):
    """
    Abstract base class for all channel connectors.
    
    Provides common interface for:
    - Sending messages (text, media, templates)
    - Handling webhooks
    - Managing connection health
    - Rate limiting
    """
    
    def __init__(self, connection: 'IntegrationConnection'):
        """
        Initialize connector with integration connection.
        
        Args:
            connection: IntegrationConnection instance with credentials
        """
        self.connection = connection
        self.session = requests.Session()
        self._setup_session()
    
    @abstractmethod
    def _setup_session(self):
        """Set up HTTP session with authentication headers."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'whatsapp', 'facebook', 'email')."""
        pass
    
    # ==================== Sending Messages ====================
    
    @abstractmethod
    def send_text(self, recipient: str, text: str, **kwargs) -> MessageResult:
        """
        Send a text message.
        
        Args:
            recipient: Recipient identifier (phone, email, user ID)
            text: Message text
            **kwargs: Provider-specific options
            
        Returns:
            MessageResult with send status
        """
        pass
    
    @abstractmethod
    def send_media(self, recipient: str, media_type: str, media_url: str, 
                   caption: str = None, **kwargs) -> MessageResult:
        """
        Send a media message (image, video, audio, document).
        
        Args:
            recipient: Recipient identifier
            media_type: Type of media (image, video, audio, document)
            media_url: URL to the media file
            caption: Optional caption
            **kwargs: Provider-specific options
            
        Returns:
            MessageResult with send status
        """
        pass
    
    def send_template(self, recipient: str, template_name: str, 
                      template_vars: Dict = None, **kwargs) -> MessageResult:
        """
        Send a template message (primarily for WhatsApp).
        
        Default implementation raises NotImplementedError.
        Override in connectors that support templates.
        """
        raise NotImplementedError(f"{self.provider_name} does not support template messages")
    
    # ==================== Webhook Handling ====================
    
    @abstractmethod
    def verify_webhook(self, request_data: Dict, signature: str) -> bool:
        """
        Verify webhook signature.
        
        Args:
            request_data: Raw request body
            signature: Signature from headers
            
        Returns:
            True if signature is valid
        """
        pass
    
    @abstractmethod
    def parse_webhook(self, payload: Dict) -> List[InboundMessage]:
        """
        Parse webhook payload into InboundMessage objects.
        
        Args:
            payload: Webhook JSON payload
            
        Returns:
            List of InboundMessage objects
        """
        pass
    
    # ==================== Health & Status ====================
    
    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """
        Check connector health and connection status.
        
        Returns:
            Dict with health status: {healthy: bool, message: str, details: dict}
        """
        pass
    
    def refresh_token(self) -> bool:
        """
        Refresh OAuth token if applicable.
        
        Default implementation returns False (no refresh needed).
        Override for OAuth-based connectors.
        """
        return False
    
    def test_connection(self):
        """
        UI-friendly connection test.
        Returns (success: bool, message: str)
        """
        health = self.check_health() or {}
        healthy = bool(health.get("healthy"))
        message = health.get("message") or ("OK" if healthy else "Unhealthy")
        return healthy, message
    
    # ==================== Utility Methods ====================
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with error handling and rate limit detection.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional request arguments
            
        Returns:
            Response object
            
        Raises:
            RateLimitError: If rate limited
            ConnectorError: For other errors
        """
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After', 60)
                raise RateLimitError(
                    f"Rate limited by {self.provider_name}",
                    retry_after=int(retry_after)
                )
            
            # Check for auth errors
            if response.status_code in (401, 403):
                raise AuthenticationError(
                    f"Authentication failed for {self.provider_name}: {response.text}"
                )
            
            return response
            
        except requests.RequestException as e:
            logger.error(f"Request error for {self.provider_name}: {e}")
            raise ConnectorError(f"Request failed: {str(e)}")
    
    def _log_send(self, recipient: str, message_type: str, result: MessageResult):
        """Log message send attempt."""
        if result.success:
            logger.info(
                f"[{self.provider_name}] Sent {message_type} to {recipient}: {result.external_id}"
            )
        else:
            logger.error(
                f"[{self.provider_name}] Failed to send {message_type} to {recipient}: "
                f"{result.error_code} - {result.error_message}"
            )
