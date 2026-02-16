"""
CRM app models
Lead management, pipeline, WhatsApp integration, and SETA funding matching
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import AuditedModel, User
from tenants.models import TenantAwareModel, Campus


# =============================================================================
# PIPELINE MODELS - Dynamic, configurable pipelines per learner type
# =============================================================================

class Pipeline(TenantAwareModel):
    """
    Configurable sales pipeline for different learner types.
    Each pipeline has its own stages and communication cadence.
    Examples: "Grade 9 Future Learner", "Grade 12 Ready Now", "Adult Career Changer"
    """
    LEARNER_TYPE_CHOICES = [
        ('SCHOOL_LEAVER_FUTURE', 'School Leaver - Future (Gr9-11)'),
        ('SCHOOL_LEAVER_READY', 'School Leaver - Ready Now (Gr12/Matric)'),
        ('ADULT', 'Adult Learner'),
        ('CORPORATE', 'Corporate/Employer Referral'),
        ('REFERRAL', 'General Referral'),
    ]
    
    FREQUENCY_CHOICES = [
        (7, 'Weekly'),
        (14, 'Bi-weekly'),
        (30, 'Monthly'),
        (90, 'Quarterly'),
        (180, 'Bi-annually'),
        (365, 'Annually'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    learner_type = models.CharField(max_length=30, choices=LEARNER_TYPE_CHOICES)
    
    # Default communication frequency for this pipeline (can be overridden per stage)
    default_communication_frequency_days = models.PositiveIntegerField(
        choices=FREQUENCY_CHOICES,
        default=14,
        help_text="Default days between automated communications"
    )
    
    # Whether this is the default pipeline for the learner type
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Pipeline color for UI
    color = models.CharField(max_length=7, default='#3B82F6')
    icon = models.CharField(max_length=50, default='fa-user-graduate')
    
    class Meta:
        ordering = ['campus', 'learner_type', 'name']
        verbose_name = 'Pipeline'
        verbose_name_plural = 'Pipelines'
    
    def __str__(self):
        return f"{self.name} ({self.get_learner_type_display()})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default pipeline per learner type per campus
        if self.is_default:
            Pipeline.objects.filter(
                campus=self.campus,
                learner_type=self.learner_type,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def stage_count(self):
        return self.stages.count()
    
    @property
    def active_leads_count(self):
        return Lead.objects.filter(
            pipeline=self,
            status__in=['NEW', 'CONTACTED', 'QUALIFIED', 'PROPOSAL', 'NEGOTIATION']
        ).count()


class PipelineStage(models.Model):
    """
    A stage within a pipeline.
    Each stage can have its own communication frequency and blueprint actions.
    """
    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.CASCADE,
        related_name='stages'
    )
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, help_text="Internal code for stage")
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    
    # Stage configuration
    expected_duration_days = models.PositiveIntegerField(
        default=7,
        help_text="Expected time a lead should spend in this stage"
    )
    
    # Communication frequency override (null = use pipeline default)
    communication_frequency_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Override pipeline's default communication frequency for this stage"
    )
    
    # Stage type for special handling
    is_entry_stage = models.BooleanField(default=False, help_text="New leads start here")
    is_won_stage = models.BooleanField(default=False, help_text="Indicates successful conversion")
    is_lost_stage = models.BooleanField(default=False, help_text="Indicates lost lead")
    is_nurture_stage = models.BooleanField(default=False, help_text="Long-term nurture (e.g., future learners)")
    
    # UI
    color = models.CharField(max_length=7, default='#6B7280')
    icon = models.CharField(max_length=50, blank=True)
    
    # Probability for forecasting
    win_probability = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Likelihood of conversion at this stage (0-100%)"
    )
    
    class Meta:
        ordering = ['pipeline', 'order']
        unique_together = [['pipeline', 'code']]
        verbose_name = 'Pipeline Stage'
        verbose_name_plural = 'Pipeline Stages'
    
    def __str__(self):
        return f"{self.pipeline.name} - {self.name}"
    
    @property
    def effective_communication_frequency(self):
        """Get the communication frequency, falling back to pipeline default."""
        return self.communication_frequency_days or self.pipeline.default_communication_frequency_days
    
    @property
    def leads_count(self):
        return Lead.objects.filter(current_stage=self).count()


class StageBlueprint(models.Model):
    """
    Blueprint of recommended actions, tasks, and communication templates for a stage.
    Non-blocking - serves as guidance and triggers automations.
    """
    stage = models.OneToOneField(
        PipelineStage,
        on_delete=models.CASCADE,
        related_name='blueprint'
    )
    
    # Recommended actions (displayed to sales agent)
    recommended_actions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of recommended actions: [{'action': 'Call lead', 'description': '...'}]"
    )
    
    # Auto-tasks to create when lead enters this stage
    auto_tasks = models.JSONField(
        default=list,
        blank=True,
        help_text="Tasks to auto-create: [{'title': 'Send welcome email', 'due_days': 1}]"
    )
    
    # Communication templates to use at this stage
    communication_templates = models.ManyToManyField(
        'crm.MessageTemplate',
        blank=True,
        related_name='stage_blueprints',
        help_text="Message templates for automated communications"
    )
    
    # Default message for this stage (for quick send)
    default_template = models.ForeignKey(
        'crm.MessageTemplate',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='default_for_stages'
    )
    
    # Agent notification settings
    notify_agent_on_entry = models.BooleanField(default=True)
    notify_agent_on_overdue = models.BooleanField(default=True)
    overdue_notification_days = models.PositiveIntegerField(
        default=3,
        help_text="Days after expected duration to send overdue notification"
    )
    
    # Automation flags
    auto_send_initial_communication = models.BooleanField(
        default=False,
        help_text="Automatically send initial communication when lead enters stage"
    )
    auto_schedule_follow_up = models.BooleanField(
        default=True,
        help_text="Automatically schedule next communication based on frequency"
    )
    
    class Meta:
        verbose_name = 'Stage Blueprint'
        verbose_name_plural = 'Stage Blueprints'
    
    def __str__(self):
        return f"Blueprint: {self.stage}"


class CommunicationCycle(AuditedModel):
    """
    Tracks scheduled automated communications for a lead.
    Manages the nurture cycle with configurable frequency.
    """
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('SKIPPED', 'Skipped'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,
        related_name='communication_cycles'
    )
    
    # Template to use
    template = models.ForeignKey(
        'crm.MessageTemplate',
        on_delete=models.SET_NULL,
        null=True,
        related_name='scheduled_communications'
    )
    
    # Scheduling
    scheduled_at = models.DateTimeField(db_index=True)
    frequency_days = models.PositiveIntegerField(help_text="Days until next communication")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Communication details
    channel_used = models.CharField(max_length=20, blank=True, help_text="WHATSAPP, EMAIL, SMS")
    message_id = models.CharField(max_length=200, blank=True, help_text="Reference to sent message")
    
    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    # Cycle management
    is_active = models.BooleanField(default=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    pause_reason = models.CharField(max_length=200, blank=True)
    
    class Meta:
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['lead', 'is_active']),
        ]
        verbose_name = 'Communication Cycle'
        verbose_name_plural = 'Communication Cycles'
    
    def __str__(self):
        return f"{self.lead} - {self.scheduled_at.strftime('%Y-%m-%d')} ({self.status})"


class PreApprovalLetter(AuditedModel):
    """
    Pre-approval letter sent to prospective learners.
    Generated when sales confirms interest and entry requirement eligibility.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('VIEWED', 'Viewed'),
        ('ACCEPTED', 'Accepted - Started Application'),
        ('EXPIRED', 'Expired'),
        ('REVOKED', 'Revoked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,
        related_name='pre_approval_letters'
    )
    
    # What they're pre-approved for
    qualification = models.ForeignKey(
        'academics.Qualification',
        on_delete=models.PROTECT,
        related_name='pre_approval_letters'
    )
    intake = models.ForeignKey(
        'intakes.Intake',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pre_approval_letters',
        help_text="Specific intake if applicable"
    )
    
    # Letter details
    letter_number = models.CharField(max_length=50, unique=True, help_text="PAL-2026-00001")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Validity
    issued_date = models.DateField(auto_now_add=True)
    valid_until = models.DateField(help_text="Pre-approval expiry date")
    
    # Entry requirements confirmation
    entry_requirements_confirmed = models.BooleanField(
        default=False,
        help_text="Sales agent confirmed learner meets/will meet entry requirements"
    )
    entry_requirements_notes = models.TextField(
        blank=True,
        help_text="Notes on how entry requirements will be met"
    )
    
    # Sending
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_via = models.CharField(max_length=20, blank=True, help_text="EMAIL, WHATSAPP, etc.")
    sent_to_contact = models.CharField(max_length=200, blank=True, help_text="Email/phone sent to")
    
    # Tracking
    viewed_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    
    # Parent/Guardian notification (for minors)
    parent_notified_at = models.DateTimeField(null=True, blank=True)
    parent_sent_to = models.CharField(max_length=200, blank=True, help_text="Parent email/phone sent to")
    parent_consent_given = models.BooleanField(default=False)
    parent_consent_at = models.DateTimeField(null=True, blank=True)
    parent_consent_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Learner acceptance (from portal)
    learner_accepted = models.BooleanField(default=False)
    learner_accepted_at = models.DateTimeField(null=True, blank=True)
    learner_accepted_ip = models.GenericIPAddressField(null=True, blank=True)
    learner_accepted_terms = models.BooleanField(default=False)
    
    # Application link
    application = models.OneToOneField(
        'crm.Application',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pre_approval_letter'
    )
    
    # PDF storage
    pdf_file = models.FileField(
        upload_to='pre_approval_letters/',
        null=True, blank=True
    )
    
    # Confirmation by sales agent
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='pre_approvals_confirmed'
    )
    confirmation_notes = models.TextField(blank=True, help_text="Agent notes on why pre-approved")
    
    class Meta:
        ordering = ['-issued_date']
        verbose_name = 'Pre-Approval Letter'
        verbose_name_plural = 'Pre-Approval Letters'
    
    def __str__(self):
        return f"{self.letter_number} - {self.lead.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.letter_number:
            # Generate letter number: PAL-YYYY-NNNNN
            from datetime import date
            year = date.today().year
            last_letter = PreApprovalLetter.objects.filter(
                letter_number__startswith=f'PAL-{year}-'
            ).order_by('-letter_number').first()
            
            if last_letter:
                last_num = int(last_letter.letter_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.letter_number = f'PAL-{year}-{new_num:05d}'
        
        super().save(*args, **kwargs)
    
    def mark_viewed(self):
        """Track when letter is viewed."""
        self.view_count += 1
        if not self.viewed_at:
            self.viewed_at = timezone.now()
            if self.status == 'SENT':
                self.status = 'VIEWED'
        self.save(update_fields=['view_count', 'viewed_at', 'status'])
    
    def start_application(self):
        """Create application from this pre-approval."""
        if self.application:
            return self.application
        
        from crm.models import Application, Opportunity
        
        # Create opportunity first (required for application)
        opportunity, _ = Opportunity.objects.get_or_create(
            lead=self.lead,
            qualification=self.qualification,
            defaults={
                'name': f"{self.lead.get_full_name()} - {self.qualification.name}",
                'campus': self.lead.campus,
                'stage': 'COMMITTED',
                'probability': 80,
                'intake': self.intake,
            }
        )
        
        # Create application
        application = Application.objects.create(
            opportunity=opportunity,
            campus=self.lead.campus,
            status='DRAFT',
        )
        
        self.application = application
        self.status = 'ACCEPTED'
        self.save(update_fields=['application', 'status'])
        
        return application
    
    def get_portal_url(self):
        """Get the public portal URL for this pre-approval letter."""
        from django.urls import reverse
        return reverse('crm:pre_approval_portal', kwargs={'token': str(self.id)})
    
    def get_full_portal_url(self, request=None):
        """Get the full absolute URL for the portal."""
        from django.conf import settings
        portal_path = self.get_portal_url()
        if request:
            return request.build_absolute_uri(portal_path)
        # Fallback to settings or default
        base_url = getattr(settings, 'SITE_URL', 'https://skillsflow.co.za')
        return f"{base_url.rstrip('/')}{portal_path}"
    
    @property
    def is_portal_valid(self):
        """Check if the portal access is still valid (not expired or revoked)."""
        from datetime import date
        if self.status in ['EXPIRED', 'REVOKED']:
            return False
        if self.valid_until and self.valid_until < date.today():
            return False
        return True
    
    @property
    def requires_parent_consent(self):
        """Check if this pre-approval requires parent consent (minor learner)."""
        return self.lead.is_minor if hasattr(self.lead, 'is_minor') else False
    
    @property
    def can_start_application(self):
        """Check if learner can start application from this pre-approval."""
        if not self.is_portal_valid:
            return False
        if self.application:  # Already has application
            return False
        if self.requires_parent_consent and not self.parent_consent_given:
            return False
        return True
    
    def record_learner_acceptance(self, ip_address=None, terms_accepted=True):
        """Record that the learner has accepted the pre-approval."""
        self.learner_accepted = True
        self.learner_accepted_at = timezone.now()
        self.learner_accepted_ip = ip_address
        self.learner_accepted_terms = terms_accepted
        self.save(update_fields=[
            'learner_accepted', 'learner_accepted_at', 
            'learner_accepted_ip', 'learner_accepted_terms'
        ])
    
    def record_parent_consent(self, ip_address=None):
        """Record that the parent has given consent."""
        self.parent_consent_given = True
        self.parent_consent_at = timezone.now()
        self.parent_consent_ip = ip_address
        self.save(update_fields=['parent_consent_given', 'parent_consent_at', 'parent_consent_ip'])


# =============================================================================
# ENGAGEMENT & NOTIFICATION MODELS
# =============================================================================

class LeadEngagement(AuditedModel):
    """
    Tracks client engagement events (quote viewed, email opened, link clicked).
    Used to calculate engagement score and trigger agent notifications.
    """
    EVENT_TYPES = [
        ('QUOTE_VIEWED', 'Quote Viewed'),
        ('QUOTE_ACCEPTED', 'Quote Accepted'),
        ('QUOTE_REJECTED', 'Quote Rejected'),
        ('EMAIL_OPENED', 'Email Opened'),
        ('EMAIL_CLICKED', 'Email Link Clicked'),
        ('WHATSAPP_READ', 'WhatsApp Read'),
        ('WEBSITE_VISIT', 'Website Visit'),
        ('FORM_SUBMITTED', 'Form Submitted'),
        ('DOCUMENT_UPLOADED', 'Document Uploaded'),
        ('CALL_ANSWERED', 'Call Answered'),
        ('CALL_MISSED', 'Call Missed'),
        ('MEETING_ATTENDED', 'Meeting Attended'),
        ('MEETING_MISSED', 'Meeting Missed'),
    ]
    
    SCORE_VALUES = {
        'QUOTE_VIEWED': 10,
        'QUOTE_ACCEPTED': 50,
        'QUOTE_REJECTED': -5,
        'EMAIL_OPENED': 5,
        'EMAIL_CLICKED': 10,
        'WHATSAPP_READ': 3,
        'WEBSITE_VISIT': 5,
        'FORM_SUBMITTED': 15,
        'DOCUMENT_UPLOADED': 20,
        'CALL_ANSWERED': 15,
        'CALL_MISSED': -2,
        'MEETING_ATTENDED': 25,
        'MEETING_MISSED': -10,
    }
    
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,
        related_name='engagements'
    )
    
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    event_timestamp = models.DateTimeField(default=timezone.now)
    
    # Event metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional event data: {quote_id, email_id, page_url, etc.}"
    )
    
    # Source tracking
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Score contribution
    score_value = models.IntegerField(default=0)
    
    # Agent notification
    agent_notified = models.BooleanField(default=False)
    agent_notified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-event_timestamp']
        indexes = [
            models.Index(fields=['lead', 'event_type']),
            models.Index(fields=['event_timestamp']),
        ]
        verbose_name = 'Lead Engagement'
        verbose_name_plural = 'Lead Engagements'
    
    def __str__(self):
        return f"{self.lead} - {self.get_event_type_display()}"
    
    def save(self, *args, **kwargs):
        # Set score value based on event type
        if not self.score_value:
            self.score_value = self.SCORE_VALUES.get(self.event_type, 0)
        super().save(*args, **kwargs)
        
        # Update lead's engagement score and last engagement
        self.lead.last_engagement_at = self.event_timestamp
        self.lead.engagement_score = (self.lead.engagement_score or 0) + self.score_value
        self.lead.save(update_fields=['last_engagement_at', 'engagement_score', 'updated_at'])


class AgentNotification(AuditedModel):
    """
    In-app notifications for sales agents.
    Triggered by engagement events, stage transitions, overdue leads, etc.
    """
    NOTIFICATION_TYPES = [
        ('ENGAGEMENT', 'Client Engagement'),
        ('STAGE_CHANGE', 'Stage Change'),
        ('NEW_LEAD', 'New Lead Assigned'),
        ('LEAD_OVERDUE', 'Lead Overdue'),
        ('FOLLOW_UP_DUE', 'Follow-up Due'),
        ('QUOTE_ACTIVITY', 'Quote Activity'),
        ('COMMUNICATION_SCHEDULED', 'Communication Scheduled'),
        ('TASK_ASSIGNED', 'Task Assigned'),
        ('TASK_OVERDUE', 'Task Overdue'),
        ('SYSTEM', 'System Notification'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    agent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='crm_notifications'
    )
    
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    
    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='agent_notifications'
    )
    engagement = models.ForeignKey(
        LeadEngagement,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='notifications'
    )
    
    # Action URL
    action_url = models.CharField(max_length=500, blank=True)
    action_label = models.CharField(max_length=50, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent', 'is_read']),
            models.Index(fields=['agent', 'notification_type']),
        ]
        verbose_name = 'Agent Notification'
        verbose_name_plural = 'Agent Notifications'
    
    def __str__(self):
        return f"{self.agent} - {self.title}"
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
    
    def dismiss(self):
        self.is_dismissed = True
        self.dismissed_at = timezone.now()
        self.save(update_fields=['is_dismissed', 'dismissed_at'])


# =============================================================================
# EXISTING MODELS
# =============================================================================

class LeadSource(models.Model):
    """
    Source of leads (WhatsApp, Website, Walk-in, etc.)
    """
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Lead Source'
        verbose_name_plural = 'Lead Sources'
    
    def __str__(self):
        return self.name


class Lead(TenantAwareModel):
    """
    Sales lead/prospect
    Full pipeline from inquiry to enrollment
    Supports school leaver tracking from age 16+
    """
    STATUS_CHOICES = [
        ('NEW', 'New Inquiry'),
        ('CONTACTED', 'Contacted'),
        ('QUALIFIED', 'Qualified'),
        ('PROPOSAL', 'Proposal Sent'),
        ('NEGOTIATION', 'Negotiation'),
        ('REGISTERED', 'Registered'),
        ('ENROLLED', 'Enrolled'),
        ('LOST', 'Lost'),
        ('ALUMNI', 'Alumni'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    LEAD_TYPE_CHOICES = [
        ('SCHOOL_LEAVER', 'School Leaver'),
        ('ADULT', 'Adult Learner'),
        ('CORPORATE', 'Corporate/Employer'),
        ('REFERRAL', 'Referral'),
    ]
    
    CONTACT_METHOD_CHOICES = [
        ('WHATSAPP', 'WhatsApp'),
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('PHONE', 'Phone Call'),
    ]
    
    # Contact Info - Only first_name, last_name, and ONE contact required
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(blank=True, help_text="Email address (at least one contact method required)")
    phone = models.CharField(max_length=20, blank=True, help_text="Phone number (at least one contact method required)")
    phone_secondary = models.CharField(max_length=20, blank=True)
    
    # Contact Preferences
    preferred_contact_method = models.CharField(
        max_length=20, 
        choices=CONTACT_METHOD_CHOICES, 
        default='WHATSAPP',
        help_text="Primary contact method for automated communications"
    )
    fallback_contact_methods = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered list of fallback contact methods: ['EMAIL', 'SMS']"
    )
    
    # School Leaver Age Tracking
    date_of_birth = models.DateField(null=True, blank=True, help_text="For school leavers - track age progression")
    lead_type = models.CharField(max_length=20, choices=LEAD_TYPE_CHOICES, default='ADULT')
    
    # ==========================================================================
    # LEARNER PROFILE FIELDS - Progressive capture for onboarding
    # ==========================================================================
    
    # Demographics
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    TITLE_CHOICES = [
        ('MR', 'Mr'),
        ('MS', 'Ms'),
        ('MRS', 'Mrs'),
        ('DR', 'Dr'),
        ('PROF', 'Prof'),
    ]
    
    RACE_CHOICES = [
        ('B', 'Black'),
        ('W', 'White'),
        ('C', 'Coloured'),
        ('I', 'Indian/Asian'),
        ('O', 'Other'),
    ]
    
    title = models.CharField(max_length=10, choices=TITLE_CHOICES, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    id_number = models.CharField(max_length=13, blank=True, help_text="SA ID Number (13 digits)")
    race = models.CharField(max_length=1, choices=RACE_CHOICES, blank=True)
    
    # Languages
    LANGUAGE_CHOICES = [
        ('ENGLISH', 'English'),
        ('AFRIKAANS', 'Afrikaans'),
        ('ZULU', 'isiZulu'),
        ('XHOSA', 'isiXhosa'),
        ('SOTHO', 'Sesotho'),
        ('TSWANA', 'Setswana'),
        ('PEDI', 'Sepedi'),
        ('VENDA', 'Tshivenda'),
        ('TSONGA', 'Xitsonga'),
        ('SWATI', 'siSwati'),
        ('NDEBELE', 'isiNdebele'),
        ('OTHER', 'Other'),
    ]
    
    first_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, blank=True)
    second_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, blank=True)
    
    # English Proficiency
    PROFICIENCY_CHOICES = [
        ('POOR', 'Poor'),
        ('GOOD', 'Good'),
        ('EXCELLENT', 'Excellent'),
    ]
    
    english_speaking = models.CharField(max_length=10, choices=PROFICIENCY_CHOICES, blank=True)
    english_reading = models.CharField(max_length=10, choices=PROFICIENCY_CHOICES, blank=True)
    english_writing = models.CharField(max_length=10, choices=PROFICIENCY_CHOICES, blank=True)
    
    # Work & Employment
    WORK_STATUS_CHOICES = [
        ('EMPLOYED', 'Employed'),
        ('UNEMPLOYED', 'Unemployed'),
        ('STUDENT', 'Student'),
        ('SELF_EMPLOYED', 'Self-Employed'),
    ]
    
    work_status = models.CharField(max_length=20, choices=WORK_STATUS_CHOICES, blank=True)
    years_experience = models.PositiveIntegerField(null=True, blank=True, help_text="Years of work experience")
    
    # Education
    GRADE_CHOICES = [
        ('9', 'Grade 9'),
        ('10', 'Grade 10'),
        ('11', 'Grade 11'),
        ('12', 'Grade 12 / Matric'),
    ]
    
    highest_grade_passed = models.CharField(max_length=2, choices=GRADE_CHOICES, blank=True)
    last_school_attended = models.CharField(max_length=200, blank=True)
    tertiary_qualification = models.CharField(max_length=200, blank=True, help_text="Tertiary or other qualification")
    subjects_completed = models.TextField(blank=True, help_text="List of subjects completed")
    
    # Health & Medical
    has_disability = models.BooleanField(default=False)
    disability_description = models.TextField(blank=True)
    has_medical_conditions = models.BooleanField(default=False)
    medical_conditions = models.TextField(blank=True, help_text="Allergies, Epilepsy, etc.")
    
    # Personal
    MARITAL_STATUS_CHOICES = [
        ('SINGLE', 'Single'),
        ('MARRIED', 'Married'),
        ('DIVORCED', 'Divorced'),
        ('WIDOWED', 'Widowed'),
    ]
    
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES, blank=True)
    number_of_dependents = models.PositiveIntegerField(null=True, blank=True)
    
    # Payment Responsibility
    PAYMENT_RESPONSIBILITY_CHOICES = [
        ('SELF', 'Self'),
        ('EMPLOYER', 'Employer'),
        ('SPONSOR', 'Sponsor/Family'),
        ('BURSARY', 'Bursary/SETA'),
        ('NSFAS', 'NSFAS'),
        ('LOAN', 'Student Loan'),
    ]
    
    payment_responsibility = models.CharField(max_length=20, choices=PAYMENT_RESPONSIBILITY_CHOICES, blank=True)
    
    # Addresses (ForeignKey to reusable Address model)
    physical_address = models.ForeignKey(
        'learners.Address',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='leads_physical'
    )
    postal_address = models.ForeignKey(
        'learners.Address',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='leads_postal'
    )
    postal_same_as_physical = models.BooleanField(default=False)
    
    # ==========================================================================
    # END LEARNER PROFILE FIELDS
    # ==========================================================================
    
    # Parent/Guardian (for school leavers under 18) - LEGACY, use SecondaryContact
    parent_name = models.CharField(max_length=100, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    parent_email = models.EmailField(blank=True)
    parent_relationship = models.CharField(max_length=50, blank=True, help_text="e.g., Mother, Father, Guardian")
    
    # School Details (for school leavers)
    school_name = models.CharField(max_length=200, blank=True)
    grade = models.CharField(max_length=10, blank=True, help_text="e.g., Grade 11, Grade 12, Matric")
    expected_matric_year = models.PositiveIntegerField(null=True, blank=True)
    
    # WhatsApp
    whatsapp_number = models.CharField(max_length=20, blank=True)
    prefers_whatsapp = models.BooleanField(default=False)
    
    # Bulk Messaging Consent
    consent_bulk_messaging = models.BooleanField(default=False, help_text="Consent to receive monthly bulk messages")
    consent_date = models.DateTimeField(null=True, blank=True)
    unsubscribed = models.BooleanField(default=False)
    unsubscribed_date = models.DateTimeField(null=True, blank=True)
    
    # Lead Details
    source = models.ForeignKey(
        LeadSource, 
        on_delete=models.PROTECT, 
        related_name='leads'
    )
    qualification_interest = models.ForeignKey(
        'academics.Qualification', 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='interested_leads'
    )
    
    # SAQA/NQF fields for matching
    highest_qualification = models.CharField(max_length=50, blank=True)
    employment_status = models.CharField(max_length=50, blank=True)
    employer_name = models.CharField(max_length=200, blank=True)
    
    # Legacy Pipeline Status (kept for backward compatibility)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # NEW: Dynamic Pipeline
    pipeline = models.ForeignKey(
        'crm.Pipeline',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='leads',
        help_text="The pipeline this lead is in"
    )
    current_stage = models.ForeignKey(
        'crm.PipelineStage',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='leads',
        help_text="Current stage within the pipeline"
    )
    stage_entered_at = models.DateTimeField(null=True, blank=True, help_text="When lead entered current stage")
    
    # NEW: Engagement Tracking
    engagement_score = models.IntegerField(
        default=0,
        help_text="Calculated score based on client interactions"
    )
    last_engagement_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp of last client engagement event"
    )
    
    # NEW: Communication Cycle Status
    nurture_active = models.BooleanField(
        default=True,
        help_text="Whether automated communications are active for this lead"
    )
    next_scheduled_communication = models.DateTimeField(
        null=True, blank=True,
        help_text="Next scheduled automated communication"
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='assigned_leads'
    )
    
    # Follow-up
    next_follow_up = models.DateTimeField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True)
    
    # Conversion
    converted_learner = models.ForeignKey(
        'learners.Learner', 
        null=True, blank=True, 
        on_delete=models.SET_NULL,
        related_name='converted_from_leads'
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Tags for segmentation
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'assigned_to']),
            models.Index(fields=['phone']),
            models.Index(fields=['email']),
            models.Index(fields=['lead_type', 'status']),
            models.Index(fields=['date_of_birth']),
            models.Index(fields=['pipeline', 'current_stage']),
            models.Index(fields=['engagement_score']),
            models.Index(fields=['next_scheduled_communication']),
        ]
    
    def clean(self):
        """
        Validate that at least one contact method is provided.
        A lead must have: first_name, last_name, and at least one of phone/email/whatsapp.
        """
        from django.core.exceptions import ValidationError
        
        errors = {}
        
        # Check required fields
        if not self.first_name:
            errors['first_name'] = 'First name is required.'
        if not self.last_name:
            errors['last_name'] = 'Last name is required.'
        
        # At least one contact method required
        has_contact = bool(self.phone or self.email or self.whatsapp_number)
        if not has_contact:
            errors['__all__'] = 'At least one contact method (phone, email, or WhatsApp) is required.'
        
        if errors:
            raise ValidationError(errors)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.status}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_contact_channels(self):
        """Get ordered list of contact channels based on preference and fallback."""
        channels = [self.preferred_contact_method]
        channels.extend(self.fallback_contact_methods or [])
        # Remove duplicates while preserving order
        seen = set()
        return [x for x in channels if not (x in seen or seen.add(x))]
    
    def get_contact_for_channel(self, channel):
        """Get the contact detail for a specific channel."""
        if channel == 'WHATSAPP':
            return self.whatsapp_number or self.phone
        elif channel == 'EMAIL':
            return self.email
        elif channel == 'SMS':
            return self.phone
        elif channel == 'PHONE':
            return self.phone
        return None
    
    @property
    def days_in_stage(self):
        """Calculate days since entering current stage."""
        if not self.stage_entered_at:
            return None
        from datetime import datetime
        delta = timezone.now() - self.stage_entered_at
        return delta.days
    
    @property
    def is_overdue_in_stage(self):
        """Check if lead has exceeded expected time in current stage."""
        if not self.current_stage or not self.stage_entered_at:
            return False
        days = self.days_in_stage
        return days is not None and days > self.current_stage.expected_duration_days
    
    @property
    def age(self):
        """Calculate current age from date of birth"""
        if not self.date_of_birth:
            return None
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
    
    @property
    def is_minor(self):
        """Check if lead is under 18"""
        age = self.age
        return age is not None and age < 18
    
    @property
    def is_enrollment_ready(self):
        """Check if school leaver is 18+ and ready for enrollment"""
        age = self.age
        if self.lead_type != 'SCHOOL_LEAVER':
            return True
        return age is not None and age >= 18
    
    def move_to_stage(self, new_stage, user=None):
        """Move lead to a new pipeline stage with activity logging."""
        old_stage = self.current_stage
        self.current_stage = new_stage
        self.stage_entered_at = timezone.now()
        
        # Map stage to legacy status for backward compatibility
        if new_stage.is_entry_stage:
            self.status = 'NEW'
        elif new_stage.is_won_stage:
            self.status = 'ENROLLED'
        elif new_stage.is_lost_stage:
            self.status = 'LOST'
        elif new_stage.is_nurture_stage:
            self.status = 'CONTACTED'
        
        self.save()
        
        # Log activity
        LeadActivity.objects.create(
            lead=self,
            activity_type='STATUS_CHANGE',
            description=f'Stage changed: {old_stage.name if old_stage else "None"} → {new_stage.name}',
            from_status=old_stage.code if old_stage else '',
            to_status=new_stage.code,
            created_by=user
        )
    
    def validate_and_extract_id_number(self):
        """Validate SA ID and auto-populate DOB and gender."""
        from learners.models import validate_sa_id
        
        if not self.id_number or len(self.id_number) != 13:
            return False
        
        if not validate_sa_id(self.id_number):
            return False
        
        # Extract DOB
        year = int(self.id_number[0:2])
        month = int(self.id_number[2:4])
        day = int(self.id_number[4:6])
        
        # Determine century (if year > current 2-digit year, assume 1900s, else 2000s)
        from datetime import date
        current_year = date.today().year % 100
        if year > current_year:
            full_year = 1900 + year
        else:
            full_year = 2000 + year
        
        try:
            self.date_of_birth = date(full_year, month, day)
        except ValueError:
            return False
        
        # Extract gender (7th digit: 0-4 = female, 5-9 = male)
        gender_digit = int(self.id_number[6])
        self.gender = 'F' if gender_digit < 5 else 'M'
        
        return True
    
    @property
    def profile_completion_percentage(self):
        """Calculate profile completion percentage for onboarding readiness."""
        total_fields = 0
        completed_fields = 0
        
        # Core fields (most important)
        core_fields = [
            ('first_name', self.first_name),
            ('last_name', self.last_name),
            ('phone', self.phone or self.whatsapp_number),
            ('email', self.email),
            ('date_of_birth', self.date_of_birth),
            ('id_number', self.id_number),
            ('gender', self.gender),
        ]
        
        # Demographics
        demo_fields = [
            ('race', self.race),
            ('marital_status', self.marital_status),
            ('first_language', self.first_language),
        ]
        
        # Education
        edu_fields = [
            ('highest_grade_passed', self.highest_grade_passed),
            ('last_school_attended', self.last_school_attended or self.school_name),
        ]
        
        # Work
        work_fields = [
            ('work_status', self.work_status),
        ]
        
        # Contact & Address
        contact_fields = [
            ('physical_address', self.physical_address),
        ]
        
        # Health (counted as complete if either NO or YES with description)
        health_complete = (not self.has_disability or bool(self.disability_description))
        medical_complete = (not self.has_medical_conditions or bool(self.medical_conditions))
        
        all_fields = core_fields + demo_fields + edu_fields + work_fields + contact_fields
        
        for name, value in all_fields:
            total_fields += 1
            if value:
                completed_fields += 1
        
        # Add health fields
        total_fields += 2
        if health_complete:
            completed_fields += 1
        if medical_complete:
            completed_fields += 1
        
        return int((completed_fields / total_fields) * 100) if total_fields > 0 else 0
    
    @property
    def profile_completion_status(self):
        """Get profile completion status with details."""
        percentage = self.profile_completion_percentage
        
        missing = []
        if not self.id_number:
            missing.append('ID Number')
        if not self.date_of_birth:
            missing.append('Date of Birth')
        if not self.gender:
            missing.append('Gender')
        if not self.race:
            missing.append('Race')
        if not self.physical_address:
            missing.append('Physical Address')
        if not self.highest_grade_passed:
            missing.append('Highest Grade')
        if not self.work_status:
            missing.append('Work Status')
        if not self.first_language:
            missing.append('First Language')
        if not (self.email):
            missing.append('Email')
        
        return {
            'percentage': percentage,
            'missing_fields': missing,
            'is_complete': percentage >= 80,
            'status': 'Complete' if percentage >= 80 else ('Partial' if percentage >= 50 else 'Incomplete')
        }
    
    def copy_profile_to_learner(self, learner):
        """Copy all profile data to a Learner instance when converting."""
        # Basic info
        learner.first_name = self.first_name
        learner.last_name = self.last_name
        learner.email = self.email
        learner.mobile_number = self.phone or self.whatsapp_number
        learner.date_of_birth = self.date_of_birth
        
        # ID
        if self.id_number:
            learner.sa_id_number = self.id_number
        
        # Demographics
        if self.gender:
            learner.gender = self.gender
        if self.race:
            learner.population_group = self.race
        if self.first_language:
            learner.home_language = self.first_language
        
        # Disability
        learner.has_disability = self.has_disability
        if self.has_disability and self.disability_description:
            learner.disability_status = '9'  # Disabled but unspecified
        
        # Addresses
        if self.physical_address:
            learner.physical_address = self.physical_address
        if self.postal_address:
            learner.postal_address = self.postal_address
        elif self.postal_same_as_physical and self.physical_address:
            learner.postal_address = self.physical_address
        
        return learner


class LeadActivity(AuditedModel):
    """
    Activity log for lead interactions
    """
    ACTIVITY_TYPES = [
        ('CALL', 'Phone Call'),
        ('EMAIL', 'Email'),
        ('WHATSAPP', 'WhatsApp'),
        ('SMS', 'SMS'),
        ('MEETING', 'Meeting'),
        ('NOTE', 'Note'),
        ('STATUS_CHANGE', 'Status Change'),
        ('STAGE_CHANGE', 'Pipeline Stage Change'),
        ('ASSIGNMENT', 'Assignment'),
        ('FOLLOW_UP', 'Follow-up Scheduled'),
        ('DOCUMENT', 'Document'),
        ('QUOTE_SENT', 'Quote Sent'),
        ('QUOTE_VIEWED', 'Quote Viewed'),
        ('QUOTE_ACCEPTED', 'Quote Accepted'),
        ('COMMUNICATION_SENT', 'Automated Communication Sent'),
    ]
    
    lead = models.ForeignKey(
        Lead, 
        on_delete=models.CASCADE, 
        related_name='activities'
    )
    
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    outcome = models.CharField(max_length=100, blank=True)
    
    # For status/stage changes
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    
    # For automated activities
    is_automated = models.BooleanField(default=False)
    automation_source = models.CharField(max_length=100, blank=True, help_text="e.g., 'nurture_cycle', 'stage_blueprint'")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lead Activity'
        verbose_name_plural = 'Lead Activities'
    
    def __str__(self):
        return f"{self.lead} - {self.activity_type} - {self.created_at}"


class SETAFundingOpportunity(AuditedModel):
    """
    SETA funding opportunities (Discretionary, PIVOTAL, etc.)
    """
    FUNDING_TYPES = [
        ('DISCRETIONARY', 'Discretionary Grant'),
        ('MANDATORY', 'Mandatory Grant'),
        ('PIVOTAL', 'PIVOTAL Grant'),
        ('LEARNERSHIP', 'Learnership'),
        ('INTERNSHIP', 'Internship'),
        ('SKILLS_PROG', 'Skills Programme'),
        ('BURSARY', 'Bursary'),
    ]
    
    seta = models.ForeignKey(
        'learners.SETA', 
        on_delete=models.CASCADE, 
        related_name='funding_opportunities'
    )
    name = models.CharField(max_length=200)
    funding_type = models.CharField(max_length=20, choices=FUNDING_TYPES)
    
    # Eligible qualifications
    qualifications = models.ManyToManyField(
        'academics.Qualification',
        blank=True,
        related_name='funding_opportunities'
    )
    
    # Window
    application_open = models.DateField()
    application_close = models.DateField()
    
    # Capacity
    max_learners = models.PositiveIntegerField(null=True, blank=True)
    funding_per_learner = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, blank=True
    )
    total_budget = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        null=True, blank=True
    )
    
    # Requirements
    requirements = models.TextField(blank=True)
    eligibility_criteria = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-application_close']
        verbose_name = 'SETA Funding Opportunity'
        verbose_name_plural = 'SETA Funding Opportunities'
    
    def __str__(self):
        return f"{self.seta.code} - {self.name}"
    
    @property
    def is_open(self):
        from django.utils import timezone
        today = timezone.now().date()
        return self.application_open <= today <= self.application_close


class FundingApplication(AuditedModel):
    """
    Application for SETA funding
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CONTRACTED', 'Contracted'),
        ('COMPLETED', 'Completed'),
    ]
    
    opportunity = models.ForeignKey(
        SETAFundingOpportunity, 
        on_delete=models.PROTECT, 
        related_name='applications'
    )
    employer = models.ForeignKey(
        'learners.Employer', 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='funding_applications'
    )
    
    # Application details
    application_date = models.DateField()
    reference_number = models.CharField(max_length=50, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Numbers
    learners_requested = models.PositiveIntegerField()
    learners_approved = models.PositiveIntegerField(null=True, blank=True)
    amount_requested = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, blank=True
    )
    amount_approved = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, blank=True
    )
    
    # Notes
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-application_date']
        verbose_name = 'Funding Application'
        verbose_name_plural = 'Funding Applications'
    
    def __str__(self):
        return f"{self.opportunity} - {self.reference_number}"


class WhatsAppConfig(models.Model):
    """
    WhatsApp Business API configuration per brand
    """
    brand = models.OneToOneField(
        'tenants.Brand', 
        on_delete=models.CASCADE, 
        related_name='whatsapp_config'
    )
    
    phone_number_id = models.CharField(max_length=50)
    business_account_id = models.CharField(max_length=50)
    api_token = models.TextField()  # Encrypted
    webhook_verify_token = models.CharField(max_length=100)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'WhatsApp Config'
        verbose_name_plural = 'WhatsApp Configs'
    
    def __str__(self):
        return f"WhatsApp Config - {self.brand.name}"


class WhatsAppMessage(AuditedModel):
    """
    WhatsApp message log
    """
    DIRECTION_CHOICES = [
        ('IN', 'Inbound'),
        ('OUT', 'Outbound'),
    ]
    
    MESSAGE_TYPES = [
        ('TEXT', 'Text'),
        ('TEMPLATE', 'Template'),
        ('DOCUMENT', 'Document'),
        ('IMAGE', 'Image'),
        ('AUDIO', 'Audio'),
        ('VIDEO', 'Video'),
        ('LOCATION', 'Location'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('READ', 'Read'),
        ('FAILED', 'Failed'),
    ]
    
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    phone_number = models.CharField(max_length=20)
    
    # Link to entities
    lead = models.ForeignKey(
        Lead, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='whatsapp_messages'
    )
    learner = models.ForeignKey(
        'learners.Learner', 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='whatsapp_messages'
    )
    
    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    content = models.TextField()
    template_name = models.CharField(max_length=100, blank=True)
    media_url = models.URLField(blank=True)
    
    # WhatsApp IDs
    wa_message_id = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'WhatsApp Message'
        verbose_name_plural = 'WhatsApp Messages'
    
    def __str__(self):
        return f"{self.direction} - {self.phone_number} - {self.created_at}"


class WhatsAppIntakeForm(AuditedModel):
    """
    Template for WhatsApp-based lead capture
    """
    name = models.CharField(max_length=100)
    brand = models.ForeignKey(
        'tenants.Brand', 
        on_delete=models.CASCADE,
        related_name='whatsapp_intake_forms'
    )
    
    # Flow configuration
    welcome_message = models.TextField()
    qualification_prompt = models.TextField()
    contact_prompt = models.TextField()
    confirmation_message = models.TextField()
    
    # Auto-assignment
    assign_to_user = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_intake_forms'
    )
    assign_to_campus = models.ForeignKey(
        'tenants.Campus', 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='intake_forms'
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'WhatsApp Intake Form'
        verbose_name_plural = 'WhatsApp Intake Forms'
    
    def __str__(self):
        return f"{self.brand.code} - {self.name}"


class WhatsAppIntakeSession(AuditedModel):
    """
    Tracks a lead capture conversation
    """
    STATUS_CHOICES = [
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('ABANDONED', 'Abandoned'),
        ('CONVERTED', 'Converted to Lead'),
    ]
    
    form = models.ForeignKey(
        WhatsAppIntakeForm, 
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    phone_number = models.CharField(max_length=20)
    
    # Collected data
    collected_data = models.JSONField(default=dict)
    
    # Progress
    current_step = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_PROGRESS')
    
    # Conversion
    converted_lead = models.ForeignKey(
        Lead, 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='intake_sessions'
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'WhatsApp Intake Session'
        verbose_name_plural = 'WhatsApp Intake Sessions'
    
    def __str__(self):
        return f"{self.phone_number} - {self.form.name} - {self.status}"


class Opportunity(TenantAwareModel):
    """
    Sales opportunity - a qualified lead pursuing enrollment.
    Bridges Lead to Application/Enrollment with value and probability tracking.
    """
    STAGE_CHOICES = [
        ('DISCOVERY', 'Discovery'),
        ('QUALIFICATION', 'Qualification'),
        ('PROPOSAL', 'Proposal'),
        ('NEGOTIATION', 'Negotiation'),
        ('COMMITTED', 'Committed'),
        ('WON', 'Won'),
        ('LOST', 'Lost'),
    ]
    
    FUNDING_TYPES = [
        ('SELF', 'Self-Funded'),
        ('EMPLOYER', 'Employer-Funded'),
        ('BURSARY', 'Bursary'),
        ('SETA', 'SETA Learnership'),
        ('NSFAS', 'NSFAS'),
        ('LOAN', 'Student Loan'),
        ('SCHOLARSHIP', 'Scholarship'),
        ('MIXED', 'Mixed Funding'),
    ]
    
    LOST_REASONS = [
        ('PRICE', 'Too Expensive'),
        ('TIMING', 'Wrong Timing'),
        ('COMPETITOR', 'Chose Competitor'),
        ('UNQUALIFIED', 'Not Qualified'),
        ('NO_RESPONSE', 'No Response'),
        ('PERSONAL', 'Personal Reasons'),
        ('LOCATION', 'Location Issue'),
        ('OTHER', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Lead link
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='opportunities'
    )
    
    # Opportunity details
    name = models.CharField(
        max_length=200,
        help_text="e.g., 'Michael Smith - Electrical Engineering N4'"
    )
    
    # What they're interested in
    qualification = models.ForeignKey(
        'academics.Qualification',
        on_delete=models.PROTECT,
        related_name='opportunities'
    )
    intake = models.ForeignKey(
        'intakes.Intake',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='opportunities'
    )
    
    # Pipeline stage
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='DISCOVERY')
    stage_entered_at = models.DateTimeField(auto_now_add=True)
    
    # Value and probability
    value = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=0,
        help_text="Expected revenue from this enrollment"
    )
    probability = models.PositiveIntegerField(
        default=10,
        help_text="Likelihood of closing (0-100%)"
    )
    
    @property
    def weighted_value(self):
        """Value * probability for pipeline forecasting."""
        return self.value * (self.probability / 100)
    
    # Timeline
    expected_close_date = models.DateField(null=True, blank=True)
    expected_start_date = models.DateField(
        null=True, blank=True,
        help_text="When they expect to start studying"
    )
    
    # Funding
    funding_type = models.CharField(max_length=20, choices=FUNDING_TYPES, default='SELF')
    funding_confirmed = models.BooleanField(default=False)
    funding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    funding_notes = models.TextField(blank=True)
    
    # SETA/Bursary application (if applicable)
    funding_application = models.ForeignKey(
        'crm.FundingApplication',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='opportunities'
    )
    
    # Assignment
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_opportunities'
    )
    
    # Lost tracking
    lost_reason = models.CharField(max_length=20, choices=LOST_REASONS, blank=True)
    lost_to_competitor = models.CharField(max_length=100, blank=True)
    lost_notes = models.TextField(blank=True)
    lost_at = models.DateTimeField(null=True, blank=True)
    
    # Re-engagement
    reopen_date = models.DateField(
        null=True, blank=True,
        help_text="When to re-engage this opportunity (e.g., when minor turns 18)"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Opportunity'
        verbose_name_plural = 'Opportunities'
        indexes = [
            models.Index(fields=['stage', 'campus']),
            models.Index(fields=['assigned_agent', 'stage']),
            models.Index(fields=['expected_close_date']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-set probability based on stage
        stage_probabilities = {
            'DISCOVERY': 10,
            'QUALIFICATION': 25,
            'PROPOSAL': 50,
            'NEGOTIATION': 75,
            'COMMITTED': 90,
            'WON': 100,
            'LOST': 0,
        }
        if not self.pk or self._state.adding:
            self.probability = stage_probabilities.get(self.stage, self.probability)
        super().save(*args, **kwargs)
    
    def advance_stage(self, new_stage, user=None):
        """Advance to a new stage with activity logging."""
        old_stage = self.stage
        self.stage = new_stage
        self.stage_entered_at = timezone.now()
        
        # Update probability
        stage_probabilities = {
            'DISCOVERY': 10,
            'QUALIFICATION': 25,
            'PROPOSAL': 50,
            'NEGOTIATION': 75,
            'COMMITTED': 90,
            'WON': 100,
            'LOST': 0,
        }
        self.probability = stage_probabilities.get(new_stage, self.probability)
        
        if new_stage == 'LOST':
            self.lost_at = timezone.now()
        
        self.save()
        
        # Log activity on lead
        LeadActivity.objects.create(
            lead=self.lead,
            activity_type='STATUS_CHANGE',
            description=f'Opportunity stage changed: {old_stage} → {new_stage}',
            created_by=user
        )


class OpportunityActivity(AuditedModel):
    """
    Activity log for opportunity interactions.
    """
    ACTIVITY_TYPES = [
        ('STAGE_CHANGE', 'Stage Change'),
        ('CALL', 'Phone Call'),
        ('EMAIL', 'Email'),
        ('MEETING', 'Meeting'),
        ('NOTE', 'Note'),
        ('QUOTE_SENT', 'Quote Sent'),
        ('DOCUMENT', 'Document'),
        ('FOLLOW_UP', 'Follow-up Scheduled'),
    ]
    
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    
    # For stage changes
    from_stage = models.CharField(max_length=20, blank=True)
    to_stage = models.CharField(max_length=20, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Opportunity Activity'
        verbose_name_plural = 'Opportunity Activities'
    
    def __str__(self):
        return f"{self.opportunity} - {self.activity_type}"


class Application(TenantAwareModel):
    """
    Enrollment application - bridging Opportunity to actual Enrollment.
    Handles document collection, review, and conversion to Learner/Enrollment.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('DOCUMENTS_PENDING', 'Documents Pending'),
        ('UNDER_REVIEW', 'Under Review'),
        ('ACCEPTED', 'Accepted'),
        ('WAITLIST', 'Waitlist'),
        ('REJECTED', 'Rejected'),
        ('ENROLLED', 'Enrolled'),
        ('WITHDRAWN', 'Withdrawn'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Links
    opportunity = models.OneToOneField(
        Opportunity,
        on_delete=models.CASCADE,
        related_name='application'
    )
    
    # Created learner (on application acceptance)
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='applications'
    )
    
    # Created enrollment (on final enrollment)
    enrollment = models.OneToOneField(
        'academics.Enrollment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='application'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Submission
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='submitted_applications'
    )
    
    # Review
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_applications'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(blank=True)
    
    # Document tracking
    required_documents = models.JSONField(
        default=list,
        help_text="List of required document types"
    )
    missing_documents = models.JSONField(
        default=list,
        help_text="List of missing document types"
    )
    
    # Parent consent (for minors)
    parent_consent_required = models.BooleanField(default=False)
    parent_consent_received = models.BooleanField(default=False)
    parent_consent_document = models.ForeignKey(
        'learners.Document',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='consent_applications'
    )
    parent_consent_date = models.DateField(null=True, blank=True)
    
    # Enrollment details
    enrollment_date = models.DateField(null=True, blank=True)
    
    # Communication
    last_communication_at = models.DateTimeField(null=True, blank=True)
    next_follow_up = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Application'
        verbose_name_plural = 'Applications'
        indexes = [
            models.Index(fields=['status', 'campus']),
        ]
    
    def __str__(self):
        return f"Application: {self.opportunity.name} ({self.get_status_display()})"
    
    def check_document_completeness(self):
        """Check if all required documents are submitted."""
        # This would integrate with the Document model
        # For now, just check if missing_documents is empty
        return len(self.missing_documents) == 0
    
    def submit(self, user):
        """Submit application for review."""
        self.status = 'SUBMITTED'
        self.submitted_at = timezone.now()
        self.submitted_by = user
        
        # Check for minor - require parent consent
        if self.opportunity.lead.is_minor:
            self.parent_consent_required = True
            if not self.parent_consent_received:
                self.status = 'DOCUMENTS_PENDING'
        
        self.save()
        
        # Update opportunity stage
        self.opportunity.advance_stage('COMMITTED', user)
    
    def accept(self, user, notes=''):
        """Accept application and create learner if needed."""
        self.status = 'ACCEPTED'
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.decision_notes = notes
        self.save()
        
        # Update opportunity
        self.opportunity.advance_stage('WON', user)
        
        # Update lead status
        self.opportunity.lead.status = 'REGISTERED'
        self.opportunity.lead.save()
    
    def reject(self, user, notes=''):
        """Reject application."""
        self.status = 'REJECTED'
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.decision_notes = notes
        self.save()
        
        # Update opportunity
        self.opportunity.advance_stage('LOST', user)
        self.opportunity.lost_reason = 'UNQUALIFIED'
        self.opportunity.save()
    
    def convert_to_enrollment(self, user):
        """Convert accepted application to actual enrollment."""
        from learners.models import Learner
        from academics.models import Enrollment
        
        lead = self.opportunity.lead
        
        # Create or get learner
        if not self.learner:
            learner = Learner.objects.create(
                first_name=lead.first_name,
                last_name=lead.last_name,
                email=lead.email,
                mobile_number=lead.phone,
                id_number=lead.id_number,
                date_of_birth=lead.date_of_birth,
                brand=self.brand,
                # Add more fields as needed
            )
            self.learner = learner
        
        # Create enrollment
        # (This would need to be customized based on your Enrollment model)
        
        self.status = 'ENROLLED'
        self.enrollment_date = timezone.now().date()
        self.save()
        
        # Update lead
        lead.status = 'ENROLLED'
        lead.converted_learner = self.learner
        lead.converted_at = timezone.now()
        lead.save()


class ApplicationDocument(AuditedModel):
    """
    Document submitted for an application.
    """
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    document = models.ForeignKey(
        'learners.Document',
        on_delete=models.CASCADE,
        related_name='application_documents'
    )
    
    document_type = models.CharField(max_length=50, help_text="e.g., 'ID', 'Matric Certificate'")
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_app_documents'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['document_type']
        verbose_name = 'Application Document'
        verbose_name_plural = 'Application Documents'
    
    def __str__(self):
        return f"{self.application} - {self.document_type}"


# =============================================================================
# LEAD DOCUMENT MODELS - Pre-enrollment document collection
# =============================================================================

class LeadDocument(AuditedModel):
    """
    Document uploaded by a lead before enrollment.
    Used for pre-enrollment document collection via public portal.
    """
    DOCUMENT_TYPES = [
        ('ID_COPY', 'ID Copy / Passport'),
        ('MATRIC', 'Matric Certificate'),
        ('PROOF_ADDRESS', 'Proof of Address'),
        ('QUALIFICATION', 'Prior Qualification'),
        ('CV', 'Curriculum Vitae'),
        ('BANK_CONFIRM', 'Bank Confirmation'),
        ('PARENT_ID', 'Parent/Guardian ID'),
        ('PARENT_CONSENT', 'Parent/Guardian Consent'),
        ('PROOF_OF_PAYMENT', 'Proof of Payment'),
        ('OTHER', 'Other Document'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    upload_request = models.ForeignKey(
        'DocumentUploadRequest',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='uploaded_documents',
        help_text="The upload request this document was uploaded through"
    )
    
    # Document details
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    
    # File
    file = models.FileField(upload_to='lead_documents/%Y/%m/')
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)  # bytes
    content_type = models.CharField(max_length=100, blank=True)
    
    # Verification
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_lead_documents'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Upload tracking
    uploaded_via_portal = models.BooleanField(default=False)
    upload_ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lead Document'
        verbose_name_plural = 'Lead Documents'
    
    def __str__(self):
        return f"{self.lead.get_full_name()} - {self.get_document_type_display()}"
    
    def verify(self, user, notes=''):
        """Mark document as verified."""
        self.status = 'VERIFIED'
        self.verified_by = user
        self.verified_at = timezone.now()
        self.verification_notes = notes
        self.save()
    
    def reject(self, user, notes=''):
        """Mark document as rejected."""
        self.status = 'REJECTED'
        self.verified_by = user
        self.verified_at = timezone.now()
        self.verification_notes = notes
        self.save()


class DocumentUploadRequest(AuditedModel):
    """
    Request for a lead to upload documents via a secure public portal.
    Similar to PreApprovalLetter, uses UUID for token-based access.
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('EXPIRED', 'Expired'),
        ('REVOKED', 'Revoked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='document_requests'
    )
    
    # Request details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    message = models.TextField(
        blank=True,
        help_text="Custom message to show on upload portal"
    )
    
    # Requested document types (JSON list)
    requested_document_types = models.JSONField(
        default=list,
        help_text="List of document types requested, e.g., ['ID_COPY', 'MATRIC']"
    )
    
    # Validity
    valid_until = models.DateTimeField(
        help_text="Token expires after this date"
    )
    
    # Tracking
    sent_via = models.CharField(
        max_length=20,
        choices=[('EMAIL', 'Email'), ('WHATSAPP', 'WhatsApp'), ('SMS', 'SMS'), ('MANUAL', 'Manual')],
        default='MANUAL'
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sent_upload_requests'
    )
    
    # Portal access tracking
    first_viewed_at = models.DateTimeField(null=True, blank=True)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    
    # Completion
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document Upload Request'
        verbose_name_plural = 'Document Upload Requests'
    
    def __str__(self):
        return f"Document Request for {self.lead.get_full_name()} ({self.status})"
    
    @property
    def is_valid(self):
        """Check if request is still valid for uploads."""
        if self.status in ['EXPIRED', 'REVOKED']:
            return False
        return timezone.now() <= self.valid_until
    
    @property
    def is_expired(self):
        """Check if request has expired."""
        return timezone.now() > self.valid_until
    
    def get_portal_url(self):
        """Get relative portal URL."""
        return f"/crm/portal/documents/{self.id}/"
    
    def get_full_portal_url(self, request=None):
        """Get full portal URL with domain."""
        from django.contrib.sites.models import Site
        try:
            site = Site.objects.get_current()
            domain = site.domain
        except Exception:
            domain = 'skillsflow.co.za'
        
        protocol = 'https'
        return f"{protocol}://{domain}{self.get_portal_url()}"
    
    def mark_viewed(self):
        """Track portal view."""
        now = timezone.now()
        if not self.first_viewed_at:
            self.first_viewed_at = now
        self.last_viewed_at = now
        self.view_count = (self.view_count or 0) + 1
        self.save(update_fields=['first_viewed_at', 'last_viewed_at', 'view_count'])
    
    def mark_completed(self):
        """Mark request as completed."""
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def revoke(self):
        """Revoke the upload request."""
        self.status = 'REVOKED'
        self.save(update_fields=['status'])
    
    def get_missing_document_types(self):
        """Get document types that haven't been uploaded yet."""
        uploaded_types = self.uploaded_documents.values_list('document_type', flat=True)
        return [dt for dt in self.requested_document_types if dt not in uploaded_types]
    
    def get_uploaded_document_types(self):
        """Get document types that have been uploaded."""
        return list(self.uploaded_documents.values_list('document_type', flat=True))
    
    @property
    def upload_progress(self):
        """Get upload progress as percentage."""
        if not self.requested_document_types:
            return 100
        uploaded = len(self.get_uploaded_document_types())
        total = len(self.requested_document_types)
        return int((uploaded / total) * 100)
    
    @property
    def all_documents_uploaded(self):
        """Check if all requested documents have been uploaded."""
        return len(self.get_missing_document_types()) == 0


# =============================================================================
# WEB FORM INTEGRATION MODELS
# =============================================================================

class WebFormSource(AuditedModel):
    """
    Maps external websites/domains to brands for form integration.
    Each source gets a unique webhook URL for receiving form submissions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Brand association
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='web_form_sources'
    )
    
    # Source identification
    name = models.CharField(max_length=100, help_text="Friendly name (e.g., 'Main College Website')")
    domain = models.CharField(
        max_length=255, 
        unique=True, 
        help_text="Website domain (e.g., 'collegename.co.za')"
    )
    description = models.TextField(blank=True)
    
    # Security
    webhook_secret = models.CharField(
        max_length=64,
        blank=True,
        help_text="Secret key for webhook verification (sent in X-Webhook-Secret header)"
    )
    
    # Defaults
    default_campus = models.ForeignKey(
        Campus,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='default_web_form_sources',
        help_text="Default campus if form doesn't specify one"
    )
    default_lead_source = models.ForeignKey(
        'crm.LeadSource',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        help_text="Default lead source for this website"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Stats
    total_leads_created = models.PositiveIntegerField(default=0)
    total_duplicates_updated = models.PositiveIntegerField(default=0)
    last_submission_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['brand', 'name']
        verbose_name = 'Web Form Source'
        verbose_name_plural = 'Web Form Sources'
    
    def __str__(self):
        return f"{self.name} ({self.domain})"
    
    def save(self, *args, **kwargs):
        import secrets
        if not self.webhook_secret:
            self.webhook_secret = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
    
    def get_webhook_url(self):
        """Get the webhook URL path for this source."""
        return f"/crm/webhooks/web-forms/{self.id}/"
    
    def regenerate_secret(self):
        """Regenerate the webhook secret key."""
        import secrets
        self.webhook_secret = secrets.token_urlsafe(32)
        self.save(update_fields=['webhook_secret', 'updated_at'])
        return self.webhook_secret


class WebFormMapping(AuditedModel):
    """
    Maps individual Gravity Forms (or other form IDs) to campuses with field mappings.
    Allows different forms to create leads in different campuses with custom field mapping.
    """
    # Common Lead field options for the UI mapper
    LEAD_FIELD_CHOICES = [
        ('first_name', 'First Name'),
        ('last_name', 'Last Name'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('phone_secondary', 'Secondary Phone'),
        ('whatsapp_number', 'WhatsApp Number'),
        ('date_of_birth', 'Date of Birth'),
        ('school_name', 'School Name'),
        ('grade', 'Grade'),
        ('expected_matric_year', 'Expected Matric Year'),
        ('parent_name', 'Parent/Guardian Name'),
        ('parent_phone', 'Parent Phone'),
        ('parent_email', 'Parent Email'),
        ('parent_relationship', 'Parent Relationship'),
        ('employer_name', 'Employer Name'),
        ('highest_qualification', 'Highest Qualification'),
        ('employment_status', 'Employment Status'),
        ('notes', 'Notes/Comments'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Parent source
    source = models.ForeignKey(
        WebFormSource,
        on_delete=models.CASCADE,
        related_name='form_mappings'
    )
    
    # Form identification
    form_id = models.CharField(
        max_length=50,
        help_text="Gravity Forms ID or other form identifier"
    )
    form_name = models.CharField(max_length=200, help_text="Descriptive name for this form")
    
    # Campus override (if different from source default)
    campus = models.ForeignKey(
        Campus,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='web_form_mappings',
        help_text="Campus for leads from this form (overrides source default)"
    )
    
    # Qualification interest
    qualification = models.ForeignKey(
        'academics.Qualification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='web_form_mappings',
        help_text="Default qualification interest for this form"
    )
    
    # Pipeline assignment
    pipeline = models.ForeignKey(
        'crm.Pipeline',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        help_text="Pipeline to assign leads to"
    )
    
    # Lead type
    lead_type = models.CharField(
        max_length=20,
        choices=Lead.LEAD_TYPE_CHOICES,
        default='ADULT',
        help_text="Lead type for leads from this form"
    )
    
    # Field mapping: Gravity Forms field ID -> Lead field name
    # Example: {"1.3": "first_name", "1.6": "last_name", "2": "email", "3": "phone"}
    field_mapping = models.JSONField(
        default=dict,
        help_text="Maps form field IDs to Lead model fields"
    )
    
    # Default values for fields not in the form
    default_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Default values for Lead fields (e.g., {'lead_type': 'SCHOOL_LEAVER'})"
    )
    
    # Auto-assign to user
    auto_assign_to = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='webform_auto_assignments',
        help_text="Automatically assign leads from this form to this user"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Stats
    leads_created = models.PositiveIntegerField(default=0)
    duplicates_updated = models.PositiveIntegerField(default=0)
    last_submission_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['source', 'form_name']
        unique_together = ['source', 'form_id']
        verbose_name = 'Web Form Mapping'
        verbose_name_plural = 'Web Form Mappings'
    
    def __str__(self):
        return f"{self.form_name} (Form ID: {self.form_id})"
    
    def get_campus(self):
        """Get the effective campus (form override or source default)."""
        return self.campus or self.source.default_campus
    
    def map_form_data(self, form_data):
        """
        Map incoming form data to Lead field values.
        
        Args:
            form_data: Dict of form field values (key is field ID)
            
        Returns:
            Dict of Lead field values
        """
        result = {}
        
        # Apply field mapping
        for form_field_id, lead_field in self.field_mapping.items():
            if form_field_id in form_data:
                value = form_data[form_field_id]
                if value is not None:
                    result[lead_field] = str(value).strip() if value else ''
        
        # Apply default values (don't override mapped values)
        for field, default_value in self.default_values.items():
            if field not in result or not result[field]:
                result[field] = default_value
        
        return result


class WebFormSubmission(AuditedModel):
    """
    Logs all form submissions for auditing and debugging.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Source and form
    source = models.ForeignKey(
        WebFormSource,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    form_mapping = models.ForeignKey(
        WebFormMapping,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='submissions'
    )
    
    # Raw submission data
    raw_payload = models.JSONField(help_text="Original webhook payload")
    mapped_data = models.JSONField(
        default=dict,
        help_text="Data after field mapping applied"
    )
    
    # Result
    STATUS_CHOICES = [
        ('SUCCESS', 'Lead Created'),
        ('DUPLICATE', 'Duplicate Updated'),
        ('FAILED', 'Failed'),
        ('IGNORED', 'Ignored'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Created/updated lead
    lead = models.ForeignKey(
        'crm.Lead',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='web_form_submissions'
    )
    
    # Error tracking
    error_message = models.TextField(blank=True)
    
    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Web Form Submission'
        verbose_name_plural = 'Web Form Submissions'
    
    def __str__(self):
        return f"Submission {self.id} - {self.status}"


# ============================================================================
# MARKETING ANALYTICS MODELS
# ============================================================================

class SocialMetricsSnapshot(models.Model):
    """
    Daily metrics snapshot for a brand's social media accounts.
    Stores aggregated daily metrics from Facebook, Instagram, and TikTok.
    """
    PLATFORM_CHOICES = [
        ('FACEBOOK', 'Facebook'),
        ('INSTAGRAM', 'Instagram'),
        ('TIKTOK', 'TikTok'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='social_metrics'
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    date = models.DateField(db_index=True)
    
    # Audience Metrics
    followers = models.PositiveIntegerField(default=0, help_text="Total followers/fans at end of day")
    followers_gained = models.IntegerField(default=0, help_text="New followers gained")
    followers_lost = models.IntegerField(default=0, help_text="Followers lost (unfollows)")
    followers_net_change = models.IntegerField(default=0, help_text="Net follower change")
    
    # Reach & Impressions
    reach = models.PositiveIntegerField(default=0, help_text="Unique accounts reached")
    impressions = models.PositiveIntegerField(default=0, help_text="Total content views")
    
    # Engagement Metrics
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    saves = models.PositiveIntegerField(default=0)
    engagement_total = models.PositiveIntegerField(default=0, help_text="Total engagements")
    engagement_rate = models.DecimalField(
        max_digits=6, decimal_places=3, default=0,
        help_text="Engagement rate as percentage"
    )
    
    # Conversion Metrics
    link_clicks = models.PositiveIntegerField(default=0, help_text="Clicks on links in bio/posts")
    profile_visits = models.PositiveIntegerField(default=0, help_text="Profile page visits")
    website_clicks = models.PositiveIntegerField(default=0, help_text="Website button clicks")
    email_contacts = models.PositiveIntegerField(default=0, help_text="Email button clicks")
    phone_calls = models.PositiveIntegerField(default=0, help_text="Call button clicks")
    get_directions = models.PositiveIntegerField(default=0, help_text="Get directions clicks")
    
    # Content Published
    posts_published = models.PositiveIntegerField(default=0)
    stories_published = models.PositiveIntegerField(default=0)
    reels_published = models.PositiveIntegerField(default=0)
    videos_published = models.PositiveIntegerField(default=0)
    
    # Video Metrics (for Reels/TikTok)
    video_views = models.PositiveIntegerField(default=0)
    video_watch_time = models.PositiveIntegerField(default=0, help_text="Total watch time in seconds")
    avg_watch_time = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Average watch time per video")
    
    # Messaging (when approved)
    messages_received = models.PositiveIntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    
    # Metadata
    raw_data = models.JSONField(default=dict, blank=True, help_text="Raw API response for debugging")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['brand', 'platform', 'date']
        ordering = ['-date', 'brand', 'platform']
        verbose_name = 'Social Metrics Snapshot'
        verbose_name_plural = 'Social Metrics Snapshots'
        indexes = [
            models.Index(fields=['brand', 'date']),
            models.Index(fields=['platform', 'date']),
        ]
    
    def __str__(self):
        return f"{self.brand.name} - {self.platform} - {self.date}"
    
    @classmethod
    def get_date_range_metrics(cls, brand, platform, start_date, end_date):
        """Get aggregated metrics for a date range."""
        from django.db.models import Sum, Avg
        return cls.objects.filter(
            brand=brand,
            platform=platform,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(
            total_reach=Sum('reach'),
            total_impressions=Sum('impressions'),
            total_engagement=Sum('engagement_total'),
            total_link_clicks=Sum('link_clicks'),
            avg_engagement_rate=Avg('engagement_rate'),
            follower_change=Sum('followers_net_change'),
        )


class WebTrafficSnapshot(models.Model):
    """
    Daily website traffic snapshot from Google Analytics 4.
    Stores aggregated daily metrics for brand websites.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='web_traffic'
    )
    date = models.DateField(db_index=True)
    
    # Session Metrics
    sessions = models.PositiveIntegerField(default=0)
    users = models.PositiveIntegerField(default=0, help_text="Total active users")
    new_users = models.PositiveIntegerField(default=0)
    returning_users = models.PositiveIntegerField(default=0)
    
    # Engagement Metrics
    pageviews = models.PositiveIntegerField(default=0)
    pages_per_session = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    avg_session_duration = models.PositiveIntegerField(default=0, help_text="Average session duration in seconds")
    bounce_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Bounce rate as percentage")
    engagement_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="GA4 engagement rate")
    
    # Traffic Sources (JSON for flexibility)
    traffic_by_source = models.JSONField(
        default=dict, blank=True,
        help_text="Sessions by source: {organic: X, direct: Y, referral: Z, ...}"
    )
    traffic_by_medium = models.JSONField(
        default=dict, blank=True,
        help_text="Sessions by medium: {organic: X, cpc: Y, social: Z, ...}"
    )
    traffic_by_social = models.JSONField(
        default=dict, blank=True,
        help_text="Sessions from social: {facebook: X, instagram: Y, tiktok: Z, ...}"
    )
    
    # Geographic Data
    traffic_by_country = models.JSONField(default=dict, blank=True)
    traffic_by_city = models.JSONField(default=dict, blank=True)
    
    # Device Data
    traffic_by_device = models.JSONField(
        default=dict, blank=True,
        help_text="Sessions by device: {desktop: X, mobile: Y, tablet: Z}"
    )
    
    # Top Pages
    top_pages = models.JSONField(
        default=list, blank=True,
        help_text="Top pages by pageviews: [{path: '/about', views: 100}, ...]"
    )
    
    # Conversions/Goals
    goal_completions = models.PositiveIntegerField(default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    form_submissions = models.PositiveIntegerField(default=0)
    
    # Metadata
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['brand', 'date']
        ordering = ['-date', 'brand']
        verbose_name = 'Web Traffic Snapshot'
        verbose_name_plural = 'Web Traffic Snapshots'
        indexes = [
            models.Index(fields=['brand', 'date']),
        ]
    
    def __str__(self):
        return f"{self.brand.name} - {self.date}"


class ContentPost(models.Model):
    """
    Individual social media post performance tracking.
    Stores metrics for each published post for content analysis.
    """
    POST_TYPE_CHOICES = [
        ('POST', 'Feed Post'),
        ('STORY', 'Story'),
        ('REEL', 'Reel'),
        ('VIDEO', 'Video'),
        ('CAROUSEL', 'Carousel'),
        ('LIVE', 'Live Video'),
    ]
    
    PLATFORM_CHOICES = [
        ('FACEBOOK', 'Facebook'),
        ('INSTAGRAM', 'Instagram'),
        ('TIKTOK', 'TikTok'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='content_posts'
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    
    # Post Identification
    platform_post_id = models.CharField(max_length=100, help_text="Platform's unique post ID")
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default='POST')
    
    # Content
    caption = models.TextField(blank=True)
    hashtags = models.JSONField(default=list, blank=True, help_text="List of hashtags used")
    media_url = models.URLField(blank=True, max_length=500)
    thumbnail_url = models.URLField(blank=True, max_length=500)
    permalink = models.URLField(blank=True, max_length=500)
    
    # Timing
    published_at = models.DateTimeField(db_index=True)
    
    # Reach & Impressions
    reach = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    
    # Engagement Metrics
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    saves = models.PositiveIntegerField(default=0)
    engagement_total = models.PositiveIntegerField(default=0)
    engagement_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    
    # Video Metrics
    video_views = models.PositiveIntegerField(default=0)
    video_watch_time = models.PositiveIntegerField(default=0, help_text="Total watch time in seconds")
    avg_watch_time = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    video_completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Click Metrics
    link_clicks = models.PositiveIntegerField(default=0)
    
    # Metadata
    raw_data = models.JSONField(default=dict, blank=True)
    metrics_updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['brand', 'platform', 'platform_post_id']
        ordering = ['-published_at']
        verbose_name = 'Content Post'
        verbose_name_plural = 'Content Posts'
        indexes = [
            models.Index(fields=['brand', 'platform', '-published_at']),
            models.Index(fields=['brand', '-engagement_rate']),
        ]
    
    def __str__(self):
        return f"{self.brand.name} - {self.platform} - {self.published_at.strftime('%Y-%m-%d')}"
    
    @property
    def is_high_performer(self):
        """Check if post is performing above average."""
        # Compare to brand's average engagement rate for this platform
        from django.db.models import Avg
        avg_rate = ContentPost.objects.filter(
            brand=self.brand,
            platform=self.platform
        ).aggregate(avg=Avg('engagement_rate'))['avg'] or 0
        return self.engagement_rate > avg_rate * 1.5


# =============================================================================
# SECONDARY CONTACT MODEL - For tracking related contacts
# =============================================================================

class SecondaryContact(AuditedModel):
    """
    Secondary contacts for leads - parents, employers, spouses, next of kin, etc.
    Migrated to Learner upon conversion.
    """
    RELATIONSHIP_TYPES = [
        ('FATHER', 'Father'),
        ('MOTHER', 'Mother'),
        ('SPOUSE', 'Spouse'),
        ('EMPLOYER', 'Employer'),
        ('GIRLFRIEND', 'Girlfriend'),
        ('BOYFRIEND', 'Boyfriend'),
        ('GUARDIAN', 'Guardian'),
        ('SIBLING', 'Sibling'),
        ('NEXT_OF_KIN', 'Next of Kin'),
        ('OTHER', 'Other'),
    ]
    
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='secondary_contacts'
    )
    
    # Contact Details
    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_TYPES)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Additional info for employer contacts
    company_name = models.CharField(max_length=200, blank=True, help_text="For employer contacts")
    company_vat_number = models.CharField(max_length=50, blank=True, help_text="Company VAT number")
    job_title = models.CharField(max_length=100, blank=True, help_text="Contact's job title")
    notes = models.TextField(blank=True)
    
    # Primary contact flag
    is_primary = models.BooleanField(default=False, help_text="Primary contact for this relationship type")
    
    class Meta:
        ordering = ['-is_primary', 'relationship', 'name']
        verbose_name = 'Secondary Contact'
        verbose_name_plural = 'Secondary Contacts'
    
    def __str__(self):
        return f"{self.name} ({self.get_relationship_display()}) - {self.lead.get_full_name()}"


# =============================================================================
# EDUCATION HISTORY MODELS - Detailed education tracking
# =============================================================================

class EducationHistory(AuditedModel):
    """
    Detailed education history for leads.
    Tracks schools, colleges, qualifications obtained.
    """
    INSTITUTION_TYPES = [
        ('PRIMARY', 'Primary School'),
        ('HIGH_SCHOOL', 'High School'),
        ('COLLEGE', 'College'),
        ('UNIVERSITY', 'University'),
        ('TVET', 'TVET College'),
        ('OTHER', 'Other'),
    ]
    
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='education_history'
    )
    
    # Institution
    institution_type = models.CharField(max_length=20, choices=INSTITUTION_TYPES)
    institution_name = models.CharField(max_length=200)
    
    # Timeline
    year_started = models.PositiveIntegerField(null=True, blank=True)
    year_completed = models.PositiveIntegerField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    
    # Qualification
    qualification_obtained = models.CharField(max_length=200, blank=True, help_text="e.g., Matric, N6, Diploma")
    nqf_level = models.CharField(max_length=5, blank=True, help_text="NQF Level achieved")
    
    # Additional
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-year_completed', '-year_started']
        verbose_name = 'Education History'
        verbose_name_plural = 'Education Histories'
    
    def __str__(self):
        return f"{self.lead.get_full_name()} - {self.institution_name} ({self.get_institution_type_display()})"


class SubjectGrade(AuditedModel):
    """
    Individual subject grades for education history.
    Supports Math/Math Lit distinction for qualification eligibility.
    """
    SUBJECT_TYPES = [
        ('MATHEMATICS', 'Mathematics'),
        ('MATH_LITERACY', 'Mathematical Literacy'),
        ('ENGLISH', 'English'),
        ('AFRIKAANS', 'Afrikaans'),
        ('PHYSICAL_SCIENCE', 'Physical Science'),
        ('LIFE_SCIENCE', 'Life Science'),
        ('ACCOUNTING', 'Accounting'),
        ('BUSINESS_STUDIES', 'Business Studies'),
        ('ECONOMICS', 'Economics'),
        ('GEOGRAPHY', 'Geography'),
        ('HISTORY', 'History'),
        ('LIFE_ORIENTATION', 'Life Orientation'),
        ('CAT', 'Computer Applications Technology'),
        ('IT', 'Information Technology'),
        ('OTHER', 'Other'),
    ]
    
    education = models.ForeignKey(
        EducationHistory,
        on_delete=models.CASCADE,
        related_name='subjects'
    )
    
    # Subject
    subject_type = models.CharField(max_length=30, choices=SUBJECT_TYPES)
    subject_name = models.CharField(max_length=100, blank=True, help_text="Custom subject name if OTHER")
    
    # Grade
    mark_percentage = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage achieved (0-100)"
    )
    level = models.CharField(max_length=10, blank=True, help_text="Level achieved (1-7) or grade symbol")
    
    class Meta:
        ordering = ['subject_type']
        verbose_name = 'Subject Grade'
        verbose_name_plural = 'Subject Grades'
    
    def __str__(self):
        subject = self.subject_name if self.subject_type == 'OTHER' else self.get_subject_type_display()
        return f"{subject}: {self.mark_percentage}%" if self.mark_percentage else subject


# =============================================================================
# LEAD INTEREST MODEL - Track qualification interests
# =============================================================================

class LeadInterest(AuditedModel):
    """
    Track lead interests in qualifications/programmes.
    Supports primary, secondary, and other interest levels.
    """
    INTEREST_TYPES = [
        ('PRIMARY', 'Primary Interest'),
        ('SECONDARY', 'Secondary Interest'),
        ('OTHER', 'Other Interest'),
    ]
    
    PROGRAMME_TYPES = [
        ('QUALIFICATION', 'Full Qualification'),
        ('SKILLS_PROGRAMME', 'Skills Programme'),
        ('LEARNERSHIP', 'Learnership'),
        ('ARPL', 'ARPL (Recognition of Prior Learning)'),
        ('SHORT_COURSE', 'Short Course'),
    ]
    
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='interests'
    )
    
    qualification = models.ForeignKey(
        'academics.Qualification',
        on_delete=models.CASCADE,
        related_name='lead_interests'
    )
    
    interest_type = models.CharField(max_length=20, choices=INTEREST_TYPES, default='PRIMARY')
    programme_type = models.CharField(max_length=20, choices=PROGRAMME_TYPES, default='QUALIFICATION')
    
    # Additional
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['interest_type', 'created_at']
        unique_together = ['lead', 'qualification']
        verbose_name = 'Lead Interest'
        verbose_name_plural = 'Lead Interests'
    
    def __str__(self):
        return f"{self.lead.get_full_name()} - {self.qualification.name} ({self.get_interest_type_display()})"


# =============================================================================
# LEAD SALES ASSIGNMENT MODEL - Multi-salesperson assignment
# =============================================================================

class LeadSalesAssignment(AuditedModel):
    """
    Track multiple sales people assigned to a lead.
    One must be marked as primary for commission purposes.
    """
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='sales_assignments'
    )
    
    sales_person = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='lead_assignments'
    )
    
    is_primary = models.BooleanField(
        default=False,
        help_text="Primary sales person receives commission"
    )
    
    assigned_date = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sales_assignments_made'
    )
    
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-is_primary', '-assigned_date']
        unique_together = ['lead', 'sales_person']
        verbose_name = 'Lead Sales Assignment'
        verbose_name_plural = 'Lead Sales Assignments'
    
    def __str__(self):
        primary = " (Primary)" if self.is_primary else ""
        return f"{self.lead.get_full_name()} → {self.sales_person.get_full_name()}{primary}"
    
    def save(self, *args, **kwargs):
        # Ensure only one primary per lead
        if self.is_primary:
            LeadSalesAssignment.objects.filter(
                lead=self.lead,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


# =============================================================================
# SALES ENROLLMENT TRACKING FOR COMMISSION
# =============================================================================

class SalesEnrollmentRecord(AuditedModel):
    """
    Tracks enrollments for sales commission purposes.
    Links enrollment to sales person with compliance tracking.
    """
    FUNDING_TYPE_CHOICES = [
        ('PRIVATE_UPFRONT', 'Private - Upfront Payment'),
        ('PRIVATE_PMT_AGREEMENT', 'Private - Payment Agreement'),
        ('GOVERNMENT_BURSARY', 'Government Bursary'),
        ('CORPORATE_BURSARY', 'Corporate Bursary'),
        ('DG_BURSARY', 'DG Bursary'),
    ]
    
    # Link to enrollment
    enrollment = models.ForeignKey(
        'intakes.IntakeEnrollment',
        on_delete=models.CASCADE,
        related_name='sales_records'
    )
    
    # Sales attribution
    sales_person = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sales_enrollment_records'
    )
    is_primary_agent = models.BooleanField(
        default=True,
        help_text="Primary agent receives full commission"
    )
    
    # Campus for scoping
    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name='sales_enrollment_records'
    )
    
    # Dates
    enrollment_date = models.DateField()
    month_period = models.CharField(max_length=7, help_text="YYYY-MM format for reporting")
    
    # Funding (determines commission eligibility)
    funding_type = models.CharField(max_length=25, choices=FUNDING_TYPE_CHOICES)
    
    # Compliance status
    documents_uploaded_complete = models.BooleanField(
        default=False,
        help_text="All required documents uploaded"
    )
    documents_quality_approved = models.BooleanField(
        default=False,
        help_text="All documents passed quality check"
    )
    proof_of_payment_received = models.BooleanField(
        default=False,
        help_text="Any proof of payment uploaded"
    )
    
    # Compliance issues (JSON for details)
    compliance_issues = models.JSONField(
        default=list,
        blank=True,
        help_text="List of compliance issues: [{type: 'MISSING_DOC', doc_type: 'ID_COPY'}]"
    )
    
    # Tracking
    last_compliance_check = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-enrollment_date', 'sales_person']
        verbose_name = 'Sales Enrollment Record'
        verbose_name_plural = 'Sales Enrollment Records'
        indexes = [
            models.Index(fields=['month_period', 'sales_person']),
            models.Index(fields=['campus', 'month_period']),
        ]
    
    def __str__(self):
        return f"{self.enrollment} - {self.sales_person.get_full_name()} ({self.month_period})"
    
    @property
    def is_bursary(self):
        """Check if this is a bursary enrollment (no commission)"""
        return self.funding_type in ['GOVERNMENT_BURSARY', 'CORPORATE_BURSARY', 'DG_BURSARY']
    
    @property
    def commission_eligible(self):
        """
        Check if enrollment qualifies for commission.
        Requires: docs complete + quality approved + POP received + NOT bursary
        """
        if self.is_bursary:
            return False
        return (
            self.documents_uploaded_complete and
            self.documents_quality_approved and
            self.proof_of_payment_received
        )
    
    def save(self, *args, **kwargs):
        # Auto-set month_period from enrollment_date
        if self.enrollment_date and not self.month_period:
            self.month_period = self.enrollment_date.strftime('%Y-%m')
        super().save(*args, **kwargs)


# =============================================================================
# COMPLIANCE ALERT MODEL - Track document issues
# =============================================================================

class ComplianceAlert(AuditedModel):
    """
    Tracks compliance issues for enrollments.
    Used to alert sales and admin managers via dashboard.
    """
    ALERT_TYPES = [
        ('MISSING_DOCUMENTS', 'Missing Documents'),
        ('QUALITY_REJECTED', 'Document Quality Rejected'),
    ]
    
    enrollment_record = models.ForeignKey(
        SalesEnrollmentRecord,
        on_delete=models.CASCADE,
        related_name='compliance_alerts'
    )
    
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    
    # Details
    details = models.JSONField(
        default=list,
        help_text="List of issues: [{doc_type: 'ID_COPY', issue: 'Missing'}]"
    )
    
    # Campus for scoping
    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name='compliance_alerts'
    )
    
    # Resolution
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_alerts'
    )
    resolved_date = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Compliance Alert'
        verbose_name_plural = 'Compliance Alerts'
        indexes = [
            models.Index(fields=['campus', 'resolved']),
            models.Index(fields=['alert_type', 'resolved']),
        ]
    
    def __str__(self):
        status = "Resolved" if self.resolved else "Open"
        return f"{self.get_alert_type_display()} - {self.enrollment_record} ({status})"
    
    def resolve(self, user, notes=''):
        """Mark alert as resolved."""
        self.resolved = True
        self.resolved_by = user
        self.resolved_date = timezone.now()
        self.resolution_notes = notes
        self.save()
    
    @property
    def days_outstanding(self):
        """Days since alert was created."""
        if self.resolved:
            return 0
        delta = timezone.now() - self.created_at
        return delta.days
