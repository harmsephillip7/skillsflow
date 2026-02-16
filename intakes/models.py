from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import date
from decimal import Decimal


class AuditedModel(models.Model):
    """Abstract base model for audit trails"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, 
        on_delete=models.SET_NULL, 
        related_name='%(class)s_created'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, 
        on_delete=models.SET_NULL, 
        related_name='%(class)s_updated'
    )

    class Meta:
        abstract = True


# =============================================================================
# CONTRACT MODEL - Parent entity for grouping multiple NOTs
# =============================================================================

class Contract(AuditedModel):
    """
    Contract represents a funding agreement that can contain multiple 
    Training Notifications (NOTs) with different qualifications and campuses.
    Tracks overall learner counts, terminations, and dropout rates.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_SIGNATURE', 'Pending Signature'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    ]
    
    FUNDER_TYPE_CHOICES = [
        ('SETA', 'SETA'),
        ('CORPORATE', 'Corporate'),
        ('GOVERNMENT', 'Government'),
        ('MUNICIPALITY', 'Municipality'),
        ('PRIVATE', 'Private'),
        ('MIXED', 'Mixed Funding'),
    ]
    
    # Contract Identification
    contract_number = models.CharField(
        max_length=50, 
        unique=True, 
        blank=True,
        help_text="Unique contract reference number"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Client & Funding
    client = models.ForeignKey(
        'corporate.CorporateClient',
        on_delete=models.PROTECT,
        related_name='contracts',
        null=True, blank=True
    )
    seta = models.ForeignKey(
        'learners.SETA',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contracts'
    )
    funder_type = models.CharField(
        max_length=20, 
        choices=FUNDER_TYPE_CHOICES, 
        default='SETA'
    )
    
    # Contract Value
    contract_value = models.DecimalField(
        max_digits=14, 
        decimal_places=2, 
        null=True, blank=True
    )
    
    # Timeline
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    signature_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Learner Tracking - Original contracted numbers
    original_learner_count = models.PositiveIntegerField(
        default=0,
        help_text="Total learners contracted at the start"
    )
    
    # Dropout Configuration
    max_dropout_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('10.00'),
        help_text="Maximum allowed dropout percentage (default 10%)"
    )
    dropout_alert_threshold = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('7.00'),
        help_text="Alert threshold for dropout percentage (default 7%)"
    )
    
    # Documents
    contract_document = models.FileField(
        upload_to='contracts/documents/', 
        null=True, blank=True
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contract'
        verbose_name_plural = 'Contracts'
    
    def __str__(self):
        return f"{self.contract_number} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.contract_number:
            # Auto-generate contract number: CON-YYYY-XXXX
            year = date.today().year
            prefix = f"CON-{year}-"
            last = Contract.objects.filter(
                contract_number__startswith=prefix
            ).order_by('-contract_number').first()
            if last:
                try:
                    last_num = int(last.contract_number.split('-')[-1])
                    self.contract_number = f"{prefix}{last_num + 1:04d}"
                except ValueError:
                    self.contract_number = f"{prefix}0001"
            else:
                self.contract_number = f"{prefix}0001"
        super().save(*args, **kwargs)
    
    # -------------------------------------------------------------------------
    # Learner Tracking Properties
    # -------------------------------------------------------------------------
    
    @property
    def total_learners_enrolled(self):
        """Total learners ever enrolled across all NOTs in this contract"""
        return self.learner_enrollments.count()
    
    @property
    def original_learners(self):
        """Count of original (non-replacement) learners"""
        return self.learner_enrollments.filter(is_original=True).count()
    
    @property
    def replacement_learners(self):
        """Count of replacement learners"""
        return self.learner_enrollments.filter(is_replacement=True).count()
    
    @property
    def active_learners(self):
        """Count of currently active learners (not terminated)"""
        return self.learner_enrollments.filter(
            termination_date__isnull=True
        ).count()
    
    @property
    def terminated_learners(self):
        """Count of terminated learners"""
        return self.learner_enrollments.filter(
            termination_date__isnull=False
        ).count()
    
    @property
    def dropout_count(self):
        """
        Dropouts = Original learners who were terminated 
        (replacements are not counted as dropouts)
        """
        return self.learner_enrollments.filter(
            is_original=True,
            termination_date__isnull=False
        ).count()
    
    @property
    def dropout_percentage(self):
        """
        Dropout percentage based on original learner count.
        Formula: (Terminated Original Learners / Original Learner Count) * 100
        """
        base = self.original_learner_count or self.original_learners
        if base > 0:
            return round((self.dropout_count / base) * 100, 1)
        return 0.0
    
    @property
    def is_dropout_warning(self):
        """True if dropout percentage exceeds alert threshold (default 7%)"""
        return self.dropout_percentage >= float(self.dropout_alert_threshold)
    
    @property
    def is_dropout_exceeded(self):
        """True if dropout percentage exceeds maximum allowed (default 10%)"""
        return self.dropout_percentage >= float(self.max_dropout_percentage)
    
    @property
    def dropout_status(self):
        """Return dropout status: OK, WARNING, or EXCEEDED"""
        if self.is_dropout_exceeded:
            return 'EXCEEDED'
        elif self.is_dropout_warning:
            return 'WARNING'
        return 'OK'
    
    @property
    def available_replacement_slots(self):
        """
        Number of replacement learners that can still be added without exceeding 
        the original contracted count.
        """
        return max(0, self.original_learner_count - self.active_learners)
    
    @property
    def not_count(self):
        """Count of Training Notifications linked to this contract"""
        from core.models import TrainingNotification
        return TrainingNotification.objects.filter(contract=self).count()
    
    def get_training_notifications(self):
        """Get all NOTs linked to this contract"""
        from core.models import TrainingNotification
        return TrainingNotification.objects.filter(contract=self).select_related(
            'qualification', 'delivery_campus'
        )


# =============================================================================
# LEARNER CONTRACT ENROLLMENT - Tracks learners at contract level
# =============================================================================

class LearnerContractEnrollment(AuditedModel):
    """
    Tracks learner participation at the contract level.
    Links learners to contracts with termination and replacement tracking.
    """
    
    TERMINATION_REASON_CHOICES = [
        ('PERSONAL', 'Personal Reasons'),
        ('FINANCIAL', 'Financial Difficulties'),
        ('EMPLOYMENT', 'Found Employment'),
        ('RELOCATION', 'Relocated'),
        ('ACADEMIC', 'Academic Performance Issues'),
        ('DISCIPLINARY', 'Disciplinary Action'),
        ('HEALTH', 'Health/Medical Reasons'),
        ('DECEASED', 'Deceased'),
        ('ABSCONDED', 'Absconded/No Contact'),
        ('EMPLOYER_REQUEST', 'Employer Request'),
        ('OTHER', 'Other'),
    ]
    
    # Core Relationships
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='learner_enrollments'
    )
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.PROTECT,
        related_name='contract_enrollments'
    )
    training_notification = models.ForeignKey(
        'core.TrainingNotification',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contract_learner_enrollments',
        help_text="Specific NOT this learner is enrolled in"
    )
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contract_enrollment',
        help_text="Link to academic enrollment for NLRD tracking"
    )
    
    # Original vs Replacement Tracking
    is_original = models.BooleanField(
        default=True,
        help_text="True if this learner was part of the original cohort"
    )
    is_replacement = models.BooleanField(
        default=False,
        help_text="True if this learner is replacing a terminated learner"
    )
    replaces_learner = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='replaced_by',
        help_text="The learner this person is replacing (if replacement)"
    )
    
    # Enrollment Dates
    enrollment_date = models.DateField(
        default=date.today,
        help_text="Date learner was enrolled in the contract"
    )
    
    # Termination Tracking
    termination_date = models.DateField(
        null=True, blank=True,
        help_text="Date of termination (if terminated)"
    )
    termination_reason = models.CharField(
        max_length=20,
        choices=TERMINATION_REASON_CHOICES,
        blank=True,
        help_text="Reason for termination"
    )
    termination_details = models.TextField(
        blank=True,
        help_text="Additional details about the termination"
    )
    terminated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='terminated_contract_enrollments'
    )
    
    # Supporting Documents
    termination_letter = models.FileField(
        upload_to='contracts/terminations/',
        null=True, blank=True,
        help_text="Termination letter or supporting documentation"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-enrollment_date']
        verbose_name = 'Contract Learner Enrollment'
        verbose_name_plural = 'Contract Learner Enrollments'
        unique_together = ['contract', 'learner']
    
    def __str__(self):
        status = "Terminated" if self.termination_date else "Active"
        return f"{self.learner} - {self.contract.contract_number} ({status})"
    
    @property
    def is_active(self):
        """True if learner is still active (not terminated)"""
        return self.termination_date is None
    
    @property
    def is_terminated(self):
        """True if learner has been terminated"""
        return self.termination_date is not None
    
    @property
    def days_enrolled(self):
        """Number of days enrolled (until termination or today)"""
        end_date = self.termination_date or date.today()
        return (end_date - self.enrollment_date).days
    
    def terminate(self, reason, details='', terminated_by=None, termination_date=None):
        """
        Terminate this learner's enrollment.
        Also updates the linked academic enrollment status to WITHDRAWN.
        """
        self.termination_date = termination_date or date.today()
        self.termination_reason = reason
        self.termination_details = details
        self.terminated_by = terminated_by
        self.save()
        
        # Update academic enrollment if linked
        if self.enrollment:
            old_status = self.enrollment.status
            self.enrollment.status = 'WITHDRAWN'
            self.enrollment.withdrawal_reason = f"{self.get_termination_reason_display()}: {details}"
            self.enrollment.save()
            
            # Create status history entry
            from academics.models import EnrollmentStatusHistory
            EnrollmentStatusHistory.objects.create(
                enrollment=self.enrollment,
                from_status=old_status,
                to_status='WITHDRAWN',
                reason=f"Contract termination: {self.get_termination_reason_display()}",
                changed_by=terminated_by
            )


class Intake(AuditedModel):
    """
    Central intake/cohort management for learner enrollments.
    Created from Training Notifications (NOTs) but can also be standalone.
    Supports mixed funding types within a single intake.
    """
    
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('RECRUITING', 'Recruiting'),
        ('ENROLLMENT_OPEN', 'Enrollment Open'),
        ('ENROLLMENT_CLOSED', 'Enrollment Closed'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    DELIVERY_MODE_CHOICES = [
        ('ON_CAMPUS', 'On Campus'),
        ('OFF_SITE', 'Off-Site / Client Premises'),
        ('ONLINE', 'Online'),
        ('BLENDED', 'Blended'),
        ('WORKPLACE', 'Workplace Based'),
    ]
    
    # Reference
    code = models.CharField(max_length=30, unique=True, help_text="Unique intake code e.g. INT-2025-001")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Programme Details
    qualification = models.ForeignKey(
        'academics.Qualification',
        on_delete=models.PROTECT,
        related_name='intakes'
    )
    campus = models.ForeignKey(
        'tenants.Campus',
        on_delete=models.PROTECT,
        related_name='intakes'
    )
    delivery_mode = models.CharField(max_length=20, choices=DELIVERY_MODE_CHOICES, default='ON_CAMPUS')
    
    # Timeline
    start_date = models.DateField()
    end_date = models.DateField()
    enrollment_deadline = models.DateField(null=True, blank=True, help_text="Last date to enroll learners")
    
    # Capacity
    max_capacity = models.PositiveIntegerField(default=30, help_text="Maximum learners for this intake")
    min_viable = models.PositiveIntegerField(default=10, help_text="Minimum learners needed to run")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    
    # Source/Origin
    training_notification = models.ForeignKey(
        'core.TrainingNotification',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='intake_records',
        help_text="NOT that created this intake (if applicable)"
    )
    not_intake = models.ForeignKey(
        'core.NOTIntake',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='intake_bucket',
        help_text="Specific NOT intake phase this relates to"
    )
    
    # Cohort linkage (for existing cohort system integration)
    cohort = models.ForeignKey(
        'logistics.Cohort',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='intake_records'
    )
    
    # Resources
    facilitator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='facilitated_intakes'
    )
    venue = models.ForeignKey(
        'logistics.Venue',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='intakes'
    )
    
    # Pricing (base fees for the programme)
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tuition_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    materials_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date', 'name']
        verbose_name = 'Intake'
        verbose_name_plural = 'Intakes'
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate code if not provided
        if not self.code:
            year = self.start_date.year if self.start_date else date.today().year
            prefix = f"INT-{year}-"
            last = Intake.objects.filter(code__startswith=prefix).order_by('-code').first()
            if last:
                try:
                    num = int(last.code.split('-')[-1]) + 1
                except ValueError:
                    num = 1
            else:
                num = 1
            self.code = f"{prefix}{num:04d}"
        super().save(*args, **kwargs)
    
    @property
    def enrolled_count(self):
        """Count of confirmed enrollments"""
        return self.enrollments.filter(
            status__in=['ENROLLED', 'ACTIVE', 'COMPLETED']
        ).count()
    
    @property
    def pending_count(self):
        """Count of pending/applied enrollments"""
        return self.enrollments.filter(
            status__in=['APPLIED', 'DOC_CHECK', 'PAYMENT_PENDING']
        ).count()
    
    @property
    def available_spots(self):
        """Remaining capacity"""
        return max(0, self.max_capacity - self.enrolled_count)
    
    @property
    def fill_percentage(self):
        """Percentage of capacity filled"""
        if self.max_capacity == 0:
            return 0
        return round((self.enrolled_count / self.max_capacity) * 100, 1)
    
    @property
    def is_full(self):
        """Check if intake is at capacity"""
        return self.enrolled_count >= self.max_capacity
    
    @property
    def is_viable(self):
        """Check if minimum viable learners enrolled"""
        return self.enrolled_count >= self.min_viable
    
    @property
    def days_until_start(self):
        """Days until intake starts"""
        if self.start_date:
            return (self.start_date - date.today()).days
        return None
    
    @property
    def total_fee(self):
        """Total fee for the intake"""
        return self.registration_fee + self.tuition_fee + self.materials_fee
    
    def get_funding_breakdown(self):
        """Get count of enrollments by funding type"""
        from django.db.models import Count
        return self.enrollments.values('funding_type').annotate(
            count=Count('id')
        ).order_by('-count')


class IntakeEnrollment(AuditedModel):
    """
    Links a learner to a specific intake with funding and payment tracking.
    This is the central enrollment record for the intake system.
    """
    
    STATUS_CHOICES = [
        ('APPLIED', 'Applied'),
        ('DOC_CHECK', 'Document Verification'),
        ('PAYMENT_PENDING', 'Payment Pending'),
        ('ENROLLED', 'Enrolled'),
        ('ACTIVE', 'Active'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('WITHDRAWN', 'Withdrawn'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    FUNDING_TYPE_CHOICES = [
        ('PRIVATE_UPFRONT', 'Private - Upfront Payment'),
        ('PRIVATE_PMT_AGREEMENT', 'Private - Payment Agreement'),
        ('GOVERNMENT_BURSARY', 'Government Bursary'),
        ('CORPORATE_BURSARY', 'Corporate Bursary'),
        ('DG_BURSARY', 'DG Bursary'),
        ('SELF_FUNDED', 'Self-Funded'),
        ('PARENT_FUNDED', 'Parent/Guardian Funded'),
        ('EMPLOYER_FUNDED', 'Employer Funded'),
        ('BURSARY', 'Bursary'),
        ('LEARNER_LOAN', 'Learner Loan'),
        ('SETA_FUNDED', 'SETA Funded'),
        ('DISCRETIONARY_GRANT', 'Discretionary Grant'),
        ('PIVOTAL_GRANT', 'PIVOTAL Grant'),
        ('MIXED', 'Mixed Funding'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('FULL_UPFRONT', 'Full Payment Upfront'),
        ('INSTALMENT', 'Instalment Plan'),
        ('DEBIT_ORDER', 'Debit Order'),
        ('CORPORATE_INVOICE', 'Corporate Invoice'),
        ('SETA_TRANCHE', 'SETA Tranche Payment'),
        ('BURSARY_DISBURSEMENT', 'Bursary Disbursement'),
    ]
    
    # Core relationships
    intake = models.ForeignKey(
        Intake,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.CASCADE,
        related_name='intake_enrollments'
    )
    
    # Optional link to academics Enrollment (for NLRD tracking)
    academic_enrollment = models.ForeignKey(
        'academics.Enrollment',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='intake_enrollment'
    )
    
    # Enrollment reference
    enrollment_number = models.CharField(max_length=30, unique=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='APPLIED')
    
    # Funding
    funding_type = models.CharField(max_length=25, choices=FUNDING_TYPE_CHOICES, default='SELF_FUNDED')
    payment_method = models.CharField(max_length=25, choices=PAYMENT_METHOD_CHOICES, blank=True)
    
    # Payer information
    responsible_payer = models.ForeignKey(
        'learners.Guardian',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='paid_enrollments',
        help_text="Guardian/parent responsible for payment"
    )
    corporate_client = models.ForeignKey(
        'corporate.CorporateClient',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='sponsored_enrollments',
        help_text="Corporate client if employer-funded"
    )
    bursary_application = models.ForeignKey(
        'finance.BursaryApplication',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='enrollments',
        help_text="Linked bursary application if bursary-funded"
    )
    
    # Fees (can override intake defaults)
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tuition_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    materials_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_reason = models.CharField(max_length=200, blank=True)
    
    # Payment tracking
    registration_paid = models.BooleanField(default=False)
    registration_paid_date = models.DateField(null=True, blank=True)
    registration_payment_reference = models.CharField(max_length=100, blank=True)
    
    # Bursary contract (for bursary-funded learners)
    bursary_contract_signed = models.BooleanField(default=False)
    bursary_contract_date = models.DateField(null=True, blank=True)
    bursary_contract_file = models.FileField(upload_to='intake_enrollments/bursary_contracts/', null=True, blank=True)
    
    # Debit order mandate (if applicable)
    debit_order_mandate = models.ForeignKey(
        'finance.DebitOrderMandate',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='enrollments'
    )
    
    # Dates
    application_date = models.DateField(auto_now_add=True)
    enrollment_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    withdrawal_date = models.DateField(null=True, blank=True)
    withdrawal_reason = models.TextField(blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-application_date']
        verbose_name = 'Intake Enrollment'
        verbose_name_plural = 'Intake Enrollments'
        unique_together = ['intake', 'learner']  # Prevent duplicate enrollments
    
    def __str__(self):
        return f"{self.enrollment_number} - {self.learner}"
    
    def save(self, *args, **kwargs):
        # Auto-generate enrollment number
        if not self.enrollment_number:
            year = date.today().year
            prefix = f"ENR-{year}-"
            last = IntakeEnrollment.objects.filter(enrollment_number__startswith=prefix).order_by('-enrollment_number').first()
            if last:
                try:
                    num = int(last.enrollment_number.split('-')[-1]) + 1
                except ValueError:
                    num = 1
            else:
                num = 1
            self.enrollment_number = f"{prefix}{num:05d}"
        
        # Copy fees from intake if not set
        if self.registration_fee is None:
            self.registration_fee = self.intake.registration_fee
        if self.tuition_fee is None:
            self.tuition_fee = self.intake.tuition_fee
        if self.materials_fee is None:
            self.materials_fee = self.intake.materials_fee
            
        super().save(*args, **kwargs)
    
    @property
    def total_fee(self):
        """Calculate total fee after discount"""
        reg = self.registration_fee or Decimal('0.00')
        tuition = self.tuition_fee or Decimal('0.00')
        materials = self.materials_fee or Decimal('0.00')
        return reg + tuition + materials - self.discount_amount
    
    @property
    def is_payment_cleared(self):
        """Check if payment requirements are met for enrollment"""
        if self.funding_type == 'BURSARY':
            return self.bursary_contract_signed
        elif self.payment_method == 'DEBIT_ORDER':
            return self.debit_order_mandate is not None and self.registration_paid
        else:
            return self.registration_paid
    
    @property
    def can_access_intake(self):
        """Check if learner can access the intake (all requirements met)"""
        # Must have registration paid or bursary contract signed
        if not self.is_payment_cleared:
            return False
        # Must be in an active status
        return self.status in ['ENROLLED', 'ACTIVE']


class IntakeDocument(AuditedModel):
    """
    Documents uploaded for intake enrollment verification.
    """
    
    DOCUMENT_TYPE_CHOICES = [
        ('ID_DOCUMENT', 'ID Document'),
        ('PASSPORT', 'Passport'),
        ('BIRTH_CERTIFICATE', 'Birth Certificate'),
        ('MATRIC_CERTIFICATE', 'Matric Certificate'),
        ('HIGHEST_QUALIFICATION', 'Highest Qualification'),
        ('PROOF_OF_PAYMENT', 'Proof of Payment'),
        ('BURSARY_CONTRACT', 'Bursary Contract'),
        ('DEBIT_ORDER_MANDATE', 'Debit Order Mandate'),
        ('PARENT_CONSENT', 'Parent/Guardian Consent'),
        ('MEDICAL_CERTIFICATE', 'Medical Certificate'),
        ('EMPLOYMENT_CONFIRMATION', 'Employment Confirmation'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    ]
    
    enrollment = models.ForeignKey(
        IntakeEnrollment,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    file = models.FileField(upload_to='intake_documents/')
    original_filename = models.CharField(max_length=255)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_intake_documents'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    expiry_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Intake Document'
        verbose_name_plural = 'Intake Documents'
    
    def __str__(self):
        return f"{self.enrollment.enrollment_number} - {self.get_document_type_display()}"


class IntakeCapacitySnapshot(models.Model):
    """
    Historical snapshots of intake capacity for reporting and analytics.
    Captured daily or on significant events.
    """
    
    intake = models.ForeignKey(
        Intake,
        on_delete=models.CASCADE,
        related_name='capacity_snapshots'
    )
    snapshot_date = models.DateField()
    
    # Counts at time of snapshot
    max_capacity = models.PositiveIntegerField()
    enrolled_count = models.PositiveIntegerField()
    pending_count = models.PositiveIntegerField()
    withdrawn_count = models.PositiveIntegerField(default=0)
    
    # Calculated metrics
    fill_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Breakdown by funding type
    self_funded_count = models.PositiveIntegerField(default=0)
    parent_funded_count = models.PositiveIntegerField(default=0)
    employer_funded_count = models.PositiveIntegerField(default=0)
    bursary_count = models.PositiveIntegerField(default=0)
    seta_funded_count = models.PositiveIntegerField(default=0)
    other_funded_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-snapshot_date']
        unique_together = ['intake', 'snapshot_date']
        verbose_name = 'Intake Capacity Snapshot'
        verbose_name_plural = 'Intake Capacity Snapshots'
    
    def __str__(self):
        return f"{self.intake.code} - {self.snapshot_date} ({self.fill_percentage}%)"
    
    @classmethod
    def capture_snapshot(cls, intake):
        """Capture a snapshot for an intake"""
        enrollments = intake.enrollments.all()
        
        funding_counts = {
            'SELF_FUNDED': 0,
            'PARENT_FUNDED': 0,
            'EMPLOYER_FUNDED': 0,
            'BURSARY': 0,
            'SETA_FUNDED': 0,
        }
        
        for e in enrollments.filter(status__in=['ENROLLED', 'ACTIVE', 'COMPLETED']):
            if e.funding_type in funding_counts:
                funding_counts[e.funding_type] += 1
            else:
                funding_counts['SETA_FUNDED'] += 1  # Group others into SETA
        
        return cls.objects.update_or_create(
            intake=intake,
            snapshot_date=date.today(),
            defaults={
                'max_capacity': intake.max_capacity,
                'enrolled_count': intake.enrolled_count,
                'pending_count': intake.pending_count,
                'withdrawn_count': enrollments.filter(status='WITHDRAWN').count(),
                'fill_percentage': intake.fill_percentage,
                'self_funded_count': funding_counts['SELF_FUNDED'],
                'parent_funded_count': funding_counts['PARENT_FUNDED'],
                'employer_funded_count': funding_counts['EMPLOYER_FUNDED'],
                'bursary_count': funding_counts['BURSARY'],
                'seta_funded_count': funding_counts['SETA_FUNDED'],
                'other_funded_count': 0,
            }
        )
