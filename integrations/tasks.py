"""
Integration Celery Tasks

Background tasks for integration operations:
- sync_connection: Run sync for a specific connection
- refresh_expiring_tokens: Refresh tokens expiring soon
- check_connections_health: Health check all active connections
- process_webhook_queue: Process queued webhook events
"""

import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)

# Try to import celery, but make it optional for serverless deployments
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Create a dummy decorator that just returns the function
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def sync_connection(self, connection_id: int, entity_type: str = None, full_sync: bool = False):
    """
    Run sync for a specific integration connection.
    
    Args:
        connection_id: IntegrationConnection ID
        entity_type: Optional entity type to sync
        full_sync: Whether to do a full sync
        
    Returns:
        Dict with sync results
    """
    from integrations.models import IntegrationConnection, IntegrationSyncLog
    from integrations.services import ConnectionError, AuthenticationError
    
    try:
        connection = IntegrationConnection.objects.select_related('provider').get(
            id=connection_id,
            is_active=True,
        )
    except IntegrationConnection.DoesNotExist:
        logger.warning(f"Connection {connection_id} not found or inactive")
        return {'status': 'skipped', 'message': 'Connection not found or inactive'}
    
    # Get the connector class
    connector = get_connector_for_connection(connection)
    if not connector:
        logger.warning(f"No connector available for provider: {connection.provider.slug}")
        return {'status': 'skipped', 'message': 'No connector available'}
    
    try:
        logger.info(f"Starting sync for connection {connection_id} ({connection.provider.name})")
        
        # Run the sync
        sync_log = connector.sync(entity_type=entity_type, full_sync=full_sync)
        
        return {
            'status': sync_log.status.lower(),
            'records_processed': sync_log.records_processed,
            'records_failed': sync_log.records_failed,
            'duration_ms': sync_log.duration_ms,
        }
        
    except AuthenticationError as e:
        logger.error(f"Authentication failed for connection {connection_id}: {e}")
        connection.health_status = 'UNHEALTHY'
        connection.status_message = f'Authentication failed: {e}'
        connection.save(update_fields=['health_status', 'status_message'])
        
        return {'status': 'failed', 'message': str(e)}
        
    except ConnectionError as e:
        logger.error(f"Connection error for {connection_id}: {e}")
        connection.health_status = 'UNHEALTHY'
        connection.status_message = f'Connection error: {e}'
        connection.save(update_fields=['health_status', 'status_message'])
        
        # Retry on connection errors
        raise self.retry(exc=e)
        
    except Exception as e:
        logger.exception(f"Sync failed for connection {connection_id}: {e}")
        
        # Create failed sync log
        IntegrationSyncLog.objects.create(
            connection=connection,
            entity_type=entity_type or 'unknown',
            direction='OUTBOUND',
            status='FAILED',
            error_message=str(e),
            is_scheduled=True,
        )
        
        return {'status': 'failed', 'message': str(e)}


@shared_task
def sync_all_connections(provider_slug: str = None):
    """
    Sync all active connections (optionally filtered by provider).
    
    Args:
        provider_slug: Optional provider slug to filter by
        
    Returns:
        Dict with summary of all syncs
    """
    from integrations.models import IntegrationConnection
    
    queryset = IntegrationConnection.objects.filter(
        is_active=True,
        sync_enabled=True,
    ).select_related('provider')
    
    if provider_slug:
        queryset = queryset.filter(provider__slug=provider_slug)
    
    results = {
        'total': 0,
        'queued': 0,
        'skipped': 0,
    }
    
    for connection in queryset:
        results['total'] += 1
        
        # Check if sync is due
        if connection.last_sync_at and connection.sync_frequency_minutes:
            next_sync = connection.last_sync_at + timedelta(minutes=connection.sync_frequency_minutes)
            if timezone.now() < next_sync:
                results['skipped'] += 1
                continue
        
        # Queue the sync task
        sync_connection.delay(connection.id)
        results['queued'] += 1
    
    logger.info(f"Queued {results['queued']} syncs out of {results['total']} connections")
    return results


@shared_task
def refresh_expiring_tokens():
    """
    Refresh access tokens that are expiring soon.
    
    Checks all OAuth connections and refreshes tokens that will
    expire within the next 10 minutes.
    
    Returns:
        Dict with refresh results
    """
    from integrations.models import IntegrationConnection
    from integrations.services.oauth import OAuthMixin, OAuthError
    
    # Find tokens expiring in the next 10 minutes
    expiry_threshold = timezone.now() + timedelta(minutes=10)
    
    connections = IntegrationConnection.objects.filter(
        is_active=True,
        provider__auth_type='OAUTH2',
        token_expires_at__lte=expiry_threshold,
        refresh_token__isnull=False,
    ).exclude(
        refresh_token=''
    ).select_related('provider')
    
    results = {
        'total': connections.count(),
        'refreshed': 0,
        'failed': 0,
        'errors': [],
    }
    
    for connection in connections:
        try:
            connector = get_connector_for_connection(connection)
            if connector and hasattr(connector, 'refresh_access_token'):
                connector.refresh_access_token()
                results['refreshed'] += 1
                logger.info(f"Refreshed token for connection {connection.id}")
            else:
                # Use generic OAuth refresh
                refresh_token_for_connection(connection)
                results['refreshed'] += 1
                
        except OAuthError as e:
            results['failed'] += 1
            results['errors'].append({
                'connection_id': connection.id,
                'error': str(e),
            })
            logger.error(f"Failed to refresh token for connection {connection.id}: {e}")
            
            # Mark connection as unhealthy
            connection.health_status = 'UNHEALTHY'
            connection.status_message = f'Token refresh failed: {e}'
            connection.save(update_fields=['health_status', 'status_message'])
            
        except Exception as e:
            results['failed'] += 1
            results['errors'].append({
                'connection_id': connection.id,
                'error': str(e),
            })
            logger.exception(f"Unexpected error refreshing token for {connection.id}")
    
    logger.info(f"Token refresh: {results['refreshed']} succeeded, {results['failed']} failed")
    return results


@shared_task
def check_connections_health():
    """
    Run health checks on all active connections.
    
    Returns:
        Dict with health check results
    """
    from integrations.models import IntegrationConnection
    
    connections = IntegrationConnection.objects.filter(
        is_active=True,
    ).select_related('provider')
    
    results = {
        'total': connections.count(),
        'healthy': 0,
        'degraded': 0,
        'unhealthy': 0,
        'errors': [],
    }
    
    for connection in connections:
        try:
            connector = get_connector_for_connection(connection)
            if connector:
                connector.update_health_status()
                
                if connection.health_status == 'HEALTHY':
                    results['healthy'] += 1
                elif connection.health_status == 'DEGRADED':
                    results['degraded'] += 1
                else:
                    results['unhealthy'] += 1
            else:
                # No connector - can't check health
                logger.debug(f"No connector for {connection.provider.slug}, skipping health check")
                
        except Exception as e:
            results['errors'].append({
                'connection_id': connection.id,
                'error': str(e),
            })
            connection.health_status = 'UNHEALTHY'
            connection.status_message = f'Health check failed: {e}'
            connection.save(update_fields=['health_status', 'status_message'])
            results['unhealthy'] += 1
    
    logger.info(
        f"Health check: {results['healthy']} healthy, "
        f"{results['degraded']} degraded, {results['unhealthy']} unhealthy"
    )
    return results


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_webhook_event(self, webhook_log_id: int):
    """
    Process a webhook event that was queued for async processing.
    
    Args:
        webhook_log_id: IntegrationWebhookLog ID
        
    Returns:
        Dict with processing result
    """
    from integrations.models import IntegrationWebhookLog
    
    try:
        log = IntegrationWebhookLog.objects.select_related(
            'webhook', 'webhook__connection', 'webhook__connection__provider'
        ).get(id=webhook_log_id)
    except IntegrationWebhookLog.DoesNotExist:
        logger.warning(f"Webhook log {webhook_log_id} not found")
        return {'status': 'skipped', 'message': 'Log not found'}
    
    if log.status != 'PENDING':
        logger.debug(f"Webhook log {webhook_log_id} already processed")
        return {'status': 'skipped', 'message': 'Already processed'}
    
    try:
        # Get the appropriate handler based on provider
        handler = get_webhook_handler_for_provider(log.webhook.connection.provider.slug)
        
        if handler:
            result = handler(log.webhook, log.event_type, log.payload)
            log.status = 'SUCCESS'
            log.response_data = result if isinstance(result, dict) else {'result': str(result)}
        else:
            # No specific handler - just mark as processed
            log.status = 'SUCCESS'
            log.response_data = {'message': 'No handler configured'}
        
        log.processed_at = timezone.now()
        log.save()
        
        return {'status': 'success', 'event_type': log.event_type}
        
    except Exception as e:
        logger.exception(f"Failed to process webhook {webhook_log_id}: {e}")
        log.status = 'FAILED'
        log.error_message = str(e)
        log.processed_at = timezone.now()
        log.save()
        
        # Retry on failure
        raise self.retry(exc=e)


@shared_task
def cleanup_old_logs(days: int = 30):
    """
    Clean up old sync and webhook logs.
    
    Args:
        days: Delete logs older than this many days
        
    Returns:
        Dict with deletion counts
    """
    from integrations.models import IntegrationSyncLog, IntegrationWebhookLog
    
    cutoff = timezone.now() - timedelta(days=days)
    
    sync_count, _ = IntegrationSyncLog.objects.filter(
        started_at__lt=cutoff,
    ).delete()
    
    webhook_count, _ = IntegrationWebhookLog.objects.filter(
        received_at__lt=cutoff,
    ).delete()
    
    logger.info(f"Cleaned up {sync_count} sync logs and {webhook_count} webhook logs")
    
    return {
        'sync_logs_deleted': sync_count,
        'webhook_logs_deleted': webhook_count,
    }


# Helper functions

def get_connector_for_connection(connection):
    """
    Get the appropriate connector instance for a connection.
    
    Args:
        connection: IntegrationConnection instance
        
    Returns:
        Connector instance or None
    """
    provider_slug = connection.provider.slug
    
    # Map provider slugs to connector classes
    connectors = {
        'microsoft365': 'integrations.connectors.microsoft365.Microsoft365Connector',
        'microsoft-365': 'integrations.connectors.microsoft365.Microsoft365Connector',
        # Add more connectors as they're implemented
        # 'moodle': 'integrations.connectors.moodle.MoodleConnector',
        # 'sage-intacct': 'integrations.connectors.sage.SageIntacctConnector',
        # 'zoho-bigin': 'integrations.connectors.zoho.ZohoBiginConnector',
    }
    
    connector_path = connectors.get(provider_slug)
    if not connector_path:
        return None
    
    try:
        module_path, class_name = connector_path.rsplit('.', 1)
        module = __import__(module_path, fromlist=[class_name])
        connector_class = getattr(module, class_name)
        return connector_class(connection)
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to load connector {connector_path}: {e}")
        return None


def refresh_token_for_connection(connection):
    """
    Generic token refresh for OAuth connections.
    
    Args:
        connection: IntegrationConnection instance
    """
    import requests
    from integrations.services.oauth import OAuthError
    
    if not connection.refresh_token:
        raise OAuthError("No refresh token available")
    
    token_url = connection.provider.oauth_token_url
    if not token_url:
        raise OAuthError("No token URL configured for provider")
    
    response = requests.post(
        token_url,
        data={
            'grant_type': 'refresh_token',
            'refresh_token': connection.refresh_token,
            'client_id': connection.client_id,
            'client_secret': connection.client_secret,
        },
        timeout=30,
    )
    
    if response.status_code != 200:
        raise OAuthError(f"Token refresh failed: {response.text}")
    
    token_data = response.json()
    
    connection.access_token = token_data.get('access_token')
    if 'refresh_token' in token_data:
        connection.refresh_token = token_data['refresh_token']
    
    expires_in = token_data.get('expires_in')
    if expires_in:
        connection.token_expires_at = timezone.now() + timedelta(seconds=int(expires_in))
    
    connection.save(update_fields=['access_token', 'refresh_token', 'token_expires_at'])


def get_webhook_handler_for_provider(provider_slug: str):
    """
    Get the webhook event handler for a provider.
    
    Args:
        provider_slug: Provider slug
        
    Returns:
        Handler function or None
    """
    # Map provider slugs to handler functions
    handlers = {
        # Add handlers as they're implemented
        # 'microsoft365': handle_microsoft_webhook,
        # 'moodle': handle_moodle_webhook,
    }
    
    return handlers.get(provider_slug)
