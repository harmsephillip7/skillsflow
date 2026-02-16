"""
Management command to seed Integration Providers.
Creates default providers for the Integration Hub.
"""

from django.core.management.base import BaseCommand
from integrations.models import IntegrationProvider


class Command(BaseCommand):
    help = 'Seed the database with default Integration Providers'

    def handle(self, *args, **options):
        providers = [
            # CRM Integrations
            {
                'slug': 'zoho-bigin',
                'name': 'Zoho Bigin',
                'description': 'Connect to Zoho Bigin CRM for pipeline management, contact sync, and deal tracking.',
                'icon_class': 'fas fa-address-book',
                'category': 'CRM',
                'auth_type': 'OAUTH2',
                'oauth_auth_url': 'https://accounts.zoho.com/oauth/v2/auth',
                'oauth_token_url': 'https://accounts.zoho.com/oauth/v2/token',
                'oauth_scopes': 'ZohoBigin.modules.ALL,ZohoBigin.settings.ALL',
                'rate_limit_requests': 100,
                'rate_limit_window_seconds': 60,
                'is_active': True,
            },
            {
                'slug': 'hubspot',
                'name': 'HubSpot',
                'description': 'Sync contacts, companies, deals, and marketing data with HubSpot CRM.',
                'icon_class': 'fab fa-hubspot',
                'category': 'CRM',
                'auth_type': 'OAUTH2',
                'oauth_auth_url': 'https://app.hubspot.com/oauth/authorize',
                'oauth_token_url': 'https://api.hubapi.com/oauth/v1/token',
                'oauth_scopes': 'crm.objects.contacts.read crm.objects.contacts.write crm.objects.companies.read',
                'rate_limit_requests': 100,
                'rate_limit_window_seconds': 10,
                'is_active': True,
            },
            # Finance Integrations
            {
                'slug': 'sage-intacct',
                'name': 'Sage Intacct',
                'description': 'Connect to Sage Intacct for financial management, invoicing, and accounting integration.',
                'icon_class': 'fas fa-calculator',
                'category': 'FINANCE',
                'auth_type': 'API_KEY',
                'docs_url': 'https://developer.intacct.com/api/',
                'setup_instructions': '''## Sage Intacct Setup

1. Log in to your Sage Intacct account
2. Navigate to Company > Admin > Web Services
3. Create a new Web Services user
4. Generate API credentials
5. Enter the credentials below:
   - Sender ID
   - Sender Password  
   - Company ID
   - User ID
   - User Password''',
                'rate_limit_requests': 50,
                'rate_limit_window_seconds': 60,
                'is_active': True,
            },
            {
                'slug': 'xero',
                'name': 'Xero',
                'description': 'Sync invoices, payments, and financial data with Xero accounting software.',
                'icon_class': 'fas fa-file-invoice-dollar',
                'category': 'FINANCE',
                'auth_type': 'OAUTH2',
                'oauth_auth_url': 'https://login.xero.com/identity/connect/authorize',
                'oauth_token_url': 'https://identity.xero.com/connect/token',
                'oauth_scopes': 'openid profile email accounting.transactions accounting.contacts',
                'rate_limit_requests': 60,
                'rate_limit_window_seconds': 60,
                'is_active': True,
            },
            # LMS Integrations
            {
                'slug': 'moodle',
                'name': 'Moodle LMS',
                'description': 'Integrate with Moodle for course management, enrolments, and grade synchronization.',
                'icon_class': 'fas fa-graduation-cap',
                'category': 'LMS',
                'auth_type': 'API_KEY',
                'docs_url': 'https://docs.moodle.org/dev/Web_services',
                'setup_instructions': '''## Moodle Setup

1. Log in to Moodle as administrator
2. Go to Site administration > Plugins > Web services > External services
3. Create a new external service or use existing
4. Enable the required web service functions
5. Go to Site administration > Plugins > Web services > Manage tokens
6. Create a token for the service
7. Copy the token and your Moodle URL below''',
                'rate_limit_requests': 120,
                'rate_limit_window_seconds': 60,
                'connector_class': 'integrations.connectors.moodle.MoodleConnector',
                'is_active': True,
            },
            # Communication Integrations
            {
                'slug': 'microsoft365',
                'name': 'Microsoft 365',
                'description': 'Connect to Microsoft 365 for email, calendar, Teams, SharePoint, and OneDrive integration.',
                'icon_class': 'fab fa-microsoft',
                'category': 'COMMS',
                'auth_type': 'OAUTH2',
                'oauth_auth_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
                'oauth_token_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
                'oauth_scopes': 'User.Read Mail.Read Mail.Send Calendars.ReadWrite Files.ReadWrite.All Sites.Read.All Team.ReadBasic.All OnlineMeetings.ReadWrite',
                'docs_url': 'https://learn.microsoft.com/graph/api/overview',
                'setup_instructions': '''## Microsoft 365 Setup

1. Go to Azure Portal > App registrations
2. Create a new app registration
3. Configure redirect URIs for OAuth
4. Add required API permissions (Microsoft Graph)
5. Create a client secret
6. Copy your Tenant ID, Client ID, and Client Secret below''',
                'connector_class': 'integrations.connectors.microsoft365.Microsoft365Connector',
                'rate_limit_requests': 10000,
                'rate_limit_window_seconds': 60,
                'supports_sync': True,
                'supports_webhooks': True,
                'is_active': True,
            },
            {
                'slug': 'whatsapp-business',
                'name': 'WhatsApp Business',
                'description': 'Send notifications, reminders, and engage with learners via WhatsApp Business API.',
                'icon_class': 'fab fa-whatsapp',
                'category': 'COMMS',
                'auth_type': 'BEARER',
                'docs_url': 'https://developers.facebook.com/docs/whatsapp/cloud-api',
                'setup_instructions': '''## WhatsApp Business API Setup

1. Create a Meta Business account
2. Set up WhatsApp Business API in Meta Developer Portal
3. Create a WhatsApp Business app
4. Add a phone number and verify
5. Generate a permanent access token
6. Configure webhook URL for incoming messages''',
                'rate_limit_requests': 80,
                'rate_limit_window_seconds': 60,
                'supports_webhooks': True,
                'is_active': True,
            },
            {
                'slug': 'zoom',
                'name': 'Zoom',
                'description': 'Create and manage meetings, webinars, and sync attendance data from Zoom.',
                'icon_class': 'fas fa-video',
                'category': 'COMMS',
                'auth_type': 'OAUTH2',
                'oauth_auth_url': 'https://zoom.us/oauth/authorize',
                'oauth_token_url': 'https://zoom.us/oauth/token',
                'oauth_scopes': 'meeting:read meeting:write user:read',
                'docs_url': 'https://developers.zoom.us/docs/api/',
                'rate_limit_requests': 30,
                'rate_limit_window_seconds': 1,
                'supports_webhooks': True,
                'is_active': True,
            },
            {
                'slug': 'google-workspace',
                'name': 'Google Workspace',
                'description': 'Integrate with Google Calendar, Gmail, Drive, and Meet for seamless collaboration.',
                'icon_class': 'fab fa-google',
                'category': 'PRODUCTIVITY',
                'auth_type': 'OAUTH2',
                'oauth_auth_url': 'https://accounts.google.com/o/oauth2/v2/auth',
                'oauth_token_url': 'https://oauth2.googleapis.com/token',
                'oauth_scopes': 'https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/drive.file',
                'docs_url': 'https://developers.google.com/workspace',
                'rate_limit_requests': 10000,
                'rate_limit_window_seconds': 100,
                'is_active': True,
            },
            # Social Media Integrations
            {
                'slug': 'meta-business',
                'name': 'Meta Business Suite',
                'description': 'Connect to Facebook and Instagram for marketing, lead ads, and audience management.',
                'icon_class': 'fab fa-meta',
                'category': 'SOCIAL',
                'auth_type': 'OAUTH2',
                'oauth_auth_url': 'https://www.facebook.com/v18.0/dialog/oauth',
                'oauth_token_url': 'https://graph.facebook.com/v18.0/oauth/access_token',
                'oauth_scopes': 'pages_read_engagement,pages_manage_metadata,leads_retrieval,ads_read',
                'docs_url': 'https://developers.facebook.com/docs/marketing-apis',
                'rate_limit_requests': 200,
                'rate_limit_window_seconds': 60,
                'supports_webhooks': True,
                'is_active': True,
            },
            # Automation Integrations
            {
                'slug': 'zapier',
                'name': 'Zapier',
                'description': 'Connect to thousands of apps through Zapier automation. Create triggers and actions.',
                'icon_class': 'fas fa-bolt',
                'category': 'AUTOMATION',
                'auth_type': 'WEBHOOK',
                'docs_url': 'https://zapier.com/platform',
                'setup_instructions': '''## Zapier Integration

1. Log in to Zapier
2. Create a new Zap
3. Select SkillsFlow as trigger or action app
4. Use the provided webhook URLs for triggers
5. Configure your automation workflow''',
                'supports_webhooks': True,
                'is_active': True,
            },
            {
                'slug': 'make',
                'name': 'Make (Integromat)',
                'description': 'Build powerful automation workflows with Make (formerly Integromat).',
                'icon_class': 'fas fa-cogs',
                'category': 'AUTOMATION',
                'auth_type': 'API_KEY',
                'docs_url': 'https://www.make.com/en/api-documentation',
                'supports_webhooks': True,
                'is_active': True,
            },
            # Storage/Documents
            {
                'slug': 'dropbox',
                'name': 'Dropbox',
                'description': 'Store and sync documents, certificates, and files with Dropbox cloud storage.',
                'icon_class': 'fab fa-dropbox',
                'category': 'STORAGE',
                'auth_type': 'OAUTH2',
                'oauth_auth_url': 'https://www.dropbox.com/oauth2/authorize',
                'oauth_token_url': 'https://api.dropboxapi.com/oauth2/token',
                'oauth_scopes': 'files.content.read files.content.write files.metadata.read',
                'docs_url': 'https://www.dropbox.com/developers/documentation',
                'rate_limit_requests': 1000,
                'rate_limit_window_seconds': 60,
                'is_active': True,
            },
            # SMS
            {
                'slug': 'twilio',
                'name': 'Twilio',
                'description': 'Send SMS notifications, reminders, and two-factor authentication via Twilio.',
                'icon_class': 'fas fa-sms',
                'category': 'COMMS',
                'auth_type': 'API_KEY',
                'docs_url': 'https://www.twilio.com/docs',
                'setup_instructions': '''## Twilio Setup

1. Create a Twilio account
2. Get your Account SID and Auth Token from the Console
3. Get or purchase a phone number
4. Optionally set up a Messaging Service
5. Enter your credentials below''',
                'rate_limit_requests': 100,
                'rate_limit_window_seconds': 1,
                'supports_webhooks': True,
                'is_active': True,
            },
        ]

        created_count = 0
        updated_count = 0

        for provider_data in providers:
            provider, created = IntegrationProvider.objects.update_or_create(
                slug=provider_data['slug'],
                defaults=provider_data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created: {provider.name}"))
            else:
                updated_count += 1
                self.stdout.write(f"Updated: {provider.name}")

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"Done! Created {created_count} new providers, updated {updated_count} existing."
        ))
        self.stdout.write(f"Total providers: {IntegrationProvider.objects.count()}")
