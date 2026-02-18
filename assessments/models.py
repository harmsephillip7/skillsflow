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


class AssessmentSchedule(AuditedModel):
    """
    Scheduled assessment for a cohort.
    Auto-generated from implementation plans with manual override capability.
    Provides transparency to learners, facilitators, parents, and management.
    """
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('POSTPONED', 'Postponed'),
    ]
    
    cohort = models.ForeignKey(
        'logistics.Cohort',
        on_delete=models.CASCADE,
        related_name='assessment_schedules'
    )
    activity = models.ForeignKey(
        AssessmentActivity,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    
    # Scheduling
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    
    # Venue
    venue = models.ForeignKey(
        'logistics.Venue',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assessment_schedules'
    )
    
    # Facilitator/Assessor
    assessor = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assessment_schedules'
    )
    
    # Auto-generation tracking
    is_auto_generated = models.BooleanField(default=True)
    source_session = models.ForeignKey(
        'logistics.ScheduleSession',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assessment_schedules',
        help_text="ScheduleSession this was generated from"
    )
    
    # Override tracking
    original_date = models.DateField(null=True, blank=True)
    override_reason = models.TextField(blank=True)
    overridden_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='overridden_schedules'
    )
    overridden_at = models.DateTimeField(null=True, blank=True)
    
    # Preparation materials
    preparation_notes = models.TextField(blank=True, help_text="Notes for learners on how to prepare")
    materials_required = models.TextField(blank=True, help_text="Materials learners should bring")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # Notifications
    learners_notified = models.BooleanField(default=False)
    learners_notified_at = models.DateTimeField(null=True, blank=True)
    parents_notified = models.BooleanField(default=False)
    parents_notified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['scheduled_date', 'scheduled_time']
        verbose_name = 'Assessment Schedule'
        verbose_name_plural = 'Assessment Schedules'
        indexes = [
            models.Index(fields=['cohort', 'scheduled_date']),
            models.Index(fields=['activity', 'status']),
        ]
    
    def __str__(self):
        return f"{self.cohort.code} - {self.activity.code} - {self.scheduled_date}"
    
    def reschedule(self, new_date, new_time=None, reason='', user=None):
        """Reschedule the assessment with audit trail"""
        if not self.original_date:
            self.original_date = self.scheduled_date
        self.scheduled_date = new_date
        if new_time:
            self.scheduled_time = new_time
        self.override_reason = reason
        self.overridden_by = user
        self.overridden_at = timezone.now()
        self.is_auto_generated = False
        self.status = 'SCHEDULED'
        self.save()
    
    @classmethod
    def generate_from_cohort_plan(cls, cohort, user=None):
        """
        Generate assessment schedules from cohort implementation plan.
        Creates schedules for all assessment activities in the cohort's modules.
        """
        from logistics.models import CohortImplementationModuleSlot
        
        schedules_created = []
        
        # Get all module slots from cohort implementation plan
        if hasattr(cohort, 'implementation_plan'):
            for phase in cohort.implementation_plan.phases.all():
                for slot in phase.module_slots.all():
                    module = slot.module
                    
                    # Get all assessment activities for this module
                    for activity in module.assessment_activities.filter(is_active=True):
                        # Calculate scheduled date based on slot
                        scheduled_date = slot.actual_end or slot.planned_end
                        
                        # Check if schedule already exists
                        existing = cls.objects.filter(
                            cohort=cohort,
                            activity=activity
                        ).first()
                        
                        if not existing:
                            schedule = cls.objects.create(
                                cohort=cohort,
                                activity=activity,
                                scheduled_date=scheduled_date,
                                is_auto_generated=True,
                                assessor=cohort.facilitator
                            )
                            schedules_created.append(schedule)
        
        return schedules_created


class AssessmentEvidence(AuditedModel):
    """
    Photo/file evidence attached to an assessment result.
    Supports offline capture with sync.
    """
    EVIDENCE_TYPES = [
        ('PHOTO', 'Photo'),
        ('DOCUMENT', 'Document'),
        ('VIDEO', 'Video'),
        ('AUDIO', 'Audio'),
    ]
    
    assessment_result = models.ForeignKey(
        AssessmentResult,
        on_delete=models.CASCADE,
        related_name='evidence'
    )
    
    evidence_type = models.CharField(max_length=20, choices=EVIDENCE_TYPES, default='PHOTO')
    file = models.FileField(upload_to='assessments/evidence/%Y/%m/')
    thumbnail = models.ImageField(upload_to='assessments/evidence/thumbs/%Y/%m/', null=True, blank=True)
    
    # Metadata
    description = models.CharField(max_length=200, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)
    captured_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='captured_evidence'
    )
    
    # Offline sync
    offline_id = models.CharField(max_length=100, blank=True, help_text="Client-side ID for offline sync")
    synced_at = models.DateTimeField(null=True, blank=True)
    
    # Geolocation (optional)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    class Meta:
        ordering = ['-captured_at']
        verbose_name = 'Assessment Evidence'
        verbose_name_plural = 'Assessment Evidence'
    
    def __str__(self):
        return f"{self.assessment_result} - {self.evidence_type} - {self.captured_at}"


class AssessmentSyncLog(models.Model):
    """
    Audit log for offline sync operations.
    Tracks conflicts and resolution for facilitator notification.
    """
    SYNC_TYPES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('CONFLICT', 'Conflict Resolved'),
        ('EVIDENCE', 'Evidence Uploaded'),
    ]
    
    RESOLUTION_CHOICES = [
        ('CLIENT_WINS', 'Client Timestamp Wins'),
        ('SERVER_WINS', 'Server Timestamp Wins'),
        ('MERGED', 'Merged Data'),
        ('MANUAL', 'Manual Resolution Required'),
    ]
    
    assessment_result = models.ForeignKey(
        AssessmentResult,
        on_delete=models.CASCADE,
        related_name='sync_logs'
    )
    
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    synced_at = models.DateTimeField(auto_now_add=True)
    synced_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='sync_logs'
    )
    
    # Client data
    client_timestamp = models.DateTimeField()
    client_device_id = models.CharField(max_length=100, blank=True)
    offline_id = models.CharField(max_length=100, blank=True)
    
    # Server state at sync time
    server_timestamp = models.DateTimeField(null=True, blank=True)
    
    # Conflict resolution
    had_conflict = models.BooleanField(default=False)
    resolution = models.CharField(max_length=20, choices=RESOLUTION_CHOICES, blank=True)
    resolution_details = models.JSONField(null=True, blank=True)
    
    # Changes
    changes_applied = models.JSONField(default=dict)
    # Structure: {"field": {"old": value, "new": value}, ...}
    
    # Notification
    facilitator_notified = models.BooleanField(default=False)
    facilitator_notified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-synced_at']
        verbose_name = 'Assessment Sync Log'
        verbose_name_plural = 'Assessment Sync Logs'
        indexes = [
            models.Index(fields=['assessment_result', 'synced_at']),
            models.Index(fields=['had_conflict', 'facilitator_notified']),
        ]
    
    def __str__(self):
        return f"{self.assessment_result} - {self.sync_type} - {self.synced_at}"

