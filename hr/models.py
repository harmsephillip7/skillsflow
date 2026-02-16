"""
HR Models for SkillsFlow ERP
Manages organizational structure, positions, job descriptions, KPIs, and staff profiles.
"""
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import User, AuditedModel


class Department(AuditedModel):
    """
    Organizational department with unlimited nesting support (tree structure).
    Used for building company HR structure and reporting hierarchy.
    """
    name = models.CharField(
        max_length=200,
        help_text='Department name (e.g., Human Resources, Finance, Operations)'
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text='Unique department code (e.g., HR, FIN, OPS)'
    )
    description = models.TextField(
        blank=True,
        help_text='Description of department function and responsibilities'
    )
    
    # Tree structure - unlimited nesting
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children',
        help_text='Parent department for hierarchical structure'
    )
    
    # Department head (optional - can be set after staff profiles exist)
    head = models.ForeignKey(
        'StaffProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_departments',
        help_text='Staff member who heads this department'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Whether department is currently active'
    )
    
    # Ordering
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text='Display order within parent department'
    )
    
    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_full_path(self):
        """Get full hierarchical path of department"""
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return ' > '.join(path)
    
    def get_ancestors(self):
        """Get all ancestor departments"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors
    
    def get_descendants(self):
        """Get all descendant departments (recursive)"""
        descendants = []
        for child in self.children.filter(is_deleted=False):
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants
    
    def get_all_staff(self):
        """Get all staff in this department and sub-departments"""
        departments = [self] + self.get_descendants()
        return StaffProfile.objects.filter(
            department__in=departments,
            is_deleted=False
        )


class Position(AuditedModel):
    """
    Job position/title with job description document and salary information.
    Positions can exist across multiple departments.
    """
    title = models.CharField(
        max_length=200,
        help_text='Job title (e.g., Senior Software Developer, HR Manager)'
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text='Unique position code (e.g., SSD-001, HRM-001)'
    )
    
    # Job description document
    job_description = models.FileField(
        upload_to='hr/job_descriptions/%Y/%m/',
        null=True,
        blank=True,
        help_text='Job description document (PDF, DOC, DOCX)'
    )
    job_description_text = models.TextField(
        blank=True,
        help_text='Job description text summary or full text'
    )
    
    # Requirements
    minimum_qualifications = models.TextField(
        blank=True,
        help_text='Minimum qualifications required for the position'
    )
    preferred_qualifications = models.TextField(
        blank=True,
        help_text='Preferred/desired qualifications'
    )
    experience_required = models.CharField(
        max_length=100,
        blank=True,
        help_text='Experience requirement (e.g., 3-5 years)'
    )
    
    # Salary information
    SALARY_BAND_CHOICES = [
        ('ENTRY', 'Entry Level'),
        ('JUNIOR', 'Junior'),
        ('MID', 'Mid-Level'),
        ('SENIOR', 'Senior'),
        ('LEAD', 'Lead/Principal'),
        ('MANAGER', 'Manager'),
        ('DIRECTOR', 'Director'),
        ('EXECUTIVE', 'Executive'),
    ]
    salary_band = models.CharField(
        max_length=20,
        choices=SALARY_BAND_CHOICES,
        blank=True,
        help_text='Salary band/grade for this position'
    )
    salary_min = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Minimum salary for this position'
    )
    salary_max = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Maximum salary for this position'
    )
    
    # Department association (position can belong to specific department or be company-wide)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='positions',
        help_text='Department this position belongs to (leave blank for company-wide positions)'
    )
    
    # Reports to position (for org chart)
    reports_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports',
        help_text='Position this role reports to'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Whether position is currently active/open'
    )
    
    class Meta:
        verbose_name = 'Position'
        verbose_name_plural = 'Positions'
        ordering = ['department__name', 'title']
    
    def __str__(self):
        dept = f" ({self.department.code})" if self.department else ""
        return f"{self.title}{dept}"
    
    def get_salary_range_display(self):
        """Get formatted salary range"""
        if self.salary_min and self.salary_max:
            return f"R{self.salary_min:,.2f} - R{self.salary_max:,.2f}"
        elif self.salary_min:
            return f"From R{self.salary_min:,.2f}"
        elif self.salary_max:
            return f"Up to R{self.salary_max:,.2f}"
        return "Not specified"


class PositionTask(AuditedModel):
    """
    Key tasks/responsibilities associated with a position.
    Used to define what is expected from staff in this role.
    """
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name='tasks',
        help_text='Position this task belongs to'
    )
    
    title = models.CharField(
        max_length=200,
        help_text='Task title (e.g., Conduct performance reviews)'
    )
    description = models.TextField(
        blank=True,
        help_text='Detailed task description and expectations'
    )
    
    # Priority and weighting
    PRIORITY_CHOICES = [
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='MEDIUM',
        help_text='Task priority level'
    )
    
    # Weight for performance evaluation (percentage)
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Weight for performance evaluation (percentage, total should be 100%)'
    )
    
    # Frequency
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('ANNUALLY', 'Annually'),
        ('AS_NEEDED', 'As Needed'),
        ('ONGOING', 'Ongoing'),
    ]
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='ONGOING',
        help_text='How often this task should be performed'
    )
    
    # Ordering
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text='Display order within position'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text='Whether task is currently active'
    )
    
    class Meta:
        verbose_name = 'Position Task'
        verbose_name_plural = 'Position Tasks'
        ordering = ['sort_order', '-priority', 'title']
    
    def __str__(self):
        return f"{self.position.title} - {self.title}"


class StaffProfile(AuditedModel):
    """
    Staff profile extending the User model for HR management.
    Links users to positions, departments, and tracks employment details.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='staff_profile',
        help_text='User account for this staff member'
    )
    
    # Employee identification
    employee_number = models.CharField(
        max_length=50,
        unique=True,
        help_text='Unique employee number/ID'
    )
    
    # Position and department
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='staff_members',
        help_text='Current position held by this staff member'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='staff_members',
        help_text='Department this staff member belongs to'
    )
    
    # Reporting structure
    reports_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports',
        help_text='Staff member this person reports to'
    )
    
    # Employment details
    EMPLOYMENT_TYPE_CHOICES = [
        ('FULL_TIME', 'Full Time'),
        ('PART_TIME', 'Part Time'),
        ('CONTRACT', 'Contract'),
        ('INTERN', 'Intern'),
        ('TEMPORARY', 'Temporary'),
    ]
    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPE_CHOICES,
        default='FULL_TIME',
        help_text='Type of employment'
    )
    
    EMPLOYMENT_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ON_LEAVE', 'On Leave'),
        ('SUSPENDED', 'Suspended'),
        ('PROBATION', 'Probation'),
        ('NOTICE', 'Notice Period'),
        ('TERMINATED', 'Terminated'),
        ('RESIGNED', 'Resigned'),
    ]
    employment_status = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_STATUS_CHOICES,
        default='ACTIVE',
        help_text='Current employment status'
    )
    
    # Dates
    date_joined = models.DateField(
        help_text='Date staff member joined the company'
    )
    probation_end_date = models.DateField(
        null=True,
        blank=True,
        help_text='End date of probation period'
    )
    termination_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date of termination (if applicable)'
    )
    
    # Salary (optional - actual salary vs position salary range)
    current_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Current salary (confidential)'
    )
    
    # Additional info
    notes = models.TextField(
        blank=True,
        help_text='Additional notes about this staff member'
    )
    
    # Work Location / Campus assignments
    work_locations = models.ManyToManyField(
        'tenants.Campus',
        blank=True,
        related_name='assigned_staff',
        help_text='Campuses/locations where this staff member works'
    )
    primary_work_location = models.ForeignKey(
        'tenants.Campus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_staff',
        help_text='Primary work location/campus for this staff member'
    )
    
    class Meta:
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'
        ordering = ['user__last_name', 'user__first_name']
    
    def __str__(self):
        return f"{self.employee_number} - {self.user.get_full_name()}"
    
    def get_position_history(self):
        """Get position history for this staff member"""
        return self.position_history.filter(is_deleted=False).order_by('-start_date')
    
    def get_direct_reports(self):
        """Get all staff who report directly to this person"""
        return StaffProfile.objects.filter(
            reports_to=self,
            is_deleted=False,
            employment_status__in=['ACTIVE', 'ON_LEAVE', 'PROBATION']
        )
    
    def get_all_subordinates(self):
        """Get all subordinates recursively"""
        subordinates = []
        for report in self.get_direct_reports():
            subordinates.append(report)
            subordinates.extend(report.get_all_subordinates())
        return subordinates
    
    def get_management_chain(self):
        """Get chain of management above this staff member"""
        chain = []
        current = self.reports_to
        while current:
            chain.append(current)
            current = current.reports_to
        return chain


class StaffPositionHistory(AuditedModel):
    """
    Tracks position changes for staff members over time.
    Used for career progression tracking and historical records.
    """
    staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.CASCADE,
        related_name='position_history',
        help_text='Staff member this history belongs to'
    )
    
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name='position_history',
        help_text='Position held'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='position_history',
        help_text='Department at the time'
    )
    
    # Date range
    start_date = models.DateField(
        help_text='Start date in this position'
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text='End date in this position (null if current)'
    )
    
    # Change details
    CHANGE_REASON_CHOICES = [
        ('HIRE', 'New Hire'),
        ('PROMOTION', 'Promotion'),
        ('TRANSFER', 'Transfer'),
        ('DEMOTION', 'Demotion'),
        ('RESTRUCTURE', 'Restructure'),
        ('LATERAL', 'Lateral Move'),
        ('ACTING', 'Acting Position'),
        ('RETURN', 'Return from Leave'),
    ]
    change_reason = models.CharField(
        max_length=20,
        choices=CHANGE_REASON_CHOICES,
        default='HIRE',
        help_text='Reason for position change'
    )
    
    # Salary at the time
    salary_at_time = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Salary at the time of this position'
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text='Notes about this position change'
    )
    
    class Meta:
        verbose_name = 'Staff Position History'
        verbose_name_plural = 'Staff Position Histories'
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.position.title} ({self.start_date})"
    
    @property
    def is_current(self):
        """Check if this is the current position"""
        return self.end_date is None
    
    @property
    def duration_days(self):
        """Get duration in days"""
        end = self.end_date or timezone.now().date()
        return (end - self.start_date).days


class StaffTaskAssignment(AuditedModel):
    """
    Tracks individual task assignments and completion for staff members.
    Used for performance tracking and task management.
    """
    staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.CASCADE,
        related_name='task_assignments',
        help_text='Staff member assigned to this task'
    )
    task = models.ForeignKey(
        PositionTask,
        on_delete=models.CASCADE,
        related_name='assignments',
        help_text='Task being tracked'
    )
    
    # Period being tracked
    period_start = models.DateField(
        help_text='Start of tracking period'
    )
    period_end = models.DateField(
        help_text='End of tracking period'
    )
    
    # Completion tracking
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('DEFERRED', 'Deferred'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NOT_STARTED',
        help_text='Current status of task'
    )
    
    completion_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date task was completed'
    )
    
    # Self-assessment
    self_rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Self-assessment rating (1-5)'
    )
    self_comments = models.TextField(
        blank=True,
        help_text='Self-assessment comments'
    )
    
    # Manager assessment
    manager_rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Manager assessment rating (1-5)'
    )
    manager_comments = models.TextField(
        blank=True,
        help_text='Manager assessment comments'
    )
    assessed_by = models.ForeignKey(
        StaffProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assessments_given',
        help_text='Manager who assessed this task'
    )
    assessed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When assessment was completed'
    )
    
    class Meta:
        verbose_name = 'Staff Task Assignment'
        verbose_name_plural = 'Staff Task Assignments'
        ordering = ['-period_start', 'task__sort_order']
        unique_together = ['staff', 'task', 'period_start', 'period_end']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.task.title} ({self.period_start})"


class PerformanceReview(AuditedModel):
    """
    Performance review records for staff members.
    Consolidates task assessments into overall review.
    """
    staff = models.ForeignKey(
        StaffProfile,
        on_delete=models.CASCADE,
        related_name='performance_reviews',
        help_text='Staff member being reviewed'
    )
    
    # Review period
    review_period_start = models.DateField(
        help_text='Start of review period'
    )
    review_period_end = models.DateField(
        help_text='End of review period'
    )
    
    # Review details
    REVIEW_TYPE_CHOICES = [
        ('PROBATION', 'Probation Review'),
        ('QUARTERLY', 'Quarterly Review'),
        ('ANNUAL', 'Annual Review'),
        ('ADHOC', 'Ad-hoc Review'),
    ]
    review_type = models.CharField(
        max_length=20,
        choices=REVIEW_TYPE_CHOICES,
        default='ANNUAL',
        help_text='Type of review'
    )
    
    # Scores
    overall_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Overall performance rating (1-5)'
    )
    
    # Comments
    achievements = models.TextField(
        blank=True,
        help_text='Key achievements during review period'
    )
    areas_for_improvement = models.TextField(
        blank=True,
        help_text='Areas identified for improvement'
    )
    goals_next_period = models.TextField(
        blank=True,
        help_text='Goals set for next review period'
    )
    manager_comments = models.TextField(
        blank=True,
        help_text='Overall manager comments'
    )
    employee_comments = models.TextField(
        blank=True,
        help_text='Employee self-assessment comments'
    )
    
    # Workflow
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SELF_REVIEW', 'Self Review'),
        ('MANAGER_REVIEW', 'Manager Review'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('COMPLETED', 'Completed'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        help_text='Review status'
    )
    
    reviewed_by = models.ForeignKey(
        StaffProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews_conducted',
        help_text='Manager who conducted the review'
    )
    review_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date review was conducted'
    )
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When employee acknowledged the review'
    )
    
    class Meta:
        verbose_name = 'Performance Review'
        verbose_name_plural = 'Performance Reviews'
        ordering = ['-review_period_end']
    
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.review_type} ({self.review_period_end})"


class LeaveRequest(AuditedModel):
    """
    Staff leave requests with approval workflow.
    Tracks annual, sick, family responsibility, study, and unpaid leave.
    """
    staff_profile = models.ForeignKey(
        StaffProfile,
        on_delete=models.CASCADE,
        related_name='leave_requests',
        help_text='Staff member requesting leave'
    )
    
    LEAVE_TYPE_CHOICES = [
        ('ANNUAL', 'Annual Leave'),
        ('SICK', 'Sick Leave'),
        ('FAMILY', 'Family Responsibility Leave'),
        ('STUDY', 'Study Leave'),
        ('UNPAID', 'Unpaid Leave'),
    ]
    leave_type = models.CharField(
        max_length=20,
        choices=LEAVE_TYPE_CHOICES,
        help_text='Type of leave being requested'
    )
    
    # Date range
    start_date = models.DateField(
        help_text='First day of leave'
    )
    end_date = models.DateField(
        help_text='Last day of leave'
    )
    days_requested = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        help_text='Number of working days requested (supports half-days)'
    )
    
    # Details
    reason = models.TextField(
        blank=True,
        help_text='Reason for leave request'
    )
    
    # Approval workflow
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text='Current status of the leave request'
    )
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leave_approvals',
        help_text='Manager who approved or rejected the request'
    )
    approved_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date and time the request was approved or rejected'
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text='Reason for rejection (if applicable)'
    )
    
    class Meta:
        verbose_name = 'Leave Request'
        verbose_name_plural = 'Leave Requests'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['staff_profile', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return (
            f"{self.staff_profile.user.get_full_name()} - "
            f"{self.get_leave_type_display()} "
            f"({self.start_date} to {self.end_date})"
        )
    
    @property
    def is_pending(self):
        return self.status == 'PENDING'
    
    @property
    def duration_display(self):
        """Human-readable duration"""
        if self.days_requested == 1:
            return '1 day'
        return f'{self.days_requested} days'


class StaffDocument(AuditedModel):
    """
    Documents associated with a staff member's employment record.
    Tracks contracts, ID copies, qualifications, certificates, and other files
    with optional expiry date monitoring.
    """
    staff_profile = models.ForeignKey(
        StaffProfile,
        on_delete=models.CASCADE,
        related_name='documents',
        help_text='Staff member this document belongs to'
    )
    
    title = models.CharField(
        max_length=255,
        help_text='Document title (e.g., Employment Contract 2024)'
    )
    
    DOCUMENT_TYPE_CHOICES = [
        ('CONTRACT', 'Employment Contract'),
        ('ID', 'ID Document'),
        ('QUALIFICATION', 'Qualification'),
        ('CERTIFICATE', 'Certificate'),
        ('OTHER', 'Other'),
    ]
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
        help_text='Category of document'
    )
    
    file = models.FileField(
        upload_to='hr/staff_documents/%Y/%m/',
        help_text='Uploaded document file'
    )
    
    expiry_date = models.DateField(
        null=True,
        blank=True,
        help_text='Document expiry date (leave blank if not applicable)'
    )
    
    notes = models.TextField(
        blank=True,
        help_text='Additional notes about this document'
    )
    
    class Meta:
        verbose_name = 'Staff Document'
        verbose_name_plural = 'Staff Documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['staff_profile', 'document_type']),
            models.Index(fields=['expiry_date']),
        ]
    
    def __str__(self):
        return (
            f"{self.staff_profile.user.get_full_name()} - "
            f"{self.get_document_type_display()}: {self.title}"
        )
    
    @property
    def is_expired(self):
        """Check if document has passed its expiry date"""
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False
    
    @property
    def expires_soon(self):
        """Check if document expires within 30 days"""
        if self.expiry_date:
            from datetime import timedelta
            return (
                not self.is_expired
                and (self.expiry_date - timezone.now().date()) <= timedelta(days=30)
            )
        return False