"""
Academics app models
Qualifications, Modules, Unit Standards, and Enrollments
"""
from django.db import models
from core.models import AuditedModel, User
from tenants.models import TenantAwareModel
from learners.models import SETA


class Qualification(AuditedModel):
    """
    QCTO Qualification/Programme
    """
    QUALIFICATION_TYPES = [
        ('OC', 'Occupational Certificate'),
        ('NC', 'National Certificate'),
        ('ND', 'National Diploma'),
        ('PQ', 'Part Qualification'),
        ('SP', 'Skills Programme'),
        ('LP', 'Learnership Programme'),
    ]
    
    # SAQA Details
    saqa_id = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=500)
    short_title = models.CharField(max_length=100)
    
    # Classification
    nqf_level = models.PositiveIntegerField()  # 1-10
    credits = models.PositiveIntegerField()
    qualification_type = models.CharField(max_length=5, choices=QUALIFICATION_TYPES)
    
    # SETA
    seta = models.ForeignKey(
        SETA, 
        on_delete=models.PROTECT, 
        related_name='qualifications'
    )
    
    # Duration
    minimum_duration_months = models.PositiveIntegerField(default=12)
    maximum_duration_months = models.PositiveIntegerField(default=36)
    
    # SAQA Registration
    registration_start = models.DateField()
    registration_end = models.DateField()
    last_enrollment_date = models.DateField()
    
    # QCTO
    qcto_code = models.CharField(max_length=50, blank=True, help_text="QCTO-specific qualification code")
    
    # Provider Accreditation
    accreditation_number = models.CharField(max_length=50, blank=True)
    accreditation_start_date = models.DateField(null=True, blank=True)
    accreditation_expiry = models.DateField(null=True, blank=True)
    accreditation_certificate = models.FileField(
        upload_to='qualifications/accreditation/%Y/',
        null=True,
        blank=True
    )
    
    # Delivery Mode Readiness
    ready_in_person = models.BooleanField(default=False, help_text="Ready for in-person/contact delivery")
    ready_online = models.BooleanField(default=False, help_text="Ready for online/distance delivery")
    ready_hybrid = models.BooleanField(default=False, help_text="Ready for hybrid/blended delivery")
    delivery_notes = models.TextField(blank=True, help_text="Notes on delivery readiness status")
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['title']
    
    def __str__(self):
        return f"{self.saqa_id} - {self.short_title} (NQF {self.nqf_level})"
    
    def create_default_checklist(self):
        """
        Create QCTO standard accreditation checklist items for this qualification
        Call this after creating a new qualification
        """
        from academics.models import AccreditationChecklistItem
        
        # QCTO Standard Checklist Items
        default_items = [
            # Documentation
            {'title': 'QCTO Accreditation Letter', 'category': 'DOCUMENTATION', 'is_required': True, 'description': 'Official QCTO accreditation letter for this qualification'},
            {'title': 'Curriculum Document', 'category': 'DOCUMENTATION', 'is_required': True, 'description': 'QCTO registered curriculum document'},
            {'title': 'Assessment Quality Partner Agreement', 'category': 'DOCUMENTATION', 'is_required': True, 'description': 'Signed AQP agreement or partnership documentation'},
            {'title': 'Learner Agreement Template', 'category': 'DOCUMENTATION', 'is_required': True, 'description': 'Standard learner agreement compliant with QCTO requirements'},
            {'title': 'Workplace Approval Letter', 'category': 'DOCUMENTATION', 'is_required': False, 'description': 'For learnerships: workplace approval documentation'},
            
            # Personnel & Staffing
            {'title': 'Registered Facilitator(s)', 'category': 'PERSONNEL', 'is_required': True, 'description': 'At least one facilitator registered with the SETA for this qualification'},
            {'title': 'Facilitator CVs and Qualifications', 'category': 'PERSONNEL', 'is_required': True, 'description': 'CVs showing relevant qualifications and experience'},
            {'title': 'Registered Assessor(s)', 'category': 'PERSONNEL', 'is_required': True, 'description': 'At least one assessor registered with the SETA'},
            {'title': 'Registered Moderator', 'category': 'PERSONNEL', 'is_required': True, 'description': 'Internal moderator registered with the SETA'},
            {'title': 'Skills Development Facilitator', 'category': 'PERSONNEL', 'is_required': False, 'description': 'SDF registration for workplace-based delivery'},
            
            # Facilities & Equipment
            {'title': 'Venue Compliance Certificate', 'category': 'FACILITIES', 'is_required': True, 'description': 'OHS compliant training venue'},
            {'title': 'Equipment List', 'category': 'FACILITIES', 'is_required': True, 'description': 'List of available equipment for practical components'},
            {'title': 'Computer Lab (if applicable)', 'category': 'FACILITIES', 'is_required': False, 'description': 'Computer facilities for digital learning components'},
            {'title': 'Workshop/Simulation Area', 'category': 'FACILITIES', 'is_required': False, 'description': 'Practical training area for hands-on components'},
            
            # Learning Materials
            {'title': 'Learner Guide', 'category': 'MATERIALS', 'is_required': True, 'description': 'Comprehensive learner guide covering all modules'},
            {'title': 'Facilitator Guide', 'category': 'MATERIALS', 'is_required': True, 'description': 'Facilitator guide with session plans and activities'},
            {'title': 'Assessment Pack', 'category': 'MATERIALS', 'is_required': True, 'description': 'Complete assessment instruments and marking guides'},
            {'title': 'POE Templates', 'category': 'MATERIALS', 'is_required': True, 'description': 'Portfolio of Evidence templates and guides'},
            {'title': 'Digital Learning Content', 'category': 'MATERIALS', 'is_required': False, 'description': 'Online or blended learning content (if applicable)'},
            
            # Compliance & Policies
            {'title': 'Appeals and Complaints Policy', 'category': 'COMPLIANCE', 'is_required': True, 'description': 'Documented appeals and complaints procedure'},
            {'title': 'RPL Policy', 'category': 'COMPLIANCE', 'is_required': True, 'description': 'Recognition of Prior Learning policy and procedures'},
            {'title': 'Moderation Policy', 'category': 'COMPLIANCE', 'is_required': True, 'description': 'Internal and external moderation procedures'},
            {'title': 'Assessment Policy', 'category': 'COMPLIANCE', 'is_required': True, 'description': 'Assessment policy aligned with QCTO requirements'},
            {'title': 'Data Protection Policy', 'category': 'COMPLIANCE', 'is_required': True, 'description': 'POPIA compliant learner data handling procedures'},
        ]
        
        for i, item_data in enumerate(default_items, start=1):
            AccreditationChecklistItem.objects.get_or_create(
                qualification=self,
                title=item_data['title'],
                defaults={
                    'category': item_data['category'],
                    'is_required': item_data['is_required'],
                    'description': item_data['description'],
                    'sequence_order': i
                }
            )
    
    @property
    def is_registration_valid(self):
        from django.utils import timezone
        today = timezone.now().date()
        return self.registration_start <= today <= self.registration_end
    
    @property
    def accreditation_status(self):
        """Return accreditation status based on expiry date"""
        if not self.accreditation_expiry:
            return 'UNKNOWN'
        
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        
        if self.accreditation_expiry < today:
            return 'EXPIRED'
        elif self.accreditation_expiry <= today + timedelta(days=180):
            return 'EXPIRING'
        else:
            return 'ACTIVE'
    
    @property
    def days_until_expiry(self):
        """Calculate days until accreditation expires"""
        if not self.accreditation_expiry:
            return None
        
        from django.utils import timezone
        today = timezone.now().date()
        delta = self.accreditation_expiry - today
        return delta.days
    
    @property
    def is_qcto_programme(self):
        """Check if this is a QCTO-accredited Occupational Certificate"""
        return self.qualification_type == 'OC'
    
    @property
    def is_legacy_programme(self):
        """Check if this is a legacy SETA-accredited programme"""
        return self.qualification_type in ('NC', 'ND', 'SP', 'LP', 'PQ')
    
    @property
    def accrediting_body(self):
        """Return the accrediting body abbreviation based on qualification type"""
        if self.is_qcto_programme:
            return 'QCTO'
        return self.seta.abbreviation if self.seta else 'SETA'
    
    @property
    def accrediting_body_full(self):
        """Return the full accrediting body name"""
        if self.is_qcto_programme:
            return 'Quality Council for Trades and Occupations'
        return self.seta.name if self.seta else 'SETA'
    
    @property
    def programme_type_label(self):
        """Return a descriptive label for the programme type"""
        if self.is_qcto_programme:
            return 'Occupational Programme'
        return 'Legacy Programme'

    # Pricing helper methods
    def get_current_pricing(self):
        """Get currently effective pricing for this qualification"""
        from django.utils import timezone
        today = timezone.now().date()
        return self.pricing_history.filter(
            effective_from__lte=today,
            is_active=True
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=today)
        ).order_by('-effective_from').first()
    
    def get_pricing_for_year(self, academic_year):
        """Get pricing for a specific academic year"""
        return self.pricing_history.filter(
            academic_year=academic_year,
            is_active=True
        ).order_by('-effective_from').first()
    
    def get_pricing_for_date(self, date):
        """Get pricing effective on a specific date"""
        return self.pricing_history.filter(
            effective_from__lte=date,
            is_active=True
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=date)
        ).order_by('-effective_from').first()


class QualificationPricing(AuditedModel):
    """
    Pricing history for qualifications with effective dates.
    Tracks historical and future pricing with full audit trail.
    Stores total all-inclusive price shown to learners, with internal breakdown for accounting.
    """
    qualification = models.ForeignKey(
        Qualification,
        on_delete=models.CASCADE,
        related_name='pricing_history'
    )
    
    # Effective dates for pricing history
    effective_from = models.DateField(
        help_text="Date this pricing becomes effective"
    )
    effective_to = models.DateField(
        null=True, blank=True,
        help_text="Date this pricing expires (null = current)"
    )
    
    # Academic year this pricing applies to
    academic_year = models.PositiveIntegerField(
        help_text="Academic year (e.g., 2026)"
    )
    
    # Total all-inclusive price shown to learners
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total all-inclusive price shown to learners"
    )
    
    # Internal breakdown for accounting (not shown to learners)
    registration_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Internal: Registration fee component"
    )
    tuition_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Internal: Tuition fee component"
    )
    materials_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Internal: Materials fee component"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-academic_year', '-effective_from']
        verbose_name = 'Qualification Pricing'
        verbose_name_plural = 'Qualification Pricing'
        indexes = [
            models.Index(fields=['qualification', 'academic_year']),
            models.Index(fields=['effective_from', 'effective_to']),
        ]
    
    def __str__(self):
        return f"{self.qualification.short_title} - {self.academic_year} - R{self.total_price:,.2f}"
    
    @property
    def is_current(self):
        """Check if this pricing is currently effective"""
        from django.utils import timezone
        today = timezone.now().date()
        if self.effective_from > today:
            return False
        if self.effective_to and self.effective_to < today:
            return False
        return self.is_active
    
    def save(self, *args, **kwargs):
        """Auto-close previous pricing when saving new pricing for same qualification/year"""
        if not self.pk:  # New record
            # Close any existing open pricing for same qualification and year
            from django.utils import timezone
            yesterday = self.effective_from - timezone.timedelta(days=1)
            QualificationPricing.objects.filter(
                qualification=self.qualification,
                academic_year=self.academic_year,
                effective_to__isnull=True,
                is_active=True
            ).exclude(pk=self.pk).update(effective_to=yesterday)
        super().save(*args, **kwargs)


class Module(AuditedModel):
    """
    Module within a Qualification
    Can be Knowledge, Practical, or Workplace component
    """
    MODULE_TYPES = [
        ('K', 'Knowledge'),
        ('P', 'Practical'),
        ('W', 'Workplace'),
    ]
    
    COMPONENT_PHASES = [
        ('INSTITUTIONAL', 'Institutional'),
        ('WORKPLACE', 'Workplace'),
    ]
    
    YEAR_LEVEL_CHOICES = [
        (1, 'Year 1'),
        (2, 'Year 2'),
        (3, 'Year 3'),
    ]
    
    qualification = models.ForeignKey(
        Qualification, 
        on_delete=models.CASCADE, 
        related_name='modules'
    )
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Classification
    module_type = models.CharField(max_length=1, choices=MODULE_TYPES)
    credits = models.PositiveIntegerField()
    notional_hours = models.PositiveIntegerField()
    
    # Year and Component Phase (QCTO structure)
    year_level = models.PositiveIntegerField(
        choices=YEAR_LEVEL_CHOICES,
        default=1,
        help_text='Which year of study this module belongs to'
    )
    component_phase = models.CharField(
        max_length=15,
        choices=COMPONENT_PHASES,
        blank=True,
        help_text='Auto-set based on module type: K/P = Institutional, W = Workplace'
    )
    
    # Ordering
    sequence_order = models.PositiveIntegerField(default=1)
    is_compulsory = models.BooleanField(default=True)
    
    # Prerequisites
    prerequisites = models.ManyToManyField(
        'self', 
        symmetrical=False, 
        blank=True,
        related_name='required_for'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['qualification', 'year_level', 'sequence_order']
        unique_together = ['qualification', 'code']
    
    def __str__(self):
        return f"{self.code} - {self.title}"
    
    def save(self, *args, **kwargs):
        # Auto-set component_phase based on module_type
        if self.module_type in ['K', 'P']:
            self.component_phase = 'INSTITUTIONAL'
        elif self.module_type == 'W':
            self.component_phase = 'WORKPLACE'
        super().save(*args, **kwargs)
    
    @property
    def is_institutional(self):
        """Returns True if this is an institutional (Knowledge/Practical) module"""
        return self.component_phase == 'INSTITUTIONAL'
    
    @property
    def is_workplace(self):
        """Returns True if this is a workplace module"""
        return self.component_phase == 'WORKPLACE'


class UnitStandard(models.Model):
    """
    SAQA Unit Standard
    """
    saqa_id = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=500)
    nqf_level = models.PositiveIntegerField()
    credits = models.PositiveIntegerField()
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['saqa_id']
        verbose_name = 'Unit Standard'
        verbose_name_plural = 'Unit Standards'
    
    def __str__(self):
        return f"{self.saqa_id} - {self.title}"


class ModuleUnitStandard(models.Model):
    """
    Links Unit Standards to Modules
    """
    module = models.ForeignKey(
        Module, 
        on_delete=models.CASCADE,
        related_name='unit_standards'
    )
    unit_standard = models.ForeignKey(
        UnitStandard, 
        on_delete=models.CASCADE,
        related_name='modules'
    )
    
    class Meta:
        unique_together = ['module', 'unit_standard']
        verbose_name = 'Module Unit Standard'
        verbose_name_plural = 'Module Unit Standards'
    
    def __str__(self):
        return f"{self.module.code} - {self.unit_standard.saqa_id}"


class Enrollment(TenantAwareModel):
    """
    Learner enrollment in a Qualification
    Full lifecycle tracking from application to certification
    """
    STATUS_CHOICES = [
        ('APPLIED', 'Applied'),
        ('DOC_CHECK', 'Document Check'),
        ('REGISTERED', 'Registered'),
        ('ENROLLED', 'Enrolled'),
        ('ACTIVE', 'Active'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('CERTIFIED', 'Certified'),
        ('WITHDRAWN', 'Withdrawn'),
        ('TRANSFERRED', 'Transferred'),
        ('EXPIRED', 'Expired'),
    ]
    
    FUNDING_TYPES = [
        ('SELF', 'Self-funded'),
        ('EMPLOYER', 'Employer-funded'),
        ('BURSARY', 'Bursary'),
        ('LEARNERSHIP', 'Learnership'),
        ('INTERNSHIP', 'Internship'),
        ('SKILLS_PROG', 'Skills Programme'),
        ('DISCRETIONARY', 'Discretionary Grant'),
        ('PIVOTAL', 'PIVOTAL Grant'),
    ]
    
    # Reference
    enrollment_number = models.CharField(max_length=30, unique=True)
    
    # Links
    learner = models.ForeignKey(
        'learners.Learner', 
        on_delete=models.PROTECT, 
        related_name='enrollments'
    )
    qualification = models.ForeignKey(
        Qualification, 
        on_delete=models.PROTECT, 
        related_name='enrollments'
    )
    cohort = models.ForeignKey(
        'logistics.Cohort', 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='enrollments'
    )
    
    # Dates
    application_date = models.DateField()
    enrollment_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    expected_completion = models.DateField()
    actual_completion = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='APPLIED')
    status_reason = models.TextField(blank=True)
    status_changed_at = models.DateTimeField(auto_now=True)
    
    # Funding
    funding_type = models.CharField(max_length=20, choices=FUNDING_TYPES, default='SELF')
    funding_source = models.CharField(max_length=100, blank=True)
    funding_reference = models.CharField(max_length=50, blank=True)
    
    # Agreement
    agreement_signed = models.BooleanField(default=False)
    agreement_date = models.DateField(null=True, blank=True)
    agreement_document = models.ForeignKey(
        'learners.Document',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='enrollment_agreements'
    )
    
    # NLRD Tracking
    nlrd_submitted = models.BooleanField(default=False)
    nlrd_submission_date = models.DateField(null=True, blank=True)
    nlrd_reference = models.CharField(max_length=50, blank=True)
    
    # Certification
    certificate_number = models.CharField(max_length=50, blank=True)
    certificate_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-application_date']
        indexes = [
            models.Index(fields=['enrollment_number']),
            models.Index(fields=['learner', 'status']),
            models.Index(fields=['qualification', 'status']),
        ]
    
    def __str__(self):
        return f"{self.enrollment_number} - {self.learner}"
    
    def get_progress_percentage(self):
        """Calculate completion progress based on assessment results"""
        from assessments.models import AssessmentResult
        
        total_activities = self.qualification.modules.aggregate(
            total=models.Count('assessment_activities')
        )['total'] or 0
        
        if total_activities == 0:
            return 0
        
        completed = AssessmentResult.objects.filter(
            enrollment=self,
            result='C',
            status='FINALIZED'
        ).count()
        
        return int((completed / total_activities) * 100)
    
    def get_year_progress(self, year_level):
        """
        Calculate completion progress for a specific year
        Returns dict with progress data for that year
        """
        modules = self.qualification.modules.filter(year_level=year_level, is_active=True)
        total_modules = modules.count()
        
        if total_modules == 0:
            return {
                'year': year_level,
                'total_modules': 0,
                'completed_modules': 0,
                'in_progress_modules': 0,
                'not_started_modules': 0,
                'progress_percent': 0,
                'institutional_progress': 0,
                'workplace_progress': 0,
            }
        
        # Get module progress records
        progress_records = self.module_progress.filter(module__in=modules)
        
        completed = progress_records.filter(overall_status='COMPETENT').count()
        in_progress = progress_records.filter(overall_status='IN_PROGRESS').count()
        not_started = total_modules - completed - in_progress
        
        # Institutional vs Workplace breakdown
        institutional_modules = modules.filter(component_phase='INSTITUTIONAL')
        workplace_modules = modules.filter(component_phase='WORKPLACE')
        
        inst_completed = progress_records.filter(
            module__in=institutional_modules, 
            overall_status='COMPETENT'
        ).count()
        inst_total = institutional_modules.count()
        inst_progress = int((inst_completed / inst_total) * 100) if inst_total > 0 else 0
        
        wbl_completed = progress_records.filter(
            module__in=workplace_modules, 
            overall_status='COMPETENT'
        ).count()
        wbl_total = workplace_modules.count()
        wbl_progress = int((wbl_completed / wbl_total) * 100) if wbl_total > 0 else 0
        
        return {
            'year': year_level,
            'total_modules': total_modules,
            'completed_modules': completed,
            'in_progress_modules': in_progress,
            'not_started_modules': not_started,
            'progress_percent': int((completed / total_modules) * 100),
            'institutional_progress': inst_progress,
            'workplace_progress': wbl_progress,
            'institutional_total': inst_total,
            'institutional_completed': inst_completed,
            'workplace_total': wbl_total,
            'workplace_completed': wbl_completed,
        }
    
    def get_institutional_progress(self):
        """
        Calculate overall institutional (Knowledge + Practical) progress
        Returns progress across all years for institutional modules
        """
        modules = self.qualification.modules.filter(
            component_phase='INSTITUTIONAL', 
            is_active=True
        )
        total = modules.count()
        
        if total == 0:
            return {'total': 0, 'completed': 0, 'progress_percent': 0}
        
        completed = self.module_progress.filter(
            module__in=modules,
            overall_status='COMPETENT'
        ).count()
        
        return {
            'total': total,
            'completed': completed,
            'progress_percent': int((completed / total) * 100),
            'in_progress': self.module_progress.filter(
                module__in=modules,
                overall_status='IN_PROGRESS'
            ).count(),
        }
    
    def get_workplace_progress(self):
        """
        Calculate overall workplace progress
        Includes both module completion and stint/time tracking
        """
        modules = self.qualification.modules.filter(
            component_phase='WORKPLACE', 
            is_active=True
        )
        total_modules = modules.count()
        
        completed_modules = self.module_progress.filter(
            module__in=modules,
            overall_status='COMPETENT'
        ).count() if total_modules > 0 else 0
        
        # Calculate stint progress
        from corporate.models import WorkplaceStint, WorkplacePlacement
        
        stints = WorkplaceStint.objects.filter(
            qualification=self.qualification,
            is_active=True
        )
        
        stint_data = []
        for stint in stints:
            placements = WorkplacePlacement.objects.filter(
                enrollment=self,
                workplace_stint=stint
            )
            total_days = sum(p.duration_days for p in placements if p.status in ['ACTIVE', 'COMPLETED'])
            stint_data.append({
                'stint': stint,
                'days_completed': total_days,
                'days_required': stint.duration_days_required,
                'progress_percent': min(100, int((total_days / stint.duration_days_required) * 100)) if stint.duration_days_required > 0 else 0,
                'is_complete': total_days >= stint.duration_days_required,
            })
        
        stints_complete = sum(1 for s in stint_data if s['is_complete'])
        
        return {
            'modules_total': total_modules,
            'modules_completed': completed_modules,
            'modules_progress_percent': int((completed_modules / total_modules) * 100) if total_modules > 0 else 0,
            'stints': stint_data,
            'stints_total': len(stint_data),
            'stints_complete': stints_complete,
            'stints_progress_percent': int((stints_complete / len(stint_data)) * 100) if stint_data else 0,
        }
    
    def get_current_year(self):
        """
        Determine learner's current year based on module completion
        Returns year level (1, 2, or 3) based on combination of 
        modules in progress and completed
        """
        # Check Year 3 first (most advanced)
        year3_progress = self.get_year_progress(3)
        if year3_progress['in_progress_modules'] > 0 or year3_progress['completed_modules'] > 0:
            if year3_progress['total_modules'] > 0:
                return 3
        
        # Check Year 2
        year2_progress = self.get_year_progress(2)
        if year2_progress['in_progress_modules'] > 0:
            return 2
        if year2_progress['completed_modules'] > 0 and year2_progress['completed_modules'] < year2_progress['total_modules']:
            return 2
        
        # Check if Year 1 is complete (would mean they're in Year 2)
        year1_progress = self.get_year_progress(1)
        if year1_progress['completed_modules'] >= year1_progress['total_modules'] and year1_progress['total_modules'] > 0:
            # Year 1 complete, check if any Year 2 activity
            if year2_progress['total_modules'] > 0:
                return 2
        
        # Default to Year 1
        return 1
    
    def get_progress_by_component(self):
        """
        Get comprehensive progress breakdown by year and component
        Returns structured data for year-based progress view
        """
        years_data = {}
        
        for year_level in [1, 2, 3]:
            year_data = self.get_year_progress(year_level)
            if year_data['total_modules'] > 0:
                # Get detailed module list for this year
                modules = self.qualification.modules.filter(
                    year_level=year_level, 
                    is_active=True
                ).select_related()
                
                institutional_modules = []
                workplace_modules = []
                
                for module in modules:
                    progress = self.module_progress.filter(module=module).first()
                    module_data = {
                        'module': module,
                        'progress': progress,
                        'formative_status': progress.formative_status if progress else 'NOT_STARTED',
                        'summative_status': progress.summative_status if progress else 'NOT_STARTED',
                        'overall_status': progress.overall_status if progress else 'NOT_STARTED',
                        'is_overridden': progress.is_manually_overridden if progress else False,
                    }
                    
                    if module.component_phase == 'INSTITUTIONAL':
                        institutional_modules.append(module_data)
                    else:
                        workplace_modules.append(module_data)
                
                year_data['institutional_modules'] = institutional_modules
                year_data['workplace_modules'] = workplace_modules
                years_data[year_level] = year_data
        
        return {
            'years': years_data,
            'current_year': self.get_current_year(),
            'institutional_total': self.get_institutional_progress(),
            'workplace_total': self.get_workplace_progress(),
            'overall_progress': self.get_progress_percentage(),
        }


class EnrollmentStatusHistory(models.Model):
    """
    Tracks enrollment status changes for audit
    """
    enrollment = models.ForeignKey(
        Enrollment, 
        on_delete=models.CASCADE, 
        related_name='status_history'
    )
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    reason = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'Enrollment Status History'
        verbose_name_plural = 'Enrollment Status Histories'
    
    def __str__(self):
        return f"{self.enrollment} - {self.from_status} → {self.to_status}"


class AccreditationChecklistItem(AuditedModel):
    """
    Checklist item for qualification accreditation requirements
    Can be QCTO standard items or qualification-specific
    """
    CATEGORY_CHOICES = [
        ('DOCUMENTATION', 'Documentation'),
        ('PERSONNEL', 'Personnel & Staffing'),
        ('FACILITIES', 'Facilities & Equipment'),
        ('MATERIALS', 'Learning Materials'),
        ('COMPLIANCE', 'Compliance & Policies'),
    ]
    
    qualification = models.ForeignKey(
        Qualification,
        on_delete=models.CASCADE,
        related_name='checklist_items'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    is_required = models.BooleanField(default=True)
    sequence_order = models.PositiveIntegerField(default=1)
    
    class Meta:
        ordering = ['qualification', 'category', 'sequence_order']
        verbose_name = 'Accreditation Checklist Item'
        verbose_name_plural = 'Accreditation Checklist Items'
    
    def __str__(self):
        return f"{self.qualification.saqa_id} - {self.title}"


class AccreditationChecklistProgress(AuditedModel):
    """
    Tracks completion of accreditation checklist items
    """
    checklist_item = models.ForeignKey(
        AccreditationChecklistItem,
        on_delete=models.CASCADE,
        related_name='progress_records'
    )
    completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='completed_checklist_items'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    evidence_documents = models.ManyToManyField(
        'learners.Document',
        blank=True,
        related_name='checklist_evidence'
    )
    
    class Meta:
        ordering = ['-completed_at']
        verbose_name = 'Accreditation Checklist Progress'
        verbose_name_plural = 'Accreditation Checklist Progress'
    
    def __str__(self):
        status = "✓" if self.completed else "○"
        return f"{status} {self.checklist_item.title}"


class ComplianceDocument(AuditedModel):
    """
    Compliance documents for OHS, fire safety, SETA policies
    Can be campus-specific or organisation-wide
    """
    DOCUMENT_TYPE_CHOICES = [
        ('OHS_POLICY', 'OHS Policy'),
        ('FIRE_CERT', 'Fire Safety Certificate'),
        ('FIRST_AID', 'First Aid Certificate'),
        ('EVACUATION_PLAN', 'Evacuation Plan'),
        ('SETA_LETTER', 'SETA Accreditation Letter'),
        ('ACCREDITATION', 'Accreditation Certificate'),
        ('INSURANCE', 'Insurance Certificate'),
        ('BUSINESS_LICENSE', 'Business License'),
        ('LEASE_AGREEMENT', 'Lease Agreement'),
        ('EQUIPMENT_CERT', 'Equipment Certification'),
        ('OTHER', 'Other Compliance Document'),
    ]
    
    title = models.CharField(max_length=200)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # File
    file = models.FileField(upload_to='compliance/%Y/%m/')
    file_size = models.PositiveIntegerField(default=0)
    
    # Scope
    campus = models.ForeignKey(
        'tenants.Campus',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='compliance_documents',
        help_text="Leave blank for organisation-wide documents"
    )
    
    # Expiry
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    reminder_days = models.PositiveIntegerField(
        default=180,
        help_text="Days before expiry to trigger reminder"
    )
    
    # Verification
    verified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_compliance_docs'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Compliance Document'
        verbose_name_plural = 'Compliance Documents'
    
    def __str__(self):
        scope = f"{self.campus.name}" if self.campus else "Organisation-wide"
        return f"{self.get_document_type_display()} - {scope}"
    
    @property
    def compliance_status(self):
        """Return compliance status based on expiry date"""
        if not self.expiry_date:
            return 'NO_EXPIRY'
        
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        
        if self.expiry_date < today:
            return 'EXPIRED'
        elif self.expiry_date <= today + timedelta(days=self.reminder_days):
            return 'EXPIRING'
        else:
            return 'VALID'
    
    @property
    def days_until_expiry(self):
        """Calculate days until document expires"""
        if not self.expiry_date:
            return None
        
        from django.utils import timezone
        today = timezone.now().date()
        delta = self.expiry_date - today
        return delta.days


class AccreditationAlert(AuditedModel):
    """
    Automated alerts for expiring accreditations and compliance documents
    """
    ALERT_TYPE_CHOICES = [
        ('6_MONTHS', '6 Months Notice'),
        ('3_MONTHS', '3 Months Notice'),
        ('1_MONTH', '1 Month Notice'),
        ('EXPIRED', 'Expired'),
    ]
    
    # Polymorphic link to either Qualification or ComplianceDocument
    qualification = models.ForeignKey(
        Qualification,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='accreditation_alerts'
    )
    compliance_document = models.ForeignKey(
        ComplianceDocument,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='compliance_alerts'
    )
    
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    alert_date = models.DateField()
    message = models.TextField()
    
    # Resolution
    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='acknowledged_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    action_taken = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['alert_date', '-created_at']
        verbose_name = 'Accreditation Alert'
        verbose_name_plural = 'Accreditation Alerts'
    
    def __str__(self):
        if self.qualification:
            return f"{self.get_alert_type_display()} - {self.qualification.short_title}"
        elif self.compliance_document:
            return f"{self.get_alert_type_display()} - {self.compliance_document.title}"
        return f"Alert {self.pk}"


class PersonnelRegistration(AuditedModel):
    """
    Track facilitator/assessor/moderator SETA registrations
    """
    PERSONNEL_TYPE_CHOICES = [
        ('FACILITATOR', 'Facilitator'),
        ('ASSESSOR', 'Assessor'),
        ('MODERATOR', 'Moderator'),
        ('SKILLS_DEV_FACILITATOR', 'Skills Development Facilitator'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='personnel_registrations'
    )
    personnel_type = models.CharField(max_length=30, choices=PERSONNEL_TYPE_CHOICES)
    
    # Registration details
    registration_number = models.CharField(max_length=50)
    seta = models.ForeignKey(
        'learners.SETA',
        on_delete=models.PROTECT,
        related_name='personnel_registrations'
    )
    
    # Validity
    registration_date = models.DateField()
    expiry_date = models.DateField()
    
    # Certificate
    certificate = models.FileField(
        upload_to='personnel/registrations/%Y/',
        null=True,
        blank=True
    )
    
    # Linked qualifications
    qualifications = models.ManyToManyField(
        Qualification,
        blank=True,
        related_name='registered_personnel'
    )
    
    # Linked campuses (where this person can work)
    campuses = models.ManyToManyField(
        'tenants.Campus',
        blank=True,
        related_name='registered_personnel',
        help_text='Campuses where this person is allocated to work'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['user', '-registration_date']
        verbose_name = 'Personnel Registration'
        verbose_name_plural = 'Personnel Registrations'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_personnel_type_display()} ({self.registration_number})"
    
    @property
    def registration_status(self):
        """Return registration status based on expiry date"""
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        
        if self.expiry_date < today:
            return 'EXPIRED'
        elif self.expiry_date <= today + timedelta(days=180):
            return 'EXPIRING'
        else:
            return 'ACTIVE'
    
    @property
    def days_until_expiry(self):
        """Calculate days until registration expires"""
        from django.utils import timezone
        today = timezone.now().date()
        delta = self.expiry_date - today
        return delta.days


class QualificationCampusAccreditationManager(models.Manager):
    """
    Custom manager for QualificationCampusAccreditation with bulk expiry updates
    """
    def update_expired_statuses(self):
        """
        Bulk update ACTIVE accreditations that are past their accredited_until date to EXPIRED.
        Call this at the start of views to ensure status is always current.
        Returns the number of records updated.
        """
        from django.utils import timezone
        today = timezone.now().date()
        
        return self.filter(
            status='ACTIVE',
            accredited_until__lt=today
        ).update(status='EXPIRED')
    
    def get_active_for_campus(self, campus):
        """Get all active accreditations for a specific campus"""
        return self.filter(campus=campus, status='ACTIVE')
    
    def get_expiring_soon(self, days=180):
        """Get all ACTIVE accreditations expiring within the specified days"""
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        threshold = today + timedelta(days=days)
        
        return self.filter(
            status='ACTIVE',
            accredited_until__lte=threshold,
            accredited_until__gte=today
        )


class QualificationCampusAccreditation(AuditedModel):
    """
    Track which campuses are accredited to deliver specific qualifications.
    Each campus can have multiple accreditation letters over time with different
    accreditation cycles and date ranges.
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SUPERSEDED', 'Superseded'),
        ('EXPIRED', 'Expired'),
    ]
    
    qualification = models.ForeignKey(
        Qualification,
        on_delete=models.CASCADE,
        related_name='campus_accreditations'
    )
    campus = models.ForeignKey(
        'tenants.Campus',
        on_delete=models.CASCADE,
        related_name='qualification_accreditations'
    )
    
    # Letter details
    letter_reference = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Accreditation letter reference number"
    )
    letter_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Date the accreditation letter was issued"
    )
    
    # Accreditation scope (date range for this accreditation cycle)
    accredited_from = models.DateField(
        help_text="Start date of accreditation for this campus"
    )
    accredited_until = models.DateField(
        help_text="End date of accreditation for this campus"
    )
    learner_capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of learners this campus can enroll"
    )
    
    # Documentation
    accreditation_reference = models.CharField(max_length=100, blank=True)
    accreditation_document = models.FileField(
        upload_to='qualifications/campus_accreditation/%Y/',
        null=True,
        blank=True,
        help_text="Accreditation letter document"
    )
    
    # Status - manually managed, auto-expired via save() or management command
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        help_text="ACTIVE = current, SUPERSEDED = replaced by newer letter, EXPIRED = past end date"
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    objects = QualificationCampusAccreditationManager()
    
    class Meta:
        ordering = ['qualification', 'campus', '-accredited_until']
        # Removed unique_together to allow multiple accreditations per campus-qualification pair
        verbose_name = 'Campus Accreditation'
        verbose_name_plural = 'Campus Accreditations'
    
    def __str__(self):
        status_icon = {'ACTIVE': '🟢', 'SUPERSEDED': '🔵', 'EXPIRED': '🔴'}.get(self.status, '')
        return f"{status_icon} {self.qualification.short_title} @ {self.campus.name} ({self.accredited_from} - {self.accredited_until})"
    
    def save(self, *args, **kwargs):
        """Auto-set status to EXPIRED if past accredited_until date"""
        from django.utils import timezone
        today = timezone.now().date()
        
        # Only auto-expire if currently ACTIVE and past end date
        if self.status == 'ACTIVE' and self.accredited_until < today:
            self.status = 'EXPIRED'
        
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Returns True if accredited_until is in the past"""
        from django.utils import timezone
        today = timezone.now().date()
        return self.accredited_until < today
    
    @property
    def is_expiring_soon(self):
        """Returns True if ACTIVE and within 6 months (180 days) of expiry"""
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        
        if self.status != 'ACTIVE':
            return False
        
        threshold = today + timedelta(days=180)
        return today <= self.accredited_until <= threshold
    
    @property
    def days_until_expiry(self):
        """Calculate days until accreditation expires"""
        from django.utils import timezone
        today = timezone.now().date()
        delta = self.accredited_until - today
        return delta.days
    
    @property
    def accreditation_status(self):
        """Return accreditation status based on dates (for backwards compatibility)"""
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        
        if today < self.accredited_from:
            return 'PENDING'
        elif self.accredited_until < today:
            return 'EXPIRED'
        elif self.accredited_until <= today + timedelta(days=180):
            return 'EXPIRING'
        else:
            return 'ACTIVE'


class LearningMaterial(AuditedModel):
    """
    Track learning materials for qualifications
    """
    MATERIAL_TYPE_CHOICES = [
        ('LEARNER_GUIDE', 'Learner Guide'),
        ('FACILITATOR_GUIDE', 'Facilitator Guide'),
        ('ASSESSMENT_PACK', 'Assessment Pack'),
        ('POE_GUIDE', 'Portfolio of Evidence Guide'),
        ('WORKBOOK', 'Workbook'),
        ('PRESENTATION', 'Presentation Slides'),
        ('VIDEO', 'Video Content'),
        ('OTHER', 'Other Material'),
    ]
    
    qualification = models.ForeignKey(
        Qualification,
        on_delete=models.CASCADE,
        related_name='learning_materials'
    )
    material_type = models.CharField(max_length=30, choices=MATERIAL_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # File
    file = models.FileField(
        upload_to='learning_materials/%Y/',
        null=True,
        blank=True
    )
    external_url = models.URLField(blank=True, help_text="Link to LMS or external resource")
    
    # Version control
    version = models.CharField(max_length=20, default='1.0')
    last_reviewed = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    
    # Status
    is_current = models.BooleanField(default=True)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_materials'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['qualification', 'material_type', '-version']
        verbose_name = 'Learning Material'
        verbose_name_plural = 'Learning Materials'
    
    def __str__(self):
        return f"{self.qualification.short_title} - {self.get_material_type_display()} (v{self.version})"
    
    @property
    def review_status(self):
        """Return review status based on next review date"""
        if not self.next_review_date:
            return 'NO_REVIEW_DATE'
        
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        
        if self.next_review_date < today:
            return 'OVERDUE'
        elif self.next_review_date <= today + timedelta(days=90):
            return 'DUE_SOON'
        else:
            return 'CURRENT'


class LearnerModuleProgress(AuditedModel):
    """
    Tracks learner progress through individual modules
    Separates formative (internal) and summative (external) assessment status
    Supports auto-calculation with manual override capability
    """
    PROGRESS_STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPETENT', 'Competent'),
        ('NYC', 'Not Yet Competent'),
    ]
    
    enrollment = models.ForeignKey(
        'Enrollment',
        on_delete=models.CASCADE,
        related_name='module_progress'
    )
    module = models.ForeignKey(
        'Module',
        on_delete=models.CASCADE,
        related_name='learner_progress'
    )
    
    # Formative (internal) assessment status
    formative_status = models.CharField(
        max_length=15,
        choices=PROGRESS_STATUS_CHOICES,
        default='NOT_STARTED',
        help_text='Status of formative (internal) assessments for this module'
    )
    formative_completed_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When formative assessments were completed'
    )
    formative_competent_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of formative assessments marked competent'
    )
    formative_total_count = models.PositiveIntegerField(
        default=0,
        help_text='Total formative assessments for this module'
    )
    
    # Summative (external) assessment status
    summative_status = models.CharField(
        max_length=15,
        choices=PROGRESS_STATUS_CHOICES,
        default='NOT_STARTED',
        help_text='Status of summative (external/EISA) assessments for this module'
    )
    summative_completed_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When summative assessments were completed'
    )
    summative_competent_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of summative assessments marked competent'
    )
    summative_total_count = models.PositiveIntegerField(
        default=0,
        help_text='Total summative assessments for this module'
    )
    
    # Overall module status
    overall_status = models.CharField(
        max_length=15,
        choices=PROGRESS_STATUS_CHOICES,
        default='NOT_STARTED',
        help_text='Overall module completion status'
    )
    overall_completed_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When module was fully completed'
    )
    
    # Manual override functionality
    is_manually_overridden = models.BooleanField(
        default=False,
        help_text='If True, auto-calculation will be skipped for this record'
    )
    override_reason = models.TextField(
        blank=True,
        help_text='Reason for manual override'
    )
    overridden_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='module_progress_overrides',
        help_text='User who applied the manual override'
    )
    overridden_at = models.DateTimeField(
        null=True, blank=True,
        help_text='When the manual override was applied'
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text='Additional notes about learner progress'
    )
    
    class Meta:
        ordering = ['enrollment', 'module__year_level', 'module__sequence_order']
        unique_together = ['enrollment', 'module']
        verbose_name = 'Learner Module Progress'
        verbose_name_plural = 'Learner Module Progress'
    
    def __str__(self):
        return f"{self.enrollment.learner} - {self.module.code}: {self.get_overall_status_display()}"
    
    def calculate_progress(self, save=True):
        """
        Auto-calculate progress based on AssessmentResult records
        Respects is_manually_overridden flag
        """
        if self.is_manually_overridden:
            return  # Don't update if manually overridden
        
        from assessments.models import AssessmentResult, AssessmentActivity
        from django.utils import timezone
        
        # Get all assessment activities for this module
        activities = AssessmentActivity.objects.filter(module=self.module, is_active=True)
        
        # Separate formative and summative
        formative_activities = activities.filter(assessment_phase='FORMATIVE')
        summative_activities = activities.filter(assessment_phase='SUMMATIVE')
        
        # Count formative results
        self.formative_total_count = formative_activities.count()
        formative_results = AssessmentResult.objects.filter(
            enrollment=self.enrollment,
            activity__in=formative_activities,
            result='C',
            status='FINALIZED'
        ).values('activity').distinct()
        self.formative_competent_count = formative_results.count()
        
        # Update formative status
        if self.formative_total_count == 0:
            self.formative_status = 'NOT_STARTED'
        elif self.formative_competent_count >= self.formative_total_count:
            self.formative_status = 'COMPETENT'
            if not self.formative_completed_at:
                self.formative_completed_at = timezone.now()
        elif self.formative_competent_count > 0:
            self.formative_status = 'IN_PROGRESS'
        else:
            # Check if any attempts exist
            has_attempts = AssessmentResult.objects.filter(
                enrollment=self.enrollment,
                activity__in=formative_activities
            ).exists()
            self.formative_status = 'IN_PROGRESS' if has_attempts else 'NOT_STARTED'
        
        # Count summative results
        self.summative_total_count = summative_activities.count()
        summative_results = AssessmentResult.objects.filter(
            enrollment=self.enrollment,
            activity__in=summative_activities,
            result='C',
            status='FINALIZED'
        ).values('activity').distinct()
        self.summative_competent_count = summative_results.count()
        
        # Update summative status
        if self.summative_total_count == 0:
            self.summative_status = 'NOT_STARTED'
        elif self.summative_competent_count >= self.summative_total_count:
            self.summative_status = 'COMPETENT'
            if not self.summative_completed_at:
                self.summative_completed_at = timezone.now()
        elif self.summative_competent_count > 0:
            self.summative_status = 'IN_PROGRESS'
        else:
            has_attempts = AssessmentResult.objects.filter(
                enrollment=self.enrollment,
                activity__in=summative_activities
            ).exists()
            self.summative_status = 'IN_PROGRESS' if has_attempts else 'NOT_STARTED'
        
        # Calculate overall status
        if self.formative_status == 'COMPETENT' and self.summative_status == 'COMPETENT':
            self.overall_status = 'COMPETENT'
            if not self.overall_completed_at:
                self.overall_completed_at = timezone.now()
        elif self.formative_status == 'COMPETENT' and self.summative_total_count == 0:
            # Module only has formative assessments
            self.overall_status = 'COMPETENT'
            if not self.overall_completed_at:
                self.overall_completed_at = timezone.now()
        elif self.summative_status == 'COMPETENT' and self.formative_total_count == 0:
            # Module only has summative assessments
            self.overall_status = 'COMPETENT'
            if not self.overall_completed_at:
                self.overall_completed_at = timezone.now()
        elif self.formative_status == 'IN_PROGRESS' or self.summative_status == 'IN_PROGRESS':
            self.overall_status = 'IN_PROGRESS'
        elif self.formative_status == 'NOT_STARTED' and self.summative_status == 'NOT_STARTED':
            self.overall_status = 'NOT_STARTED'
        else:
            self.overall_status = 'IN_PROGRESS'
        
        if save:
            self.save()
    
    def apply_manual_override(self, user, formative_status=None, summative_status=None, 
                              overall_status=None, reason=''):
        """Apply a manual override to this progress record"""
        from django.utils import timezone
        
        self.is_manually_overridden = True
        self.override_reason = reason
        self.overridden_by = user
        self.overridden_at = timezone.now()
        
        if formative_status:
            self.formative_status = formative_status
            if formative_status == 'COMPETENT' and not self.formative_completed_at:
                self.formative_completed_at = timezone.now()
        
        if summative_status:
            self.summative_status = summative_status
            if summative_status == 'COMPETENT' and not self.summative_completed_at:
                self.summative_completed_at = timezone.now()
        
        if overall_status:
            self.overall_status = overall_status
            if overall_status == 'COMPETENT' and not self.overall_completed_at:
                self.overall_completed_at = timezone.now()
        
        self.save()
    
    def clear_manual_override(self):
        """Clear the manual override and recalculate"""
        self.is_manually_overridden = False
        self.override_reason = ''
        self.overridden_by = None
        self.overridden_at = None
        self.calculate_progress(save=True)
    
    @property
    def formative_progress_percent(self):
        """Percentage of formative assessments complete"""
        if self.formative_total_count == 0:
            return 0
        return int((self.formative_competent_count / self.formative_total_count) * 100)
    
    @property
    def summative_progress_percent(self):
        """Percentage of summative assessments complete"""
        if self.summative_total_count == 0:
            return 0
        return int((self.summative_competent_count / self.summative_total_count) * 100)
    
    @property
    def overall_progress_percent(self):
        """Overall progress percentage"""
        total = self.formative_total_count + self.summative_total_count
        if total == 0:
            return 0
        completed = self.formative_competent_count + self.summative_competent_count
        return int((completed / total) * 100)
    
    @property
    def is_complete(self):
        """Returns True if module is fully complete"""
        return self.overall_status == 'COMPETENT'


class QCTOSyncLog(AuditedModel):
    """
    Tracks QCTO data synchronization history
    Monthly sync on 15th + max 2 manual syncs per month
    """
    TRIGGER_TYPE_CHOICES = [
        ('SCHEDULED', 'Scheduled (15th)'),
        ('MANUAL', 'Manual Trigger'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    # Sync details
    synced_at = models.DateTimeField(auto_now_add=True)
    trigger_type = models.CharField(max_length=15, choices=TRIGGER_TYPE_CHOICES)
    triggered_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='qcto_syncs',
        help_text="User who triggered manual sync (null for scheduled)"
    )
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    
    # Results
    qualifications_checked = models.PositiveIntegerField(default=0)
    qualifications_updated = models.PositiveIntegerField(default=0)
    changes_detected = models.JSONField(
        default=list,
        blank=True,
        help_text="List of changes detected: [{saqa_id, field, old_value, new_value}]"
    )
    
    # Errors
    error_message = models.TextField(blank=True)
    
    # Duration
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-synced_at']
        verbose_name = 'QCTO Sync Log'
        verbose_name_plural = 'QCTO Sync Logs'
    
    def __str__(self):
        return f"QCTO Sync {self.synced_at.strftime('%Y-%m-%d %H:%M')} ({self.get_trigger_type_display()})"
    
    @classmethod
    def get_manual_sync_count_this_month(cls):
        """Count manual syncs in current month"""
        from django.utils import timezone
        from datetime import datetime
        now = timezone.now()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return cls.objects.filter(
            trigger_type='MANUAL',
            synced_at__gte=first_of_month,
            status__in=['COMPLETED', 'RUNNING', 'PENDING']
        ).count()
    
    @classmethod
    def can_trigger_manual_sync(cls):
        """Check if manual sync is allowed (max 2 per month)"""
        return cls.get_manual_sync_count_this_month() < 2
    
    @classmethod
    def get_last_sync(cls):
        """Get most recent successful sync"""
        return cls.objects.filter(status='COMPLETED').first()
    
    @classmethod
    def get_next_scheduled_sync(cls):
        """Calculate next scheduled sync date (15th of month)"""
        from django.utils import timezone
        from datetime import datetime
        import calendar
        
        now = timezone.now()
        # If before 15th this month, next sync is 15th this month
        if now.day < 15:
            return now.replace(day=15, hour=6, minute=0, second=0, microsecond=0)
        else:
            # Next sync is 15th of next month
            if now.month == 12:
                return now.replace(year=now.year + 1, month=1, day=15, hour=6, minute=0, second=0, microsecond=0)
            else:
                return now.replace(month=now.month + 1, day=15, hour=6, minute=0, second=0, microsecond=0)
    
    @property
    def duration_seconds(self):
        """Calculate sync duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class QCTOQualificationChange(AuditedModel):
    """
    Tracks detected changes from QCTO sync for review
    Changes shown in dashboard until acknowledged
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('DISMISSED', 'Dismissed'),
        ('APPLIED', 'Applied to System'),
    ]
    
    sync_log = models.ForeignKey(
        QCTOSyncLog,
        on_delete=models.CASCADE,
        related_name='qualification_changes'
    )
    qualification = models.ForeignKey(
        'Qualification',
        on_delete=models.CASCADE,
        related_name='qcto_changes'
    )
    
    # Change details
    field_name = models.CharField(max_length=100, help_text="Field that changed")
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    change_description = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_qcto_changes'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'QCTO Qualification Change'
        verbose_name_plural = 'QCTO Qualification Changes'
    
    def __str__(self):
        return f"{self.qualification.saqa_id}: {self.field_name} changed"


class QCTOAssessmentCriteria(AuditedModel):
    """
    Assessment criteria from QCTO website for specific modules.
    Used for AI-powered mapping to Moodle LMS activities.
    """
    module = models.ForeignKey(
        'Module',
        on_delete=models.CASCADE,
        related_name='qcto_criteria'
    )
    
    # Criteria details
    criteria_code = models.CharField(
        max_length=50,
        help_text="e.g., AC1.1, AC1.2 - Assessment Criteria identifier"
    )
    description = models.TextField(help_text="Full criteria description from QCTO")
    
    # Criticality
    is_critical = models.BooleanField(
        default=False,
        help_text="Critical criteria must be assessed for competence"
    )
    
    # Verification tracking
    manually_added = models.BooleanField(
        default=False,
        help_text="Manually added by SME vs scraped from QCTO"
    )
    verified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_criteria',
        help_text="SME who verified this criteria"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['module', 'criteria_code']
        verbose_name = 'QCTO Assessment Criteria'
        verbose_name_plural = 'QCTO Assessment Criteria'
        unique_together = [['module', 'criteria_code']]
    
    def __str__(self):
        return f"{self.module.code} - {self.criteria_code}: {self.description[:50]}..."


# ============================================================================
# Block Plan & Lesson Planning Models
# ============================================================================

class ImplementationPlan(AuditedModel):
    """
    Standard Implementation Plan for a qualification.
    Defines the delivery schedule structure that gets copied to each cohort implementation.
    Multiple plans can exist per qualification (e.g., full-time vs part-time).
    """
    DELIVERY_MODE_CHOICES = [
        ('FULL_TIME', 'Full-Time (Contact)'),
        ('PART_TIME', 'Part-Time'),
        ('BLENDED', 'Blended Learning'),
        ('DISTANCE', 'Distance Learning'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('ARCHIVED', 'Archived'),
    ]
    
    qualification = models.ForeignKey(
        Qualification,
        on_delete=models.CASCADE,
        related_name='implementation_plans'
    )
    
    name = models.CharField(max_length=200, help_text="e.g., 'Standard 12-Month Full-Time'")
    description = models.TextField(blank=True)
    delivery_mode = models.CharField(max_length=20, choices=DELIVERY_MODE_CHOICES, default='FULL_TIME')
    
    # Duration
    total_weeks = models.PositiveIntegerField(help_text="Total duration in weeks")
    contact_days_per_week = models.PositiveIntegerField(default=5, help_text="Training days per week")
    hours_per_day = models.PositiveIntegerField(default=6, help_text="Total hours per training day")
    classroom_hours_per_day = models.PositiveIntegerField(default=2, help_text="Classroom/theory hours per day")
    practical_hours_per_day = models.PositiveIntegerField(default=4, help_text="Practical hours per day")
    
    # Default status
    is_default = models.BooleanField(default=False, help_text="Default template for new cohorts")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    
    # Version tracking
    version = models.CharField(max_length=20, default='1.0')
    effective_from = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['qualification', '-is_default', 'name']
        verbose_name = 'Implementation Plan'
        verbose_name_plural = 'Implementation Plans'
    
    def __str__(self):
        default_marker = " (Default)" if self.is_default else ""
        return f"{self.qualification.short_title} - {self.name}{default_marker}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default per qualification
        if self.is_default:
            ImplementationPlan.objects.filter(
                qualification=self.qualification,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def total_classroom_hours(self):
        """Calculate total classroom hours across all institutional phases"""
        return sum(phase.classroom_hours for phase in self.phases.filter(phase_type='INSTITUTIONAL'))
    
    @property
    def total_practical_hours(self):
        """Calculate total practical hours across all institutional phases"""
        return sum(phase.practical_hours for phase in self.phases.filter(phase_type='INSTITUTIONAL'))
    
    @property
    def total_workplace_weeks(self):
        """Calculate total workplace stint weeks"""
        return sum(phase.duration_weeks for phase in self.phases.filter(phase_type='WORKPLACE_STINT'))
    
    @property
    def total_training_days(self):
        """Calculate total institutional training days"""
        return sum(phase.total_training_days for phase in self.phases.filter(phase_type='INSTITUTIONAL'))
    
    def copy_to_cohort(self, cohort, created_by):
        """
        Create a CohortImplementationPlan copy of this template for a specific cohort.
        Calculates planned dates based on the cohort's start_date.
        Returns the new CohortImplementationPlan instance.
        """
        from logistics.models import CohortImplementationPlan, CohortImplementationPhase, CohortImplementationModuleSlot
        from datetime import timedelta
        
        # Create the cohort implementation plan
        cohort_plan = CohortImplementationPlan.objects.create(
            cohort=cohort,
            source_template=self,
            created_by=created_by,
            name=self.name,
            delivery_mode=self.delivery_mode,
            total_weeks=self.total_weeks,
            contact_days_per_week=self.contact_days_per_week,
            hours_per_day=self.hours_per_day,
            classroom_hours_per_day=self.classroom_hours_per_day,
            practical_hours_per_day=self.practical_hours_per_day
        )
        
        # Calculate dates based on cohort start date
        # Use cohort.start_date or training_notification.planned_start_date
        start_date = None
        if cohort.start_date:
            start_date = cohort.start_date
        elif hasattr(cohort, 'not_intakes') and cohort.not_intakes.exists():
            not_intake = cohort.not_intakes.first()
            if not_intake.intake_date:
                start_date = not_intake.intake_date
            elif not_intake.training_notification.planned_start_date:
                start_date = not_intake.training_notification.planned_start_date
        
        # Copy phases with calculated dates
        current_date = start_date
        for phase in self.phases.all().order_by('sequence'):
            planned_start = current_date
            planned_end = None
            
            if current_date:
                # Calculate end date (add duration_weeks * 7 days)
                planned_end = current_date + timedelta(weeks=phase.duration_weeks)
                # Move current_date to the day after this phase ends
                current_date = planned_end
            
            cohort_phase = CohortImplementationPhase.objects.create(
                cohort_implementation_plan=cohort_plan,
                source_phase=phase,
                phase_type=phase.phase_type,
                name=phase.name,
                sequence=phase.sequence,
                duration_weeks=phase.duration_weeks,
                year_level=phase.year_level,
                description=phase.description,
                planned_start=planned_start,
                planned_end=planned_end,
            )
            
            # Copy module slots for institutional phases
            for slot in phase.module_slots.all():
                CohortImplementationModuleSlot.objects.create(
                    cohort_implementation_phase=cohort_phase,
                    source_slot=slot,
                    module=slot.module,
                    sequence=slot.sequence,
                    classroom_sessions=slot.classroom_sessions,
                    practical_sessions=slot.practical_sessions,
                    total_days=slot.total_days
                )
        
        return cohort_plan


class ImplementationPhase(AuditedModel):
    """
    A phase within an implementation plan.
    Phases are sequential and make up the overall training program.
    """
    PHASE_TYPE_CHOICES = [
        ('INDUCTION', 'Induction'),
        ('INSTITUTIONAL', 'Institutional'),
        ('WORKPLACE', 'Workplace'),
        ('WORKPLACE_STINT', 'Workplace Stint'),  # Legacy - kept for backward compatibility
        ('TRADE_TEST', 'Trade Test'),
        ('ASSESSMENT', 'Assessment'),
    ]
    
    implementation_plan = models.ForeignKey(
        ImplementationPlan,
        on_delete=models.CASCADE,
        related_name='phases'
    )
    
    phase_type = models.CharField(max_length=20, choices=PHASE_TYPE_CHOICES)
    name = models.CharField(max_length=100, help_text="e.g., 'Phase 1 - Knowledge Modules' or 'Stint 1'")
    sequence = models.PositiveIntegerField(help_text="Order in the overall plan")
    duration_weeks = models.PositiveIntegerField()
    year_level = models.PositiveIntegerField(default=1, help_text="Which year of study (1, 2, or 3)")
    description = models.TextField(blank=True)
    
    # Color coding for UI
    color = models.CharField(max_length=20, default='blue', help_text="Color for Gantt chart display")
    
    # Source tracking - link to standard block if created from one
    source_block = models.ForeignKey(
        'StandardBlock',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='generated_phases',
        help_text="Standard block this phase was generated from"
    )
    
    class Meta:
        ordering = ['implementation_plan', 'sequence']
        verbose_name = 'Implementation Phase'
        verbose_name_plural = 'Implementation Phases'
    
    def __str__(self):
        return f"{self.implementation_plan.name} - {self.name}"
    
    @property
    def is_institutional(self):
        return self.phase_type == 'INSTITUTIONAL'
    
    @property
    def is_workplace(self):
        return self.phase_type in ('WORKPLACE', 'WORKPLACE_STINT')
    
    @property
    def classroom_hours(self):
        """Total classroom hours for this phase"""
        if not self.is_institutional:
            return 0
        days = self.duration_weeks * self.implementation_plan.contact_days_per_week
        return days * self.implementation_plan.classroom_hours_per_day
    
    @property
    def practical_hours(self):
        """Total practical hours for this phase"""
        if not self.is_institutional:
            return 0
        days = self.duration_weeks * self.implementation_plan.contact_days_per_week
        return days * self.implementation_plan.practical_hours_per_day
    
    @property
    def total_training_days(self):
        """Total training days in this phase"""
        if self.is_workplace:
            return self.duration_weeks * 5  # Assume 5-day work week at host
        return self.duration_weeks * self.implementation_plan.contact_days_per_week
    
    @property
    def total_hours(self):
        """Total hours for this phase"""
        if self.is_workplace:
            return self.duration_weeks * 5 * 8  # 8 hour work days
        return self.classroom_hours + self.practical_hours


class ImplementationModuleSlot(AuditedModel):
    """
    A module slot within an institutional phase.
    Defines which module is delivered, in what order, and how many sessions.
    """
    phase = models.ForeignKey(
        ImplementationPhase,
        on_delete=models.CASCADE,
        related_name='module_slots'
    )
    
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='implementation_slots'
    )
    
    sequence = models.PositiveIntegerField(help_text="Order within the phase")
    
    # Session breakdown (based on 6hr day: 2hr classroom + 4hr practical)
    classroom_sessions = models.PositiveIntegerField(
        default=1,
        help_text="Number of classroom/theory sessions (2 hours each)"
    )
    practical_sessions = models.PositiveIntegerField(
        default=1,
        help_text="Number of practical sessions (4 hours each)"
    )
    total_days = models.PositiveIntegerField(
        help_text="Total training days for this module"
    )
    
    # Linked outcomes/unit standards
    linked_outcomes = models.ManyToManyField(
        'UnitStandard',
        blank=True,
        related_name='block_plan_slots',
        help_text="Unit standards/outcomes covered in this module slot"
    )
    
    notes = models.TextField(blank=True, help_text="Delivery notes for this module")
    
    # Source tracking - link to standard block module if created from one
    source_block_module = models.ForeignKey(
        'StandardBlockModule',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='generated_slots',
        help_text="Standard block module this slot was generated from"
    )
    
    class Meta:
        ordering = ['phase', 'sequence']
        verbose_name = 'Implementation Module Slot'
        verbose_name_plural = 'Implementation Module Slots'
        unique_together = ['phase', 'sequence']
    
    def __str__(self):
        return f"{self.phase.name} - {self.module.code} (Seq {self.sequence})"
    
    @property
    def total_classroom_hours(self):
        return self.classroom_sessions * self.phase.implementation_plan.classroom_hours_per_day
    
    @property
    def total_practical_hours(self):
        return self.practical_sessions * self.phase.implementation_plan.practical_hours_per_day
    
    @property
    def total_hours(self):
        return self.total_classroom_hours + self.total_practical_hours
    
    @property
    def module_type_display(self):
        """Return color-coded module type"""
        return self.module.get_module_type_display()


class LessonPlanTemplate(AuditedModel):
    """
    Lesson plan template for a specific session within a module.
    Provides structured content for facilitators including theory and practical components.
    Standard structure: 2hr classroom + 4hr practical = 6hr total per session.
    """
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='lesson_plans'
    )
    
    # Session identification
    session_number = models.PositiveIntegerField(help_text="Session number within the module (1, 2, 3...)")
    topic = models.CharField(max_length=200)
    
    # Learning outcomes
    learning_outcomes = models.JSONField(
        default=list,
        help_text="List of learning outcomes for this session"
    )
    
    # =========================================
    # CLASSROOM SEGMENT (2 hours default)
    # =========================================
    classroom_duration_minutes = models.PositiveIntegerField(default=120)
    
    # Introduction (10 min)
    classroom_introduction = models.TextField(
        blank=True,
        help_text="Opening activity, ice-breaker, and context setting"
    )
    
    # Main content topics
    classroom_topics = models.JSONField(
        default=list,
        help_text="List of theory topics with duration and content"
    )
    # Structure: [{"title": "Topic 1", "duration_minutes": 30, "content": "...", "key_points": ["..."]}]
    
    # Discussion questions
    discussion_questions = models.JSONField(
        default=list,
        help_text="Discussion questions to engage learners"
    )
    
    # Key concepts summary
    key_concepts = models.JSONField(
        default=list,
        help_text="Key concepts learners must understand"
    )
    
    # Classroom wrap-up
    classroom_summary = models.TextField(
        blank=True,
        help_text="Summary and transition to practical (10 min)"
    )
    
    # =========================================
    # PRACTICAL SEGMENT (4 hours default)
    # =========================================
    practical_duration_minutes = models.PositiveIntegerField(default=240)
    
    # Safety briefing
    safety_briefing = models.TextField(
        blank=True,
        help_text="Safety briefing and PPE requirements"
    )
    
    # Practical activities
    practical_activities = models.JSONField(
        default=list,
        help_text="Practical activities with instructions"
    )
    # Structure: [{"title": "Activity 1", "duration_minutes": 90, "description": "...", 
    #              "steps": ["..."], "equipment": ["..."], "assessment_criteria": ["..."]}]
    
    # Demonstration notes
    demonstration_notes = models.TextField(
        blank=True,
        help_text="What the facilitator should demonstrate"
    )
    
    # Practical debrief
    practical_debrief = models.TextField(
        blank=True,
        help_text="Review, Q&A, and feedback session"
    )
    
    # =========================================
    # RESOURCES & MATERIALS
    # =========================================
    resources_required = models.JSONField(
        default=list,
        help_text="Resources and materials needed"
    )
    # Structure: [{"type": "handout|equipment|consumable|digital", "name": "...", "quantity": N}]
    
    equipment_list = models.JSONField(
        default=list,
        help_text="Equipment and tools required"
    )
    
    consumables_list = models.JSONField(
        default=list,
        help_text="Consumable materials needed"
    )
    
    # =========================================
    # ASSESSMENT
    # =========================================
    has_assessment = models.BooleanField(default=False)
    assessment_type = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="e.g., Quiz, Practical demonstration, Observation"
    )
    assessment_criteria = models.JSONField(
        default=list,
        help_text="Assessment criteria for this session"
    )
    assessment_notes = models.TextField(blank=True)
    
    # =========================================
    # FACILITATOR GUIDANCE
    # =========================================
    facilitator_notes = models.TextField(
        blank=True, 
        help_text="Additional guidance for facilitators"
    )
    
    preparation_checklist = models.JSONField(
        default=list,
        help_text="Pre-session preparation checklist"
    )
    
    common_mistakes = models.JSONField(
        default=list,
        help_text="Common learner mistakes to watch for"
    )
    
    differentiation_notes = models.TextField(
        blank=True,
        help_text="How to adapt for different learner needs"
    )
    
    # =========================================
    # STATUS
    # =========================================
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_lesson_plans'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['module', 'session_number']
        unique_together = ['module', 'session_number']
        verbose_name = 'Lesson Plan Template'
        verbose_name_plural = 'Lesson Plan Templates'
    
    def __str__(self):
        return f"{self.module.code} - Session {self.session_number}: {self.topic}"
    
    @property
    def total_duration_minutes(self):
        return self.classroom_duration_minutes + self.practical_duration_minutes
    
    @property
    def total_duration_hours(self):
        return self.total_duration_minutes / 60
    
    def get_printable_format(self):
        """Return formatted lesson plan for printing"""
        return {
            'module': self.module,
            'session': self.session_number,
            'topic': self.topic,
            'duration': f"{self.total_duration_hours} hours",
            'learning_outcomes': self.learning_outcomes,
            'classroom': {
                'duration': f"{self.classroom_duration_minutes} min",
                'introduction': self.classroom_introduction,
                'topics': self.classroom_topics,
                'discussion_questions': self.discussion_questions,
                'key_concepts': self.key_concepts,
                'summary': self.classroom_summary,
            },
            'practical': {
                'duration': f"{self.practical_duration_minutes} min",
                'safety': self.safety_briefing,
                'activities': self.practical_activities,
                'demonstration': self.demonstration_notes,
                'debrief': self.practical_debrief,
            },
            'resources': self.resources_required,
            'equipment': self.equipment_list,
            'consumables': self.consumables_list,
            'assessment': {
                'has_assessment': self.has_assessment,
                'type': self.assessment_type,
                'criteria': self.assessment_criteria,
                'notes': self.assessment_notes,
            },
            'facilitator_notes': self.facilitator_notes,
            'preparation': self.preparation_checklist,
        }


# =============================================================================
# Workplace Module Outcomes (SAQA Curriculum Tasks)
# =============================================================================

class WorkplaceModuleOutcome(AuditedModel):
    """
    Individual task/outcome within a Workplace Module.
    Imported from SAQA curriculum document.
    Used for daily logbook task selection.
    """
    
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='workplace_outcomes',
        limit_choices_to={'module_type': 'W'},
        help_text="Workplace module this outcome belongs to"
    )
    
    # SAQA Outcome Details
    outcome_code = models.CharField(
        max_length=50,
        help_text="SAQA outcome code (e.g., WM1.1, WM1.2)"
    )
    outcome_number = models.PositiveIntegerField(
        default=1,
        help_text="Numeric ordering for the outcome"
    )
    title = models.CharField(
        max_length=500,
        help_text="Full outcome title from SAQA curriculum"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description or assessment criteria"
    )
    
    # Range Statement (from SAQA)
    range_statement = models.TextField(
        blank=True,
        help_text="Range statement or conditions from SAQA curriculum"
    )
    
    # Assessment Criteria
    assessment_criteria = models.TextField(
        blank=True,
        help_text="Assessment criteria for this outcome"
    )
    
    # Estimated hours to complete
    estimated_hours = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True, blank=True,
        help_text="Estimated hours to demonstrate this outcome"
    )
    
    # Grouping (some outcomes may be grouped together)
    outcome_group = models.CharField(
        max_length=100,
        blank=True,
        help_text="Group name if outcomes are grouped (e.g., 'Communication Skills')"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # SAQA Import Tracking
    saqa_source = models.CharField(
        max_length=255,
        blank=True,
        help_text="Source URL or document for SAQA import"
    )
    imported_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When this outcome was imported from SAQA"
    )
    
    class Meta:
        ordering = ['module', 'outcome_number']
        verbose_name = 'Workplace Module Outcome'
        verbose_name_plural = 'Workplace Module Outcomes'
        unique_together = ['module', 'outcome_code']
    
    def __str__(self):
        return f"{self.outcome_code}: {self.title[:50]}"
    
    @property
    def full_code(self):
        """Full code including module code"""
        return f"{self.module.code}-{self.outcome_code}"


# ============================================================================
# Standard Blocks for Academic Implementation Plans
# ============================================================================

class StandardBlock(AuditedModel):
    """
    Reusable institutional or workplace block template.
    Can be used across multiple qualifications to build implementation plans.
    """
    BLOCK_TYPE_CHOICES = [
        ('INSTITUTIONAL', 'Institutional Training'),
        ('WORKPLACE', 'Workplace Stint'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('ARCHIVED', 'Archived'),
    ]
    
    name = models.CharField(
        max_length=200,
        help_text="e.g., 'Standard 8-Week Foundational Knowledge Block'"
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Short code for reference (e.g., 'INST-FND-8W')"
    )
    description = models.TextField(blank=True)
    
    block_type = models.CharField(
        max_length=20,
        choices=BLOCK_TYPE_CHOICES,
        default='INSTITUTIONAL'
    )
    
    # Duration
    duration_weeks = models.PositiveIntegerField(
        help_text="Standard duration in weeks"
    )
    
    # Applicability - which qualification types can use this block
    applicable_qualification_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Qualification types (OC, NC, ND, PQ, SP, LP) this block applies to (empty = all)"
    )
    
    # For institutional blocks - timing configuration
    contact_days_per_week = models.PositiveIntegerField(
        default=5,
        help_text="Training days per week"
    )
    hours_per_day = models.PositiveIntegerField(
        default=6,
        help_text="Total hours per training day"
    )
    classroom_hours_per_day = models.PositiveIntegerField(
        default=2,
        help_text="Classroom/theory hours per day"
    )
    practical_hours_per_day = models.PositiveIntegerField(
        default=4,
        help_text="Practical hours per day"
    )
    
    # For workplace blocks - specific configuration
    workplace_hours_per_day = models.PositiveIntegerField(
        default=8,
        help_text="Hours per day for workplace blocks"
    )
    workplace_days_per_week = models.PositiveIntegerField(
        default=5,
        help_text="Days per week for workplace blocks"
    )
    
    # Status and versioning
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )
    version = models.CharField(max_length=20, default='1.0')
    
    # UI display
    color = models.CharField(
        max_length=20,
        default='blue',
        help_text="Color for Gantt chart display"
    )
    
    class Meta:
        ordering = ['block_type', 'name']
        verbose_name = 'Standard Block'
        verbose_name_plural = 'Standard Blocks'
    
    def __str__(self):
        return f"{self.code} - {self.name} ({self.duration_weeks}w)"
    
    @property
    def is_institutional(self):
        return self.block_type == 'INSTITUTIONAL'
    
    @property
    def is_workplace(self):
        return self.block_type == 'WORKPLACE'
    
    @property
    def total_training_days(self):
        """Calculate total training days"""
        if self.is_workplace:
            return self.duration_weeks * self.workplace_days_per_week
        return self.duration_weeks * self.contact_days_per_week
    
    @property
    def total_hours(self):
        """Calculate total hours"""
        if self.is_workplace:
            return self.total_training_days * self.workplace_hours_per_day
        return self.total_training_days * self.hours_per_day
    
    @property
    def total_classroom_hours(self):
        """Calculate total classroom hours (institutional only)"""
        if not self.is_institutional:
            return 0
        return self.total_training_days * self.classroom_hours_per_day
    
    @property
    def total_practical_hours(self):
        """Calculate total practical hours (institutional only)"""
        if not self.is_institutional:
            return 0
        return self.total_training_days * self.practical_hours_per_day
    
    def applies_to_qualification(self, qualification):
        """Check if this block can be used for a given qualification"""
        if not self.applicable_qualification_types:
            return True  # Empty list means applies to all
        return qualification.qualification_type in self.applicable_qualification_types
    
    def create_phase_from_block(self, implementation_plan, sequence, year_level=1, name_override=None):
        """
        Create an ImplementationPhase from this standard block.
        
        Args:
            implementation_plan: The ImplementationPlan to add the phase to
            sequence: The sequence number for this phase
            year_level: The year level (1, 2, or 3)
            name_override: Optional custom name for the phase
        
        Returns:
            Created ImplementationPhase instance
        """
        phase = ImplementationPhase.objects.create(
            implementation_plan=implementation_plan,
            phase_type=self.block_type,
            name=name_override or self.name,
            sequence=sequence,
            duration_weeks=self.duration_weeks,
            year_level=year_level,
            description=self.description,
            color=self.color,
            source_block=self,
        )
        
        # Copy module slots if this is an institutional block
        if self.is_institutional:
            for block_module in self.modules.all():
                ImplementationModuleSlot.objects.create(
                    phase=phase,
                    module=block_module.module,
                    sequence=block_module.sequence,
                    classroom_sessions=block_module.classroom_sessions,
                    practical_sessions=block_module.practical_sessions,
                    total_days=block_module.total_days,
                    notes=block_module.notes,
                    source_block_module=block_module,
                )
        
        return phase


class StandardBlockModule(AuditedModel):
    """
    A module slot within a standard block.
    Defines which modules are typically included in this type of block.
    """
    block = models.ForeignKey(
        StandardBlock,
        on_delete=models.CASCADE,
        related_name='modules'
    )
    
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='standard_block_slots',
        help_text="Module to include in this block"
    )
    
    sequence = models.PositiveIntegerField(
        help_text="Order within the block"
    )
    
    # Session breakdown (based on institutional hours settings)
    classroom_sessions = models.PositiveIntegerField(
        default=1,
        help_text="Number of classroom/theory sessions"
    )
    practical_sessions = models.PositiveIntegerField(
        default=1,
        help_text="Number of practical sessions"
    )
    total_days = models.PositiveIntegerField(
        help_text="Total training days for this module"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Delivery notes for this module in this block"
    )
    
    # Alternative modules that can substitute
    alternatives = models.ManyToManyField(
        Module,
        blank=True,
        related_name='alternative_for_block_slots',
        help_text="Alternative modules that can substitute for this one"
    )
    
    class Meta:
        ordering = ['block', 'sequence']
        verbose_name = 'Standard Block Module'
        verbose_name_plural = 'Standard Block Modules'
        unique_together = ['block', 'sequence']
    
    def __str__(self):
        return f"{self.block.code} - {self.module.code} (Seq {self.sequence})"
    
    @property
    def total_classroom_hours(self):
        """Calculate total classroom hours based on block settings"""
        return self.classroom_sessions * self.block.classroom_hours_per_day
    
    @property
    def total_practical_hours(self):
        """Calculate total practical hours based on block settings"""
        return self.practical_sessions * self.block.practical_hours_per_day
    
    @property
    def total_hours(self):
        return self.total_classroom_hours + self.total_practical_hours


class ImplementationPlanBlock(AuditedModel):
    """
    Links a standard block to an implementation plan with customization options.
    Tracks which standard blocks make up an implementation plan.
    """
    implementation_plan = models.ForeignKey(
        ImplementationPlan,
        on_delete=models.CASCADE,
        related_name='plan_blocks'
    )
    
    standard_block = models.ForeignKey(
        StandardBlock,
        on_delete=models.PROTECT,
        related_name='plan_usages'
    )
    
    # Position in the plan
    sequence = models.PositiveIntegerField(
        help_text="Order of this block in the implementation plan"
    )
    year_level = models.PositiveIntegerField(
        default=1,
        help_text="Which year of study (1, 2, or 3)"
    )
    
    # Customization
    custom_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Custom name for this block in this plan (overrides standard name)"
    )
    custom_duration_weeks = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Custom duration (overrides standard block duration)"
    )
    
    # Generated phase tracking
    generated_phase = models.OneToOneField(
        ImplementationPhase,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='source_plan_block'
    )
    
    class Meta:
        ordering = ['implementation_plan', 'sequence']
        verbose_name = 'Implementation Plan Block'
        verbose_name_plural = 'Implementation Plan Blocks'
        unique_together = ['implementation_plan', 'sequence']
    
    def __str__(self):
        name = self.custom_name or self.standard_block.name
        return f"{self.implementation_plan.name} - {name} (Seq {self.sequence})"
    
    @property
    def effective_name(self):
        """Get the effective name (custom or standard)"""
        return self.custom_name or self.standard_block.name
    
    @property
    def effective_duration_weeks(self):
        """Get the effective duration (custom or standard)"""
        return self.custom_duration_weeks or self.standard_block.duration_weeks
    
    def generate_phase(self, created_by=None):
        """
        Generate an ImplementationPhase from this plan block.
        Updates or creates the linked phase.
        """
        if self.generated_phase:
            # Update existing
            phase = self.generated_phase
            phase.name = self.effective_name
            phase.duration_weeks = self.effective_duration_weeks
            phase.sequence = self.sequence
            phase.year_level = self.year_level
            phase.save()
        else:
            # Create new using the standard block helper
            phase = self.standard_block.create_phase_from_block(
                implementation_plan=self.implementation_plan,
                sequence=self.sequence,
                year_level=self.year_level,
                name_override=self.custom_name if self.custom_name else None
            )
            self.generated_phase = phase
            self.save(update_fields=['generated_phase'])
        
        return phase
