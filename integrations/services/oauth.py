"""
OAuth Service Mixin

Provides OAuth 2.0 authentication flow support:
- Authorization URL generation
- Authorization code exchange
- Token refresh
- Token validation
"""

import secrets
import hashlib
import base64
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from django.utils import timezone
from django.conf import settings

from integrations.models import IntegrationConnection, IntegrationProvider

logger = logging.getLogger(__name__)


class OAuthError(Exception):
    """Exception for OAuth-related errors."""
    pass


class OAuthMixin:
    """
    Mixin class providing OAuth 2.0 functionality for integration clients.
    
    Supports:
    - OAuth 2.0 Authorization Code flow
    - OAuth 2.0 Authorization Code with PKCE
    - Token refresh
    - State and PKCE verifier generation
    
    Usage:
        class MyConnector(OAuthMixin, BaseIntegrationClient):
            ...
    """
    
    # OAuth endpoints - override in subclass if different from provider defaults
    OAUTH_AUTHORIZE_URL: str = None
    OAUTH_TOKEN_URL: str = None
    OAUTH_REVOKE_URL: str = None
    
    # Default scopes - override in subclass
    DEFAULT_SCOPES: list = []
    
    # Token refresh buffer (refresh this many seconds before expiry)
    TOKEN_REFRESH_BUFFER = 300  # 5 minutes
    
    @classmethod
    def get_authorization_url(
        cls,
        provider: IntegrationProvider,
        client_id: str,
        redirect_uri: str,
        scopes: list = None,
        state: str = None,
        extra_params: dict = None,
        use_pkce: bool = False,
    ) -> Tuple[str, str, Optional[str]]:
        """
        Generate the OAuth authorization URL.
        
        Args:
            provider: IntegrationProvider instance
            client_id: OAuth client ID
            redirect_uri: Callback URL after authorization
            scopes: List of scopes to request (defaults to provider's default scopes)
            state: Optional state parameter (generated if not provided)
            extra_params: Additional query parameters for the auth URL
            use_pkce: Whether to use PKCE (generates code_verifier)
            
        Returns:
            Tuple of (authorization_url, state, code_verifier or None)
        """
        # Use provider's OAuth URL or class default
        authorize_url = provider.oauth_authorization_url or cls.OAUTH_AUTHORIZE_URL
        if not authorize_url:
            raise OAuthError(f"No authorization URL configured for {provider.name}")
        
        # Generate state for CSRF protection
        if not state:
            state = secrets.token_urlsafe(32)
        
        # Build scopes
        if scopes is None:
            scopes = provider.default_scopes or cls.DEFAULT_SCOPES
        scope_string = ' '.join(scopes) if isinstance(scopes, list) else scopes
        
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'state': state,
            'scope': scope_string,
        }
        
        # PKCE support
        code_verifier = None
        if use_pkce:
            code_verifier = secrets.token_urlsafe(64)
            code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).decode().rstrip('=')
            params['code_challenge'] = code_challenge
            params['code_challenge_method'] = 'S256'
        
        # Add extra params
        if extra_params:
            params.update(extra_params)
        
        # Build URL
        auth_url = f"{authorize_url}?{urlencode(params)}"
        
        return auth_url, state, code_verifier
    
    @classmethod
    def exchange_authorization_code(
        cls,
        provider: IntegrationProvider,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        code_verifier: str = None,
    ) -> Dict:
        """
        Exchange authorization code for tokens.
        
        Args:
            provider: IntegrationProvider instance
            code: Authorization code from callback
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Same redirect URI used in authorization
            code_verifier: PKCE code verifier (if PKCE was used)
            
        Returns:
            Dict with access_token, refresh_token, expires_in, etc.
            
        Raises:
            OAuthError: If token exchange fails
        """
        token_url = provider.oauth_token_url or cls.OAUTH_TOKEN_URL
        if not token_url:
            raise OAuthError(f"No token URL configured for {provider.name}")
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
        }
        
        if code_verifier:
            data['code_verifier'] = code_verifier
        
        try:
            response = requests.post(
                token_url,
                data=data,
                headers={'Accept': 'application/json'},
                timeout=30,
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('error_description', error_data.get('error', response.text))
                raise OAuthError(f"Token exchange failed: {error_msg}")
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise OAuthError(f"Token exchange request failed: {e}")
    
    def refresh_access_token(self) -> Dict:
        """
        Refresh the access token using the refresh token.
        
        Returns:
            Dict with new access_token, refresh_token (optional), expires_in, etc.
            
        Raises:
            OAuthError: If refresh fails
        """
        if not self.connection.refresh_token:
            raise OAuthError("No refresh token available")
        
        token_url = self.provider.oauth_token_url or self.OAUTH_TOKEN_URL
        if not token_url:
            raise OAuthError(f"No token URL configured for {self.provider.name}")
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.connection.refresh_token,
            'client_id': self.connection.client_id,
            'client_secret': self.connection.client_secret,
        }
        
        try:
            response = requests.post(
                token_url,
                data=data,
                headers={'Accept': 'application/json'},
                timeout=30,
            )
            
            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('error_description', error_data.get('error', response.text))
                
                # Mark connection as needing reauthorization
                self.connection.health_status = 'UNHEALTHY'
                self.connection.status_message = f'Token refresh failed: {error_msg}'
                self.connection.save(update_fields=['health_status', 'status_message'])
                
                raise OAuthError(f"Token refresh failed: {error_msg}")
            
            token_data = response.json()
            
            # Update connection with new tokens
            self._update_tokens(token_data)
            
            return token_data
            
        except requests.exceptions.RequestException as e:
            raise OAuthError(f"Token refresh request failed: {e}")
    
    def _update_tokens(self, token_data: Dict) -> None:
        """
        Update connection with new token data.
        
        Args:
            token_data: Response from token endpoint
        """
        self.connection.access_token = token_data.get('access_token')
        
        # Some providers return new refresh token
        if 'refresh_token' in token_data:
            self.connection.refresh_token = token_data['refresh_token']
        
        # Calculate expiry
        expires_in = token_data.get('expires_in')
        if expires_in:
            self.connection.token_expires_at = timezone.now() + timedelta(seconds=int(expires_in))
        
        # Store additional token data
        if not self.connection.settings:
            self.connection.settings = {}
        self.connection.settings['token_type'] = token_data.get('token_type', 'Bearer')
        self.connection.settings['scope'] = token_data.get('scope', '')
        
        self.connection.save(update_fields=[
            'access_token', 'refresh_token', 'token_expires_at', 'settings'
        ])
        
        logger.info(f"Updated tokens for connection {self.connection.id}")
    
    def ensure_valid_token(self) -> bool:
        """
        Ensure the access token is valid, refreshing if necessary.
        
        Returns:
            True if token is valid (or was successfully refreshed)
            
        Raises:
            OAuthError: If token cannot be refreshed
        """
        if self.connection.is_token_valid:
            # Check if refresh is needed soon
            if self.connection.token_expires_at:
                time_until_expiry = (self.connection.token_expires_at - timezone.now()).total_seconds()
                if time_until_expiry > self.TOKEN_REFRESH_BUFFER:
                    return True
        
        # Token expired or expiring soon - refresh
        if self.connection.refresh_token:
            logger.info(f"Refreshing token for connection {self.connection.id}")
            self.refresh_access_token()
            return True
        else:
            raise OAuthError("Token expired and no refresh token available")
    
    def revoke_token(self) -> bool:
        """
        Revoke the current access and refresh tokens.
        
        Returns:
            True if successfully revoked
        """
        revoke_url = self.provider.oauth_revoke_url or self.OAUTH_REVOKE_URL
        if not revoke_url:
            logger.warning(f"No revoke URL configured for {self.provider.name}")
            return False
        
        try:
            # Revoke access token
            if self.connection.access_token:
                response = requests.post(
                    revoke_url,
                    data={
                        'token': self.connection.access_token,
                        'token_type_hint': 'access_token',
                        'client_id': self.connection.client_id,
                        'client_secret': self.connection.client_secret,
                    },
                    timeout=30,
                )
            
            # Revoke refresh token
            if self.connection.refresh_token:
                response = requests.post(
                    revoke_url,
                    data={
                        'token': self.connection.refresh_token,
                        'token_type_hint': 'refresh_token',
                        'client_id': self.connection.client_id,
                        'client_secret': self.connection.client_secret,
                    },
                    timeout=30,
                )
            
            # Clear tokens from connection
            self.connection.access_token = None
            self.connection.refresh_token = None
            self.connection.token_expires_at = None
            self.connection.is_active = False
            self.connection.save()
            
            logger.info(f"Revoked tokens for connection {self.connection.id}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Token revocation failed: {e}")
            return False


class OAuthCallbackHandler:
    """
    Handler for processing OAuth callbacks.
    
    Usage in views:
        handler = OAuthCallbackHandler()
        connection = handler.process_callback(request, provider, brand)
    """
    
    def __init__(self, session_key_prefix: str = 'oauth'):
        """
        Initialize the callback handler.
        
        Args:
            session_key_prefix: Prefix for session keys storing OAuth state
        """
        self.session_prefix = session_key_prefix
    
    def store_state(
        self,
        request,
        provider_slug: str,
        state: str,
        code_verifier: str = None,
        extra_data: dict = None,
    ) -> None:
        """
        Store OAuth state in session for callback verification.
        
        Args:
            request: Django request object
            provider_slug: Provider identifier
            state: State parameter
            code_verifier: PKCE verifier (if used)
            extra_data: Additional data to store
        """
        key = f"{self.session_prefix}_{provider_slug}"
        request.session[key] = {
            'state': state,
            'code_verifier': code_verifier,
            'created_at': timezone.now().isoformat(),
            'extra': extra_data or {},
        }
        request.session.modified = True
    
    def verify_state(self, request, provider_slug: str, state: str) -> Tuple[bool, Optional[str], dict]:
        """
        Verify the state parameter from callback.
        
        Args:
            request: Django request object
            provider_slug: Provider identifier
            state: State parameter from callback
            
        Returns:
            Tuple of (is_valid, code_verifier, extra_data)
        """
        key = f"{self.session_prefix}_{provider_slug}"
        stored = request.session.get(key)
        
        if not stored:
            return False, None, {}
        
        if stored.get('state') != state:
            return False, None, {}
        
        # Clean up session
        del request.session[key]
        request.session.modified = True
        
        return True, stored.get('code_verifier'), stored.get('extra', {})
    
    def process_callback(
        self,
        request,
        provider: IntegrationProvider,
        brand,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        connector_class=None,
    ) -> IntegrationConnection:
        """
        Process OAuth callback and create/update connection.
        
        Args:
            request: Django request object
            provider: IntegrationProvider instance
            brand: Brand instance
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Redirect URI used in authorization
            connector_class: Optional connector class with custom OAuth handling
            
        Returns:
            IntegrationConnection instance
            
        Raises:
            OAuthError: If callback processing fails
        """
        # Check for error in callback
        error = request.GET.get('error')
        if error:
            error_desc = request.GET.get('error_description', 'Unknown error')
            raise OAuthError(f"OAuth error: {error} - {error_desc}")
        
        # Get authorization code
        code = request.GET.get('code')
        if not code:
            raise OAuthError("No authorization code in callback")
        
        # Verify state
        state = request.GET.get('state')
        if not state:
            raise OAuthError("No state parameter in callback")
        
        is_valid, code_verifier, extra_data = self.verify_state(
            request, provider.slug, state
        )
        if not is_valid:
            raise OAuthError("Invalid state parameter - possible CSRF attack")
        
        # Exchange code for tokens
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
                'token_expires_at': timezone.now() + timedelta(seconds=int(token_data.get('expires_in', 3600))),
                'is_active': True,
                'health_status': 'HEALTHY',
                'status_message': 'Connected successfully',
            }
        )
        
        # Store additional data
        if not connection.settings:
            connection.settings = {}
        connection.settings['token_type'] = token_data.get('token_type', 'Bearer')
        connection.settings['scope'] = token_data.get('scope', '')
        connection.settings.update(extra_data)
        connection.save(update_fields=['settings'])
        
        logger.info(f"{'Created' if created else 'Updated'} connection for {provider.name} - {brand.name}")
        
        return connection
