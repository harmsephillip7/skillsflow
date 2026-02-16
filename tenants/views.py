"""
Tenants Views

Views for managing tenant-level configurations including
brand social account integrations.
"""

import logging
import secrets
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST, require_GET
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView, DetailView, UpdateView

from tenants.models import Brand, Campus, BrandSocialAccount
from integrations.models import IntegrationProvider, IntegrationConnection

logger = logging.getLogger(__name__)


def _get_current_brand(request):
    """Get the current brand for the logged-in user."""
    try:
        profile = getattr(request.user, 'profile', None)
        if profile and getattr(profile, 'brand', None):
            return profile.brand
    except Exception:
        pass
    
    brand_id = request.session.get('brand_id')
    if brand_id:
        return Brand.objects.filter(id=brand_id, is_active=True).first()
    
    return Brand.objects.filter(is_active=True).first()


# ============================================================================
# BRAND SOCIAL ACCOUNT MANAGEMENT
# ============================================================================

@login_required
def brand_integrations(request, brand_id=None):
    """
    View and manage social media integrations for a brand.
    
    Shows all connected social accounts and allows adding new ones.
    """
    if brand_id:
        brand = get_object_or_404(Brand, id=brand_id, is_active=True)
    else:
        brand = _get_current_brand(request)
    
    if not brand:
        messages.warning(request, "No brand selected.")
        return redirect('admin:brand_list')
    
    # Get existing social accounts
    social_accounts = BrandSocialAccount.objects.filter(
        brand=brand
    ).select_related('connection', 'connection__provider')
    
    # Get available providers for connecting
    available_providers = IntegrationProvider.objects.filter(
        is_active=True,
        category='SOCIAL',
    )
    
    # Determine which platforms are already connected
    connected_platforms = set(social_accounts.values_list('platform', flat=True))
    
    context = {
        'brand': brand,
        'social_accounts': social_accounts,
        'available_providers': available_providers,
        'connected_platforms': connected_platforms,
        'page_title': f'Social Integrations - {brand.name}',
    }
    
    return render(request, 'tenants/brand_integrations.html', context)


@login_required
def brand_integration_detail(request, brand_id, account_id):
    """
    View details of a specific social account connection.
    """
    brand = get_object_or_404(Brand, id=brand_id, is_active=True)
    account = get_object_or_404(BrandSocialAccount, id=account_id, brand=brand)
    
    # Get recent sync data
    from crm.models import SocialMetricsSnapshot, WebTrafficSnapshot
    
    recent_metrics = None
    if account.platform == 'GOOGLE_ANALYTICS':
        recent_metrics = WebTrafficSnapshot.objects.filter(
            brand=brand
        ).order_by('-date')[:7]
    else:
        platform = 'FACEBOOK' if account.platform == 'META' else account.platform
        recent_metrics = SocialMetricsSnapshot.objects.filter(
            brand=brand,
            platform__in=['FACEBOOK', 'INSTAGRAM'] if account.platform == 'META' else [platform]
        ).order_by('-date')[:14]
    
    context = {
        'brand': brand,
        'account': account,
        'recent_metrics': recent_metrics,
        'page_title': f'{account.get_platform_display()} - {brand.name}',
    }
    
    return render(request, 'tenants/brand_integration_detail.html', context)


@login_required
@require_POST
def connect_social_account(request, brand_id):
    """
    Initiate OAuth connection for a social platform.
    
    Creates a BrandSocialAccount record and redirects to OAuth flow.
    """
    brand = get_object_or_404(Brand, id=brand_id, is_active=True)
    platform = request.POST.get('platform')
    
    if platform not in ['META', 'TIKTOK', 'GOOGLE_ANALYTICS']:
        messages.error(request, "Invalid platform selected.")
        return redirect('brand_integrations', brand_id=brand_id)
    
    # Map platform to provider slug
    provider_slugs = {
        'META': 'meta-business',
        'TIKTOK': 'tiktok-business',
        'GOOGLE_ANALYTICS': 'google-analytics',
    }
    
    provider_slug = provider_slugs.get(platform)
    
    try:
        provider = IntegrationProvider.objects.get(slug=provider_slug, is_active=True)
    except IntegrationProvider.DoesNotExist:
        messages.error(request, f"Provider not configured. Please contact your administrator.")
        return redirect('brand_integrations', brand_id=brand_id)
    
    # Check if already connected
    existing = BrandSocialAccount.objects.filter(brand=brand, platform=platform).first()
    if existing and existing.is_active:
        messages.warning(request, f"{existing.get_platform_display()} is already connected.")
        return redirect('brand_integrations', brand_id=brand_id)
    
    # Store state for OAuth callback
    state = secrets.token_urlsafe(32)
    request.session['oauth_state'] = state
    request.session['oauth_brand_id'] = str(brand_id)
    request.session['oauth_platform'] = platform
    
    # Build OAuth URL based on provider
    if platform == 'META':
        oauth_url = _build_meta_oauth_url(request, provider, state)
    elif platform == 'TIKTOK':
        oauth_url = _build_tiktok_oauth_url(request, provider, state)
    elif platform == 'GOOGLE_ANALYTICS':
        oauth_url = _build_google_oauth_url(request, provider, state)
    else:
        messages.error(request, "OAuth not configured for this platform.")
        return redirect('brand_integrations', brand_id=brand_id)
    
    return redirect(oauth_url)


def _build_meta_oauth_url(request, provider, state):
    """Build Meta OAuth authorization URL."""
    from urllib.parse import urlencode
    
    config = provider.config or {}
    client_id = config.get('client_id', '')
    
    redirect_uri = request.build_absolute_uri(reverse('social_oauth_callback'))
    
    # Scopes for analytics + messaging readiness
    scopes = [
        'pages_show_list',
        'pages_read_engagement',
        'pages_read_user_content',
        'instagram_basic',
        'instagram_manage_insights',
        'business_management',
    ]
    
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': ','.join(scopes),
        'response_type': 'code',
    }
    
    return f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"


def _build_tiktok_oauth_url(request, provider, state):
    """Build TikTok OAuth authorization URL."""
    from urllib.parse import urlencode
    
    config = provider.config or {}
    client_key = config.get('client_key', '')
    
    redirect_uri = request.build_absolute_uri(reverse('social_oauth_callback'))
    
    scopes = [
        'user.info.basic',
        'user.info.stats',
        'video.list',
    ]
    
    params = {
        'client_key': client_key,
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': ','.join(scopes),
        'response_type': 'code',
    }
    
    return f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"


def _build_google_oauth_url(request, provider, state):
    """Build Google OAuth authorization URL."""
    from urllib.parse import urlencode
    
    config = provider.config or {}
    client_id = config.get('client_id', '')
    
    redirect_uri = request.build_absolute_uri(reverse('social_oauth_callback'))
    
    scopes = [
        'https://www.googleapis.com/auth/analytics.readonly',
    ]
    
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': ' '.join(scopes),
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent',
    }
    
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


@login_required
def social_oauth_callback(request):
    """
    Handle OAuth callback for social platform connections.
    
    Exchanges authorization code for access token and creates
    the integration connection and brand social account.
    """
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f"OAuth failed: {request.GET.get('error_description', error)}")
        return redirect('integration_hub')
    
    # Verify state
    if state != request.session.get('oauth_state'):
        messages.error(request, "Invalid OAuth state. Please try again.")
        return redirect('integration_hub')
    
    brand_id = request.session.get('oauth_brand_id')
    platform = request.session.get('oauth_platform')
    
    if not brand_id or not platform:
        messages.error(request, "Session expired. Please try again.")
        return redirect('integration_hub')
    
    brand = get_object_or_404(Brand, id=brand_id)
    
    try:
        if platform == 'META':
            connection = _complete_meta_oauth(request, code, brand)
        elif platform == 'TIKTOK':
            connection = _complete_tiktok_oauth(request, code, brand)
        elif platform == 'GOOGLE_ANALYTICS':
            connection = _complete_google_oauth(request, code, brand)
        else:
            raise ValueError(f"Unknown platform: {platform}")
        
        # Create or update BrandSocialAccount
        account, created = BrandSocialAccount.objects.update_or_create(
            brand=brand,
            platform=platform,
            defaults={
                'connection': connection,
                'is_active': True,
                'has_analytics_permission': True,
            }
        )
        
        # Fetch account details if Meta
        if platform == 'META':
            _fetch_meta_account_details(account, connection)
        elif platform == 'GOOGLE_ANALYTICS':
            _fetch_ga4_properties(account, connection)
        
        messages.success(
            request,
            f"Successfully connected {account.get_platform_display()} for {brand.name}!"
        )
        
        # Clear session data
        request.session.pop('oauth_state', None)
        request.session.pop('oauth_brand_id', None)
        request.session.pop('oauth_platform', None)
        
        return redirect('brand_integrations', brand_id=brand_id)
        
    except Exception as e:
        logger.error(f"OAuth completion failed: {e}")
        messages.error(request, f"Failed to complete connection: {str(e)}")
        return redirect('brand_integrations', brand_id=brand_id)


def _complete_meta_oauth(request, code, brand):
    """Complete Meta OAuth and create connection."""
    import requests
    
    provider = IntegrationProvider.objects.get(slug='meta-business')
    config = provider.config or {}
    
    redirect_uri = request.build_absolute_uri(reverse('social_oauth_callback'))
    
    # Exchange code for short-lived token
    token_url = 'https://graph.facebook.com/v18.0/oauth/access_token'
    response = requests.get(token_url, params={
        'client_id': config.get('client_id'),
        'client_secret': config.get('client_secret'),
        'redirect_uri': redirect_uri,
        'code': code,
    })
    
    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.text}")
    
    data = response.json()
    short_token = data['access_token']
    
    # Exchange for long-lived token
    response = requests.get(token_url, params={
        'grant_type': 'fb_exchange_token',
        'client_id': config.get('client_id'),
        'client_secret': config.get('client_secret'),
        'fb_exchange_token': short_token,
    })
    
    if response.status_code != 200:
        raise Exception(f"Long-lived token exchange failed: {response.text}")
    
    data = response.json()
    
    # Create or update connection
    connection, _ = IntegrationConnection.objects.update_or_create(
        brand=brand,
        provider=provider,
        defaults={
            'status': 'ACTIVE',
            'access_token': data['access_token'],
            'token_expires_at': timezone.now() + timedelta(seconds=data.get('expires_in', 5184000)),
            'client_id': config.get('client_id'),
            'client_secret': config.get('client_secret'),
        }
    )
    
    return connection


def _complete_tiktok_oauth(request, code, brand):
    """Complete TikTok OAuth and create connection."""
    import requests
    
    provider = IntegrationProvider.objects.get(slug='tiktok-business')
    config = provider.config or {}
    
    redirect_uri = request.build_absolute_uri(reverse('social_oauth_callback'))
    
    # Exchange code for token
    token_url = 'https://open.tiktokapis.com/v2/oauth/token/'
    response = requests.post(token_url, json={
        'client_key': config.get('client_key'),
        'client_secret': config.get('client_secret'),
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
    })
    
    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.text}")
    
    data = response.json()
    if data.get('error', {}).get('code') != 'ok':
        raise Exception(f"TikTok error: {data.get('error', {}).get('message')}")
    
    token_data = data.get('data', {})
    
    # Create or update connection
    connection, _ = IntegrationConnection.objects.update_or_create(
        brand=brand,
        provider=provider,
        defaults={
            'status': 'ACTIVE',
            'access_token': token_data['access_token'],
            'refresh_token': token_data.get('refresh_token'),
            'token_expires_at': timezone.now() + timedelta(seconds=token_data.get('expires_in', 86400)),
            'client_id': config.get('client_key'),
            'client_secret': config.get('client_secret'),
        }
    )
    
    return connection


def _complete_google_oauth(request, code, brand):
    """Complete Google OAuth and create connection."""
    import requests
    
    provider = IntegrationProvider.objects.get(slug='google-analytics')
    config = provider.config or {}
    
    redirect_uri = request.build_absolute_uri(reverse('social_oauth_callback'))
    
    # Exchange code for tokens
    token_url = 'https://oauth2.googleapis.com/token'
    response = requests.post(token_url, data={
        'client_id': config.get('client_id'),
        'client_secret': config.get('client_secret'),
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
    })
    
    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.text}")
    
    data = response.json()
    
    # Create or update connection
    connection, _ = IntegrationConnection.objects.update_or_create(
        brand=brand,
        provider=provider,
        defaults={
            'status': 'ACTIVE',
            'access_token': data['access_token'],
            'refresh_token': data.get('refresh_token'),
            'token_expires_at': timezone.now() + timedelta(seconds=data.get('expires_in', 3600)),
            'client_id': config.get('client_id'),
            'client_secret': config.get('client_secret'),
        }
    )
    
    return connection


def _fetch_meta_account_details(account, connection):
    """Fetch Facebook Page and Instagram account details."""
    import requests
    
    headers = {'Authorization': f"Bearer {connection.access_token}"}
    
    # Get connected pages
    pages_url = 'https://graph.facebook.com/v18.0/me/accounts'
    response = requests.get(pages_url, headers=headers, params={
        'fields': 'id,name,access_token,instagram_business_account{id,username}'
    })
    
    if response.status_code == 200:
        pages = response.json().get('data', [])
        if pages:
            # Use first page (or could prompt user to select)
            page = pages[0]
            account.facebook_page_id = page['id']
            account.account_name = page.get('name', '')
            
            # Check for Instagram
            ig_account = page.get('instagram_business_account', {})
            if ig_account:
                account.instagram_business_id = ig_account.get('id')
            
            account.save()


def _fetch_ga4_properties(account, connection):
    """Prompt user to select GA4 property (or auto-detect)."""
    # For now, we'll require the user to enter the property ID manually
    # In a full implementation, you'd list available properties
    pass


@login_required
@require_POST
def update_social_account(request, brand_id, account_id):
    """Update social account settings."""
    brand = get_object_or_404(Brand, id=brand_id, is_active=True)
    account = get_object_or_404(BrandSocialAccount, id=account_id, brand=brand)
    
    # Update fields from form
    if 'facebook_page_id' in request.POST:
        account.facebook_page_id = request.POST.get('facebook_page_id', '').strip()
    if 'instagram_business_id' in request.POST:
        account.instagram_business_id = request.POST.get('instagram_business_id', '').strip()
    if 'tiktok_business_id' in request.POST:
        account.tiktok_business_id = request.POST.get('tiktok_business_id', '').strip()
    if 'ga4_property_id' in request.POST:
        account.ga4_property_id = request.POST.get('ga4_property_id', '').strip()
    if 'account_name' in request.POST:
        account.account_name = request.POST.get('account_name', '').strip()
    if 'is_active' in request.POST:
        account.is_active = request.POST.get('is_active') == 'true'
    
    account.save()
    
    messages.success(request, "Account settings updated.")
    return redirect('tenants:brand_integration_detail', brand_id=brand_id, account_id=account_id)


@login_required
@require_POST
def disconnect_social_account(request, brand_id, account_id):
    """Disconnect a social account."""
    brand = get_object_or_404(Brand, id=brand_id, is_active=True)
    account = get_object_or_404(BrandSocialAccount, id=account_id, brand=brand)
    
    account.is_active = False
    account.save()
    
    # Optionally also deactivate the connection
    if account.connection:
        account.connection.status = 'INACTIVE'
        account.connection.save()
    
    messages.success(request, f"Disconnected {account.get_platform_display()} from {brand.name}.")
    return redirect('tenants:brand_integrations', brand_id=brand_id)


@login_required
@require_POST
def trigger_sync(request, brand_id, account_id):
    """Manually trigger a sync for a social account."""
    brand = get_object_or_404(Brand, id=brand_id, is_active=True)
    account = get_object_or_404(BrandSocialAccount, id=account_id, brand=brand)
    
    from integrations.services.social_sync import SocialSyncService
    from datetime import date, timedelta
    
    # Sync last 7 days
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=6)
    
    service = SocialSyncService()
    result = service.sync_brand(brand, start_date, end_date)
    
    if result.get('success'):
        messages.success(
            request,
            f"Sync complete! Created {result.get('metrics_created', 0)} metric snapshots."
        )
    else:
        messages.warning(
            request,
            f"Sync completed with errors: {', '.join(result.get('errors', []))}"
        )
    
    return redirect('tenants:brand_integration_detail', brand_id=brand_id, account_id=account_id)


@login_required
@require_POST
def trigger_backfill(request, brand_id, account_id):
    """Trigger historical data backfill for a social account."""
    brand = get_object_or_404(Brand, id=brand_id, is_active=True)
    account = get_object_or_404(BrandSocialAccount, id=account_id, brand=brand)
    
    from integrations.services.social_sync import SocialSyncService
    
    service = SocialSyncService()
    result = service.backfill_brand(brand, account.platform)
    
    if result.get('success'):
        messages.success(
            request,
            f"Backfill complete! Processed {result.get('days_processed', 0)} days of data."
        )
    else:
        messages.warning(
            request,
            f"Backfill completed with errors: {', '.join(result.get('errors', []))}"
        )
    
    return redirect('tenants:brand_integration_detail', brand_id=brand_id, account_id=account_id)

