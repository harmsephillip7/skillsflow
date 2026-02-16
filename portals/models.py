"""
Portals app models
Portal configuration, permissions, and PWA settings for different user types
"""
from django.db import models
from core.models import AuditedModel


class PortalConfiguration(models.Model):
    """
    Portal configuration for different user types
    """
    PORTAL_TYPES = [
        ('LEARNER', 'Learner Portal'),
        ('STAFF', 'Staff Portal'),
        ('FACILITATOR', 'Facilitator Portal'),
        ('ASSESSOR', 'Assessor Portal'),
        ('EMPLOYER', 'Employer Portal'),
        ('CORPORATE', 'Corporate Client Portal'),
    ]
    
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='portal_configs'
    )
    
    portal_type = models.CharField(max_length=20, choices=PORTAL_TYPES)
    
    # Branding
    name = models.CharField(max_length=100)
    tagline = models.CharField(max_length=200, blank=True)
    logo = models.ImageField(upload_to='portal_logos/', blank=True)
    favicon = models.ImageField(upload_to='portal_favicons/', blank=True)
    
    # Theme colors
    primary_color = models.CharField(max_length=7, default='#1a56db')  # Hex
    secondary_color = models.CharField(max_length=7, default='#7e3af2')
    accent_color = models.CharField(max_length=7, default='#0e9f6e')
    
    # URLs
    custom_domain = models.CharField(max_length=100, blank=True)
    base_path = models.CharField(max_length=50, default='/')
    
    # Features
    enable_notifications = models.BooleanField(default=True)
    enable_messaging = models.BooleanField(default=True)
    enable_calendar = models.BooleanField(default=True)
    enable_documents = models.BooleanField(default=True)
    
    # PWA
    pwa_enabled = models.BooleanField(default=True)
    pwa_name = models.CharField(max_length=100, blank=True)
    pwa_short_name = models.CharField(max_length=20, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['brand', 'portal_type']
        verbose_name = 'Portal Configuration'
        verbose_name_plural = 'Portal Configurations'
    
    def __str__(self):
        return f"{self.brand.code} - {self.get_portal_type_display()}"


class PortalWidget(models.Model):
    """
    Dashboard widgets available in portals
    """
    WIDGET_TYPES = [
        ('PROGRESS', 'Progress Overview'),
        ('CALENDAR', 'Calendar/Schedule'),
        ('ANNOUNCEMENTS', 'Announcements'),
        ('QUICK_LINKS', 'Quick Links'),
        ('DOCUMENTS', 'Recent Documents'),
        ('GRADES', 'Grades Summary'),
        ('ATTENDANCE', 'Attendance Summary'),
        ('STATS', 'Statistics'),
        ('NOTIFICATIONS', 'Notifications'),
        ('TASKS', 'Tasks/To-Do'),
    ]
    
    portal = models.ForeignKey(
        PortalConfiguration,
        on_delete=models.CASCADE,
        related_name='widgets'
    )
    
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    title = models.CharField(max_length=100)
    
    # Layout
    position = models.PositiveIntegerField(default=0)
    width = models.CharField(max_length=20, default='col-span-1')  # Tailwind grid
    
    # Settings
    settings = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['portal', 'position']
        verbose_name = 'Portal Widget'
        verbose_name_plural = 'Portal Widgets'
    
    def __str__(self):
        return f"{self.portal} - {self.title}"


class PortalMenuItem(models.Model):
    """
    Navigation menu items for portals
    """
    portal = models.ForeignKey(
        PortalConfiguration,
        on_delete=models.CASCADE,
        related_name='menu_items'
    )
    
    # Parent for nested menus
    parent = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='children'
    )
    
    title = models.CharField(max_length=50)
    icon = models.CharField(max_length=50, blank=True)  # Icon class name
    url = models.CharField(max_length=200)
    
    # Permissions required
    required_permissions = models.JSONField(default=list, blank=True)
    
    # Order
    position = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['portal', 'position']
        verbose_name = 'Portal Menu Item'
        verbose_name_plural = 'Portal Menu Items'
    
    def __str__(self):
        return f"{self.portal} - {self.title}"


class Announcement(AuditedModel):
    """
    Portal announcements
    """
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    AUDIENCE_CHOICES = [
        ('ALL', 'All Users'),
        ('LEARNERS', 'All Learners'),
        ('STAFF', 'All Staff'),
        ('FACILITATORS', 'Facilitators'),
        ('ASSESSORS', 'Assessors'),
        ('SPECIFIC', 'Specific Selection'),
    ]
    
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='announcements'
    )
    campus = models.ForeignKey(
        'tenants.Campus',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='announcements'
    )
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Audience
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='ALL')
    
    # Specific audience (if audience = 'SPECIFIC')
    target_qualifications = models.ManyToManyField(
        'academics.Qualification',
        blank=True,
        related_name='announcements'
    )
    target_cohorts = models.ManyToManyField(
        'logistics.Cohort',
        blank=True,
        related_name='announcements'
    )
    
    # Display
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    is_pinned = models.BooleanField(default=False)
    
    # Scheduling
    publish_at = models.DateTimeField()
    expire_at = models.DateTimeField(null=True, blank=True)
    
    is_published = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-is_pinned', '-priority', '-publish_at']
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
    
    def __str__(self):
        return self.title


class AnnouncementRead(models.Model):
    """
    Track which users have read announcements
    """
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='read_by'
    )
    user = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='announcements_read'
    )
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['announcement', 'user']
        verbose_name = 'Announcement Read'
        verbose_name_plural = 'Announcements Read'


class Notification(AuditedModel):
    """
    User notifications
    """
    NOTIFICATION_TYPES = [
        ('INFO', 'Information'),
        ('SUCCESS', 'Success'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('REMINDER', 'Reminder'),
    ]
    
    CATEGORIES = [
        ('ENROLLMENT', 'Enrollment'),
        ('ASSESSMENT', 'Assessment'),
        ('ATTENDANCE', 'Attendance'),
        ('DOCUMENT', 'Document'),
        ('PAYMENT', 'Payment'),
        ('SCHEDULE', 'Schedule'),
        ('SYSTEM', 'System'),
        ('MESSAGE', 'Message'),
    ]
    
    user = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='INFO')
    category = models.CharField(max_length=20, choices=CATEGORIES, default='SYSTEM')
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Link
    link_url = models.CharField(max_length=200, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Push notification
    push_sent = models.BooleanField(default=False)
    push_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
    
    def __str__(self):
        return f"{self.user} - {self.title}"


class NotificationPreference(models.Model):
    """
    User notification preferences
    """
    user = models.OneToOneField(
        'core.User',
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Email preferences
    email_enabled = models.BooleanField(default=True)
    email_enrollment = models.BooleanField(default=True)
    email_assessment = models.BooleanField(default=True)
    email_attendance = models.BooleanField(default=True)
    email_document = models.BooleanField(default=True)
    email_payment = models.BooleanField(default=True)
    email_schedule = models.BooleanField(default=True)
    
    # Push preferences
    push_enabled = models.BooleanField(default=True)
    push_enrollment = models.BooleanField(default=True)
    push_assessment = models.BooleanField(default=True)
    push_attendance = models.BooleanField(default=True)
    push_document = models.BooleanField(default=True)
    push_payment = models.BooleanField(default=True)
    push_schedule = models.BooleanField(default=True)
    
    # SMS preferences
    sms_enabled = models.BooleanField(default=False)
    sms_urgent_only = models.BooleanField(default=True)
    
    # WhatsApp preferences
    whatsapp_enabled = models.BooleanField(default=False)
    
    # Digest
    digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ('NONE', 'No Digest'),
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
        ],
        default='DAILY'
    )
    
    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Notification Preferences - {self.user}"


class PushSubscription(models.Model):
    """
    Web push notification subscriptions
    """
    user = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='push_subscriptions'
    )
    
    # Push subscription details
    endpoint = models.URLField(max_length=500)
    p256dh_key = models.CharField(max_length=200)
    auth_key = models.CharField(max_length=50)
    
    # Device info
    user_agent = models.CharField(max_length=300, blank=True)
    device_type = models.CharField(max_length=20, blank=True)  # web, mobile, tablet
    
    # Status
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Push Subscription'
        verbose_name_plural = 'Push Subscriptions'
    
    def __str__(self):
        return f"{self.user} - {self.device_type}"


class PortalMessage(AuditedModel):
    """
    Internal messaging between users
    """
    sender = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    
    subject = models.CharField(max_length=200)
    body = models.TextField()
    
    # Thread
    parent = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Deletion (soft delete per user)
    sender_deleted = models.BooleanField(default=False)
    recipient_deleted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Portal Message'
        verbose_name_plural = 'Portal Messages'
    
    def __str__(self):
        return f"{self.sender} -> {self.recipient}: {self.subject}"


class MessageAttachment(models.Model):
    """
    Attachments for portal messages
    """
    message = models.ForeignKey(
        PortalMessage,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    
    file = models.FileField(upload_to='message_attachments/')
    filename = models.CharField(max_length=200)
    file_size = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=100)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Message Attachment'
        verbose_name_plural = 'Message Attachments'
    
    def __str__(self):
        return f"{self.message} - {self.filename}"


class UserActivity(models.Model):
    """
    Track user activity in portals for analytics
    """
    user = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='portal_activities'
    )
    
    # Activity
    activity_type = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    
    # Context
    portal = models.ForeignKey(
        PortalConfiguration,
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    url_path = models.CharField(max_length=200, blank=True)
    
    # Related object (generic)
    related_model = models.CharField(max_length=100, blank=True)
    related_id = models.PositiveIntegerField(null=True, blank=True)
    
    # Request info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['activity_type', '-timestamp']),
        ]
        verbose_name = 'User Activity'
        verbose_name_plural = 'User Activities'
    
    def __str__(self):
        return f"{self.user} - {self.activity_type} - {self.timestamp}"
