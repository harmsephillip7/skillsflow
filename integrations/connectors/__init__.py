"""
Integration Connectors Package

Provider-specific connector implementations:
- Microsoft365Connector: Microsoft Graph API (Teams, SharePoint, Outlook, OneDrive)
- MicrosoftGraphConnector: Microsoft Graph API for email operations
- MetaConnector: Meta Cloud API base (WhatsApp, Facebook, Instagram)
- MetaAnalyticsConnector: Meta Graph API for analytics data
- WhatsAppConnector: WhatsApp Business Cloud API
- FacebookConnector: Facebook Messenger
- InstagramConnector: Instagram Direct Messages
- TikTokConnector: TikTok Business API for analytics
- GoogleAnalyticsConnector: GA4 Data API for web traffic
- BulkSMSConnector: BulkSMS gateway
- ClickatellConnector: Clickatell gateway
"""

from integrations.connectors.base import (
    BaseConnector,
    ConnectorError,
    RateLimitError,
    AuthenticationError,
    MessageResult,
    MessageStatus,
    InboundMessage,
    Contact,
)

from integrations.connectors.meta import (
    MetaConnector,
    MetaAnalyticsConnector,
    WhatsAppConnector,
    FacebookConnector,
    InstagramConnector,
)

from integrations.connectors.tiktok import TikTokConnector

from integrations.connectors.google_analytics import GoogleAnalyticsConnector

from integrations.connectors.sms import (
    BulkSMSConnector,
    ClickatellConnector,
    get_sms_connector,
)

from integrations.connectors.microsoft import (
    MicrosoftGraphConnector,
    EmailSyncService,
)


# Keep legacy import for backwards compatibility
try:
    from integrations.connectors.microsoft365 import Microsoft365Connector
except ImportError:
    Microsoft365Connector = None

__all__ = [
    # Base
    'BaseConnector',
    'ConnectorError',
    'RateLimitError',
    'AuthenticationError',
    'MessageResult',
    'MessageStatus',
    'InboundMessage',
    'Contact',
    # Meta
    'MetaConnector',
    'MetaAnalyticsConnector',
    'WhatsAppConnector',
    'FacebookConnector',
    'InstagramConnector',
    # TikTok
    'TikTokConnector',
    # Google Analytics
    'GoogleAnalyticsConnector',
    # SMS
    'BulkSMSConnector',
    'ClickatellConnector',
    'get_sms_connector',
    # Microsoft
    'MicrosoftGraphConnector',
    'EmailSyncService',
    'Microsoft365Connector',
]
