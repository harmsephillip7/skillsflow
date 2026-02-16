"""
Webhook Handler Service

Provides webhook receiving and verification:
- HMAC-SHA256 signature verification
- IP allowlist checking
- Event routing and logging
- Payload parsing
"""

import hmac
import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from django.http import HttpRequest, JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from ipaddress import ip_address, ip_network

from integrations.models import (
    IntegrationWebhook,
    IntegrationWebhookLog,
    IntegrationConnection,
)

logger = logging.getLogger(__name__)


class WebhookVerificationError(Exception):
    """Raised when webhook verification fails."""
    pass


class WebhookHandler:
    """
    Handler for incoming webhooks with security verification.
    
    Security features:
    - HMAC-SHA256 signature verification
    - IP allowlist checking
    - Timestamp validation (replay attack prevention)
    - Event type filtering
    
    Usage:
        handler = WebhookHandler(webhook)
        if handler.verify_request(request):
            data = handler.parse_payload(request)
            # Process webhook data
    """
    
    # Header names for different providers (common defaults)
    SIGNATURE_HEADERS = [
        'X-Hub-Signature-256',  # GitHub, Meta
        'X-Signature-256',      # Generic
        'X-Webhook-Signature',  # Various
        'Stripe-Signature',     # Stripe
        'X-Shopify-Hmac-Sha256',  # Shopify
    ]
    
    TIMESTAMP_HEADERS = [
        'X-Hub-Timestamp',
        'X-Webhook-Timestamp',
        'Stripe-Signature',  # Contains timestamp
    ]
    
    # Maximum age for timestamp validation (5 minutes)
    MAX_TIMESTAMP_AGE = 300
    
    def __init__(
        self,
        webhook: IntegrationWebhook,
        signature_header: str = None,
        timestamp_header: str = None,
    ):
        """
        Initialize the webhook handler.
        
        Args:
            webhook: IntegrationWebhook instance
            signature_header: Custom header name for signature
            timestamp_header: Custom header name for timestamp
        """
        self.webhook = webhook
        self.signature_header = signature_header
        self.timestamp_header = timestamp_header
        self._log: Optional[IntegrationWebhookLog] = None
    
    def verify_request(self, request: HttpRequest) -> bool:
        """
        Verify the incoming webhook request.
        
        Performs:
        1. IP allowlist check (if configured)
        2. HMAC signature verification
        3. Timestamp validation (if available)
        
        Args:
            request: Django HttpRequest object
            
        Returns:
            True if verification passes
            
        Raises:
            WebhookVerificationError: If verification fails
        """
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # IP allowlist check
        if not self._verify_ip(client_ip):
            logger.warning(f"Webhook IP not allowed: {client_ip}")
            raise WebhookVerificationError(f"IP address {client_ip} not in allowlist")
        
        # Signature verification
        if self.webhook.secret:
            if not self._verify_signature(request):
                logger.warning(f"Webhook signature verification failed")
                raise WebhookVerificationError("Invalid signature")
        
        # Timestamp validation (optional, provider-specific)
        timestamp = self._extract_timestamp(request)
        if timestamp and not self._verify_timestamp(timestamp):
            logger.warning(f"Webhook timestamp too old: {timestamp}")
            raise WebhookVerificationError("Timestamp too old - possible replay attack")
        
        return True
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP from request, handling proxies."""
        # Check X-Forwarded-For first (for proxied requests)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Get the first IP in the chain
            return x_forwarded_for.split(',')[0].strip()
        
        # Check X-Real-IP
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        # Fall back to REMOTE_ADDR
        return request.META.get('REMOTE_ADDR', '')
    
    def _verify_ip(self, client_ip: str) -> bool:
        """
        Check if client IP is in the allowlist.
        
        Args:
            client_ip: Client IP address string
            
        Returns:
            True if IP is allowed (or no allowlist configured)
        """
        # If no allowlist configured, allow all
        if not self.webhook.allowed_ips:
            return True
        
        try:
            client = ip_address(client_ip)
            
            for allowed in self.webhook.allowed_ips:
                # Handle CIDR notation
                if '/' in allowed:
                    if client in ip_network(allowed, strict=False):
                        return True
                else:
                    if client == ip_address(allowed):
                        return True
            
            return False
            
        except ValueError as e:
            logger.error(f"Invalid IP address format: {e}")
            return False
    
    def _verify_signature(self, request: HttpRequest) -> bool:
        """
        Verify HMAC-SHA256 signature.
        
        Args:
            request: Django HttpRequest
            
        Returns:
            True if signature is valid
        """
        # Get signature from headers
        signature = None
        header_name = self.signature_header
        
        if header_name:
            signature = request.META.get(f'HTTP_{header_name.upper().replace("-", "_")}')
        else:
            # Try common signature headers
            for header in self.SIGNATURE_HEADERS:
                sig = request.META.get(f'HTTP_{header.upper().replace("-", "_")}')
                if sig:
                    signature = sig
                    header_name = header
                    break
        
        if not signature:
            # No signature header found
            logger.debug("No signature header found in request")
            return False
        
        # Get the raw body
        body = request.body
        
        # Calculate expected signature
        expected = self._calculate_signature(body)
        
        # Handle different signature formats
        # Some providers prefix with algorithm (e.g., "sha256=abc123")
        if '=' in signature:
            parts = signature.split('=', 1)
            if len(parts) == 2:
                algo, sig = parts
                if algo.lower() in ('sha256', 'sha-256'):
                    signature = sig
        
        # Handle Stripe-style signatures (t=timestamp,v1=signature)
        if ',' in signature and 't=' in signature:
            for part in signature.split(','):
                if part.startswith('v1='):
                    signature = part[3:]
                    break
        
        # Constant-time comparison
        return hmac.compare_digest(expected.lower(), signature.lower())
    
    def _calculate_signature(self, body: bytes) -> str:
        """
        Calculate HMAC-SHA256 signature.
        
        Args:
            body: Request body bytes
            
        Returns:
            Hex-encoded signature
        """
        secret = self.webhook.secret
        if isinstance(secret, str):
            secret = secret.encode('utf-8')
        
        signature = hmac.new(secret, body, hashlib.sha256)
        return signature.hexdigest()
    
    def _extract_timestamp(self, request: HttpRequest) -> Optional[int]:
        """
        Extract timestamp from request.
        
        Args:
            request: Django HttpRequest
            
        Returns:
            Unix timestamp or None
        """
        timestamp = None
        
        # Check custom header first
        if self.timestamp_header:
            ts = request.META.get(f'HTTP_{self.timestamp_header.upper().replace("-", "_")}')
            if ts:
                try:
                    timestamp = int(ts)
                except ValueError:
                    pass
        
        # Check common timestamp headers
        if not timestamp:
            for header in self.TIMESTAMP_HEADERS:
                ts = request.META.get(f'HTTP_{header.upper().replace("-", "_")}')
                if ts:
                    # Handle Stripe-style (t=timestamp in signature header)
                    if 't=' in ts:
                        for part in ts.split(','):
                            if part.startswith('t='):
                                try:
                                    timestamp = int(part[2:])
                                    break
                                except ValueError:
                                    pass
                    else:
                        try:
                            timestamp = int(ts)
                            break
                        except ValueError:
                            pass
        
        return timestamp
    
    def _verify_timestamp(self, timestamp: int) -> bool:
        """
        Verify timestamp is recent enough.
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            True if timestamp is within allowed age
        """
        now = int(timezone.now().timestamp())
        age = abs(now - timestamp)
        return age <= self.MAX_TIMESTAMP_AGE
    
    def parse_payload(self, request: HttpRequest) -> Dict[str, Any]:
        """
        Parse the webhook payload.
        
        Args:
            request: Django HttpRequest
            
        Returns:
            Parsed payload dictionary
        """
        content_type = request.content_type or ''
        
        if 'application/json' in content_type:
            try:
                return json.loads(request.body)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON payload: {e}")
                return {}
        
        elif 'application/x-www-form-urlencoded' in content_type:
            return dict(request.POST)
        
        elif 'multipart/form-data' in content_type:
            return dict(request.POST)
        
        else:
            # Try JSON parsing anyway
            try:
                return json.loads(request.body)
            except:
                return {'raw': request.body.decode('utf-8', errors='replace')}
    
    def create_log(
        self,
        request: HttpRequest,
        event_type: str = None,
        verified: bool = True,
    ) -> IntegrationWebhookLog:
        """
        Create a webhook log entry.
        
        Args:
            request: Django HttpRequest
            event_type: Type of event
            verified: Whether verification passed
            
        Returns:
            IntegrationWebhookLog instance
        """
        payload = self.parse_payload(request) if verified else {}
        
        # Extract headers (sanitize sensitive ones)
        headers = {}
        for key, value in request.META.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').title()
                # Don't log signature values
                if 'signature' not in header_name.lower() and 'auth' not in header_name.lower():
                    headers[header_name] = value
        
        self._log = IntegrationWebhookLog.objects.create(
            webhook=self.webhook,
            event_type=event_type or payload.get('event', payload.get('type', 'unknown')),
            payload=payload,
            headers=headers,
            source_ip=self._get_client_ip(request),
            was_verified=verified,
            status='PENDING',
        )
        
        return self._log
    
    def complete_log(
        self,
        status: str = 'SUCCESS',
        response_data: dict = None,
        error_message: str = '',
    ) -> Optional[IntegrationWebhookLog]:
        """
        Complete a webhook log entry.
        
        Args:
            status: Final status (SUCCESS, FAILED, IGNORED)
            response_data: Response data to log
            error_message: Error message if failed
            
        Returns:
            Updated IntegrationWebhookLog instance
        """
        if not self._log:
            return None
        
        self._log.status = status
        if response_data:
            self._log.response_data = response_data
        if error_message:
            self._log.error_message = error_message
        self._log.processed_at = timezone.now()
        self._log.save()
        
        return self._log
    
    def is_event_subscribed(self, event_type: str) -> bool:
        """
        Check if webhook is subscribed to this event type.
        
        Args:
            event_type: Event type string
            
        Returns:
            True if subscribed (or no filter configured)
        """
        if not self.webhook.event_types:
            return True  # No filter = all events
        
        # Support wildcards (e.g., "user.*")
        for subscribed in self.webhook.event_types:
            if subscribed == '*':
                return True
            if subscribed.endswith('.*'):
                prefix = subscribed[:-2]
                if event_type.startswith(prefix):
                    return True
            if subscribed == event_type:
                return True
        
        return False


def webhook_endpoint(get_webhook_func: Callable[[str], IntegrationWebhook]):
    """
    Decorator for webhook endpoint views.
    
    Usage:
        @webhook_endpoint(lambda endpoint_id: IntegrationWebhook.objects.get(endpoint_id=endpoint_id))
        def my_webhook(request, webhook, payload, handler):
            # Process webhook
            return {'status': 'ok'}
    
    Args:
        get_webhook_func: Function to retrieve webhook from endpoint_id
    """
    def decorator(view_func):
        @csrf_exempt
        @require_POST
        def wrapper(request, endpoint_id, *args, **kwargs):
            try:
                webhook = get_webhook_func(endpoint_id)
            except IntegrationWebhook.DoesNotExist:
                return JsonResponse({'error': 'Webhook not found'}, status=404)
            
            if not webhook.is_active:
                return JsonResponse({'error': 'Webhook inactive'}, status=403)
            
            handler = WebhookHandler(webhook)
            
            # Verify request
            try:
                handler.verify_request(request)
            except WebhookVerificationError as e:
                handler.create_log(request, verified=False)
                handler.complete_log(status='FAILED', error_message=str(e))
                return JsonResponse({'error': 'Verification failed'}, status=403)
            
            # Parse payload
            payload = handler.parse_payload(request)
            event_type = payload.get('event', payload.get('type', 'unknown'))
            
            # Check event subscription
            if not handler.is_event_subscribed(event_type):
                handler.create_log(request, event_type=event_type)
                handler.complete_log(status='IGNORED', error_message='Event type not subscribed')
                return JsonResponse({'status': 'ignored'}, status=200)
            
            # Create log
            handler.create_log(request, event_type=event_type)
            
            try:
                # Call the actual view
                result = view_func(request, webhook, payload, handler, *args, **kwargs)
                
                # Complete log
                if isinstance(result, dict):
                    handler.complete_log(status='SUCCESS', response_data=result)
                    return JsonResponse(result)
                elif isinstance(result, HttpResponse):
                    handler.complete_log(status='SUCCESS')
                    return result
                else:
                    handler.complete_log(status='SUCCESS')
                    return JsonResponse({'status': 'ok'})
                    
            except Exception as e:
                logger.exception(f"Webhook processing error: {e}")
                handler.complete_log(status='FAILED', error_message=str(e))
                return JsonResponse({'error': 'Processing failed'}, status=500)
        
        return wrapper
    return decorator


class WebhookDispatcher:
    """
    Dispatcher for routing webhooks to appropriate handlers.
    
    Usage:
        dispatcher = WebhookDispatcher()
        dispatcher.register('user.created', handle_user_created)
        dispatcher.register('order.*', handle_order_events)
        
        dispatcher.dispatch(webhook, event_type, payload)
    """
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
    
    def register(self, event_pattern: str, handler: Callable) -> None:
        """
        Register a handler for an event pattern.
        
        Args:
            event_pattern: Event type or pattern (supports * wildcard)
            handler: Callable(webhook, payload) -> result
        """
        if event_pattern not in self._handlers:
            self._handlers[event_pattern] = []
        self._handlers[event_pattern].append(handler)
    
    def dispatch(
        self,
        webhook: IntegrationWebhook,
        event_type: str,
        payload: dict,
    ) -> List[Tuple[Callable, Any]]:
        """
        Dispatch event to registered handlers.
        
        Args:
            webhook: IntegrationWebhook instance
            event_type: Event type string
            payload: Event payload
            
        Returns:
            List of (handler, result) tuples
        """
        results = []
        
        for pattern, handlers in self._handlers.items():
            if self._matches_pattern(event_type, pattern):
                for handler in handlers:
                    try:
                        result = handler(webhook, payload)
                        results.append((handler, result))
                    except Exception as e:
                        logger.exception(f"Handler {handler.__name__} failed: {e}")
                        results.append((handler, e))
        
        return results
    
    def _matches_pattern(self, event_type: str, pattern: str) -> bool:
        """Check if event type matches pattern."""
        if pattern == '*':
            return True
        if pattern.endswith('.*'):
            return event_type.startswith(pattern[:-2])
        return pattern == event_type
