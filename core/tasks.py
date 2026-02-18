"""
Task Management System

Central task hub for all users to see and manage their work.
Tasks are automatically generated from business events or can be manually created.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta


class TaskAuditModel(models.Model):
    """
    Custom audit model for tasks to avoid conflicts with workflows.Task
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='%(app_label)s_%(class)s_created',
        null=True, blank=True
    )
    
    class Meta:
        abstract = True


class TaskCategory(models.TextChoices):
    """Categories of tasks in the system"""
    # Document & Verification
    DOCUMENT_VERIFICATION = 'doc_verify', 'Document Verification'
    DOCUMENT_UPLOAD = 'doc_upload', 'Document Upload Required'
    
    # Academic
    ASSESSMENT_MARK = 'assess_mark', 'Assessment to Mark'
    ASSESSMENT_MODERATE = 'assess_mod', 'Assessment to Moderate'
    ASSESSMENT_DUE = 'assess_due', 'Assessment Due'
    POE_REVIEW = 'poe_review', 'PoE to Review'
    
    # Enrollment & Registration
    ENROLLMENT_PROCESS = 'enroll_proc', 'Enrollment Processing'
    REGISTRATION_SETA = 'reg_seta', 'SETA Registration'
    
    # Finance
    INVOICE_CREATE = 'inv_create', 'Invoice to Create'
    PAYMENT_FOLLOW_UP = 'pay_follow', 'Payment Follow-up'
    PAYMENT_OVERDUE = 'pay_overdue', 'Overdue Payment'
    
    # Attendance & Logistics
    ATTENDANCE_CAPTURE = 'attend_cap', 'Attendance to Capture'
    LOGBOOK_UPDATE = 'log_update', 'Logbook to Update'
    
    # Learner Support
    LEARNER_AT_RISK = 'learn_risk', 'At-Risk Learner Intervention'
    LEARNER_SUPPORT = 'learn_support', 'Learner Support Required'
    
    # Reporting
    REPORT_DUE = 'report_due', 'Report Due'
    TRANCHE_CLAIM = 'tranche', 'Tranche Claim Due'
    
    # Communication
    FOLLOW_UP = 'follow_up', 'Follow-up Required'
    CALLBACK = 'callback', 'Callback Required'
    
    # General
    APPROVAL = 'approval', 'Approval Required'
    REVIEW = 'review', 'Review Required'
    ACTION = 'action', 'Action Required'
    REMINDER = 'reminder', 'Reminder'


class TaskPriority(models.TextChoices):
    """Task priority levels"""
    URGENT = 'urgent', 'Urgent'
    HIGH = 'high', 'High'
    MEDIUM = 'medium', 'Medium'
    LOW = 'low', 'Low'


class TaskStatus(models.TextChoices):
    """Task status"""
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    WAITING = 'waiting', 'Waiting on Others'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'
    DEFERRED = 'deferred', 'Deferred'


class Task(TaskAuditModel):
    """
    Central task model for all user tasks.
    Can be linked to any entity via GenericForeignKey.
    """
    # Task identification
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, 
        choices=TaskCategory.choices,
        default=TaskCategory.ACTION
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='core_assigned_tasks'
    )
    assigned_role = models.CharField(max_length=50, blank=True, default='')  # If task is for any user with role
    assigned_campus = models.ForeignKey(
        'tenants.Campus',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='campus_tasks'
    )
    
    # Status & Priority
    status = models.CharField(
        max_length=20, 
        choices=TaskStatus.choices, 
        default=TaskStatus.PENDING
    )
    priority = models.CharField(
        max_length=20, 
        choices=TaskPriority.choices, 
        default=TaskPriority.MEDIUM
    )
    
    # Timing
    due_date = models.DateField(null=True, blank=True)
    due_time = models.TimeField(null=True, blank=True)
    reminder_date = models.DateField(null=True, blank=True)
    
    # Completion
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='core_completed_tasks'
    )
    
    # Generic relation to any model
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Quick action URL
    action_url = models.CharField(max_length=255, blank=True)
    action_label = models.CharField(max_length=50, default='View')
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Auto-generated flag
    is_auto_generated = models.BooleanField(default=False)
    source_event = models.CharField(max_length=100, blank=True)  # e.g., "document_uploaded"
    
    class Meta:
        ordering = ['-priority', 'due_date', '-created_at']
        indexes = [
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return self.title
    
    def mark_complete(self, user=None):
        """Mark task as complete"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save()
    
    def mark_in_progress(self):
        """Mark task as in progress"""
        self.status = TaskStatus.IN_PROGRESS
        self.save()
    
    @property
    def is_overdue(self):
        """Check if task is overdue"""
        if self.due_date and self.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            return self.due_date < timezone.now().date()
        return False
    
    @property
    def days_until_due(self):
        """Days until due (negative if overdue)"""
        if self.due_date:
            return (self.due_date - timezone.now().date()).days
        return None
    
    @classmethod
    def create_task(cls, title, category, assigned_to=None, assigned_role=None,
                    due_date=None, priority=TaskPriority.MEDIUM, related_object=None,
                    action_url='', description='', is_auto=False, source_event=''):
        """Factory method to create tasks consistently"""
        task = cls(
            title=title,
            description=description,
            category=category,
            assigned_to=assigned_to,
            assigned_role=assigned_role or '',
            priority=priority,
            due_date=due_date,
            action_url=action_url,
            is_auto_generated=is_auto,
            source_event=source_event,
        )
        
        if related_object:
            task.content_type = ContentType.objects.get_for_model(related_object)
            task.object_id = related_object.pk
        
        task.save()
        return task


class TaskComment(models.Model):
    """Comments/updates on tasks"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.task.title} - {self.user.email}"


class TaskTemplate(models.Model):
    """
    Templates for auto-generating tasks from events.
    E.g., when document uploaded, create verification task.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Trigger event
    trigger_event = models.CharField(max_length=100, unique=True)  # e.g., "document_uploaded"
    trigger_model = models.CharField(max_length=100, blank=True)  # e.g., "learners.LearnerDocument"
    
    # Task details
    task_title_template = models.CharField(max_length=200)  # Can use {field} placeholders
    task_description_template = models.TextField(blank=True)
    task_category = models.CharField(max_length=20, choices=TaskCategory.choices)
    task_priority = models.CharField(max_length=20, choices=TaskPriority.choices, default=TaskPriority.MEDIUM)
    
    # Assignment
    assign_to_role = models.CharField(max_length=50, blank=True)
    assign_to_field = models.CharField(max_length=100, blank=True)  # e.g., "enrollment.campus.registrar"
    
    # Due date calculation
    due_days = models.PositiveIntegerField(default=3)  # Days from creation
    
    # Action URL template
    action_url_template = models.CharField(max_length=255, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['trigger_event']
        verbose_name = 'Task Template'
        verbose_name_plural = 'Task Templates'
    
    def __str__(self):
        return f"{self.name} ({self.trigger_event})"


# =====================================================
# STIPEND MANAGEMENT
# =====================================================

class StipendType(models.Model):
    """Types of stipends/allowances"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_frequency = models.CharField(max_length=20, choices=[
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('ONCE_OFF', 'Once-off'),
    ], default='MONTHLY')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class StipendAllocation(TaskAuditModel):
    """
    Stipend allocation to a learner enrollment
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    enrollment = models.ForeignKey(
        'academics.Enrollment',
        on_delete=models.CASCADE,
        related_name='stipend_allocations'
    )
    stipend_type = models.ForeignKey(
        StipendType,
        on_delete=models.PROTECT,
        related_name='allocations'
    )
    
    # Grant project (if funded by grant)
    grant_project = models.ForeignKey(
        'corporate.GrantProject',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='stipend_allocations'
    )
    
    # Amount
    amount_per_period = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Period
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Bank details
    bank_name = models.CharField(max_length=100, blank=True)
    account_holder = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    branch_code = models.CharField(max_length=20, blank=True)
    account_type = models.CharField(max_length=20, choices=[
        ('SAVINGS', 'Savings'),
        ('CURRENT', 'Current/Cheque'),
        ('TRANSMISSION', 'Transmission'),
    ], blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Stipend Allocation'
        verbose_name_plural = 'Stipend Allocations'
    
    def __str__(self):
        return f"{self.enrollment} - {self.stipend_type.name}"


class StipendPayment(TaskAuditModel):
    """
    Individual stipend payment record
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('PROCESSING', 'Processing'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    allocation = models.ForeignKey(
        StipendAllocation,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    
    # Payment period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Amount
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Attendance-based calculation
    days_attended = models.PositiveIntegerField(null=True, blank=True)
    days_expected = models.PositiveIntegerField(null=True, blank=True)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Approval
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_stipends'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Payment details
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=20, choices=[
        ('EFT', 'EFT/Bank Transfer'),
        ('CASH', 'Cash'),
        ('CHEQUE', 'Cheque'),
    ], default='EFT')
    
    notes = models.TextField(blank=True)
    deduction_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-period_start']
        verbose_name = 'Stipend Payment'
        verbose_name_plural = 'Stipend Payments'
    
    def __str__(self):
        return f"{self.allocation.enrollment} - {self.period_start} to {self.period_end}"
    
    def calculate_net_amount(self):
        """Calculate net amount based on attendance if applicable"""
        if self.days_attended is not None and self.days_expected:
            self.attendance_rate = (self.days_attended / self.days_expected) * 100
            # Pro-rata based on attendance
            self.net_amount = (self.base_amount * self.days_attended / self.days_expected) - self.deductions
        else:
            self.net_amount = self.base_amount - self.deductions
        return self.net_amount


# =====================================================
# LEARNING PLAN
# =====================================================

class LearningPlan(TaskAuditModel):
    """
    Individual learning plan for a learner's enrollment
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('UNDER_REVIEW', 'Under Review'),
        ('COMPLETED', 'Completed'),
        ('ARCHIVED', 'Archived'),
    ]
    
    enrollment = models.OneToOneField(
        'academics.Enrollment',
        on_delete=models.CASCADE,
        related_name='learning_plan'
    )
    
    # Plan overview
    title = models.CharField(max_length=200, blank=True)
    objectives = models.TextField(blank=True)
    learning_style = models.CharField(max_length=50, blank=True)
    special_requirements = models.TextField(blank=True)
    
    # Dates
    start_date = models.DateField()
    target_completion = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Review
    last_reviewed = models.DateField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_learning_plans'
    )
    next_review_date = models.DateField(null=True, blank=True)
    
    # Sign-off
    learner_signed = models.BooleanField(default=False)
    learner_signed_date = models.DateField(null=True, blank=True)
    facilitator_signed = models.BooleanField(default=False)
    facilitator_signed_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Learning Plan'
        verbose_name_plural = 'Learning Plans'
    
    def __str__(self):
        return f"Learning Plan - {self.enrollment}"


class LearningPlanModule(models.Model):
    """
    Module schedule within a learning plan
    """
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('DEFERRED', 'Deferred'),
    ]
    
    learning_plan = models.ForeignKey(
        LearningPlan,
        on_delete=models.CASCADE,
        related_name='modules'
    )
    module = models.ForeignKey(
        'academics.Module',
        on_delete=models.CASCADE,
        related_name='learning_plan_entries'
    )
    
    # Schedule
    sequence = models.PositiveIntegerField(default=1)
    planned_start = models.DateField()
    planned_end = models.DateField()
    
    # Actuals
    actual_start = models.DateField(null=True, blank=True)
    actual_end = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOT_STARTED')
    
    # Resources
    facilitator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_learning_modules'
    )
    venue = models.ForeignKey(
        'logistics.Venue',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    delivery_mode = models.CharField(max_length=20, choices=[
        ('CONTACT', 'Contact/Face-to-face'),
        ('DISTANCE', 'Distance Learning'),
        ('BLENDED', 'Blended'),
        ('WORKPLACE', 'Workplace'),
        ('ONLINE', 'Online'),
    ], default='CONTACT')
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['learning_plan', 'sequence']
        verbose_name = 'Learning Plan Module'
        verbose_name_plural = 'Learning Plan Modules'
    
    def __str__(self):
        return f"{self.learning_plan.enrollment} - {self.module.code}"


class LearningPlanMilestone(models.Model):
    """
    Key milestones in a learning plan
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACHIEVED', 'Achieved'),
        ('MISSED', 'Missed'),
        ('RESCHEDULED', 'Rescheduled'),
    ]
    
    learning_plan = models.ForeignKey(
        LearningPlan,
        on_delete=models.CASCADE,
        related_name='milestones'
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    target_date = models.DateField()
    achieved_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Linked assessment
    assessment = models.ForeignKey(
        'assessments.AssessmentActivity',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['learning_plan', 'target_date']
        verbose_name = 'Learning Plan Milestone'
        verbose_name_plural = 'Learning Plan Milestones'
    
    def __str__(self):
        return f"{self.learning_plan.enrollment} - {self.title}"
