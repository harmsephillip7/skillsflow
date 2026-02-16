"""
Omnichannel Communication Models

Unified communication infrastructure for WhatsApp, Facebook, Instagram, 
TikTok, Email (Microsoft 365), and SMS channels.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import AuditedModel
from tenants.models import TenantAwareModel


class SocialChannel(TenantAwareModel):
    """
    Social media channel configuration.
    One record per WhatsApp number, Facebook page, Instagram account, or TikTok account.
    """
    CHANNEL_TYPES = [
        ('WHATSAPP', 'WhatsApp Business'),
        ('FACEBOOK', 'Facebook Messenger'),
        ('INSTAGRAM', 'Instagram DM'),
        ('TIKTOK', 'TikTok'),
    ]
    
    PURPOSE_CHOICES = [
        ('SALES', 'Sales'),
        ('MARKETING', 'Marketing'),
        ('SUPPORT', 'Support'),
        ('GENERAL', 'General'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('PENDING', 'Pending Setup'),
        ('ERROR', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Integration connection (for credentials)
    connection = models.ForeignKey(
        'integrations.IntegrationConnection',
        on_delete=models.CASCADE,
        related_name='social_channels'
    )
    
    # Channel identification
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPES)
    external_id = models.CharField(
        max_length=100, 
        help_text="Phone number ID (WhatsApp), Page ID (FB), IG ID, or TikTok ID"
    )
    display_name = models.CharField(max_length=100, help_text="e.g., 'JHB Campus WhatsApp'")
    display_number = models.CharField(max_length=20, blank=True, help_text="Display phone number for WhatsApp")
    
    # Purpose and assignment
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='SALES')
    assigned_agents = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='assigned_channels',
        help_text="Agents who can receive conversations from this channel"
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    status_message = models.TextField(blank=True)
    last_health_check = models.DateTimeField(null=True, blank=True)
    
    # Webhook configuration
    webhook_verify_token = models.CharField(max_length=100, blank=True)
    
    # WhatsApp-specific
    whatsapp_business_account_id = models.CharField(max_length=50, blank=True)
    
    # Rate limiting
    daily_message_limit = models.PositiveIntegerField(default=1000)
    messages_sent_today = models.PositiveIntegerField(default=0)
    limit_reset_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['campus', 'channel_type']
        unique_together = [['channel_type', 'external_id']]
        verbose_name = 'Social Channel'
        verbose_name_plural = 'Social Channels'
    
    def __str__(self):
        return f"{self.display_name} ({self.get_channel_type_display()})"
    
    def get_icon_class(self):
        """Return CSS icon class for channel type."""
        icons = {
            'WHATSAPP': 'fab fa-whatsapp',
            'FACEBOOK': 'fab fa-facebook-messenger',
            'INSTAGRAM': 'fab fa-instagram',
            'TIKTOK': 'fab fa-tiktok',
        }
        return icons.get(self.channel_type, 'fas fa-comment')
    
    def get_color(self):
        """Return brand color for channel type."""
        colors = {
            'WHATSAPP': '#25D366',
            'FACEBOOK': '#0084FF',
            'INSTAGRAM': '#E4405F',
            'TIKTOK': '#000000',
        }
        return colors.get(self.channel_type, '#6B7280')


class EmailAccount(TenantAwareModel):
    """
    Email account configuration for Microsoft 365 integration.
    One record per agent's email inbox.
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('PENDING', 'Pending OAuth'),
        ('ERROR', 'Error'),
        ('EXPIRED', 'Token Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Integration connection (Microsoft 365)
    connection = models.ForeignKey(
        'integrations.IntegrationConnection',
        on_delete=models.CASCADE,
        related_name='email_accounts'
    )
    
    # Email account details
    email_address = models.EmailField(unique=True)
    display_name = models.CharField(max_length=100)
    
    # Agent assignment (one email per agent typically)
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_accounts'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    status_message = models.TextField(blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    
    # OAuth tokens (encrypted via connection or stored here)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Configuration
    signature_html = models.TextField(blank=True, help_text="HTML email signature")
    auto_reply_enabled = models.BooleanField(default=False)
    auto_reply_message = models.TextField(blank=True)
    
    # Sync settings
    sync_enabled = models.BooleanField(default=True)
    sync_inbox = models.BooleanField(default=True)
    sync_sent = models.BooleanField(default=True)
    last_delta_token = models.TextField(blank=True, help_text="Microsoft Graph delta token")
    
    class Meta:
        ordering = ['campus', 'email_address']
        verbose_name = 'Email Account'
        verbose_name_plural = 'Email Accounts'
    
    def __str__(self):
        return f"{self.email_address} ({self.agent.get_full_name()})"


class SMSConfig(TenantAwareModel):
    """
    SMS gateway configuration per brand.
    Shared SMS pool for a brand with sender ID.
    """
    PROVIDER_CHOICES = [
        ('BULKSMS', 'BulkSMS'),
        ('CLICKATELL', 'Clickatell'),
        ('TWILIO', 'Twilio'),
        ('AFRICA_TALKING', "Africa's Talking"),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ERROR', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Provider configuration
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    
    # Credentials (encrypted)
    api_key = models.CharField(max_length=200)
    api_secret = models.CharField(max_length=200, blank=True)
    account_id = models.CharField(max_length=100, blank=True)
    
    # Sender configuration
    sender_id = models.CharField(max_length=11, help_text="Alphanumeric sender ID (max 11 chars)")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    status_message = models.TextField(blank=True)
    
    # Limits
    monthly_limit = models.PositiveIntegerField(default=10000)
    messages_sent_this_month = models.PositiveIntegerField(default=0)
    limit_reset_at = models.DateTimeField(null=True, blank=True)
    
    # Cost tracking
    cost_per_sms = models.DecimalField(max_digits=6, decimal_places=4, default=0.0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['campus', 'provider']
        verbose_name = 'SMS Configuration'
        verbose_name_plural = 'SMS Configurations'
    
    def __str__(self):
        return f"{self.brand.name} - {self.get_provider_display()} ({self.sender_id})"


class ConversationTag(TenantAwareModel):
    """
    Tags for organizing and filtering conversations.
    """
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default='#6B7280')
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['campus', 'name']
        unique_together = [['campus', 'name']]
        verbose_name = 'Conversation Tag'
        verbose_name_plural = 'Conversation Tags'
    
    def __str__(self):
        return self.name


class Conversation(TenantAwareModel):
    """
    A conversation thread with a contact across any channel.
    Unified inbox entry for WhatsApp, Facebook, Instagram, TikTok, Email, SMS.
    """
    CHANNEL_TYPES = [
        ('WHATSAPP', 'WhatsApp'),
        ('FACEBOOK', 'Facebook Messenger'),
        ('INSTAGRAM', 'Instagram DM'),
        ('TIKTOK', 'TikTok'),
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('PENDING', 'Pending Response'),
        ('SNOOZED', 'Snoozed'),
        ('CLOSED', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Channel identification
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPES)
    social_channel = models.ForeignKey(
        SocialChannel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversations',
        help_text="For social media channels"
    )
    email_account = models.ForeignKey(
        EmailAccount,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversations',
        help_text="For email conversations"
    )
    sms_config = models.ForeignKey(
        SMSConfig,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversations',
        help_text="For SMS conversations"
    )
    
    # Contact identification
    contact_identifier = models.CharField(
        max_length=200,
        help_text="Phone number (WA/SMS), email, or platform user ID"
    )
    contact_name = models.CharField(max_length=200, blank=True)
    contact_profile_pic = models.URLField(blank=True)
    
    # External conversation/thread ID
    external_id = models.CharField(max_length=200, blank=True, help_text="Platform's conversation ID")
    
    # Email-specific: thread tracking
    email_thread_id = models.CharField(max_length=200, blank=True)
    email_subject = models.CharField(max_length=500, blank=True)
    
    # CRM linking
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversations'
    )
    opportunity = models.ForeignKey(
        'crm.Opportunity',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversations'
    )
    
    # Assignment
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_conversations'
    )
    
    # Status and priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='NORMAL')
    snoozed_until = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_inbound_at = models.DateTimeField(null=True, blank=True)
    last_outbound_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    
    # Response metrics
    response_time_seconds = models.PositiveIntegerField(null=True, blank=True)
    
    # WhatsApp-specific: 24-hour window tracking
    whatsapp_window_expires_at = models.DateTimeField(null=True, blank=True)
    requires_template = models.BooleanField(
        default=False,
        help_text="True if 24hr window expired and template message required"
    )
    
    # Tags
    tags = models.ManyToManyField(ConversationTag, blank=True, related_name='conversations')
    
    # Message counts
    message_count = models.PositiveIntegerField(default=0)
    unread_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-last_message_at']
        indexes = [
            models.Index(fields=['channel_type', 'contact_identifier']),
            models.Index(fields=['assigned_agent', 'status']),
            models.Index(fields=['lead']),
            models.Index(fields=['last_message_at']),
        ]
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
    
    def __str__(self):
        name = self.contact_name or self.contact_identifier
        return f"{name} ({self.get_channel_type_display()})"
    
    def get_channel_icon(self):
        """Return icon class for this conversation's channel."""
        icons = {
            'WHATSAPP': 'fab fa-whatsapp',
            'FACEBOOK': 'fab fa-facebook-messenger',
            'INSTAGRAM': 'fab fa-instagram',
            'TIKTOK': 'fab fa-tiktok',
            'EMAIL': 'fas fa-envelope',
            'SMS': 'fas fa-sms',
        }
        return icons.get(self.channel_type, 'fas fa-comment')
    
    def get_channel_color(self):
        """Return color for this conversation's channel."""
        colors = {
            'WHATSAPP': '#25D366',
            'FACEBOOK': '#0084FF',
            'INSTAGRAM': '#E4405F',
            'TIKTOK': '#000000',
            'EMAIL': '#EA4335',
            'SMS': '#34B7F1',
        }
        return colors.get(self.channel_type, '#6B7280')
    
    def update_whatsapp_window(self):
        """Update WhatsApp 24-hour messaging window."""
        if self.channel_type == 'WHATSAPP' and self.last_inbound_at:
            self.whatsapp_window_expires_at = self.last_inbound_at + timezone.timedelta(hours=24)
            self.requires_template = timezone.now() > self.whatsapp_window_expires_at
    
    def calculate_response_time(self):
        """Calculate response time from first inbound to first outbound."""
        if self.last_inbound_at and self.first_response_at:
            delta = self.first_response_at - self.last_inbound_at
            self.response_time_seconds = int(delta.total_seconds())


class Message(AuditedModel):
    """
    Individual message in a conversation.
    Supports text, media, templates, and platform-specific message types.
    """
    DIRECTION_CHOICES = [
        ('IN', 'Inbound'),
        ('OUT', 'Outbound'),
    ]
    
    MESSAGE_TYPES = [
        ('TEXT', 'Text'),
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
        ('AUDIO', 'Audio'),
        ('DOCUMENT', 'Document'),
        ('STICKER', 'Sticker'),
        ('LOCATION', 'Location'),
        ('CONTACT', 'Contact'),
        ('TEMPLATE', 'Template'),
        ('INTERACTIVE', 'Interactive'),
        ('REACTION', 'Reaction'),
        ('EMAIL', 'Email'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('QUEUED', 'Queued'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('READ', 'Read'),
        ('FAILED', 'Failed'),
        ('DELETED', 'Deleted'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Conversation link
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    # Message identification
    external_id = models.CharField(max_length=200, blank=True, help_text="Platform's message ID")
    
    # Direction and type
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='TEXT')
    
    # Content
    content = models.JSONField(
        default=dict,
        help_text="Message content: {text, media_url, caption, template_name, etc.}"
    )
    text_content = models.TextField(blank=True, help_text="Plain text version for search")
    
    # For templates
    template = models.ForeignKey(
        'crm.MessageTemplate',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='messages'
    )
    template_variables = models.JSONField(default=dict, blank=True)
    
    # Email-specific fields
    email_subject = models.CharField(max_length=500, blank=True)
    email_html = models.TextField(blank=True)
    email_attachments = models.JSONField(default=list, blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    status_updated_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    
    # Delivery timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Sender (for outbound)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='crm_sent_messages'
    )
    
    # Campaign tracking
    campaign = models.ForeignKey(
        'crm.Campaign',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='messages'
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Platform-specific metadata")
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['external_id']),
            models.Index(fields=['status']),
        ]
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
    
    def __str__(self):
        direction = "→" if self.direction == 'OUT' else "←"
        return f"{direction} {self.get_message_type_display()}: {self.text_content[:50]}"
    
    def get_display_content(self):
        """Return human-readable content for display."""
        if self.message_type == 'TEXT':
            return self.text_content or self.content.get('text', '')
        elif self.message_type == 'IMAGE':
            return f"📷 {self.content.get('caption', 'Image')}"
        elif self.message_type == 'VIDEO':
            return f"🎥 {self.content.get('caption', 'Video')}"
        elif self.message_type == 'AUDIO':
            return "🎵 Audio message"
        elif self.message_type == 'DOCUMENT':
            return f"📄 {self.content.get('filename', 'Document')}"
        elif self.message_type == 'LOCATION':
            return f"📍 {self.content.get('name', 'Location')}"
        elif self.message_type == 'TEMPLATE':
            return f"📋 {self.template.name if self.template else 'Template'}"
        elif self.message_type == 'EMAIL':
            return self.email_subject or self.text_content[:100]
        return self.text_content or str(self.content)


class MessageTemplate(TenantAwareModel):
    """
    Reusable message templates for WhatsApp, Email, and SMS.
    WhatsApp templates require Meta approval.
    """
    CHANNEL_TYPES = [
        ('WHATSAPP', 'WhatsApp'),
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
    ]
    
    CATEGORY_CHOICES = [
        ('MARKETING', 'Marketing'),
        ('UTILITY', 'Utility'),
        ('AUTHENTICATION', 'Authentication'),
    ]
    
    HEADER_TYPES = [
        ('NONE', 'No Header'),
        ('TEXT', 'Text'),
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
        ('DOCUMENT', 'Document'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Template identity
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    
    # Channel and category
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='UTILITY')
    
    # Content
    header_type = models.CharField(max_length=20, choices=HEADER_TYPES, default='NONE')
    header_content = models.TextField(blank=True, help_text="Header text or media URL")
    body = models.TextField(help_text="Message body with {{variable}} placeholders")
    footer = models.CharField(max_length=60, blank=True, help_text="Footer text (WhatsApp)")
    
    # Variables
    variables = models.JSONField(
        default=list,
        help_text="List of variable names: ['first_name', 'course_name']"
    )
    
    # Buttons (WhatsApp)
    buttons = models.JSONField(
        default=list,
        blank=True,
        help_text="Button configuration for interactive templates"
    )
    
    # Email-specific
    email_subject = models.CharField(max_length=200, blank=True)
    email_html_template = models.TextField(blank=True)
    
    # WhatsApp approval
    whatsapp_template_id = models.CharField(max_length=100, blank=True)
    whatsapp_template_name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    rejection_reason = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
    times_used = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['campus', 'channel_type', 'name']
        unique_together = [['campus', 'channel_type', 'slug']]
        verbose_name = 'Message Template'
        verbose_name_plural = 'Message Templates'
    
    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"
    
    def render(self, context: dict) -> str:
        """Render template with variables."""
        content = self.body
        for var in self.variables:
            placeholder = f"{{{{{var}}}}}"
            value = context.get(var, '')
            content = content.replace(placeholder, str(value))
        return content


class Campaign(TenantAwareModel):
    """
    Marketing campaign for bulk or drip messaging.
    Supports WhatsApp, Email, and SMS channels.
    """
    TYPE_CHOICES = [
        ('BULK', 'Bulk Send'),
        ('DRIP', 'Drip Campaign'),
        ('TRIGGERED', 'Triggered'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('SCHEDULED', 'Scheduled'),
        ('SENDING', 'Sending'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Campaign identity
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Type and status
    campaign_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='BULK')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Channel and content
    channel_type = models.CharField(max_length=20, choices=Conversation.CHANNEL_TYPES)
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.PROTECT,
        related_name='campaigns'
    )
    
    # Target channel (for social media)
    social_channel = models.ForeignKey(
        SocialChannel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='campaigns'
    )
    sms_config = models.ForeignKey(
        SMSConfig,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='campaigns'
    )
    
    # Targeting (campus scope is additional to brand from TenantAwareModel)
    target_campuses = models.ManyToManyField(
        'tenants.Campus',
        blank=True,
        related_name='campaigns',
        help_text="Empty = all campuses in brand"
    )
    
    # Audience filter
    audience_filter = models.JSONField(
        default=dict,
        help_text="Filter criteria: {lead_type, age_range, status, source, tags}"
    )
    
    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metrics
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    read_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    opted_out_count = models.PositiveIntegerField(default=0)
    replied_count = models.PositiveIntegerField(default=0)
    
    # Cost tracking
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Campaign'
        verbose_name_plural = 'Campaigns'
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def delivery_rate(self):
        """Calculate delivery rate as percentage."""
        if self.sent_count == 0:
            return 0
        return round((self.delivered_count / self.sent_count) * 100, 1)
    
    @property
    def read_rate(self):
        """Calculate read rate as percentage."""
        if self.delivered_count == 0:
            return 0
        return round((self.read_count / self.delivered_count) * 100, 1)
    
    @property
    def reply_rate(self):
        """Calculate reply rate as percentage."""
        if self.delivered_count == 0:
            return 0
        return round((self.replied_count / self.delivered_count) * 100, 1)


class CampaignApproval(AuditedModel):
    """
    Approval workflow for campaigns.
    Manager must approve before sending.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CHANGES_REQUESTED', 'Changes Requested'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='approvals'
    )
    
    # Request
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='campaign_approval_requests'
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    request_notes = models.TextField(blank=True)
    
    # Decision
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='campaign_approvals'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    decision_at = models.DateTimeField(null=True, blank=True)
    comments = models.TextField(blank=True)
    
    # Version tracking
    version = models.PositiveIntegerField(default=1)
    campaign_snapshot = models.JSONField(
        default=dict,
        help_text="Snapshot of campaign config at time of approval request"
    )
    
    class Meta:
        ordering = ['-requested_at']
        verbose_name = 'Campaign Approval'
        verbose_name_plural = 'Campaign Approvals'
    
    def __str__(self):
        return f"{self.campaign.name} - {self.get_status_display()}"


class CampaignRecipient(models.Model):
    """
    Individual recipient in a campaign with delivery tracking.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('QUEUED', 'Queued'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('READ', 'Read'),
        ('FAILED', 'Failed'),
        ('OPTED_OUT', 'Opted Out'),
        ('REPLIED', 'Replied'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,
        related_name='campaign_recipients'
    )
    
    # Delivery tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='campaign_recipient'
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='campaign_recipients'
    )
    
    # Timestamps
    queued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    # Template variables (rendered for this recipient)
    rendered_content = models.TextField(blank=True)
    
    class Meta:
        ordering = ['campaign', 'status']
        unique_together = [['campaign', 'lead']]
        indexes = [
            models.Index(fields=['campaign', 'status']),
        ]
        verbose_name = 'Campaign Recipient'
        verbose_name_plural = 'Campaign Recipients'
    
    def __str__(self):
        return f"{self.lead} - {self.get_status_display()}"


class AutomationRule(TenantAwareModel):
    """
    Automated actions triggered by events.
    E.g., send birthday message, follow up on inactivity.
    """
    TRIGGER_EVENTS = [
        ('LEAD_CREATED', 'Lead Created'),
        ('LEAD_STATUS_CHANGE', 'Lead Status Changed'),
        ('OPPORTUNITY_CREATED', 'Opportunity Created'),
        ('OPPORTUNITY_STAGE_CHANGE', 'Opportunity Stage Changed'),
        ('BIRTHDAY', 'Birthday'),
        ('AGE_MILESTONE', 'Age Milestone (e.g., turns 18)'),
        ('MATRIC_RESULTS', 'Matric Results Released'),
        ('INACTIVITY', 'Inactivity Period'),
        ('MESSAGE_RECEIVED', 'Message Received'),
        ('FORM_SUBMITTED', 'Form Submitted'),
    ]
    
    ACTION_TYPES = [
        ('SEND_MESSAGE', 'Send Message'),
        ('SEND_EMAIL', 'Send Email'),
        ('SEND_SMS', 'Send SMS'),
        ('CREATE_TASK', 'Create Task'),
        ('ASSIGN_AGENT', 'Assign to Agent'),
        ('UPDATE_LEAD_STATUS', 'Update Lead Status'),
        ('UPDATE_OPPORTUNITY_STAGE', 'Update Opportunity Stage'),
        ('ADD_TAG', 'Add Tag'),
        ('NOTIFY_AGENT', 'Notify Agent'),
        ('WEBHOOK', 'Trigger Webhook'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Rule identity
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Trigger
    trigger_event = models.CharField(max_length=30, choices=TRIGGER_EVENTS)
    trigger_conditions = models.JSONField(
        default=dict,
        help_text="Conditions that must be met: {field: value, operator: 'eq'|'gt'|'lt'|'contains'}"
    )
    
    # Action
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    action_config = models.JSONField(
        default=dict,
        help_text="Action configuration: {template_id, channel_id, delay_minutes, etc.}"
    )
    
    # Template (for message actions)
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='automation_rules'
    )
    
    # Channel (for message actions)
    social_channel = models.ForeignKey(
        SocialChannel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='automation_rules'
    )
    
    # Timing
    delay_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Wait time before executing action"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metrics
    times_triggered = models.PositiveIntegerField(default=0)
    times_executed = models.PositiveIntegerField(default=0)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['campus', 'trigger_event', 'name']
        verbose_name = 'Automation Rule'
        verbose_name_plural = 'Automation Rules'
    
    def __str__(self):
        return f"{self.name} ({self.get_trigger_event_display()})"


class AutomationExecution(models.Model):
    """
    Log of automation rule executions.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SCHEDULED', 'Scheduled'),
        ('EXECUTING', 'Executing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('SKIPPED', 'Skipped'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    rule = models.ForeignKey(
        AutomationRule,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    
    # Context
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='automation_executions'
    )
    opportunity = models.ForeignKey(
        'crm.Opportunity',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='automation_executions'
    )
    trigger_data = models.JSONField(default=dict)
    
    # Timing
    triggered_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    result = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['rule', 'status']),
            models.Index(fields=['scheduled_for', 'status']),
        ]
        verbose_name = 'Automation Execution'
        verbose_name_plural = 'Automation Executions'
    
    def __str__(self):
        return f"{self.rule.name} - {self.get_status_display()}"
