"""
LMS Sync app models
Moodle integration for course sync, grades, and completion
"""
from django.db import models
from core.models import AuditedModel
from tenants.models import TenantAwareModel


class MoodleInstance(models.Model):
    """
    Moodle LMS instance configuration
    """
    brand = models.OneToOneField(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='moodle_instance'
    )
    
    name = models.CharField(max_length=100)
    base_url = models.URLField()
    
    # API credentials
    ws_token = models.TextField()  # Web services token (encrypted)
    
    # Sync settings
    sync_enabled = models.BooleanField(default=True)
    auto_create_users = models.BooleanField(default=True)
    auto_enroll = models.BooleanField(default=True)
    sync_grades = models.BooleanField(default=True)
    sync_completions = models.BooleanField(default=True)
    
    # Last sync
    last_sync = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=50, blank=True)
    last_sync_error = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Moodle Instance'
        verbose_name_plural = 'Moodle Instances'
    
    def __str__(self):
        return f"{self.brand.name} - {self.name}"


class MoodleCategory(models.Model):
    """
    Moodle course category mapping
    """
    instance = models.ForeignKey(
        MoodleInstance,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    
    moodle_id = models.PositiveIntegerField()
    name = models.CharField(max_length=200)
    parent_id = models.PositiveIntegerField(null=True, blank=True)
    
    # Map to internal qualification
    qualification = models.ForeignKey(
        'academics.Qualification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='moodle_categories'
    )
    
    class Meta:
        unique_together = ['instance', 'moodle_id']
        verbose_name = 'Moodle Category'
        verbose_name_plural = 'Moodle Categories'
    
    def __str__(self):
        return f"{self.instance.name} - {self.name}"


class MoodleCourse(models.Model):
    """
    Moodle course mapping
    """
    instance = models.ForeignKey(
        MoodleInstance,
        on_delete=models.CASCADE,
        related_name='courses'
    )
    
    moodle_id = models.PositiveIntegerField()
    shortname = models.CharField(max_length=100)
    fullname = models.CharField(max_length=254)
    
    category = models.ForeignKey(
        MoodleCategory,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='courses'
    )
    
    # Map to internal module
    module = models.ForeignKey(
        'academics.Module',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='moodle_courses'
    )
    
    # Course info
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Sync
    sync_enabled = models.BooleanField(default=True)
    last_synced = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['instance', 'moodle_id']
        verbose_name = 'Moodle Course'
        verbose_name_plural = 'Moodle Courses'
    
    def __str__(self):
        return f"{self.shortname} - {self.fullname}"


class MoodleUser(models.Model):
    """
    Moodle user mapping
    """
    instance = models.ForeignKey(
        MoodleInstance,
        on_delete=models.CASCADE,
        related_name='moodle_users'
    )
    
    moodle_id = models.PositiveIntegerField()
    username = models.CharField(max_length=100)
    email = models.EmailField()
    
    # Map to internal learner
    learner = models.ForeignKey(
        'learners.Learner',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='moodle_accounts'
    )
    
    # Map to internal user (staff)
    user = models.ForeignKey(
        'core.User',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='moodle_accounts'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    last_access = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['instance', 'moodle_id']
        verbose_name = 'Moodle User'
        verbose_name_plural = 'Moodle Users'
    
    def __str__(self):
        return f"{self.username} ({self.instance.name})"


class MoodleEnrollment(AuditedModel):
    """
    Moodle course enrollment tracking
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Sync'),
        ('ENROLLED', 'Enrolled'),
        ('SUSPENDED', 'Suspended'),
        ('COMPLETED', 'Completed'),
        ('SYNC_ERROR', 'Sync Error'),
    ]
    
    moodle_user = models.ForeignKey(
        MoodleUser,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    moodle_course = models.ForeignKey(
        MoodleCourse,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    
    # Link to internal enrollment
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='moodle_enrollments'
    )
    
    # Moodle enrollment info
    moodle_enrollment_id = models.PositiveIntegerField(null=True, blank=True)
    role_id = models.PositiveIntegerField(default=5)  # Default student role
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Dates
    enrolled_at = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Sync
    last_synced = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['moodle_user', 'moodle_course']
        verbose_name = 'Moodle Enrollment'
        verbose_name_plural = 'Moodle Enrollments'
    
    def __str__(self):
        return f"{self.moodle_user.username} - {self.moodle_course.shortname}"


class MoodleGrade(AuditedModel):
    """
    Moodle grade sync
    """
    enrollment = models.ForeignKey(
        MoodleEnrollment,
        on_delete=models.CASCADE,
        related_name='grades'
    )
    
    # Grade item info
    grade_item_id = models.PositiveIntegerField()
    item_name = models.CharField(max_length=200)
    item_type = models.CharField(max_length=50)  # course, category, manual, mod
    
    # Grade
    raw_grade = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True, blank=True
    )
    final_grade = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True, blank=True
    )
    grade_max = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True, blank=True
    )
    grade_min = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        default=0
    )
    
    # Percentage
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True, blank=True
    )
    
    # Sync
    synced_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-synced_at']
        verbose_name = 'Moodle Grade'
        verbose_name_plural = 'Moodle Grades'
    
    def __str__(self):
        return f"{self.enrollment} - {self.item_name}: {self.final_grade}"


class MoodleCompletion(AuditedModel):
    """
    Moodle course completion tracking
    """
    enrollment = models.ForeignKey(
        MoodleEnrollment,
        on_delete=models.CASCADE,
        related_name='completions'
    )
    
    # Completion status
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Progress
    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    activities_completed = models.PositiveIntegerField(default=0)
    activities_total = models.PositiveIntegerField(default=0)
    
    # Time spent
    time_spent_seconds = models.PositiveIntegerField(default=0)
    last_access = models.DateTimeField(null=True, blank=True)
    
    # Sync
    synced_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-synced_at']
        verbose_name = 'Moodle Completion'
        verbose_name_plural = 'Moodle Completions'
    
    def __str__(self):
        status = "Complete" if self.is_completed else f"{self.progress_percentage}%"
        return f"{self.enrollment} - {status}"


class MoodleActivity(models.Model):
    """
    Moodle activity completion tracking
    """
    enrollment = models.ForeignKey(
        MoodleEnrollment,
        on_delete=models.CASCADE,
        related_name='activity_completions'
    )
    
    # Activity info
    cm_id = models.PositiveIntegerField()  # Course module ID
    activity_name = models.CharField(max_length=200)
    module_type = models.CharField(max_length=50)  # quiz, assign, forum, etc.
    
    # Completion
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # For graded activities
    grade = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True, blank=True
    )
    grade_max = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True, blank=True
    )
    
    synced_at = models.DateTimeField()
    
    class Meta:
        unique_together = ['enrollment', 'cm_id']
        verbose_name = 'Moodle Activity'
        verbose_name_plural = 'Moodle Activities'
    
    def __str__(self):
        return f"{self.enrollment.moodle_user.username} - {self.activity_name}"


class MoodleSyncLog(AuditedModel):
    """
    Sync operation log
    """
    SYNC_TYPES = [
        ('USERS', 'Users'),
        ('COURSES', 'Courses'),
        ('ENROLLMENTS', 'Enrollments'),
        ('GRADES', 'Grades'),
        ('COMPLETIONS', 'Completions'),
        ('FULL', 'Full Sync'),
    ]
    
    STATUS_CHOICES = [
        ('STARTED', 'Started'),
        ('SUCCESS', 'Success'),
        ('PARTIAL', 'Partial Success'),
        ('FAILED', 'Failed'),
    ]
    
    instance = models.ForeignKey(
        MoodleInstance,
        on_delete=models.CASCADE,
        related_name='sync_logs'
    )
    
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    direction = models.CharField(max_length=10)  # PUSH, PULL, BIDIRECTIONAL
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='STARTED')
    
    # Stats
    records_processed = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    
    # Timing
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Errors
    error_details = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Moodle Sync Log'
        verbose_name_plural = 'Moodle Sync Logs'
    
    def __str__(self):
        return f"{self.instance.name} - {self.sync_type} - {self.status}"


class MoodleCourseActivity(models.Model):
    """
    Individual activity/resource within a Moodle course (quiz, assignment, etc.)
    Used for AI mapping to QCTO assessment criteria.
    """
    ACTIVITY_TYPES = [
        ('QUIZ', 'Quiz'),
        ('ASSIGN', 'Assignment'),
        ('LESSON', 'Lesson'),
        ('SCORM', 'SCORM Package'),
        ('WORKSHOP', 'Workshop'),
        ('CHOICE', 'Choice'),
        ('FORUM', 'Forum'),
        ('OTHER', 'Other'),
    ]
    
    course = models.ForeignKey(
        MoodleCourse,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    
    # Moodle identifiers
    moodle_id = models.PositiveIntegerField(help_text="Activity ID from Moodle")
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    
    # Activity details
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    grade_max = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.00,
        help_text="Maximum grade for this activity"
    )
    
    # Sync metadata
    last_synced = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['course', 'name']
        verbose_name = 'Moodle Course Activity'
        verbose_name_plural = 'Moodle Course Activities'
        unique_together = [['course', 'moodle_id']]
    
    def __str__(self):
        return f"{self.course.shortname} - {self.name}"


class AssessmentMapping(models.Model):
    """
    Maps Moodle activities to QCTO assessment criteria.
    AI-suggested mappings require SME approval.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    # Relations
    moodle_activity = models.ForeignKey(
        MoodleCourseActivity,
        on_delete=models.CASCADE,
        related_name='criteria_mappings'
    )
    qcto_criteria = models.ForeignKey(
        'academics.QCTOAssessmentCriteria',
        on_delete=models.CASCADE,
        related_name='moodle_mappings'
    )
    assessment_activity = models.ForeignKey(
        'assessments.AssessmentActivity',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='lms_mappings',
        help_text="Link to internal assessment activity"
    )
    
    # AI mapping metadata
    ai_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="AI confidence score (0-100)"
    )
    ai_reasoning = models.TextField(
        blank=True,
        help_text="AI explanation for this mapping suggestion"
    )
    
    # Review workflow
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(
        'core.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_mappings'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_mappings'
    )
    
    class Meta:
        ordering = ['-ai_confidence', 'status', '-created_at']
        verbose_name = 'Assessment Mapping'
        verbose_name_plural = 'Assessment Mappings'
        unique_together = [['moodle_activity', 'qcto_criteria']]
    
    def __str__(self):
        return f"{self.moodle_activity.name} → {self.qcto_criteria.criteria_code}"


class GradeThreshold(models.Model):
    """
    Grade thresholds for pass/fail determination.
    Global default or per-brand override.
    """
    brand = models.OneToOneField(
        'tenants.Brand',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='grade_threshold',
        help_text="Leave blank for global default"
    )
    
    pass_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50.00,
        help_text="Minimum percentage to pass"
    )
    
    is_global = models.BooleanField(
        default=False,
        help_text="Is this the global default threshold?"
    )
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='threshold_updates'
    )
    
    class Meta:
        verbose_name = 'Grade Threshold'
        verbose_name_plural = 'Grade Thresholds'
    
    def __str__(self):
        if self.is_global:
            return f"Global Default: {self.pass_percentage}%"
        return f"{self.brand.name}: {self.pass_percentage}%"
    
    @classmethod
    def get_threshold_for_brand(cls, brand):
        """Get threshold for brand, falling back to global default"""
        try:
            return cls.objects.get(brand=brand)
        except cls.DoesNotExist:
            return cls.objects.get(is_global=True)
