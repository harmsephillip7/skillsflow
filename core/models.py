"""
Core models for SkillsFlow ERP
Contains base classes, User model, Role, and Permission models
"""
import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.db.models import Q
from datetime import date


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model with email as primary identifier
    """
    username = None  # Remove username field
    email = models.EmailField('email address', unique=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Profile
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = UserManager()
    
    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_active_roles(self):
        """Get all active roles for this user"""
        return UserRole.objects.filter(
            user=self,
            is_active=True,
            valid_from__lte=date.today()
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=date.today())
        ).select_related('role')
    
    def has_permission(self, permission_code):
        """Check if user has a specific permission"""
        from .permissions import check_user_permission
        return check_user_permission(self, permission_code)


class UserTOTPDevice(models.Model):
    """
    Stores TOTP (Time-based One-Time Password) configuration for two-factor authentication.
    Users can enable Google Authenticator or compatible apps for additional security.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='totp_device'
    )
    secret = models.CharField(
        max_length=32,
        help_text="Base32-encoded TOTP secret"
    )
    is_confirmed = models.BooleanField(
        default=False,
        help_text="Whether the device has been verified by the user"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether 2FA is currently enabled for this user"
    )
    backup_codes = models.TextField(
        blank=True,
        help_text="Comma-separated backup codes for account recovery"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "User TOTP Device"
        verbose_name_plural = "User TOTP Devices"

    def __str__(self):
        return f"TOTP Device for {self.user.email}"


class FacilitatorProfile(models.Model):
    """
    Facilitator-specific profile with campus assignments.
    Facilitators can be assigned to multiple campuses, with one primary campus.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='facilitator_profile',
        help_text="User account for this facilitator"
    )
    campuses = models.ManyToManyField(
        'tenants.Campus',
        related_name='facilitators',
        blank=True,
        help_text="All campuses where this facilitator can work"
    )
    primary_campus = models.ForeignKey(
        'tenants.Campus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_facilitators',
        help_text="Primary/default campus for reporting and filtering"
    )
    
    # Additional facilitator-specific fields can be added here
    employee_number = models.CharField(max_length=50, blank=True)
    specializations = models.TextField(
        blank=True,
        help_text="Areas of expertise or specialization"
    )
    
    # Digital Signature (captured during onboarding, locked after first capture)
    signature = models.ImageField(
        upload_to='signatures/facilitators/%Y/%m/',
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
    
    class Meta:
        verbose_name = 'Facilitator Profile'
        verbose_name_plural = 'Facilitator Profiles'
    
    def __str__(self):
        return f"Facilitator: {self.user.get_full_name()}"
    
    def has_campus_access(self, campus):
        """Check if facilitator has access to a specific campus"""
        return self.campuses.filter(id=campus.id).exists()


class AuditedModel(models.Model):
    """
    Abstract base class for all models requiring audit trail
    Provides created/updated timestamps and soft delete functionality
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='%(class)s_created',
        null=True, blank=True
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='%(class)s_updated',
        null=True, blank=True
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='%(class)s_deleted'
    )
    
    class Meta:
        abstract = True
    
    def soft_delete(self, user=None):
        """Soft delete the record"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()
    
    def restore(self):
        """Restore a soft-deleted record"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()


class Region(models.Model):
    """
    Geographic regions for pricing and management purposes.
    Used for regional pricing variations and manager assignments.
    """
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text='Unique region code (e.g., GAU, WC, KZN)'
    )
    name = models.CharField(
        max_length=100,
        help_text='Full region name (e.g., Gauteng, Western Cape)'
    )
    description = models.TextField(blank=True)
    
    # Pricing modifier (1.0 = no change, 1.10 = 10% increase, 0.90 = 10% decrease)
    price_modifier = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=1.0000,
        help_text='Price modifier (1.0 = base price, 1.10 = +10%, 0.90 = -10%)'
    )
    
    # Parent region for hierarchical structure (optional)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='sub_regions',
        help_text='Parent region for hierarchical grouping'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Ordering
    display_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Region'
        verbose_name_plural = 'Regions'
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def effective_price_modifier(self):
        """
        Get the effective price modifier including parent region modifiers.
        Multiplies through the hierarchy.
        """
        modifier = self.price_modifier
        if self.parent:
            modifier *= self.parent.effective_price_modifier
        return modifier


class Role(models.Model):
    """
    System roles with hierarchical permissions
    20+ roles as per requirements
    """
    ROLE_CHOICES = [
        # Head Office Roles
        ('SUPER_ADMIN', 'Super Administrator'),
        ('SYSTEM_ADMIN', 'System Administrator'),
        ('HEAD_OFFICE_MANAGER', 'Head Office Manager'),
        ('FINANCE_DIRECTOR', 'Finance Director'),
        ('ACADEMIC_DIRECTOR', 'Academic Director'),
        ('CORPORATE_DIRECTOR', 'Corporate Services Director'),
        
        # Brand Level Roles
        ('BRAND_MANAGER', 'Brand Manager'),
        ('BRAND_ACADEMIC_LEAD', 'Brand Academic Lead'),
        ('BRAND_FINANCE_LEAD', 'Brand Finance Lead'),
        
        # Campus Level Roles
        ('CAMPUS_PRINCIPAL', 'Campus Principal'),
        ('CAMPUS_ADMIN', 'Campus Administrator'),
        ('REGISTRAR', 'Registrar'),
        ('ACADEMIC_COORDINATOR', 'Academic Coordinator'),
        
        # Academic Delivery Roles
        ('FACILITATOR', 'Facilitator'),
        ('ASSESSOR', 'Assessor'),
        ('MODERATOR', 'Moderator'),
        ('QCTO_INTERNAL_MODERATOR', 'QCTO Internal Moderator'),
        
        # Skills Development Roles
        ('SDF', 'Skills Development Facilitator'),
        ('SDF_ADMIN', 'SDF Administrator'),
        
        # Sales & CRM Roles
        ('SALES_MANAGER', 'Sales Manager'),
        ('SALES_REP', 'Sales Representative'),
        
        # Finance Roles
        ('FINANCE_MANAGER', 'Finance Manager'),
        ('FINANCE_CLERK', 'Finance Clerk'),
        
        # External Portal Roles
        ('LEARNER', 'Learner'),
        ('CORPORATE_CLIENT_ADMIN', 'Corporate Client Administrator'),
        ('CORPORATE_CLIENT_HR', 'Corporate Client HR Manager'),
        ('CORPORATE_CLIENT_SDF', 'Corporate Client SDF'),
        ('CORPORATE_EMPLOYEE', 'Corporate Employee'),
        
        # Workplace-Based Learning Roles
        ('WORKPLACE_OFFICER', 'Workplace Officer'),
        ('MENTOR', 'Workplace Mentor'),
        ('HOST_EMPLOYER_ADMIN', 'Host Employer Administrator'),
        ('LEAD_EMPLOYER_ADMIN', 'Lead Employer Administrator'),
    ]
    
    ACCESS_LEVELS = [
        ('SYSTEM', 'System-wide'),
        ('HEAD_OFFICE', 'Head Office'),
        ('BRAND', 'Brand Level'),
        ('CAMPUS', 'Campus Level'),
        ('SELF', 'Own Records Only'),
    ]
    
    code = models.CharField(max_length=30, choices=ROLE_CHOICES, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVELS, default='SELF')
    permissions = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class UserRole(AuditedModel):
    """
    Links users to roles with optional scope restrictions (brand/campus)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    
    # Scope (optional - for brand/campus restriction)
    brand = models.ForeignKey(
        'tenants.Brand', 
        null=True, blank=True, 
        on_delete=models.CASCADE
    )
    campus = models.ForeignKey(
        'tenants.Campus', 
        null=True, blank=True, 
        on_delete=models.CASCADE
    )
    corporate_client = models.ForeignKey(
        'corporate.CorporateClient', 
        null=True, blank=True, 
        on_delete=models.CASCADE
    )
    
    # Validity
    valid_from = models.DateField(default=date.today)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'role', 'brand', 'campus', 'corporate_client']
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
    
    def __str__(self):
        scope = ''
        if self.campus:
            scope = f' @ {self.campus.name}'
        elif self.brand:
            scope = f' @ {self.brand.name}'
        return f"{self.user.email} - {self.role.name}{scope}"


class AuditLog(models.Model):
    """
    Detailed audit log for tracking all changes
    """
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('SOFT_DELETE', 'Soft Delete'),
        ('RESTORE', 'Restore'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('EXPORT', 'Export'),
        ('VIEW', 'View'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=500, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.action} - {self.model_name} - {self.timestamp}"


class SystemConfiguration(models.Model):
    """
    System-wide configuration settings
    """
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    description = models.TextField(blank=True)
    is_sensitive = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, 
        null=True, 
        on_delete=models.SET_NULL
    )
    
    class Meta:
        verbose_name = 'System Configuration'
        verbose_name_plural = 'System Configurations'
    
    def __str__(self):
        return self.key
    
    @classmethod
    def get_value(cls, key, default=None):
        """Get a configuration value by key"""
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default


# =============================================================================
# Notification of Training (NOT) Models
# =============================================================================

class TrainingNotification(AuditedModel):
    """
    Notification of Training (NOT) - Main record for new training projects.
    Captures project details, planning meetings, stakeholder assignments,
    resource requirements, and deliverables.
    """
    
    PROJECT_TYPE_CHOICES = [
        ('OC_APPRENTICESHIP', 'OC Apprenticeship'),
        ('OC_LEARNERSHIP', 'OC Learnership'),
        ('SKILLS_PROGRAMME', 'Skills Programme'),
        ('SHORT_COURSE', 'Short Course'),
        ('LEGACY_APPRENTICESHIP', 'Legacy Apprenticeship'),
        ('LEGACY_LEARNERSHIP', 'Legacy Learnership'),
    ]
    
    FUNDER_CHOICES = [
        ('PRIVATE', 'Private'),
        ('SETA', 'SETA'),
        ('CORPORATE_DG', 'Corporate DG'),
        ('CORPORATE', 'Corporate'),
        ('MUNICIPALITY', 'Municipality'),
        ('GOVERNMENT', 'Government'),
    ]
    
    BILLING_SCHEDULE_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('DELIVERABLE', 'Based on Deliverables'),
        ('ANNUALLY', 'Annually'),
        ('UPFRONT', 'Upfront (Full Payment)'),
        ('MANUAL', 'Manual Override'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PLANNING', 'Planning Meeting Scheduled'),
        ('IN_MEETING', 'In Planning Meeting'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('NOTIFICATIONS_SENT', 'Notifications Sent'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    # Basic Information
    reference_number = models.CharField(max_length=50, unique=True, editable=False)
    title = models.CharField(max_length=255)
    project_type = models.CharField(max_length=30, choices=PROJECT_TYPE_CHOICES)
    funder = models.CharField(max_length=30, choices=FUNDER_CHOICES, default='PRIVATE')
    billing_schedule = models.CharField(
        max_length=20,
        choices=BILLING_SCHEDULE_CHOICES,
        default='MONTHLY',
        help_text="How invoices will be generated for this project"
    )
    auto_generate_invoices = models.BooleanField(
        default=True,
        help_text="Automatically generate invoices based on billing schedule"
    )
    description = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Client/Source Information
    client_name = models.CharField(max_length=255, blank=True, help_text="Corporate client, SETA, or funding body")
    corporate_client = models.ForeignKey(
        'corporate.CorporateClient',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='training_notifications'
    )
    tender_reference = models.CharField(max_length=100, blank=True, help_text="Tender/RFQ reference number if applicable")
    contract_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    
    # Link to Contract (optional - for grouping multiple NOTs under one contract)
    contract = models.ForeignKey(
        'intakes.Contract',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='training_notifications',
        help_text="Link to parent contract (optional - for grouping multiple NOTs)"
    )
    
    # Primary Academic Delivery Team (optional - for quick assignment during creation)
    facilitator = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='not_as_facilitator',
        help_text="Primary facilitator for this training project"
    )
    assessor = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='not_as_assessor',
        help_text="Primary assessor for this training project"
    )
    moderator = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='not_as_moderator',
        help_text="Primary moderator for this training project"
    )
    
    # Program Details
    qualification = models.ForeignKey(
        'academics.Qualification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='training_notifications'
    )
    program_description = models.TextField(blank=True, help_text="Description of the training program/modules")
    
    # Learner Information
    expected_learner_count = models.PositiveIntegerField(default=1)
    learner_source = models.CharField(
        max_length=50,
        choices=[
            ('NEW_RECRUITMENT', 'New Recruitment Required'),
            ('CLIENT_PROVIDED', 'Client Will Provide Learners'),
            ('EXISTING_PIPELINE', 'Existing Pipeline/Waitlist'),
            ('MIXED', 'Mixed Sources'),
        ],
        default='NEW_RECRUITMENT'
    )
    recruitment_notes = models.TextField(blank=True)
    
    # Timeline
    planned_start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    duration_months = models.PositiveIntegerField(null=True, blank=True)
    
    # Location
    delivery_campus = models.ForeignKey(
        'tenants.Campus',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='training_notifications'
    )
    delivery_mode = models.CharField(
        max_length=30,
        choices=[
            ('ON_CAMPUS', 'On Campus'),
            ('OFF_SITE', 'Off-Site (Client Premises)'),
            ('ONLINE', 'Online/Virtual'),
            ('BLENDED', 'Blended Learning'),
            ('WORKPLACE', 'Workplace-Based'),
        ],
        default='ON_CAMPUS'
    )
    delivery_address = models.TextField(blank=True, help_text="Address if off-site delivery")
    
    # Planning Meeting
    planning_meeting_date = models.DateTimeField(null=True, blank=True)
    planning_meeting_venue = models.CharField(max_length=255, blank=True)
    planning_meeting_notes = models.TextField(blank=True)
    planning_meeting_completed = models.BooleanField(default=False)
    
    # Approval
    approved_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_training_notifications'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    # Notifications
    notifications_sent_date = models.DateTimeField(null=True, blank=True)
    
    # Related Project
    cohort = models.ForeignKey(
        'logistics.Cohort',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='training_notifications',
        help_text="Link to created cohort once project starts"
    )
    
    # Stipend Configuration
    has_stipend = models.BooleanField(
        default=False,
        help_text="Does this project include learner stipends?"
    )
    stipend_daily_rate = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text="Default daily stipend rate for this project"
    )
    stipend_frequency = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
        ],
        default='MONTHLY',
        blank=True
    )
    stipend_start_month = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Month number when stipends start (1=first month, 2=second month, etc.)"
    )
    stipend_escalation_percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Annual escalation percentage for stipends"
    )
    stipend_notes = models.TextField(
        blank=True,
        help_text="Special conditions, payment terms, or escalation rules"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification of Training'
        verbose_name_plural = 'Notifications of Training'
        permissions = [
            ('can_approve_not', 'Can approve Notification of Training'),
            ('can_send_not_notifications', 'Can send NOT notifications'),
        ]
    
    def __str__(self):
        return f"{self.reference_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Generate reference number: NOT-YYYYMM-XXXX
            from datetime import datetime
            prefix = f"NOT-{datetime.now().strftime('%Y%m')}-"
            last = TrainingNotification.objects.filter(
                reference_number__startswith=prefix
            ).order_by('-reference_number').first()
            if last:
                last_num = int(last.reference_number.split('-')[-1])
                self.reference_number = f"{prefix}{last_num + 1:04d}"
            else:
                self.reference_number = f"{prefix}0001"
        super().save(*args, **kwargs)
    
    @property
    def is_overdue(self):
        if self.planned_start_date and self.status in ['DRAFT', 'PLANNING', 'PENDING_APPROVAL']:
            return date.today() > self.planned_start_date
        return False
    
    @property
    def resource_shortages(self):
        """Return list of resource shortages"""
        shortages = []
        for req in self.resource_requirements.filter(is_available=False):
            shortages.append(req)
        return shortages
    
    @property
    def has_resource_shortages(self):
        return self.resource_requirements.filter(is_available=False).exists()
    
    @property
    def intake_year(self):
        """Return the year of the planned intake"""
        if self.planned_start_date:
            return self.planned_start_date.year
        return None
    
    @property
    def total_original_cohort_size(self):
        """Total original cohort size across all intakes/classes"""
        from django.db.models import Sum
        total = self.intakes.aggregate(total=Sum('original_cohort_size'))['total']
        return total if total else self.expected_learner_count
    
    @property
    def total_active_learners(self):
        """Total currently active learners across all intakes"""
        total = 0
        for intake in self.intakes.all():
            total += intake.active_learner_count
        return total
    
    @property
    def total_dropouts(self):
        """Total dropouts across all intakes"""
        return max(0, self.total_original_cohort_size - self.total_active_learners)
    
    @property
    def dropout_percentage(self):
        """Dropout percentage across all intakes"""
        original = self.total_original_cohort_size
        if original > 0:
            return round((self.total_dropouts / original) * 100, 1)
        return 0
    
    @property
    def fill_rate(self):
        """
        How full is the project compared to expected learners.
        Based on original cohort size vs expected learner count.
        """
        if self.expected_learner_count > 0:
            return round((self.total_original_cohort_size / self.expected_learner_count) * 100, 1)
        return 0
    
    @property
    def capacity_status(self):
        """Return capacity status: EMPTY, PARTIAL, FULL, OVER"""
        fill = self.fill_rate
        if fill == 0:
            return 'EMPTY'
        elif fill < 80:
            return 'PARTIAL'
        elif fill <= 100:
            return 'FULL'
        else:
            return 'OVER'


class NOTIntake(AuditedModel):
    """
    Intake/Class within a Training Notification project.
    A NOT can have multiple intakes (phases/classes) that run together.
    Tracks original cohort size vs active learners for dropout calculation.
    """
    
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('RECRUITING', 'Recruiting'),
        ('FILLED', 'Filled'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='intakes'
    )
    
    # Intake identification
    intake_number = models.PositiveIntegerField(default=1, help_text="Phase/class number within the project")
    name = models.CharField(max_length=100, blank=True, help_text="e.g., 'Phase 1', 'Class A', 'Morning Group'")
    
    # Capacity tracking
    original_cohort_size = models.PositiveIntegerField(
        default=0,
        help_text="Number of learners at project start (for dropout calculation)"
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    
    # Timeline (inherits from NOT but can have specific dates)
    intake_date = models.DateField(null=True, blank=True, help_text="Specific start date for this intake")
    
    # Link to cohort for enrollment tracking
    cohort = models.ForeignKey(
        'logistics.Cohort',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='not_intakes',
        help_text="Link to cohort for enrollment management"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['training_notification', 'intake_number']
        unique_together = ['training_notification', 'intake_number']
        verbose_name = 'NOT Intake'
        verbose_name_plural = 'NOT Intakes'
    
    def __str__(self):
        if self.name:
            return f"{self.training_notification.reference_number} - {self.name}"
        return f"{self.training_notification.reference_number} - Intake {self.intake_number}"
    
    def save(self, *args, **kwargs):
        # Auto-generate name if not provided
        if not self.name:
            if self.intake_number == 1:
                self.name = "Main Intake"
            else:
                self.name = f"Phase {self.intake_number}"
        super().save(*args, **kwargs)
    
    @property
    def start_date(self):
        """Return intake-specific date or fall back to NOT planned start"""
        return self.intake_date or self.training_notification.planned_start_date
    
    @property
    def active_learner_count(self):
        """
        Count of currently active learners in this intake.
        Uses cohort enrollment if linked, otherwise returns original_cohort_size.
        """
        if self.cohort:
            return self.cohort.enrollments.filter(
                status__in=['ENROLLED', 'ACTIVE']
            ).count()
        # If no cohort linked, assume all original learners still active
        return self.original_cohort_size
    
    @property
    def dropout_count(self):
        """Number of learners who have dropped out"""
        return max(0, self.original_cohort_size - self.active_learner_count)
    
    @property
    def dropout_percentage(self):
        """Dropout percentage for this intake"""
        if self.original_cohort_size > 0:
            return round((self.dropout_count / self.original_cohort_size) * 100, 1)
        return 0
    
    @property
    def retention_percentage(self):
        """Retention percentage (inverse of dropout)"""
        return 100 - self.dropout_percentage


class NOTQualificationStipendRate(AuditedModel):
    """
    Qualification-specific stipend rates for different levels/years.
    Allows configuration of different stipend amounts based on qualification
    level or year of study.
    """
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='qualification_stipend_rates'
    )
    
    qualification = models.ForeignKey(
        'academics.Qualification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='not_stipend_rates',
        help_text="Specific qualification (leave blank for default rate)"
    )
    
    # Level-based configuration
    year_level = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Year/level of study (e.g., 1 for first year, 2 for second year)"
    )
    
    # Rate configuration
    daily_rate = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Daily stipend rate for this qualification/level"
    )
    
    effective_from_month = models.PositiveIntegerField(
        default=1,
        help_text="Month number when this rate becomes effective (1=first month)"
    )
    
    effective_to_month = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Month number when this rate ends (leave blank for no end date)"
    )
    
    # Escalation
    auto_escalate = models.BooleanField(
        default=False,
        help_text="Automatically escalate this rate annually"
    )
    
    escalation_percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Annual escalation percentage if auto_escalate is enabled"
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['training_notification', 'qualification', 'year_level', 'effective_from_month']
        unique_together = ['training_notification', 'qualification', 'year_level', 'effective_from_month']
        verbose_name = 'Qualification Stipend Rate'
        verbose_name_plural = 'Qualification Stipend Rates'
    
    def __str__(self):
        parts = [str(self.training_notification.reference_number)]
        if self.qualification:
            parts.append(str(self.qualification.short_title))
        if self.year_level:
            parts.append(f"Year {self.year_level}")
        parts.append(f"R{self.daily_rate}/day")
        return " - ".join(parts)
    
    @property
    def display_name(self):
        """Human-readable display name"""
        if self.qualification:
            name = str(self.qualification.short_title)
            if self.year_level:
                name += f" (Year {self.year_level})"
            return name
        return "Default Rate"


class NOTStakeholder(AuditedModel):
    """
    Stakeholders involved in a Training Notification project.
    Tracks their department, role, responsibilities, and notification status.
    """
    
    DEPARTMENT_CHOICES = [
        ('EXECUTIVE', 'Executive/Management'),
        ('ACADEMIC', 'Academic/Training'),
        ('FINANCE', 'Finance'),
        ('SALES', 'Sales/Business Development'),
        ('RECRUITMENT', 'Recruitment/Admissions'),
        ('LOGISTICS', 'Logistics/Operations'),
        ('HR', 'Human Resources'),
        ('QUALITY', 'Quality Assurance'),
        ('IT', 'IT/Systems'),
        ('MARKETING', 'Marketing'),
        ('COMPLIANCE', 'Compliance/SDF'),
        ('EXTERNAL', 'External Stakeholder'),
    ]
    
    ROLE_IN_PROJECT_CHOICES = [
        ('PROJECT_LEAD', 'Project Lead'),
        ('PROJECT_MANAGER', 'Project Manager'),
        ('FACILITATOR', 'Facilitator'),
        ('ASSESSOR', 'Assessor'),
        ('MODERATOR', 'Moderator'),
        ('RECRUITER', 'Recruiter'),
        ('FINANCE_LEAD', 'Finance Lead'),
        ('COMPLIANCE_LEAD', 'Compliance/SDF Lead'),
        ('LOGISTICS_LEAD', 'Logistics Coordinator'),
        ('QUALITY_LEAD', 'Quality Assurance Lead'),
        ('CLIENT_LIAISON', 'Client Liaison'),
        ('OBSERVER', 'Observer/Informed'),
        ('SUPPORT', 'Support Staff'),
    ]
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='stakeholders'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='not_assignments'
    )
    department = models.CharField(max_length=30, choices=DEPARTMENT_CHOICES)
    role_in_project = models.CharField(max_length=30, choices=ROLE_IN_PROJECT_CHOICES)
    responsibilities = models.TextField(blank=True, help_text="Specific responsibilities for this project")
    
    # Meeting attendance
    invited_to_meeting = models.BooleanField(default=True)
    attended_meeting = models.BooleanField(default=False)
    meeting_notes = models.TextField(blank=True)
    
    # Notification status
    notification_sent = models.BooleanField(default=False)
    notification_sent_date = models.DateTimeField(null=True, blank=True)
    notification_acknowledged = models.BooleanField(default=False)
    notification_acknowledged_date = models.DateTimeField(null=True, blank=True)
    
    # Task tracking
    tasks_assigned = models.TextField(blank=True, help_text="Specific tasks assigned during planning")
    tasks_completed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['department', 'role_in_project']
        unique_together = ['training_notification', 'user', 'role_in_project']
        verbose_name = 'NOT Stakeholder'
        verbose_name_plural = 'NOT Stakeholders'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_role_in_project_display()}"


class NOTResourceRequirement(AuditedModel):
    """
    Resource requirements for a Training Notification project.
    Tracks what resources are needed, availability, and acquisition status.
    """
    
    RESOURCE_TYPE_CHOICES = [
        ('FACILITATOR', 'Facilitator'),
        ('ASSESSOR', 'Assessor'),
        ('MODERATOR', 'Moderator'),
        ('VENUE', 'Venue/Classroom'),
        ('EQUIPMENT', 'Equipment'),
        ('MATERIALS', 'Learning Materials'),
        ('PPE', 'PPE/Safety Equipment'),
        ('SOFTWARE', 'Software/Licenses'),
        ('TRANSPORT', 'Transport'),
        ('ACCOMMODATION', 'Accommodation'),
        ('CATERING', 'Catering'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('REQUIRED', 'Required'),
        ('SOURCING', 'Sourcing/Procurement'),
        ('ORDERED', 'Ordered'),
        ('AVAILABLE', 'Available'),
        ('ALLOCATED', 'Allocated to Project'),
        ('NOT_AVAILABLE', 'Not Available'),
    ]
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='resource_requirements'
    )
    resource_type = models.CharField(max_length=30, choices=RESOURCE_TYPE_CHOICES)
    description = models.CharField(max_length=255)
    quantity_required = models.PositiveIntegerField(default=1)
    quantity_available = models.PositiveIntegerField(default=0)
    
    is_available = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='REQUIRED')
    
    # For human resources
    assigned_user = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='not_resource_assignments'
    )
    
    # Cost tracking
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Procurement
    supplier = models.CharField(max_length=255, blank=True)
    procurement_notes = models.TextField(blank=True)
    expected_availability_date = models.DateField(null=True, blank=True)
    
    # Manager alert
    manager_notified = models.BooleanField(default=False)
    manager_notified_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['resource_type', 'description']
        verbose_name = 'NOT Resource Requirement'
        verbose_name_plural = 'NOT Resource Requirements'
    
    def __str__(self):
        return f"{self.get_resource_type_display()}: {self.description}"
    
    @property
    def shortage_quantity(self):
        return max(0, self.quantity_required - self.quantity_available)
    
    @property
    def is_shortage(self):
        return self.quantity_available < self.quantity_required


class ResourceAllocationPeriod(AuditedModel):
    """
    Tracks resource allocations over time periods.
    Used to detect conflicts when the same resource is allocated to multiple NOTs.
    Supports both human resources (facilitators, assessors, moderators) and venues.
    Records are archived after 3 years (when projects complete).
    """
    
    ALLOCATION_TYPE_CHOICES = [
        ('FACILITATOR', 'Facilitator'),
        ('ASSESSOR', 'Assessor'),
        ('MODERATOR', 'Moderator'),
        ('VENUE', 'Venue'),
    ]
    
    # Link to the source resource requirement
    resource_requirement = models.ForeignKey(
        NOTResourceRequirement,
        on_delete=models.CASCADE,
        related_name='allocation_periods'
    )
    
    # Link to training notification for quick lookups
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='resource_allocations'
    )
    
    allocation_type = models.CharField(max_length=20, choices=ALLOCATION_TYPE_CHOICES)
    
    # For human resources (facilitator, assessor, moderator)
    user = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='resource_allocations'
    )
    
    # For venue resources
    venue = models.ForeignKey(
        'logistics.Venue',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='resource_allocations'
    )
    
    # Cohort link (once cohort is created)
    cohort = models.ForeignKey(
        'logistics.Cohort',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='resource_allocations'
    )
    
    # Allocation period
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Archive management (archive after 3 years)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date', 'allocation_type']
        verbose_name = 'Resource Allocation Period'
        verbose_name_plural = 'Resource Allocation Periods'
        indexes = [
            models.Index(fields=['user', 'start_date', 'end_date']),
            models.Index(fields=['venue', 'start_date', 'end_date']),
            models.Index(fields=['is_archived', 'end_date']),
        ]
    
    def __str__(self):
        resource_name = self.user.get_full_name() if self.user else (self.venue.name if self.venue else 'Unknown')
        return f"{self.get_allocation_type_display()}: {resource_name} ({self.start_date} - {self.end_date})"
    
    @classmethod
    def get_conflicts(cls, allocation_type, start_date, end_date, user=None, venue=None, exclude_not_id=None):
        """
        Find conflicting allocations for a resource within a date range.
        Returns QuerySet of conflicting ResourceAllocationPeriod records.
        """
        conflicts = cls.objects.filter(
            allocation_type=allocation_type,
            is_archived=False,
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        
        if user:
            conflicts = conflicts.filter(user=user)
        if venue:
            conflicts = conflicts.filter(venue=venue)
        if exclude_not_id:
            conflicts = conflicts.exclude(training_notification_id=exclude_not_id)
        
        return conflicts.select_related('training_notification', 'user', 'venue')
    
    @classmethod
    def check_availability(cls, allocation_type, start_date, end_date, user=None, venue=None, exclude_not_id=None):
        """
        Check if a resource is available for a given period.
        Returns tuple: (is_available: bool, conflicts: QuerySet)
        """
        conflicts = cls.get_conflicts(
            allocation_type=allocation_type,
            start_date=start_date,
            end_date=end_date,
            user=user,
            venue=venue,
            exclude_not_id=exclude_not_id
        )
        return (not conflicts.exists(), conflicts)


class NOTDeliverable(AuditedModel):
    """
    Deliverables and milestones for a Training Notification project.
    Tracks reporting requirements, deadlines, and completion status.
    Supports recurring deliverables (monthly, quarterly, etc.)
    """
    
    DELIVERABLE_TYPE_CHOICES = [
        ('REPORT', 'Report'),
        ('MILESTONE', 'Milestone'),
        ('REGISTRATION', 'Registration/Enrollment'),
        ('ASSESSMENT', 'Assessment Event'),
        ('MODERATION', 'Moderation'),
        ('CERTIFICATION', 'Certification'),
        ('AUDIT', 'Audit/Verification'),
        ('PAYMENT', 'Payment Milestone'),
        ('SUBMISSION', 'Document Submission'),
        ('MEETING', 'Progress Meeting'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
        ('OVERDUE', 'Overdue'),
    ]
    
    RECURRENCE_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('BIANNUALLY', 'Every 6 Months'),
        ('ANNUALLY', 'Annually'),
    ]
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='deliverables'
    )
    title = models.CharField(max_length=255)
    deliverable_type = models.CharField(max_length=30, choices=DELIVERABLE_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Responsibility
    responsible_stakeholder = models.ForeignKey(
        NOTStakeholder,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='deliverables'
    )
    # Direct assignment to any user (campus employee)
    assigned_to = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_deliverables',
        help_text="Campus employee responsible for this deliverable"
    )
    responsible_department = models.CharField(max_length=30, choices=NOTStakeholder.DEPARTMENT_CHOICES, blank=True)
    
    # Timeline
    due_date = models.DateField()
    reminder_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    
    # Recurring deliverables
    is_recurring = models.BooleanField(default=False, help_text="Is this a recurring deliverable?")
    recurrence_type = models.CharField(
        max_length=20, 
        choices=RECURRENCE_CHOICES, 
        blank=True,
        help_text="How often the deliverable repeats"
    )
    recurrence_end_date = models.DateField(
        null=True, 
        blank=True, 
        help_text="When to stop creating recurring deliverables"
    )
    parent_deliverable = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='recurring_instances',
        help_text="Parent deliverable if this is a recurring instance"
    )
    occurrence_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Which occurrence this is (1, 2, 3, etc.)"
    )
    
    # Status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    
    # Documentation
    notes = models.TextField(blank=True)
    attachments = models.FileField(upload_to='not_deliverables/', null=True, blank=True)
    
    # External requirements
    submit_to = models.CharField(max_length=255, blank=True, help_text="Who/where to submit (e.g., SETA, Client)")
    external_reference = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['due_date', 'title']
        verbose_name = 'NOT Deliverable'
        verbose_name_plural = 'NOT Deliverables'
    
    def __str__(self):
        return f"{self.title} - Due: {self.due_date}"
    
    @property
    def is_overdue(self):
        if self.status not in ['COMPLETED', 'APPROVED']:
            return date.today() > self.due_date
        return False
    
    @property
    def days_until_due(self):
        if self.status in ['COMPLETED', 'APPROVED']:
            return None
        return (self.due_date - date.today()).days
    
    def get_recurrence_delta(self):
        """Return timedelta for the recurrence type"""
        from dateutil.relativedelta import relativedelta
        deltas = {
            'MONTHLY': relativedelta(months=1),
            'QUARTERLY': relativedelta(months=3),
            'BIANNUALLY': relativedelta(months=6),
            'ANNUALLY': relativedelta(years=1),
        }
        return deltas.get(self.recurrence_type)
    
    def generate_recurring_instances(self):
        """
        Generate all recurring instances from this deliverable.
        Returns list of created NOTDeliverable instances.
        """
        if not self.is_recurring or not self.recurrence_type or not self.recurrence_end_date:
            return []
        
        from dateutil.relativedelta import relativedelta
        
        created_instances = []
        delta = self.get_recurrence_delta()
        
        if not delta:
            return []
        
        current_date = self.due_date + delta
        occurrence = 1
        
        while current_date <= self.recurrence_end_date:
            occurrence += 1
            instance = NOTDeliverable.objects.create(
                training_notification=self.training_notification,
                title=f"{self.title} (#{occurrence})",
                deliverable_type=self.deliverable_type,
                description=self.description,
                responsible_stakeholder=self.responsible_stakeholder,
                responsible_department=self.responsible_department,
                due_date=current_date,
                submit_to=self.submit_to,
                is_recurring=False,  # Instances are not recurring themselves
                parent_deliverable=self,
                occurrence_number=occurrence,
                created_by=self.created_by
            )
            created_instances.append(instance)
            current_date = current_date + delta
        
        # Mark the original as occurrence #1
        self.occurrence_number = 1
        self.save(update_fields=['occurrence_number'])
        
        return created_instances

    @property
    def evidence_count(self):
        """Return total evidence files attached"""
        return self.evidence_files.count()
    
    @property
    def verified_evidence_count(self):
        """Return count of verified evidence files"""
        return self.evidence_files.filter(status='VERIFIED').count()
    
    @property
    def pending_evidence_count(self):
        """Return count of pending evidence files"""
        return self.evidence_files.filter(status='PENDING').count()


def validate_evidence_file_extension(value):
    """Validate evidence file has allowed extension"""
    from django.core.exceptions import ValidationError
    import os
    ext = os.path.splitext(value.name)[1].lower()
    allowed = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif']
    if ext not in allowed:
        raise ValidationError(
            f'Invalid file type. Allowed types: {", ".join(allowed)}'
        )


def validate_evidence_file_size(value):
    """Validate evidence file size is under 10MB"""
    from django.core.exceptions import ValidationError
    max_size = 10 * 1024 * 1024  # 10MB
    if value.size > max_size:
        raise ValidationError('File size must be under 10MB.')


class NOTDeliverableEvidenceRequirement(AuditedModel):
    """
    QC Template: Defines what evidence/documents are required for a deliverable type.
    Used to create checklists for QC verification.
    """
    
    DELIVERABLE_TYPE_CHOICES = NOTDeliverable.DELIVERABLE_TYPE_CHOICES
    
    deliverable_type = models.CharField(
        max_length=50,
        choices=DELIVERABLE_TYPE_CHOICES,
        help_text="Which deliverable type this requirement applies to"
    )
    name = models.CharField(max_length=255, help_text="Name of required evidence")
    description = models.TextField(blank=True, help_text="Details of what is expected")
    is_mandatory = models.BooleanField(default=True, help_text="Must be provided for QC pass")
    acceptance_criteria = models.TextField(
        blank=True, 
        help_text="Criteria that must be met for this evidence to be accepted"
    )
    order = models.PositiveIntegerField(default=0, help_text="Display order in checklist")
    
    class Meta:
        ordering = ['deliverable_type', 'order', 'name']
        verbose_name = 'Deliverable Evidence Requirement'
        verbose_name_plural = 'Deliverable Evidence Requirements'
        unique_together = ['deliverable_type', 'name']
    
    def __str__(self):
        return f"{self.get_deliverable_type_display()} - {self.name}"


class NOTDeliverableEvidence(AuditedModel):
    """
    Evidence files attached to deliverables for QC verification.
    Supports multiple files per deliverable.
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('NEEDS_REVISION', 'Needs Revision'),
    ]
    
    deliverable = models.ForeignKey(
        NOTDeliverable,
        on_delete=models.CASCADE,
        related_name='evidence_files'
    )
    
    # Optional link to QC requirement (for template-based QC)
    requirement = models.ForeignKey(
        NOTDeliverableEvidenceRequirement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fulfilled_evidence',
        help_text="Which QC requirement this evidence fulfills"
    )
    
    # File storage
    file = models.FileField(
        upload_to='deliverable_evidence/%Y/%m/',
        validators=[validate_evidence_file_extension, validate_evidence_file_size]
    )
    original_filename = models.CharField(max_length=255, help_text="Original uploaded filename")
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    
    # Metadata
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # QC Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Verification workflow
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliverable_evidence_verified'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Rejection details
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['deliverable', '-created_at']
        verbose_name = 'Deliverable Evidence'
        verbose_name_plural = 'Deliverable Evidence'
    
    def __str__(self):
        return f"{self.deliverable.title} - {self.title}"
    
    def save(self, *args, **kwargs):
        # Auto-populate file metadata
        if self.file and not self.original_filename:
            self.original_filename = self.file.name.split('/')[-1]
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    @property
    def file_extension(self):
        import os
        return os.path.splitext(self.original_filename)[1].lower()
    
    @property
    def is_image(self):
        return self.file_extension in ['.jpg', '.jpeg', '.png', '.gif']
    
    @property
    def is_pdf(self):
        return self.file_extension == '.pdf'
    
    @property
    def file_size_display(self):
        """Human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class NOTMeetingMinutes(AuditedModel):
    """
    Meeting minutes and discussion points for NOT planning meetings.
    """
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='meeting_minutes'
    )
    meeting_date = models.DateTimeField()
    meeting_type = models.CharField(
        max_length=30,
        choices=[
            ('PLANNING', 'Initial Planning Meeting'),
            ('PROGRESS', 'Progress Review'),
            ('STAKEHOLDER', 'Stakeholder Meeting'),
            ('PROBLEM_SOLVING', 'Problem Solving'),
            ('CLOSEOUT', 'Project Closeout'),
        ],
        default='PLANNING'
    )
    
    attendees = models.ManyToManyField(User, related_name='not_meetings_attended')
    
    agenda = models.TextField(blank=True)
    minutes = models.TextField(blank=True)
    decisions = models.TextField(blank=True, help_text="Key decisions made")
    action_items = models.TextField(blank=True, help_text="Action items with owners")
    
    next_meeting_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-meeting_date']
        verbose_name = 'NOT Meeting Minutes'
        verbose_name_plural = 'NOT Meeting Minutes'
    
    def __str__(self):
        return f"Meeting: {self.training_notification.reference_number} - {self.meeting_date.date()}"


class NOTNotificationLog(models.Model):
    """
    Log of all notifications sent for a Training Notification.
    """
    
    NOTIFICATION_TYPE_CHOICES = [
        ('ASSIGNMENT', 'Role Assignment'),
        ('MEETING_INVITE', 'Meeting Invitation'),
        ('REMINDER', 'Reminder'),
        ('RESOURCE_SHORTAGE', 'Resource Shortage Alert'),
        ('DELIVERABLE_DUE', 'Deliverable Due'),
        ('STATUS_CHANGE', 'Status Change'),
        ('APPROVAL_REQUEST', 'Approval Request'),
        ('APPROVAL_GRANTED', 'Approval Granted'),
        ('PROJECT_START', 'Project Start'),
        ('GENERAL', 'General Notification'),
    ]
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='notification_logs'
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='not_notifications_received'
    )
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_via = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', 'Email'),
            ('SMS', 'SMS'),
            ('IN_APP', 'In-App Notification'),
            ('ALL', 'All Channels'),
        ],
        default='EMAIL'
    )
    
    delivered = models.BooleanField(default=False)
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'NOT Notification Log'
        verbose_name_plural = 'NOT Notification Logs'
    
    def __str__(self):
        return f"{self.notification_type} to {self.recipient.email} - {self.sent_at}"


# =============================================================================
# TRANCHE PAYMENT & EVIDENCE MANAGEMENT
# =============================================================================

class TrancheTemplate(AuditedModel):
    """
    Pre-defined tranche structures for different project types.
    These templates define the standard tranches and evidence requirements
    for each type of funded training program.
    """
    
    PROJECT_TYPE_CHOICES = TrainingNotification.PROJECT_TYPE_CHOICES
    
    FUNDER_CHOICES = TrainingNotification.FUNDER_CHOICES
    
    name = models.CharField(max_length=255, help_text="Template name, e.g., 'MERSETA OC Apprenticeship 3-Year'")
    project_type = models.CharField(max_length=30, choices=PROJECT_TYPE_CHOICES)
    funder_type = models.CharField(max_length=30, choices=FUNDER_CHOICES)
    description = models.TextField(blank=True)
    
    duration_months = models.PositiveIntegerField(default=36, help_text="Total program duration in months")
    total_tranches = models.PositiveIntegerField(default=9, help_text="Total number of tranches")
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['project_type', 'funder_type', 'name']
        verbose_name = 'Tranche Template'
        verbose_name_plural = 'Tranche Templates'
        unique_together = ['project_type', 'funder_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_project_type_display()})"


class TrancheTemplateItem(AuditedModel):
    """
    Individual tranche definition within a template.
    Defines the sequence, timing, and evidence requirements for each tranche.
    """
    
    TRANCHE_TYPE_CHOICES = [
        ('COMMENCEMENT', 'Commencement'),
        ('RECRUITMENT', 'Learner Recruitment'),
        ('REGISTRATION', 'Learner Registration'),
        ('PPE_TOOLBOX', 'PPE & Toolbox Issuance'),
        ('LEARNING_MATERIAL', 'Learning Material Issuance'),
        ('ASSESSMENT_1', 'Assessment Cycle 1'),
        ('ASSESSMENT_2', 'Assessment Cycle 2'),
        ('ASSESSMENT_3', 'Assessment Cycle 3'),
        ('PLACEMENT', 'Workplace Placement'),
        ('MODERATION', 'Moderation'),
        ('TRADE_TEST', 'Trade Test'),
        ('CERTIFICATION', 'Certification'),
        ('COMPLETION', 'Programme Completion'),
        ('FINAL', 'Final Claim'),
        ('INTERIM', 'Interim Claim'),
        ('CUSTOM', 'Custom Milestone'),
    ]
    
    template = models.ForeignKey(
        TrancheTemplate,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    sequence_number = models.PositiveIntegerField(help_text="Order in the tranche sequence")
    tranche_type = models.CharField(max_length=30, choices=TRANCHE_TYPE_CHOICES)
    name = models.CharField(max_length=255, help_text="Tranche name, e.g., 'Tranche 1 - Commencement'")
    description = models.TextField(blank=True)
    
    # Timing
    months_from_start = models.PositiveIntegerField(
        default=0, 
        help_text="Months from program start when this tranche is due"
    )
    days_before_deadline_reminder = models.PositiveIntegerField(
        default=14,
        help_text="Days before due date to send reminder"
    )
    
    # Financial
    percentage_of_total = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=0,
        help_text="Percentage of total contract value for this tranche"
    )
    
    # Evidence requirements as JSON
    evidence_requirements = models.JSONField(
        default=list,
        blank=True,
        help_text="List of evidence types required for this tranche"
    )
    
    class Meta:
        ordering = ['template', 'sequence_number']
        verbose_name = 'Tranche Template Item'
        verbose_name_plural = 'Tranche Template Items'
        unique_together = ['template', 'sequence_number']
    
    def __str__(self):
        return f"{self.template.name} - {self.sequence_number}. {self.name}"


class TrancheSchedule(AuditedModel):
    """
    Actual tranche schedule for a specific Training Notification (NOT).
    Created from a template or manually, tracks the payment milestones
    and evidence collection for a funded training project.
    """
    
    TRANCHE_TYPE_CHOICES = TrancheTemplateItem.TRANCHE_TYPE_CHOICES
    
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('EVIDENCE_COLLECTION', 'Collecting Evidence'),
        ('EVIDENCE_COMPLETE', 'Evidence Complete'),
        ('PENDING_QC', 'Pending Quality Check'),
        ('QC_FAILED', 'QC Failed - Rework Required'),
        ('QC_PASSED', 'QC Passed'),
        ('SUBMITTED', 'Submitted to Funder'),
        ('QUERY', 'Funder Query'),
        ('APPROVED', 'Approved by Funder'),
        ('INVOICED', 'Invoice Sent'),
        ('PAID', 'Payment Received'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    # Link to NOT
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='tranches'
    )
    
    # Template reference (optional)
    template_item = models.ForeignKey(
        TrancheTemplateItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_instances'
    )
    
    # Tranche Details
    reference_number = models.CharField(max_length=50, unique=True, editable=False)
    sequence_number = models.PositiveIntegerField(help_text="Order in the tranche sequence")
    tranche_type = models.CharField(max_length=30, choices=TRANCHE_TYPE_CHOICES)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='SCHEDULED')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Dates
    due_date = models.DateField(help_text="Target date for tranche completion")
    reminder_date = models.DateField(null=True, blank=True, help_text="Date to send reminder")
    
    evidence_submitted_date = models.DateField(null=True, blank=True)
    qc_completed_date = models.DateField(null=True, blank=True)
    submitted_to_funder_date = models.DateField(null=True, blank=True)
    funder_approved_date = models.DateField(null=True, blank=True)
    invoice_sent_date = models.DateField(null=True, blank=True)
    payment_received_date = models.DateField(null=True, blank=True)
    
    # Financial
    amount = models.DecimalField(
        max_digits=14, 
        decimal_places=2,
        default=0,
        help_text="Amount to be claimed for this tranche"
    )
    actual_amount_received = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual amount received (may differ from claimed)"
    )
    
    # Invoice Link
    invoice = models.ForeignKey(
        'finance.Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tranches'
    )
    
    # Learner counts at this tranche
    learner_count_target = models.PositiveIntegerField(default=0, help_text="Target learner count")
    learner_count_actual = models.PositiveIntegerField(default=0, help_text="Actual learner count at submission")
    
    # QC Details
    qc_performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tranches_qc_performed'
    )
    qc_notes = models.TextField(blank=True)
    qc_passed = models.BooleanField(null=True, blank=True)
    
    # Funder Response
    funder_reference = models.CharField(max_length=100, blank=True, help_text="Funder's reference number")
    funder_response_notes = models.TextField(blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['training_notification', 'sequence_number']
        verbose_name = 'Tranche Schedule'
        verbose_name_plural = 'Tranche Schedules'
        unique_together = ['training_notification', 'sequence_number']
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Generate reference: TRN-NOT-XXX-01
            not_ref = self.training_notification.reference_number.replace('NOT-', '')
            self.reference_number = f"TRN-{not_ref}-{self.sequence_number:02d}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.reference_number} - {self.name}"
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.status in ['PAID', 'CANCELLED']:
            return False
        return self.due_date < timezone.now().date()
    
    @property
    def days_until_due(self):
        from django.utils import timezone
        if self.due_date:
            delta = self.due_date - timezone.now().date()
            return delta.days
        return None
    
    @property
    def evidence_completion_percentage(self):
        """Calculate percentage of evidence requirements fulfilled"""
        requirements = self.evidence_requirements.all()
        if not requirements.exists():
            return 100
        completed = requirements.filter(evidence__isnull=False).distinct().count()
        total = requirements.count()
        return int((completed / total) * 100) if total > 0 else 0


class TrancheEvidenceRequirement(AuditedModel):
    """
    Defines what evidence is required for a specific tranche.
    Each requirement can be marked as mandatory or optional.
    """
    
    EVIDENCE_TYPE_CHOICES = [
        # Learner Documentation
        ('LEARNER_LIST', 'Learner List/Register'),
        ('LEARNER_AGREEMENTS', 'Learner Agreements'),
        ('ID_COPIES', 'ID Document Copies'),
        ('QUALIFICATION_COPIES', 'Qualification Copies'),
        
        # Registration & Enrollment
        ('REGISTRATION_FORMS', 'Registration Forms'),
        ('ENROLLMENT_PROOF', 'Enrollment Confirmation'),
        ('NLRD_REGISTRATION', 'NLRD Registration Proof'),
        ('SETA_REGISTRATION', 'SETA Registration Confirmation'),
        
        # PPE & Equipment
        ('PPE_ISSUE_REGISTER', 'PPE Issue Register'),
        ('TOOLBOX_ISSUE_REGISTER', 'Toolbox Issue Register'),
        ('EQUIPMENT_PHOTOS', 'Equipment Issue Photos'),
        ('DELIVERY_NOTES', 'Delivery Notes'),
        
        # Learning Materials
        ('MATERIAL_ISSUE_REGISTER', 'Learning Material Issue Register'),
        ('TEXTBOOK_LIST', 'Textbook/Material List'),
        
        # Attendance & Training
        ('ATTENDANCE_REGISTERS', 'Attendance Registers'),
        ('TRAINING_SCHEDULE', 'Training Schedule'),
        ('FACILITATOR_REPORTS', 'Facilitator Reports'),
        ('LESSON_PLANS', 'Lesson Plans'),
        
        # Assessments
        ('ASSESSMENT_SCHEDULE', 'Assessment Schedule'),
        ('ASSESSMENT_RESULTS', 'Assessment Results'),
        ('COMPETENCY_MATRIX', 'Competency Matrix'),
        ('POE_SAMPLES', 'POE Samples'),
        ('ASSESSMENT_TOOLS', 'Assessment Tools Used'),
        
        # Workplace
        ('PLACEMENT_LETTERS', 'Workplace Placement Letters'),
        ('WORKPLACE_AGREEMENTS', 'Workplace Agreements'),
        ('MENTOR_ASSIGNMENTS', 'Mentor Assignment Records'),
        ('LOGBOOKS', 'Learner Logbooks'),
        ('WORKPLACE_REPORTS', 'Workplace Progress Reports'),
        
        # Moderation & Verification
        ('MODERATION_REPORTS', 'Moderation Reports'),
        ('VERIFICATION_REPORTS', 'Verification Reports'),
        ('EXTERNAL_MODERATION', 'External Moderation Proof'),
        
        # Trade Test & Certification
        ('TRADE_TEST_BOOKINGS', 'Trade Test Bookings'),
        ('TRADE_TEST_RESULTS', 'Trade Test Results'),
        ('CERTIFICATES', 'Certificates Issued'),
        ('CERTIFICATE_REGISTER', 'Certificate Issue Register'),
        
        # Financial & Administrative
        ('INVOICES', 'Invoices'),
        ('BANK_STATEMENTS', 'Bank Statements'),
        ('FINANCIAL_REPORT', 'Financial Report'),
        ('PROJECT_REPORT', 'Project Progress Report'),
        
        # Photos & Media
        ('TRAINING_PHOTOS', 'Training Session Photos'),
        ('CEREMONY_PHOTOS', 'Ceremony/Event Photos'),
        ('SITE_PHOTOS', 'Training Site Photos'),
        
        # Other
        ('OTHER', 'Other Supporting Document'),
    ]
    
    tranche = models.ForeignKey(
        TrancheSchedule,
        on_delete=models.CASCADE,
        related_name='evidence_requirements'
    )
    
    evidence_type = models.CharField(max_length=50, choices=EVIDENCE_TYPE_CHOICES)
    name = models.CharField(max_length=255, help_text="Specific name for this evidence requirement")
    description = models.TextField(blank=True, help_text="Details about what is required")
    
    is_mandatory = models.BooleanField(default=True)
    
    # Expected counts (for documents with multiple items)
    expected_count = models.PositiveIntegerField(
        default=1,
        help_text="Expected number of documents/items (e.g., one per learner)"
    )
    
    # Deadline (can differ from tranche due date)
    deadline = models.DateField(null=True, blank=True)
    
    # Verification
    requires_verification = models.BooleanField(default=False)
    verification_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['tranche', 'evidence_type']
        verbose_name = 'Tranche Evidence Requirement'
        verbose_name_plural = 'Tranche Evidence Requirements'
    
    def __str__(self):
        return f"{self.tranche.reference_number} - {self.get_evidence_type_display()}"
    
    @property
    def is_fulfilled(self):
        """Check if this requirement has been fulfilled"""
        return self.evidence.filter(status='VERIFIED').exists()
    
    @property
    def collected_count(self):
        """Number of evidence items collected"""
        return self.evidence.count()


class TrancheEvidence(AuditedModel):
    """
    Actual evidence documents collected for a tranche requirement.
    Links to the learners Document model for file storage.
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('NEEDS_REVISION', 'Needs Revision'),
    ]
    
    requirement = models.ForeignKey(
        TrancheEvidenceRequirement,
        on_delete=models.CASCADE,
        related_name='evidence'
    )
    
    # Link to actual document
    document = models.ForeignKey(
        'learners.Document',
        on_delete=models.CASCADE,
        related_name='tranche_evidence'
    )
    
    # Additional metadata
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Verification
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tranche_evidence_verified'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Rejection details
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['requirement', '-created_at']
        verbose_name = 'Tranche Evidence'
        verbose_name_plural = 'Tranche Evidence'
    
    def __str__(self):
        return f"{self.requirement.tranche.reference_number} - {self.title}"


class TrancheSubmission(AuditedModel):
    """
    Tracks the submission of a tranche claim to the funder.
    Includes all communication and status updates from the funder.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_QC', 'Pending Internal QC'),
        ('QC_APPROVED', 'QC Approved'),
        ('SUBMITTED', 'Submitted to Funder'),
        ('ACKNOWLEDGED', 'Funder Acknowledged Receipt'),
        ('UNDER_REVIEW', 'Under Funder Review'),
        ('QUERY', 'Funder Query'),
        ('QUERY_RESOLVED', 'Query Resolved'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PAYMENT_PENDING', 'Payment Pending'),
        ('PAID', 'Paid'),
    ]
    
    SUBMISSION_METHOD_CHOICES = [
        ('PORTAL', 'Online Portal'),
        ('EMAIL', 'Email'),
        ('HAND_DELIVERY', 'Hand Delivery'),
        ('COURIER', 'Courier'),
        ('POST', 'Postal Service'),
    ]
    
    tranche = models.ForeignKey(
        TrancheSchedule,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    
    submission_reference = models.CharField(max_length=100, unique=True, editable=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    
    # Submission Details
    submission_method = models.CharField(max_length=30, choices=SUBMISSION_METHOD_CHOICES, default='PORTAL')
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tranche_submissions'
    )
    submission_date = models.DateTimeField(null=True, blank=True)
    
    # Funder Portal Details
    portal_reference = models.CharField(max_length=100, blank=True)
    portal_submission_id = models.CharField(max_length=100, blank=True)
    
    # QC Details
    qc_checklist_completed = models.BooleanField(default=False)
    qc_completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tranche_qc_completed'
    )
    qc_completed_date = models.DateTimeField(null=True, blank=True)
    qc_notes = models.TextField(blank=True)
    
    # Funder Response
    funder_response_date = models.DateTimeField(null=True, blank=True)
    funder_reference = models.CharField(max_length=100, blank=True)
    funder_notes = models.TextField(blank=True)
    
    # Amount Details
    claimed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    approved_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    
    # Payment Details
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    
    # Documents (as JSON list of document IDs or paths)
    attached_documents = models.JSONField(default=list, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-submission_date', '-created_at']
        verbose_name = 'Tranche Submission'
        verbose_name_plural = 'Tranche Submissions'
    
    def save(self, *args, **kwargs):
        if not self.submission_reference:
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d%H%M')
            self.submission_reference = f"SUB-{self.tranche.reference_number}-{timestamp}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.submission_reference} ({self.get_status_display()})"


class TrancheComment(AuditedModel):
    """
    Comments and communication log for a tranche.
    Used for internal notes and tracking funder communication.
    """
    
    COMMENT_TYPE_CHOICES = [
        ('INTERNAL', 'Internal Note'),
        ('FUNDER_QUERY', 'Funder Query'),
        ('FUNDER_RESPONSE', 'Response to Funder'),
        ('QC_NOTE', 'QC Note'),
        ('STATUS_UPDATE', 'Status Update'),
    ]
    
    tranche = models.ForeignKey(
        TrancheSchedule,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    comment_type = models.CharField(max_length=30, choices=COMMENT_TYPE_CHOICES, default='INTERNAL')
    comment = models.TextField()
    
    # If related to a submission
    submission = models.ForeignKey(
        TrancheSubmission,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='comments'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Tranche Comment'
        verbose_name_plural = 'Tranche Comments'
    
    def __str__(self):
        return f"{self.tranche.reference_number} - {self.get_comment_type_display()} ({self.created_at})"


# =====================================================
# MESSAGING SYSTEM MODELS
# =====================================================

class MessageThread(AuditedModel):
    """
    Conversation thread between users.
    Can be linked to a placement for context.
    """
    THREAD_TYPE_CHOICES = [
        ('GENERAL', 'General'),
        ('PLACEMENT', 'Placement Related'),
        ('SUPPORT', 'Support/Advice'),
        ('DISCIPLINARY', 'Disciplinary'),
        ('ACADEMIC', 'Academic'),
    ]
    
    subject = models.CharField(max_length=200)
    thread_type = models.CharField(
        max_length=20,
        choices=THREAD_TYPE_CHOICES,
        default='GENERAL'
    )
    
    # Optional link to placement for context
    related_placement = models.ForeignKey(
        'corporate.WorkplacePlacement',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='message_threads'
    )
    
    # Optional link to learner (if not placement-specific)
    related_learner = models.ForeignKey(
        'learners.Learner',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='message_threads'
    )
    
    is_archived = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Message Thread'
        verbose_name_plural = 'Message Threads'
    
    def __str__(self):
        return self.subject
    
    @property
    def last_message(self):
        return self.messages.order_by('-sent_at').first()
    
    @property
    def message_count(self):
        return self.messages.count()


class ThreadParticipant(models.Model):
    """
    Participant in a message thread.
    Tracks read status and participation.
    """
    ROLE_LABEL_CHOICES = [
        ('LEARNER', 'Learner'),
        ('MENTOR', 'Mentor'),
        ('FACILITATOR', 'Facilitator'),
        ('WORKPLACE_OFFICER', 'Workplace Officer'),
        ('HOST_EMPLOYER', 'Host Employer'),
        ('ADMIN', 'Administrator'),
    ]
    
    thread = models.ForeignKey(
        MessageThread,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='thread_participations'
    )
    
    role_label = models.CharField(
        max_length=20,
        choices=ROLE_LABEL_CHOICES,
        blank=True
    )
    
    # Read tracking
    last_read_at = models.DateTimeField(null=True, blank=True)
    
    # Notifications
    is_muted = models.BooleanField(default=False)
    
    # Participation
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['thread', 'user']
        verbose_name = 'Thread Participant'
        verbose_name_plural = 'Thread Participants'
    
    def __str__(self):
        return f"{self.user.get_full_name()} in {self.thread.subject}"
    
    @property
    def unread_count(self):
        if not self.last_read_at:
            return self.thread.messages.count()
        return self.thread.messages.filter(sent_at__gt=self.last_read_at).count()


class Message(models.Model):
    """
    Individual message within a thread.
    """
    thread = models.ForeignKey(
        MessageThread,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='thread_messages_sent'
    )
    
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    
    # System messages (e.g., "User joined the conversation")
    is_system_message = models.BooleanField(default=False)
    
    # Edit tracking
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    
    # Read receipts (JSON: {user_id: timestamp})
    read_by = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['sent_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
    
    def __str__(self):
        sender_name = self.sender.get_full_name() if self.sender else 'System'
        return f"{sender_name}: {self.content[:50]}..."
    
    def mark_read_by(self, user):
        """Mark message as read by a user"""
        from django.utils import timezone
        self.read_by[str(user.id)] = timezone.now().isoformat()
        self.save(update_fields=['read_by'])


# =====================================================
# NOTIFICATION SYSTEM MODELS
# =====================================================

class Notification(models.Model):
    """
    User notification for system events.
    Supports email and SMS delivery.
    """
    NOTIFICATION_TYPE_CHOICES = [
        # Attendance & Logbooks
        ('LOGBOOK_UNSIGNED', 'Logbook Requires Signature'),
        ('LOGBOOK_SIGNED', 'Logbook Signed'),
        ('ATTENDANCE_REMINDER', 'Attendance Submission Reminder'),
        ('ATTENDANCE_VERIFIED', 'Attendance Verified'),
        
        # Disciplinary
        ('DISCIPLINARY_ACTION', 'Disciplinary Action'),
        ('DISCIPLINARY_REVIEW_DUE', 'Disciplinary Review Due'),
        
        # Stipends
        ('STIPEND_CALCULATED', 'Stipend Calculated'),
        ('STIPEND_APPROVED', 'Stipend Approved'),
        
        # Placements
        ('PLACEMENT_VISIT_SCHEDULED', 'Placement Visit Scheduled'),
        ('PLACEMENT_STATUS_CHANGE', 'Placement Status Changed'),
        
        # Messaging
        ('NEW_MESSAGE', 'New Message'),
        
        # Workplace Modules
        ('WM_COMPLETED', 'Workplace Module Completed'),
        ('WM_SIGNED', 'Workplace Module Signed Off'),
        
        # Corporate Services
        ('TASK_COMPLETED', 'Service Task Completed'),
        ('TASK_EVIDENCE_UPLOADED', 'Task Evidence Uploaded'),
        
        # General
        ('SYSTEM', 'System Notification'),
        ('REMINDER', 'Reminder'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='system_notifications'
    )
    
    notification_type = models.CharField(
        max_length=30,
        choices=NOTIFICATION_TYPE_CHOICES,
        default='SYSTEM'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='NORMAL'
    )
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Link to related object
    link = models.CharField(max_length=500, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery status
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    sms_sent = models.BooleanField(default=False)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'notification_type']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"
    
    def mark_read(self):
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])


class NotificationPreference(models.Model):
    """
    User preferences for notification delivery.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='system_notification_preferences'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=Notification.NOTIFICATION_TYPE_CHOICES
    )
    
    # Delivery preferences
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['user', 'notification_type']
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"{self.user.email} - {self.notification_type}"


# =====================================================
# DOCUMENT MANAGEMENT MODELS
# =====================================================

class ManagedDocument(AuditedModel):
    """
    Unified document management with support for local and SharePoint storage.
    Abstracts storage backend - application queries ManagedDocument,
    service handles SharePoint/local transparently.
    """
    STORAGE_BACKEND_CHOICES = [
        ('LOCAL', 'Local Storage'),
        ('SHAREPOINT', 'SharePoint'),
    ]
    
    DOCUMENT_TYPE_CHOICES = [
        # Learner documents
        ('ID_COPY', 'ID Copy'),
        ('QUALIFICATION', 'Qualification Certificate'),
        ('AGREEMENT', 'Agreement/Contract'),
        
        # Workplace documents
        ('LOGBOOK_SCAN', 'Logbook Scan'),
        ('ATTENDANCE_REGISTER', 'Attendance Register'),
        ('LEAVE_DOCUMENT', 'Leave Supporting Document'),
        ('WM_EVIDENCE', 'Workplace Module Evidence'),
        
        # Disciplinary
        ('DISCIPLINARY_NOTICE', 'Disciplinary Notice'),
        ('DISCIPLINARY_RESPONSE', 'Disciplinary Response'),
        ('HEARING_MINUTES', 'Hearing Minutes'),
        
        # Placement
        ('PLACEMENT_LETTER', 'Placement Letter'),
        ('VISIT_REPORT', 'Visit Report'),
        
        # Other
        ('REPORT', 'Report'),
        ('CORRESPONDENCE', 'Correspondence'),
        ('OTHER', 'Other'),
    ]
    
    title = models.CharField(max_length=200)
    document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPE_CHOICES,
        default='OTHER'
    )
    description = models.TextField(blank=True)
    
    # Storage backend
    storage_backend = models.CharField(
        max_length=20,
        choices=STORAGE_BACKEND_CHOICES,
        default='LOCAL'
    )
    
    # Local storage
    local_file = models.FileField(
        upload_to='managed_documents/%Y/%m/',
        null=True, blank=True
    )
    
    # SharePoint storage
    sharepoint_id = models.CharField(max_length=255, blank=True)
    sharepoint_site_id = models.CharField(max_length=255, blank=True)
    sharepoint_drive_id = models.CharField(max_length=255, blank=True)
    sharepoint_item_id = models.CharField(max_length=255, blank=True)
    sharepoint_web_url = models.URLField(max_length=500, blank=True)
    sharepoint_folder_path = models.CharField(max_length=500, blank=True)
    
    # File metadata
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)  # bytes
    mime_type = models.CharField(max_length=100, blank=True)
    file_hash = models.CharField(max_length=64, blank=True)  # SHA-256
    
    # Thumbnail/Preview caching for SharePoint docs
    thumbnail_cache = models.ImageField(
        upload_to='document_thumbnails/',
        null=True, blank=True
    )
    preview_cached_at = models.DateTimeField(null=True, blank=True)
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Versioning
    version = models.PositiveIntegerField(default=1)
    replaces = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='replaced_by'
    )
    
    # Access control
    is_confidential = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Managed Document'
        verbose_name_plural = 'Managed Documents'
        indexes = [
            models.Index(fields=['document_type']),
            models.Index(fields=['storage_backend']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_document_type_display()})"
    
    @property
    def file_url(self):
        """Get URL to access the document"""
        if self.storage_backend == 'LOCAL' and self.local_file:
            return self.local_file.url
        elif self.storage_backend == 'SHAREPOINT' and self.sharepoint_web_url:
            return self.sharepoint_web_url
        return None
    
    @property
    def file_size_display(self):
        """Human-readable file size"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"


# =====================================================
# WORKPLACE OFFICER PROFILE
# =====================================================

class WorkplaceOfficerProfile(AuditedModel):
    """
    Profile for workplace officers who monitor learner placements.
    Links to User for portal access.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='workplace_officer_profile'
    )
    
    employee_number = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Region/Area assignment
    assigned_region = models.CharField(max_length=100, blank=True)
    
    # Capacity
    max_placements = models.PositiveIntegerField(
        default=30,
        help_text='Maximum number of placements this officer can manage'
    )
    
    # Qualifications
    qualifications = models.TextField(blank=True)
    
    # Digital Signature (captured during onboarding, locked after first capture)
    signature = models.ImageField(
        upload_to='signatures/officers/%Y/%m/',
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
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Workplace Officer Profile'
        verbose_name_plural = 'Workplace Officer Profiles'
    
    def __str__(self):
        return f"WO: {self.user.get_full_name()}"
    
    @property
    def current_placement_count(self):
        """Count of currently assigned active placements"""
        from corporate.models import WorkplacePlacement
        return WorkplacePlacement.objects.filter(
            workplace_officer=self.user,
            status='ACTIVE'
        ).count()
    
    @property
    def available_capacity(self):
        return max(0, self.max_placements - self.current_placement_count)


# ==============================================
# ACCESS REQUEST SYSTEM
# ==============================================
class AccessRequest(AuditedModel):
    """
    Model for self-service registration requests.
    New staff can sign up and request access to specific sections.
    Admins review and approve/modify/reject requests.
    """
    
    REQUEST_STATUS = [
        ('PENDING', 'Pending Review'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    ]
    
    # Personal Information (collected during signup)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    
    # Password will be stored hashed for approved users
    password_hash = models.CharField(max_length=255)
    
    # Employment Information
    employee_number = models.CharField(max_length=50, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    
    # Organization Scope (where they work)
    requested_brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_requests',
        help_text='The brand/organization the user belongs to'
    )
    requested_campus = models.ForeignKey(
        'tenants.Campus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_requests',
        help_text='The campus/site the user is based at'
    )
    
    # Requested Access - Many-to-Many to Roles
    requested_roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name='access_requests',
        help_text='The roles/sections the user is requesting access to'
    )
    
    # Additional Access Notes
    access_justification = models.TextField(
        blank=True,
        help_text='Why the user needs the requested access'
    )
    
    # Request Status
    status = models.CharField(max_length=20, choices=REQUEST_STATUS, default='PENDING')
    
    # Request Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Request expires if not reviewed by this date'
    )
    
    # Review Information
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_access_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(
        blank=True,
        help_text='Admin notes about the decision'
    )
    
    # Approved Roles (may differ from requested)
    approved_roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name='approved_access_requests',
        help_text='The roles actually approved (admin can modify)'
    )
    approved_brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_access_requests'
    )
    approved_campus = models.ForeignKey(
        'tenants.Campus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_access_requests'
    )
    
    # Created User (populated after approval)
    created_user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_request_origin'
    )
    
    # Email Verification
    verification_token = models.CharField(max_length=100, blank=True)
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Access Request'
        verbose_name_plural = 'Access Requests'
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email}) - {self.status}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_pending(self):
        return self.status == 'PENDING'
    
    @property
    def is_expired(self):
        from django.utils import timezone
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return self.status == 'EXPIRED'
    
    def set_password(self, raw_password):
        """Hash and store the password."""
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)
    
    def check_password(self, raw_password):
        """Check the password against the stored hash."""
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)
    
    def generate_verification_token(self):
        """Generate a unique email verification token."""
        import secrets
        self.verification_token = secrets.token_urlsafe(32)
        return self.verification_token
    
    def approve(self, reviewer, approved_roles=None, approved_brand=None, approved_campus=None, notes=''):
        """
        Approve the request and create the user account.
        """
        from django.utils import timezone
        from django.contrib.auth.hashers import check_password
        
        # Update request status
        self.status = 'APPROVED'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        
        # Set approved scope (use requested if not overridden)
        self.approved_brand = approved_brand or self.requested_brand
        self.approved_campus = approved_campus or self.requested_campus
        
        # Create the user
        user = User.objects.create(
            email=self.email,
            first_name=self.first_name,
            last_name=self.last_name,
            phone=self.phone,
            is_active=True,
            email_verified=self.email_verified
        )
        # Set password from stored hash
        user.password = self.password_hash
        user.save()
        
        self.created_user = user
        self.save()
        
        # Assign roles
        roles_to_assign = approved_roles if approved_roles else self.requested_roles.all()
        for role in roles_to_assign:
            UserRole.objects.create(
                user=user,
                role=role,
                brand=self.approved_brand,
                campus=self.approved_campus,
                created_by=reviewer
            )
        
        # Update approved_roles M2M
        self.approved_roles.set(roles_to_assign)
        
        return user
    
    def reject(self, reviewer, notes=''):
        """Reject the access request."""
        from django.utils import timezone
        
        self.status = 'REJECTED'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
    
    def mark_expired(self):
        """Mark the request as expired."""
        self.status = 'EXPIRED'
        self.save()


class AccessRequestSection(AuditedModel):
    """
    Predefined sections/modules users can request access to.
    Maps to specific roles or permission sets.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Icon class or emoji')
    
    # Which role(s) this section grants
    default_roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name='access_sections',
        help_text='Roles granted when this section is approved'
    )
    
    # Display order
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Access level required to see this section as requestable
    min_access_level = models.CharField(
        max_length=20,
        choices=[
            ('SELF', 'Self Service'),
            ('CAMPUS', 'Campus Level'),
            ('BRAND', 'Brand Level'),
            ('HEAD_OFFICE', 'Head Office'),
        ],
        default='CAMPUS',
        help_text='Minimum organizational level to request this section'
    )
    
    class Meta:
        verbose_name = 'Access Request Section'
        verbose_name_plural = 'Access Request Sections'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class AccessRequestSectionChoice(models.Model):
    """
    Links AccessRequest to specific sections they're requesting.
    """
    access_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name='section_choices'
    )
    section = models.ForeignKey(
        AccessRequestSection,
        on_delete=models.CASCADE,
        related_name='request_choices'
    )
    is_approved = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['access_request', 'section']
    
    def __str__(self):
        return f"{self.access_request.email} - {self.section.name}"


# =====================================================
# DIGITAL SIGNATURE CAPTURE
# =====================================================

class SignatureCapture(AuditedModel):
    """
    Stores digital signatures captured during onboarding.
    Signatures are locked after first capture and can only be unlocked by admin.
    Used for compliance document generation (agreements, certificates, etc.)
    
    POPIA Compliance: Captures consent timestamp, IP address, and full legal text.
    Image Format: PNG with transparent background, standardized to 400x150px.
    """
    POPIA_CONSENT_TEXT_DEFAULT = (
        "I consent to SkillsFlow storing and using my digital signature for the purpose of "
        "generating compliance documents, agreements, and certificates on my behalf. "
        "I understand that my signature will be securely stored in accordance with the "
        "Protection of Personal Information Act (POPIA) and will only be used for official "
        "training-related documentation. I confirm that I am the person whose signature is "
        "being captured and that this digital signature has the same legal effect as my "
        "handwritten signature."
    )
    
    # Link to user (owner of the signature)
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        related_name='signature_capture',
        help_text='User this signature belongs to'
    )
    
    # Signature image (PNG with transparent background, 400x150px)
    signature_image = models.ImageField(
        upload_to='signatures/%Y/%m/',
        help_text='PNG image with transparent background (400x150px)'
    )
    
    # Security hash for integrity verification
    signature_hash = models.CharField(
        max_length=64,
        help_text='SHA-256 hash of the signature image for integrity verification'
    )
    
    # Capture metadata
    captured_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        help_text='IP address from which signature was captured'
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        help_text='Browser/device user agent string'
    )
    
    # POPIA Consent
    popia_consent_text = models.TextField(
        default=POPIA_CONSENT_TEXT_DEFAULT,
        help_text='Full consent text shown to user at time of capture'
    )
    popia_consent_given = models.BooleanField(
        default=True,
        help_text='User explicitly consented to signature storage'
    )
    popia_consent_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp when consent was given'
    )
    
    # Lock mechanism (signatures are locked by default after capture)
    is_locked = models.BooleanField(
        default=True,
        help_text='Locked signatures cannot be modified'
    )
    
    # Admin unlock audit trail
    unlocked_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='signatures_unlocked',
        help_text='Admin who unlocked this signature'
    )
    unlocked_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When signature was unlocked'
    )
    unlock_reason = models.TextField(
        blank=True,
        help_text='Reason for unlocking (required for audit)'
    )
    
    class Meta:
        verbose_name = 'Signature Capture'
        verbose_name_plural = 'Signature Captures'
        ordering = ['-captured_at']
    
    def __str__(self):
        return f"Signature: {self.user.get_full_name()} ({self.captured_at.strftime('%Y-%m-%d')})"
    
    def can_be_modified(self):
        """Check if signature can be modified (only if unlocked)"""
        return not self.is_locked
    
    def unlock(self, admin_user, reason):
        """
        Unlock signature for modification (admin only).
        Creates audit trail of unlock action.
        """
        if not reason.strip():
            raise ValueError("Unlock reason is required for audit trail")
        
        self.is_locked = False
        self.unlocked_by = admin_user
        self.unlocked_at = timezone.now()
        self.unlock_reason = reason
        self.save(update_fields=['is_locked', 'unlocked_by', 'unlocked_at', 'unlock_reason'])
    
    def lock(self):
        """Re-lock signature after modification"""
        self.is_locked = True
        self.save(update_fields=['is_locked'])
    
    def verify_integrity(self):
        """Verify signature image has not been tampered with using stored hash"""
        import hashlib
        if self.signature_image:
            self.signature_image.seek(0)
            computed_hash = hashlib.sha256(self.signature_image.read()).hexdigest()
            return computed_hash == self.signature_hash
        return False


# =============================================================================
# Training Class - Facilitator Assignment
# =============================================================================

class TrainingClass(AuditedModel):
    """
    Training class within a NOT project.
    Groups learners under one facilitator for capacity management.
    Auto-created based on intake size during NOT creation, with manual override option.
    Uses "Group 1, 2, 3..." naming convention.
    """
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='training_classes'
    )
    
    intake = models.ForeignKey(
        'NOTIntake',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='classes',
        help_text="Optional link to specific intake within the NOT"
    )
    
    # Class identification
    name = models.CharField(
        max_length=100,
        help_text="e.g., 'Group 1', 'Group 2'"
    )
    group_number = models.PositiveIntegerField(
        default=1,
        help_text="Group number for ordering"
    )
    
    # Facilitator assignment
    facilitator = models.ForeignKey(
        FacilitatorProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_classes',
        help_text="Facilitator responsible for this class"
    )
    
    # Capacity
    max_capacity = models.PositiveIntegerField(
        default=30,
        help_text="Maximum learners in this class"
    )
    
    # Schedule (optional - just for reference)
    schedule_notes = models.TextField(
        blank=True,
        help_text="Schedule information (days, times, etc.)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['training_notification', 'group_number']
        verbose_name = 'Training Class'
        verbose_name_plural = 'Training Classes'
        unique_together = ['training_notification', 'group_number']
    
    def __str__(self):
        facilitator_name = self.facilitator.user.get_full_name() if self.facilitator else "Unassigned"
        return f"{self.training_notification.reference_number} - {self.name} ({facilitator_name})"
    
    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"Group {self.group_number}"
        super().save(*args, **kwargs)
    
    @property
    def enrolled_count(self):
        """Count of learners enrolled in this class"""
        return self.learner_assignments.filter(is_active=True).count()
    
    @property
    def available_capacity(self):
        """Remaining capacity in this class"""
        return max(0, self.max_capacity - self.enrolled_count)
    
    @property
    def is_full(self):
        """Check if class is at capacity"""
        return self.enrolled_count >= self.max_capacity
    
    @classmethod
    def auto_create_classes(cls, training_notification, learners_per_class=30):
        """
        Auto-create classes based on expected learner count.
        Called during NOT creation/approval.
        Returns list of created classes.
        """
        expected = training_notification.expected_learner_count
        num_classes = max(1, (expected + learners_per_class - 1) // learners_per_class)
        
        created_classes = []
        for i in range(num_classes):
            group_num = i + 1
            class_obj, created = cls.objects.get_or_create(
                training_notification=training_notification,
                group_number=group_num,
                defaults={
                    'name': f"Group {group_num}",
                    'max_capacity': learners_per_class,
                }
            )
            if created:
                created_classes.append(class_obj)
        
        return created_classes


class LearnerClassAssignment(AuditedModel):
    """
    Links a learner's enrollment to a training class.
    Tracks which facilitator teaches which learner.
    Supports class transfers with date tracking.
    """
    
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        on_delete=models.CASCADE,
        related_name='class_assignments'
    )
    
    training_class = models.ForeignKey(
        TrainingClass,
        on_delete=models.CASCADE,
        related_name='learner_assignments'
    )
    
    # Assignment period
    assigned_from = models.DateField(
        default=date.today,
        help_text="When learner was assigned to this class"
    )
    assigned_until = models.DateField(
        null=True, blank=True,
        help_text="When assignment ended (for class transfers)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Transfer tracking
    transfer_reason = models.TextField(
        blank=True,
        help_text="Reason for transfer if moved from another class"
    )
    previous_class = models.ForeignKey(
        TrainingClass,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transferred_from',
        help_text="Previous class if this is a transfer"
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-assigned_from']
        verbose_name = 'Learner Class Assignment'
        verbose_name_plural = 'Learner Class Assignments'
    
    def __str__(self):
        return f"{self.enrollment.learner} in {self.training_class.name}"
    
    @property
    def facilitator(self):
        """Convenience property to get the facilitator for this learner"""
        return self.training_class.facilitator
    
    @property
    def facilitator_name(self):
        """Get facilitator name for display"""
        if self.training_class.facilitator:
            return self.training_class.facilitator.user.get_full_name()
        return "Unassigned"
    
    def transfer_to(self, new_class, reason='', user=None):
        """
        Transfer learner to a different class.
        Closes current assignment and creates new one.
        """
        # Close current assignment
        self.is_active = False
        self.assigned_until = date.today()
        self.save()
        
        # Create new assignment
        new_assignment = LearnerClassAssignment.objects.create(
            enrollment=self.enrollment,
            training_class=new_class,
            assigned_from=date.today(),
            is_active=True,
            transfer_reason=reason,
            previous_class=self.training_class,
            created_by=user,
        )
        return new_assignment


# =============================================================================
# External Moderation Request
# =============================================================================

class ExternalModerationRequest(AuditedModel):
    """
    Request for external moderation from ETQA.
    Tracks the full workflow from request to completion with document attachments.
    Linked to NOTDeliverable for project management integration.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('READY', 'Ready to Submit'),
        ('SUBMITTED', 'Submitted to ETQA'),
        ('ACKNOWLEDGED', 'ETQA Acknowledged'),
        ('SCHEDULED', 'Visit Scheduled'),
        ('IN_PROGRESS', 'Moderation In Progress'),
        ('COMPLETED', 'Completed'),
        ('REQUIRES_RESUBMIT', 'Requires Resubmission'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    RESULT_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESSFUL', 'Successful'),
        ('PARTIAL', 'Partial Success (Corrections Required)'),
        ('UNSUCCESSFUL', 'Unsuccessful'),
    ]
    
    # Link to NOT deliverable (optional - created as standalone or linked)
    deliverable = models.ForeignKey(
        NOTDeliverable,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='moderation_requests',
        help_text="The deliverable this moderation fulfills"
    )
    
    training_notification = models.ForeignKey(
        TrainingNotification,
        on_delete=models.CASCADE,
        related_name='moderation_requests',
        help_text="The NOT project this moderation is for"
    )
    
    # Request details
    reference_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Auto-generated reference number"
    )
    title = models.CharField(
        max_length=255,
        help_text="Brief description of moderation request"
    )
    
    # ETQA Contact
    etqa_name = models.CharField(
        max_length=200,
        help_text="Name of the ETQA body (e.g., NAMB, MerSETA, QCTO)"
    )
    etqa_contact_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Contact person at ETQA"
    )
    etqa_contact_email = models.EmailField(
        blank=True,
        help_text="ETQA contact email"
    )
    etqa_contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="ETQA contact phone"
    )
    
    # Learner selection (manual by external person)
    learners_for_moderation = models.ManyToManyField(
        'learners.Learner',
        blank=True,
        related_name='moderation_requests',
        help_text="Learners selected for this moderation sample"
    )
    sample_size = models.PositiveIntegerField(
        default=0,
        help_text="Number of learners in the moderation sample"
    )
    
    # Status and workflow
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )
    
    # Key dates
    ready_date = models.DateField(
        null=True, blank=True,
        help_text="Date when learners are ready for moderation"
    )
    one_month_reminder_sent = models.BooleanField(
        default=False,
        help_text="Has the 1-month advance reminder been sent?"
    )
    submitted_date = models.DateField(
        null=True, blank=True,
        help_text="Date request was submitted to ETQA"
    )
    scheduled_date = models.DateField(
        null=True, blank=True,
        help_text="Scheduled date for the moderation visit"
    )
    completed_date = models.DateField(
        null=True, blank=True,
        help_text="Date moderation was completed"
    )
    
    # Request documentation (PDF or email sent to ETQA)
    request_document = models.FileField(
        upload_to='moderation_requests/outgoing/%Y/%m/',
        null=True, blank=True,
        help_text="PDF or email attachment sent to ETQA"
    )
    request_notes = models.TextField(
        blank=True,
        help_text="Notes or email content for the request"
    )
    
    # Response documentation (PDF or email from ETQA)
    response_document = models.FileField(
        upload_to='moderation_requests/incoming/%Y/%m/',
        null=True, blank=True,
        help_text="PDF or email response from ETQA"
    )
    response_notes = models.TextField(
        blank=True,
        help_text="ETQA response notes"
    )
    response_date = models.DateField(
        null=True, blank=True,
        help_text="Date of ETQA response"
    )
    
    # Result documentation (final report/certificate)
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default='PENDING'
    )
    result_document = models.FileField(
        upload_to='moderation_requests/results/%Y/%m/',
        null=True, blank=True,
        help_text="Final moderation report/certificate from ETQA"
    )
    result_notes = models.TextField(
        blank=True,
        help_text="Summary of moderation result and any findings"
    )
    
    # Tracking delays and escalation
    days_waiting = models.PositiveIntegerField(
        default=0,
        help_text="Days since submission (auto-calculated)"
    )
    escalation_notes = models.TextField(
        blank=True,
        help_text="Notes on escalation actions taken if ETQA is delayed"
    )
    
    # Assigned to (project admin handling this request)
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_moderation_requests',
        help_text="Project admin responsible for this request"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'External Moderation Request'
        verbose_name_plural = 'External Moderation Requests'
    
    def __str__(self):
        return f"{self.reference_number} - {self.etqa_name} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Generate reference: MOD-YYYYMM-XXXX
            prefix = f"MOD-{timezone.now().strftime('%Y%m')}-"
            last = ExternalModerationRequest.objects.filter(
                reference_number__startswith=prefix
            ).order_by('-reference_number').first()
            if last:
                last_num = int(last.reference_number.split('-')[-1])
                self.reference_number = f"{prefix}{last_num + 1:04d}"
            else:
                self.reference_number = f"{prefix}0001"
        
        # Calculate days waiting
        if self.submitted_date and self.status not in ['COMPLETED', 'CANCELLED']:
            self.days_waiting = (date.today() - self.submitted_date).days
        else:
            self.days_waiting = 0
        
        super().save(*args, **kwargs)
    
    @property
    def is_overdue(self):
        """Check if ETQA response is overdue (>30 days)"""
        if self.submitted_date and self.status in ['SUBMITTED', 'ACKNOWLEDGED']:
            return self.days_waiting > 30
        return False
    
    @property
    def needs_escalation(self):
        """Check if this request needs escalation (>14 days without response)"""
        if self.submitted_date and self.status in ['SUBMITTED', 'ACKNOWLEDGED']:
            return self.days_waiting > 14
        return False
    
    @property
    def days_until_ready(self):
        """Days until learners are ready for moderation"""
        if self.ready_date:
            delta = (self.ready_date - date.today()).days
            return delta if delta > 0 else 0
        return None
    
    @property
    def needs_one_month_reminder(self):
        """Check if 1-month reminder should be sent"""
        if self.ready_date and not self.one_month_reminder_sent:
            days_until = self.days_until_ready
            return days_until is not None and days_until <= 30
        return False
    
    def update_sample_size(self):
        """Update sample size from M2M relationship"""
        self.sample_size = self.learners_for_moderation.count()
        self.save(update_fields=['sample_size'])


# Import NOT Learner Document models to ensure Django discovers them
from .models_not_documents import (
    NOTLearnerDocumentType,
    NOTLearnerDocument,
    NOTProjectDocument
)

# Import Project Template models to ensure Django discovers them
from .project_templates import (
    TriggerType,
    DateReferencePoint,
    RecurringInterval,
    OperationalCategory,
    ProjectTemplateSet,
    ProjectTaskTemplate,
    NOTScheduledTask,
    NOTTemplateSetApplication
)


class UserAuthSession(models.Model):
    """Server-side session backing for refresh tokens.

    Access tokens are short-lived JWTs that reference this session via `sid`.
    Refresh tokens are opaque strings that are stored hashed via
    `refresh_token_hash`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_sessions')
    
    refresh_token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=64, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    
    rotated_from = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='rotations',
    )

    class Meta:
        indexes = [
            models.Index(fields=['user', 'revoked_at']),
            models.Index(fields=['expires_at']),
        ]

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at and timezone.now() >= self.expires_at:
            return False
        return True

    def revoke(self, *, reason: str = '') -> None:
        if self.revoked_at is not None:
            return
        self.revoked_at = timezone.now()
        self.revoke_reason = reason[:64]
        self.save(update_fields=['revoked_at', 'revoke_reason'])


# =============================================================================
# REQUIRED DOCUMENT CONFIGURATION - Global compliance settings
# =============================================================================

class RequiredDocumentConfig(models.Model):
    """
    Global configuration for required documents for enrollment compliance.
    Admin-editable list of document types required for all enrollments.
    """
    DOCUMENT_TYPES = [
        ('ID_COPY', 'ID Copy / Passport'),
        ('MATRIC', 'Matric Certificate'),
        ('PROOF_ADDRESS', 'Proof of Address'),
        ('QUALIFICATION', 'Prior Qualification'),
        ('CV', 'Curriculum Vitae'),
        ('BANK_CONFIRM', 'Bank Confirmation'),
        ('PROOF_OF_PAYMENT', 'Proof of Payment'),
        ('PARENT_ID', 'Parent/Guardian ID'),
        ('PARENT_CONSENT', 'Parent/Guardian Consent'),
    ]
    
    document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPES,
        unique=True
    )
    
    is_required = models.BooleanField(
        default=True,
        help_text="Whether this document is required for enrollment"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description shown to users"
    )
    
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order"
    )
    
    class Meta:
        ordering = ['order', 'document_type']
        verbose_name = 'Required Document Config'
        verbose_name_plural = 'Required Document Configs'
    
    def __str__(self):
        status = "Required" if self.is_required else "Optional"
        return f"{self.get_document_type_display()} ({status})"
    
    @classmethod
    def get_required_types(cls):
        """Get list of required document type codes."""
        return list(cls.objects.filter(is_required=True).values_list('document_type', flat=True))
