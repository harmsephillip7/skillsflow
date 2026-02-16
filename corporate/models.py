"""
Corporate app models
Corporate clients, WSP, ATR, Employment Equity, BBBEE, and Grant management
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from core.models import AuditedModel, User
from tenants.models import TenantAwareModel


class CorporateClient(TenantAwareModel):
    """
    Corporate client (employer) for training services
    """
    STATUS_CHOICES = [
        ('PROSPECT', 'Prospect'),
        ('ACTIVE', 'Active'),
        ('ON_HOLD', 'On Hold'),
        ('INACTIVE', 'Inactive'),
    ]
    
    CLIENT_TIER_CHOICES = [
        ('STRATEGIC', 'Strategic'),
        ('KEY', 'Key Account'),
        ('STANDARD', 'Standard'),
        ('EMERGING', 'Emerging'),
    ]
    
    # Company Info
    company_name = models.CharField(max_length=200)
    trading_name = models.CharField(max_length=200, blank=True)
    registration_number = models.CharField(max_length=20, blank=True)
    vat_number = models.CharField(max_length=20, blank=True)
    
    # Contact
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    website = models.URLField(blank=True)
    
    # Physical Address
    physical_address = models.TextField()
    postal_address = models.TextField(blank=True)
    
    # Industry
    sic_code = models.CharField(max_length=10, blank=True)  # Standard Industry Code
    industry = models.CharField(max_length=100, blank=True)
    
    # SETA
    seta = models.ForeignKey(
        'learners.SETA',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='corporate_clients'
    )
    seta_number = models.CharField(max_length=50, blank=True)  # SDL Number
    
    # Size
    employee_count = models.PositiveIntegerField(null=True, blank=True)
    annual_revenue = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        null=True, blank=True
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROSPECT')
    
    # CRM Fields
    client_tier = models.CharField(max_length=20, choices=CLIENT_TIER_CHOICES, default='STANDARD')
    lead_source = models.ForeignKey(
        'LeadSource',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='clients'
    )
    first_contact_date = models.DateField(null=True, blank=True)
    conversion_date = models.DateField(null=True, blank=True, help_text='Date prospect became active client')
    
    # Health Score (1-100)
    health_score = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Client health score (1-100)'
    )
    health_score_updated = models.DateTimeField(null=True, blank=True)
    
    # Lifetime Value
    lifetime_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True, blank=True,
        help_text='Total revenue from this client'
    )
    
    # Account Manager
    account_manager = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_clients'
    )
    
    # Contract
    contract_start_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    
    # Workplace-Based Learning flags
    is_host_employer = models.BooleanField(
        default=False,
        help_text='This client can host learners for workplace-based learning'
    )
    is_lead_employer = models.BooleanField(
        default=False,
        help_text='This client is a lead employer overseeing placements at host employers'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['company_name']
        verbose_name = 'Corporate Client'
        verbose_name_plural = 'Corporate Clients'
    
    def __str__(self):
        return self.company_name
    
    @property
    def name(self):
        """Alias for company_name for template compatibility."""
        return self.company_name
    
    @property
    def is_active(self):
        """Returns True if status is ACTIVE."""
        return self.status == 'ACTIVE'
    
    @property
    def active_services_count(self):
        return self.service_subscriptions.filter(status='ACTIVE').count()
    
    @property
    def open_opportunities_count(self):
        return self.opportunities.exclude(stage__in=['CLOSED_WON', 'CLOSED_LOST']).count()
    
    @property
    def total_opportunity_value(self):
        from django.db.models import Sum
        return self.opportunities.exclude(stage__in=['CLOSED_WON', 'CLOSED_LOST']).aggregate(
            total=Sum('estimated_value')
        )['total'] or Decimal('0.00')
    
    def calculate_health_score(self):
        """Calculate health score based on engagement metrics."""
        from django.utils import timezone
        from datetime import timedelta
        
        score = 50  # Base score
        
        # Active services (+10 per service, max 30)
        active_services = self.active_services_count
        score += min(active_services * 10, 30)
        
        # Recent activity (+20 if activity in last 30 days)
        recent_activity = self.activities.filter(
            activity_date__gte=timezone.now() - timedelta(days=30)
        ).exists()
        if recent_activity:
            score += 20
        
        # Contract renewal (+10 if renewing soon)
        if self.contract_end_date:
            days_to_renewal = (self.contract_end_date - timezone.now().date()).days
            if 0 < days_to_renewal <= 90:
                score += 10
        
        # Cap at 100
        self.health_score = min(score, 100)
        self.health_score_updated = timezone.now()
        self.save(update_fields=['health_score', 'health_score_updated'])
        return self.health_score


class CorporateContact(AuditedModel):
    """
    Contacts at corporate clients
    """
    ROLE_CHOICES = [
        ('HR_MANAGER', 'HR Manager'),
        ('TRAINING_MANAGER', 'Training Manager'),
        ('SDF', 'Skills Development Facilitator'),
        ('FINANCE', 'Finance Contact'),
        ('EXEC', 'Executive'),
        ('OTHER', 'Other'),
    ]
    
    INFLUENCE_LEVEL_CHOICES = [
        ('DECISION_MAKER', 'Decision Maker'),
        ('INFLUENCER', 'Influencer'),
        ('CHAMPION', 'Champion'),
        ('BLOCKER', 'Blocker'),
        ('END_USER', 'End User'),
        ('UNKNOWN', 'Unknown'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='contacts'
    )
    
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    job_title = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    mobile = models.CharField(max_length=20, blank=True)
    
    # CRM Fields
    influence_level = models.CharField(
        max_length=20,
        choices=INFLUENCE_LEVEL_CHOICES,
        default='UNKNOWN'
    )
    engagement_score = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Engagement score (1-100)'
    )
    last_contacted = models.DateField(null=True, blank=True)
    linkedin_url = models.URLField(blank=True)
    preferred_contact_method = models.CharField(max_length=20, blank=True)
    birthday = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Link to user account for portal access
    user = models.OneToOneField(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='corporate_contact'
    )
    
    # Workplace-Based Learning permissions
    is_mentor = models.BooleanField(
        default=False,
        help_text='This contact can act as a mentor for learners'
    )
    can_submit_attendance = models.BooleanField(
        default=False,
        help_text='Can submit attendance on behalf of the organisation'
    )
    can_approve_logbooks = models.BooleanField(
        default=False,
        help_text='Can sign off on learner logbooks'
    )
    can_view_placements = models.BooleanField(
        default=False,
        help_text='Can view placement details and reports'
    )
    
    # Service deliverable permissions
    can_complete_deliverables = models.BooleanField(
        default=False,
        help_text='Can mark service deliverables/tasks as complete'
    )
    can_upload_evidence = models.BooleanField(
        default=False,
        help_text='Can upload evidence files for deliverables'
    )
    
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-is_primary', 'last_name']
        verbose_name = 'Corporate Contact'
        verbose_name_plural = 'Corporate Contacts'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.client.company_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class CorporateEmployee(AuditedModel):
    """
    Employees of corporate clients enrolled for training
    Links learners to corporate clients
    """
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='employees'
    )
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.CASCADE,
        related_name='corporate_links'
    )
    
    employee_number = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    ofo_code = models.CharField(max_length=20, blank=True)
    occupational_level = models.CharField(max_length=20, blank=True)
    employment_type = models.CharField(max_length=20, blank=True)
    
    # Employment dates at this company
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    is_current = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Corporate Employee'
        verbose_name_plural = 'Corporate Employees'
    
    def __str__(self):
        return f"{self.learner} - {self.client.company_name}"

    def get_full_name(self):
        return f"{self.learner.first_name} {self.learner.last_name}"

    def get_occupational_level_display(self):
        levels = {
            'TM': 'Top Management',
            'SM': 'Senior Management',
            'PM': 'Professional/Middle Management',
            'SS': 'Skilled/Supervisory',
            'SD': 'Semi-skilled/Discretionary',
            'US': 'Unskilled/Defined',
        }
        return levels.get(self.occupational_level, self.occupational_level)

    def get_employment_type_display(self):
        types = {
            'PERM': 'Permanent',
            'TEMP': 'Temporary',
            'CONT': 'Contract',
        }
        return types.get(self.employment_type, self.employment_type)


# =====================================================
# WSP/ATR MODELS
# =====================================================

class WSPYear(AuditedModel):
    """
    WSP/ATR reporting year
    """
    year = models.PositiveIntegerField(unique=True)
    submission_deadline = models.DateField()
    
    is_current = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-year']
        verbose_name = 'WSP Year'
        verbose_name_plural = 'WSP Years'
    
    def __str__(self):
        return f"WSP Year {self.year}/{self.year + 1} (May-Apr)"


class WSPSubmission(TenantAwareModel):
    """
    Workplace Skills Plan submission for a corporate client
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('IN_PROGRESS', 'In Progress'),
        ('REVIEW', 'Internal Review'),
        ('SUBMITTED', 'Submitted to SETA'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='wsp_submissions'
    )
    wsp_year = models.ForeignKey(
        WSPYear,
        on_delete=models.PROTECT,
        related_name='submissions'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # SETA Info
    seta_reference = models.CharField(max_length=50, blank=True)
    submitted_date = models.DateField(null=True, blank=True)
    accepted_date = models.DateField(null=True, blank=True)
    
    # Totals
    total_planned_training_spend = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_learners_planned = models.PositiveIntegerField(default=0)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-wsp_year__year']
        unique_together = ['client', 'wsp_year']
        verbose_name = 'WSP Submission'
        verbose_name_plural = 'WSP Submissions'
    
    def __str__(self):
        return f"{self.client.company_name} - WSP {self.wsp_year.year}"


class WSPPlannedTraining(models.Model):
    """
    Planned training interventions in WSP
    """
    INTERVENTION_TYPES = [
        ('LEARNERSHIP', 'Learnership'),
        ('SKILLS_PROG', 'Skills Programme'),
        ('INTERNSHIP', 'Internship'),
        ('BURSARY', 'Bursary'),
        ('SHORT_COURSE', 'Short Course'),
        ('ARTISAN', 'Artisan Development'),
        ('OTHER', 'Other'),
    ]
    
    wsp = models.ForeignKey(
        WSPSubmission,
        on_delete=models.CASCADE,
        related_name='planned_training'
    )
    
    intervention_type = models.CharField(max_length=20, choices=INTERVENTION_TYPES)
    
    qualification = models.ForeignKey(
        'academics.Qualification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='wsp_planned'
    )
    training_description = models.CharField(max_length=200)
    
    # Demographics
    african_male = models.PositiveIntegerField(default=0)
    african_female = models.PositiveIntegerField(default=0)
    coloured_male = models.PositiveIntegerField(default=0)
    coloured_female = models.PositiveIntegerField(default=0)
    indian_male = models.PositiveIntegerField(default=0)
    indian_female = models.PositiveIntegerField(default=0)
    white_male = models.PositiveIntegerField(default=0)
    white_female = models.PositiveIntegerField(default=0)
    
    # Disability
    disabled_male = models.PositiveIntegerField(default=0)
    disabled_female = models.PositiveIntegerField(default=0)
    
    # Cost
    estimated_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    class Meta:
        ordering = ['intervention_type']
        verbose_name = 'WSP Planned Training'
        verbose_name_plural = 'WSP Planned Training'
    
    def __str__(self):
        return f"{self.wsp} - {self.training_description}"
    
    @property
    def total_learners(self):
        return (
            self.african_male + self.african_female +
            self.coloured_male + self.coloured_female +
            self.indian_male + self.indian_female +
            self.white_male + self.white_female
        )


class ATRSubmission(TenantAwareModel):
    """
    Annual Training Report submission
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('IN_PROGRESS', 'In Progress'),
        ('REVIEW', 'Internal Review'),
        ('SUBMITTED', 'Submitted to SETA'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='atr_submissions'
    )
    # ATR reports on the previous WSP year
    reporting_year = models.ForeignKey(
        WSPYear,
        on_delete=models.PROTECT,
        related_name='atr_submissions'
    )
    
    # Link to WSP
    wsp = models.OneToOneField(
        WSPSubmission,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='atr'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # SETA Info
    seta_reference = models.CharField(max_length=50, blank=True)
    submitted_date = models.DateField(null=True, blank=True)
    accepted_date = models.DateField(null=True, blank=True)
    
    # Totals
    total_actual_spend = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_learners_trained = models.PositiveIntegerField(default=0)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-reporting_year__year']
        unique_together = ['client', 'reporting_year']
        verbose_name = 'ATR Submission'
        verbose_name_plural = 'ATR Submissions'
    
    def __str__(self):
        return f"{self.client.company_name} - ATR {self.reporting_year.year}"


class ATRCompletedTraining(models.Model):
    """
    Completed training reported in ATR
    """
    INTERVENTION_TYPES = [
        ('LEARNERSHIP', 'Learnership'),
        ('SKILLS_PROG', 'Skills Programme'),
        ('INTERNSHIP', 'Internship'),
        ('BURSARY', 'Bursary'),
        ('SHORT_COURSE', 'Short Course'),
        ('ARTISAN', 'Artisan Development'),
        ('OTHER', 'Other'),
    ]
    
    atr = models.ForeignKey(
        ATRSubmission,
        on_delete=models.CASCADE,
        related_name='completed_training'
    )
    
    intervention_type = models.CharField(max_length=20, choices=INTERVENTION_TYPES)
    
    qualification = models.ForeignKey(
        'academics.Qualification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='atr_completed'
    )
    training_description = models.CharField(max_length=200)
    
    # Demographics - completed
    african_male = models.PositiveIntegerField(default=0)
    african_female = models.PositiveIntegerField(default=0)
    coloured_male = models.PositiveIntegerField(default=0)
    coloured_female = models.PositiveIntegerField(default=0)
    indian_male = models.PositiveIntegerField(default=0)
    indian_female = models.PositiveIntegerField(default=0)
    white_male = models.PositiveIntegerField(default=0)
    white_female = models.PositiveIntegerField(default=0)
    
    # Disability
    disabled_male = models.PositiveIntegerField(default=0)
    disabled_female = models.PositiveIntegerField(default=0)
    
    # Cost
    actual_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    class Meta:
        ordering = ['intervention_type']
        verbose_name = 'ATR Completed Training'
        verbose_name_plural = 'ATR Completed Training'
    
    def __str__(self):
        return f"{self.atr} - {self.training_description}"
    
    @property
    def total_learners(self):
        return (
            self.african_male + self.african_female +
            self.coloured_male + self.coloured_female +
            self.indian_male + self.indian_female +
            self.white_male + self.white_female
        )


# =====================================================
# WSP/ATR EVIDENCE & PROJECT MANAGEMENT MODELS
# =====================================================

class WSPATREvidenceCategory(models.Model):
    """
    Categories of evidence required for WSP/ATR submissions
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    sequence = models.PositiveIntegerField(default=1)
    
    # Whether this is for WSP, ATR, or both
    APPLIES_TO_CHOICES = [
        ('WSP', 'WSP Only'),
        ('ATR', 'ATR Only'),
        ('BOTH', 'Both WSP and ATR'),
    ]
    applies_to = models.CharField(max_length=10, choices=APPLIES_TO_CHOICES, default='BOTH')
    
    is_mandatory = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['sequence', 'name']
        verbose_name = 'WSP/ATR Evidence Category'
        verbose_name_plural = 'WSP/ATR Evidence Categories'
    
    def __str__(self):
        return self.name


class WSPATRChecklist(TenantAwareModel):
    """
    Checklist of required items for a WSP/ATR submission
    """
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('PENDING_REVIEW', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    # Link to either WSP or ATR
    wsp = models.ForeignKey(
        WSPSubmission,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='checklist_items'
    )
    atr = models.ForeignKey(
        ATRSubmission,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='checklist_items'
    )
    
    category = models.ForeignKey(
        WSPATREvidenceCategory,
        on_delete=models.PROTECT,
        related_name='checklist_items'
    )
    
    # Item details
    item_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOT_STARTED')
    assigned_to = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='wsp_atr_checklist_assignments'
    )
    
    # Dates
    due_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    
    # Review
    reviewed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='wsp_atr_checklist_reviews'
    )
    review_date = models.DateField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['category__sequence', 'item_name']
        verbose_name = 'WSP/ATR Checklist Item'
        verbose_name_plural = 'WSP/ATR Checklist Items'
    
    def __str__(self):
        submission = self.wsp or self.atr
        return f"{submission} - {self.item_name}"


class WSPATREvidence(TenantAwareModel):
    """
    Evidence documents uploaded for WSP/ATR submissions
    """
    EVIDENCE_TYPE_CHOICES = [
        ('POP', 'Proof of Payment'),
        ('ATTENDANCE', 'Attendance Register'),
        ('CERTIFICATE', 'Certificate/Statement of Results'),
        ('POE', 'Portfolio of Evidence'),
        ('PAYROLL', 'Training Levy Payroll Record'),
        ('COMMITTEE_MINUTES', 'Training Committee Minutes'),
        ('IDP', 'Individual Development Plan'),
        ('EMPLOYEE_DB', 'Employee Database/List'),
        ('QUALIFICATION_PROOF', 'Qualification Proof'),
        ('COMPETENCY_CERT', 'Competency Certificate'),
        ('LOGBOOK', 'Logbook'),
        ('WORKPLACE_APPROVAL', 'Workplace Approval'),
        ('CONTRACT', 'Training Contract/Agreement'),
        ('OTHER', 'Other'),
    ]
    
    # Link to checklist item (optional) or directly to WSP/ATR
    checklist_item = models.ForeignKey(
        WSPATRChecklist,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='evidence_files'
    )
    wsp = models.ForeignKey(
        WSPSubmission,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='evidence_files'
    )
    atr = models.ForeignKey(
        ATRSubmission,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='evidence_files'
    )
    
    evidence_type = models.CharField(max_length=30, choices=EVIDENCE_TYPE_CHOICES)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # File
    file = models.FileField(upload_to='wsp_atr_evidence/')
    file_size = models.PositiveIntegerField(default=0)
    
    # Reference (e.g., invoice number, certificate number)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Date the evidence relates to
    evidence_date = models.DateField(null=True, blank=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_wsp_atr_evidence'
    )
    verified_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'WSP/ATR Evidence'
        verbose_name_plural = 'WSP/ATR Evidence'
    
    def __str__(self):
        return f"{self.get_evidence_type_display()} - {self.name}"
    
    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)


class EmployeeQualification(TenantAwareModel):
    """
    Qualifications held by corporate employees - for employee database uploads
    """
    QUALIFICATION_TYPE_CHOICES = [
        ('MATRIC', 'Matric/Grade 12'),
        ('CERTIFICATE', 'Certificate'),
        ('HIGHER_CERT', 'Higher Certificate'),
        ('DIPLOMA', 'Diploma'),
        ('ADVANCED_DIP', 'Advanced Diploma'),
        ('BACHELORS', 'Bachelor\'s Degree'),
        ('HONOURS', 'Honours Degree'),
        ('MASTERS', 'Master\'s Degree'),
        ('DOCTORATE', 'Doctorate'),
        ('TRADE_CERT', 'Trade Certificate'),
        ('LEARNERSHIP', 'Learnership'),
        ('SKILLS_PROG', 'Skills Programme'),
        ('SHORT_COURSE', 'Short Course'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('VERIFIED', 'Verified'),
        ('PENDING', 'Pending Verification'),
        ('UNVERIFIED', 'Unverified'),
    ]
    
    employee = models.ForeignKey(
        CorporateEmployee,
        on_delete=models.CASCADE,
        related_name='qualifications'
    )
    
    qualification_type = models.CharField(max_length=20, choices=QUALIFICATION_TYPE_CHOICES)
    qualification_name = models.CharField(max_length=200)
    
    # SAQA/NQF
    saqa_id = models.CharField(max_length=20, blank=True, verbose_name='SAQA ID')
    nqf_level = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name='NQF Level'
    )
    credits = models.PositiveIntegerField(null=True, blank=True)
    
    # Institution
    institution = models.CharField(max_length=200, blank=True)
    
    # Dates
    date_obtained = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, help_text='For certifications that expire')
    
    # Verification
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNVERIFIED')
    verification_date = models.DateField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_employee_qualifications'
    )
    
    # Evidence
    certificate_file = models.FileField(upload_to='employee_qualifications/', blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-date_obtained']
        verbose_name = 'Employee Qualification'
        verbose_name_plural = 'Employee Qualifications'
    
    def __str__(self):
        return f"{self.employee} - {self.qualification_name}"
    
    @property
    def is_expired(self):
        if self.expiry_date:
            from django.utils import timezone
            return self.expiry_date < timezone.now().date()
        return False


class MeetingAgendaItem(models.Model):
    """
    Agenda items for committee meetings
    """
    meeting = models.ForeignKey(
        'CommitteeMeeting',
        on_delete=models.CASCADE,
        related_name='agenda_items'
    )
    
    sequence = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    presenter = models.ForeignKey(
        'CommitteeMember',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='agenda_presentations'
    )
    
    # Time allocation
    duration_minutes = models.PositiveIntegerField(default=15)
    
    # Documents for this item
    documents = models.TextField(blank=True, help_text='Reference documents for this agenda item')
    
    class Meta:
        ordering = ['sequence']
        verbose_name = 'Meeting Agenda Item'
        verbose_name_plural = 'Meeting Agenda Items'
    
    def __str__(self):
        return f"{self.meeting} - {self.title}"


class MeetingActionItem(TenantAwareModel):
    """
    Action items arising from committee meetings
    """
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('DEFERRED', 'Deferred'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]
    
    meeting = models.ForeignKey(
        'CommitteeMeeting',
        on_delete=models.CASCADE,
        related_name='action_items'
    )
    
    # Action details
    action_number = models.CharField(max_length=20, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Assignment
    assigned_to = models.ForeignKey(
        'CommitteeMember',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_actions'
    )
    assigned_to_user = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='committee_action_items'
    )
    
    # Dates
    due_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Progress
    progress_notes = models.TextField(blank=True)
    
    # Follow-up meeting
    follow_up_meeting = models.ForeignKey(
        'CommitteeMeeting',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='followed_up_actions'
    )
    
    class Meta:
        ordering = ['due_date', '-priority']
        verbose_name = 'Meeting Action Item'
        verbose_name_plural = 'Meeting Action Items'
    
    def __str__(self):
        return f"{self.meeting.committee} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.action_number:
            # Generate action number
            count = MeetingActionItem.objects.filter(
                meeting__committee=self.meeting.committee
            ).count() + 1
            self.action_number = f"ACT-{self.meeting.committee.id}-{count:04d}"
        super().save(*args, **kwargs)


class AnnualServiceDelivery(TenantAwareModel):
    """
    Annual service delivery tracking for WSP/ATR cycle
    """
    STATUS_CHOICES = [
        ('PLANNING', 'Planning'),
        ('IN_PROGRESS', 'In Progress'),
        ('ON_TRACK', 'On Track'),
        ('AT_RISK', 'At Risk'),
        ('DELAYED', 'Delayed'),
        ('COMPLETED', 'Completed'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='annual_service_deliveries'
    )
    wsp_year = models.ForeignKey(
        WSPYear,
        on_delete=models.PROTECT,
        related_name='service_deliveries'
    )
    
    # Link to WSP and ATR
    wsp = models.OneToOneField(
        WSPSubmission,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='service_delivery'
    )
    atr = models.OneToOneField(
        ATRSubmission,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='service_delivery'
    )
    
    # Overall status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNING')
    
    # Progress
    overall_progress = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Overall progress percentage'
    )
    
    # Key dates
    year_start = models.DateField()
    year_end = models.DateField()
    wsp_deadline = models.DateField(null=True, blank=True)
    atr_deadline = models.DateField(null=True, blank=True)
    
    # Budget tracking
    planned_budget = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    actual_spend = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Notes
    executive_summary = models.TextField(blank=True)
    risks_and_issues = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-wsp_year__year']
        unique_together = ['client', 'wsp_year']
        verbose_name = 'Annual Service Delivery'
        verbose_name_plural = 'Annual Service Deliveries'
    
    def __str__(self):
        return f"{self.client.company_name} - {self.wsp_year}"
    
    @property
    def budget_variance(self):
        return self.planned_budget - self.actual_spend
    
    @property
    def budget_utilization(self):
        if self.planned_budget > 0:
            return (self.actual_spend / self.planned_budget) * 100
        return 0


class ServiceDeliveryActivity(TenantAwareModel):
    """
    Individual activities within annual service delivery
    """
    ACTIVITY_TYPE_CHOICES = [
        ('EVIDENCE_COLLECTION', 'Evidence Collection'),
        ('POP_TRAINING', 'Proof of Payment - Training'),
        ('LEARNER_EVIDENCE', 'Learner Evidence'),
        ('EMPLOYEE_DB', 'Employee Database Update'),
        ('COMMITTEE_MEETING', 'Training Committee Meeting'),
        ('IDP_REVIEW', 'IDP Review'),
        ('TRAINING_DELIVERY', 'Training Delivery'),
        ('ASSESSMENT', 'Assessment'),
        ('CERTIFICATION', 'Certification'),
        ('WSP_PREP', 'WSP Preparation'),
        ('ATR_PREP', 'ATR Preparation'),
        ('SETA_SUBMISSION', 'SETA Submission'),
        ('AUDIT', 'Audit/Verification'),
        ('REPORT', 'Reporting'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('DELAYED', 'Delayed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]
    
    service_delivery = models.ForeignKey(
        AnnualServiceDelivery,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    
    # Activity details
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPE_CHOICES)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Schedule
    planned_start = models.DateField()
    planned_end = models.DateField()
    actual_start = models.DateField(null=True, blank=True)
    actual_end = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Progress
    progress = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='service_delivery_activities'
    )
    
    # Dependencies (other activities that must complete first)
    dependencies = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='dependents'
    )
    
    # Evidence requirement
    requires_evidence = models.BooleanField(default=False)
    evidence_description = models.TextField(blank=True)
    
    # Link to committee meeting (if activity type is committee meeting)
    committee_meeting = models.ForeignKey(
        'CommitteeMeeting',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='service_delivery_activities'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['planned_start', 'priority']
        verbose_name = 'Service Delivery Activity'
        verbose_name_plural = 'Service Delivery Activities'
    
    def __str__(self):
        return f"{self.service_delivery} - {self.name}"
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.status not in ['COMPLETED', 'CANCELLED']:
            return timezone.now().date() > self.planned_end
        return False
    
    @property
    def days_remaining(self):
        from django.utils import timezone
        if self.status not in ['COMPLETED', 'CANCELLED']:
            return (self.planned_end - timezone.now().date()).days
        return 0


class ServiceDeliveryEvidence(TenantAwareModel):
    """
    Evidence files uploaded for service delivery activities
    """
    activity = models.ForeignKey(
        ServiceDeliveryActivity,
        on_delete=models.CASCADE,
        related_name='evidence_files'
    )
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='service_delivery_evidence/')
    file_size = models.PositiveIntegerField(default=0)
    
    # Upload info
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_service_delivery_evidence'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Service Delivery Evidence'
        verbose_name_plural = 'Service Delivery Evidence'
    
    def __str__(self):
        return f"{self.activity} - {self.name}"
    
    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)


class EmployeeDatabaseUpload(TenantAwareModel):
    """
    Track employee database uploads for WSP/ATR
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Processing'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('PARTIALLY_COMPLETED', 'Partially Completed'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='employee_db_uploads'
    )
    wsp_year = models.ForeignKey(
        WSPYear,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='employee_db_uploads'
    )
    
    # File
    file = models.FileField(upload_to='employee_db_uploads/')
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    
    # Processing status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    
    # Results
    total_rows = models.PositiveIntegerField(default=0)
    successful_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    
    # New vs updated
    new_employees = models.PositiveIntegerField(default=0)
    updated_employees = models.PositiveIntegerField(default=0)
    new_qualifications = models.PositiveIntegerField(default=0)
    
    # Error log
    error_log = models.TextField(blank=True)
    
    # Processing timestamps
    processed_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Employee Database Upload'
        verbose_name_plural = 'Employee Database Uploads'
    
    def __str__(self):
        return f"{self.client.company_name} - {self.original_filename}"


# =====================================================
# SHARED EMPLOYEE SNAPSHOT MODELS
# =====================================================

class ClientEmployeeSnapshot(TenantAwareModel):
    """
    Unified employee demographic snapshot that can be used by both WSP/ATR and EE modules.
    This is the single source of truth for employee headcount data at a point in time.
    """
    SNAPSHOT_TYPE_CHOICES = [
        ('MONTHLY', 'Monthly Snapshot'),
        ('QUARTERLY', 'Quarterly Snapshot'),
        ('ANNUAL', 'Annual Snapshot'),
        ('WSP_ATR', 'WSP/ATR Reporting'),
        ('EE_REPORT', 'EE Reporting'),
        ('MANUAL', 'Manual Entry'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='employee_snapshots'
    )
    
    snapshot_date = models.DateField(help_text='Date this snapshot represents')
    snapshot_type = models.CharField(max_length=20, choices=SNAPSHOT_TYPE_CHOICES, default='MANUAL')
    
    # Source tracking
    source_description = models.CharField(max_length=200, blank=True, help_text='e.g., "Payroll export Jan 2026"')
    imported_from_file = models.FileField(upload_to='employee_snapshots/', null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_employee_snapshots'
    )
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_employee_snapshots'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-snapshot_date']
        verbose_name = 'Employee Snapshot'
        verbose_name_plural = 'Employee Snapshots'
        unique_together = ['client', 'snapshot_date', 'snapshot_type']
    
    def __str__(self):
        return f"{self.client.company_name} - {self.snapshot_date} ({self.get_snapshot_type_display()})"
    
    @property
    def total_employees(self):
        return sum(row.total for row in self.occupational_data.all())
    
    def get_occupational_data(self, level):
        """Get data for a specific occupational level."""
        return self.occupational_data.filter(occupational_level=level).first()


class OccupationalLevelData(models.Model):
    """
    Employee counts by occupational level and demographics.
    Used by both WSP/ATR and EE modules via ClientEmployeeSnapshot.
    """
    OCCUPATIONAL_LEVEL_CHOICES = [
        ('TOP_MANAGEMENT', 'Top Management'),
        ('SENIOR_MANAGEMENT', 'Senior Management'),
        ('PROFESSIONAL', 'Professionally Qualified and Experienced Specialists and Mid-Management'),
        ('SKILLED_TECHNICAL', 'Skilled Technical and Academically Qualified Workers, Junior Management, Supervisors, Foremen and Superintendents'),
        ('SEMI_SKILLED', 'Semi-Skilled and Discretionary Decision Making'),
        ('UNSKILLED', 'Unskilled and Defined Decision Making'),
        ('NON_PERMANENT', 'Non-Permanent/Temporary Employees'),
    ]
    
    snapshot = models.ForeignKey(
        ClientEmployeeSnapshot,
        on_delete=models.CASCADE,
        related_name='occupational_data'
    )
    
    occupational_level = models.CharField(max_length=30, choices=OCCUPATIONAL_LEVEL_CHOICES)
    
    # Male by race
    african_male = models.PositiveIntegerField(default=0)
    coloured_male = models.PositiveIntegerField(default=0)
    indian_male = models.PositiveIntegerField(default=0)
    white_male = models.PositiveIntegerField(default=0)
    foreign_national_male = models.PositiveIntegerField(default=0)
    
    # Female by race
    african_female = models.PositiveIntegerField(default=0)
    coloured_female = models.PositiveIntegerField(default=0)
    indian_female = models.PositiveIntegerField(default=0)
    white_female = models.PositiveIntegerField(default=0)
    foreign_national_female = models.PositiveIntegerField(default=0)
    
    # Disability counts (included in race counts above)
    disabled_male = models.PositiveIntegerField(default=0)
    disabled_female = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['occupational_level']
        unique_together = ['snapshot', 'occupational_level']
        verbose_name = 'Occupational Level Data'
        verbose_name_plural = 'Occupational Level Data'
    
    def __str__(self):
        return f"{self.snapshot} - {self.get_occupational_level_display()}"
    
    @property
    def total_male(self):
        return (
            self.african_male + self.coloured_male + 
            self.indian_male + self.white_male + self.foreign_national_male
        )
    
    @property
    def total_female(self):
        return (
            self.african_female + self.coloured_female + 
            self.indian_female + self.white_female + self.foreign_national_female
        )
    
    @property
    def total(self):
        return self.total_male + self.total_female
    
    @property
    def total_african(self):
        return self.african_male + self.african_female
    
    @property
    def total_coloured(self):
        return self.coloured_male + self.coloured_female
    
    @property
    def total_indian(self):
        return self.indian_male + self.indian_female
    
    @property
    def total_white(self):
        return self.white_male + self.white_female
    
    @property
    def total_foreign(self):
        return self.foreign_national_male + self.foreign_national_female
    
    @property
    def total_disabled(self):
        return self.disabled_male + self.disabled_female


# =====================================================
# EMPLOYMENT EQUITY MODELS
# =====================================================

class EEServiceYear(TenantAwareModel):
    """
    Employment Equity service year - tracks EE work for a specific reporting year.
    Similar to WSPATRServiceYear but for EE compliance.
    
    EE Reporting Period: 1 October to 30 September (different from WSP/ATR which is May-April)
    Submission Deadline: 15 January (online)
    """
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('ANALYSIS', 'Workforce Analysis'),
        ('PLAN_DEVELOPMENT', 'Plan Development'),
        ('DATA_COLLECTION', 'Data Collection'),
        ('CONSULTATION', 'Committee Consultation'),
        ('DRAFTING', 'Report Drafting'),
        ('INTERNAL_REVIEW', 'Internal Review'),
        ('CLIENT_REVIEW', 'Client Review'),
        ('SUBMITTED', 'Submitted to DEL'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected - Resubmission Required'),
        ('COMPLETED', 'Completed'),
    ]
    
    OUTCOME_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLIANT', 'Compliant'),
        ('NON_COMPLIANT', 'Non-Compliant'),
        ('APPROVED', 'Approved'),
        ('APPROVED_CONDITIONS', 'Approved with Conditions'),
        ('REJECTED', 'Rejected'),
        ('NOT_SUBMITTED', 'Not Submitted'),
    ]
    
    subscription = models.ForeignKey(
        'ClientServiceSubscription',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ee_service_years'
    )
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='ee_service_years'
    )
    
    # EE Year follows Oct-Sep cycle. reporting_year=2026 means Oct 2025 - Sep 2026
    reporting_year = models.PositiveIntegerField(
        help_text='The year ending the reporting period (e.g., 2026 for Oct 2025 - Sep 2026)'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOT_STARTED')
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, default='PENDING')
    
    # Key dates
    submission_deadline = models.DateField(null=True, blank=True, help_text='Usually 15 January')
    submitted_date = models.DateField(null=True, blank=True)
    outcome_date = models.DateField(null=True, blank=True)
    
    # DEL reference
    del_reference_number = models.CharField(max_length=100, blank=True, help_text='Department of Employment and Labour reference')
    ee_certificate_number = models.CharField(max_length=100, blank=True)
    del_feedback = models.TextField(blank=True)
    
    # Assignment
    assigned_consultant = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_ee_years'
    )
    
    # Link to employee snapshot used for this report
    employee_snapshot = models.ForeignKey(
        ClientEmployeeSnapshot,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='ee_service_years'
    )
    
    # Link to EE Plan
    ee_plan = models.ForeignKey(
        'EEPlan',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='service_years'
    )
    
    # Progress tracking
    progress_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-reporting_year']
        unique_together = ['client', 'reporting_year']
        verbose_name = 'EE Service Year'
        verbose_name_plural = 'EE Service Years'
    
    def save(self, *args, **kwargs):
        # Auto-calculate submission deadline if not provided (15 January following year)
        if not self.submission_deadline and self.reporting_year:
            from datetime import date
            self.submission_deadline = date(self.reporting_year + 1, 1, 15)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.client.company_name} - EE {self.reporting_year}"
    
    @property
    def period_display(self):
        """Display the reporting period."""
        return f"Oct {self.reporting_year - 1} - Sep {self.reporting_year}"
    
    @property
    def reporting_period_start(self):
        from datetime import date
        return date(self.reporting_year - 1, 10, 1)
    
    @property
    def reporting_period_end(self):
        from datetime import date
        return date(self.reporting_year, 9, 30)
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.submitted_date:
            return False
        if self.submission_deadline:
            return timezone.now().date() > self.submission_deadline
        return False
    
    @property
    def days_until_deadline(self):
        from django.utils import timezone
        if self.submitted_date:
            return None
        if self.submission_deadline:
            delta = self.submission_deadline - timezone.now().date()
            return delta.days
        return None


class EEPlan(TenantAwareModel):
    """
    Employment Equity Plan - typically 1-5 years.
    Required under the EEA before submission of EEA2/EEA4.
    """
    PLAN_DURATION_CHOICES = [
        (1, '1 Year'),
        (2, '2 Years'),
        (3, '3 Years'),
        (4, '4 Years'),
        (5, '5 Years'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('CONSULTATION', 'Under Consultation'),
        ('APPROVED', 'Approved'),
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('SUPERSEDED', 'Superseded'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='ee_plans'
    )
    
    plan_name = models.CharField(max_length=200, default='Employment Equity Plan')
    
    duration_years = models.PositiveIntegerField(choices=PLAN_DURATION_CHOICES, default=3)
    start_date = models.DateField()
    end_date = models.DateField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # CEO/MD approval
    approved_by_name = models.CharField(max_length=200, blank=True)
    approved_by_designation = models.CharField(max_length=200, blank=True)
    approval_date = models.DateField(null=True, blank=True)
    
    # Plan document
    plan_document = models.FileField(
        upload_to='ee_plans/',
        null=True, blank=True,
        help_text='Signed EE Plan document'
    )
    
    # Consultation record
    consultation_completed = models.BooleanField(default=False)
    consultation_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'EE Plan'
        verbose_name_plural = 'EE Plans'
    
    def __str__(self):
        return f"{self.client.company_name} - {self.plan_name} ({self.start_date.year}-{self.end_date.year})"
    
    @property
    def is_active(self):
        from django.utils import timezone
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date and self.status == 'ACTIVE'
    
    @property
    def years_remaining(self):
        from django.utils import timezone
        today = timezone.now().date()
        if today > self.end_date:
            return 0
        delta = self.end_date - today
        return round(delta.days / 365, 1)


class EEAnalysis(TenantAwareModel):
    """
    Employment Equity Analysis - required before developing the EE Plan.
    Identifies barriers to transformation and underrepresentation.
    """
    service_year = models.OneToOneField(
        EEServiceYear,
        on_delete=models.CASCADE,
        related_name='analysis'
    )
    
    # Analysis dates
    analysis_start_date = models.DateField(null=True, blank=True)
    analysis_completion_date = models.DateField(null=True, blank=True)
    
    # Workforce analysis done
    workforce_analysis_complete = models.BooleanField(default=False)
    
    # Policy review
    policies_reviewed = models.JSONField(
        default=list,
        blank=True,
        help_text='List of policies reviewed: recruitment, promotion, training, etc.'
    )
    
    # Barriers identified
    barriers_identified = models.JSONField(
        default=list,
        blank=True,
        help_text='List of barriers to employment equity'
    )
    
    # Affirmative action measures proposed
    affirmative_measures = models.JSONField(
        default=list,
        blank=True,
        help_text='Proposed affirmative action measures'
    )
    
    # Analysis report document
    analysis_document = models.FileField(
        upload_to='ee_analysis/',
        null=True, blank=True
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'EE Analysis'
        verbose_name_plural = 'EE Analyses'
    
    def __str__(self):
        return f"{self.service_year.client.company_name} - EE Analysis {self.service_year.reporting_year}"


class EEBarrier(TenantAwareModel):
    """
    Identified barrier to employment equity.
    """
    CATEGORY_CHOICES = [
        ('RECRUITMENT', 'Recruitment & Selection'),
        ('APPOINTMENTS', 'Appointments'),
        ('PROMOTIONS', 'Promotions & Advancement'),
        ('TRAINING', 'Training & Development'),
        ('REMUNERATION', 'Remuneration & Benefits'),
        ('WORKING_CONDITIONS', 'Working Conditions'),
        ('CULTURE', 'Organizational Culture'),
        ('RETENTION', 'Retention'),
        ('PHYSICAL', 'Physical Accessibility'),
        ('POLICY', 'Policy & Procedures'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('IDENTIFIED', 'Identified'),
        ('IN_PROGRESS', 'Being Addressed'),
        ('ADDRESSED', 'Addressed'),
        ('MONITORING', 'Monitoring'),
    ]
    
    service_year = models.ForeignKey(
        EEServiceYear,
        on_delete=models.CASCADE,
        related_name='barriers'
    )
    
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    description = models.TextField()
    
    # Affected groups
    affects_african = models.BooleanField(default=False)
    affects_coloured = models.BooleanField(default=False)
    affects_indian = models.BooleanField(default=False)
    affects_women = models.BooleanField(default=False)
    affects_disabled = models.BooleanField(default=False)
    
    # Proposed measure to address
    proposed_measure = models.TextField(blank=True)
    responsible_person = models.CharField(max_length=200, blank=True)
    target_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IDENTIFIED')
    addressed_date = models.DateField(null=True, blank=True)
    outcome_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['category']
        verbose_name = 'EE Barrier'
        verbose_name_plural = 'EE Barriers'
    
    def __str__(self):
        return f"{self.service_year} - {self.get_category_display()}"
    
    @property
    def affected_groups_display(self):
        groups = []
        if self.affects_african:
            groups.append('African')
        if self.affects_coloured:
            groups.append('Coloured')
        if self.affects_indian:
            groups.append('Indian')
        if self.affects_women:
            groups.append('Women')
        if self.affects_disabled:
            groups.append('People with Disabilities')
        return ', '.join(groups) if groups else 'Not specified'


class EENumericalGoal(TenantAwareModel):
    """
    Numerical goals/targets for EE transformation.
    Part of the EE Plan and tracked in annual reporting.
    """
    ee_plan = models.ForeignKey(
        EEPlan,
        on_delete=models.CASCADE,
        related_name='numerical_goals'
    )
    
    OCCUPATIONAL_LEVEL_CHOICES = [
        ('TOP_MANAGEMENT', 'Top Management'),
        ('SENIOR_MANAGEMENT', 'Senior Management'),
        ('PROFESSIONAL', 'Professionally Qualified'),
        ('SKILLED_TECHNICAL', 'Skilled Technical'),
        ('SEMI_SKILLED', 'Semi-Skilled'),
        ('UNSKILLED', 'Unskilled'),
    ]
    
    occupational_level = models.CharField(max_length=30, choices=OCCUPATIONAL_LEVEL_CHOICES)
    target_year = models.PositiveIntegerField(help_text='Year this target should be achieved')
    
    # Targets by demographic
    african_male_target = models.PositiveIntegerField(default=0)
    african_female_target = models.PositiveIntegerField(default=0)
    coloured_male_target = models.PositiveIntegerField(default=0)
    coloured_female_target = models.PositiveIntegerField(default=0)
    indian_male_target = models.PositiveIntegerField(default=0)
    indian_female_target = models.PositiveIntegerField(default=0)
    white_male_target = models.PositiveIntegerField(default=0)
    white_female_target = models.PositiveIntegerField(default=0)
    disabled_target = models.PositiveIntegerField(default=0)
    
    # Actual (updated from service year data)
    actual_african_male = models.PositiveIntegerField(default=0)
    actual_african_female = models.PositiveIntegerField(default=0)
    actual_coloured_male = models.PositiveIntegerField(default=0)
    actual_coloured_female = models.PositiveIntegerField(default=0)
    actual_indian_male = models.PositiveIntegerField(default=0)
    actual_indian_female = models.PositiveIntegerField(default=0)
    actual_white_male = models.PositiveIntegerField(default=0)
    actual_white_female = models.PositiveIntegerField(default=0)
    actual_disabled = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['target_year', 'occupational_level']
        unique_together = ['ee_plan', 'occupational_level', 'target_year']
        verbose_name = 'EE Numerical Goal'
        verbose_name_plural = 'EE Numerical Goals'
    
    def __str__(self):
        return f"{self.ee_plan.client.company_name} - {self.get_occupational_level_display()} Target {self.target_year}"
    
    @property
    def total_target(self):
        return (
            self.african_male_target + self.african_female_target +
            self.coloured_male_target + self.coloured_female_target +
            self.indian_male_target + self.indian_female_target +
            self.white_male_target + self.white_female_target
        )
    
    @property
    def total_actual(self):
        return (
            self.actual_african_male + self.actual_african_female +
            self.actual_coloured_male + self.actual_coloured_female +
            self.actual_indian_male + self.actual_indian_female +
            self.actual_white_male + self.actual_white_female
        )


class EEIncomeDifferential(TenantAwareModel):
    """
    Income differential data for EEA2/EEA4 reporting.
    Required to report salary gaps by occupational level and demographics.
    """
    service_year = models.ForeignKey(
        EEServiceYear,
        on_delete=models.CASCADE,
        related_name='income_differentials'
    )
    
    OCCUPATIONAL_LEVEL_CHOICES = [
        ('TOP_MANAGEMENT', 'Top Management'),
        ('SENIOR_MANAGEMENT', 'Senior Management'),
        ('PROFESSIONAL', 'Professionally Qualified'),
        ('SKILLED_TECHNICAL', 'Skilled Technical'),
        ('SEMI_SKILLED', 'Semi-Skilled'),
        ('UNSKILLED', 'Unskilled'),
    ]
    
    occupational_level = models.CharField(max_length=30, choices=OCCUPATIONAL_LEVEL_CHOICES)
    
    # Salary averages by demographic
    african_male_avg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    african_female_avg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    coloured_male_avg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    coloured_female_avg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    indian_male_avg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    indian_female_avg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    white_male_avg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    white_female_avg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['occupational_level']
        unique_together = ['service_year', 'occupational_level']
        verbose_name = 'EE Income Differential'
        verbose_name_plural = 'EE Income Differentials'
    
    def __str__(self):
        return f"{self.service_year} - {self.get_occupational_level_display()} Income"


class EEDocument(TenantAwareModel):
    """
    Document management for Employment Equity.
    """
    DOCUMENT_TYPE_CHOICES = [
        # Required for submission
        ('EE_PLAN', 'Employment Equity Plan (EEA13)'),
        ('EE_POLICY', 'Employment Equity Policy'),
        ('EEA2_REPORT', 'EEA2 - Workforce Profile'),
        ('EEA4_REPORT', 'EEA4 - Employment Equity Report'),
        ('EEA12_FORM', 'EEA12 - Employer Details'),
        ('ANALYSIS_REPORT', 'Workforce Analysis Report'),
        ('BARRIERS_ANALYSIS', 'Barriers Analysis Document'),
        ('COMMITTEE_CONSTITUTION', 'EE Committee Constitution'),
        ('COMMITTEE_MINUTES', 'EE Committee Meeting Minutes'),
        ('COMMITTEE_ATTENDANCE', 'EE Committee Attendance Register'),
        ('CONSULTATION_RECORD', 'Consultation Records'),
        ('AFFIRMATIVE_MEASURES', 'Affirmative Action Measures'),
        # Company documents
        ('COMPANY_REGISTRATION', 'Company Registration (CIPC)'),
        ('ORGANOGRAM', 'Company Organogram'),
        # Output documents
        ('EE_CERTIFICATE', 'EE Compliance Certificate'),
        ('DEL_CONFIRMATION', 'DEL Submission Confirmation'),
        ('COMPLIANCE_LETTER', 'Compliance Letter'),
        ('DG_ORDER', 'Director General Review/Order'),
        ('DG_QUERY_LETTER', 'Director-General Query Letter'),
        ('OTHER', 'Other Document'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Upload'),
        ('UPLOADED', 'Uploaded'),
        ('APPROVED', 'Approved/Verified'),
        ('REJECTED', 'Rejected - Reupload Required'),
        ('NOT_APPLICABLE', 'Not Applicable'),
    ]
    
    service_year = models.ForeignKey(
        EEServiceYear,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    # Link to meeting if meeting-specific document
    meeting = models.ForeignKey(
        'TrainingCommitteeMeeting',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='ee_documents'
    )
    
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    name = models.CharField(max_length=200, blank=True, help_text='Custom name if needed')
    description = models.TextField(blank=True)
    
    # File
    file = models.FileField(upload_to='ee_documents/%Y/%m/', null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    # Metadata
    uploaded_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='uploaded_ee_documents'
    )
    
    is_required = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Review
    reviewed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_ee_documents'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Display order
    sort_order = models.PositiveIntegerField(default=0)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['sort_order', 'document_type']
        verbose_name = 'EE Document'
        verbose_name_plural = 'EE Documents'
    
    def __str__(self):
        name = self.name or self.get_document_type_display()
        return f"{self.service_year} - {name}"
    
    @property
    def display_name(self):
        return self.name or self.get_document_type_display()
    
    @property
    def is_uploaded(self):
        return bool(self.file)
    
    def save(self, *args, **kwargs):
        if self.file:
            if not self.file_name:
                self.file_name = self.file.name.split('/')[-1]
            if not self.file_size:
                try:
                    self.file_size = self.file.size
                except:
                    pass
            if not self.uploaded_at:
                from django.utils import timezone
                self.uploaded_at = timezone.now()
            if self.status == 'PENDING':
                self.status = 'UPLOADED'
        super().save(*args, **kwargs)


# Legacy EEReport model (kept for backwards compatibility)
class EEReport(TenantAwareModel):
    """
    Employment Equity Report
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('IN_PROGRESS', 'In Progress'),
        ('REVIEW', 'Internal Review'),
        ('SUBMITTED', 'Submitted'),
        ('ACCEPTED', 'Accepted'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='ee_reports'
    )
    
    reporting_period_start = models.DateField()
    reporting_period_end = models.DateField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    submitted_date = models.DateField(null=True, blank=True)
    reference_number = models.CharField(max_length=50, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-reporting_period_end']
        verbose_name = 'EE Report'
        verbose_name_plural = 'EE Reports'
    
    def __str__(self):
        return f"{self.client.company_name} - EE {self.reporting_period_end.year}"


class EEWorkforceProfile(models.Model):
    """
    Workforce profile data for EE report
    """
    OCCUPATIONAL_LEVELS = [
        ('TOP_MGMT', 'Top Management'),
        ('SENIOR_MGMT', 'Senior Management'),
        ('PROF_QUALIFIED', 'Professionally Qualified'),
        ('SKILLED_TECH', 'Skilled Technical'),
        ('SEMI_SKILLED', 'Semi-Skilled'),
        ('UNSKILLED', 'Unskilled'),
        ('TOTAL_PERM', 'Total Permanent'),
        ('TEMP', 'Temporary'),
    ]
    
    ee_report = models.ForeignKey(
        EEReport,
        on_delete=models.CASCADE,
        related_name='workforce_profiles'
    )
    
    occupational_level = models.CharField(max_length=20, choices=OCCUPATIONAL_LEVELS)
    
    # Male
    african_male = models.PositiveIntegerField(default=0)
    coloured_male = models.PositiveIntegerField(default=0)
    indian_male = models.PositiveIntegerField(default=0)
    white_male = models.PositiveIntegerField(default=0)
    foreign_male = models.PositiveIntegerField(default=0)
    
    # Female
    african_female = models.PositiveIntegerField(default=0)
    coloured_female = models.PositiveIntegerField(default=0)
    indian_female = models.PositiveIntegerField(default=0)
    white_female = models.PositiveIntegerField(default=0)
    foreign_female = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['occupational_level']
        unique_together = ['ee_report', 'occupational_level']
        verbose_name = 'EE Workforce Profile'
        verbose_name_plural = 'EE Workforce Profiles'
    
    def __str__(self):
        return f"{self.ee_report} - {self.occupational_level}"
    
    @property
    def total_male(self):
        return (
            self.african_male + self.coloured_male +
            self.indian_male + self.white_male + self.foreign_male
        )
    
    @property
    def total_female(self):
        return (
            self.african_female + self.coloured_female +
            self.indian_female + self.white_female + self.foreign_female
        )
    
    @property
    def total(self):
        return self.total_male + self.total_female


# =====================================================
# BBBEE MODELS
# =====================================================

class BBBEEScorecard(TenantAwareModel):
    """
    BBBEE Scorecard tracking
    """
    LEVEL_CHOICES = [(i, f"Level {i}") for i in range(1, 9)]
    LEVEL_CHOICES.append((0, 'Non-Compliant'))
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='bbbee_scorecards'
    )
    
    # Certificate
    verification_date = models.DateField()
    expiry_date = models.DateField()
    verification_agency = models.CharField(max_length=200)
    certificate_number = models.CharField(max_length=50, blank=True)
    
    # Level
    bbbee_level = models.PositiveIntegerField(choices=LEVEL_CHOICES)
    
    # Element scores
    ownership_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    management_control_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    skills_development_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    enterprise_supplier_dev_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    socio_economic_dev_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    
    total_score = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0.00')
    )
    
    # Certificate document
    certificate = models.FileField(
        upload_to='bbbee_certificates/',
        blank=True
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-verification_date']
        verbose_name = 'BBBEE Scorecard'
        verbose_name_plural = 'BBBEE Scorecards'
    
    def __str__(self):
        return f"{self.client.company_name} - Level {self.bbbee_level}"


class BBBEEServiceYear(TenantAwareModel):
    """
    B-BBEE service year - tracks B-BBEE verification work for a specific financial year.
    Aligns with client's financial year-end.
    
    Generic Scorecard Elements (109 points total):
    - Ownership: 25 points
    - Management Control: 19 points
    - Skills Development: 20 points (links to WSP/ATR data)
    - Enterprise & Supplier Development: 40 points
    - Socio-Economic Development: 5 points
    """
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('DATA_COLLECTION', 'Data Collection'),
        ('OWNERSHIP_ANALYSIS', 'Ownership Analysis'),
        ('MANAGEMENT_ANALYSIS', 'Management Control Analysis'),
        ('SKILLS_DEV_ANALYSIS', 'Skills Development Analysis'),
        ('ESD_ANALYSIS', 'Enterprise/Supplier Development Analysis'),
        ('SED_ANALYSIS', 'Socio-Economic Development Analysis'),
        ('INTERNAL_REVIEW', 'Internal Review'),
        ('CLIENT_REVIEW', 'Client Review'),
        ('VERIFICATION_SCHEDULED', 'Verification Scheduled'),
        ('VERIFICATION_IN_PROGRESS', 'Verification In Progress'),
        ('VERIFIED', 'Verified'),
        ('CERTIFICATE_ISSUED', 'Certificate Issued'),
        ('COMPLETED', 'Completed'),
    ]
    
    OUTCOME_CHOICES = [
        ('PENDING', 'Pending Verification'),
        ('LEVEL_1', 'Level 1'),
        ('LEVEL_2', 'Level 2'),
        ('LEVEL_3', 'Level 3'),
        ('LEVEL_4', 'Level 4'),
        ('LEVEL_5', 'Level 5'),
        ('LEVEL_6', 'Level 6'),
        ('LEVEL_7', 'Level 7'),
        ('LEVEL_8', 'Level 8'),
        ('NON_COMPLIANT', 'Non-Compliant'),
        ('NOT_VERIFIED', 'Not Verified'),
    ]
    
    ENTERPRISE_TYPE_CHOICES = [
        ('EME', 'Exempted Micro Enterprise (≤R10m)'),
        ('QSE', 'Qualifying Small Enterprise (R10-50m)'),
        ('GENERIC', 'Generic Enterprise (>R50m)'),
    ]
    
    subscription = models.ForeignKey(
        'ClientServiceSubscription',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bbbee_service_years'
    )
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='bbbee_service_years'
    )
    
    # Financial year aligned with client's year-end
    # e.g., financial_year=2025 with year_end_month=2 means Mar 2024 - Feb 2025
    financial_year = models.PositiveIntegerField(
        help_text='Financial year ending (e.g., 2025 for FY ending Feb 2025)'
    )
    year_end_month = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text='Month in which financial year ends (1-12)'
    )
    
    # Enterprise classification
    enterprise_type = models.CharField(
        max_length=10,
        choices=ENTERPRISE_TYPE_CHOICES,
        default='GENERIC',
        help_text='Classification based on annual turnover'
    )
    annual_turnover = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True, blank=True,
        help_text='Annual turnover used for classification'
    )
    
    # Black ownership percentage (for EME/QSE auto-level)
    black_ownership_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True, blank=True,
        help_text='Total black ownership % (for EME/QSE auto-recognition)'
    )
    black_women_ownership_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True, blank=True,
        help_text='Black women ownership % (for bonus level)'
    )
    
    # Status and outcome
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='NOT_STARTED')
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, default='PENDING')
    
    # Key dates
    target_verification_date = models.DateField(
        null=True, blank=True,
        help_text='Target date for verification'
    )
    actual_verification_date = models.DateField(null=True, blank=True)
    certificate_issue_date = models.DateField(null=True, blank=True)
    certificate_expiry_date = models.DateField(null=True, blank=True)
    
    # Verification agency (free text per user request)
    verification_agency = models.CharField(max_length=200, blank=True)
    verification_agency_contact = models.CharField(max_length=200, blank=True)
    verification_agency_email = models.EmailField(blank=True)
    verification_agency_phone = models.CharField(max_length=20, blank=True)
    
    # Certificate details
    certificate_number = models.CharField(max_length=100, blank=True)
    
    # Link to resulting scorecard
    scorecard = models.OneToOneField(
        BBBEEScorecard,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='service_year'
    )
    
    # Link to employee snapshot used for management control analysis
    employee_snapshot = models.ForeignKey(
        'ClientEmployeeSnapshot',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='bbbee_service_years'
    )
    
    # Link to WSP/ATR service year for skills development data
    wspatr_service_year = models.ForeignKey(
        'WSPATRServiceYear',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='bbbee_service_years',
        help_text='WSP/ATR data for Skills Development element'
    )
    
    # Link to EE service year for management control data
    ee_service_year = models.ForeignKey(
        'EEServiceYear',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='bbbee_service_years',
        help_text='EE data for Management Control element'
    )
    
    # Assignment
    assigned_consultant = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_bbbee_years'
    )
    
    # Progress tracking
    progress_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-financial_year']
        unique_together = ['client', 'financial_year']
        verbose_name = 'B-BBEE Service Year'
        verbose_name_plural = 'B-BBEE Service Years'
    
    def __str__(self):
        return f"{self.client.company_name} - B-BBEE FY{self.financial_year}"
    
    @property
    def financial_year_display(self):
        """Display the financial year period."""
        from datetime import date
        if self.year_end_month == 12:
            return f"Jan {self.financial_year} - Dec {self.financial_year}"
        elif self.year_end_month < 12:
            start_year = self.financial_year - 1
            end_year = self.financial_year
            start_month = self.year_end_month + 1
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            return f"{month_names[start_month-1]} {start_year} - {month_names[self.year_end_month-1]} {end_year}"
        return f"FY{self.financial_year}"
    
    @property
    def period_start_date(self):
        from datetime import date
        if self.year_end_month == 12:
            return date(self.financial_year, 1, 1)
        return date(self.financial_year - 1, self.year_end_month + 1, 1)
    
    @property
    def period_end_date(self):
        from datetime import date
        import calendar
        last_day = calendar.monthrange(self.financial_year, self.year_end_month)[1]
        return date(self.financial_year, self.year_end_month, last_day)
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.status in ['VERIFIED', 'CERTIFICATE_ISSUED', 'COMPLETED']:
            return False
        if self.target_verification_date:
            return timezone.now().date() > self.target_verification_date
        return False
    
    @property
    def days_until_target(self):
        from django.utils import timezone
        if not self.target_verification_date:
            return None
        if self.status in ['VERIFIED', 'CERTIFICATE_ISSUED', 'COMPLETED']:
            return None
        delta = self.target_verification_date - timezone.now().date()
        return delta.days
    
    @property
    def certificate_days_remaining(self):
        """Days until certificate expires."""
        from django.utils import timezone
        if not self.certificate_expiry_date:
            return None
        delta = self.certificate_expiry_date - timezone.now().date()
        return delta.days
    
    def determine_enterprise_type(self):
        """Auto-classify enterprise type based on turnover."""
        if self.annual_turnover:
            if self.annual_turnover <= Decimal('10000000'):  # ≤R10m
                return 'EME'
            elif self.annual_turnover <= Decimal('50000000'):  # R10-50m
                return 'QSE'
            else:
                return 'GENERIC'
        return self.enterprise_type
    
    def calculate_eme_qse_level(self):
        """
        For EME/QSE, calculate automatic B-BBEE level.
        EME: 100% black owned = Level 1, 51%+ black owned = Level 2, else Level 4
        QSE: Uses simplified scorecard but similar auto-recognition rules
        """
        if self.enterprise_type == 'EME':
            if self.black_ownership_percentage and self.black_ownership_percentage >= Decimal('100'):
                return 'LEVEL_1'
            elif self.black_ownership_percentage and self.black_ownership_percentage >= Decimal('51'):
                return 'LEVEL_2'
            else:
                return 'LEVEL_4'
        elif self.enterprise_type == 'QSE':
            if self.black_ownership_percentage and self.black_ownership_percentage >= Decimal('100'):
                return 'LEVEL_1'
            elif self.black_ownership_percentage and self.black_ownership_percentage >= Decimal('51'):
                return 'LEVEL_2'
        return 'PENDING'


class BBBEEDocument(TenantAwareModel):
    """
    Document management for B-BBEE verification process.
    """
    DOCUMENT_TYPE_CHOICES = [
        # Company documents
        ('CIPC_REGISTRATION', 'CIPC Company Registration'),
        ('SHARE_CERTIFICATES', 'Share Certificates'),
        ('SHAREHOLDERS_AGREEMENT', 'Shareholders Agreement'),
        ('DIRECTORS_RESOLUTION', 'Directors Resolution'),
        ('ANNUAL_FINANCIAL_STATEMENTS', 'Annual Financial Statements'),
        ('MANAGEMENT_ACCOUNTS', 'Management Accounts'),
        ('TAX_CLEARANCE', 'Tax Clearance Certificate'),
        ('ORGANOGRAM', 'Company Organogram'),
        # Element-specific
        ('OWNERSHIP_PROOF', 'Ownership Proof Documentation'),
        ('BOARD_COMPOSITION', 'Board Composition Documentation'),
        ('EXEC_DEMOGRAPHICS', 'Executive Demographics'),
        ('PAYROLL_SUMMARY', 'Payroll Summary (Management Control)'),
        ('SKILLS_DEV_SPEND', 'Skills Development Spend Evidence'),
        ('LEARNERSHIPS_PROOF', 'Learnerships/Internships Proof'),
        ('ESD_CONTRIBUTIONS', 'Enterprise/Supplier Development Evidence'),
        ('SED_CONTRIBUTIONS', 'Socio-Economic Development Evidence'),
        ('PREFERENTIAL_PROCUREMENT', 'Preferential Procurement Records'),
        ('SUPPLIER_DECLARATIONS', 'Supplier B-BBEE Declarations'),
        # Verification documents
        ('VERIFICATION_REPORT', 'Verification Agency Report'),
        ('BBBEE_CERTIFICATE', 'B-BBEE Certificate'),
        ('SWORN_AFFIDAVIT', 'Sworn Affidavit (EME/QSE)'),
        # Other
        ('TRANSFORMATION_PLAN', 'Transformation Strategy/Plan'),
        ('OTHER', 'Other Document'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Upload'),
        ('UPLOADED', 'Uploaded'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved/Verified'),
        ('REJECTED', 'Rejected - Reupload Required'),
        ('NOT_APPLICABLE', 'Not Applicable'),
    ]
    
    service_year = models.ForeignKey(
        BBBEEServiceYear,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    name = models.CharField(max_length=200, blank=True, help_text='Custom name if needed')
    description = models.TextField(blank=True)
    
    # File
    file = models.FileField(upload_to='bbbee_documents/%Y/%m/', null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_required = models.BooleanField(default=True)
    
    # Metadata
    uploaded_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='uploaded_bbbee_documents'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['document_type']
        verbose_name = 'B-BBEE Document'
        verbose_name_plural = 'B-BBEE Documents'
    
    def __str__(self):
        return f"{self.service_year.client.company_name} - {self.get_document_type_display()}"


class OwnershipStructure(TenantAwareModel):
    """
    Detailed ownership structure for B-BBEE Ownership element scoring.
    Tracks voting rights, economic interest, and flow-through calculations.
    """
    service_year = models.OneToOneField(
        BBBEEServiceYear,
        on_delete=models.CASCADE,
        related_name='ownership_structure'
    )
    
    # Total issued shares
    total_shares_issued = models.PositiveIntegerField(default=0)
    
    # Ownership summary (calculated from shareholders)
    total_black_voting_rights = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Total black voting rights %'
    )
    total_black_economic_interest = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Total black economic interest %'
    )
    black_women_voting_rights = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Black women voting rights %'
    )
    black_women_economic_interest = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Black women economic interest %'
    )
    
    # New entrant status (for bonus points)
    has_new_entrants = models.BooleanField(
        default=False,
        help_text='Ownership includes new entrants (previously disadvantaged)'
    )
    new_entrant_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='% ownership by new entrants'
    )
    
    # Ownership fulfillment
    ownership_fulfilled = models.BooleanField(
        default=False,
        help_text='Ownership is fully vested (not vendor-financed/encumbered)'
    )
    
    # Calculated score (out of 25 for Generic)
    calculated_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Ownership Structure'
        verbose_name_plural = 'Ownership Structures'
    
    def __str__(self):
        return f"{self.service_year.client.company_name} - Ownership FY{self.service_year.financial_year}"


class Shareholder(TenantAwareModel):
    """
    Individual shareholder for ownership structure.
    """
    SHAREHOLDER_TYPE_CHOICES = [
        ('INDIVIDUAL', 'Individual'),
        ('COMPANY', 'Company/Entity'),
        ('TRUST', 'Trust'),
        ('ESOP', 'Employee Share Ownership Programme'),
        ('BROAD_BASED', 'Broad-Based Ownership Scheme'),
    ]
    
    DEMOGRAPHIC_CHOICES = [
        ('BLACK_MALE', 'Black Male'),
        ('BLACK_FEMALE', 'Black Female'),
        ('COLOURED_MALE', 'Coloured Male'),
        ('COLOURED_FEMALE', 'Coloured Female'),
        ('INDIAN_MALE', 'Indian Male'),
        ('INDIAN_FEMALE', 'Indian Female'),
        ('WHITE_MALE', 'White Male'),
        ('WHITE_FEMALE', 'White Female'),
        ('NON_SA', 'Non-South African'),
        ('ENTITY', 'Entity (Flow-through)'),
    ]
    
    ownership_structure = models.ForeignKey(
        OwnershipStructure,
        on_delete=models.CASCADE,
        related_name='shareholders'
    )
    
    shareholder_type = models.CharField(max_length=20, choices=SHAREHOLDER_TYPE_CHOICES)
    
    # Shareholder details
    name = models.CharField(max_length=200)
    id_number = models.CharField(max_length=20, blank=True, help_text='SA ID number (individuals)')
    registration_number = models.CharField(max_length=50, blank=True, help_text='Company registration (entities)')
    
    # Demographics (for individuals)
    demographic = models.CharField(
        max_length=20,
        choices=DEMOGRAPHIC_CHOICES,
        blank=True
    )
    is_black = models.BooleanField(default=False)
    is_female = models.BooleanField(default=False)
    is_disabled = models.BooleanField(default=False)
    is_youth = models.BooleanField(default=False, help_text='Under 35 years old')
    is_new_entrant = models.BooleanField(
        default=False,
        help_text='New entrant (previously disadvantaged with no prior significant ownership)'
    )
    
    # Shareholding
    shares_held = models.PositiveIntegerField(default=0)
    voting_rights_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    economic_interest_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    
    # Flow-through (for entity shareholders)
    # When shareholder is an entity, we need to know its B-BBEE recognition level
    entity_bbbee_level = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='B-BBEE level of entity shareholder (for flow-through)'
    )
    entity_black_ownership = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text='Black ownership % of entity shareholder'
    )
    
    # Encumbrance/Vesting
    is_fully_vested = models.BooleanField(
        default=True,
        help_text='Shares are fully vested (not under vendor financing)'
    )
    vesting_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-voting_rights_percentage']
        verbose_name = 'Shareholder'
        verbose_name_plural = 'Shareholders'
    
    def __str__(self):
        return f"{self.name} - {self.voting_rights_percentage}%"


class ManagementControlProfile(TenantAwareModel):
    """
    Management Control element data.
    Tracks board composition, executive management, and senior management demographics.
    Links to ClientEmployeeSnapshot for workforce demographics.
    """
    service_year = models.OneToOneField(
        BBBEEServiceYear,
        on_delete=models.CASCADE,
        related_name='management_profile'
    )
    
    # Board of Directors
    board_total = models.PositiveIntegerField(default=0)
    board_black = models.PositiveIntegerField(default=0)
    board_black_female = models.PositiveIntegerField(default=0)
    board_black_executive = models.PositiveIntegerField(default=0, help_text='Black executive directors')
    board_black_independent = models.PositiveIntegerField(default=0, help_text='Black independent non-exec directors')
    
    # Executive Directors/C-Suite
    exec_total = models.PositiveIntegerField(default=0)
    exec_black = models.PositiveIntegerField(default=0)
    exec_black_female = models.PositiveIntegerField(default=0)
    
    # Senior Management (typically one level below exec)
    senior_mgmt_total = models.PositiveIntegerField(default=0)
    senior_mgmt_black = models.PositiveIntegerField(default=0)
    senior_mgmt_black_female = models.PositiveIntegerField(default=0)
    
    # Middle Management
    middle_mgmt_total = models.PositiveIntegerField(default=0)
    middle_mgmt_black = models.PositiveIntegerField(default=0)
    middle_mgmt_black_female = models.PositiveIntegerField(default=0)
    
    # Junior Management
    junior_mgmt_total = models.PositiveIntegerField(default=0)
    junior_mgmt_black = models.PositiveIntegerField(default=0)
    junior_mgmt_black_female = models.PositiveIntegerField(default=0)
    
    # Employees with disabilities in management
    disabled_in_management = models.PositiveIntegerField(default=0)
    
    # Calculated score (out of 19 for Generic)
    calculated_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Management Control Profile'
        verbose_name_plural = 'Management Control Profiles'
    
    def __str__(self):
        return f"{self.service_year.client.company_name} - Management Control FY{self.service_year.financial_year}"
    
    @property
    def board_black_percentage(self):
        if self.board_total == 0:
            return Decimal('0.00')
        return Decimal(self.board_black) / Decimal(self.board_total) * 100
    
    @property
    def exec_black_percentage(self):
        if self.exec_total == 0:
            return Decimal('0.00')
        return Decimal(self.exec_black) / Decimal(self.exec_total) * 100


class SkillsDevelopmentElement(TenantAwareModel):
    """
    Skills Development element data.
    Links to WSP/ATR for training spend and beneficiary data.
    Tracks Skills Development Spend as % of leviable amount.
    """
    service_year = models.OneToOneField(
        BBBEEServiceYear,
        on_delete=models.CASCADE,
        related_name='skills_development'
    )
    
    # Leviable amount (annual payroll)
    leviable_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Annual leviable payroll amount'
    )
    
    # Total skills development spend
    total_skills_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    
    # Spend on black employees
    black_skills_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    black_female_skills_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    black_disabled_skills_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    
    # Learnerships/Internships
    learnerships_total = models.PositiveIntegerField(default=0)
    learnerships_black = models.PositiveIntegerField(default=0)
    learnerships_black_female = models.PositiveIntegerField(default=0)
    learnerships_black_disabled = models.PositiveIntegerField(default=0)
    learnerships_black_youth = models.PositiveIntegerField(default=0)
    
    internships_total = models.PositiveIntegerField(default=0)
    internships_black = models.PositiveIntegerField(default=0)
    internships_absorbed = models.PositiveIntegerField(
        default=0,
        help_text='Interns absorbed into permanent employment'
    )
    
    # Bursaries
    bursaries_total = models.PositiveIntegerField(default=0)
    bursaries_black = models.PositiveIntegerField(default=0)
    bursaries_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    
    # Calculated percentages
    @property
    def skills_spend_percentage(self):
        if self.leviable_amount == 0:
            return Decimal('0.00')
        return (self.total_skills_spend / self.leviable_amount) * 100
    
    @property
    def black_skills_spend_percentage(self):
        if self.leviable_amount == 0:
            return Decimal('0.00')
        return (self.black_skills_spend / self.leviable_amount) * 100
    
    # Calculated score (out of 20 for Generic)
    calculated_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Skills Development Element'
        verbose_name_plural = 'Skills Development Elements'
    
    def __str__(self):
        return f"{self.service_year.client.company_name} - Skills Dev FY{self.service_year.financial_year}"


class ESDElement(TenantAwareModel):
    """
    Enterprise and Supplier Development element data.
    Tracks Preferential Procurement, Supplier Development, and Enterprise Development.
    Combined 40 points in Generic scorecard.
    """
    service_year = models.OneToOneField(
        BBBEEServiceYear,
        on_delete=models.CASCADE,
        related_name='esd_element'
    )
    
    # Total Measured Procurement Spend (TMPS)
    total_procurement_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Total measured procurement spend'
    )
    
    # Preferential Procurement - B-BBEE spend
    bbbee_procurement_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Spend with B-BBEE compliant suppliers'
    )
    qse_eme_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Spend with QSE/EME suppliers'
    )
    black_owned_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Spend with 51%+ black-owned suppliers'
    )
    black_women_owned_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Spend with 30%+ black women-owned suppliers'
    )
    designated_group_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Spend with suppliers owned by designated groups (youth, disabled, rural)'
    )
    
    # Net Profit After Tax (for ED/SD calculations)
    npat = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Net Profit After Tax'
    )
    
    # Supplier Development
    supplier_dev_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Annual spend on supplier development'
    )
    supplier_dev_beneficiaries = models.PositiveIntegerField(
        default=0,
        help_text='Number of supplier development beneficiaries'
    )
    
    # Enterprise Development
    enterprise_dev_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Annual spend on enterprise development'
    )
    enterprise_dev_beneficiaries = models.PositiveIntegerField(
        default=0,
        help_text='Number of enterprise development beneficiaries'
    )
    
    # Graduated EMEs/QSEs
    graduated_emes = models.PositiveIntegerField(
        default=0,
        help_text='EMEs graduated to QSE status'
    )
    graduated_qses = models.PositiveIntegerField(
        default=0,
        help_text='QSEs graduated to Generic status'
    )
    
    # Calculated scores
    preferential_procurement_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    supplier_development_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    enterprise_development_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    calculated_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Combined ESD score (out of 40 for Generic)'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'ESD Element'
        verbose_name_plural = 'ESD Elements'
    
    def __str__(self):
        return f"{self.service_year.client.company_name} - ESD FY{self.service_year.financial_year}"
    
    @property
    def bbbee_procurement_percentage(self):
        if self.total_procurement_spend == 0:
            return Decimal('0.00')
        return (self.bbbee_procurement_spend / self.total_procurement_spend) * 100


class ESDSupplier(TenantAwareModel):
    """
    Individual supplier for ESD beneficiary tracking.
    """
    esd_element = models.ForeignKey(
        ESDElement,
        on_delete=models.CASCADE,
        related_name='suppliers'
    )
    
    SUPPLIER_TYPE_CHOICES = [
        ('PREFERENTIAL', 'Preferential Procurement Supplier'),
        ('SUPPLIER_DEV', 'Supplier Development Beneficiary'),
        ('ENTERPRISE_DEV', 'Enterprise Development Beneficiary'),
    ]
    
    supplier_type = models.CharField(max_length=20, choices=SUPPLIER_TYPE_CHOICES)
    
    # Supplier details
    supplier_name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50, blank=True)
    contact_person = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # B-BBEE status
    bbbee_level = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Supplier B-BBEE level'
    )
    is_eme = models.BooleanField(default=False)
    is_qse = models.BooleanField(default=False)
    black_ownership_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    black_women_ownership_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    
    # Spend/Support
    annual_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Annual procurement spend with this supplier'
    )
    development_contribution = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='ED/SD contribution value'
    )
    
    # Development details (for ED/SD beneficiaries)
    support_type = models.CharField(
        max_length=200, blank=True,
        help_text='Type of ED/SD support provided'
    )
    support_start_date = models.DateField(null=True, blank=True)
    support_end_date = models.DateField(null=True, blank=True)
    
    # Evidence
    bbbee_certificate = models.FileField(
        upload_to='bbbee_supplier_certificates/',
        null=True, blank=True
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['supplier_name']
        verbose_name = 'ESD Supplier'
        verbose_name_plural = 'ESD Suppliers'
    
    def __str__(self):
        return f"{self.supplier_name} - {self.get_supplier_type_display()}"


class SEDElement(TenantAwareModel):
    """
    Socio-Economic Development element data.
    Tracks contributions to beneficiaries that are 75%+ black.
    5 points in Generic scorecard.
    """
    service_year = models.OneToOneField(
        BBBEEServiceYear,
        on_delete=models.CASCADE,
        related_name='sed_element'
    )
    
    # Net Profit After Tax (for calculation)
    npat = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Net Profit After Tax'
    )
    
    # Total SED contributions
    total_sed_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    
    # Number of beneficiaries
    total_beneficiaries = models.PositiveIntegerField(default=0)
    black_beneficiaries = models.PositiveIntegerField(default=0)
    
    # Calculated score (out of 5 for Generic)
    calculated_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00')
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'SED Element'
        verbose_name_plural = 'SED Elements'
    
    def __str__(self):
        return f"{self.service_year.client.company_name} - SED FY{self.service_year.financial_year}"
    
    @property
    def sed_spend_percentage(self):
        """SED spend as % of NPAT."""
        if self.npat == 0:
            return Decimal('0.00')
        return (self.total_sed_spend / self.npat) * 100


class SEDContribution(TenantAwareModel):
    """
    Individual SED contribution/beneficiary.
    """
    sed_element = models.ForeignKey(
        SEDElement,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    
    CONTRIBUTION_TYPE_CHOICES = [
        ('MONETARY', 'Monetary Donation'),
        ('IN_KIND', 'In-Kind Contribution'),
        ('TIME', 'Time/Pro-Bono Services'),
        ('SPONSORSHIP', 'Sponsorship'),
        ('BURSARY', 'Bursary/Educational Support'),
        ('OTHER', 'Other'),
    ]
    
    contribution_type = models.CharField(max_length=20, choices=CONTRIBUTION_TYPE_CHOICES)
    
    # Beneficiary details
    beneficiary_name = models.CharField(max_length=200)
    beneficiary_type = models.CharField(
        max_length=100, blank=True,
        help_text='e.g., NPO, School, Community Project'
    )
    npo_number = models.CharField(max_length=50, blank=True, help_text='NPO registration number')
    
    # Beneficiary demographics
    black_beneficiary_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('75.00'),
        help_text='% of beneficiaries that are black (must be 75%+)'
    )
    
    # Contribution details
    description = models.TextField(blank=True)
    contribution_date = models.DateField()
    monetary_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    
    # Evidence
    proof_document = models.FileField(
        upload_to='bbbee_sed_proof/',
        null=True, blank=True
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-contribution_date']
        verbose_name = 'SED Contribution'
        verbose_name_plural = 'SED Contributions'
    
    def __str__(self):
        return f"{self.beneficiary_name} - R{self.monetary_value}"


class TransformationPlan(TenantAwareModel):
    """
    B-BBEE Transformation Plan/Strategy.
    Multi-year plan for improving B-BBEE score.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('UNDER_REVIEW', 'Under Review'),
        ('COMPLETED', 'Completed'),
        ('SUPERSEDED', 'Superseded'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='transformation_plans'
    )
    
    name = models.CharField(max_length=200, default='B-BBEE Transformation Plan')
    
    # Duration
    start_date = models.DateField()
    end_date = models.DateField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Current vs Target
    current_level = models.PositiveIntegerField(null=True, blank=True)
    target_level = models.PositiveIntegerField(null=True, blank=True)
    
    # Element-specific targets
    ownership_target = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    management_control_target = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    skills_development_target = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    esd_target = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    sed_target = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    
    # Strategy document
    strategy_document = models.FileField(
        upload_to='bbbee_transformation_plans/',
        null=True, blank=True
    )
    
    # Key initiatives
    initiatives = models.JSONField(
        default=list,
        help_text='List of transformation initiatives'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Transformation Plan'
        verbose_name_plural = 'Transformation Plans'
    
    def __str__(self):
        return f"{self.client.company_name} - {self.name}"


# =====================================================
# GRANT MANAGEMENT MODELS
# =====================================================

class GrantProject(TenantAwareModel):
    """
    SETA grant/project tracking
    """
    STATUS_CHOICES = [
        ('APPLIED', 'Application Submitted'),
        ('APPROVED', 'Approved'),
        ('CONTRACTED', 'Contracted'),
        ('ACTIVE', 'Active/In Progress'),
        ('REPORTING', 'Reporting Phase'),
        ('COMPLETED', 'Completed'),
        ('CLOSED', 'Closed'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='grant_projects'
    )
    funding_opportunity = models.ForeignKey(
        'crm.SETAFundingOpportunity',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='grant_projects'
    )
    
    # Project details
    project_name = models.CharField(max_length=200)
    project_number = models.CharField(max_length=50, blank=True)
    
    # SETA
    seta = models.ForeignKey(
        'learners.SETA',
        on_delete=models.PROTECT,
        related_name='grant_projects'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='APPLIED')
    
    # Dates
    application_date = models.DateField(null=True, blank=True)
    approval_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    # Financials
    approved_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True, blank=True
    )
    claimed_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    received_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Learner targets
    target_learners = models.PositiveIntegerField(null=True, blank=True)
    enrolled_learners = models.PositiveIntegerField(default=0)
    completed_learners = models.PositiveIntegerField(default=0)
    
    # Project manager
    project_manager = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_grants'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Grant Project'
        verbose_name_plural = 'Grant Projects'
    
    def __str__(self):
        return f"{self.client.company_name} - {self.project_name}"


class GrantClaim(AuditedModel):
    """
    Grant payment claim/tranche
    """
    CLAIM_TYPES = [
        ('TRANCHE_1', 'Tranche 1 - Commencement'),
        ('TRANCHE_2', 'Tranche 2 - Midpoint'),
        ('TRANCHE_3', 'Tranche 3 - Completion'),
        ('FINAL', 'Final Claim'),
        ('INTERIM', 'Interim Claim'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('QUERY', 'Query/Rework Required'),
        ('APPROVED', 'Approved'),
        ('PAID', 'Paid'),
        ('REJECTED', 'Rejected'),
    ]
    
    project = models.ForeignKey(
        GrantProject,
        on_delete=models.CASCADE,
        related_name='claims'
    )
    
    claim_type = models.CharField(max_length=20, choices=CLAIM_TYPES)
    claim_number = models.CharField(max_length=50)
    
    # Dates
    submission_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Amounts
    claim_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True, blank=True
    )
    
    # Learner numbers at claim
    learners_commenced = models.PositiveIntegerField(default=0)
    learners_completed = models.PositiveIntegerField(default=0)
    
    # Payment
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=50, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-submission_date']
        verbose_name = 'Grant Claim'
        verbose_name_plural = 'Grant Claims'
    
    def __str__(self):
        return f"{self.project.project_name} - {self.claim_type}"


# =====================================================
# COMMITTEE MODELS
# =====================================================

class Committee(TenantAwareModel):
    """
    Training Committee for corporate clients
    """
    COMMITTEE_TYPES = [
        ('TRAINING', 'Training Committee'),
        ('EE', 'Employment Equity Committee'),
        ('WSP', 'WSP Committee'),
        ('SAFETY', 'Health & Safety Committee'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='committees'
    )
    
    committee_type = models.CharField(max_length=20, choices=COMMITTEE_TYPES)
    name = models.CharField(max_length=100)
    
    # Meeting schedule
    meeting_frequency = models.CharField(max_length=50, blank=True)  # e.g., "Monthly", "Quarterly"
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['committee_type', 'name']
        verbose_name = 'Committee'
        verbose_name_plural = 'Committees'
    
    def __str__(self):
        return f"{self.client.company_name} - {self.name}"


class CommitteeMember(models.Model):
    """
    Committee member
    """
    ROLE_CHOICES = [
        ('CHAIR', 'Chairperson'),
        ('VICE_CHAIR', 'Vice Chairperson'),
        ('SECRETARY', 'Secretary'),
        ('MEMBER', 'Member'),
    ]
    
    committee = models.ForeignKey(
        Committee,
        on_delete=models.CASCADE,
        related_name='members'
    )
    
    contact = models.ForeignKey(
        CorporateContact,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='committee_memberships'
    )
    
    # If not a contact
    name = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER')
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['role', 'name']
        verbose_name = 'Committee Member'
        verbose_name_plural = 'Committee Members'
    
    def __str__(self):
        return f"{self.committee} - {self.get_member_name()}"
    
    def get_member_name(self):
        if self.contact:
            return f"{self.contact.first_name} {self.contact.last_name}"
        return self.name


class CommitteeMeeting(AuditedModel):
    """
    Committee meeting records
    """
    committee = models.ForeignKey(
        Committee,
        on_delete=models.CASCADE,
        related_name='meetings'
    )
    
    meeting_date = models.DateField()
    meeting_time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=200, blank=True)
    
    # Agenda
    agenda = models.TextField(blank=True)
    
    # Minutes
    minutes = models.TextField(blank=True)
    minutes_file = models.FileField(
        upload_to='committee_minutes/',
        blank=True
    )
    
    # Attendance
    attendees = models.ManyToManyField(
        CommitteeMember,
        blank=True,
        related_name='meetings_attended'
    )
    
    # Next meeting
    next_meeting_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-meeting_date']
        verbose_name = 'Committee Meeting'
        verbose_name_plural = 'Committee Meetings'
    
    def __str__(self):
        return f"{self.committee} - {self.meeting_date}"


# =====================================================
# IDP (Individual Development Plan) MODELS
# =====================================================

class EmployeeIDP(TenantAwareModel):
    """
    Individual Development Plan for corporate employees
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('APPROVED', 'Approved'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    employee = models.ForeignKey(
        CorporateEmployee,
        on_delete=models.CASCADE,
        related_name='idps'
    )
    
    # Link to WSP/ATR Service Year
    service_year = models.ForeignKey(
        'WSPATRServiceYear',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='idps'
    )
    
    # Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Career goals
    career_goals = models.TextField(blank=True)
    development_areas = models.TextField(blank=True)
    
    # Sign-off
    employee_sign_off_date = models.DateField(null=True, blank=True)
    manager_sign_off_date = models.DateField(null=True, blank=True)
    manager = models.ForeignKey(
        CorporateContact,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_idps'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-period_start']
        verbose_name = 'Employee IDP'
        verbose_name_plural = 'Employee IDPs'
    
    def __str__(self):
        return f"{self.employee} - IDP {self.period_start.year}"


class IDPTrainingNeed(models.Model):
    """
    Training need identified in IDP
    """
    PRIORITY_CHOICES = [
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]
    
    STATUS_CHOICES = [
        ('IDENTIFIED', 'Identified'),
        ('PLANNED', 'Planned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('DEFERRED', 'Deferred'),
    ]
    
    idp = models.ForeignKey(
        EmployeeIDP,
        on_delete=models.CASCADE,
        related_name='training_needs'
    )
    
    # Need
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Link to qualification/module
    qualification = models.ForeignKey(
        'academics.Qualification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='idp_needs'
    )
    
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IDENTIFIED')
    
    # WSP Integration
    is_wsp_planned = models.BooleanField(
        default=False,
        verbose_name='Include in WSP Planned Training',
        help_text='If checked, this will be pulled into the WSP submission for the linked service year.'
    )
    
    # Planning
    target_date = models.DateField(null=True, blank=True)
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True
    )
    
    # Completion
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='idp_needs'
    )
    completed_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['priority', 'target_date']
        verbose_name = 'IDP Training Need'
        verbose_name_plural = 'IDP Training Needs'
    
    def __str__(self):
        return f"{self.idp} - {self.title}"


# =====================================================
# CLIENT PROJECT MODELS
# =====================================================

class ClientProject(TenantAwareModel):
    """
    Service delivery project for corporate client
    """
    STATUS_CHOICES = [
        ('PLANNING', 'Planning'),
        ('ACTIVE', 'Active'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNING')
    
    # Manager
    project_manager = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='client_projects'
    )
    
    # Budget
    budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True, blank=True
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Client Project'
        verbose_name_plural = 'Client Projects'
    
    def __str__(self):
        return f"{self.client.company_name} - {self.name}"


class ClientProjectTask(AuditedModel):
    """
    Tasks within a client project (legacy - use ProjectTask for delivery projects)
    """
    STATUS_CHOICES = [
        ('TODO', 'To Do'),
        ('IN_PROGRESS', 'In Progress'),
        ('BLOCKED', 'Blocked'),
        ('DONE', 'Done'),
    ]
    
    project = models.ForeignKey(
        ClientProject,
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TODO')
    
    # Dates
    due_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='client_project_tasks'
    )
    
    class Meta:
        ordering = ['status', 'due_date']
        verbose_name = 'Client Project Task'
        verbose_name_plural = 'Client Project Tasks'
    
    def __str__(self):
        return f"{self.project} - {self.title}"


class DeadlineReminder(AuditedModel):
    """
    Deadline reminders for corporate services
    """
    REMINDER_TYPES = [
        ('WSP', 'WSP Deadline'),
        ('ATR', 'ATR Deadline'),
        ('EE', 'EE Report Deadline'),
        ('BBBEE', 'BBBEE Expiry'),
        ('GRANT', 'Grant Deadline'),
        ('CLAIM', 'Claim Deadline'),
        ('CONTRACT', 'Contract Renewal'),
        ('CUSTOM', 'Custom Reminder'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='deadline_reminders'
    )
    
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Deadline
    deadline_date = models.DateField()
    
    # Reminders
    reminder_days_before = models.JSONField(
        default=list,
        help_text='Days before deadline to send reminders, e.g. [30, 14, 7, 1]'
    )
    
    # Status
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    
    # Notification
    notify_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='deadline_reminders'
    )
    
    class Meta:
        ordering = ['deadline_date']
        verbose_name = 'Deadline Reminder'
        verbose_name_plural = 'Deadline Reminders'
    
    def __str__(self):
        return f"{self.client.company_name} - {self.title}"


# =====================================================
# SERVICE CATALOG MODELS
# =====================================================

class ServiceCategory(models.Model):
    """
    Category of services offered to corporate clients
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Icon class name for UI')
    color = models.CharField(max_length=7, default='#1a56db', help_text='Hex color for UI')
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Service Category'
        verbose_name_plural = 'Service Categories'
    
    def __str__(self):
        return self.name


class ServiceOffering(AuditedModel):
    """
    Specific service or product offered to corporate clients
    """
    SERVICE_TYPE_CHOICES = [
        # Core Consulting Services
        ('WSP_ATR', 'WSP/ATR (Full Package)'),
        ('BEE_CONSULTING', 'BEE Consulting & Preparation'),
        ('EE_CONSULTING', 'Employment Equity (Full Package)'),
        ('HOST_EMPLOYMENT', 'Host Employment'),
        ('DG_APPLICATION', 'Discretionary Grant Applications'),
    ]
    
    BILLING_TYPE_CHOICES = [
        ('ONCE_OFF', 'Once-off Fee'),
        ('MONTHLY', 'Monthly Retainer'),
        ('ANNUAL', 'Annual Fee'),
        ('PER_LEARNER', 'Per Learner'),
        ('PER_SUBMISSION', 'Per Submission'),
        ('HOURLY', 'Hourly Rate'),
        ('PROJECT', 'Project-based'),
    ]
    
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name='services'
    )
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30, unique=True)
    service_type = models.CharField(max_length=30, choices=SERVICE_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Features/Inclusions
    features = models.JSONField(
        default=list,
        blank=True,
        help_text='List of features/inclusions'
    )
    
    # Pricing
    billing_type = models.CharField(max_length=20, choices=BILLING_TYPE_CHOICES, default='ONCE_OFF')
    base_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_description = models.CharField(max_length=200, blank=True, help_text='e.g., "From R5,000 per learner"')
    
    # SLA
    sla_response_hours = models.PositiveIntegerField(null=True, blank=True, help_text='Response time in hours')
    sla_delivery_days = models.PositiveIntegerField(null=True, blank=True, help_text='Delivery time in days')
    
    # Requirements
    requires_qualification = models.BooleanField(default=False)
    requires_seta = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Service Offering'
        verbose_name_plural = 'Service Offerings'
    
    def __str__(self):
        return f"{self.category.name} - {self.name}"


class ClientServiceSubscription(TenantAwareModel):
    """
    Links a corporate client to services they have subscribed to
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Setup'),
        ('ACTIVE', 'Active'),
        ('ON_HOLD', 'On Hold'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='service_subscriptions'
    )
    service = models.ForeignKey(
        ServiceOffering,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    
    # CRM Link - which opportunity led to this subscription
    opportunity_source = models.ForeignKey(
        'CorporateOpportunity',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='resulting_subscriptions',
        help_text='The opportunity that resulted in this subscription'
    )
    proposal_source = models.ForeignKey(
        'ServiceProposal',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='resulting_subscriptions',
        help_text='The proposal that was accepted for this subscription'
    )
    
    # Contract
    contract_reference = models.CharField(max_length=50, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    renewal_date = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Pricing (can override service base price)
    agreed_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    billing_frequency = models.CharField(max_length=20, blank=True)
    
    # Assignment
    assigned_consultant = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_service_subscriptions'
    )
    
    # Satisfaction tracking
    satisfaction_score = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Client satisfaction score (1-5)'
    )
    last_review_date = models.DateField(null=True, blank=True)
    
    # Renewal tracking
    renewal_reminder_sent = models.BooleanField(default=False)
    renewal_reminder_date = models.DateField(null=True, blank=True)
    
    # Notes
    scope_of_work = models.TextField(blank=True, help_text='Specific scope for this client')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Client Service Subscription'
        verbose_name_plural = 'Client Service Subscriptions'
        unique_together = ['client', 'service', 'start_date']
    
    def __str__(self):
        return f"{self.client.company_name} - {self.service.name}"
    
    @property
    def is_active(self):
        from django.utils import timezone
        today = timezone.now().date()
        if self.status != 'ACTIVE':
            return False
        if self.end_date and self.end_date < today:
            return False
        return self.start_date <= today
    
    @property
    def days_until_renewal(self):
        from django.utils import timezone
        if self.renewal_date:
            return (self.renewal_date - timezone.now().date()).days
        return None
    
    @property
    def needs_renewal_reminder(self):
        """Check if renewal reminder should be sent (30 days before)."""
        if self.renewal_reminder_sent:
            return False
        days = self.days_until_renewal
        return days is not None and 0 < days <= 30


# =====================================================
# WORKPLACE-BASED LEARNING CONFIGURATION
# =====================================================

class LeavePolicy(AuditedModel):
    """
    Leave policy configuration for workplace-based learning stipend calculations.
    Defines how different leave types affect stipend payments.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Annual leave
    annual_leave_days_per_year = models.PositiveIntegerField(
        default=15,
        help_text='Total annual leave days per year (pro-rated for placement duration)'
    )
    annual_leave_paid = models.BooleanField(
        default=True,
        help_text='Whether annual leave is paid'
    )
    
    # Sick leave
    sick_leave_days_per_month = models.PositiveIntegerField(
        default=2,
        help_text='Paid sick leave days allowed per month'
    )
    sick_leave_requires_documentation_after_days = models.PositiveIntegerField(
        default=2,
        help_text='Sick note required after this many consecutive days'
    )
    
    # Family responsibility leave
    family_responsibility_days_per_year = models.PositiveIntegerField(
        default=3,
        help_text='Total family responsibility leave days per year'
    )
    family_leave_paid = models.BooleanField(
        default=True,
        help_text='Whether family responsibility leave is paid'
    )
    
    # Other settings
    public_holidays_paid = models.BooleanField(
        default=True,
        help_text='Whether public holidays are paid'
    )
    
    # Standard working hours
    standard_hours_per_day = models.DecimalField(
        max_digits=4, decimal_places=2,
        default=8,
        help_text='Standard working hours per day'
    )
    
    is_default = models.BooleanField(
        default=False,
        help_text='Use as default policy for new placements'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Leave Policy'
        verbose_name_plural = 'Leave Policies'
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Ensure only one default policy
        if self.is_default:
            LeavePolicy.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


# =====================================================
# HOST EMPLOYER MODELS
# =====================================================

class HostEmployer(TenantAwareModel):
    """
    Host employer for workplace-based learning placements
    Extends Employer model with host-specific tracking
    """
    STATUS_CHOICES = [
        ('PROSPECT', 'Prospect'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('SUSPENDED', 'Suspended'),
        ('INACTIVE', 'Inactive'),
    ]
    
    # Can link to existing employer or standalone
    employer = models.OneToOneField(
        'learners.Employer',
        on_delete=models.CASCADE,
        related_name='host_profile',
        null=True, blank=True
    )
    
    # Or standalone company info if no employer link
    company_name = models.CharField(max_length=200)
    trading_name = models.CharField(max_length=200, blank=True)
    registration_number = models.CharField(max_length=20, blank=True)
    
    # Contact
    contact_person = models.CharField(max_length=100)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    
    # Address
    physical_address = models.TextField()
    
    # GPS Location and Geofencing
    gps_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='GPS latitude of workplace location'
    )
    gps_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='GPS longitude of workplace location'
    )
    geofence_radius_meters = models.IntegerField(
        default=5000,
        help_text='Geofence radius in meters for attendance verification (default: 5000m = 5km)'
    )
    
    # SETA
    seta = models.ForeignKey(
        'learners.SETA',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='host_employers'
    )
    
    # Approval Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROSPECT')
    approval_date = models.DateField(null=True, blank=True)
    approval_expiry = models.DateField(null=True, blank=True)
    approval_reference = models.CharField(max_length=50, blank=True)
    
    # Capacity
    max_placement_capacity = models.PositiveIntegerField(
        default=10,
        help_text='Maximum number of learners that can be placed'
    )
    current_placements = models.PositiveIntegerField(default=0)
    
    # Trades/Qualifications offered
    approved_qualifications = models.ManyToManyField(
        'academics.Qualification',
        blank=True,
        related_name='host_employers'
    )
    
    # Workplace Details
    has_workshop = models.BooleanField(default=False)
    has_training_room = models.BooleanField(default=False)
    equipment_available = models.TextField(blank=True)
    safety_requirements_met = models.BooleanField(default=False)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['company_name']
        verbose_name = 'Host Employer'
        verbose_name_plural = 'Host Employers'
    
    def __str__(self):
        return self.company_name
    
    @property
    def available_capacity(self):
        return max(0, self.max_placement_capacity - self.current_placements)
    
    @property
    def is_approved(self):
        from django.utils import timezone
        if self.status != 'APPROVED':
            return False
        if self.approval_expiry and self.approval_expiry < timezone.now().date():
            return False
        return True


class HostMentor(AuditedModel):
    """
    Workplace mentor at a host employer.
    Mentors can be invited via MentorInvitation, create their own profile with password,
    and are activated when approved by HR/admin.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('INACTIVE', 'Inactive'),
    ]
    
    host = models.ForeignKey(
        HostEmployer,
        on_delete=models.CASCADE,
        related_name='mentors'
    )
    
    # Approval Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    approved_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_mentors'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Personal Details
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    id_number = models.CharField(max_length=13, blank=True)
    
    # Contact
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    # Position
    job_title = models.CharField(max_length=100)
    department = models.CharField(max_length=100, blank=True)
    years_experience = models.PositiveIntegerField(null=True, blank=True)
    
    # Trade/Qualification
    trade = models.CharField(max_length=100, blank=True)
    trade_certificate_number = models.CharField(max_length=50, blank=True)
    
    # Mentor Training
    mentor_trained = models.BooleanField(default=False)
    mentor_training_date = models.DateField(null=True, blank=True)
    mentor_certificate = models.FileField(upload_to='mentor_documents/certificates/', blank=True)
    
    # Document uploads with tracking
    cv_document = models.FileField(upload_to='mentor_documents/cv/', blank=True)
    cv_uploaded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='uploaded_mentor_cvs'
    )
    cv_uploaded_at = models.DateTimeField(null=True, blank=True)
    
    red_seal_certificate = models.FileField(upload_to='mentor_documents/certificates/', blank=True)
    red_seal_uploaded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='uploaded_mentor_red_seals'
    )
    red_seal_uploaded_at = models.DateTimeField(null=True, blank=True)
    
    id_copy = models.FileField(upload_to='mentor_documents/id/', blank=True)
    id_copy_uploaded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='uploaded_mentor_ids'
    )
    id_copy_uploaded_at = models.DateTimeField(null=True, blank=True)
    
    # Additional profile fields
    languages = models.JSONField(default=list, blank=True, help_text='List of languages spoken')
    additional_notes = models.TextField(blank=True)
    
    # Capacity
    max_mentees = models.PositiveIntegerField(default=4)
    current_mentees = models.PositiveIntegerField(default=0)
    
    # User account for portal access (created during registration, activated on approval)
    user = models.OneToOneField(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='mentor_profile'
    )
    
    # Digital Signature (captured during onboarding, locked after first capture)
    signature = models.ImageField(
        upload_to='signatures/mentors/%Y/%m/',
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
        ordering = ['last_name', 'first_name']
        verbose_name = 'Host Mentor'
        verbose_name_plural = 'Host Mentors'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.host.company_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def available_capacity(self):
        return max(0, self.max_mentees - self.current_mentees)
    
    @property
    def is_approved(self):
        return self.status == 'APPROVED'
    
    def approve(self, approved_by_user):
        """Approve the mentor and activate their user account."""
        from django.utils import timezone
        self.status = 'APPROVED'
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save()
        
        # Activate the user account if it exists
        if self.user:
            self.user.is_active = True
            self.user.save()


class MentorInvitation(AuditedModel):
    """
    Token-based invitation for mentor registration.
    HR sends invite link to mentor, mentor completes profile and creates password,
    HR/admin then approves to activate account.
    """
    import uuid
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    host = models.ForeignKey(
        HostEmployer,
        on_delete=models.CASCADE,
        related_name='mentor_invitations'
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_mentor_invitations'
    )
    
    # Invitation details
    email = models.EmailField()
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    
    # Token for registration link
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Expiry
    expires_at = models.DateTimeField()
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Link to created mentor profile
    created_mentor = models.OneToOneField(
        HostMentor,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='invitation'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Mentor Invitation'
        verbose_name_plural = 'Mentor Invitations'
    
    def __str__(self):
        return f"Invitation to {self.email} for {self.host.company_name}"
    
    @property
    def is_valid(self):
        """Check if invitation is still valid (not expired, not used)."""
        from django.utils import timezone
        if self.status != 'PENDING':
            return False
        if self.expires_at < timezone.now():
            return False
        return True
    
    def mark_accepted(self, mentor):
        """Mark invitation as accepted and link to created mentor."""
        from django.utils import timezone
        self.status = 'ACCEPTED'
        self.accepted_at = timezone.now()
        self.created_mentor = mentor
        self.save()
    
    @classmethod
    def create_invitation(cls, host, invited_by, email, first_name='', last_name='', days_valid=14):
        """Create a new invitation with expiry date."""
        from django.utils import timezone
        from datetime import timedelta
        
        invitation = cls.objects.create(
            host=host,
            invited_by=invited_by,
            email=email,
            first_name=first_name,
            last_name=last_name,
            expires_at=timezone.now() + timedelta(days=days_valid)
        )
        return invitation


class PlacementInvoice(AuditedModel):
    """
    Invoice for workplace placement services.
    Can be approved by client directly or by admin on behalf of client
    (requires screenshot of email approval).
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PAID', 'Paid'),
    ]
    
    APPROVAL_METHOD_CHOICES = [
        ('CLIENT', 'Approved by Client'),
        ('ADMIN_ON_BEHALF', 'Approved by Admin on Behalf of Client'),
    ]
    
    placement = models.ForeignKey(
        'WorkplacePlacement',
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    
    # Invoice details
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_file = models.FileField(upload_to='placement_invoices/')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Approval tracking
    approval_method = models.CharField(
        max_length=20,
        choices=APPROVAL_METHOD_CHOICES,
        blank=True
    )
    approved_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_placement_invoices'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Screenshot required when admin approves on behalf of client
    approval_screenshot = models.FileField(
        upload_to='placement_invoices/approval_screenshots/',
        blank=True,
        help_text='Required when admin approves on behalf of client (screenshot of email approval)'
    )
    
    # Rejection
    rejection_reason = models.TextField(blank=True)
    rejected_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='rejected_placement_invoices'
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-invoice_date']
        verbose_name = 'Placement Invoice'
        verbose_name_plural = 'Placement Invoices'
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.placement}"
    
    def approve(self, user, method='CLIENT', screenshot=None):
        """
        Approve the invoice.
        If method is ADMIN_ON_BEHALF, screenshot is required.
        """
        from django.utils import timezone
        
        if method == 'ADMIN_ON_BEHALF' and not screenshot:
            raise ValueError("Screenshot of email approval is required when admin approves on behalf of client")
        
        self.status = 'APPROVED'
        self.approval_method = method
        self.approved_by = user
        self.approved_at = timezone.now()
        
        if screenshot:
            self.approval_screenshot = screenshot
        
        self.save()
    
    def reject(self, user, reason):
        """Reject the invoice with a reason."""
        from django.utils import timezone
        self.status = 'REJECTED'
        self.rejection_reason = reason
        self.rejected_by = user
        self.rejected_at = timezone.now()
        self.save()


class WorkplaceStint(AuditedModel):
    """
    Defines workplace stint requirements for a qualification
    QCTO qualifications typically have 3 workplace stints spread across the program years
    """
    STINT_NUMBERS = [
        (1, 'Stint 1'),
        (2, 'Stint 2'),
        (3, 'Stint 3'),
    ]
    
    YEAR_LEVEL_CHOICES = [
        (1, 'Year 1'),
        (2, 'Year 2'),
        (3, 'Year 3'),
    ]
    
    qualification = models.ForeignKey(
        'academics.Qualification',
        on_delete=models.CASCADE,
        related_name='workplace_stints'
    )
    stint_number = models.PositiveIntegerField(
        choices=STINT_NUMBERS,
        help_text='Stint sequence (1, 2, or 3)'
    )
    year_level = models.PositiveIntegerField(
        choices=YEAR_LEVEL_CHOICES,
        help_text='Which program year this stint occurs in'
    )
    
    # Duration requirements
    duration_days_required = models.PositiveIntegerField(
        help_text='Minimum number of workplace days required for this stint'
    )
    duration_weeks = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Approximate weeks (calculated from days / 5)'
    )
    
    # Description and objectives
    title = models.CharField(max_length=100, blank=True)
    description = models.TextField(
        blank=True,
        help_text='Learning objectives and expectations for this stint'
    )
    
    # Linked workplace modules
    modules = models.ManyToManyField(
        'academics.Module',
        blank=True,
        related_name='workplace_stints',
        limit_choices_to={'module_type': 'W'},
        help_text='Workplace modules to be completed during this stint'
    )
    
    # Ordering
    sequence_order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['qualification', 'stint_number']
        unique_together = ['qualification', 'stint_number']
        verbose_name = 'Workplace Stint'
        verbose_name_plural = 'Workplace Stints'
    
    def __str__(self):
        return f"{self.qualification.saqa_id} - Stint {self.stint_number} (Year {self.year_level})"
    
    def save(self, *args, **kwargs):
        # Auto-calculate weeks from days
        if self.duration_days_required:
            self.duration_weeks = self.duration_days_required // 5
        if not self.title:
            self.title = f"Workplace Stint {self.stint_number}"
        super().save(*args, **kwargs)
    
    @property
    def duration_display(self):
        """Human-readable duration"""
        if self.duration_weeks:
            return f"{self.duration_weeks} weeks ({self.duration_days_required} days)"
        return f"{self.duration_days_required} days"


class WorkplacePlacement(TenantAwareModel):
    """
    Learner placement at a host employer
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Placement'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('TERMINATED', 'Terminated Early'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    TERMINATION_REASONS = [
        ('COMPLETED', 'Successfully Completed'),
        ('RESIGNED', 'Learner Resigned'),
        ('DISMISSED', 'Dismissed'),
        ('HOST_TERMINATED', 'Host Terminated'),
        ('TRANSFERRED', 'Transferred to Another Host'),
        ('MEDICAL', 'Medical Reasons'),
        ('OTHER', 'Other'),
    ]
    
    # Links
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.CASCADE,
        related_name='workplace_placements'
    )
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        on_delete=models.CASCADE,
        related_name='workplace_placements'
    )
    host = models.ForeignKey(
        HostEmployer,
        on_delete=models.PROTECT,
        related_name='placements'
    )
    mentor = models.ForeignKey(
        HostMentor,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='mentees'
    )
    
    # Workplace stint link (QCTO structure)
    workplace_stint = models.ForeignKey(
        WorkplaceStint,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='placements',
        help_text='Which stint requirement this placement fulfills'
    )
    
    # Training Notification link
    training_notification = models.ForeignKey(
        'core.TrainingNotification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='workplace_placements'
    )
    
    # Lead employer (if different from host)
    lead_employer = models.ForeignKey(
        CorporateClient,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='lead_employer_placements',
        help_text='Lead employer if different from host employer'
    )
    
    # Workplace officer assignment
    workplace_officer = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_placements',
        help_text='Assigned workplace monitoring officer'
    )
    
    # Placement Details
    placement_reference = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    expected_end_date = models.DateField()
    actual_end_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    termination_reason = models.CharField(max_length=20, choices=TERMINATION_REASONS, blank=True)
    termination_notes = models.TextField(blank=True)
    
    # Department/Position
    department = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    
    # Stipend configuration
    stipend_daily_rate = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text='Daily stipend rate for this placement'
    )
    stipend_payment_day = models.PositiveIntegerField(
        default=25,
        help_text='Day of month stipend is paid'
    )
    
    # Leave policy
    leave_policy = models.ForeignKey(
        'LeavePolicy',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='placements'
    )
    
    # Documents
    placement_letter = models.FileField(upload_to='placement_letters/', blank=True)
    agreement_signed = models.BooleanField(default=False)
    agreement_date = models.DateField(null=True, blank=True)
    
    # Progress tracking
    logbook_issued = models.BooleanField(default=False)
    logbook_number = models.CharField(max_length=50, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Workplace Placement'
        verbose_name_plural = 'Workplace Placements'
    
    def save(self, *args, **kwargs):
        if not self.placement_reference:
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d%H%M')
            self.placement_reference = f"WPL-{timestamp}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.learner} @ {self.host.company_name}"
    
    @property
    def duration_days(self):
        end = self.actual_end_date or self.expected_end_date
        return (end - self.start_date).days
    
    @property
    def is_active(self):
        return self.status == 'ACTIVE'


class PlacementVisit(AuditedModel):
    """
    Workplace visit record for placement monitoring
    """
    VISIT_TYPE_CHOICES = [
        ('INITIAL', 'Initial Visit'),
        ('ROUTINE', 'Routine Monitoring'),
        ('ASSESSMENT', 'Assessment Visit'),
        ('ISSUE', 'Issue Follow-up'),
        ('FINAL', 'Final/Exit Visit'),
    ]
    
    placement = models.ForeignKey(
        WorkplacePlacement,
        on_delete=models.CASCADE,
        related_name='visits'
    )
    
    visit_type = models.CharField(max_length=20, choices=VISIT_TYPE_CHOICES)
    visit_date = models.DateField()
    visitor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='placement_visits'
    )
    
    # Meeting details
    met_with_learner = models.BooleanField(default=True)
    met_with_mentor = models.BooleanField(default=False)
    met_with_supervisor = models.BooleanField(default=False)
    
    # Assessment
    learner_progress_rating = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Rating 1-5'
    )
    workplace_suitability_rating = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Rating 1-5'
    )
    mentor_support_rating = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Rating 1-5'
    )
    
    # Findings
    findings = models.TextField(blank=True)
    issues_identified = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    
    # Evidence
    visit_report = models.FileField(upload_to='visit_reports/', blank=True)
    photos = models.JSONField(default=list, blank=True)  # List of photo paths
    
    class Meta:
        ordering = ['-visit_date']
        verbose_name = 'Placement Visit'
        verbose_name_plural = 'Placement Visits'
    
    def __str__(self):
        return f"{self.placement} - {self.visit_date}"


# =====================================================
# TRADE TEST ADMINISTRATION MODELS
# =====================================================

class TradeTestVenue(models.Model):
    """
    Trade test venue (NAMB/INDLELA accredited)
    """
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    
    # Location
    address = models.TextField()
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=50)
    
    # Contact
    contact_person = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Accreditation
    accreditation_number = models.CharField(max_length=50, blank=True)
    accreditation_expiry = models.DateField(null=True, blank=True)
    
    # Trades offered
    trades_offered = models.JSONField(
        default=list,
        blank=True,
        help_text='List of trade codes offered at this venue'
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Trade Test Venue'
        verbose_name_plural = 'Trade Test Venues'
    
    def __str__(self):
        return f"{self.name} ({self.city})"


class LegacyTradeTestBooking(TenantAwareModel):
    """
    Trade test booking/scheduling - DEPRECATED: Use trade_tests.TradeTestBooking instead
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Submission'),
        ('SUBMITTED', 'Submitted to NAMB'),
        ('CONFIRMED', 'Confirmed'),
        ('RESCHEDULED', 'Rescheduled'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show'),
    ]
    
    # Learner
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.CASCADE,
        related_name='trade_test_bookings'
    )
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        on_delete=models.CASCADE,
        related_name='trade_test_bookings'
    )
    
    # Qualification/Trade
    qualification = models.ForeignKey(
        'academics.Qualification',
        on_delete=models.PROTECT,
        related_name='trade_test_bookings'
    )
    trade_code = models.CharField(max_length=20, help_text='NAMB trade code')
    
    # Venue
    venue = models.ForeignKey(
        TradeTestVenue,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='bookings'
    )
    
    # Dates
    booking_reference = models.CharField(max_length=50, unique=True)
    submission_date = models.DateField(null=True, blank=True)
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.TimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # NAMB Reference
    namb_reference = models.CharField(max_length=50, blank=True)
    confirmation_letter = models.FileField(upload_to='trade_test_confirmations/', blank=True)
    
    # Training Notification link
    training_notification = models.ForeignKey(
        'core.TrainingNotification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='trade_test_bookings'
    )
    
    # Fees
    booking_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fee_paid = models.BooleanField(default=False)
    fee_payment_date = models.DateField(null=True, blank=True)
    fee_payment_reference = models.CharField(max_length=50, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-scheduled_date']
        verbose_name = 'Legacy Trade Test Booking'
        verbose_name_plural = 'Legacy Trade Test Bookings'
    
    def save(self, *args, **kwargs):
        if not self.booking_reference:
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d%H%M')
            self.booking_reference = f"TTB-{timestamp}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.learner} - {self.trade_code} ({self.booking_reference})"


class LegacyTradeTestResult(AuditedModel):
    """
    Trade test result - DEPRECATED: Use trade_tests.TradeTestResult instead
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
        LegacyTradeTestBooking,
        on_delete=models.CASCADE,
        related_name='results'
    )
    
    # Result details
    section = models.CharField(max_length=20, choices=SECTION_CHOICES)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    score = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text='Percentage score if applicable'
    )
    
    # Dates
    test_date = models.DateField()
    result_date = models.DateField(null=True, blank=True)
    
    # Certificate (for competent results)
    certificate_number = models.CharField(max_length=50, blank=True)
    certificate_date = models.DateField(null=True, blank=True)
    certificate_file = models.FileField(upload_to='trade_test_certificates/', blank=True)
    
    # Comments
    assessor_comments = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-test_date']
        verbose_name = 'Legacy Trade Test Result'
        verbose_name_plural = 'Legacy Trade Test Results'
        unique_together = ['booking', 'section']
    
    def __str__(self):
        return f"{self.booking.learner} - {self.section}: {self.result}"


class LegacyTradeTestAppeal(AuditedModel):
    """
    Trade test result appeal - DEPRECATED: Use trade_tests.TradeTestAppeal instead
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
        LegacyTradeTestResult,
        on_delete=models.CASCADE,
        related_name='appeals'
    )
    
    # Appeal details
    appeal_date = models.DateField()
    grounds = models.TextField(help_text='Grounds for appeal')
    supporting_documents = models.FileField(upload_to='trade_test_appeals/', blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUBMITTED')
    
    # Resolution
    resolution_date = models.DateField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    new_result = models.CharField(max_length=20, choices=LegacyTradeTestResult.RESULT_CHOICES, blank=True)
    
    # Re-test
    retest_date = models.DateField(null=True, blank=True)
    retest_booking = models.ForeignKey(
        LegacyTradeTestBooking,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='appeal_retests'
    )
    
    class Meta:
        ordering = ['-appeal_date']
        verbose_name = 'Legacy Trade Test Appeal'
        verbose_name_plural = 'Legacy Trade Test Appeals'
    
    def __str__(self):
        return f"Appeal - {self.result.booking.learner}"


# =====================================================
# CRM PIPELINE MODELS
# =====================================================

class LeadSource(models.Model):
    """
    Source of corporate leads/opportunities
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Lead Source'
        verbose_name_plural = 'Lead Sources'
    
    def __str__(self):
        return self.name


class CorporateOpportunity(TenantAwareModel):
    """
    Sales opportunity/deal for corporate client - tracks the sales pipeline
    """
    OPPORTUNITY_TYPE_CHOICES = [
        ('NEW_CLIENT', 'New Client'),
        ('NEW_SERVICE', 'New Service (Existing Client)'),
        ('UPSELL', 'Upsell'),
        ('CROSS_SELL', 'Cross-sell'),
        ('RENEWAL', 'Renewal'),
        ('EXPANSION', 'Expansion'),
    ]
    
    STAGE_CHOICES = [
        ('IDENTIFIED', 'Identified'),
        ('QUALIFIED', 'Qualified'),
        ('NEEDS_ANALYSIS', 'Needs Analysis'),
        ('PROPOSAL', 'Proposal Sent'),
        ('NEGOTIATION', 'Negotiation'),
        ('CLOSED_WON', 'Closed Won'),
        ('CLOSED_LOST', 'Closed Lost'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    # Auto-generated reference
    reference_number = models.CharField(max_length=20, unique=True, editable=False)
    
    # Client link (optional for new prospects)
    client = models.ForeignKey(
        CorporateClient,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='opportunities'
    )
    
    # Prospect info (for new clients not yet in system)
    prospect_company_name = models.CharField(max_length=200, blank=True)
    prospect_contact_name = models.CharField(max_length=100, blank=True)
    prospect_email = models.EmailField(blank=True)
    prospect_phone = models.CharField(max_length=20, blank=True)
    
    # Opportunity details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    opportunity_type = models.CharField(max_length=20, choices=OPPORTUNITY_TYPE_CHOICES, default='NEW_CLIENT')
    
    # Pipeline stage
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='IDENTIFIED')
    stage_changed_date = models.DateField(auto_now=True)
    
    # Services proposed (M2M to ServiceOffering)
    proposed_services = models.ManyToManyField(
        'ServiceOffering',
        blank=True,
        related_name='opportunities'
    )
    
    # Value
    estimated_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True, blank=True,
        help_text='Estimated total deal value'
    )
    probability = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Win probability percentage'
    )
    
    @property
    def weighted_value(self):
        if self.estimated_value and self.probability:
            return self.estimated_value * Decimal(self.probability) / 100
        return Decimal('0.00')
    
    # Dates
    expected_close_date = models.DateField(null=True, blank=True)
    actual_close_date = models.DateField(null=True, blank=True)
    
    # Source
    lead_source = models.ForeignKey(
        LeadSource,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='opportunities'
    )
    referral_source = models.CharField(max_length=200, blank=True)
    
    # Owner
    sales_owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='owned_opportunities'
    )
    
    # Priority
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Loss reason (if closed lost)
    loss_reason = models.TextField(blank=True)
    competitor = models.CharField(max_length=200, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Corporate Opportunity'
        verbose_name_plural = 'Corporate Opportunities'
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            from django.utils import timezone
            year_month = timezone.now().strftime('%Y%m')
            last_opp = CorporateOpportunity.objects.filter(
                reference_number__startswith=f'OPP-{year_month}'
            ).order_by('-reference_number').first()
            if last_opp:
                last_num = int(last_opp.reference_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            self.reference_number = f'OPP-{year_month}-{new_num:04d}'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.reference_number} - {self.title}"
    
    @property
    def client_name(self):
        if self.client:
            return self.client.company_name
        return self.prospect_company_name or 'Unknown'
    
    @property
    def is_open(self):
        return self.stage not in ['CLOSED_WON', 'CLOSED_LOST']
    
    @property
    def days_in_pipeline(self):
        from django.utils import timezone
        return (timezone.now().date() - self.created_at.date()).days


class CorporateActivity(AuditedModel):
    """
    Activity log for corporate clients and opportunities
    """
    ACTIVITY_TYPE_CHOICES = [
        ('CALL', 'Phone Call'),
        ('EMAIL', 'Email'),
        ('MEETING', 'Meeting'),
        ('VIDEO_CALL', 'Video Call'),
        ('SITE_VISIT', 'Site Visit'),
        ('PROPOSAL_SENT', 'Proposal Sent'),
        ('PRESENTATION', 'Presentation'),
        ('FOLLOW_UP', 'Follow-up'),
        ('NOTE', 'Note'),
        ('TASK', 'Task'),
    ]
    
    OUTCOME_CHOICES = [
        ('POSITIVE', 'Positive'),
        ('NEUTRAL', 'Neutral'),
        ('NEGATIVE', 'Negative'),
        ('NO_ANSWER', 'No Answer'),
        ('CALLBACK', 'Callback Requested'),
    ]
    
    # Link to client OR opportunity (at least one required)
    client = models.ForeignKey(
        CorporateClient,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    opportunity = models.ForeignKey(
        CorporateOpportunity,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    
    # Activity details
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES)
    subject = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Timing
    activity_date = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    
    # Participants
    contact = models.ForeignKey(
        CorporateContact,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='activities'
    )
    participants = models.TextField(blank=True, help_text='Other participants')
    
    # Outcome
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True)
    outcome_notes = models.TextField(blank=True)
    
    # Follow-up
    next_action = models.CharField(max_length=200, blank=True)
    next_action_date = models.DateField(null=True, blank=True)
    follow_up_assigned_to = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_follow_ups'
    )
    
    # Completed flag for tasks
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-activity_date']
        verbose_name = 'Corporate Activity'
        verbose_name_plural = 'Corporate Activities'
    
    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.subject}"


class ServiceProposal(TenantAwareModel):
    """
    Formal proposal/quote for corporate client
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('INTERNAL_REVIEW', 'Internal Review'),
        ('SENT', 'Sent to Client'),
        ('VIEWED', 'Viewed by Client'),
        ('UNDER_CONSIDERATION', 'Under Consideration'),
        ('REVISION_REQUESTED', 'Revision Requested'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    ]
    
    VALIDITY_DAYS = 30  # Default validity period
    
    # Auto-generated reference
    proposal_number = models.CharField(max_length=20, unique=True, editable=False)
    
    # Links
    opportunity = models.ForeignKey(
        CorporateOpportunity,
        on_delete=models.CASCADE,
        related_name='proposals'
    )
    client = models.ForeignKey(
        CorporateClient,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='proposals'
    )
    
    # Proposal details
    title = models.CharField(max_length=200)
    introduction = models.TextField(blank=True, help_text='Introduction/cover letter text')
    scope_of_work = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Dates
    proposal_date = models.DateField(auto_now_add=True)
    valid_until = models.DateField(null=True, blank=True)
    sent_date = models.DateTimeField(null=True, blank=True)
    viewed_date = models.DateTimeField(null=True, blank=True)
    response_date = models.DateTimeField(null=True, blank=True)
    
    # Pricing
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('15.00'))
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Contact
    prepared_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='prepared_proposals'
    )
    contact_person = models.ForeignKey(
        CorporateContact,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='proposals_received'
    )
    
    # Document
    proposal_document = models.FileField(upload_to='proposals/', blank=True)
    
    # Client response
    rejection_reason = models.TextField(blank=True)
    client_feedback = models.TextField(blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-proposal_date']
        verbose_name = 'Service Proposal'
        verbose_name_plural = 'Service Proposals'
    
    def save(self, *args, **kwargs):
        if not self.proposal_number:
            from django.utils import timezone
            year_month = timezone.now().strftime('%Y%m')
            last_prop = ServiceProposal.objects.filter(
                proposal_number__startswith=f'PROP-{year_month}'
            ).order_by('-proposal_number').first()
            if last_prop:
                last_num = int(last_prop.proposal_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            self.proposal_number = f'PROP-{year_month}-{new_num:04d}'
        
        # Set valid_until if not set
        if not self.valid_until and self.proposal_date:
            from django.utils import timezone
            from datetime import timedelta
            self.valid_until = self.proposal_date + timedelta(days=self.VALIDITY_DAYS)
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.proposal_number} - {self.title}"
    
    def calculate_totals(self):
        """Recalculate totals from line items."""
        self.subtotal = sum(item.line_total for item in self.line_items.all())
        if self.discount_percentage > 0:
            self.discount_amount = self.subtotal * self.discount_percentage / 100
        self.vat_amount = (self.subtotal - self.discount_amount) * self.vat_percentage / 100
        self.total_amount = self.subtotal - self.discount_amount + self.vat_amount
        self.save()


class ProposalLineItem(models.Model):
    """
    Line item in a proposal
    """
    proposal = models.ForeignKey(
        ServiceProposal,
        on_delete=models.CASCADE,
        related_name='line_items'
    )
    
    # Service (optional - can be custom line)
    service = models.ForeignKey(
        'ServiceOffering',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='proposal_lines'
    )
    
    # Line details
    description = models.CharField(max_length=500)
    details = models.TextField(blank=True)
    
    # Pricing
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    unit = models.CharField(max_length=50, default='each')  # each, per learner, per month, etc.
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    @property
    def line_total(self):
        return self.quantity * self.unit_price
    
    # Ordering
    sequence = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['sequence']
        verbose_name = 'Proposal Line Item'
        verbose_name_plural = 'Proposal Line Items'
    
    def __str__(self):
        return f"{self.proposal.proposal_number} - {self.description}"


# =====================================================
# SERVICE DELIVERY PROJECT MANAGEMENT
# =====================================================

class ServiceDeliveryProject(TenantAwareModel):
    """
    Project for delivering a subscribed service
    Links ClientServiceSubscription to project management
    """
    STATUS_CHOICES = [
        ('SETUP', 'Setup/Onboarding'),
        ('PLANNING', 'Planning'),
        ('IN_PROGRESS', 'In Progress'),
        ('ON_HOLD', 'On Hold'),
        ('REVIEW', 'Under Review'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    HEALTH_CHOICES = [
        ('GREEN', 'On Track'),
        ('AMBER', 'At Risk'),
        ('RED', 'Critical'),
    ]
    
    # Auto-generated reference
    project_number = models.CharField(max_length=20, unique=True, editable=False)
    
    # Links
    subscription = models.OneToOneField(
        'ClientServiceSubscription',
        on_delete=models.CASCADE,
        related_name='delivery_project'
    )
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='delivery_projects'
    )
    
    # Training Notification link (for training-related services)
    training_notification = models.ForeignKey(
        'core.TrainingNotification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='delivery_projects'
    )
    
    # Project details
    name = models.CharField(max_length=200, blank=True)
    implementation_year = models.PositiveIntegerField(null=True, blank=True, help_text='Implementation year cycle e.g. 2024, 2025')
    description = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SETUP')
    health = models.CharField(max_length=10, choices=HEALTH_CHOICES, default='GREEN')
    health_notes = models.TextField(blank=True)
    
    # Progress
    progress_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Dates
    planned_start_date = models.DateField(null=True, blank=True)
    actual_start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    
    # Team
    project_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_delivery_projects'
    )
    team_members = models.ManyToManyField(
        User,
        blank=True,
        related_name='delivery_project_teams'
    )
    
    # Client contact
    client_contact = models.ForeignKey(
        CorporateContact,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='delivery_projects'
    )
    
    # Budget (if tracked separately from subscription)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Service Delivery Project'
        verbose_name_plural = 'Service Delivery Projects'
    
    def save(self, *args, **kwargs):
        if not self.project_number:
            from django.utils import timezone
            year_month = timezone.now().strftime('%Y%m')
            last_proj = ServiceDeliveryProject.objects.filter(
                project_number__startswith=f'PROJ-{year_month}'
            ).order_by('-project_number').first()
            if last_proj:
                last_num = int(last_proj.project_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            self.project_number = f'PROJ-{year_month}-{new_num:04d}'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.project_number} - {self.name}"
    
    def update_progress(self):
        """Calculate progress from milestones."""
        milestones = self.milestones.all()
        if milestones.exists():
            completed = milestones.filter(status='COMPLETED').count()
            self.progress_percentage = int((completed / milestones.count()) * 100)
            self.save()
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.planned_end_date and self.status not in ['COMPLETED', 'CANCELLED']:
            return timezone.now().date() > self.planned_end_date
        return False


class ProjectMilestone(AuditedModel):
    """
    Milestone/phase in a service delivery project
    """
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('BLOCKED', 'Blocked'),
        ('COMPLETED', 'Completed'),
        ('SKIPPED', 'Skipped'),
    ]
    
    project = models.ForeignKey(
        ServiceDeliveryProject,
        on_delete=models.CASCADE,
        related_name='milestones'
    )
    
    # Milestone details
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    sequence = models.PositiveIntegerField(default=1)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOT_STARTED')
    
    # Dates
    planned_start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_milestones'
    )
    
    # Weight for progress calculation
    weight = models.PositiveIntegerField(default=1)
    
    # Evidence/deliverables
    requires_evidence = models.BooleanField(default=False)
    evidence_description = models.TextField(blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['sequence']
        verbose_name = 'Project Milestone'
        verbose_name_plural = 'Project Milestones'
    
    def __str__(self):
        return f"{self.project.project_number} - {self.name}"
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.planned_end_date and self.status not in ['COMPLETED', 'SKIPPED']:
            return timezone.now().date() > self.planned_end_date
        return False


class MilestoneTask(AuditedModel):
    """
    Task within a project milestone (Service Delivery)
    """
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('TODO', 'To Do'),
        ('IN_PROGRESS', 'In Progress'),
        ('BLOCKED', 'Blocked'),
        ('DONE', 'Done'),
    ]
    
    milestone = models.ForeignKey(
        ProjectMilestone,
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    
    # Task details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TODO')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='milestone_tasks'
    )
    
    # Dates
    due_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    
    # Effort
    estimated_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    # Client portal visibility
    client_visible = models.BooleanField(
        default=True,
        help_text='Show this task in client portal'
    )
    requires_evidence = models.BooleanField(
        default=False,
        help_text='This task requires evidence upload for completion'
    )
    
    # Completion tracking
    completed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='completed_milestone_tasks',
        help_text='Staff member who marked this task complete'
    )
    completed_by_contact = models.ForeignKey(
        'CorporateContact',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='completed_tasks',
        help_text='Client contact who marked this task complete'
    )
    completion_notes = models.TextField(
        blank=True,
        help_text='Notes added when task was completed'
    )
    
    class Meta:
        ordering = ['priority', 'due_date']
        verbose_name = 'Milestone Task'
        verbose_name_plural = 'Milestone Tasks'
    
    def __str__(self):
        return f"{self.milestone.project.project_number} - {self.title}"
    
    @property
    def has_required_evidence(self):
        """Check if task has evidence when required"""
        if not self.requires_evidence:
            return True
        return self.evidence.exists()


def validate_evidence_file_extension(value):
    """Validate that uploaded evidence files are allowed types"""
    import os
    from django.core.exceptions import ValidationError
    
    allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            f'File type "{ext}" is not allowed. Allowed types: {", ".join(allowed_extensions)}'
        )


class TaskEvidence(AuditedModel):
    """
    Evidence file attached directly to a milestone task.
    Used by account managers and SDFs to upload proof of task completion.
    """
    task = models.ForeignKey(
        MilestoneTask,
        on_delete=models.CASCADE,
        related_name='evidence'
    )
    
    # File details
    name = models.CharField(max_length=200, help_text='Name/description of this evidence')
    description = models.TextField(blank=True)
    
    # File with validation for allowed types
    file = models.FileField(
        upload_to='task_evidence/',
        validators=[validate_evidence_file_extension],
        help_text='Allowed: PDF, Word, Excel, Images (JPG, PNG, GIF)'
    )
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text='File size in bytes')
    
    # Who uploaded (either staff user or client contact)
    uploaded_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='uploaded_task_evidence',
        help_text='Staff member who uploaded this evidence'
    )
    uploaded_by_contact = models.ForeignKey(
        'CorporateContact',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='uploaded_evidence',
        help_text='Client contact who uploaded this evidence'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task Evidence'
        verbose_name_plural = 'Task Evidence'
    
    def __str__(self):
        return f"{self.task.title} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate file size
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)
    
    @property
    def file_extension(self):
        import os
        return os.path.splitext(self.file.name)[1].lower() if self.file else ''
    
    @property
    def is_image(self):
        return self.file_extension in ['.jpg', '.jpeg', '.png', '.gif']


class ProjectDocument(AuditedModel):
    """
    Document/evidence attached to a project or milestone
    """
    DOCUMENT_TYPE_CHOICES = [
        ('CONTRACT', 'Contract'),
        ('PROPOSAL', 'Proposal'),
        ('REPORT', 'Report'),
        ('EVIDENCE', 'Evidence'),
        ('CORRESPONDENCE', 'Correspondence'),
        ('DELIVERABLE', 'Deliverable'),
        ('OTHER', 'Other'),
    ]
    
    project = models.ForeignKey(
        ServiceDeliveryProject,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    milestone = models.ForeignKey(
        ProjectMilestone,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='documents'
    )
    
    # Document details
    name = models.CharField(max_length=200)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # File
    file = models.FileField(upload_to='project_documents/')
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    # Metadata
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_project_documents'
    )
    upload_date = models.DateTimeField(auto_now_add=True)
    
    # Version tracking
    version = models.CharField(max_length=20, default='1.0')
    replaces = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='replaced_by'
    )
    
    class Meta:
        ordering = ['-upload_date']
        verbose_name = 'Project Document'
        verbose_name_plural = 'Project Documents'
    
    def __str__(self):
        return f"{self.project.project_number} - {self.name}"


# =====================================================
# SERVICE DELIVERY TEMPLATES
# =====================================================

class ServiceDeliveryTemplate(models.Model):
    """
    Pre-defined milestone template for a service type
    """
    service_type = models.CharField(
        max_length=30,
        choices=ServiceOffering.SERVICE_TYPE_CHOICES,
        unique=True
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Estimated duration
    default_duration_days = models.PositiveIntegerField(default=30)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Service Delivery Template'
        verbose_name_plural = 'Service Delivery Templates'
    
    def __str__(self):
        return f"{self.name} ({self.get_service_type_display()})"
    
    def create_project_milestones(self, project):
        """
        Create milestones for a project based on this template.
        """
        for template_item in self.milestones.all():
            ProjectMilestone.objects.create(
                project=project,
                name=template_item.name,
                description=template_item.description,
                sequence=template_item.sequence,
                weight=template_item.weight,
                requires_evidence=template_item.requires_evidence,
                evidence_description=template_item.evidence_description,
            )


class ServiceDeliveryTemplateMilestone(models.Model):
    """
    Milestone template item
    """
    template = models.ForeignKey(
        ServiceDeliveryTemplate,
        on_delete=models.CASCADE,
        related_name='milestones'
    )
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    sequence = models.PositiveIntegerField(default=1)
    
    # Timing (days from project start)
    days_from_start = models.PositiveIntegerField(default=0)
    duration_days = models.PositiveIntegerField(default=7)
    
    # Weight for progress calculation
    weight = models.PositiveIntegerField(default=1)
    
    # Evidence requirements
    requires_evidence = models.BooleanField(default=False)
    evidence_description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['sequence']
        verbose_name = 'Template Milestone'
        verbose_name_plural = 'Template Milestones'
    
    def __str__(self):
        return f"{self.template.name} - {self.name}"


# =====================================================
# WSP/ATR SERVICE DELIVERY ENHANCEMENT
# =====================================================

class WSPATRServiceYear(TenantAwareModel):
    """
    Tracks WSP/ATR service delivery for a specific financial year.
    One record per client subscription per financial year.
    """
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('DATA_COLLECTION', 'Data Collection'),
        ('DRAFTING', 'Drafting'),
        ('INTERNAL_REVIEW', 'Internal Review'),
        ('CLIENT_REVIEW', 'Client Review'),
        ('SUBMITTED', 'Submitted to SETA'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected - Resubmission Required'),
        ('COMPLETED', 'Completed'),
    ]
    
    OUTCOME_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('APPROVED_CONDITIONS', 'Approved with Conditions'),
        ('REJECTED', 'Rejected'),
        ('NOT_SUBMITTED', 'Not Submitted'),
    ]
    
    subscription = models.ForeignKey(
        ClientServiceSubscription,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='wspatr_years'
    )
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='wspatr_service_years'
    )
    
    # Financial year (e.g., 2024 means 1 May 2024 - 30 April 2025)
    financial_year = models.PositiveIntegerField(
        help_text='Financial year start (e.g., 2024 for 1 May 2024 - 30 April 2025)'
    )
    
    # Link to actual WSP/ATR submissions (existing models)
    wsp_submission = models.OneToOneField(
        'WSPSubmission',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='service_year'
    )
    atr_submission = models.OneToOneField(
        'ATRSubmission',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='service_year'
    )
    
    # Status and outcome
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='NOT_STARTED')
    outcome = models.CharField(max_length=30, choices=OUTCOME_CHOICES, default='PENDING')
    
    # Key dates - submission_deadline auto-calculated if not provided
    submission_deadline = models.DateField(
        null=True, blank=True,
        help_text='SETA submission deadline (typically 30 April)'
    )
    submitted_date = models.DateField(null=True, blank=True)
    outcome_date = models.DateField(null=True, blank=True)
    
    # SETA info
    seta = models.ForeignKey(
        'learners.SETA',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='wspatr_service_years'
    )
    seta_reference = models.CharField(max_length=100, blank=True)
    seta_feedback = models.TextField(blank=True)
    
    # Assignment
    assigned_consultant = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_wspatr_years'
    )
    
    # Progress tracking (0-100)
    progress_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-financial_year', 'client__company_name']
        unique_together = ['client', 'financial_year']
        verbose_name = 'WSP/ATR Service Year'
        verbose_name_plural = 'WSP/ATR Service Years'
    
    def save(self, *args, **kwargs):
        # Auto-calculate submission deadline if not provided
        if not self.submission_deadline and self.financial_year:
            from datetime import date
            self.submission_deadline = date(self.financial_year + 1, 4, 30)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.client.company_name} - FY{self.financial_year}/{self.financial_year + 1}"
    
    @property
    def financial_year_display(self):
        return f"FY{self.financial_year}/{str(self.financial_year + 1)[-2:]}"
    
    @property
    def cycle_start_date(self):
        from datetime import date
        return date(self.financial_year, 5, 1)

    @property
    def cycle_end_date(self):
        from datetime import date
        return date(self.financial_year + 1, 4, 30)
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.status not in ['SUBMITTED', 'ACCEPTED', 'COMPLETED']:
            return timezone.now().date() > self.submission_deadline
        return False
    
    @property
    def days_until_deadline(self):
        from django.utils import timezone
        if self.submitted_date:
            return None
        delta = self.submission_deadline - timezone.now().date()
        return delta.days
    
    @property
    def approval_letter(self):
        """Get the approval letter document if uploaded."""
        return self.documents.filter(document_type='APPROVAL_LETTER').first()
    
    def calculate_progress(self):
        """Calculate submission progress based on required documents."""
        required_docs = self.documents.filter(is_required=True)
        if not required_docs.exists():
            return self.progress_percentage
        
        uploaded = required_docs.exclude(file='').count()
        total = required_docs.count()
        return int((uploaded / total) * 100) if total > 0 else 0
    
    def update_progress(self):
        """Update the progress percentage based on document completion."""
        self.progress_percentage = self.calculate_progress()
        self.save(update_fields=['progress_percentage'])


class WSPATRDocument(TenantAwareModel):
    """
    Documents required for WSP/ATR submission.
    Tracks required documents, uploaded files, and completion status.
    """
    DOCUMENT_TYPE_CHOICES = [
        # Required documents for submission
        ('SDL_CERTIFICATE', 'SDL Certificate'),
        ('COMPANY_REGISTRATION', 'Company Registration (CIPC)'),
        ('BEE_CERTIFICATE', 'B-BBEE Certificate'),
        ('TAX_CLEARANCE', 'Tax Clearance Certificate'),
        ('EMPLOYEE_LIST', 'Employee List/Headcount'),
        ('TRAINING_PLAN', 'Training Plan'),
        ('TRAINING_BUDGET', 'Training Budget'),
        ('COMMITTEE_MINUTES', 'Training Committee Minutes'),
        ('COMMITTEE_ATTENDANCE', 'Training Committee Attendance Register'),
        ('ATR_EVIDENCE', 'ATR Training Evidence/POE'),
        ('PIVOTAL_EVIDENCE', 'PIVOTAL Training Evidence'),
        ('SKILLS_AUDIT', 'Skills Audit Report'),
        ('ORGANOGRAM', 'Company Organogram'),
        ('SIGNED_WSP', 'Signed WSP Document'),
        ('SIGNED_ATR', 'Signed ATR Document'),
        # Output/result documents
        ('APPROVAL_LETTER', 'WSP Approval Letter from SETA'),
        ('GRANT_LETTER', 'Mandatory Grant Letter'),
        ('REJECTION_LETTER', 'Rejection/Query Letter'),
        ('SUBMISSION_RECEIPT', 'Submission Receipt/Confirmation'),
        # Other
        ('OTHER', 'Other Document'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Upload'),
        ('UPLOADED', 'Uploaded'),
        ('APPROVED', 'Approved/Verified'),
        ('REJECTED', 'Rejected - Reupload Required'),
        ('NOT_APPLICABLE', 'Not Applicable'),
    ]
    
    service_year = models.ForeignKey(
        WSPATRServiceYear,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    # Optional link to a specific meeting
    meeting = models.ForeignKey(
        'TrainingCommitteeMeeting',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='wspatr_documents'
    )
    
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    name = models.CharField(max_length=200, blank=True, help_text='Custom document name (optional)')
    description = models.TextField(blank=True)
    
    # File upload
    file = models.FileField(
        upload_to='wspatr_documents/%Y/%m/',
        null=True, blank=True
    )
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='uploaded_wspatr_documents'
    )
    
    # Requirements
    is_required = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Review
    reviewed_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_wspatr_documents'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    # Ordering
    sort_order = models.PositiveIntegerField(default=0)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['sort_order', 'document_type']
        verbose_name = 'WSP/ATR Document'
        verbose_name_plural = 'WSP/ATR Documents'
    
    def __str__(self):
        name = self.name or self.get_document_type_display()
        return f"{self.service_year} - {name}"
    
    @property
    def display_name(self):
        return self.name or self.get_document_type_display()
    
    @property
    def is_uploaded(self):
        return bool(self.file)
    
    def save(self, *args, **kwargs):
        if self.file:
            if not self.file_name:
                self.file_name = self.file.name.split('/')[-1]
            if not self.file_size:
                try:
                    self.file_size = self.file.size
                except:
                    pass
            if not self.uploaded_at:
                from django.utils import timezone
                self.uploaded_at = timezone.now()
            if self.status == 'PENDING':
                self.status = 'UPLOADED'
        super().save(*args, **kwargs)


class WSPATRDocumentTemplate(TenantAwareModel):
    """
    Template defining which documents are required for WSP/ATR submissions.
    Can be SETA-specific to handle different requirements per SETA.
    """
    seta = models.ForeignKey(
        'learners.SETA',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='wspatr_document_templates',
        help_text='Leave blank for default template'
    )
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # JSON list of required documents
    # Format: [{"document_type": "SDL_CERTIFICATE", "is_required": true, "notes": "..."}]
    required_documents = models.JSONField(
        default=list,
        help_text='List of required document types and their settings'
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['seta__name', 'name']
        verbose_name = 'WSP/ATR Document Template'
        verbose_name_plural = 'WSP/ATR Document Templates'
    
    def __str__(self):
        seta_name = self.seta.name if self.seta else 'Default'
        return f"{seta_name} - {self.name}"
    
    def create_documents_for_service_year(self, service_year):
        """
        Create document records for a service year based on this template.
        """
        documents_created = []
        for idx, doc_config in enumerate(self.required_documents):
            doc = WSPATRDocument.objects.create(
                service_year=service_year,
                document_type=doc_config.get('document_type', 'OTHER'),
                name=doc_config.get('name', ''),
                description=doc_config.get('notes', ''),
                is_required=doc_config.get('is_required', True),
                sort_order=idx
            )
            documents_created.append(doc)
        return documents_created


class WSPATREmployeeData(models.Model):
    """
    Employee headcount data for WSP/ATR submission.
    Captures workforce profile by demographics.
    """
    OCCUPATIONAL_LEVEL_CHOICES = [
        ('TOP_MANAGEMENT', 'Top Management'),
        ('SENIOR_MANAGEMENT', 'Senior Management'),
        ('PROFESSIONAL', 'Professionally Qualified'),
        ('SKILLED_TECHNICAL', 'Skilled Technical'),
        ('SEMI_SKILLED', 'Semi-Skilled'),
        ('UNSKILLED', 'Unskilled'),
    ]
    
    service_year = models.ForeignKey(
        WSPATRServiceYear,
        on_delete=models.CASCADE,
        related_name='employee_data'
    )
    
    occupational_level = models.CharField(max_length=30, choices=OCCUPATIONAL_LEVEL_CHOICES)
    
    # Demographics - Male
    african_male = models.PositiveIntegerField(default=0)
    coloured_male = models.PositiveIntegerField(default=0)
    indian_male = models.PositiveIntegerField(default=0)
    white_male = models.PositiveIntegerField(default=0)
    foreign_male = models.PositiveIntegerField(default=0)
    
    # Demographics - Female
    african_female = models.PositiveIntegerField(default=0)
    coloured_female = models.PositiveIntegerField(default=0)
    indian_female = models.PositiveIntegerField(default=0)
    white_female = models.PositiveIntegerField(default=0)
    foreign_female = models.PositiveIntegerField(default=0)
    
    # Disability
    disabled_male = models.PositiveIntegerField(default=0)
    disabled_female = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['occupational_level']
        unique_together = ['service_year', 'occupational_level']
        verbose_name = 'WSP/ATR Employee Data'
        verbose_name_plural = 'WSP/ATR Employee Data'
    
    def __str__(self):
        return f"{self.service_year} - {self.get_occupational_level_display()}"
    
    @property
    def total_male(self):
        return self.african_male + self.coloured_male + self.indian_male + self.white_male + self.foreign_male
    
    @property
    def total_female(self):
        return self.african_female + self.coloured_female + self.indian_female + self.white_female + self.foreign_female
    
    @property
    def total(self):
        return self.total_male + self.total_female


class WSPATRTrainingData(models.Model):
    """
    Training intervention data for WSP (planned) or ATR (actual).
    """
    DATA_TYPE_CHOICES = [
        ('PLANNED', 'WSP Planned'),
        ('ACTUAL', 'ATR Actual'),
    ]
    
    INTERVENTION_TYPE_CHOICES = [
        ('LEARNERSHIP', 'Learnership'),
        ('SKILLS_PROGRAMME', 'Skills Programme'),
        ('APPRENTICESHIP', 'Apprenticeship'),
        ('INTERNSHIP', 'Internship'),
        ('BURSARY', 'Bursary'),
        ('SHORT_COURSE', 'Short Course'),
        ('ARTISAN', 'Artisan Development'),
        ('AET', 'Adult Education & Training'),
        ('OTHER', 'Other'),
    ]
    
    service_year = models.ForeignKey(
        WSPATRServiceYear,
        on_delete=models.CASCADE,
        related_name='training_data'
    )
    
    data_type = models.CharField(max_length=10, choices=DATA_TYPE_CHOICES)
    intervention_type = models.CharField(max_length=20, choices=INTERVENTION_TYPE_CHOICES)
    
    # Programme details
    qualification = models.ForeignKey(
        'academics.Qualification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='wspatr_training_data'
    )
    programme_name = models.CharField(max_length=200)
    nqf_level = models.PositiveIntegerField(null=True, blank=True)
    
    # Demographics
    african_male = models.PositiveIntegerField(default=0)
    african_female = models.PositiveIntegerField(default=0)
    coloured_male = models.PositiveIntegerField(default=0)
    coloured_female = models.PositiveIntegerField(default=0)
    indian_male = models.PositiveIntegerField(default=0)
    indian_female = models.PositiveIntegerField(default=0)
    white_male = models.PositiveIntegerField(default=0)
    white_female = models.PositiveIntegerField(default=0)
    
    disabled_male = models.PositiveIntegerField(default=0)
    disabled_female = models.PositiveIntegerField(default=0)
    
    # Cost
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['data_type', 'intervention_type']
        verbose_name = 'WSP/ATR Training Data'
        verbose_name_plural = 'WSP/ATR Training Data'
    
    def __str__(self):
        return f"{self.service_year} - {self.get_data_type_display()} - {self.programme_name}"
    
    @property
    def total_learners(self):
        return (
            self.african_male + self.african_female +
            self.coloured_male + self.coloured_female +
            self.indian_male + self.indian_female +
            self.white_male + self.white_female
        )


class WSPATRPivotalData(models.Model):
    """
    PIVOTAL (Professional, Vocational, Technical and Academic Learning) data.
    Required for discretionary grant applications.
    """
    service_year = models.ForeignKey(
        WSPATRServiceYear,
        on_delete=models.CASCADE,
        related_name='pivotal_data'
    )
    
    PIVOTAL_TYPE_CHOICES = [
        ('LEARNERSHIP_18_1', 'Learnership 18.1 (Employed)'),
        ('LEARNERSHIP_18_2', 'Learnership 18.2 (Unemployed)'),
        ('SKILLS_PROGRAMME', 'Skills Programme'),
        ('APPRENTICESHIP', 'Apprenticeship'),
        ('INTERNSHIP', 'Internship'),
        ('BURSARY_EMPLOYED', 'Bursary (Employed)'),
        ('BURSARY_UNEMPLOYED', 'Bursary (Unemployed)'),
        ('CANDIDACY', 'Candidacy Programme'),
        ('WIL', 'Work Integrated Learning'),
    ]
    
    pivotal_type = models.CharField(max_length=30, choices=PIVOTAL_TYPE_CHOICES)
    programme_name = models.CharField(max_length=200)
    
    # Number of beneficiaries
    planned_beneficiaries = models.PositiveIntegerField(default=0)
    actual_beneficiaries = models.PositiveIntegerField(default=0)
    
    # Cost
    planned_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['pivotal_type']
        verbose_name = 'WSP/ATR PIVOTAL Data'
        verbose_name_plural = 'WSP/ATR PIVOTAL Data'
    
    def __str__(self):
        return f"{self.service_year} - {self.get_pivotal_type_display()}"


# =====================================================
# TRAINING COMMITTEE MANAGEMENT
# =====================================================

class TrainingCommittee(TenantAwareModel):
    """
    Training Committee for a corporate client.
    Required for Skills Development compliance.
    Can also serve as EE Committee, B-BBEE Transformation Committee, or Combined.
    """
    COMMITTEE_FUNCTION_CHOICES = [
        ('TRAINING_ONLY', 'Training Committee Only'),
        ('EE_ONLY', 'EE Committee Only'),
        ('BBBEE_ONLY', 'B-BBEE Transformation Committee Only'),
        ('COMBINED', 'Combined Training & EE Committee'),
        ('TRAINING_BBBEE', 'Combined Training & B-BBEE Committee'),
        ('EE_BBBEE', 'Combined EE & B-BBEE Committee'),
        ('ALL', 'All Committees (Training, EE & B-BBEE)'),
    ]
    
    client = models.OneToOneField(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='training_committee'
    )
    
    name = models.CharField(max_length=200, default='Training Committee')
    
    # Committee function - Training, EE, B-BBEE, or Combined
    committee_function = models.CharField(
        max_length=20,
        choices=COMMITTEE_FUNCTION_CHOICES,
        default='TRAINING_ONLY',
        help_text='Whether this committee handles Training, EE, B-BBEE, or combinations thereof'
    )
    is_ee_committee = models.BooleanField(
        default=False,
        help_text='Committee handles Employment Equity matters'
    )
    is_bbbee_committee = models.BooleanField(
        default=False,
        help_text='Committee handles B-BBEE transformation matters'
    )
    
    # Constitution details (Training)
    constitution_date = models.DateField(null=True, blank=True, help_text='Date committee was constituted')
    constitution_document = models.FileField(
        upload_to='training_committees/constitutions/',
        null=True, blank=True
    )
    
    # EE-specific constitution (if separate from training)
    ee_constitution_date = models.DateField(
        null=True, blank=True,
        help_text='Date EE committee was constituted (if separate)'
    )
    ee_constitution_document = models.FileField(
        upload_to='training_committees/ee_constitutions/',
        null=True, blank=True
    )
    
    # B-BBEE-specific constitution (if separate)
    bbbee_constitution_date = models.DateField(
        null=True, blank=True,
        help_text='Date B-BBEE transformation committee was constituted (if separate)'
    )
    bbbee_constitution_document = models.FileField(
        upload_to='training_committees/bbbee_constitutions/',
        null=True, blank=True
    )
    
    # Meeting frequency
    MEETING_FREQUENCY_CHOICES = [
        ('QUARTERLY', 'Quarterly (4 per year)'),
        ('BI_MONTHLY', 'Bi-Monthly (6 per year)'),
        ('MONTHLY', 'Monthly (12 per year)'),
    ]
    meeting_frequency = models.CharField(
        max_length=20,
        choices=MEETING_FREQUENCY_CHOICES,
        default='QUARTERLY'
    )
    
    # EE-specific meeting frequency (if different from training)
    EE_MEETING_FREQUENCY_CHOICES = [
        ('QUARTERLY', 'Quarterly (4 per year)'),
        ('BI_ANNUALLY', 'Bi-Annually (2 per year)'),
        ('ANNUALLY', 'Annually (1 per year)'),
    ]
    ee_meeting_frequency = models.CharField(
        max_length=20,
        choices=EE_MEETING_FREQUENCY_CHOICES,
        default='QUARTERLY',
        blank=True
    )
    
    # Contact preferences for meeting invites
    send_calendar_invites = models.BooleanField(default=True)
    include_zoom_link = models.BooleanField(default=False)
    default_meeting_duration_minutes = models.PositiveIntegerField(default=120)
    
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Training Committee'
        verbose_name_plural = 'Training Committees'
    
    def __str__(self):
        return f"{self.client.company_name} - {self.name}"
    
    @property
    def member_count(self):
        return self.members.filter(is_active=True).count()


class TrainingCommitteeMember(AuditedModel):
    """
    Member of a Training Committee.
    Can participate in Training meetings, EE meetings, or both.
    """
    ROLE_CHOICES = [
        # Training Committee roles
        ('CHAIRPERSON', 'Chairperson'),
        ('SECRETARY', 'Secretary'),
        ('SDF', 'Skills Development Facilitator'),
        ('EMPLOYER_REP', 'Employer Representative'),
        ('EMPLOYEE_REP', 'Employee Representative'),
        ('UNION_REP', 'Union Representative'),
        ('OBSERVER', 'Observer'),
        # EE-specific roles
        ('EE_CHAIRPERSON', 'EE Committee Chairperson'),
        ('EE_SECRETARY', 'EE Committee Secretary'),
        ('EE_MANAGER', 'EE Manager'),
        ('DESIGNATED_GROUP_REP', 'Designated Group Representative'),
    ]
    
    committee = models.ForeignKey(
        TrainingCommittee,
        on_delete=models.CASCADE,
        related_name='members'
    )
    
    # Link to corporate contact (preferred)
    contact = models.ForeignKey(
        CorporateContact,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='training_committee_memberships'
    )
    
    # Manual entry if not linked to contact
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department = models.CharField(max_length=100, blank=True)
    
    # Which committee functions this member participates in
    participates_in_training = models.BooleanField(
        default=True,
        help_text='Member participates in Training Committee meetings'
    )
    participates_in_ee = models.BooleanField(
        default=False,
        help_text='Member participates in EE Committee meetings'
    )
    
    # For designated group representatives - which group they represent
    represents_group = models.CharField(
        max_length=100,
        blank=True,
        help_text='e.g., "African Female", "People with Disabilities"'
    )
    
    # Dates
    appointed_date = models.DateField(null=True, blank=True)
    term_end_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    receives_meeting_invites = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['role', 'name']
        verbose_name = 'Committee Member'
        verbose_name_plural = 'Committee Members'
    
    def __str__(self):
        display_name = self.contact.full_name if self.contact else self.name
        return f"{display_name} - {self.get_role_display()}"
    
    @property
    def display_name(self):
        return self.contact.full_name if self.contact else self.name
    
    @property
    def display_email(self):
        return self.contact.email if self.contact else self.email
    
    @property
    def display_phone(self):
        return self.contact.phone if self.contact else self.phone


class MeetingTemplate(models.Model):
    """
    Standard meeting templates for Training/EE Committee meetings.
    E.g., Q1 WSP Review, Q2 Mid-Year Review, EE Analysis Review, etc.
    """
    QUARTER_CHOICES = [
        ('Q1', 'Q1 (Jan-Mar)'),
        ('Q2', 'Q2 (Apr-Jun)'),
        ('Q3', 'Q3 (Jul-Sep)'),
        ('Q4', 'Q4 (Oct-Dec)'),
    ]
    
    MEETING_PURPOSE_CHOICES = [
        ('TRAINING', 'Training Committee'),
        ('EE', 'Employment Equity Committee'),
        ('COMBINED', 'Combined Training & EE'),
    ]
    
    name = models.CharField(max_length=200)
    quarter = models.CharField(max_length=2, choices=QUARTER_CHOICES)
    description = models.TextField(blank=True)
    
    # Meeting purpose - Training, EE, or Combined
    meeting_purpose = models.CharField(
        max_length=15,
        choices=MEETING_PURPOSE_CHOICES,
        default='TRAINING',
        help_text='What type of committee meeting this template is for'
    )
    
    # Default agenda items as JSON list
    default_agenda = models.JSONField(
        default=list,
        help_text='List of agenda items: [{"title": "...", "description": "...", "duration_minutes": 15}]'
    )
    
    # Timing guidance
    suggested_month = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text='Suggested month (1-12) for this meeting'
    )
    
    # Required documents/preparation
    preparation_notes = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['quarter', 'name']
        verbose_name = 'Meeting Template'
        verbose_name_plural = 'Meeting Templates'
    
    def __str__(self):
        return f"{self.quarter} - {self.name}"


class TrainingCommitteeMeeting(TenantAwareModel):
    """
    Scheduled or completed Training/EE Committee meeting.
    Can be a Training Committee meeting, EE Committee meeting, or Combined.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SCHEDULED', 'Scheduled'),
        ('INVITES_SENT', 'Invites Sent'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('POSTPONED', 'Postponed'),
    ]
    
    MEETING_PURPOSE_CHOICES = [
        ('TRAINING', 'Training Committee'),
        ('EE', 'Employment Equity Committee'),
        ('COMBINED', 'Combined Training & EE'),
    ]
    
    committee = models.ForeignKey(
        TrainingCommittee,
        on_delete=models.CASCADE,
        related_name='meetings'
    )
    
    # Link to service year (for WSP/ATR context)
    service_year = models.ForeignKey(
        WSPATRServiceYear,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='committee_meetings'
    )
    
    # Link to EE service year (for EE meetings)
    ee_service_year = models.ForeignKey(
        'EEServiceYear',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='committee_meetings'
    )
    
    # Meeting purpose - Training, EE, or Combined
    meeting_purpose = models.CharField(
        max_length=15,
        choices=MEETING_PURPOSE_CHOICES,
        default='TRAINING',
        help_text='What type of committee meeting this is'
    )
    
    # Template used
    template = models.ForeignKey(
        MeetingTemplate,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='meetings'
    )
    
    # Meeting details
    title = models.CharField(max_length=200)
    meeting_number = models.PositiveIntegerField(default=1, help_text='Meeting number in sequence')
    
    # Scheduling
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=120)
    
    # Location
    MEETING_TYPE_CHOICES = [
        ('IN_PERSON', 'In Person'),
        ('VIRTUAL', 'Virtual'),
        ('HYBRID', 'Hybrid'),
    ]
    meeting_type = models.CharField(max_length=15, choices=MEETING_TYPE_CHOICES, default='VIRTUAL')
    location = models.CharField(max_length=200, blank=True, help_text='Physical location or virtual platform')
    meeting_link = models.URLField(blank=True, help_text='Zoom/Teams/Google Meet link')
    meeting_id = models.CharField(max_length=100, blank=True, help_text='External meeting ID (e.g., Zoom meeting ID)')
    meeting_password = models.CharField(max_length=50, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # EE-specific tracking (when meeting_purpose is EE or COMBINED)
    ee_report_period = models.CharField(
        max_length=50,
        blank=True,
        help_text='EE reporting period discussed (e.g., "Oct 2025 - Sep 2026")'
    )
    workforce_analysis_reviewed = models.BooleanField(default=False)
    ee_plan_reviewed = models.BooleanField(default=False)
    barriers_analysis_discussed = models.BooleanField(default=False)
    numerical_goals_reviewed = models.BooleanField(default=False)
    
    # Invitations
    invites_sent_date = models.DateTimeField(null=True, blank=True)
    reminder_sent_date = models.DateTimeField(null=True, blank=True)
    
    # Completion
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time = models.TimeField(null=True, blank=True)
    
    # Organizer
    organized_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='organized_tc_meetings'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-scheduled_date', '-scheduled_time']
        verbose_name = 'Training Committee Meeting'
        verbose_name_plural = 'Training Committee Meetings'
    
    def __str__(self):
        return f"{self.committee.client.company_name} - {self.title} ({self.scheduled_date})"
    
    @property
    def scheduled_datetime(self):
        from datetime import datetime
        return datetime.combine(self.scheduled_date, self.scheduled_time)
    
    @property
    def is_upcoming(self):
        from django.utils import timezone
        from datetime import datetime
        meeting_dt = datetime.combine(self.scheduled_date, self.scheduled_time)
        return timezone.make_aware(meeting_dt) > timezone.now() and self.status in ['SCHEDULED', 'INVITES_SENT']
    
    @property
    def is_past_due(self):
        from django.utils import timezone
        from datetime import datetime
        meeting_dt = datetime.combine(self.scheduled_date, self.scheduled_time)
        return timezone.make_aware(meeting_dt) < timezone.now() and self.status in ['DRAFT', 'SCHEDULED', 'INVITES_SENT']


class TCMeetingAgendaItem(models.Model):
    """
    Agenda item for a Training Committee meeting.
    """
    meeting = models.ForeignKey(
        TrainingCommitteeMeeting,
        on_delete=models.CASCADE,
        related_name='tc_agenda_items'
    )
    
    sequence = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Time allocation
    duration_minutes = models.PositiveIntegerField(default=15)
    
    # Presenter/responsible
    presenter = models.ForeignKey(
        TrainingCommitteeMember,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='tc_presenting_items'
    )
    
    # Supporting documents
    supporting_document = models.FileField(
        upload_to='training_committees/agenda_documents/',
        null=True, blank=True
    )
    
    # For tracking during meeting
    is_discussed = models.BooleanField(default=False)
    discussion_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['sequence']
        verbose_name = 'TC Agenda Item'
        verbose_name_plural = 'TC Agenda Items'
    
    def __str__(self):
        return f"{self.meeting.title} - {self.sequence}. {self.title}"


class MeetingMinutes(AuditedModel):
    """
    Minutes recorded for a Training Committee meeting.
    """
    meeting = models.OneToOneField(
        TrainingCommitteeMeeting,
        on_delete=models.CASCADE,
        related_name='minutes'
    )
    
    # Minutes content
    opening_remarks = models.TextField(blank=True)
    matters_arising = models.TextField(blank=True, help_text='Matters arising from previous minutes')
    general_discussion = models.TextField(blank=True)
    closing_remarks = models.TextField(blank=True)
    
    # Next meeting
    next_meeting_date = models.DateField(null=True, blank=True)
    next_meeting_notes = models.TextField(blank=True)
    
    # Document
    minutes_document = models.FileField(
        upload_to='training_committees/minutes/',
        null=True, blank=True
    )
    
    # Approval
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    approved_date = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(
        TrainingCommitteeMember,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_minutes'
    )
    
    class Meta:
        verbose_name = 'Meeting Minutes'
        verbose_name_plural = 'Meeting Minutes'
    
    def __str__(self):
        return f"Minutes: {self.meeting.title}"


class TCMeetingAttendance(models.Model):
    """
    Attendance record for a Training Committee meeting.
    """
    ATTENDANCE_STATUS_CHOICES = [
        ('INVITED', 'Invited'),
        ('CONFIRMED', 'Confirmed'),
        ('ATTENDED', 'Attended'),
        ('APOLOGIES', 'Apologies'),
        ('ABSENT', 'Absent'),
    ]
    
    meeting = models.ForeignKey(
        TrainingCommitteeMeeting,
        on_delete=models.CASCADE,
        related_name='tc_attendance_records'
    )
    member = models.ForeignKey(
        TrainingCommitteeMember,
        on_delete=models.CASCADE,
        related_name='tc_attendance_records'
    )
    
    status = models.CharField(max_length=15, choices=ATTENDANCE_STATUS_CHOICES, default='INVITED')
    
    # Invite tracking
    invite_sent = models.BooleanField(default=False)
    invite_sent_date = models.DateTimeField(null=True, blank=True)
    invite_response_date = models.DateTimeField(null=True, blank=True)
    
    # For actual attendance
    arrival_time = models.TimeField(null=True, blank=True)
    departure_time = models.TimeField(null=True, blank=True)
    
    # Signature (for compliance)
    signature_image = models.ImageField(
        upload_to='training_committees/signatures/',
        null=True, blank=True
    )
    signed_date = models.DateTimeField(null=True, blank=True)
    
    apology_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['member__role']
        unique_together = ['meeting', 'member']
        verbose_name = 'TC Meeting Attendance'
        verbose_name_plural = 'TC Meeting Attendance Records'
    
    def __str__(self):
        return f"{self.meeting.title} - {self.member.display_name} ({self.get_status_display()})"


class TCMeetingActionItem(AuditedModel):
    """
    Action item arising from a Training Committee meeting.
    """
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('DEFERRED', 'Deferred'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    meeting = models.ForeignKey(
        TrainingCommitteeMeeting,
        on_delete=models.CASCADE,
        related_name='tc_action_items'
    )
    
    # From agenda item (optional)
    agenda_item = models.ForeignKey(
        TCMeetingAgendaItem,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='tc_action_items'
    )
    
    description = models.TextField()
    
    # Assignment
    assigned_to = models.ForeignKey(
        TrainingCommitteeMember,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='tc_assigned_actions'
    )
    
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='OPEN')
    
    completed_date = models.DateField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-priority', 'due_date']
        verbose_name = 'TC Action Item'
        verbose_name_plural = 'TC Action Items'
    
    def __str__(self):
        return f"{self.meeting.title} - {self.description[:50]}"


# =====================================================
# SETA EXPORT TEMPLATES
# =====================================================

class SETAExportTemplate(models.Model):
    """
    Configurable export template for different SETA requirements.
    """
    seta = models.ForeignKey(
        'learners.SETA',
        on_delete=models.CASCADE,
        related_name='corporate_export_templates'
    )
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    EXPORT_TYPE_CHOICES = [
        ('WSP', 'WSP Submission'),
        ('ATR', 'ATR Submission'),
        ('EMPLOYEE_DATA', 'Employee Data'),
        ('TRAINING_DATA', 'Training Data'),
        ('PIVOTAL', 'PIVOTAL Data'),
        ('COMMITTEE_ATTENDANCE', 'Committee Attendance'),
        ('COMBINED', 'Combined WSP/ATR'),
    ]
    export_type = models.CharField(max_length=30, choices=EXPORT_TYPE_CHOICES)
    
    # Column mappings as JSON
    # Format: [{"source_field": "...", "export_column": "...", "format": "...", "required": true}]
    column_mappings = models.JSONField(
        default=list,
        help_text='Column mapping configuration'
    )
    
    # File format
    FILE_FORMAT_CHOICES = [
        ('XLSX', 'Excel (.xlsx)'),
        ('CSV', 'CSV (.csv)'),
        ('XML', 'XML'),
    ]
    file_format = models.CharField(max_length=10, choices=FILE_FORMAT_CHOICES, default='XLSX')
    
    # Template file (if SETA provides a template)
    template_file = models.FileField(
        upload_to='seta_templates/',
        null=True, blank=True,
        help_text='SETA-provided template file'
    )
    
    # Version tracking
    version = models.CharField(max_length=20, default='1.0')
    effective_date = models.DateField(null=True, blank=True)
    superseded_date = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['seta__name', 'export_type', '-version']
        verbose_name = 'SETA Export Template'
        verbose_name_plural = 'SETA Export Templates'
    
    def __str__(self):
        return f"{self.seta.name} - {self.name} (v{self.version})"


# =============================================================================
# CLIENT ONBOARDING MODELS
# =============================================================================

class ClientOnboarding(TenantAwareModel):
    """
    Tracks the onboarding progress for a corporate client.
    Created when client becomes ACTIVE, guides setup process.
    """
    STEP_CHOICES = [
        ('COMPANY_VERIFY', 'Company Verification'),
        ('SERVICES', 'Services Configuration'),
        ('CONTACTS', 'Contacts & Portal Access'),
        ('DOCUMENTS', 'Document Initialization'),
        ('KICKOFF', 'Kickoff Meeting'),
        ('COMPLETE', 'Onboarding Complete'),
    ]
    
    client = models.OneToOneField(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='onboarding'
    )
    account_manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='managed_onboardings'
    )
    started_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='started_onboardings'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Legacy flag for existing clients
    legacy_onboarding = models.BooleanField(
        default=False,
        help_text='True if this is a legacy client onboarded before this system'
    )
    
    # Current step
    current_step = models.CharField(
        max_length=20,
        choices=STEP_CHOICES,
        default='COMPANY_VERIFY'
    )
    
    # Step statuses (JSONField for flexibility)
    # Format: {"COMPANY_VERIFY": {"completed": true, "completed_at": "...", "completed_by": 1}}
    step_statuses = models.JSONField(default=dict)
    
    # Step completion flags
    company_verified = models.BooleanField(default=False)
    company_verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+'
    )
    company_verified_at = models.DateTimeField(null=True, blank=True)
    
    services_configured = models.BooleanField(default=False)
    contacts_invited = models.BooleanField(default=False)
    documents_initialized = models.BooleanField(default=False)
    
    kickoff_scheduled = models.BooleanField(default=False)
    kickoff_meeting = models.ForeignKey(
        'TrainingCommitteeMeeting',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kickoff_onboardings'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Client Onboarding'
        verbose_name_plural = 'Client Onboardings'
    
    def __str__(self):
        return f"Onboarding: {self.client.company_name}"
    
    @property
    def is_complete(self):
        return self.current_step == 'COMPLETE' and self.completed_at is not None
    
    @property
    def progress_percentage(self):
        """Calculate onboarding progress as percentage."""
        steps = ['COMPANY_VERIFY', 'SERVICES', 'CONTACTS', 'DOCUMENTS', 'KICKOFF']
        completed = sum([
            self.company_verified,
            self.services_configured,
            self.contacts_invited,
            self.documents_initialized,
            self.kickoff_scheduled
        ])
        return int((completed / len(steps)) * 100)
    
    @property
    def current_step_number(self):
        """Return 1-based step number."""
        steps = ['COMPANY_VERIFY', 'SERVICES', 'CONTACTS', 'DOCUMENTS', 'KICKOFF', 'COMPLETE']
        try:
            return steps.index(self.current_step) + 1
        except ValueError:
            return 1
    
    def complete_step(self, step, user):
        """Mark a step as complete and advance to next."""
        from django.utils import timezone
        
        step_flags = {
            'COMPANY_VERIFY': 'company_verified',
            'SERVICES': 'services_configured',
            'CONTACTS': 'contacts_invited',
            'DOCUMENTS': 'documents_initialized',
            'KICKOFF': 'kickoff_scheduled',
        }
        
        step_order = ['COMPANY_VERIFY', 'SERVICES', 'CONTACTS', 'DOCUMENTS', 'KICKOFF', 'COMPLETE']
        
        if step in step_flags:
            setattr(self, step_flags[step], True)
            
            # Update step statuses JSON
            self.step_statuses[step] = {
                'completed': True,
                'completed_at': timezone.now().isoformat(),
                'completed_by': user.id if user else None
            }
            
            # Special handling for company verification
            if step == 'COMPANY_VERIFY':
                self.company_verified_by = user
                self.company_verified_at = timezone.now()
            
            # Advance to next step
            current_index = step_order.index(step)
            if current_index < len(step_order) - 1:
                self.current_step = step_order[current_index + 1]
            
            # Check if all complete
            if self.current_step == 'COMPLETE':
                self.completed_at = timezone.now()
            
            self.save()
    
    def get_step_status(self, step):
        """Get status info for a specific step."""
        return self.step_statuses.get(step, {'completed': False})


class ServiceOnboarding(TenantAwareModel):
    """
    Tracks onboarding progress for a specific service subscription.
    Each service type has its own set of onboarding steps.
    """
    SERVICE_TYPE_CHOICES = [
        ('WSP_ATR', 'WSP/ATR'),
        ('EE', 'Employment Equity'),
        ('BBBEE', 'B-BBEE'),
        ('HOST_EMPLOYMENT', 'Host Employment'),
        ('DG_APPLICATION', 'Discretionary Grant'),
    ]
    
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETE', 'Complete'),
    ]
    
    subscription = models.OneToOneField(
        'ClientServiceSubscription',
        on_delete=models.CASCADE,
        related_name='onboarding'
    )
    client_onboarding = models.ForeignKey(
        ClientOnboarding,
        on_delete=models.CASCADE,
        related_name='service_onboardings',
        null=True, blank=True
    )
    
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOT_STARTED')
    
    current_step = models.PositiveIntegerField(default=1)
    total_steps = models.PositiveIntegerField(default=1)
    
    # Step completion data
    # Format: {"1": {"name": "SETA Confirmation", "completed": true, "completed_at": "..."}, ...}
    step_data = models.JSONField(default=dict)
    
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_service_onboardings'
    )
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['subscription__client__company_name', 'service_type']
        verbose_name = 'Service Onboarding'
        verbose_name_plural = 'Service Onboardings'
    
    def __str__(self):
        return f"{self.subscription.client.company_name} - {self.get_service_type_display()} Onboarding"
    
    @property
    def progress_percentage(self):
        if self.total_steps == 0:
            return 0
        completed_steps = sum(1 for s in self.step_data.values() if s.get('completed'))
        return int((completed_steps / self.total_steps) * 100)
    
    def initialize_steps(self):
        """Initialize step data based on service type."""
        from django.utils import timezone
        
        step_definitions = {
            'WSP_ATR': [
                ('SETA_CONFIRMATION', 'SETA Confirmation'),
                ('FINANCIAL_YEAR', 'Financial Year Setup'),
                ('COMMITTEE', 'Committee Establishment'),
                ('SDF_APPOINTMENT', 'SDF Appointment'),
                ('WORKFORCE', 'Workforce Profile'),
                ('TRAINING_HISTORY', 'Training History'),
                ('DOCUMENTS', 'Document Checklist'),
                ('MEETINGS', 'Meeting Schedule'),
            ],
            'EE': [
                ('REPORTING_PERIOD', 'Reporting Period'),
                ('SENIOR_MANAGER', 'Senior Manager Appointment'),
                ('COMMITTEE', 'Committee Setup'),
                ('WORKFORCE', 'Workforce Analysis'),
                ('BARRIERS', 'Barrier Identification'),
                ('EE_PLAN', 'EE Plan Status'),
                ('DOCUMENTS', 'Document Checklist'),
            ],
            'BBBEE': [
                ('CLASSIFICATION', 'Entity Classification'),
                ('FINANCIAL_YEAR', 'Financial Year'),
                ('OWNERSHIP', 'Ownership Structure'),
                ('SCORECARD', 'Current Scorecard'),
                ('DATA_INTEGRATION', 'Data Integration'),
                ('DOCUMENTS', 'Document Checklist'),
            ],
            'HOST_EMPLOYMENT': [
                ('CAPACITY', 'Hosting Capacity'),
                ('MENTORS', 'Mentor Assignment'),
                ('COMPLIANCE', 'Compliance Check'),
                ('AGREEMENTS', 'Agreements'),
            ],
            'DG_APPLICATION': [
                ('ELIGIBILITY', 'Eligibility Check'),
                ('PROJECT_SCOPE', 'Project Scope'),
                ('LEARNERS', 'Learner Allocation'),
                ('DOCUMENTS', 'Document Checklist'),
            ],
        }
        
        steps = step_definitions.get(self.service_type, [])
        self.total_steps = len(steps)
        self.step_data = {
            str(i + 1): {
                'code': code,
                'name': name,
                'completed': False,
                'completed_at': None,
                'completed_by': None
            }
            for i, (code, name) in enumerate(steps)
        }
        self.started_at = timezone.now()
        self.status = 'IN_PROGRESS'
        self.save()
    
    def complete_step(self, step_number, user):
        """Mark a step as complete."""
        from django.utils import timezone
        
        step_key = str(step_number)
        if step_key in self.step_data:
            self.step_data[step_key]['completed'] = True
            self.step_data[step_key]['completed_at'] = timezone.now().isoformat()
            self.step_data[step_key]['completed_by'] = user.id if user else None
            
            # Advance to next step
            if step_number < self.total_steps:
                self.current_step = step_number + 1
            else:
                self.status = 'COMPLETE'
                self.completed_at = timezone.now()
            
            self.save()


class PortalInvitation(TenantAwareModel):
    """
    Invitation for corporate contacts to access the client portal.
    Uses token-based authentication for secure invitation acceptance.
    """
    import uuid
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('EXPIRED', 'Expired'),
        ('REVOKED', 'Revoked'),
    ]
    
    ROLE_CHOICES = [
        ('SDF', 'Skills Development Facilitator'),
        ('HR_MANAGER', 'HR Manager'),
        ('TRAINING_MANAGER', 'Training Manager'),
        ('FINANCE', 'Finance Contact'),
        ('SENIOR_MANAGER', 'Senior Manager'),
        ('OTHER', 'Other'),
    ]
    
    PERMISSION_TEMPLATE_CHOICES = [
        ('FULL_ACCESS', 'Full Access'),
        ('VIEW_ONLY', 'View Only'),
        ('SDF_STANDARD', 'SDF Standard'),
        ('HR_STANDARD', 'HR Standard'),
    ]
    
    client = models.ForeignKey(
        CorporateClient,
        on_delete=models.CASCADE,
        related_name='portal_invitations'
    )
    contact = models.ForeignKey(
        CorporateContact,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='portal_invitations',
        help_text='Contact created on invitation acceptance'
    )
    
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_invitations'
    )
    
    # Invitation details
    email = models.EmailField()
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='OTHER')
    permission_template = models.CharField(
        max_length=20,
        choices=PERMISSION_TEMPLATE_CHOICES,
        default='VIEW_ONLY'
    )
    
    # Token for secure acceptance
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Timestamps
    invited_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Custom message
    personal_message = models.TextField(blank=True, help_text='Optional personal message in invitation email')
    
    class Meta:
        ordering = ['-invited_at']
        verbose_name = 'Portal Invitation'
        verbose_name_plural = 'Portal Invitations'
    
    def __str__(self):
        return f"Invitation to {self.name} ({self.email}) for {self.client.company_name}"
    
    @property
    def is_valid(self):
        """Check if invitation is still valid."""
        from django.utils import timezone
        return (
            self.status == 'PENDING' and
            self.expires_at > timezone.now()
        )
    
    def accept(self, user):
        """Accept the invitation and create/link contact."""
        from django.utils import timezone
        
        if not self.is_valid:
            raise ValueError("Invitation is no longer valid")
        
        # Create or get contact
        contact, created = CorporateContact.objects.get_or_create(
            client=self.client,
            email=self.email,
            defaults={
                'name': self.name,
                'role': self.role,
                'user': user,
                'is_primary': False,
            }
        )
        
        if not created:
            contact.user = user
            contact.save()
        
        # Apply permission template
        self._apply_permissions(contact)
        
        # Update invitation
        self.contact = contact
        self.status = 'ACCEPTED'
        self.accepted_at = timezone.now()
        self.save()
        
        return contact
    
    def _apply_permissions(self, contact):
        """Apply permission template to contact."""
        permission_mappings = {
            'FULL_ACCESS': {
                'can_view_reports': True,
                'can_approve_documents': True,
                'can_complete_tasks': True,
                'can_upload_evidence': True,
            },
            'VIEW_ONLY': {
                'can_view_reports': True,
                'can_approve_documents': False,
                'can_complete_tasks': False,
                'can_upload_evidence': False,
            },
            'SDF_STANDARD': {
                'can_view_reports': True,
                'can_approve_documents': True,
                'can_complete_tasks': True,
                'can_upload_evidence': True,
            },
            'HR_STANDARD': {
                'can_view_reports': True,
                'can_approve_documents': False,
                'can_complete_tasks': True,
                'can_upload_evidence': True,
            },
        }
        
        permissions = permission_mappings.get(self.permission_template, {})
        for field, value in permissions.items():
            if hasattr(contact, field):
                setattr(contact, field, value)
        contact.save()
    
    def revoke(self):
        """Revoke the invitation."""
        self.status = 'REVOKED'
        self.save()
    
    def resend(self, user):
        """Resend the invitation with new expiry."""
        from django.utils import timezone
        from datetime import timedelta
        
        self.invited_by = user
        self.invited_at = timezone.now()
        self.expires_at = timezone.now() + timedelta(days=7)
        self.status = 'PENDING'
        self.save()
    
    def save(self, *args, **kwargs):
        """Set expiry date if not set."""
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        
        # Check for expiry
        if self.status == 'PENDING' and self.expires_at < timezone.now():
            self.status = 'EXPIRED'
        
        super().save(*args, **kwargs)