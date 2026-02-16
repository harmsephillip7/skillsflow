"""
Trade Tests Models

This module provides comprehensive trade test management including:
- Trade definitions linked to qualifications
- Trade test centres with capability tracking
- Trade test applications with candidate source tracking (Internal/External/ARPL)
- ARPL toolkit assessments
- Trade test bookings with multi-attempt tracking
- Trade test results and assessment reports
- Appeals management
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from core.models import AuditedModel
from tenants.models import TenantAwareModel

User = get_user_model()


# =============================================================================
# TRADE DEFINITIONS
# =============================================================================

class Trade(AuditedModel):
    """
    NAMB-registered trade definition.
    Links to Qualification for internal learners to auto-populate trade on application.
    """
    namb_code = models.CharField(
        max_length=20,
        unique=True,
        help_text='Official NAMB trade code'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Link to qualification for internal learners
    qualification = models.ForeignKey(
        'academics.Qualification',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='trades',
        help_text='Linked qualification for internal learners'
    )
    
    # SETA
    seta = models.ForeignKey(
        'learners.SETA',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='trades'
    )
    
    # Pass requirements
    theory_pass_mark = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=60.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Minimum percentage for theory component'
    )
    practical_pass_mark = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=60.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Minimum percentage for practical component'
    )
    
    # Duration
    typical_duration_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Typical training duration in months'
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Trade'
        verbose_name_plural = 'Trades'
    
    def __str__(self):
        return f"{self.name} ({self.namb_code})"


# =============================================================================
# TRADE TEST CENTRES
# =============================================================================

class TradeTestCentre(AuditedModel):
    """
    Trade test centre (NAMB/INDLELA accredited).
    Separate from Campus - dedicated trade test venues.
    """
    PROVINCE_CHOICES = [
        ('EC', 'Eastern Cape'),
        ('FS', 'Free State'),
        ('GP', 'Gauteng'),
        ('KZN', 'KwaZulu-Natal'),
        ('LP', 'Limpopo'),
        ('MP', 'Mpumalanga'),
        ('NC', 'Northern Cape'),
        ('NW', 'North West'),
        ('WC', 'Western Cape'),
    ]
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    
    # Location
    address = models.TextField()
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=3, choices=PROVINCE_CHOICES)
    postal_code = models.CharField(max_length=10, blank=True)
    
    # GPS coordinates for mapping
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    
    # Contact
    contact_person = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Accreditation
    accreditation_number = models.CharField(
        max_length=50,
        blank=True,
        help_text='NAMB/INDLELA accreditation number'
    )
    accreditation_expiry = models.DateField(null=True, blank=True)
    
    # Facilities
    max_daily_capacity = models.PositiveIntegerField(
        default=20,
        help_text='Maximum candidates per day'
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Trade Test Centre'
        verbose_name_plural = 'Trade Test Centres'
    
    def __str__(self):
        return f"{self.name} ({self.city})"
    
    @property
    def is_accreditation_valid(self):
        """Check if accreditation is still valid"""
        if not self.accreditation_expiry:
            return True  # No expiry set
        return self.accreditation_expiry >= timezone.now().date()
    
    @property
    def accreditation_days_remaining(self):
        """Days until accreditation expires"""
        if not self.accreditation_expiry:
            return None
        delta = self.accreditation_expiry - timezone.now().date()
        return delta.days


class TradeTestCentreCapability(AuditedModel):
    """
    Links Trade Test Centres to the trades they can assess.
    Through model for many-to-many with additional fields.
    """
    centre = models.ForeignKey(
        TradeTestCentre,
        on_delete=models.CASCADE,
        related_name='capabilities'
    )
    trade = models.ForeignKey(
        Trade,
        on_delete=models.CASCADE,
        related_name='centre_capabilities'
    )
    
    # Capacity
    max_candidates_per_session = models.PositiveIntegerField(
        default=10,
        help_text='Maximum candidates per test session for this trade'
    )
    
    # Scheduling
    next_available_date = models.DateField(
        null=True,
        blank=True,
        help_text='Next scheduled test date for this trade'
    )
    typical_test_days = models.CharField(
        max_length=50,
        blank=True,
        help_text='e.g., "Monday, Wednesday" or "First Monday of month"'
    )
    
    # Equipment/facilities specific to this trade
    equipment_notes = models.TextField(
        blank=True,
        help_text='Special equipment or facilities for this trade'
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['centre', 'trade']
        verbose_name = 'Centre Trade Capability'
        verbose_name_plural = 'Centre Trade Capabilities'
        unique_together = ['centre', 'trade']
    
    def __str__(self):
        return f"{self.centre.name} - {self.trade.name}"


# =============================================================================
# TRADE TEST APPLICATIONS
# =============================================================================

class TradeTestApplication(TenantAwareModel):
    """
    Trade test application tracking.
    Supports Internal (from enrollment), External, and ARPL candidates.
    """
    CANDIDATE_SOURCE_CHOICES = [
        ('INTERNAL', 'Internal Learner'),
        ('EXTERNAL', 'External Candidate'),
        ('ARPL', 'ARPL Candidate'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('LEARNER_PENDING', 'Awaiting Learner Record'),
        ('SUBMITTED', 'Submitted'),
        ('DOCUMENTS_PENDING', 'Documents Pending'),
        ('READY_FOR_NAMB', 'Ready for NAMB Submission'),
        ('SUBMITTED_TO_NAMB', 'Submitted to NAMB'),
        ('AWAITING_SCHEDULE', 'Awaiting Schedule'),
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    # Reference number
    reference_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )
    
    # Candidate source
    candidate_source = models.CharField(
        max_length=10,
        choices=CANDIDATE_SOURCE_CHOICES
    )
    
    # Learner (always required - redirect to create if not exists)
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.CASCADE,
        related_name='trade_test_applications'
    )
    
    # Enrollment (nullable - only for internal learners)
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='trade_test_applications',
        help_text='Linked enrollment for internal learners'
    )
    
    # Trade
    trade = models.ForeignKey(
        Trade,
        on_delete=models.PROTECT,
        related_name='applications'
    )
    
    # Centre (application made to specific centre)
    centre = models.ForeignKey(
        TradeTestCentre,
        on_delete=models.PROTECT,
        related_name='applications'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )
    
    # Dates
    application_date = models.DateField(default=timezone.now)
    namb_submission_date = models.DateField(null=True, blank=True)
    
    # NAMB reference
    namb_reference = models.CharField(max_length=50, blank=True)
    
    # Documents
    supporting_documents = models.JSONField(
        default=list,
        blank=True,
        help_text='List of uploaded document references'
    )
    
    # External candidate details (for non-internal)
    previous_training_provider = models.CharField(
        max_length=200,
        blank=True,
        help_text='Training provider for external candidates'
    )
    years_experience = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Years of practical experience'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(
        blank=True,
        help_text='Internal notes not visible to candidate'
    )
    
    class Meta:
        ordering = ['-application_date', '-created_at']
        verbose_name = 'Trade Test Application'
        verbose_name_plural = 'Trade Test Applications'
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Generate reference: TTA-YYYYMMDD-XXXX
            from django.utils.crypto import get_random_string
            date_str = timezone.now().strftime('%Y%m%d')
            random_str = get_random_string(4, '0123456789').upper()
            self.reference_number = f"TTA-{date_str}-{random_str}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.reference_number} - {self.learner}"
    
    @property
    def current_attempt(self):
        """Get the current/latest attempt number"""
        latest_booking = self.bookings.order_by('-attempt_number').first()
        return latest_booking.attempt_number if latest_booking else 0
    
    @property
    def remaining_attempts(self):
        """Get remaining attempts (max 3)"""
        return max(0, 3 - self.current_attempt)
    
    @property
    def has_passed(self):
        """Check if candidate has passed"""
        return self.bookings.filter(
            results__section='FINAL',
            results__result='COMPETENT'
        ).exists()


# =============================================================================
# ARPL TOOLKIT ASSESSMENT
# =============================================================================

class ARPLToolkitAssessment(AuditedModel):
    """
    ARPL (Artisan Recognition of Prior Learning) toolkit assessment.
    Pre-requisite assessment for ARPL candidates before trade test.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    RESULT_CHOICES = [
        ('PENDING', 'Pending Assessment'),
        ('READY', 'Ready for Trade Test'),
        ('NOT_READY', 'Not Ready - Further Training Required'),
        ('DEFERRED', 'Deferred'),
    ]
    
    application = models.OneToOneField(
        TradeTestApplication,
        on_delete=models.CASCADE,
        related_name='arpl_assessment'
    )
    
    # Scheduling
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.TimeField(null=True, blank=True)
    
    # Centre (defaults to application centre, can override)
    centre = models.ForeignKey(
        TradeTestCentre,
        on_delete=models.PROTECT,
        related_name='arpl_assessments',
        help_text='Defaults to application centre, can override'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    # Result
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default='PENDING'
    )
    result_date = models.DateField(null=True, blank=True)
    
    # Portfolio of evidence
    portfolio_documents = models.JSONField(
        default=list,
        blank=True,
        help_text='Uploaded portfolio documents'
    )
    
    # Assessment details
    assessor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='arpl_assessments_conducted'
    )
    assessor_notes = models.TextField(blank=True)
    
    # Recommendations
    training_recommendations = models.TextField(
        blank=True,
        help_text='Recommended training if not ready'
    )
    
    class Meta:
        ordering = ['-scheduled_date']
        verbose_name = 'ARPL Toolkit Assessment'
        verbose_name_plural = 'ARPL Toolkit Assessments'
    
    def __str__(self):
        return f"ARPL Assessment - {self.application.learner}"


# =============================================================================
# TRADE TEST BOOKINGS
# =============================================================================

class TradeTestBooking(TenantAwareModel):
    """
    Trade test booking/scheduling with multi-attempt tracking.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Submission'),
        ('SUBMITTED', 'Submitted to NAMB'),
        ('AWAITING_SCHEDULE', 'Awaiting Schedule'),
        ('CONFIRMED', 'Confirmed'),
        ('RESCHEDULED', 'Rescheduled'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show'),
    ]
    
    # Link to application
    application = models.ForeignKey(
        TradeTestApplication,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    
    # Attempt tracking (max 3)
    attempt_number = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(3)]
    )
    
    # Learner (denormalized for easier querying)
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.CASCADE,
        related_name='trade_test_bookings_new'
    )
    
    # Trade (denormalized)
    trade = models.ForeignKey(
        Trade,
        on_delete=models.PROTECT,
        related_name='bookings'
    )
    
    # Centre (defaults to application centre, can override for rescheduling)
    centre = models.ForeignKey(
        TradeTestCentre,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='bookings'
    )
    
    # Reference
    booking_reference = models.CharField(max_length=50, unique=True)
    
    # Dates
    submission_date = models.DateField(null=True, blank=True)
    scheduled_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date received from NAMB'
    )
    scheduled_time = models.TimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    # NAMB Reference
    namb_reference = models.CharField(max_length=50, blank=True)
    confirmation_letter = models.FileField(
        upload_to='trade_tests/confirmations/',
        blank=True
    )
    
    # Fees
    booking_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    fee_paid = models.BooleanField(default=False)
    fee_payment_date = models.DateField(null=True, blank=True)
    fee_payment_reference = models.CharField(max_length=50, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Link to previous attempt (for retry tracking)
    previous_attempt = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='retry_booking'
    )
    
    class Meta:
        ordering = ['-scheduled_date', '-attempt_number']
        verbose_name = 'Trade Test Booking'
        verbose_name_plural = 'Trade Test Bookings'
        unique_together = ['application', 'attempt_number']
    
    def save(self, *args, **kwargs):
        if not self.booking_reference:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.booking_reference = f"TTB-{timestamp}-A{self.attempt_number}"
        
        # Denormalize from application
        if self.application:
            self.learner = self.application.learner
            self.trade = self.application.trade
            if not self.centre:
                self.centre = self.application.centre
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.learner} - Attempt {self.attempt_number} ({self.booking_reference})"
    
    @property
    def is_final_attempt(self):
        """Check if this is the final (3rd) attempt"""
        return self.attempt_number >= 3
    
    def create_next_attempt(self):
        """Create booking for next attempt (if attempts remaining)"""
        if self.attempt_number >= 3:
            return None
        
        next_booking = TradeTestBooking.objects.create(
            application=self.application,
            attempt_number=self.attempt_number + 1,
            learner=self.learner,
            trade=self.trade,
            centre=self.centre,
            status='AWAITING_SCHEDULE',
            previous_attempt=self,
        )
        return next_booking


# =============================================================================
# TRADE TEST RESULTS
# =============================================================================

class TradeTestResult(AuditedModel):
    """
    Trade test result with assessment report tracking.
    """
    RESULT_CHOICES = [
        ('COMPETENT', 'Competent'),
        ('NOT_YET_COMPETENT', 'Not Yet Competent'),
        ('ABSENT', 'Absent'),
        ('DEFERRED', 'Deferred'),
    ]
    
    SECTION_CHOICES = [
        ('THEORY', 'Theory'),
        ('PRACTICAL', 'Practical'),
        ('FINAL', 'Final/Overall'),
    ]
    
    booking = models.ForeignKey(
        TradeTestBooking,
        on_delete=models.CASCADE,
        related_name='results'
    )
    
    # Result details
    section = models.CharField(max_length=20, choices=SECTION_CHOICES)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Percentage score if applicable'
    )
    
    # Dates
    test_date = models.DateField()
    result_date = models.DateField(null=True, blank=True)
    
    # Assessment Report (not certificate)
    report_reference = models.CharField(
        max_length=50,
        blank=True,
        help_text='NAMB assessment report reference'
    )
    report_date = models.DateField(null=True, blank=True)
    report_file = models.FileField(
        upload_to='trade_tests/assessment_reports/',
        blank=True,
        help_text='Uploaded assessment report from NAMB'
    )
    
    # Assessor details
    assessor_name = models.CharField(max_length=100, blank=True)
    assessor_registration = models.CharField(
        max_length=50,
        blank=True,
        help_text='Assessor registration number'
    )
    assessor_comments = models.TextField(blank=True)
    
    # Next attempt booking (for NOT_YET_COMPETENT results)
    next_attempt_booking = models.OneToOneField(
        TradeTestBooking,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='previous_result',
        help_text='Auto-created for failed attempts if retries remaining'
    )
    
    class Meta:
        ordering = ['-test_date']
        verbose_name = 'Trade Test Result'
        verbose_name_plural = 'Trade Test Results'
        unique_together = ['booking', 'section']
    
    def __str__(self):
        return f"{self.booking.learner} - {self.section}: {self.result}"
    
    @property
    def passed(self):
        return self.result == 'COMPETENT'
    
    @property
    def can_retry(self):
        """Check if candidate can retry after this result"""
        if self.result != 'NOT_YET_COMPETENT':
            return False
        return self.booking.attempt_number < 3


# =============================================================================
# TRADE TEST APPEALS
# =============================================================================

class TradeTestAppeal(AuditedModel):
    """
    Trade test result appeal.
    """
    STATUS_CHOICES = [
        ('SUBMITTED', 'Appeal Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('SCHEDULED', 'Re-test Scheduled'),
        ('UPHELD', 'Appeal Upheld'),
        ('DISMISSED', 'Appeal Dismissed'),
        ('WITHDRAWN', 'Withdrawn'),
    ]
    
    result = models.ForeignKey(
        TradeTestResult,
        on_delete=models.CASCADE,
        related_name='appeals'
    )
    
    # Appeal details
    appeal_date = models.DateField()
    grounds = models.TextField(help_text='Grounds for appeal')
    supporting_documents = models.FileField(
        upload_to='trade_tests/appeals/',
        blank=True
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='SUBMITTED'
    )
    
    # Resolution
    resolution_date = models.DateField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    new_result = models.CharField(
        max_length=20,
        choices=TradeTestResult.RESULT_CHOICES,
        blank=True
    )
    
    # Re-test
    retest_date = models.DateField(null=True, blank=True)
    retest_booking = models.ForeignKey(
        TradeTestBooking,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='appeal_retests'
    )
    
    class Meta:
        ordering = ['-appeal_date']
        verbose_name = 'Trade Test Appeal'
        verbose_name_plural = 'Trade Test Appeals'
    
    def __str__(self):
        return f"Appeal - {self.result.booking.learner}"
