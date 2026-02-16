"""
Tender Management Models

This module provides comprehensive tender tracking from discovery through approval,
with probability-based revenue forecasting and segmentation analytics.
"""

import uuid
import math
from decimal import Decimal
from datetime import date, timedelta

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from core.models import AuditedModel


class TenderSegment(AuditedModel):
    """
    Categorization for tenders to enable accurate historical analysis.
    Segments can be based on funder type, region, tender type, etc.
    """
    
    SEGMENT_TYPE_CHOICES = [
        ('FUNDER', 'By Funder'),
        ('REGION', 'By Region'),
        ('TYPE', 'By Tender Type'),
        ('SETA', 'By SETA'),
        ('VALUE', 'By Value Range'),
        ('CUSTOM', 'Custom Segment'),
    ]
    
    DECAY_MODEL_CHOICES = [
        ('LINEAR', 'Linear Decay'),
        ('EXPONENTIAL', 'Exponential Decay'),
        ('STEP', 'Step Function'),
        ('CUSTOM', 'Custom Curve'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES, default='CUSTOM')
    description = models.TextField(blank=True)
    
    # Probability decay configuration
    decay_model = models.CharField(
        max_length=20, 
        choices=DECAY_MODEL_CHOICES, 
        default='EXPONENTIAL',
        help_text="Mathematical model for probability decay over time"
    )
    initial_probability = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        default=Decimal('0.7000'),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Starting probability immediately after submission (0-1)"
    )
    decay_rate = models.DecimalField(
        max_digits=7, 
        decimal_places=5, 
        default=Decimal('0.01500'),
        help_text="Daily decay rate (for linear: amount per day, for exponential: lambda)"
    )
    floor_probability = models.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        default=Decimal('0.0500'),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Minimum probability floor (never drops below this)"
    )
    expected_response_days = models.PositiveIntegerField(
        default=90,
        help_text="Typical days until response for this segment"
    )
    
    # Historical performance
    total_applications = models.PositiveIntegerField(default=0)
    successful_applications = models.PositiveIntegerField(default=0)
    total_value_applied = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_value_won = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Step function thresholds (JSON for custom step configs)
    step_thresholds = models.JSONField(
        default=list,
        blank=True,
        help_text="For step function: list of {days: X, probability: Y} thresholds"
    )
    
    class Meta:
        ordering = ['segment_type', 'name']
        verbose_name = 'Tender Segment'
        verbose_name_plural = 'Tender Segments'
    
    def __str__(self):
        return f"{self.name} ({self.get_segment_type_display()})"
    
    @property
    def historical_success_rate(self):
        """Calculate historical success rate."""
        if self.total_applications == 0:
            return None
        return self.successful_applications / self.total_applications
    
    @property
    def average_value(self):
        """Calculate average tender value."""
        if self.total_applications == 0:
            return Decimal('0.00')
        return self.total_value_applied / self.total_applications
    
    def calculate_probability(self, days_since_submission):
        """
        Calculate current probability based on decay model and days elapsed.
        
        Args:
            days_since_submission: Number of days since tender was submitted
            
        Returns:
            Decimal probability between floor_probability and initial_probability
        """
        initial = float(self.initial_probability)
        floor = float(self.floor_probability)
        rate = float(self.decay_rate)
        days = days_since_submission
        
        if self.decay_model == 'LINEAR':
            # P(t) = max(floor, initial - rate * days)
            prob = max(floor, initial - (rate * days))
            
        elif self.decay_model == 'EXPONENTIAL':
            # P(t) = floor + (initial - floor) * e^(-rate * days)
            prob = floor + (initial - floor) * math.exp(-rate * days)
            
        elif self.decay_model == 'STEP':
            # Use step thresholds
            prob = initial
            for threshold in sorted(self.step_thresholds, key=lambda x: x.get('days', 0)):
                if days >= threshold.get('days', 0):
                    prob = threshold.get('probability', floor)
            prob = max(floor, prob)
            
        else:  # CUSTOM - fall back to exponential
            prob = floor + (initial - floor) * math.exp(-rate * days)
        
        return Decimal(str(round(prob, 4)))
    
    def update_statistics(self, application_value, was_successful):
        """Update segment statistics after an application is resolved."""
        self.total_applications += 1
        self.total_value_applied += application_value
        
        if was_successful:
            self.successful_applications += 1
            self.total_value_won += application_value
        
        self.save(update_fields=[
            'total_applications', 'successful_applications',
            'total_value_applied', 'total_value_won'
        ])


class TenderSource(AuditedModel):
    """
    Configuration for tender source websites to scrape.
    Supports both simple HTML scraping (BeautifulSoup) and JS-heavy sites (Playwright).
    """
    
    SCRAPER_TYPE_CHOICES = [
        ('BEAUTIFULSOUP', 'BeautifulSoup (Simple HTML)'),
        ('PLAYWRIGHT', 'Playwright (JavaScript-heavy)'),
        ('RSS', 'RSS Feed'),
        ('API', 'API Endpoint'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('ERROR', 'Error'),
        ('DISABLED', 'Disabled'),
    ]
    
    name = models.CharField(max_length=200, help_text="Source name (e.g., 'eTender Portal')")
    slug = models.SlugField(max_length=100, unique=True)
    base_url = models.URLField(help_text="Base URL for the tender source")
    
    # Scraper configuration
    scraper_type = models.CharField(max_length=20, choices=SCRAPER_TYPE_CHOICES, default='BEAUTIFULSOUP')
    scrape_config = models.JSONField(
        default=dict,
        help_text="""Scraper configuration including:
        - list_url: URL pattern for tender listings
        - selectors: CSS/XPath selectors for data extraction
        - pagination: Pagination handling config
        - auth: Authentication config if needed
        - headers: Custom headers to send
        """
    )
    
    # Scheduling
    scrape_frequency_hours = models.PositiveIntegerField(
        default=24,
        help_text="How often to scrape this source (in hours)"
    )
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    next_scrape_at = models.DateTimeField(null=True, blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    status_message = models.TextField(blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    max_failures_before_pause = models.PositiveIntegerField(default=5)
    
    # Statistics
    total_tenders_found = models.PositiveIntegerField(default=0)
    last_tenders_found = models.PositiveIntegerField(default=0)
    
    # Default segment for tenders from this source
    default_segment = models.ForeignKey(
        TenderSegment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sources',
        help_text="Default segment for tenders found from this source"
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Tender Source'
        verbose_name_plural = 'Tender Sources'
    
    def __str__(self):
        return self.name
    
    def mark_scraped(self, tenders_found=0, success=True, message=''):
        """Update scrape status after a scrape attempt."""
        self.last_scraped_at = timezone.now()
        self.next_scrape_at = timezone.now() + timedelta(hours=self.scrape_frequency_hours)
        self.last_tenders_found = tenders_found
        
        if success:
            self.total_tenders_found += tenders_found
            self.consecutive_failures = 0
            self.status = 'ACTIVE'
            self.status_message = message or f"Found {tenders_found} tenders"
        else:
            self.consecutive_failures += 1
            self.status_message = message
            if self.consecutive_failures >= self.max_failures_before_pause:
                self.status = 'ERROR'
        
        self.save()
    
    def get_scrape_config_display(self):
        """Return a formatted display of scrape configuration."""
        config = self.scrape_config or {}
        return {
            'list_url': config.get('list_url', 'Not configured'),
            'selectors': len(config.get('selectors', {})),
            'has_pagination': 'pagination' in config,
            'has_auth': 'auth' in config,
        }


class Tender(AuditedModel):
    """
    Core tender record representing a discovered tender opportunity.
    """
    
    STATUS_CHOICES = [
        ('DISCOVERED', 'Discovered'),
        ('REVIEWING', 'Under Review'),
        ('APPLICABLE', 'Applicable - Will Apply'),
        ('NOT_APPLICABLE', 'Not Applicable'),
        ('APPLIED', 'Application Submitted'),
        ('ACKNOWLEDGED', 'Acknowledgement Received'),
        ('PENDING', 'Pending Decision'),
        ('APPROVED', 'Approved'),
        ('PARTIALLY_APPROVED', 'Partially Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Tender Cancelled'),
        ('EXPIRED', 'Expired - Not Applied'),
    ]
    
    PRIORITY_CHOICES = [
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]
    
    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_number = models.CharField(max_length=100, db_index=True, help_text="Official tender reference number")
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    
    # Source
    source = models.ForeignKey(
        TenderSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenders'
    )
    source_url = models.URLField(blank=True, help_text="Direct URL to tender details")
    
    # Classification
    segment = models.ForeignKey(
        TenderSegment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenders'
    )
    funder = models.CharField(max_length=200, blank=True, help_text="Funding organization name")
    funder_type = models.CharField(max_length=50, blank=True, help_text="Type: SETA, Government, Private")
    region = models.CharField(max_length=100, blank=True, help_text="Geographic region")
    seta = models.ForeignKey(
        'learners.SETA',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenders'
    )
    
    # Dates
    published_date = models.DateField(null=True, blank=True, help_text="Date tender was published")
    opening_date = models.DateField(null=True, blank=True, help_text="Date tender window opens")
    closing_date = models.DateField(null=True, blank=True, help_text="Deadline for submissions")
    expected_award_date = models.DateField(null=True, blank=True, help_text="Expected date of award announcement")
    discovered_at = models.DateTimeField(auto_now_add=True)
    
    # Value
    estimated_value = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Estimated total tender value"
    )
    currency = models.CharField(max_length=3, default='ZAR')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DISCOVERED')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Requirements summary
    requirements_summary = models.TextField(blank=True, help_text="Summary of key requirements")
    eligibility_notes = models.TextField(blank=True, help_text="Notes on eligibility criteria")
    
    # Internal tracking
    assigned_to = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tenders',
        help_text="Staff member responsible for this tender"
    )
    notes = models.TextField(blank=True, help_text="Internal notes")
    tags = models.JSONField(default=list, blank=True, help_text="Tags for filtering")
    
    # Campus (optional multi-tenancy)
    campus = models.ForeignKey(
        'tenants.Campus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenders',
        help_text="Optional campus association"
    )
    
    class Meta:
        ordering = ['-closing_date', '-discovered_at']
        verbose_name = 'Tender'
        verbose_name_plural = 'Tenders'
        unique_together = [['reference_number', 'source']]
        permissions = [
            ('can_manage_tenders', 'Can manage tender pipeline'),
            ('can_apply_tenders', 'Can submit tender applications'),
            ('can_view_tender_analytics', 'Can view tender analytics'),
        ]
    
    def __str__(self):
        return f"{self.reference_number} - {self.title[:50]}"
    
    def get_absolute_url(self):
        return reverse('tenders:tender_detail', kwargs={'pk': self.pk})
    
    @property
    def days_until_closing(self):
        """Days remaining until closing date."""
        if not self.closing_date:
            return None
        delta = self.closing_date - date.today()
        return delta.days
    
    @property
    def is_open(self):
        """Check if tender is still open for applications."""
        if not self.closing_date:
            return True
        return date.today() <= self.closing_date
    
    @property
    def is_urgent(self):
        """Check if tender closes within 7 days."""
        days = self.days_until_closing
        return days is not None and 0 <= days <= 7


class TenderQualification(models.Model):
    """
    Link between a Tender and Qualifications we can offer for it.
    Tracks pricing and learner counts per qualification.
    """
    
    tender = models.ForeignKey(
        Tender,
        on_delete=models.CASCADE,
        related_name='qualifications'
    )
    qualification = models.ForeignKey(
        'academics.Qualification',
        on_delete=models.CASCADE,
        related_name='tenders'
    )
    
    # Pricing
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price per learner for this qualification"
    )
    min_learners = models.PositiveIntegerField(default=1)
    max_learners = models.PositiveIntegerField(null=True, blank=True)
    proposed_learners = models.PositiveIntegerField(null=True, blank=True)
    
    # Approved values (after award)
    approved_learners = models.PositiveIntegerField(null=True, blank=True)
    approved_unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = [['tender', 'qualification']]
        verbose_name = 'Tender Qualification'
        verbose_name_plural = 'Tender Qualifications'
    
    def __str__(self):
        return f"{self.tender.reference_number} - {self.qualification}"
    
    @property
    def proposed_total(self):
        """Calculate total proposed value."""
        if self.unit_price and self.proposed_learners:
            return self.unit_price * self.proposed_learners
        return None
    
    @property
    def approved_total(self):
        """Calculate total approved value."""
        if self.approved_unit_price and self.approved_learners:
            return self.approved_unit_price * self.approved_learners
        return None


class TenderApplication(AuditedModel):
    """
    Tracks the application/bid submission for a tender.
    Includes probability tracking for revenue forecasting.
    """
    
    STATUS_CHOICES = [
        ('PREPARING', 'Preparing'),
        ('SUBMITTED', 'Submitted'),
        ('ACKNOWLEDGED', 'Acknowledgement Received'),
        ('UNDER_EVALUATION', 'Under Evaluation'),
        ('SHORTLISTED', 'Shortlisted'),
        ('APPROVED', 'Approved'),
        ('PARTIALLY_APPROVED', 'Partially Approved'),
        ('REJECTED', 'Rejected'),
        ('WITHDRAWN', 'Withdrawn'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tender = models.ForeignKey(
        Tender,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    
    # Submission tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PREPARING')
    
    # Key dates
    preparation_started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_reference = models.CharField(max_length=100, blank=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    
    # What we applied for
    total_learners = models.PositiveIntegerField(default=0, help_text="Total learners across all qualifications")
    total_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Total tender amount applied for"
    )
    
    # Course type summary
    course_types = models.JSONField(
        default=list,
        help_text="List of course/qualification types included"
    )
    
    # Outcome (after decision)
    approved_learners = models.PositiveIntegerField(null=True, blank=True)
    approved_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Probability tracking
    current_probability = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.7000'),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Current success probability (0-1)"
    )
    probability_override = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Manual probability override (if set, ignores calculated probability)"
    )
    last_probability_update = models.DateTimeField(null=True, blank=True)
    
    # Expected revenue
    expected_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Probability-weighted expected revenue"
    )
    
    # Contact at funder
    funder_contact_name = models.CharField(max_length=200, blank=True)
    funder_contact_email = models.EmailField(blank=True)
    funder_contact_phone = models.CharField(max_length=20, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-submitted_at', '-created_at']
        verbose_name = 'Tender Application'
        verbose_name_plural = 'Tender Applications'
    
    def __str__(self):
        return f"Application for {self.tender.reference_number}"
    
    @property
    def days_since_submission(self):
        """Days elapsed since submission."""
        if not self.submitted_at:
            return 0
        delta = timezone.now() - self.submitted_at
        return delta.days
    
    @property
    def effective_probability(self):
        """Return override probability if set, otherwise current calculated probability."""
        if self.probability_override is not None:
            return self.probability_override
        return self.current_probability
    
    def calculate_probability(self):
        """
        Calculate current probability based on segment decay model.
        Returns the calculated probability (doesn't save automatically).
        """
        if self.status in ['APPROVED', 'PARTIALLY_APPROVED']:
            return Decimal('1.0000')
        elif self.status in ['REJECTED', 'WITHDRAWN']:
            return Decimal('0.0000')
        
        # Use segment's decay model
        segment = self.tender.segment
        if segment:
            days = self.days_since_submission
            return segment.calculate_probability(days)
        
        # Default exponential decay if no segment
        days = self.days_since_submission
        initial = 0.7
        floor = 0.05
        rate = 0.015
        prob = floor + (initial - floor) * math.exp(-rate * days)
        return Decimal(str(round(prob, 4)))
    
    def update_probability(self):
        """Recalculate and save probability and expected revenue."""
        self.current_probability = self.calculate_probability()
        self.expected_revenue = self.total_amount * self.effective_probability
        self.last_probability_update = timezone.now()
        self.save(update_fields=[
            'current_probability', 'expected_revenue', 'last_probability_update'
        ])
    
    def mark_submitted(self, submitted_at=None):
        """Mark application as submitted."""
        self.status = 'SUBMITTED'
        self.submitted_at = submitted_at or timezone.now()
        self.tender.status = 'APPLIED'
        self.tender.save(update_fields=['status'])
        self.update_probability()
        self.save()
    
    def mark_acknowledged(self, acknowledged_at=None, reference=''):
        """Mark application as acknowledged."""
        self.status = 'ACKNOWLEDGED'
        self.acknowledged_at = acknowledged_at or timezone.now()
        self.acknowledgement_reference = reference
        self.tender.status = 'ACKNOWLEDGED'
        self.tender.save(update_fields=['status'])
        self.save()
    
    def mark_approved(self, approved_learners=None, approved_amount=None, decision_at=None):
        """Mark application as approved."""
        self.status = 'APPROVED'
        self.decision_at = decision_at or timezone.now()
        self.approved_learners = approved_learners or self.total_learners
        self.approved_amount = approved_amount or self.total_amount
        self.current_probability = Decimal('1.0000')
        self.expected_revenue = self.approved_amount
        
        self.tender.status = 'APPROVED'
        self.tender.save(update_fields=['status'])
        
        # Update segment statistics
        if self.tender.segment:
            self.tender.segment.update_statistics(self.total_amount, True)
        
        self.save()
    
    def mark_rejected(self, reason='', decision_at=None):
        """Mark application as rejected."""
        self.status = 'REJECTED'
        self.decision_at = decision_at or timezone.now()
        self.rejection_reason = reason
        self.current_probability = Decimal('0.0000')
        self.expected_revenue = Decimal('0.00')
        
        self.tender.status = 'REJECTED'
        self.tender.save(update_fields=['status'])
        
        # Update segment statistics
        if self.tender.segment:
            self.tender.segment.update_statistics(self.total_amount, False)
        
        self.save()


class TenderDocument(AuditedModel):
    """
    Documents associated with tenders - requirements, submissions, etc.
    """
    
    CATEGORY_CHOICES = [
        ('TENDER_DOCUMENT', 'Original Tender Document'),
        ('REQUIREMENTS', 'Requirements Document'),
        ('APPLICATION', 'Application Form'),
        ('SUBMISSION', 'Submission Document'),
        ('SUPPORTING', 'Supporting Document'),
        ('ACKNOWLEDGEMENT', 'Acknowledgement'),
        ('AWARD', 'Award Letter'),
        ('CONTRACT', 'Contract'),
        ('OTHER', 'Other'),
    ]
    
    tender = models.ForeignKey(
        Tender,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    application = models.ForeignKey(
        TenderApplication,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='documents'
    )
    
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    file = models.FileField(upload_to='tenders/documents/%Y/%m/')
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, blank=True)
    
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=False, help_text="Is this a required submission document?")
    is_submitted = models.BooleanField(default=False, help_text="Has this been submitted with the application?")
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Tender Document'
        verbose_name_plural = 'Tender Documents'
    
    def __str__(self):
        return f"{self.tender.reference_number} - {self.name}"
    
    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)


class TenderNote(AuditedModel):
    """
    Timeline notes and activity log for tenders.
    """
    
    NOTE_TYPE_CHOICES = [
        ('STATUS_CHANGE', 'Status Change'),
        ('COMMENT', 'Comment'),
        ('CALL', 'Phone Call'),
        ('EMAIL', 'Email'),
        ('MEETING', 'Meeting'),
        ('REMINDER', 'Reminder'),
        ('SYSTEM', 'System Generated'),
    ]
    
    tender = models.ForeignKey(
        Tender,
        on_delete=models.CASCADE,
        related_name='timeline_notes'
    )
    application = models.ForeignKey(
        TenderApplication,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='timeline_notes'
    )
    
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='COMMENT')
    content = models.TextField()
    
    # For status changes
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    
    # Optional reminder
    reminder_date = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Tender Note'
        verbose_name_plural = 'Tender Notes'
    
    def __str__(self):
        return f"{self.tender.reference_number} - {self.get_note_type_display()}"


class TenderNotificationRule(AuditedModel):
    """
    Configurable notification triggers for tender events.
    """
    
    TRIGGER_CHOICES = [
        ('CLOSING_SOON', 'Tender Closing Soon'),
        ('NEW_TENDER', 'New Tender Discovered'),
        ('PROBABILITY_DROP', 'Probability Dropped Below Threshold'),
        ('NO_UPDATE', 'No Update for X Days'),
        ('MATCH_CRITERIA', 'Matches Search Criteria'),
        ('STATUS_CHANGE', 'Status Changed'),
    ]
    
    CHANNEL_CHOICES = [
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('PUSH', 'Push Notification'),
        ('SLACK', 'Slack'),
        ('TEAMS', 'Microsoft Teams'),
    ]
    
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    trigger_config = models.JSONField(
        default=dict,
        help_text="""Trigger-specific configuration:
        - CLOSING_SOON: {days_before: 7}
        - PROBABILITY_DROP: {threshold: 0.3}
        - NO_UPDATE: {days: 14}
        - MATCH_CRITERIA: {funder: 'SETA', region: 'Gauteng', min_value: 100000}
        """
    )
    
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='EMAIL')
    recipients = models.JSONField(
        default=list,
        help_text="List of user IDs or email addresses"
    )
    
    # Template
    subject_template = models.CharField(max_length=200, blank=True)
    body_template = models.TextField(blank=True)
    
    # Frequency limits
    cooldown_hours = models.PositiveIntegerField(
        default=24,
        help_text="Minimum hours between notifications of this type"
    )
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    total_triggered = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['trigger', 'name']
        verbose_name = 'Notification Rule'
        verbose_name_plural = 'Notification Rules'
    
    def __str__(self):
        return f"{self.name} ({self.get_trigger_display()})"
    
    def can_trigger(self):
        """Check if this rule can be triggered based on cooldown."""
        if not self.last_triggered_at:
            return True
        cooldown = timedelta(hours=self.cooldown_hours)
        return timezone.now() - self.last_triggered_at >= cooldown
    
    def mark_triggered(self):
        """Mark this rule as triggered."""
        self.last_triggered_at = timezone.now()
        self.total_triggered += 1
        self.save(update_fields=['last_triggered_at', 'total_triggered'])
