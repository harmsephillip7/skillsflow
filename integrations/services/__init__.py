"""
Integration Services Package

Provides base classes and utilities for integration connectors:
- BaseIntegrationClient: Core HTTP client with retry and rate limiting
- OAuthMixin: OAuth 2.0 authentication support
- WebhookHandler: Webhook verification and processing
"""

from integrations.services.base import (
    BaseIntegrationClient,
    IntegrationError,
    AuthenticationError,
    RateLimitError,
    APIError,
    ConnectionError,
)

from integrations.services.oauth import (
    OAuthMixin,
    OAuthCallbackHandler,
    OAuthError,
)

from integrations.services.webhooks import (
    WebhookHandler,
    WebhookDispatcher,
    WebhookVerificationError,
    webhook_endpoint,
)

__all__ = [
    # Base client
    'BaseIntegrationClient',
    'IntegrationError',
    'AuthenticationError',
    'RateLimitError',
    'APIError',
    'ConnectionError',
    
    # OAuth
    'OAuthMixin',
    'OAuthCallbackHandler',
    'OAuthError',
    
    # Webhooks
    'WebhookHandler',
    'WebhookDispatcher',
    'WebhookVerificationError',
    'webhook_endpoint',
]
