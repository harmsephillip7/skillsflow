"""
Integration Hub Views

Provides a user-friendly interface for managing integrations:
- Integration marketplace (available providers)
- Connected integrations management
- OAuth flows
- Sync operations
- Webhook management
"""

import secrets
import logging
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator

from integrations.models import (
    IntegrationProvider,
    IntegrationConnection,
    IntegrationSyncLog,
    IntegrationWebhook,
    IntegrationWebhookLog,
)
from integrations.services.oauth import OAuthMixin, OAuthCallbackHandler, OAuthError
from integrations.services.webhooks import WebhookHandler, WebhookVerificationError
from integrations.tasks import sync_connection, check_connections_health
from tenants.models import Brand

logger = logging.getLogger(__name__)


#Added for testing
from tenants.models import Brand


def _get_current_brand(request):
    """
    Determine the active brand for the logged-in user.

    Priority:
      1) request.user.profile.brand (if exists)
      2) session brand_id (if set)
      3) first active Brand in DB (fallback for superusers/dev)
    """
    try:
        profile = getattr(request.user, "profile", None)
        if profile and getattr(profile, "brand", None):
            return profile.brand
    except Exception:
        pass

    brand_id = request.session.get("brand_id")
    if brand_id:
        try:
            from tenants.models import Brand
            return Brand.objects.filter(id=brand_id, is_active=True).first()
        except Exception:
            pass

    # Fallback for dev / superuser
    try:
        from tenants.models import Brand
        return Brand.objects.filter(is_active=True).first()
    except Exception:
        return None
    

def _get_active_brand_for_request(request):
    # 1) if your project stores a selected brand in session
    brand_id = request.session.get("active_brand_id")
    if brand_id:
        b = Brand.objects.filter(id=brand_id).first()
        if b:
            return b

    # 2) if your user model has a brand relation (common)
    user_brand = getattr(request.user, "brand", None)
    if user_brand:
        return user_brand

    # 3) last resort: first brand in DB (DEV ONLY)
    return Brand.objects.order_by("id").first()




# Permission decorator shortcut
def integration_permission_required(view_func):
    """Decorator for views requiring integration management permission."""
    from functools import wraps
    
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        # Superusers always have access
        if request.user.is_superuser or request.user.has_perm('integrations.can_manage_integrations'):
            return view_func(request, *args, **kwargs)
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    
    return wrapper


# ============================================================================
# Integration Hub Dashboard
# ============================================================================

@integration_permission_required
def integration_hub(request):
    """
    Main Integration Hub dashboard.
    
    Shows:
    - Overview of connected integrations
    - Health status summary
    - Quick actions
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    # Get connections for this brand
    connections = IntegrationConnection.objects.filter(
        brand=brand,
    ).select_related('provider').order_by('-created_at')
    
    # Health summary
    health_summary = {
        'total': connections.count(),
        'healthy': connections.filter(health_status='HEALTHY').count(),
        'degraded': connections.filter(health_status='DEGRADED').count(),
        'unhealthy': connections.filter(health_status='UNHEALTHY').count(),
        'active': connections.filter(status='ACTIVE').count(),
    }
    
    # Recent sync logs
    recent_syncs = IntegrationSyncLog.objects.filter(
        connection__brand=brand,
    ).select_related('connection', 'connection__provider').order_by('-started_at')[:10]
    
    # Available providers not yet connected
    connected_provider_ids = connections.values_list('provider_id', flat=True)
    available_providers = IntegrationProvider.objects.filter(
        is_active=True,
    ).exclude(
        id__in=connected_provider_ids
    ).order_by('category', 'name')
    
    context = {
        'connections': connections,
        'health_summary': health_summary,
        'recent_syncs': recent_syncs,
        'available_providers': available_providers,
        'page_title': 'Integration Hub',
    }
    
    return render(request, 'integrations/hub.html', context)


@integration_permission_required
def marketplace(request):
    """
    Integration marketplace - browse and connect new integrations.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    # Get all providers grouped by category
    providers = IntegrationProvider.objects.filter(
        is_active=True,
    ).order_by('category', 'name')
    
    # Get connected providers for this brand
    connected_ids = set(
        IntegrationConnection.objects.filter(brand=brand).values_list('provider_id', flat=True)
    )
    
    # Group by category
    categories = {}
    category_names = dict(IntegrationProvider.CATEGORY_CHOICES)
    
    for provider in providers:
        category = provider.category
        if category not in categories:
            categories[category] = {
                'name': category_names.get(category, category),
                'providers': [],
            }
        
        provider.is_connected = provider.id in connected_ids
        categories[category]['providers'].append(provider)
    
    context = {
        'categories': categories,
        'page_title': 'Integration Marketplace',
    }
    
    return render(request, 'integrations/marketplace.html', context)


# ============================================================================
# Provider Connection
# ============================================================================

@integration_permission_required
def provider_detail(request, provider_slug):
    provider = get_object_or_404(IntegrationProvider, slug=provider_slug, is_active=True)

    brand = _get_current_brand(request)
    connection = None
    sync_logs = []

    if brand:
        connection = IntegrationConnection.objects.filter(
            brand=brand,
            provider=provider,
        ).first()

        if connection:
            sync_logs = IntegrationSyncLog.objects.filter(
                connection=connection
            ).order_by('-started_at')[:10]

    context = {
        'provider': provider,
        'connection': connection,
        'sync_logs': sync_logs,
        'page_title': provider.name,
    }
    return render(request, 'integrations/provider_detail.html', context)


@integration_permission_required
@require_POST
def connect_provider(request, provider_slug):
    """
    Initiate connection to a provider.
    
    For OAuth providers, redirects to authorization URL.
    For API key providers, processes the form submission.
    """
   # brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    brand = _get_active_brand_for_request(request)
    
    provider = get_object_or_404(IntegrationProvider, slug=provider_slug, is_active=True)
    
    if provider.auth_type == 'OAUTH2':
        return _initiate_oauth(request, provider, brand)
    elif provider.auth_type == 'API_KEY':
        return _connect_api_key(request, provider, brand)
    elif provider.auth_type == 'BASIC':
        return _connect_basic_auth(request, provider, brand)
    else:
        messages.error(request, f"Unsupported authentication type: {provider.auth_type}")
       # return redirect('integrations:provider_detail', provider_slug=provider_slug)
        return _connect_api_key(request, provider, brand)


def _initiate_oauth(request, provider, brand):
    """Start OAuth 2.0 authorization flow."""
    client_id = request.POST.get('client_id') or provider.default_settings.get('client_id')
    client_secret = request.POST.get('client_secret') or provider.default_settings.get('client_secret')
    
    if not client_id:
        messages.error(request, "Client ID is required for OAuth connection")
        return redirect('integrations:provider_detail', provider_slug=provider.slug)
    
    # Build redirect URI
    redirect_uri = request.build_absolute_uri(
        reverse('integrations:oauth_callback', kwargs={'provider_slug': provider.slug})
    )
    
    # Get connector class for provider-specific OAuth handling
    connector_class = _get_connector_class(provider.slug)
    
    try:
        if connector_class and hasattr(connector_class, 'get_authorization_url'):
            auth_url, state, code_verifier = connector_class.get_authorization_url(
                provider=provider,
                client_id=client_id,
                redirect_uri=redirect_uri,
                use_pkce=True,
            )
        else:
            auth_url, state, code_verifier = OAuthMixin.get_authorization_url(
                OAuthMixin,
                provider=provider,
                client_id=client_id,
                redirect_uri=redirect_uri,
                use_pkce=True,
            )
        
        # Store state in session
        handler = OAuthCallbackHandler()
        handler.store_state(
            request,
            provider.slug,
            state,
            code_verifier,
            extra_data={
                'client_id': client_id,
                'client_secret': client_secret,
                'brand_id': brand.id if brand else None,
            }
        )
        
        return redirect(auth_url)
        
    except Exception as e:
        logger.exception(f"Failed to initiate OAuth for {provider.slug}")
        messages.error(request, f"Failed to start authorization: {e}")
        return redirect('integrations:provider_detail', provider_slug=provider.slug)


def _connect_api_key(request, provider, brand):
    """
    Create connection with API-key-like authentication.

    NOTE: WhatsApp Cloud API is NOT an api_key. It uses:
      - access_token (Bearer token)
      - phone_number_id (required)
      - optional waba_id
    We store those on IntegrationConnection fields/config.
    """
    # Generic fields
    api_key = (request.POST.get('api_key') or '').strip()
    base_url = (request.POST.get('base_url') or '').strip()

    # WhatsApp-specific fields
    access_token = (request.POST.get('access_token') or '').strip()
    phone_number_id = (request.POST.get('phone_number_id') or '').strip()
    waba_id = (request.POST.get('waba_id') or '').strip()

    # Set default base_url per provider slug (provider model has no base_url)
    DEFAULT_BASE_URLS = {
        "whatsapp": "https://graph.facebook.com/v18.0",
        "facebook": "https://graph.facebook.com/v18.0",
        "instagram": "https://graph.facebook.com/v18.0",
    }
    if not base_url:
        base_url = DEFAULT_BASE_URLS.get(provider.slug, "")

    # Validation rules
    if provider.slug == "whatsapp":
        if not access_token:
            messages.error(request, "Access token is required for WhatsApp Cloud API.")
            return redirect('integrations:provider_detail', provider_slug=provider.slug)
        if not phone_number_id:
            messages.error(request, "Phone Number ID is required for WhatsApp Cloud API.")
            return redirect('integrations:provider_detail', provider_slug=provider.slug)

        # api_key is NOT used by WhatsApp but DB may require it; store a harmless placeholder.
        # (Alternative is changing the model to null=True, but this avoids migrations tonight.)
        if not api_key:
            api_key = "WHATSAPP_TOKEN"

        defaults = {
            'api_key': api_key,
            'access_token': access_token,
            'base_url': base_url,
            'status': 'ACTIVE',
            'health_status': 'UNKNOWN',
            'connected_at': timezone.now(),
            'config': {
                "phone_number_id": phone_number_id,
                **({"waba_id": waba_id} if waba_id else {}),
            }
        }
    else:
        # Generic API_KEY providers
        if not api_key:
            messages.error(request, "API key is required")
            return redirect('integrations:provider_detail', provider_slug=provider.slug)

        defaults = {
            'api_key': api_key,
            'base_url': base_url,
            'status': 'ACTIVE',
            'health_status': 'UNKNOWN',
            'connected_at': timezone.now(),
        }

    # Create or update connection
    connection, created = IntegrationConnection.objects.update_or_create(
        brand=brand,
        provider=provider,
        defaults=defaults
    )

    # Test the connection (if connector supports it)
    connector = _get_connector_instance(connection)
    if connector:
        try:
            # Some connectors use test_connection, others use check_health
            if hasattr(connector, "test_connection"):
                success, msg = connector.test_connection()
                if success:
                    connection.health_status = 'HEALTHY'
                    connection.status_message = msg
                    messages.success(request, f"Successfully connected to {provider.name}")
                else:
                    connection.health_status = 'UNHEALTHY'
                    connection.status_message = msg
                    messages.warning(request, f"Connected but verification failed: {msg}")
            else:
                health = connector.check_health()
                if health.get("healthy"):
                    connection.health_status = "HEALTHY"
                    connection.status_message = health.get("message", "OK")
                    messages.success(request, f"Successfully connected to {provider.name}")
                else:
                    connection.health_status = "UNHEALTHY"
                    connection.status_message = health.get("message", "Unhealthy")
                    messages.warning(request, f"Connected but verification failed: {connection.status_message}")

            connection.save(update_fields=['health_status', 'status_message'])
        except Exception as e:
            messages.warning(request, f"Connected, but health check failed: {str(e)}")
    else:
        messages.success(request, f"Connected to {provider.name}")

    return redirect('integrations:provider_detail', provider_slug=provider.slug)

def _connect_basic_auth(request, provider, brand):
    username = (request.POST.get("username") or "").strip()
    password = (request.POST.get("password") or "").strip()
    base_url = (request.POST.get("base_url") or "").strip()

    if not brand:
        messages.error(request, "No brand selected. Please select a brand/tenant before connecting.")
        return redirect("integrations:provider_detail", provider_slug=provider.slug)

    if not base_url:
        base_url = ""  # or a DEFAULT_BASE_URLS dict like in _connect_api_key

    if not username or not password:
        messages.error(request, "Username and password are required")
        return redirect("integrations:provider_detail", provider_slug=provider.slug)

    connection, created = IntegrationConnection.objects.update_or_create(
        brand=brand,
        provider=provider,
        defaults={
            "base_url": base_url,
            "api_key": username,     # or store in config if you prefer
            "api_secret": password,  # encrypted field exists
            "status": "ACTIVE",
            "health_status": "UNKNOWN",
            "connected_at": timezone.now(),
        },
    )

    connector = _get_connector_instance(connection)
    if connector:
        health = connector.check_health() or {}
        if health.get("healthy"):
            connection.health_status = "HEALTHY"
            messages.success(request, f"Successfully connected to {provider.name}")
        else:
            connection.health_status = "UNHEALTHY"
            messages.warning(request, f"Connected but verification failed: {health.get('message','')}")
        connection.save(update_fields=["health_status"])
    else:
        messages.success(request, f"Connected to {provider.name}")

    return redirect("integrations:provider_detail", provider_slug=provider.slug)


@login_required
def oauth_callback(request, provider_slug):
    """
    OAuth callback handler.
    
    Processes the authorization response and creates/updates the connection.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    provider = get_object_or_404(IntegrationProvider, slug=provider_slug, is_active=True)
    
    # Check for error
    error = request.GET.get('error')
    if error:
        error_desc = request.GET.get('error_description', 'Authorization failed')
        messages.error(request, f"Authorization failed: {error_desc}")
        return redirect('integrations:provider_detail', provider_slug=provider_slug)
    
    # Process callback
    handler = OAuthCallbackHandler()
    connector_class = _get_connector_class(provider.slug)
    
    try:
        # Verify state
        state = request.GET.get('state')
        is_valid, code_verifier, extra_data = handler.verify_state(request, provider_slug, state)
        
        if not is_valid:
            messages.error(request, "Invalid state parameter - please try again")
            return redirect('integrations:provider_detail', provider_slug=provider_slug)
        
        # Get credentials from extra_data
        client_id = extra_data.get('client_id')
        client_secret = extra_data.get('client_secret')
        
        # Build redirect URI
        redirect_uri = request.build_absolute_uri(
            reverse('integrations:oauth_callback', kwargs={'provider_slug': provider.slug})
        )
        
        # Exchange code for tokens
        code = request.GET.get('code')
        
        if connector_class and hasattr(connector_class, 'exchange_authorization_code'):
            token_data = connector_class.exchange_authorization_code(
                provider, code, client_id, client_secret, redirect_uri, code_verifier
            )
        else:
            token_data = OAuthMixin.exchange_authorization_code(
                OAuthMixin, provider, code, client_id, client_secret, redirect_uri, code_verifier
            )
        
        # Create or update connection
        connection, created = IntegrationConnection.objects.update_or_create(
            brand=brand,
            provider=provider,
            defaults={
                'client_id': client_id,
                'client_secret': client_secret,
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'token_expires_at': timezone.now() + timedelta(
                    seconds=int(token_data.get('expires_in', 3600))
                ),
                'status': 'ACTIVE',
                'health_status': 'HEALTHY',
                'status_message': 'Connected successfully',
                'connected_at': timezone.now(),
            }
        )
        
        # Test connection
        connector = _get_connector_instance(connection)
        if connector:
            success, message = connector.test_connection()
            connection.status_message = message
            connection.save(update_fields=['status_message'])
        
        messages.success(request, f"Successfully connected to {provider.name}")
        
    except OAuthError as e:
        logger.error(f"OAuth error for {provider_slug}: {e}")
        messages.error(request, f"Authorization failed: {e}")
    except Exception as e:
        logger.exception(f"Failed to complete OAuth for {provider_slug}")
        messages.error(request, f"Failed to complete authorization: {e}")
    
    return redirect('integrations:provider_detail', provider_slug=provider_slug)


@integration_permission_required
@require_POST
def disconnect_provider(request, provider_slug):
    """Disconnect (deactivate) an integration."""
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    connection = get_object_or_404(
        IntegrationConnection,
        brand=brand,
        provider__slug=provider_slug,
    )
    
    # Revoke tokens if OAuth
    if connection.provider.auth_type == 'OAUTH2':
        connector = _get_connector_instance(connection)
        if connector and hasattr(connector, 'revoke_token'):
            try:
                connector.revoke_token()
            except Exception as e:
                logger.warning(f"Failed to revoke token: {e}")
    
    # Deactivate connection
    connection.status = 'DISCONNECTED'
    connection.access_token = None
    connection.refresh_token = None
    connection.api_key = None
    connection.health_status = 'UNKNOWN'
    connection.status_message = 'Disconnected'
    connection.disconnected_at = timezone.now()
    connection.save()
    
    messages.success(request, f"Disconnected from {connection.provider.name}")
    return redirect('integrations:hub')


# ============================================================================
# Connection Management
# ============================================================================

@integration_permission_required
def connection_detail(request, connection_id):
    """
    Connection detail and management page.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    connection = get_object_or_404(
        IntegrationConnection,
        id=connection_id,
        brand=brand,
    )
    
    # Get sync logs
    sync_logs = IntegrationSyncLog.objects.filter(
        connection=connection,
    ).order_by('-started_at')[:50]
    
    # Get webhooks
    webhooks = IntegrationWebhook.objects.filter(
        connection=connection,
    )
    
    context = {
        'connection': connection,
        'sync_logs': sync_logs,
        'webhooks': webhooks,
        'page_title': f'{connection.provider.name} Connection',
    }
    
    return render(request, 'integrations/connection_detail.html', context)


@integration_permission_required
@require_POST
def connection_sync(request, connection_id):
    """
    Trigger a sync for a connection.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    connection = get_object_or_404(
        IntegrationConnection,
        id=connection_id,
        brand=brand,
        status='ACTIVE',
    )
    
    entity_type = request.POST.get('entity_type')
    full_sync = request.POST.get('full_sync') == 'true'
    
    # Queue sync task
    sync_connection.delay(connection.id, entity_type=entity_type, full_sync=full_sync)
    
    messages.success(request, f"Sync started for {connection.provider.name}")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'queued'})
    
    return redirect('integrations:connection_detail', connection_id=connection_id)


@integration_permission_required
@require_POST
def connection_test(request, connection_id):
    """
    Test a connection.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    connection = get_object_or_404(
        IntegrationConnection,
        id=connection_id,
        brand=brand,
    )
    
    connector = _get_connector_instance(connection)
    if not connector:
        return JsonResponse({
            'success': False,
            'message': 'No connector available for this provider',
        })
    
    try:
        success, message = connector.test_connection()
        connector.update_health_status()
        
        return JsonResponse({
            'success': success,
            'message': message,
            'health_status': connection.health_status,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e),
        })


@integration_permission_required
@require_POST
def connection_settings(request, connection_id):
    """
    Update connection settings.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    connection = get_object_or_404(
        IntegrationConnection,
        id=connection_id,
        brand=brand,
    )
    
    # Update sync settings
    sync_enabled = request.POST.get('sync_enabled') == 'true'
    sync_frequency = request.POST.get('sync_frequency')
    
    connection.sync_enabled = sync_enabled
    if sync_frequency:
        connection.sync_frequency_minutes = int(sync_frequency)
    
    # Update base URL if provided
    base_url = request.POST.get('base_url')
    if base_url:
        connection.base_url = base_url
    
    connection.save()
    
    messages.success(request, "Settings updated")
    return redirect('integrations:connection_detail', connection_id=connection_id)


# ============================================================================
# Webhooks
# ============================================================================

@integration_permission_required
def webhook_list(request, connection_id):
    """
    List webhooks for a connection.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    connection = get_object_or_404(
        IntegrationConnection,
        id=connection_id,
        brand=brand,
    )
    
    webhooks = IntegrationWebhook.objects.filter(
        connection=connection,
    ).annotate(
        log_count=Count('logs'),
    )
    
    context = {
        'connection': connection,
        'webhooks': webhooks,
        'page_title': f'{connection.provider.name} Webhooks',
    }
    
    return render(request, 'integrations/webhook_list.html', context)


@integration_permission_required
@require_POST
def webhook_create(request, connection_id):
    """
    Create a new webhook endpoint.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    connection = get_object_or_404(
        IntegrationConnection,
        id=connection_id,
        brand=brand,
    )
    
    name = request.POST.get('name', f'{connection.provider.name} Webhook')
    event_types = request.POST.getlist('event_types')
    
    # Generate secret
    webhook_secret = secrets.token_urlsafe(32)
    
    webhook = IntegrationWebhook.objects.create(
        connection=connection,
        name=name,
        secret_key=webhook_secret,
        event_types=event_types or [],
        is_active=True,
    )
    
    # Build webhook URL using the webhook's UUID
    webhook_url = request.build_absolute_uri(
        reverse('integrations:webhook_receive', kwargs={'webhook_id': str(webhook.id)})
    )
    
    messages.success(request, f"Webhook created. URL: {webhook_url}")
    return redirect('integrations:webhook_list', connection_id=connection_id)


@csrf_exempt
@require_POST
def webhook_receive(request, webhook_id):
    """
    Receive incoming webhook events.
    
    This endpoint:
    1. Validates the webhook exists and is active
    2. Verifies the request (signature, IP allowlist)
    3. Logs the event
    4. Queues for async processing
    """
    try:
        webhook = IntegrationWebhook.objects.select_related(
            'connection', 'connection__provider'
        ).get(id=webhook_id)
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
        logger.warning(f"Webhook verification failed for {webhook_id}: {e}")
        return JsonResponse({'error': 'Verification failed'}, status=403)
    
    # Parse payload
    payload = handler.parse_payload(request)
    event_type = payload.get('event', payload.get('type', 'unknown'))
    
    # Check event subscription
    if not handler.is_event_subscribed(event_type):
        handler.create_log(request, event_type=event_type)
        handler.complete_log(status='IGNORED', error_message='Event type not subscribed')
        return JsonResponse({'status': 'ignored'})
    
    # Create log
    log = handler.create_log(request, event_type=event_type)
    
    # Queue for async processing
    from integrations.tasks import process_webhook_event
    process_webhook_event.delay(log.id)
    
    return JsonResponse({'status': 'accepted'})


@integration_permission_required
def webhook_logs(request, webhook_id):
    """
    View webhook logs.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    webhook = get_object_or_404(
        IntegrationWebhook,
        id=webhook_id,
        connection__brand=brand,
    )
    
    logs = IntegrationWebhookLog.objects.filter(
        webhook=webhook,
    ).order_by('-received_at')
    
    paginator = Paginator(logs, 50)
    page = request.GET.get('page', 1)
    logs_page = paginator.get_page(page)
    
    context = {
        'webhook': webhook,
        'logs': logs_page,
        'page_title': f'{webhook.name} Logs',
    }
    
    return render(request, 'integrations/webhook_logs.html', context)


# ============================================================================
# Sync Logs
# ============================================================================

@integration_permission_required
def sync_logs(request, connection_id=None):
    """
    View sync logs for a connection or all connections.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    logs_query = IntegrationSyncLog.objects.filter(
        connection__brand=brand,
    ).select_related('connection', 'connection__provider')
    
    if connection_id:
        logs_query = logs_query.filter(connection_id=connection_id)
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        logs_query = logs_query.filter(status=status)
    
    logs = logs_query.order_by('-started_at')
    
    paginator = Paginator(logs, 50)
    page = request.GET.get('page', 1)
    logs_page = paginator.get_page(page)
    
    context = {
        'logs': logs_page,
        'selected_status': status,
        'page_title': 'Sync Logs',
    }
    
    return render(request, 'integrations/sync_logs.html', context)


# ============================================================================
# API Endpoints (for AJAX)
# ============================================================================

@integration_permission_required
@require_GET
def api_connections(request):
    """
    API: List connections with status.
    """
    brand = request.user.profile.brand if hasattr(request.user, 'profile') else None
    
    connections = IntegrationConnection.objects.filter(
        brand=brand,
    ).select_related('provider')
    
    data = [
        {
            'id': c.id,
            'provider': c.provider.name,
            'provider_slug': c.provider.slug,
            'status': c.status,
            'health_status': c.health_status,
            'status_message': c.status_message,
            'last_sync': c.last_sync_at.isoformat() if c.last_sync_at else None,
        }
        for c in connections
    ]
    
    return JsonResponse({'connections': data})


@integration_permission_required
@require_GET
def api_health_check(request):
    """
    API: Run health check on all connections.
    """
    check_connections_health.delay()
    return JsonResponse({'status': 'queued'})


# ============================================================================
# Helper Functions
# ============================================================================

def _get_connector_class(provider_slug: str):
    """
    Return connector class for a provider slug.
    """
    connector_map = {
        "microsoft365": "integrations.connectors.microsoft365.MicrosoftGraphConnector",
        "whatsapp": "integrations.connectors.whatsapp.WhatsAppConnector",
    }

    import_path = connector_map.get(provider_slug)
    if not import_path:
        return None

    try:
        module_path, class_name = import_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
    except Exception:
        logger.exception(f"Failed to import connector for provider {provider_slug}")
        return None

def _get_connector_instance(connection):
    """Get connector instance for a connection."""
    connector_class = _get_connector_class(connection.provider.slug)
    if connector_class:
        return connector_class(connection)
    return None
