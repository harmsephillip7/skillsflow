"""
Tenants app models - Multi-tenancy support
Brand and Campus models with Row-Level Security
"""
import uuid
from django.db import models
from core.models import AuditedModel


class Brand(models.Model):
    """
    Brand represents a distinct training brand/institution
    Supports 8+ brands as per requirements
    """
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    legal_name = models.CharField(max_length=200, blank=True)
    
    # Branding
    logo = models.ImageField(upload_to='brands/logos/', null=True, blank=True)
    favicon = models.ImageField(upload_to='brands/favicons/', null=True, blank=True)
    primary_color = models.CharField(max_length=7, default='#007bff')  # Hex color
    secondary_color = models.CharField(max_length=7, default='#6c757d')
    
    # Accreditation
    accreditation_number = models.CharField(max_length=50, blank=True)
    seta_registration = models.CharField(max_length=50, blank=True)
    
    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_active_campuses(self):
        return self.campuses.filter(is_active=True)
    
    def get_social_account(self, platform):
        """Get the social account for a specific platform."""
        return self.social_accounts.filter(platform=platform, is_active=True).first()
    
    def get_meta_account(self):
        """Get the Meta (Facebook/Instagram) account."""
        return self.get_social_account('META')
    
    def get_tiktok_account(self):
        """Get the TikTok account."""
        return self.get_social_account('TIKTOK')
    
    def get_google_analytics(self):
        """Get the Google Analytics account."""
        return self.get_social_account('GOOGLE_ANALYTICS')


class Campus(models.Model):
    """
    Campus represents a physical or virtual location within a brand
    Supports 15+ campuses as per requirements
    """
    CAMPUS_TYPES = [
        ('HEAD_OFFICE', 'Head Office'),
        ('CAMPUS', 'Campus'),
        ('SATELLITE', 'Satellite Office'),
        ('VIRTUAL', 'Virtual Campus'),
    ]
    
    brand = models.ForeignKey(
        Brand, 
        on_delete=models.PROTECT, 
        related_name='campuses'
    )
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    campus_type = models.CharField(max_length=20, choices=CAMPUS_TYPES, default='CAMPUS')
    region = models.CharField(max_length=50, blank=True)  # For regional manager views
    
    # Address
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    suburb = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=50, default='South Africa')
    
    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Coordinates (for mapping)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Capacity Settings (Admin-configured)
    max_learner_capacity = models.PositiveIntegerField(
        default=300,
        help_text="Maximum total learners this campus can handle (including off-site learners)"
    )
    on_campus_capacity = models.PositiveIntegerField(
        default=150,
        help_text="Maximum learners that can be on-campus at any time (physical seats)"
    )
    target_utilization = models.PositiveIntegerField(
        default=85,
        help_text="Target utilization percentage (e.g., 85 = 85%)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['brand', 'name']
        verbose_name_plural = 'Campuses'
    
    def __str__(self):
        return f"{self.brand.code} - {self.name}"
    
    @property
    def current_total_learners(self):
        """Get current total active learners for this campus"""
        from academics.models import Enrollment
        return Enrollment.objects.filter(
            campus=self,
            status__in=['ENROLLED', 'ACTIVE']
        ).count()
    
    @property
    def current_on_campus_learners(self):
        """Get learners currently on campus (ON_CAMPUS delivery mode)"""
        from intakes.models import Intake, IntakeEnrollment
        on_campus_intakes = Intake.objects.filter(
            campus=self,
            delivery_mode='ON_CAMPUS',
            status__in=['ACTIVE', 'ENROLLMENT_OPEN']
        )
        return IntakeEnrollment.objects.filter(
            intake__in=on_campus_intakes,
            status__in=['ENROLLED', 'ACTIVE']
        ).count()
    
    @property
    def total_utilization_percentage(self):
        """Calculate total utilization as percentage"""
        if self.max_learner_capacity == 0:
            return 0
        return round((self.current_total_learners / self.max_learner_capacity) * 100, 1)
    
    @property
    def on_campus_utilization_percentage(self):
        """Calculate on-campus utilization as percentage"""
        if self.on_campus_capacity == 0:
            return 0
        return round((self.current_on_campus_learners / self.on_campus_capacity) * 100, 1)


class TenantAwareModel(AuditedModel):
    """
    Abstract base class for all tenant-scoped models
    Provides automatic campus filtering via middleware
    """
    campus = models.ForeignKey(
        Campus, 
        on_delete=models.PROTECT,
        related_name='%(class)s_items'
    )
    
    class Meta:
        abstract = True
    
    @property
    def brand(self):
        """Get the brand through campus"""
        return self.campus.brand


class BrandSocialAccount(AuditedModel):
    """
    Links a brand to a social media platform account.
    Single source of truth for platform credentials used by both analytics AND messaging.
    """
    PLATFORM_CHOICES = [
        ('META', 'Meta (Facebook + Instagram)'),
        ('TIKTOK', 'TikTok'),
        ('GOOGLE_ANALYTICS', 'Google Analytics 4'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name='social_accounts'
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    
    # Connection reference (OAuth tokens stored here)
    connection = models.OneToOneField(
        'integrations.IntegrationConnection',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='social_account'
    )
    
    # Platform-specific account IDs
    # Meta (Facebook + Instagram)
    facebook_page_id = models.CharField(max_length=50, blank=True, help_text="Facebook Page ID")
    facebook_page_name = models.CharField(max_length=200, blank=True)
    facebook_page_access_token = models.TextField(blank=True, help_text="Long-lived Page Access Token")
    instagram_business_id = models.CharField(max_length=50, blank=True, help_text="Instagram Business Account ID")
    instagram_username = models.CharField(max_length=100, blank=True)
    
    # TikTok
    tiktok_business_id = models.CharField(max_length=50, blank=True, help_text="TikTok Business Center ID")
    tiktok_advertiser_id = models.CharField(max_length=50, blank=True, help_text="TikTok Advertiser ID")
    tiktok_username = models.CharField(max_length=100, blank=True)
    
    # Google Analytics
    ga4_property_id = models.CharField(max_length=50, blank=True, help_text="GA4 Property ID (e.g., 123456789)")
    ga4_property_name = models.CharField(max_length=200, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=50, blank=True)
    sync_error = models.TextField(blank=True)
    
    # Permissions tracking (for phased messaging rollout)
    has_analytics_permission = models.BooleanField(default=False, help_text="Has permission to read analytics/insights")
    has_messaging_permission = models.BooleanField(default=False, help_text="Has permission to send/receive messages")
    messaging_approval_status = models.CharField(
        max_length=20,
        choices=[
            ('NOT_REQUIRED', 'Not Required'),
            ('PENDING', 'Pending Approval'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected'),
        ],
        default='NOT_REQUIRED',
        help_text="Meta App Review status for messaging"
    )
    
    # Historical data backfill tracking
    backfill_complete = models.BooleanField(default=False)
    backfill_start_date = models.DateField(null=True, blank=True, help_text="Earliest date with data")
    
    class Meta:
        unique_together = ['brand', 'platform']
        verbose_name = 'Brand Social Account'
        verbose_name_plural = 'Brand Social Accounts'
        ordering = ['brand__name', 'platform']
    
    def __str__(self):
        return f"{self.brand.name} - {self.get_platform_display()}"
    
    @property
    def is_connected(self):
        """Check if the account is connected and active."""
        if self.platform == 'META':
            return bool(self.facebook_page_id or self.instagram_business_id)
        elif self.platform == 'TIKTOK':
            return bool(self.tiktok_business_id)
        elif self.platform == 'GOOGLE_ANALYTICS':
            return bool(self.ga4_property_id)
        return False
    
    @property
    def display_name(self):
        """Get a display name for the connected account."""
        if self.platform == 'META':
            if self.facebook_page_name and self.instagram_username:
                return f"{self.facebook_page_name} / @{self.instagram_username}"
            return self.facebook_page_name or f"@{self.instagram_username}" or "Not connected"
        elif self.platform == 'TIKTOK':
            return f"@{self.tiktok_username}" if self.tiktok_username else "Not connected"
        elif self.platform == 'GOOGLE_ANALYTICS':
            return self.ga4_property_name or self.ga4_property_id or "Not connected"
        return "Unknown"
