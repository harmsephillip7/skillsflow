"""
Integration Hub Models

Central models for managing all external service integrations:
- IntegrationProvider: Registry of available integration types
- IntegrationConnection: Per-brand connection instances with encrypted credentials
- IntegrationSyncLog: Audit trail for all sync operations
- IntegrationWebhook: Inbound webhook management
- IntegrationFieldMapping: Configurable field mappings
"""

import uuid
from django.db import models
from django.utils import timezone
from core.models import AuditedModel, User


class IntegrationProvider(models.Model):
    """
    Registry of available integration providers.
    Pre-populated with supported integrations (Sage, Moodle, Microsoft, etc.)
    """
    
    CATEGORY_CHOICES = [
        ('FINANCE', 'Finance & Accounting'),
        ('LMS', 'Learning Management'),
        ('CRM', 'CRM & Sales'),
        ('COMMS', 'Communication'),
        ('PRODUCTIVITY', 'Productivity & Collaboration'),
        ('SOCIAL', 'Social Media'),
        ('AUTOMATION', 'Automation & Workflow'),
        ('STORAGE', 'File Storage'),
        ('ANALYTICS', 'Analytics & Reporting'),
        ('HR', 'HR & Workforce'),
        ('OTHER', 'Other'),
    ]
    
    AUTH_TYPE_CHOICES = [
        ('API_KEY', 'API Key'),
        ('OAUTH2', 'OAuth 2.0'),
        ('OAUTH1', 'OAuth 1.0'),
        ('BASIC', 'Basic Auth (Username/Password)'),
        ('BEARER', 'Bearer Token'),
        ('WEBHOOK', 'Webhook Only'),
        ('CUSTOM', 'Custom Authentication'),
    ]
    
    # Identity
    slug = models.SlugField(max_length=50, unique=True, help_text="Unique identifier (e.g., 'sage-intacct', 'microsoft-365')")
    name = models.CharField(max_length=100, help_text="Display name")
    description = models.TextField(blank=True, help_text="Brief description of the integration")
    
    # Classification
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPE_CHOICES, default='API_KEY')
    
    # Branding
    logo = models.ImageField(upload_to='integration_logos/', null=True, blank=True)
    icon_class = models.CharField(max_length=50, blank=True, help_text="CSS icon class (e.g., 'fab fa-microsoft')")
    color = models.CharField(max_length=7, default='#6366f1', help_text="Brand color (hex)")
    
    # Documentation
    docs_url = models.URLField(blank=True, help_text="Link to integration documentation")
    setup_instructions = models.TextField(blank=True, help_text="Step-by-step setup guide (Markdown)")
    
    # OAuth Configuration (for OAuth-based integrations)
    oauth_auth_url = models.URLField(blank=True, help_text="OAuth authorization endpoint")
    oauth_token_url = models.URLField(blank=True, help_text="OAuth token endpoint")
    oauth_scopes = models.TextField(blank=True, help_text="Required OAuth scopes (comma-separated)")
    
    # Rate Limiting
    rate_limit_requests = models.PositiveIntegerField(default=1000, help_text="Max requests per window")
    rate_limit_window_seconds = models.PositiveIntegerField(default=3600, help_text="Rate limit window in seconds")
    
    # Features
    supports_sync = models.BooleanField(default=True, help_text="Supports data synchronization")
    supports_webhooks = models.BooleanField(default=False, help_text="Supports inbound webhooks")
    supports_realtime = models.BooleanField(default=False, help_text="Supports real-time updates")
    
    # Status
    is_active = models.BooleanField(default=True, help_text="Available for new connections")
    is_beta = models.BooleanField(default=False, help_text="Beta/experimental integration")
    
    # Connector class
    connector_class = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Python path to connector class (e.g., 'integrations.connectors.microsoft.MicrosoftConnector')"
    )
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Integration Provider'
        verbose_name_plural = 'Integration Providers'
    
    def __str__(self):
        return self.name
    
    @property
    def base_url(self) -> str:
        """
        Default base URL for this provider.
        NOTE: base_url is stored on IntegrationConnection, but templates/views
        sometimes read provider.base_url to pre-fill UI inputs.
        """
        defaults = {
            "whatsapp": "https://graph.facebook.com/v18.0",
        }
        return defaults.get(self.slug, "")

    @property
    def logo_url(self):
        """Return logo URL or default based on category."""
        if self.logo:
            return self.logo.url
        return None


class IntegrationConnection(AuditedModel):
    """
    A connection instance between a brand and an external service.
    Stores encrypted credentials and connection status.
    """
    from .encryption import EncryptedCharField, EncryptedTextField
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Setup'),
        ('ACTIVE', 'Active'),
        ('ERROR', 'Error'),
        ('DISCONNECTED', 'Disconnected'),
        ('EXPIRED', 'Credentials Expired'),
        ('RATE_LIMITED', 'Rate Limited'),
    ]
    
    HEALTH_CHOICES = [
        ('HEALTHY', 'Healthy'),
        ('DEGRADED', 'Degraded'),
        ('UNHEALTHY', 'Unhealthy'),
        ('UNKNOWN', 'Unknown'),
    ]
    
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    provider = models.ForeignKey(
        IntegrationProvider,
        on_delete=models.PROTECT,
        related_name='connections'
    )
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='integration_connections'
    )
    
    # Display
    name = models.CharField(max_length=100, blank=True, help_text="Custom name for this connection")
    
    # Credentials (encrypted)
    api_key = EncryptedCharField(blank=True, help_text="API Key or Token")
    api_secret = EncryptedCharField(blank=True, help_text="API Secret")
    access_token = EncryptedTextField(blank=True, help_text="OAuth Access Token")
    refresh_token = EncryptedTextField(blank=True, help_text="OAuth Refresh Token")
    client_id = EncryptedCharField(blank=True, help_text="OAuth Client ID")
    client_secret = EncryptedCharField(blank=True, help_text="OAuth Client Secret")
    
    # OAuth state
    token_expires_at = models.DateTimeField(null=True, blank=True, help_text="When access token expires")
    oauth_state = models.CharField(max_length=100, blank=True, help_text="OAuth state parameter for CSRF")
    
    # Additional configuration (JSON)
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific configuration (e.g., tenant_id, company_id)"
    )
    
    # Endpoints
    base_url = models.URLField(blank=True, help_text="Custom API base URL (if applicable)")
    webhook_url = models.URLField(blank=True, help_text="Outbound webhook URL (if applicable)")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    health_status = models.CharField(max_length=20, choices=HEALTH_CHOICES, default='UNKNOWN')
    last_health_check = models.DateTimeField(null=True, blank=True)
    status_message = models.TextField(blank=True, help_text="Last status/error message")
    
    # Sync Configuration
    sync_enabled = models.BooleanField(default=True, help_text="Enable automatic sync")
    sync_interval_minutes = models.PositiveIntegerField(default=60, help_text="Sync interval in minutes")
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=20, blank=True)
    next_sync_at = models.DateTimeField(null=True, blank=True)
    
    # Rate Limiting
    rate_limit_remaining = models.PositiveIntegerField(null=True, blank=True, help_text="Remaining API calls")
    rate_limit_resets_at = models.DateTimeField(null=True, blank=True, help_text="When rate limit resets")
    
    # Timestamps
    connected_at = models.DateTimeField(null=True, blank=True, help_text="When connection was established")
    disconnected_at = models.DateTimeField(null=True, blank=True, help_text="When connection was disconnected")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Integration Connection'
        verbose_name_plural = 'Integration Connections'
        unique_together = [['provider', 'brand', 'name']]
        permissions = [
            ('can_manage_integrations', 'Can manage integration connections'),
        ]
    
    def __str__(self):
        display_name = self.name or self.provider.name
        return f"{self.brand.name} - {display_name}"
    
    def save(self, *args, **kwargs):
        # Set default name if not provided
        if not self.name:
            self.name = self.provider.name
        
        # Calculate next sync time
        if self.sync_enabled and self.last_sync_at:
            from datetime import timedelta
            self.next_sync_at = self.last_sync_at + timedelta(minutes=self.sync_interval_minutes)
        
        super().save(*args, **kwargs)
    
    @property
    def is_connected(self):
        """Check if connection is active."""
        return self.status == 'ACTIVE'
    
    @property
    def is_token_expired(self):
        """Check if OAuth token is expired."""
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at
    
    @property
    def token_expires_soon(self):
        """Check if token expires within 1 hour."""
        if not self.token_expires_at:
            return False
        from datetime import timedelta
        return timezone.now() >= (self.token_expires_at - timedelta(hours=1))
    
    @property
    def rate_limit_percentage(self):
        """Calculate rate limit usage percentage."""
        if not self.rate_limit_remaining or not self.provider.rate_limit_requests:
            return None
        used = self.provider.rate_limit_requests - self.rate_limit_remaining
        return round((used / self.provider.rate_limit_requests) * 100, 1)
    
    def update_rate_limit(self, remaining, resets_at=None):
        """Update rate limit info from API response headers."""
        self.rate_limit_remaining = remaining
        if resets_at:
            self.rate_limit_resets_at = resets_at
        self.save(update_fields=['rate_limit_remaining', 'rate_limit_resets_at'])
    
    def mark_sync_complete(self, status='SUCCESS'):
        """Update sync timestamps after a sync operation."""
        self.last_sync_at = timezone.now()
        self.last_sync_status = status
        from datetime import timedelta
        self.next_sync_at = self.last_sync_at + timedelta(minutes=self.sync_interval_minutes)
        self.save(update_fields=['last_sync_at', 'last_sync_status', 'next_sync_at'])
    
    def disconnect(self, user=None):
        """Disconnect and clear credentials."""
        self.status = 'DISCONNECTED'
        self.disconnected_at = timezone.now()
        self.access_token = ''
        self.refresh_token = ''
        self.api_key = ''
        self.api_secret = ''
        self.updated_by = user
        self.save()


class IntegrationSyncLog(models.Model):
    """
    Audit log for all sync operations.
    Tracks success/failure, records processed, and full request/response for debugging.
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('SUCCESS', 'Success'),
        ('PARTIAL', 'Partial Success'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    DIRECTION_CHOICES = [
        ('INBOUND', 'Inbound (External → SkillsFlow)'),
        ('OUTBOUND', 'Outbound (SkillsFlow → External)'),
        ('BIDIRECTIONAL', 'Bidirectional'),
    ]
    
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        related_name='sync_logs'
    )
    
    # Operation details
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default='OUTBOUND')
    entity_type = models.CharField(max_length=50, help_text="Type of data synced (e.g., 'learner', 'invoice', 'course')")
    operation = models.CharField(max_length=50, blank=True, help_text="Specific operation (e.g., 'create', 'update', 'sync_all')")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Metrics
    records_total = models.PositiveIntegerField(default=0, help_text="Total records to process")
    records_processed = models.PositiveIntegerField(default=0, help_text="Records successfully processed")
    records_failed = models.PositiveIntegerField(default=0, help_text="Records that failed")
    records_skipped = models.PositiveIntegerField(default=0, help_text="Records skipped (already synced)")
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True, help_text="Duration in milliseconds")
    
    # Debug info
    request_payload = models.JSONField(null=True, blank=True, help_text="Request data sent to API")
    response_payload = models.JSONField(null=True, blank=True, help_text="Response data received")
    error_message = models.TextField(blank=True, help_text="Error message if failed")
    error_details = models.JSONField(null=True, blank=True, help_text="Detailed error info (stack trace, etc.)")
    
    # Triggered by
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='integration_syncs',
        help_text="User who triggered the sync (null for scheduled)"
    )
    is_scheduled = models.BooleanField(default=False, help_text="Was this a scheduled sync?")
    
    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Sync Log'
        verbose_name_plural = 'Sync Logs'
        indexes = [
            models.Index(fields=['connection', '-started_at']),
            models.Index(fields=['status', '-started_at']),
            models.Index(fields=['entity_type', '-started_at']),
        ]
    
    def __str__(self):
        return f"{self.connection.provider.name} - {self.entity_type} - {self.status}"
    
    def complete(self, status='SUCCESS', error_message=''):
        """Mark sync as complete and calculate duration."""
        self.completed_at = timezone.now()
        self.status = status
        if error_message:
            self.error_message = error_message
        
        # Calculate duration
        delta = self.completed_at - self.started_at
        self.duration_ms = int(delta.total_seconds() * 1000)
        
        self.save()
    
    @property
    def success_rate(self):
        """Calculate success rate percentage."""
        if self.records_total == 0:
            return 100.0
        return round((self.records_processed / self.records_total) * 100, 1)


class IntegrationWebhook(AuditedModel):
    """
    Inbound webhook configuration.
    Each provider can have multiple webhooks for different event types.
    """
    from .encryption import EncryptedCharField
    
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        related_name='webhooks'
    )
    
    # Configuration
    name = models.CharField(max_length=100, help_text="Webhook name (e.g., 'Payment Notifications')")
    event_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Event types this webhook handles (list of strings)"
    )
    
    # Security
    secret_key = EncryptedCharField(help_text="HMAC secret for signature verification")
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text="Optional IP allowlist (list of IP addresses)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False, help_text="Has webhook been verified?")
    
    # Metrics
    last_received_at = models.DateTimeField(null=True, blank=True)
    total_received = models.PositiveIntegerField(default=0)
    total_processed = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'
    
    def __str__(self):
        return f"{self.connection} - {self.name}"
    
    @property
    def endpoint_url(self):
        """Generate the webhook endpoint URL."""
        from django.urls import reverse
        return reverse('integrations:webhook_receiver', kwargs={
            'provider_slug': self.connection.provider.slug,
            'webhook_id': str(self.id)
        })
    
    def generate_secret(self):
        """Generate a new HMAC secret."""
        import secrets
        self.secret_key = secrets.token_urlsafe(32)
        self.save(update_fields=['secret_key'])
        return self.secret_key
    
    def record_received(self, success=True):
        """Record that a webhook was received."""
        self.last_received_at = timezone.now()
        self.total_received += 1
        if success:
            self.total_processed += 1
        else:
            self.total_failed += 1
        self.save(update_fields=['last_received_at', 'total_received', 'total_processed', 'total_failed'])


class IntegrationWebhookLog(models.Model):
    """
    Log of incoming webhook requests for debugging.
    """
    
    STATUS_CHOICES = [
        ('RECEIVED', 'Received'),
        ('VERIFIED', 'Signature Verified'),
        ('PROCESSED', 'Processed'),
        ('FAILED', 'Failed'),
        ('REJECTED', 'Rejected (Invalid Signature)'),
    ]
    
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    webhook = models.ForeignKey(
        IntegrationWebhook,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    
    # Request details
    event_type = models.CharField(max_length=50, blank=True)
    headers = models.JSONField(default=dict, help_text="Request headers")
    payload = models.JSONField(default=dict, help_text="Request body")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Processing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RECEIVED')
    error_message = models.TextField(blank=True)
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Webhook Log'
        verbose_name_plural = 'Webhook Logs'
        indexes = [
            models.Index(fields=['webhook', '-received_at']),
            models.Index(fields=['status', '-received_at']),
        ]
    
    def __str__(self):
        return f"{self.webhook.name} - {self.event_type} - {self.status}"


class IntegrationFieldMapping(AuditedModel):
    """
    Configurable field mapping between SkillsFlow and external systems.
    Allows users to customize how data is mapped during sync.
    """
    
    TRANSFORM_CHOICES = [
        ('DIRECT', 'Direct Copy'),
        ('UPPERCASE', 'Convert to Uppercase'),
        ('LOWERCASE', 'Convert to Lowercase'),
        ('DATE_FORMAT', 'Format Date'),
        ('LOOKUP', 'Lookup Value'),
        ('CONCAT', 'Concatenate Fields'),
        ('SPLIT', 'Split Field'),
        ('CUSTOM', 'Custom Transform'),
    ]
    
    # Relationships
    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        related_name='field_mappings'
    )
    
    # Entity context
    entity_type = models.CharField(max_length=50, help_text="Entity type (e.g., 'learner', 'invoice')")
    direction = models.CharField(
        max_length=20,
        choices=IntegrationSyncLog.DIRECTION_CHOICES,
        default='BIDIRECTIONAL'
    )
    
    # Mapping
    internal_field = models.CharField(max_length=100, help_text="SkillsFlow field path (e.g., 'learner.email')")
    external_field = models.CharField(max_length=100, help_text="External system field (e.g., 'contact_email')")
    
    # Transform
    transform_type = models.CharField(max_length=20, choices=TRANSFORM_CHOICES, default='DIRECT')
    transform_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Transform configuration (e.g., date format, lookup table)"
    )
    
    # Options
    is_required = models.BooleanField(default=False, help_text="Is this field required for sync?")
    is_active = models.BooleanField(default=True)
    default_value = models.CharField(max_length=500, blank=True, help_text="Default value if source is empty")
    
    class Meta:
        ordering = ['entity_type', 'internal_field']
        verbose_name = 'Field Mapping'
        verbose_name_plural = 'Field Mappings'
        unique_together = [['connection', 'entity_type', 'internal_field', 'direction']]
    
    def __str__(self):
        return f"{self.entity_type}: {self.internal_field} ↔ {self.external_field}"
    
    def apply_transform(self, value):
        """Apply the configured transform to a value."""
        if value is None:
            return self.default_value or None
        
        if self.transform_type == 'DIRECT':
            return value
        elif self.transform_type == 'UPPERCASE':
            return str(value).upper()
        elif self.transform_type == 'LOWERCASE':
            return str(value).lower()
        elif self.transform_type == 'DATE_FORMAT':
            # Transform date using format from config
            date_format = self.transform_config.get('format', '%Y-%m-%d')
            if hasattr(value, 'strftime'):
                return value.strftime(date_format)
            return value
        elif self.transform_type == 'LOOKUP':
            # Lookup value in mapping table
            lookup_table = self.transform_config.get('lookup', {})
            return lookup_table.get(str(value), value)
        elif self.transform_type == 'CONCAT':
            # Concatenation is handled at sync level
            return value
        
        return value


class IntegrationEntityMapping(models.Model):
    """
    Maps internal entity IDs to external system IDs.
    Used to track which records have been synced and their external counterparts.
    """
    
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    connection = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        related_name='entity_mappings'
    )
    
    # Entity type
    entity_type = models.CharField(max_length=50, help_text="Entity type (e.g., 'learner', 'invoice')")
    
    # IDs
    internal_id = models.CharField(max_length=100, help_text="SkillsFlow entity ID")
    external_id = models.CharField(max_length=100, help_text="External system entity ID")
    
    # Metadata
    external_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cached external entity data"
    )
    
    # Sync status
    last_synced_at = models.DateTimeField(auto_now=True)
    sync_status = models.CharField(max_length=20, default='SYNCED')
    checksum = models.CharField(max_length=64, blank=True, help_text="Hash for change detection")
    
    class Meta:
        ordering = ['-last_synced_at']
        verbose_name = 'Entity Mapping'
        verbose_name_plural = 'Entity Mappings'
        unique_together = [['connection', 'entity_type', 'internal_id']]
        indexes = [
            models.Index(fields=['connection', 'entity_type', 'external_id']),
            models.Index(fields=['entity_type', 'internal_id']),
        ]
    
    def __str__(self):
        return f"{self.entity_type}: {self.internal_id} ↔ {self.external_id}"
