"""
Base Integration Client

Provides the foundational class for all integration connectors with:
- HTTP request handling with retry logic
- Rate limit tracking and enforcement
- Health check infrastructure
- Sync operation framework
- Logging and error handling
"""

import time
import logging
import hashlib
import requests
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from django.utils import timezone

from integrations.models import (
    IntegrationConnection,
    IntegrationSyncLog,
    IntegrationEntityMapping,
)

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Base exception for integration errors."""
    pass


class AuthenticationError(IntegrationError):
    """Raised when authentication fails."""
    pass


class RateLimitError(IntegrationError):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after


class APIError(IntegrationError):
    """Raised when API returns an error response."""
    
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class ConnectionError(IntegrationError):
    """Raised when connection to external service fails."""
    pass


class BaseIntegrationClient(ABC):
    """
    Abstract base class for all integration connectors.
    
    Subclasses must implement:
    - _get_headers(): Return auth headers for requests
    - test_connection(): Verify connection is working
    - sync(): Perform data synchronization
    
    Provides:
    - _request(): HTTP client with retry and rate limit handling
    - Rate limit tracking from response headers
    - Sync logging infrastructure
    - Entity mapping helpers
    """
    
    # Rate limit header names (override in subclass if different)
    RATE_LIMIT_REMAINING_HEADER = 'X-RateLimit-Remaining'
    RATE_LIMIT_RESET_HEADER = 'X-RateLimit-Reset'
    RATE_LIMIT_LIMIT_HEADER = 'X-RateLimit-Limit'
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF_FACTOR = 2  # Exponential backoff: 1s, 2s, 4s
    RETRY_STATUS_CODES = [429, 500, 502, 503, 504]
    
    # Request timeout (seconds)
    REQUEST_TIMEOUT = 30
    
    def __init__(self, connection: IntegrationConnection):
        """
        Initialize the client with a connection instance.
        
        Args:
            connection: IntegrationConnection instance with credentials
        """
        self.connection = connection
        self.provider = connection.provider
        self.session = requests.Session()
        self._sync_log: Optional[IntegrationSyncLog] = None
    
    @property
    def base_url(self) -> str:
        """Get the API base URL."""
        return self.connection.base_url or self._get_default_base_url()
    
    @abstractmethod
    def _get_default_base_url(self) -> str:
        """Return the default API base URL for this provider."""
        pass
    
    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """
        Return headers for API requests including authentication.
        
        Returns:
            Dictionary of HTTP headers
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test if the connection is working.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        pass
    
    @abstractmethod
    def sync(self, entity_type: str = None, full_sync: bool = False) -> IntegrationSyncLog:
        """
        Perform data synchronization.
        
        Args:
            entity_type: Specific entity type to sync (or all if None)
            full_sync: Whether to do a full sync or incremental
            
        Returns:
            IntegrationSyncLog instance with results
        """
        pass
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None,
        json_data: Dict = None,
        headers: Dict = None,
        timeout: int = None,
        retry: bool = True,
    ) -> requests.Response:
        """
        Make an HTTP request with retry logic and rate limit handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: API endpoint (will be joined with base_url)
            params: Query parameters
            data: Form data
            json_data: JSON body data
            headers: Additional headers (merged with auth headers)
            timeout: Request timeout in seconds
            retry: Whether to retry on failure
            
        Returns:
            requests.Response object
            
        Raises:
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit exceeded and no retry
            APIError: If API returns error response
            ConnectionError: If connection fails
        """
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Merge headers
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)
        
        timeout = timeout or self.REQUEST_TIMEOUT
        
        last_exception = None
        
        for attempt in range(self.MAX_RETRIES if retry else 1):
            try:
                # Check if we're rate limited
                if self._is_rate_limited():
                    wait_time = self._get_rate_limit_wait_time()
                    if wait_time > 0:
                        logger.warning(f"Rate limited, waiting {wait_time}s before request")
                        time.sleep(min(wait_time, 60))  # Max 60s wait
                
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=request_headers,
                    timeout=timeout,
                )
                
                # Update rate limit info from headers
                self._update_rate_limits(response)
                
                # Handle response
                if response.status_code == 401:
                    raise AuthenticationError(f"Authentication failed: {response.text}")
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    if attempt < self.MAX_RETRIES - 1 and retry:
                        logger.warning(f"Rate limited, retrying in {retry_after}s")
                        time.sleep(min(retry_after, 60))
                        continue
                    raise RateLimitError(f"Rate limit exceeded", retry_after=retry_after)
                
                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                    except:
                        error_data = {'raw': response.text}
                    
                    if response.status_code in self.RETRY_STATUS_CODES and attempt < self.MAX_RETRIES - 1 and retry:
                        wait_time = self.RETRY_BACKOFF_FACTOR ** attempt
                        logger.warning(f"Request failed with {response.status_code}, retrying in {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    
                    raise APIError(
                        f"API error: {response.status_code}",
                        status_code=response.status_code,
                        response_data=error_data
                    )
                
                return response
                
            except requests.exceptions.Timeout as e:
                last_exception = ConnectionError(f"Request timeout: {e}")
                if attempt < self.MAX_RETRIES - 1 and retry:
                    wait_time = self.RETRY_BACKOFF_FACTOR ** attempt
                    logger.warning(f"Request timeout, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                    
            except requests.exceptions.ConnectionError as e:
                last_exception = ConnectionError(f"Connection failed: {e}")
                if attempt < self.MAX_RETRIES - 1 and retry:
                    wait_time = self.RETRY_BACKOFF_FACTOR ** attempt
                    logger.warning(f"Connection error, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
        
        # All retries exhausted
        if last_exception:
            raise last_exception
        raise ConnectionError("Request failed after all retries")
    
    def _update_rate_limits(self, response: requests.Response) -> None:
        """
        Update connection rate limit info from response headers.
        
        Args:
            response: HTTP response object
        """
        try:
            remaining = response.headers.get(self.RATE_LIMIT_REMAINING_HEADER)
            reset = response.headers.get(self.RATE_LIMIT_RESET_HEADER)
            
            if remaining is not None:
                self.connection.rate_limit_remaining = int(remaining)
            
            if reset is not None:
                # Handle both timestamp and seconds-until-reset formats
                reset_val = int(reset)
                if reset_val > 1000000000:  # Unix timestamp
                    self.connection.rate_limit_resets_at = datetime.fromtimestamp(reset_val, tz=timezone.utc)
                else:  # Seconds until reset
                    self.connection.rate_limit_resets_at = timezone.now() + timedelta(seconds=reset_val)
            
            self.connection.save(update_fields=['rate_limit_remaining', 'rate_limit_resets_at'])
            
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse rate limit headers: {e}")
    
    def _is_rate_limited(self) -> bool:
        """Check if we're currently rate limited."""
        if self.connection.rate_limit_remaining is not None and self.connection.rate_limit_remaining <= 0:
            if self.connection.rate_limit_resets_at and self.connection.rate_limit_resets_at > timezone.now():
                return True
        return False
    
    def _get_rate_limit_wait_time(self) -> int:
        """Get seconds to wait before rate limit resets."""
        if self.connection.rate_limit_resets_at:
            delta = self.connection.rate_limit_resets_at - timezone.now()
            return max(0, int(delta.total_seconds()))
        return 0
    
    # Sync helpers
    
    def start_sync_log(
        self,
        entity_type: str,
        direction: str = 'OUTBOUND',
        operation: str = 'sync',
        user=None,
        is_scheduled: bool = False
    ) -> IntegrationSyncLog:
        """
        Create a new sync log entry.
        
        Args:
            entity_type: Type of entity being synced
            direction: INBOUND, OUTBOUND, or BIDIRECTIONAL
            operation: Specific operation name
            user: User who triggered the sync (None for scheduled)
            is_scheduled: Whether this is a scheduled sync
            
        Returns:
            IntegrationSyncLog instance
        """
        self._sync_log = IntegrationSyncLog.objects.create(
            connection=self.connection,
            entity_type=entity_type,
            direction=direction,
            operation=operation,
            status='IN_PROGRESS',
            triggered_by=user,
            is_scheduled=is_scheduled,
        )
        return self._sync_log
    
    def complete_sync_log(
        self,
        status: str = 'SUCCESS',
        records_total: int = 0,
        records_processed: int = 0,
        records_failed: int = 0,
        records_skipped: int = 0,
        error_message: str = '',
        error_details: dict = None,
        request_payload: dict = None,
        response_payload: dict = None,
    ) -> IntegrationSyncLog:
        """
        Complete a sync log entry with results.
        
        Args:
            status: Final status (SUCCESS, PARTIAL, FAILED)
            records_*: Record counts
            error_message: Error message if failed
            error_details: Detailed error info
            request_payload: Request data for debugging
            response_payload: Response data for debugging
            
        Returns:
            Updated IntegrationSyncLog instance
        """
        if not self._sync_log:
            logger.warning("No sync log to complete")
            return None
        
        self._sync_log.records_total = records_total
        self._sync_log.records_processed = records_processed
        self._sync_log.records_failed = records_failed
        self._sync_log.records_skipped = records_skipped
        
        if request_payload:
            self._sync_log.request_payload = request_payload
        if response_payload:
            self._sync_log.response_payload = response_payload
        if error_details:
            self._sync_log.error_details = error_details
        
        self._sync_log.complete(status=status, error_message=error_message)
        
        # Update connection sync status
        self.connection.mark_sync_complete(status=status)
        
        return self._sync_log
    
    # Entity mapping helpers
    
    def get_external_id(self, entity_type: str, internal_id: str) -> Optional[str]:
        """
        Get the external ID for an internal entity.
        
        Args:
            entity_type: Type of entity
            internal_id: Internal (SkillsFlow) ID
            
        Returns:
            External ID or None if not mapped
        """
        mapping = IntegrationEntityMapping.objects.filter(
            connection=self.connection,
            entity_type=entity_type,
            internal_id=str(internal_id)
        ).first()
        return mapping.external_id if mapping else None
    
    def get_internal_id(self, entity_type: str, external_id: str) -> Optional[str]:
        """
        Get the internal ID for an external entity.
        
        Args:
            entity_type: Type of entity
            external_id: External system ID
            
        Returns:
            Internal ID or None if not mapped
        """
        mapping = IntegrationEntityMapping.objects.filter(
            connection=self.connection,
            entity_type=entity_type,
            external_id=str(external_id)
        ).first()
        return mapping.internal_id if mapping else None
    
    def create_or_update_mapping(
        self,
        entity_type: str,
        internal_id: str,
        external_id: str,
        external_data: dict = None,
    ) -> IntegrationEntityMapping:
        """
        Create or update an entity mapping.
        
        Args:
            entity_type: Type of entity
            internal_id: Internal (SkillsFlow) ID
            external_id: External system ID
            external_data: Optional cached external data
            
        Returns:
            IntegrationEntityMapping instance
        """
        mapping, created = IntegrationEntityMapping.objects.update_or_create(
            connection=self.connection,
            entity_type=entity_type,
            internal_id=str(internal_id),
            defaults={
                'external_id': str(external_id),
                'external_data': external_data or {},
                'sync_status': 'SYNCED',
            }
        )
        return mapping
    
    def calculate_checksum(self, data: dict) -> str:
        """
        Calculate a checksum for change detection.
        
        Args:
            data: Dictionary of entity data
            
        Returns:
            SHA-256 hash string
        """
        import json
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    # Health check
    
    def check_health(self) -> Tuple[str, str]:
        """
        Perform a health check on the connection.
        
        Returns:
            Tuple of (status: HEALTHY/DEGRADED/UNHEALTHY, message: str)
        """
        try:
            success, message = self.test_connection()
            
            if success:
                # Check rate limits
                if self._is_rate_limited():
                    return 'DEGRADED', 'Rate limited'
                
                # Check token expiry
                if self.connection.token_expires_soon:
                    return 'DEGRADED', 'Token expires soon'
                
                return 'HEALTHY', message
            else:
                return 'UNHEALTHY', message
                
        except AuthenticationError as e:
            return 'UNHEALTHY', f'Authentication failed: {e}'
        except RateLimitError as e:
            return 'DEGRADED', f'Rate limited: {e}'
        except (APIError, ConnectionError) as e:
            return 'UNHEALTHY', str(e)
        except Exception as e:
            return 'UNHEALTHY', f'Unexpected error: {e}'
    
    def update_health_status(self) -> None:
        """Update the connection's health status."""
        status, message = self.check_health()
        self.connection.health_status = status
        self.connection.status_message = message
        self.connection.last_health_check = timezone.now()
        self.connection.save(update_fields=['health_status', 'status_message', 'last_health_check'])
