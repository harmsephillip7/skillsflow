"""
Assessments app models
Assessment activities, results, moderation, and PoE management
"""
from django.db import models
from django.utils import timezone
from core.models import AuditedModel, User


class AssessmentActivity(AuditedModel):
    """
    Assessment activity within a module
    E.g., Knowledge Test 1, Practical Assessment 2, Workplace Logbook
    """
    ACTIVITY_TYPES = [
        ('TEST', 'Knowledge Test'),
        ('ASSIGNMENT', 'Assignment'),
        ('PRACTICAL', 'Practical Assessment'),
        ('LOGBOOK', 'Workplace Logbook'),
        ('PORTFOLIO', 'Portfolio Evidence'),
        ('SIMULATION', 'Simulation'),
        ('ORAL', 'Oral Assessment'),
        ('EXTERNAL', 'External Assessment'),
    ]
    
    ASSESSMENT_PHASE_CHOICES = [
        ('FORMATIVE', 'Formative'),
        ('SUMMATIVE', 'Summative'),
    ]
    
    module = models.ForeignKey(
        'academics.Module', 
        on_delete=models.CASCADE, 
        related_name='assessment_activities'
    )
    
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Type and settings
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    max_attempts = models.PositiveIntegerField(default=3)
    
    # QCTO Assessment Phase
    assessment_phase = models.CharField(
        max_length=10,
        choices=ASSESSMENT_PHASE_CHOICES,
        default='FORMATIVE',
        help_text='Formative (internal) or Summative (external/final) assessment'
    )
    is_eisa = models.BooleanField(
        default=False,
        verbose_name='Is EISA',
        help_text='External Integrated Summative Assessment - final QCTO exam'
    )
    
    # External assessment (AQP managed)
    is_external = models.BooleanField(default=False)
    aqp = models.ForeignKey(
        'AQP', 
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    
    # Ordering
    sequence_order = models.PositiveIntegerField(default=1)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['module', 'sequence_order']
        unique_together = ['module', 'code']
        verbose_name = 'Assessment Activity'
        verbose_name_plural = 'Assessment Activities'
    
    def __str__(self):
        return f"{self.code} - {self.title}"
    
    def save(self, *args, **kwargs):
        # Auto-set assessment_phase to SUMMATIVE if is_eisa or is_external
        if self.is_eisa or self.is_external:
            self.assessment_phase = 'SUMMATIVE'
        super().save(*args, **kwargs)
    
    @property
    def is_formative(self):
        """Returns True if this is a formative (internal) assessment"""
        return self.assessment_phase == 'FORMATIVE'
    
    @property
    def is_summative(self):
        """Returns True if this is a summative (external/final) assessment"""
        return self.assessment_phase == 'SUMMATIVE'


class AQP(models.Model):
    """
    Assessment Quality Partner
    External body that conducts final assessments for QCTO qualifications
    """
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    
    # Contact
    contact_person = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Integration
    api_endpoint = models.URLField(blank=True)
    api_key = models.CharField(max_length=200, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'AQP'
        verbose_name_plural = 'AQPs'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class AssessmentResult(AuditedModel):
    """
    Assessment result for a learner
    QCTO-compliant with Competent/NYC workflow
    """
    RESULT_CHOICES = [
        ('C', 'Competent'),
        ('NYC', 'Not Yet Competent'),
        ('ABS', 'Absent'),
        ('DEF', 'Deferred'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_MOD', 'Pending Moderation'),
        ('MODERATED', 'Moderated'),
        ('FINALIZED', 'Finalized'),
        ('APPEALED', 'Under Appeal'),
    ]
    
    enrollment = models.ForeignKey(
        'academics.Enrollment', 
        on_delete=models.CASCADE, 
        related_name='assessment_results'
    )
    activity = models.ForeignKey(
        AssessmentActivity, 
        on_delete=models.PROTECT, 
        related_name='results'
    )
    
    # Attempt tracking
    attempt_number = models.PositiveIntegerField(default=1)
    
    # Assessment
    assessor = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='assessed_results'
    )
    result = models.CharField(max_length=5, choices=RESULT_CHOICES)
    percentage_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, blank=True
    )
    assessment_date = models.DateField()
    
    # Feedback
    feedback = models.TextField(blank=True)
    evidence_reference = models.CharField(max_length=100, blank=True)
    
    # Workflow Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    is_flagged_moderation = models.BooleanField(default=False)
    
    # Lock mechanism
    locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='locked_results'
    )
    
    # Digital Signature
    assessor_signature = models.TextField(blank=True)
    assessor_signed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-assessment_date']
        unique_together = ['enrollment', 'activity', 'attempt_number']
        indexes = [
            models.Index(fields=['enrollment', 'status']),
            models.Index(fields=['activity', 'result']),
        ]
    
    def __str__(self):
        return f"{self.enrollment} - {self.activity.code} - Attempt {self.attempt_number}"
    
    def lock_result(self, user):
        """Lock the result after moderation"""
        self.locked = True
        self.locked_at = timezone.now()
        self.locked_by = user
        self.status = 'FINALIZED'
        self.save()


class ModerationRecord(AuditedModel):
    """
    Moderation record for assessment results
    Tracks moderator review and decisions
    """
    assessment_result = models.ForeignKey(
        AssessmentResult, 
        on_delete=models.CASCADE, 
        related_name='moderation_records'
    )
    moderator = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='moderation_records'
    )
    
    # Moderation outcome
    original_result = models.CharField(max_length=5)
    moderated_result = models.CharField(max_length=5)
    is_upheld = models.BooleanField()
    
    # Details
    comments = models.TextField()
    moderated_at = models.DateTimeField()
    
    # Digital Signature
    moderator_signature = models.TextField(blank=True)
    moderator_signed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-moderated_at']
    
    def __str__(self):
        return f"Moderation - {self.assessment_result}"


class PoESubmission(AuditedModel):
    """
    Portfolio of Evidence submission
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected - Resubmit'),
        ('PARTIAL', 'Partially Approved'),
    ]
    
    enrollment = models.ForeignKey(
        'academics.Enrollment', 
        on_delete=models.CASCADE, 
        related_name='poe_submissions'
    )
    module = models.ForeignKey(
        'academics.Module', 
        on_delete=models.PROTECT, 
        related_name='poe_submissions'
    )
    
    # Submission
    submission_date = models.DateField()
    description = models.TextField(blank=True)
    
    # Review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='poe_reviews'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-submission_date']
        verbose_name = 'PoE Submission'
        verbose_name_plural = 'PoE Submissions'
    
    def __str__(self):
        return f"{self.enrollment} - {self.module.code} - {self.submission_date}"


class PoEDocument(models.Model):
    """
    Links documents to PoE submissions
    """
    poe_submission = models.ForeignKey(
        PoESubmission, 
        on_delete=models.CASCADE, 
        related_name='documents'
    )
    document = models.ForeignKey(
        'learners.Document', 
        on_delete=models.PROTECT,
        related_name='poe_submissions'
    )
    page_reference = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'PoE Document'
        verbose_name_plural = 'PoE Documents'
    
    def __str__(self):
        return f"{self.poe_submission} - {self.document}"


class ExternalAssessment(AuditedModel):
    """
    External assessment booking and results (via AQP)
    """
    STATUS_CHOICES = [
        ('BOOKED', 'Booked'),
        ('CONFIRMED', 'Confirmed'),
        ('COMPLETED', 'Completed'),
        ('CERTIFIED', 'Certified'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    RESULT_CHOICES = [
        ('C', 'Competent'),
        ('NYC', 'Not Yet Competent'),
    ]
    
    enrollment = models.ForeignKey(
        'academics.Enrollment', 
        on_delete=models.CASCADE, 
        related_name='external_assessments'
    )
    qualification = models.ForeignKey(
        'academics.Qualification', 
        on_delete=models.PROTECT
    )
    aqp = models.ForeignKey(
        AQP, 
        on_delete=models.PROTECT, 
        related_name='assessments'
    )
    
    # Booking
    booking_date = models.DateField()
    booking_reference = models.CharField(max_length=50)
    
    # Assessment
    assessment_date = models.DateField(null=True, blank=True)
    assessment_venue = models.CharField(max_length=200, blank=True)
    
    # Result
    result = models.CharField(max_length=5, choices=RESULT_CHOICES, blank=True)
    result_date = models.DateField(null=True, blank=True)
    certificate_number = models.CharField(max_length=50, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BOOKED')
    
    class Meta:
        ordering = ['-booking_date']
        verbose_name = 'External Assessment'
        verbose_name_plural = 'External Assessments'
    
    def __str__(self):
        return f"{self.enrollment} - {self.aqp.code} - {self.booking_reference}"


class AppealRecord(AuditedModel):
    """
    Assessment result appeals
    """
    STATUS_CHOICES = [
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('UPHELD', 'Upheld (Result Changed)'),
        ('DISMISSED', 'Dismissed'),
        ('WITHDRAWN', 'Withdrawn'),
    ]
    
    assessment_result = models.ForeignKey(
        AssessmentResult, 
        on_delete=models.CASCADE, 
        related_name='appeals'
    )
    
    # Appeal details
    appeal_date = models.DateField()
    grounds = models.TextField()
    supporting_documents = models.ManyToManyField(
        'learners.Document',
        blank=True,
        related_name='appeal_records'
    )
    
    # Review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUBMITTED')
    reviewed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='appeal_reviews'
    )
    review_date = models.DateField(null=True, blank=True)
    outcome = models.TextField(blank=True)
    new_result = models.CharField(max_length=5, blank=True)
    
    class Meta:
        ordering = ['-appeal_date']
        verbose_name = 'Appeal Record'
        verbose_name_plural = 'Appeal Records'
    
    def __str__(self):
        return f"Appeal - {self.assessment_result} - {self.status}"
