"""
Learners app models
Learner profiles, documents, employers, and related models
"""
import uuid
from django.db import models
from django.core.validators import MinLengthValidator
from core.models import AuditedModel, User
from tenants.models import TenantAwareModel


def validate_sa_id(value):
    """Validate South African ID number using Luhn algorithm"""
    if not value or len(value) != 13:
        return False
    
    try:
        # Extract date of birth
        year = int(value[0:2])
        month = int(value[2:4])
        day = int(value[4:6])
        
        # Validate date components
        if month < 1 or month > 12:
            return False
        if day < 1 or day > 31:
            return False
        
        # Luhn algorithm check
        total = 0
        for i, digit in enumerate(value[:-1]):
            d = int(digit)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        
        check_digit = (10 - (total % 10)) % 10
        return check_digit == int(value[-1])
    except (ValueError, IndexError):
        return False


class Address(AuditedModel):
    """
    Reusable address model
    """
    line_1 = models.CharField(max_length=200)
    line_2 = models.CharField(max_length=200, blank=True)
    suburb = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=50, default='South Africa')
    
    class Meta:
        verbose_name_plural = 'Addresses'
    
    def __str__(self):
        return f"{self.line_1}, {self.city}"
    
    def get_full_address(self):
        parts = [self.line_1]
        if self.line_2:
            parts.append(self.line_2)
        if self.suburb:
            parts.append(self.suburb)
        parts.extend([self.city, self.province, self.postal_code])
        return ', '.join(parts)


class Learner(TenantAwareModel):
    """
    Learner model with full NLRD compliance fields
    """
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    POPULATION_GROUP_CHOICES = [
        ('A', 'African'),
        ('C', 'Coloured'),
        ('I', 'Indian'),
        ('W', 'White'),
        ('O', 'Other'),
    ]
    
    CITIZENSHIP_CHOICES = [
        ('SA', 'South African'),
        ('PR', 'Permanent Resident'),
        ('O', 'Other'),
    ]
    
    DISABILITY_CHOICES = [
        ('N', 'None'),
        ('1', 'Sight (even with glasses)'),
        ('2', 'Hearing (even with hearing aid)'),
        ('3', 'Communication (talking, listening)'),
        ('4', 'Physical (moving, standing, grasping)'),
        ('5', 'Intellectual (learning, remembering)'),
        ('6', 'Emotional (behavioural, psychological)'),
        ('7', 'Multiple'),
        ('9', 'Disabled but unspecified'),
    ]
    
    SOCIO_ECONOMIC_CHOICES = [
        ('E', 'Employed'),
        ('U', 'Unemployed'),
        ('S', 'Self-employed'),
        ('N', 'NEET (Not in Employment, Education, or Training)'),
    ]
    
    NQF_LEVEL_CHOICES = [
        ('0', 'No schooling'),
        ('1', 'NQF 1 / Grade 9'),
        ('2', 'NQF 2 / Grade 10'),
        ('3', 'NQF 3 / Grade 11'),
        ('4', 'NQF 4 / Grade 12 / Matric'),
        ('5', 'NQF 5 / Higher Certificate'),
        ('6', 'NQF 6 / Diploma / Advanced Certificate'),
        ('7', 'NQF 7 / Bachelor\'s Degree'),
        ('8', 'NQF 8 / Honours / Postgrad Diploma'),
        ('9', 'NQF 9 / Master\'s Degree'),
        ('10', 'NQF 10 / Doctoral Degree'),
    ]
    
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
    
    # Link to user account (optional - for portal access)
    user = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='learner_profile'
    )
    
    # Internal reference
    learner_number = models.CharField(max_length=20, unique=True)
    
    # Identity
    sa_id_number = models.CharField(
        max_length=13, 
        null=True, blank=True,
        validators=[MinLengthValidator(13)],
        help_text='South African ID Number (13 digits)'
    )
    passport_number = models.CharField(max_length=20, null=True, blank=True)
    passport_country = models.CharField(max_length=50, blank=True)
    
    # Personal Details
    title = models.CharField(max_length=10, blank=True)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50)
    preferred_name = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    
    # SETA Demographics (Required for NLRD)
    population_group = models.CharField(max_length=1, choices=POPULATION_GROUP_CHOICES)
    citizenship = models.CharField(max_length=2, choices=CITIZENSHIP_CHOICES, default='SA')
    home_language = models.CharField(max_length=50, blank=True)
    disability_status = models.CharField(max_length=1, choices=DISABILITY_CHOICES, default='N')
    disability_description = models.TextField(blank=True)
    
    # Socio-Economic
    socio_economic_status = models.CharField(
        max_length=1, 
        choices=SOCIO_ECONOMIC_CHOICES,
        default='U'
    )
    highest_qualification = models.CharField(
        max_length=2, 
        choices=NQF_LEVEL_CHOICES,
        default='4'
    )
    
    # Contact
    email = models.EmailField()
    email_secondary = models.EmailField(blank=True)
    phone_mobile = models.CharField(max_length=20)
    phone_home = models.CharField(max_length=20, blank=True)
    phone_work = models.CharField(max_length=20, blank=True)
    
    # Addresses
    physical_address = models.ForeignKey(
        Address, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='physical_learners'
    )
    postal_address = models.ForeignKey(
        Address, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='postal_learners'
    )
    province_code = models.CharField(max_length=3, choices=PROVINCE_CHOICES, blank=True)
    municipality_code = models.CharField(max_length=10, blank=True)
    
    # Compliance
    popia_consent_given = models.BooleanField(default=False)
    popia_consent_date = models.DateTimeField(null=True, blank=True)
    marketing_consent = models.BooleanField(default=False)
    
    # Financial
    financial_hold = models.BooleanField(default=False)
    financial_hold_reason = models.TextField(blank=True)
    
    # Sage Intacct Integration
    sage_customer_id = models.CharField(
        max_length=50,
        null=True, blank=True,
        help_text='Sage Intacct Customer ID for payment integration'
    )
    
    # Photo
    photo = models.ImageField(upload_to='learner_photos/', null=True, blank=True)
    
    # Digital Signature (captured during onboarding, locked after first capture)
    signature = models.ImageField(
        upload_to='signatures/learners/%Y/%m/',
        null=True, blank=True,
        help_text='Digital signature PNG (400x150px, transparent background)'
    )
    signature_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text='SHA-256 hash for integrity verification'
    )
    signature_captured_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When signature was captured'
    )
    signature_locked = models.BooleanField(
        default=False,
        help_text='Signature is locked after first capture'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['learner_number']),
            models.Index(fields=['sa_id_number']),
            models.Index(fields=['email']),
            models.Index(fields=['last_name', 'first_name']),
        ]
    
    def __str__(self):
        return f"{self.learner_number} - {self.get_full_name()}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def compliance_status(self):
        """
        Calculate compliance traffic light status
        Returns: 'RED', 'YELLOW', or 'GREEN'
        """
        required_docs = ['ID_COPY', 'MATRIC', 'AGREEMENT']
        docs = self.documents.filter(
            document_type__in=required_docs, 
            is_deleted=False
        )
        
        if docs.count() < len(required_docs):
            return 'RED'
        
        pending = docs.filter(verified=False).exists()
        if pending:
            return 'YELLOW'
        
        return 'GREEN'
    
    def is_valid_sa_id(self):
        """Validate SA ID number"""
        return validate_sa_id(self.sa_id_number)


class Document(AuditedModel):
    """
    Document storage for learner files
    Supports compliance traffic light system
    """
    DOCUMENT_TYPES = [
        ('ID_COPY', 'ID Copy'),
        ('MATRIC', 'Matric Certificate'),
        ('AGREEMENT', 'Learner Agreement'),
        ('POE', 'Portfolio of Evidence'),
        ('QUALIFICATION', 'Prior Qualification'),
        ('EMPLOYER_LETTER', 'Employer Confirmation Letter'),
        ('CV', 'Curriculum Vitae'),
        ('PROOF_ADDRESS', 'Proof of Address'),
        ('BANK_CONFIRM', 'Bank Confirmation'),
        ('PROOF_OF_PAYMENT', 'Proof of Payment'),
        ('OTHER', 'Other'),
    ]
    
    learner = models.ForeignKey(
        Learner, 
        on_delete=models.CASCADE, 
        related_name='documents'
    )
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    
    # File
    file = models.FileField(upload_to='documents/%Y/%m/')
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)  # bytes
    file_hash = models.CharField(max_length=64, blank=True)  # SHA-256
    
    # Versioning
    version = models.PositiveIntegerField(default=1)
    replaces = models.ForeignKey(
        'self', 
        null=True, blank=True, 
        on_delete=models.SET_NULL,
        related_name='replaced_by'
    )
    
    # Verification
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_documents'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Expiry
    expiry_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.learner.learner_number} - {self.get_document_type_display()}"
    
    @property
    def status(self):
        """Get document status"""
        if not self.verified:
            return 'PENDING'
        if self.expiry_date and self.expiry_date < models.functions.Now():
            return 'EXPIRED'
        return 'VALID'


class SETA(models.Model):
    """
    Sector Education and Training Authority
    """
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'SETA'
        verbose_name_plural = 'SETAs'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Employer(AuditedModel):
    """
    Employer/Company for workplace-based learning
    """
    name = models.CharField(max_length=200)
    trading_name = models.CharField(max_length=200, blank=True)
    
    # Registration
    registration_number = models.CharField(max_length=20, blank=True)  # CIPC
    vat_number = models.CharField(max_length=20, blank=True)
    sdl_number = models.CharField(max_length=20, blank=True)  # Skills Dev Levy
    sic_code = models.CharField(max_length=10, blank=True)  # Standard Industry Code
    
    # SETA
    seta = models.ForeignKey(
        SETA, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='employers'
    )
    
    # Contact
    contact_person = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Address
    address = models.ForeignKey(
        Address, 
        on_delete=models.SET_NULL, 
        null=True, blank=True
    )
    
    # Workplace Approval (for WBL)
    workplace_approved = models.BooleanField(default=False)
    approval_date = models.DateField(null=True, blank=True)
    approval_expiry = models.DateField(null=True, blank=True)
    approval_reference = models.CharField(max_length=50, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class LearnerEmployment(AuditedModel):
    """
    Links learners to their employers
    Tracks employment history and workplace mentors
    """
    learner = models.ForeignKey(
        Learner, 
        on_delete=models.CASCADE, 
        related_name='employments'
    )
    employer = models.ForeignKey(
        Employer, 
        on_delete=models.PROTECT, 
        related_name='learner_employments'
    )
    
    # Position
    position = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    
    # Duration
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=True)
    
    # Workplace Mentor
    mentor_name = models.CharField(max_length=100, blank=True)
    mentor_email = models.EmailField(blank=True)
    mentor_phone = models.CharField(max_length=20, blank=True)
    mentor_position = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Learner Employment'
        verbose_name_plural = 'Learner Employments'
    
    def __str__(self):
        return f"{self.learner} at {self.employer}"


# =====================================================
# WORKPLACE-BASED LEARNING (WBL) MODELS
# =====================================================

class WorkplaceAttendance(AuditedModel):
    """
    Daily attendance record for workplace-based learning.
    Tracks clock-in/out times, hours worked, and leave types.
    """
    ATTENDANCE_TYPE_CHOICES = [
        ('PRESENT', 'Present'),
        ('ANNUAL', 'Annual Leave'),
        ('SICK', 'Sick Leave'),
        ('FAMILY', 'Family Responsibility Leave'),
        ('UNPAID', 'Unpaid Leave'),
        ('PUBLIC_HOLIDAY', 'Public Holiday'),
        ('ABSENT', 'Absent Without Leave'),
        ('SUSPENDED', 'Suspended'),
    ]
    
    placement = models.ForeignKey(
        'corporate.WorkplacePlacement',
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    
    # Date and time
    date = models.DateField()
    clock_in = models.TimeField(null=True, blank=True)
    clock_out = models.TimeField(null=True, blank=True)
    hours_worked = models.DecimalField(
        max_digits=4, decimal_places=2,
        null=True, blank=True,
        help_text='Hours worked (calculated or manual)'
    )
    
    # Attendance type
    attendance_type = models.CharField(
        max_length=20,
        choices=ATTENDANCE_TYPE_CHOICES,
        default='PRESENT'
    )
    
    # Leave documentation
    leave_document = models.ForeignKey(
        'core.ManagedDocument',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='attendance_leave_docs',
        help_text='Supporting document for leave (e.g., sick note)'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Verification workflow
    mentor_verified = models.BooleanField(default=False)
    mentor_verified_at = models.DateTimeField(null=True, blank=True)
    mentor_verified_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='mentor_verified_attendance'
    )
    
    facilitator_verified = models.BooleanField(default=False)
    facilitator_verified_at = models.DateTimeField(null=True, blank=True)
    facilitator_verified_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='facilitator_verified_attendance'
    )
    
    # Offline sync support
    offline_created = models.BooleanField(
        default=False,
        help_text='Record was created offline and synced later'
    )
    offline_sync_id = models.CharField(max_length=100, blank=True)
    client_uuid = models.UUIDField(
        null=True,
        blank=True,
        help_text='Client-generated UUID for offline deduplication'
    )
    sync_status = models.CharField(
        max_length=20,
        choices=[
            ('SYNCED', 'Synced'),
            ('PENDING', 'Pending Sync'),
            ('FAILED', 'Sync Failed'),
        ],
        default='SYNCED'
    )
    
    # GPS location capture
    gps_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='GPS latitude at clock-in'
    )
    gps_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='GPS longitude at clock-in'
    )
    gps_accuracy = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='GPS accuracy in meters'
    )
    gps_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When GPS coordinates were captured'
    )
    
    # Photo proof of attendance
    photo = models.ImageField(
        upload_to='attendance_photos/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text='Photo proof of attendance (selfie at workplace)'
    )
    
    # Verification overrides for edge cases
    off_site_work_verified = models.BooleanField(
        default=False,
        help_text='Mentor verified that work was performed off-site (outside geofence)'
    )
    time_override_clock_in = models.TimeField(
        null=True,
        blank=True,
        help_text='Manual override for clock-in time (if GPS timestamp incorrect)'
    )
    time_override_clock_out = models.TimeField(
        null=True,
        blank=True,
        help_text='Manual override for clock-out time (if GPS timestamp incorrect)'
    )
    override_notes = models.TextField(
        blank=True,
        help_text='Explanation for any manual overrides applied'
    )
    override_applied_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='attendance_overrides_applied',
        help_text='User who applied the override'
    )
    override_applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the override was applied'
    )
    
    class Meta:
        ordering = ['-date']
        unique_together = ['placement', 'date']
        verbose_name = 'Workplace Attendance'
        verbose_name_plural = 'Workplace Attendance Records'
        indexes = [
            models.Index(fields=['placement', 'date']),
            models.Index(fields=['date', 'attendance_type']),
        ]
    
    def __str__(self):
        return f"{self.placement.learner} - {self.date} - {self.get_attendance_type_display()}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate hours if clock in/out provided
        if self.clock_in and self.clock_out and not self.hours_worked:
            from datetime import datetime, timedelta
            clock_in_dt = datetime.combine(self.date, self.clock_in)
            clock_out_dt = datetime.combine(self.date, self.clock_out)
            if clock_out_dt < clock_in_dt:
                # Handle overnight shifts
                clock_out_dt += timedelta(days=1)
            delta = clock_out_dt - clock_in_dt
            self.hours_worked = round(delta.total_seconds() / 3600, 2)
        super().save(*args, **kwargs)
    
    @property
    def is_fully_verified(self):
        return self.mentor_verified and self.facilitator_verified


class AttendanceAuditLog(models.Model):
    """
    Comprehensive audit trail for all attendance record changes.
    Tracks verifications, rejections, overrides, and field edits.
    Optimized for archiving: routine logs archived after 3 years, latest overrides retained.
    """
    ACTION_CHOICES = [
        ('VERIFY', 'Verified'),
        ('REJECT', 'Rejected'),
        ('OVERRIDE', 'Override Applied'),
        ('EDIT', 'Field Edited'),
        ('CREATE', 'Record Created'),
    ]
    
    # Core relationships
    attendance = models.ForeignKey(
        'WorkplaceAttendance',
        on_delete=models.CASCADE,
        related_name='audit_logs',
        help_text='Attendance record being audited'
    )
    
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='attendance_audit_actions',
        help_text='User who performed the action'
    )
    
    changed_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the action was performed',
        db_index=True
    )
    
    # Action details
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        db_index=True,
        help_text='Type of action performed'
    )
    
    field_changed = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text='Specific field that was changed (for EDIT/OVERRIDE actions)'
    )
    
    old_value = models.TextField(
        blank=True,
        help_text='Previous value before change'
    )
    
    new_value = models.TextField(
        blank=True,
        help_text='New value after change'
    )
    
    # Additional context
    notes = models.TextField(
        blank=True,
        help_text='Additional notes or reason for change'
    )
    
    # GPS location at time of action (for mobile verifications)
    action_gps_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='GPS latitude where action was performed'
    )
    action_gps_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='GPS longitude where action was performed'
    )
    
    # Archival management
    archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Archived logs moved to cold storage'
    )
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'Attendance Audit Log'
        verbose_name_plural = 'Attendance Audit Logs'
        indexes = [
            models.Index(fields=['attendance', '-changed_at']),
            models.Index(fields=['action', 'archived', 'changed_at']),
            models.Index(fields=['attendance', 'field_changed', '-changed_at']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} by {self.changed_by} at {self.changed_at}"


class WorkplaceLogbookEntry(AuditedModel):
    """
    Monthly logbook entry for workplace-based learning.
    Contains tasks completed, challenges faced, and requires sign-off
    from learner, mentor, and facilitator.
    """
    placement = models.ForeignKey(
        'corporate.WorkplacePlacement',
        on_delete=models.CASCADE,
        related_name='logbook_entries'
    )
    
    # Period
    month = models.PositiveIntegerField(help_text='Month number (1-12)')
    year = models.PositiveIntegerField()
    
    # Content
    tasks_completed = models.JSONField(
        default=list,
        help_text='List of tasks completed during the month'
    )
    skills_developed = models.TextField(
        blank=True,
        help_text='Skills and competencies developed'
    )
    challenges_faced = models.TextField(
        blank=True,
        help_text='Challenges encountered and how they were addressed'
    )
    learning_outcomes = models.TextField(
        blank=True,
        help_text='Key learning outcomes for the period'
    )
    
    # Hours summary
    total_hours_worked = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True
    )
    total_days_present = models.PositiveIntegerField(null=True, blank=True)
    
    # Learner sign-off
    learner_signed = models.BooleanField(default=False)
    learner_signed_at = models.DateTimeField(null=True, blank=True)
    learner_comments = models.TextField(blank=True)
    
    # Mentor sign-off
    mentor_signed = models.BooleanField(default=False)
    mentor_signed_at = models.DateTimeField(null=True, blank=True)
    mentor_signed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='mentor_signed_logbooks'
    )
    mentor_comments = models.TextField(blank=True)
    mentor_rating = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Overall performance rating 1-5'
    )
    
    # Facilitator sign-off
    facilitator_signed = models.BooleanField(default=False)
    facilitator_signed_at = models.DateTimeField(null=True, blank=True)
    facilitator_signed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='facilitator_signed_logbooks'
    )
    facilitator_comments = models.TextField(blank=True)
    
    # Scanned copy of physical logbook
    scanned_document = models.ForeignKey(
        'core.ManagedDocument',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='logbook_scans'
    )
    
    class Meta:
        ordering = ['-year', '-month']
        unique_together = ['placement', 'month', 'year']
        verbose_name = 'Workplace Logbook Entry'
        verbose_name_plural = 'Workplace Logbook Entries'
    
    def __str__(self):
        return f"{self.placement.learner} - {self.month}/{self.year}"
    
    @property
    def period_display(self):
        from calendar import month_name
        return f"{month_name[self.month]} {self.year}"
    
    @property
    def month_start_date(self):
        """Return first day of the month"""
        from datetime import date
        return date(self.year, self.month, 1)
    
    @property
    def month_end_date(self):
        """Return last day of the month"""
        from datetime import date
        from calendar import monthrange
        _, last_day = monthrange(self.year, self.month)
        return date(self.year, self.month, last_day)
    
    @property
    def is_fully_signed(self):
        return self.learner_signed and self.mentor_signed and self.facilitator_signed
    
    @property
    def sign_off_status(self):
        """Return sign-off status for display"""
        if self.is_fully_signed:
            return 'COMPLETE'
        if self.mentor_signed:
            return 'AWAITING_FACILITATOR'
        if self.learner_signed:
            return 'AWAITING_MENTOR'
        return 'AWAITING_LEARNER'


class WorkplaceModuleCompletion(AuditedModel):
    """
    Tracks completion of workplace modules (WMs) / practical components.
    Each module requires mentor and facilitator sign-off.
    """
    placement = models.ForeignKey(
        'corporate.WorkplacePlacement',
        on_delete=models.CASCADE,
        related_name='module_completions'
    )
    
    # Module details
    module_code = models.CharField(max_length=50)
    module_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Completion
    started_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    
    # Evidence
    evidence_description = models.TextField(
        blank=True,
        help_text='Description of evidence demonstrating competence'
    )
    evidence_document = models.ForeignKey(
        'core.ManagedDocument',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='wm_evidence'
    )
    
    # Mentor sign-off
    mentor_signed = models.BooleanField(default=False)
    mentor_signed_at = models.DateTimeField(null=True, blank=True)
    mentor_signed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='mentor_signed_modules'
    )
    mentor_comments = models.TextField(blank=True)
    
    # Facilitator sign-off
    facilitator_signed = models.BooleanField(default=False)
    facilitator_signed_at = models.DateTimeField(null=True, blank=True)
    facilitator_signed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='facilitator_signed_modules'
    )
    facilitator_comments = models.TextField(blank=True)
    
    class Meta:
        ordering = ['module_code']
        unique_together = ['placement', 'module_code']
        verbose_name = 'Workplace Module Completion'
        verbose_name_plural = 'Workplace Module Completions'
    
    def __str__(self):
        return f"{self.placement.learner} - {self.module_code}"
    
    @property
    def is_complete(self):
        return self.completed_date is not None and self.mentor_signed and self.facilitator_signed
    
    @property
    def status(self):
        if not self.started_date:
            return 'NOT_STARTED'
        if not self.completed_date:
            return 'IN_PROGRESS'
        if not self.mentor_signed:
            return 'AWAITING_MENTOR'
        if not self.facilitator_signed:
            return 'AWAITING_FACILITATOR'
        return 'COMPLETE'


class StipendCalculation(AuditedModel):
    """
    Monthly stipend/allowance calculation for learners on placement.
    Calculates based on attendance, leave policy, and daily rate.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('CALCULATED', 'Calculated'),
        ('VERIFIED', 'Verified'),
        ('APPROVED', 'Approved'),
        ('PAID', 'Paid'),
    ]
    
    placement = models.ForeignKey(
        'corporate.WorkplacePlacement',
        on_delete=models.CASCADE,
        related_name='stipend_calculations'
    )
    
    # Period
    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()
    
    # Attendance breakdown
    total_working_days = models.PositiveIntegerField(
        help_text='Total working days in the month'
    )
    days_present = models.PositiveIntegerField(default=0)
    days_annual_leave = models.PositiveIntegerField(default=0)
    days_sick_leave = models.PositiveIntegerField(default=0)
    days_family_leave = models.PositiveIntegerField(default=0)
    days_unpaid_leave = models.PositiveIntegerField(default=0)
    days_public_holiday = models.PositiveIntegerField(default=0)
    days_absent = models.PositiveIntegerField(default=0)
    days_suspended = models.PositiveIntegerField(default=0)
    
    # Rate
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Calculation
    gross_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )
    deductions = models.JSONField(
        default=dict,
        help_text='Breakdown of deductions {reason: amount}'
    )
    total_deductions = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0
    )
    net_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )
    
    # Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    calculated_at = models.DateTimeField(null=True, blank=True)
    calculated_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='calculated_stipends'
    )
    
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_stipends'
    )
    verification_notes = models.TextField(blank=True)
    
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_stipend_calculations'
    )
    
    # Payment tracking (for reporting, actual payment in finance module later)
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    
    # Attendance verification progress
    total_attendance_records = models.PositiveIntegerField(
        default=0,
        help_text='Total attendance records for this period'
    )
    dual_verified_records = models.PositiveIntegerField(
        default=0,
        help_text='Records verified by both mentor and facilitator'
    )
    mentor_verified_only = models.PositiveIntegerField(
        default=0,
        help_text='Records verified only by mentor'
    )
    facilitator_verified_only = models.PositiveIntegerField(
        default=0,
        help_text='Records verified only by facilitator'
    )
    unverified_records = models.PositiveIntegerField(
        default=0,
        help_text='Records with no verification'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-year', '-month']
        unique_together = ['placement', 'month', 'year']
        verbose_name = 'Stipend Calculation'
        verbose_name_plural = 'Stipend Calculations'
    
    def __str__(self):
        return f"{self.placement.learner} - {self.month}/{self.year} - R{self.net_amount or 0}"
    
    @property
    def period_display(self):
        from calendar import month_name
        return f"{month_name[self.month]} {self.year}"
    
    @property
    def paid_days(self):
        """Calculate total paid days based on leave policy"""
        return (
            self.days_present +
            self.days_annual_leave +
            self.days_sick_leave +
            self.days_family_leave +
            self.days_public_holiday
        )
    
    @property
    def verification_percentage(self):
        """Calculate percentage of dual-verified records"""
        if self.total_attendance_records == 0:
            return 0
        return round((self.dual_verified_records / self.total_attendance_records) * 100, 1)
    
    @property
    def can_finalize(self):
        """Check if stipend can be finalized (requires 100% dual verification)"""
        return self.verification_percentage == 100.0
    
    def update_verification_stats(self):
        """Update verification statistics from attendance records"""
        from calendar import monthrange
        from datetime import date
        
        # Get start and end dates for the month
        _, last_day = monthrange(self.year, self.month)
        start_date = date(self.year, self.month, 1)
        end_date = date(self.year, self.month, last_day)
        
        # Get all attendance records for this period
        attendance_records = WorkplaceAttendance.objects.filter(
            placement=self.placement,
            date__gte=start_date,
            date__lte=end_date
        )
        
        self.total_attendance_records = attendance_records.count()
        self.dual_verified_records = attendance_records.filter(
            mentor_verified=True,
            facilitator_verified=True
        ).count()
        self.mentor_verified_only = attendance_records.filter(
            mentor_verified=True,
            facilitator_verified=False
        ).count()
        self.facilitator_verified_only = attendance_records.filter(
            mentor_verified=False,
            facilitator_verified=True
        ).count()
        self.unverified_records = attendance_records.filter(
            mentor_verified=False,
            facilitator_verified=False
        ).count()
        
        self.save(update_fields=[
            'total_attendance_records',
            'dual_verified_records',
            'mentor_verified_only',
            'facilitator_verified_only',
            'unverified_records'
        ])


class DisciplinaryRecord(AuditedModel):
    """
    Disciplinary record for a learner.
    Tracks the progression through disciplinary steps.
    """
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('APPEALED', 'Under Appeal'),
        ('DISMISSED', 'Case Dismissed'),
    ]
    
    CURRENT_STEP_CHOICES = [
        ('VERBAL_WARNING', 'Verbal Warning'),
        ('WRITTEN_WARNING', 'Written Warning'),
        ('FINAL_WARNING', 'Final Written Warning'),
        ('DISMISSAL', 'Dismissal'),
    ]
    
    learner = models.ForeignKey(
        Learner,
        on_delete=models.CASCADE,
        related_name='disciplinary_records'
    )
    placement = models.ForeignKey(
        'corporate.WorkplacePlacement',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='disciplinary_records'
    )
    
    # Record details
    case_number = models.CharField(max_length=50, unique=True)
    
    # Current step in disciplinary process
    current_step = models.CharField(
        max_length=20,
        choices=CURRENT_STEP_CHOICES,
        default='VERBAL_WARNING'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    
    # Dates
    opened_date = models.DateField()
    resolved_date = models.DateField(null=True, blank=True)
    
    # Resolution
    resolution_summary = models.TextField(blank=True)
    
    # Assigned officer
    assigned_officer = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_disciplinary_records'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-opened_date']
        verbose_name = 'Disciplinary Record'
        verbose_name_plural = 'Disciplinary Records'
    
    def save(self, *args, **kwargs):
        if not self.case_number:
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d%H%M')
            self.case_number = f"DISC-{timestamp}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.case_number} - {self.learner}"
    
    @property
    def is_active(self):
        return self.status in ('OPEN', 'IN_PROGRESS', 'APPEALED')


class DisciplinaryAction(AuditedModel):
    """
    Individual disciplinary action/step within a disciplinary record.
    Follows simple linear process: Verbal → Written → Final → Dismissal
    """
    STEP_CHOICES = [
        ('VERBAL_WARNING', 'Verbal Warning'),
        ('WRITTEN_WARNING', 'Written Warning'),
        ('FINAL_WARNING', 'Final Written Warning'),
        ('DISMISSAL', 'Dismissal'),
    ]
    
    record = models.ForeignKey(
        DisciplinaryRecord,
        on_delete=models.CASCADE,
        related_name='actions'
    )
    
    # Action details
    step = models.CharField(max_length=20, choices=STEP_CHOICES)
    action_date = models.DateField()
    
    # Issued by
    issued_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='issued_disciplinary_actions'
    )
    
    # Offence details
    offence_type = models.CharField(max_length=100)
    offence_date = models.DateField()
    offence_description = models.TextField()
    
    # Learner response
    learner_response = models.TextField(blank=True)
    learner_acknowledged = models.BooleanField(default=False)
    learner_acknowledged_at = models.DateTimeField(null=True, blank=True)
    refused_to_sign = models.BooleanField(default=False)
    
    # Witness (if learner refused to sign)
    witness_name = models.CharField(max_length=100, blank=True)
    witness_signed = models.BooleanField(default=False)
    
    # Review/Expiry
    valid_until = models.DateField(
        null=True, blank=True,
        help_text='Warning expires after this date'
    )
    next_review_date = models.DateField(null=True, blank=True)
    
    # Supporting documents
    documents = models.ManyToManyField(
        'core.ManagedDocument',
        blank=True,
        related_name='disciplinary_actions'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['action_date']
        verbose_name = 'Disciplinary Action'
        verbose_name_plural = 'Disciplinary Actions'
    
    def __str__(self):
        return f"{self.record.case_number} - {self.get_step_display()} - {self.action_date}"
    
    @property
    def is_expired(self):
        from django.utils import timezone
        if not self.valid_until:
            return False
        return self.valid_until < timezone.now().date()


class LearnerSupportNote(AuditedModel):
    """
    Support notes and life advice given to learners by workplace officers.
    Tracks ongoing support and guidance.
    """
    CATEGORY_CHOICES = [
        ('CAREER', 'Career Guidance'),
        ('PERSONAL', 'Personal Support'),
        ('FINANCIAL', 'Financial Advice'),
        ('HEALTH', 'Health & Wellness'),
        ('WORKPLACE', 'Workplace Issues'),
        ('ACADEMIC', 'Academic Support'),
        ('OTHER', 'Other'),
    ]
    
    learner = models.ForeignKey(
        Learner,
        on_delete=models.CASCADE,
        related_name='support_notes'
    )
    placement = models.ForeignKey(
        'corporate.WorkplacePlacement',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='support_notes'
    )
    
    # Note details
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    date = models.DateField()
    
    # Content
    summary = models.CharField(max_length=200)
    details = models.TextField()
    advice_given = models.TextField(blank=True)
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_completed = models.BooleanField(default=False)
    
    # Recorded by (workplace officer)
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='recorded_support_notes'
    )
    
    # Confidentiality
    is_confidential = models.BooleanField(
        default=False,
        help_text='Restrict visibility to workplace officers only'
    )
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Learner Support Note'
        verbose_name_plural = 'Learner Support Notes'
    
    def __str__(self):
        return f"{self.learner} - {self.get_category_display()} - {self.date}"


class Guardian(AuditedModel):
    """
    Parent/Guardian/Sponsor model for learners.
    Used for minors requiring parent consent, or for tracking who is financially
    responsible for tuition payments.
    """
    
    RELATIONSHIP_CHOICES = [
        ('PARENT', 'Parent'),
        ('GUARDIAN', 'Legal Guardian'),
        ('SPONSOR', 'Sponsor'),
        ('EMPLOYER', 'Employer Representative'),
        ('SELF', 'Self (Adult Learner)'),
        ('SPOUSE', 'Spouse'),
        ('SIBLING', 'Sibling'),
        ('OTHER', 'Other'),
    ]
    
    TITLE_CHOICES = [
        ('MR', 'Mr'),
        ('MRS', 'Mrs'),
        ('MS', 'Ms'),
        ('MISS', 'Miss'),
        ('DR', 'Dr'),
        ('PROF', 'Prof'),
    ]
    
    # Linked learner
    learner = models.ForeignKey(
        Learner,
        on_delete=models.CASCADE,
        related_name='guardians'
    )
    
    # Relationship
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    
    # Identity
    title = models.CharField(max_length=10, choices=TITLE_CHOICES, blank=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    id_number = models.CharField(max_length=13, blank=True, help_text="SA ID Number")
    
    # Contact
    email = models.EmailField()
    phone_mobile = models.CharField(max_length=20)
    phone_work = models.CharField(max_length=20, blank=True)
    phone_home = models.CharField(max_length=20, blank=True)
    
    # Address
    address = models.ForeignKey(
        Address,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='guardians'
    )
    
    # Financial responsibility
    is_financially_responsible = models.BooleanField(
        default=False,
        help_text="Is this person responsible for paying fees?"
    )
    
    # Emergency contact
    is_emergency_contact = models.BooleanField(
        default=False,
        help_text="Should be contacted in emergencies?"
    )
    
    # Primary guardian flag
    is_primary = models.BooleanField(
        default=False,
        help_text="Primary guardian/parent for communications"
    )
    
    # Consent tracking
    consent_signed = models.BooleanField(default=False)
    consent_date = models.DateTimeField(null=True, blank=True)
    consent_document = models.FileField(
        upload_to='guardian_consents/',
        null=True, blank=True,
        help_text="Signed consent form"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-is_primary', 'last_name', 'first_name']
        verbose_name = 'Guardian'
        verbose_name_plural = 'Guardians'
    
    def __str__(self):
        return f"{self.get_title_display()} {self.first_name} {self.last_name} ({self.get_relationship_display()})"
    
    @property
    def full_name(self):
        """Return full name with title"""
        parts = []
        if self.title:
            parts.append(self.get_title_display())
        parts.extend([self.first_name, self.last_name])
        return ' '.join(parts)
    
    def save(self, *args, **kwargs):
        # If setting as primary, unset other primaries for same learner
        if self.is_primary:
            Guardian.objects.filter(
                learner=self.learner, 
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class GuardianPortalAccess(AuditedModel):
    """
    Portal access credentials for guardians/parents.
    Allows parents to login and view learner progress, schedules, and results.
    """
    guardian = models.OneToOneField(
        Guardian,
        on_delete=models.CASCADE,
        related_name='portal_access'
    )
    
    # Login via email + access code (no password needed)
    access_code = models.CharField(max_length=20, unique=True)
    access_code_expires = models.DateTimeField(null=True, blank=True)
    
    # Portal status
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    
    # Terms acceptance
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Guardian Portal Access'
        verbose_name_plural = 'Guardian Portal Accesses'
    
    def __str__(self):
        return f"Portal Access - {self.guardian}"
    
    def generate_access_code(self):
        """Generate a new access code for the guardian"""
        import secrets
        from datetime import timedelta
        from django.utils import timezone
        
        self.access_code = secrets.token_urlsafe(12)
        self.access_code_expires = timezone.now() + timedelta(days=365)
        self.save()
        return self.access_code
    
    def record_login(self):
        """Record a login event"""
        from django.utils import timezone
        self.last_login = timezone.now()
        self.login_count += 1
        self.save(update_fields=['last_login', 'login_count'])


class GuardianNotificationPreference(AuditedModel):
    """
    Notification preferences for guardians/parents.
    Controls what automated emails they receive.
    """
    guardian = models.OneToOneField(
        Guardian,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Assessment notifications
    notify_assessment_completed = models.BooleanField(
        default=True,
        help_text="Email when learner completes an assessment"
    )
    notify_assessment_scheduled = models.BooleanField(
        default=True,
        help_text="Email when new assessments are scheduled"
    )
    notify_schedule_changed = models.BooleanField(
        default=True,
        help_text="Email when assessment schedule changes"
    )
    
    # Progress notifications
    notify_weekly_progress = models.BooleanField(
        default=False,
        help_text="Weekly progress summary email"
    )
    notify_monthly_report = models.BooleanField(
        default=True,
        help_text="Monthly progress report email"
    )
    
    # Attendance notifications
    notify_absence = models.BooleanField(
        default=True,
        help_text="Email when learner is marked absent"
    )
    
    # Result notifications
    notify_not_yet_competent = models.BooleanField(
        default=True,
        help_text="Email when learner receives NYC result"
    )
    notify_competent = models.BooleanField(
        default=True,
        help_text="Email when learner achieves competence"
    )
    notify_module_completed = models.BooleanField(
        default=True,
        help_text="Email when learner completes a module"
    )
    
    # Communication preferences
    preferred_language = models.CharField(max_length=5, default='en')
    email_frequency = models.CharField(
        max_length=20,
        choices=[
            ('IMMEDIATE', 'Immediate'),
            ('DAILY_DIGEST', 'Daily Digest'),
            ('WEEKLY_DIGEST', 'Weekly Digest'),
        ],
        default='IMMEDIATE'
    )
    
    # Unsubscribe
    unsubscribed = models.BooleanField(default=False)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Guardian Notification Preference'
        verbose_name_plural = 'Guardian Notification Preferences'
    
    def __str__(self):
        return f"Notification Preferences - {self.guardian}"


# ==================== Financial Literacy Models ====================

class FinancialLiteracyModule(AuditedModel):
    """
    Educational modules for financial literacy training
    """
    CONTENT_TYPE_CHOICES = [
        ('ARTICLE', 'Article'),
        ('VIDEO', 'Video'),
        ('CALCULATOR', 'Interactive Calculator'),
        ('QUIZ', 'Quiz'),
    ]
    
    VIDEO_PROVIDER_CHOICES = [
        ('INTERNAL', 'Internal Hosting'),
        ('YOUTUBE', 'YouTube'),
        ('VIMEO', 'Vimeo'),
        ('EXTERNAL', 'External Link'),
    ]
    
    CONTENT_SOURCE_CHOICES = [
        ('INTERNAL', 'Internal Content'),
        ('SAVVI', 'SAVVI'),
        ('MYMONEY123', 'MyMoney123'),
        ('OLDMUTUAL', 'Old Mutual iMasii'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    content_body = models.TextField(help_text='Main content (HTML supported)')
    video_url = models.URLField(blank=True, null=True)
    video_provider = models.CharField(max_length=20, choices=VIDEO_PROVIDER_CHOICES, default='INTERNAL')
    sequence_order = models.PositiveIntegerField(default=0)
    passing_score = models.IntegerField(default=70, help_text='Minimum score to pass (for quizzes)')
    duration_minutes = models.PositiveIntegerField(default=15, help_text='Expected completion time')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_modules')
    
    # Content licensing integration
    content_source = models.CharField(max_length=20, choices=CONTENT_SOURCE_CHOICES, default='INTERNAL')
    external_module_id = models.CharField(max_length=100, blank=True, null=True, 
                                          help_text='External provider module ID for API mapping')
    
    class Meta:
        ordering = ['sequence_order', 'title']
        verbose_name = 'Financial Literacy Module'
        verbose_name_plural = 'Financial Literacy Modules'
    
    def __str__(self):
        return f"{self.sequence_order}. {self.title}"
    
    def get_completion_count(self):
        return self.progress_records.filter(status='COMPLETED').count()
    
    def get_average_score(self):
        from django.db.models import Avg
        return self.progress_records.filter(
            status='COMPLETED', 
            score__isnull=False
        ).aggregate(avg=Avg('score'))['avg'] or 0


class FinancialLiteracyProgress(AuditedModel):
    """
    Tracks learner progress through financial literacy modules
    """
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
    ]
    
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name='financial_literacy_progress')
    module = models.ForeignKey(FinancialLiteracyModule, on_delete=models.CASCADE, related_name='progress_records')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOT_STARTED')
    score = models.IntegerField(null=True, blank=True, help_text='Quiz score (if applicable)')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Certificate tracking
    certificate_code = models.UUIDField(unique=True, default=uuid.uuid4)
    certificate_issued_at = models.DateTimeField(null=True, blank=True)
    certificate_hash = models.CharField(max_length=64, blank=True, null=True, 
                                       help_text='SHA-256 hash for blockchain anchoring')
    blockchain_tx_id = models.CharField(max_length=200, blank=True, null=True,
                                       help_text='Blockchain transaction ID')
    
    # Engagement tracking
    time_spent_minutes = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ['learner', 'module']
        verbose_name = 'Financial Literacy Progress'
        verbose_name_plural = 'Financial Literacy Progress Records'
    
    def __str__(self):
        return f"{self.learner.get_full_name()} - {self.module.title} ({self.status})"
    
    def is_passed(self):
        if self.module.content_type == 'QUIZ' and self.score is not None:
            return self.score >= self.module.passing_score
        return self.status == 'COMPLETED'
    
    def get_attempts_count(self):
        return self.quiz_attempts.count()


class QuizQuestion(AuditedModel):
    """
    Questions for financial literacy quizzes
    """
    QUESTION_TYPE_CHOICES = [
        ('MULTIPLE_CHOICE', 'Multiple Choice'),
        ('TRUE_FALSE', 'True/False'),
        ('NUMERIC', 'Numeric Answer'),
    ]
    
    module = models.ForeignKey(FinancialLiteracyModule, on_delete=models.CASCADE, related_name='quiz_questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    correct_answer = models.CharField(max_length=200)
    options = models.JSONField(default=list, help_text='List of answer options for multiple choice')
    explanation = models.TextField(help_text='Explanation shown after answering')
    points = models.IntegerField(default=10)
    sequence_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['module', 'sequence_order']
        verbose_name = 'Quiz Question'
        verbose_name_plural = 'Quiz Questions'
    
    def __str__(self):
        return f"{self.module.title} - Q{self.sequence_order}"


class QuizAttempt(AuditedModel):
    """
    Records of quiz attempts by learners
    """
    progress = models.ForeignKey(FinancialLiteracyProgress, on_delete=models.CASCADE, related_name='quiz_attempts')
    answers = models.JSONField(default=dict, help_text='Question ID to submitted answer mapping')
    score = models.IntegerField()
    attempt_number = models.PositiveIntegerField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Quiz Attempt'
        verbose_name_plural = 'Quiz Attempts'
    
    def __str__(self):
        return f"{self.progress.learner.get_full_name()} - Attempt {self.attempt_number} - {self.score}%"
    
    @property
    def passed(self):
        return self.score >= self.progress.module.passing_score


class BudgetCategory(AuditedModel):
    """
    Categories for budgeting and expense tracking
    """
    TYPE_CHOICES = [
        ('INCOME', 'Income'),
        ('EXPENSE', 'Expense'),
    ]
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    icon = models.CharField(max_length=10, help_text='Emoji icon', default='💰')
    color = models.CharField(max_length=7, help_text='Hex color code', default='#6366f1')
    is_system_category = models.BooleanField(default=False, help_text='Pre-defined system category')
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Budget Category'
        verbose_name_plural = 'Budget Categories'
    
    def __str__(self):
        return f"{self.icon} {self.name}"


class LearnerBudget(AuditedModel):
    """
    Monthly budget for learners
    """
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name='budgets')
    month = models.IntegerField(choices=[(i, i) for i in range(1, 13)])
    year = models.IntegerField()
    total_income = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       help_text='Auto-calculated from stipend')
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ['learner', 'month', 'year']
        ordering = ['-year', '-month']
        verbose_name = 'Learner Budget'
        verbose_name_plural = 'Learner Budgets'
    
    def __str__(self):
        from datetime import date
        month_name = date(self.year, self.month, 1).strftime('%B')
        return f"{self.learner.get_full_name()} - {month_name} {self.year}"
    
    @property
    def total_planned_expenses(self):
        from django.db.models import Sum
        return self.budget_items.aggregate(total=Sum('planned_amount'))['total'] or 0
    
    @property
    def total_actual_expenses(self):
        from django.db.models import Sum
        return self.expense_entries.aggregate(total=Sum('amount'))['total'] or 0
    
    @property
    def variance(self):
        return self.total_planned_expenses - self.total_actual_expenses
    
    @property
    def balance(self):
        return self.total_income - self.total_actual_expenses


class BudgetItem(AuditedModel):
    """
    Planned budget items
    """
    budget = models.ForeignKey(LearnerBudget, on_delete=models.CASCADE, related_name='budget_items')
    category = models.ForeignKey(BudgetCategory, on_delete=models.PROTECT)
    planned_amount = models.DecimalField(max_digits=10, decimal_places=2)
    actual_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Budget Item'
        verbose_name_plural = 'Budget Items'
    
    def __str__(self):
        return f"{self.budget} - {self.category.name}: R{self.planned_amount}"


class SavingsGoal(AuditedModel):
    """
    Savings goals for learners
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ACHIEVED', 'Achieved'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    ]
    
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name='savings_goals')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    target_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    achieved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Savings Goal'
        verbose_name_plural = 'Savings Goals'
    
    def __str__(self):
        return f"{self.learner.get_full_name()} - {self.name}"
    
    @property
    def completion_percentage(self):
        if self.target_amount > 0:
            return min(100, (self.current_amount / self.target_amount) * 100)
        return 0
    
    @property
    def is_achieved(self):
        return self.current_amount >= self.target_amount
    
    def check_and_update_status(self):
        from django.utils import timezone
        if self.is_achieved and self.status == 'ACTIVE':
            self.status = 'ACHIEVED'
            self.achieved_at = timezone.now()
            self.save()
        elif self.target_date < timezone.now().date() and self.status == 'ACTIVE':
            self.status = 'EXPIRED'
            self.save()


class ExpenseEntry(AuditedModel):
    """
    Individual expense entries for learners
    """
    SYNC_STATUS_CHOICES = [
        ('PENDING', 'Pending Sync'),
        ('SYNCED', 'Synced'),
        ('FAILED', 'Sync Failed'),
    ]
    
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name='expense_entries')
    category = models.ForeignKey(BudgetCategory, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_date = models.DateField()
    description = models.TextField()
    receipt = models.ForeignKey('core.ManagedDocument', on_delete=models.SET_NULL, 
                                null=True, blank=True, related_name='expense_receipts')
    
    # Offline sync support
    sync_status = models.CharField(max_length=20, choices=SYNC_STATUS_CHOICES, default='SYNCED')
    sync_error_message = models.TextField(blank=True, null=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    client_uuid = models.UUIDField(unique=True, default=uuid.uuid4,
                                   help_text='Client-side UUID for offline deduplication')
    
    class Meta:
        ordering = ['-transaction_date', '-created_at']
        verbose_name = 'Expense Entry'
        verbose_name_plural = 'Expense Entries'
    
    def __str__(self):
        return f"{self.learner.get_full_name()} - {self.category.name}: R{self.amount}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Auto-update budget if exists
        budget, created = LearnerBudget.objects.get_or_create(
            learner=self.learner,
            month=self.transaction_date.month,
            year=self.transaction_date.year
        )
        
        # Update savings goal if category is savings
        if self.category.slug == 'savings':
            active_goals = self.learner.savings_goals.filter(status='ACTIVE')
            if active_goals.exists():
                goal = active_goals.first()
                goal.current_amount += self.amount
                goal.check_and_update_status()


class StipendDispute(AuditedModel):
    """
    Formal dispute tracking for stipend calculations
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('UNDER_REVIEW', 'Under Review'),
        ('RESOLVED', 'Resolved'),
        ('ESCALATED', 'Escalated to Management'),
        ('CLOSED', 'Closed'),
    ]
    
    stipend_calculation = models.ForeignKey('StipendCalculation', on_delete=models.CASCADE, 
                                            related_name='disputes')
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name='stipend_disputes')
    reason = models.TextField(help_text='Learner reason for dispute')
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    # Review tracking
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='reviewed_disputes')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    response = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Escalation tracking
    escalated_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='escalated_disputes',
                                     help_text='Senior management for escalation')
    escalated_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(blank=True, null=True, help_text='Final resolution notes')
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Stipend Dispute'
        verbose_name_plural = 'Stipend Disputes'
    
    def __str__(self):
        return f"Dispute #{self.id} - {self.learner.get_full_name()} - {self.status}"
    
    @property
    def sla_deadline(self):
        from datetime import timedelta
        return self.submitted_at + timedelta(days=3)
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.status == 'PENDING' and timezone.now() > self.sla_deadline


# ============================================================================
# Workplace Exposure Tracking Models
# ============================================================================

class WorkplaceExposureLog(AuditedModel):
    """
    Tracks learner exposure to workplace modules during placement stints.
    Each learner logs activities per workplace module, with mentor verification.
    Hours are calculated from module notional hours (credits × 10).
    """
    VERIFICATION_STATUS = [
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified by Mentor'),
        ('REJECTED', 'Rejected'),
        ('DISPUTED', 'Disputed'),
    ]
    
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        on_delete=models.CASCADE,
        related_name='workplace_exposure_logs'
    )
    
    workplace_module = models.ForeignKey(
        'academics.Module',
        on_delete=models.PROTECT,
        related_name='exposure_logs',
        limit_choices_to={'module_type': 'W'},  # Only workplace modules
        help_text="Workplace module (WM) for this exposure"
    )
    
    host_employer = models.ForeignKey(
        'corporate.HostEmployer',
        on_delete=models.PROTECT,
        related_name='exposure_logs',
        help_text="Host employer where exposure occurred"
    )
    
    # Exposure details
    date = models.DateField()
    hours_logged = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Hours of exposure logged for this activity"
    )
    activity_description = models.TextField(
        help_text="Description of the activity performed"
    )
    
    # Skills/competencies demonstrated
    skills_demonstrated = models.JSONField(
        default=list,
        help_text="List of skills demonstrated during this activity"
    )
    
    # Evidence (optional)
    evidence_file = models.FileField(
        upload_to='workplace_exposure/evidence/%Y/%m/',
        blank=True,
        null=True,
        help_text="Photo or document evidence of the activity"
    )
    evidence_notes = models.TextField(blank=True)
    
    # Mentor verification
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='PENDING'
    )
    mentor = models.ForeignKey(
        'corporate.HostMentor',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_exposures'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Quality rating by mentor
    quality_rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Mentor rating 1-5 for quality of work"
    )
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Workplace Exposure Log'
        verbose_name_plural = 'Workplace Exposure Logs'
    
    def __str__(self):
        return f"{self.enrollment.learner.get_full_name()} - {self.workplace_module.code} - {self.date}"
    
    def verify(self, mentor, notes="", rating=None):
        """Verify this exposure log"""
        from django.utils import timezone
        self.verification_status = 'VERIFIED'
        self.mentor = mentor
        self.verified_at = timezone.now()
        self.verification_notes = notes
        if rating:
            self.quality_rating = rating
        self.save()
    
    def reject(self, mentor, reason):
        """Reject this exposure log"""
        from django.utils import timezone
        self.verification_status = 'REJECTED'
        self.mentor = mentor
        self.verified_at = timezone.now()
        self.verification_notes = reason
        self.save()
    
    @classmethod
    def get_required_hours_for_module(cls, module):
        """
        Calculate required hours for a workplace module.
        Formula: credits × 10 notional hours
        """
        return module.credits * 10
    
    @classmethod
    def get_exposure_summary_for_enrollment(cls, enrollment):
        """
        Get exposure summary for all workplace modules for an enrollment.
        Returns dict of module_id: {required, logged, verified, remaining, percentage}
        """
        from django.db.models import Sum, Q
        
        # Get all workplace modules for the qualification
        workplace_modules = enrollment.cohort.qualification.modules.filter(module_type='W')
        
        summary = {}
        for module in workplace_modules:
            required_hours = cls.get_required_hours_for_module(module)
            
            # Get logged hours (verified only)
            verified_hours = cls.objects.filter(
                enrollment=enrollment,
                workplace_module=module,
                verification_status='VERIFIED'
            ).aggregate(total=Sum('hours_logged'))['total'] or 0
            
            # Get pending hours
            pending_hours = cls.objects.filter(
                enrollment=enrollment,
                workplace_module=module,
                verification_status='PENDING'
            ).aggregate(total=Sum('hours_logged'))['total'] or 0
            
            remaining = max(0, required_hours - verified_hours)
            percentage = min(100, (verified_hours / required_hours * 100)) if required_hours > 0 else 0
            
            summary[module.id] = {
                'module': module,
                'required_hours': required_hours,
                'verified_hours': float(verified_hours),
                'pending_hours': float(pending_hours),
                'remaining_hours': float(remaining),
                'completion_percentage': round(percentage, 1),
                'is_complete': remaining == 0,
            }
        
        return summary
    
    @classmethod
    def get_gap_analysis_for_enrollment(cls, enrollment):
        """
        Identify modules where learner needs more exposure.
        Returns list of modules with gaps sorted by urgency.
        """
        summary = cls.get_exposure_summary_for_enrollment(enrollment)
        
        gaps = []
        for module_id, data in summary.items():
            if not data['is_complete']:
                gaps.append({
                    'module': data['module'],
                    'required': data['required_hours'],
                    'completed': data['verified_hours'],
                    'remaining': data['remaining_hours'],
                    'completion_percentage': data['completion_percentage'],
                    'urgency': 'HIGH' if data['completion_percentage'] < 30 else 'MEDIUM' if data['completion_percentage'] < 70 else 'LOW'
                })
        
        # Sort by urgency (HIGH first) then by remaining hours
        urgency_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        gaps.sort(key=lambda x: (urgency_order[x['urgency']], -x['remaining']))
        
        return gaps


class WorkplaceRotationRecommendation(AuditedModel):
    """
    System-generated or manual recommendation for learner rotation
    to a different workplace to get specific exposure.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('ACTIONED', 'Actioned'),
        ('DECLINED', 'Declined'),
    ]
    
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        on_delete=models.CASCADE,
        related_name='rotation_recommendations'
    )
    
    # Current placement
    current_host = models.ForeignKey(
        'corporate.HostEmployer',
        on_delete=models.PROTECT,
        related_name='rotation_out_recommendations'
    )
    
    # Recommended new placement
    recommended_host = models.ForeignKey(
        'corporate.HostEmployer',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='rotation_in_recommendations'
    )
    
    # Reason for rotation
    modules_needing_exposure = models.ManyToManyField(
        'academics.Module',
        related_name='rotation_recommendations',
        help_text="Modules where learner needs more exposure"
    )
    
    reason = models.TextField(help_text="Detailed reason for rotation recommendation")
    
    # Generated by system or manual
    is_system_generated = models.BooleanField(default=False)
    
    # Review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_rotations'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Action taken
    new_placement = models.ForeignKey(
        'corporate.WorkplacePlacement',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='rotation_source'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Workplace Rotation Recommendation'
        verbose_name_plural = 'Workplace Rotation Recommendations'
    
    def __str__(self):
        return f"Rotation: {self.enrollment.learner.get_full_name()} from {self.current_host}"


# =============================================================================
# Daily Logbook - Attendance & Task Tracking
# =============================================================================

class DailyLogbookEntry(AuditedModel):
    """
    Daily attendance and logbook entry for a learner.
    Captures daily activities with multiple WM tasks per day.
    Used for monthly aggregation and Excel export.
    """
    
    ATTENDANCE_STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('SICK_LEAVE', 'Sick Leave'),
        ('ANNUAL_LEAVE', 'Annual Leave'),
        ('STUDY_LEAVE', 'Study Leave'),
        ('PUBLIC_HOLIDAY', 'Public Holiday'),
        ('LATE', 'Late Arrival'),
        ('EARLY_OUT', 'Early Departure'),
    ]
    
    # Link to placement
    placement = models.ForeignKey(
        'corporate.WorkplacePlacement',
        on_delete=models.CASCADE,
        related_name='daily_logbook_entries'
    )
    
    # Link to WorkplaceAttendance record (one-to-one per day)
    attendance_record = models.OneToOneField(
        'learners.WorkplaceAttendance',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='daily_logbook_entry',
        help_text="Linked attendance record for this day"
    )
    
    # Date
    entry_date = models.DateField(
        help_text="Date of this logbook entry"
    )
    
    # Attendance
    attendance_status = models.CharField(
        max_length=20,
        choices=ATTENDANCE_STATUS_CHOICES,
        default='PRESENT'
    )
    
    # Time tracking
    clock_in = models.TimeField(
        null=True, blank=True,
        help_text="Time arrived at workplace"
    )
    clock_out = models.TimeField(
        null=True, blank=True,
        help_text="Time left workplace"
    )
    
    # Break time
    break_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Break time in minutes"
    )
    
    # Daily summary
    daily_summary = models.TextField(
        blank=True,
        help_text="Summary of activities for the day"
    )
    
    # Challenges / learning notes
    challenges_faced = models.TextField(
        blank=True,
        help_text="Any challenges or difficulties faced"
    )
    lessons_learned = models.TextField(
        blank=True,
        help_text="Key lessons learned during the day"
    )
    
    # Mentor feedback (optional daily)
    mentor_feedback = models.TextField(
        blank=True,
        help_text="Daily feedback from mentor if provided"
    )
    
    # Sign-off (usually done at end of day)
    learner_signed = models.BooleanField(
        default=False,
        help_text="Learner confirmed this entry"
    )
    learner_signed_at = models.DateTimeField(null=True, blank=True)
    
    mentor_signed = models.BooleanField(
        default=False,
        help_text="Mentor approved this entry"
    )
    mentor_signed_at = models.DateTimeField(null=True, blank=True)
    mentor_signed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='mentor_signed_daily_entries'
    )
    
    class Meta:
        ordering = ['-entry_date']
        verbose_name = 'Daily Logbook Entry'
        verbose_name_plural = 'Daily Logbook Entries'
        unique_together = ['placement', 'entry_date']
    
    def __str__(self):
        return f"{self.placement.learner} - {self.entry_date}"
    
    @property
    def hours_worked(self):
        """Calculate hours worked for the day"""
        if self.clock_in and self.clock_out and self.attendance_status == 'PRESENT':
            from datetime import datetime, timedelta
            clock_in_dt = datetime.combine(self.entry_date, self.clock_in)
            clock_out_dt = datetime.combine(self.entry_date, self.clock_out)
            
            # Handle overnight (unlikely but possible)
            if clock_out_dt < clock_in_dt:
                clock_out_dt += timedelta(days=1)
            
            total_minutes = (clock_out_dt - clock_in_dt).seconds / 60
            worked_minutes = total_minutes - self.break_minutes
            return round(worked_minutes / 60, 2)
        return 0
    
    @property
    def tasks_count(self):
        """Number of tasks completed for this day"""
        return self.task_completions.count()
    
    @property
    def is_complete(self):
        """Entry is complete when signed by learner and mentor"""
        return self.learner_signed and self.mentor_signed
    
    @classmethod
    def get_monthly_summary(cls, placement, year, month):
        """Get summary statistics for a month"""
        from django.db.models import Count, Sum, Q
        
        entries = cls.objects.filter(
            placement=placement,
            entry_date__year=year,
            entry_date__month=month
        )
        
        summary = entries.aggregate(
            total_entries=Count('id'),
            present_days=Count('id', filter=Q(attendance_status='PRESENT')),
            absent_days=Count('id', filter=Q(attendance_status='ABSENT')),
            sick_days=Count('id', filter=Q(attendance_status='SICK_LEAVE')),
            leave_days=Count('id', filter=Q(attendance_status='ANNUAL_LEAVE')),
        )
        
        # Calculate total hours
        total_hours = sum(e.hours_worked for e in entries)
        summary['total_hours'] = total_hours
        
        # Task count
        task_count = DailyTaskCompletion.objects.filter(
            daily_entry__in=entries
        ).count()
        summary['tasks_completed'] = task_count
        
        return summary


class DailyTaskCompletion(AuditedModel):
    """
    Individual WM task completion for a specific day.
    Multiple tasks can be completed per day.
    Links to WorkplaceModuleOutcome from SAQA curriculum.
    """
    
    daily_entry = models.ForeignKey(
        DailyLogbookEntry,
        on_delete=models.CASCADE,
        related_name='task_completions'
    )
    
    # Link to SAQA curriculum outcome (optional - for new system)
    workplace_outcome = models.ForeignKey(
        'academics.WorkplaceModuleOutcome',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='daily_completions',
        help_text="SAQA curriculum outcome this task relates to"
    )
    
    # Legacy/manual entry support
    module_code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Module code (auto-filled from outcome or manual)"
    )
    task_description = models.TextField(
        help_text="Description of the task/activity performed"
    )
    
    # Hours spent on this task
    hours_spent = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.0,
        help_text="Hours spent on this task"
    )
    
    # Evidence
    evidence_notes = models.TextField(
        blank=True,
        help_text="Notes on evidence or outputs from this task"
    )
    evidence_file = models.FileField(
        upload_to='logbook/task_evidence/%Y/%m/',
        null=True, blank=True,
        help_text="Optional evidence file (photo, document)"
    )
    
    # Competency rating (optional)
    COMPETENCY_CHOICES = [
        ('NYC', 'Not Yet Competent'),
        ('WTC', 'Working Towards Competent'),
        ('C', 'Competent'),
        ('E', 'Exceeds Expectations'),
    ]
    competency_rating = models.CharField(
        max_length=5,
        choices=COMPETENCY_CHOICES,
        blank=True,
        help_text="Optional competency rating from mentor"
    )
    
    class Meta:
        ordering = ['daily_entry', 'created_at']
        verbose_name = 'Daily Task Completion'
        verbose_name_plural = 'Daily Task Completions'
    
    def __str__(self):
        date_str = self.daily_entry.entry_date.strftime('%Y-%m-%d')
        return f"{date_str}: {self.task_description[:50]}"
    
    def save(self, *args, **kwargs):
        # Auto-fill module_code from workplace_outcome
        if self.workplace_outcome and not self.module_code:
            self.module_code = self.workplace_outcome.module.code
        super().save(*args, **kwargs)
    
    @property
    def outcome_code(self):
        """Get the outcome code for display"""
        if self.workplace_outcome:
            return self.workplace_outcome.outcome_code
        return self.module_code or '-'
