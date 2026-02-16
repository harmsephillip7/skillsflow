"""
Project Template System for NOT (Notification of Training) Automation

This module provides:
1. ProjectTemplateSet - Groupings of task templates with inheritance support
2. ProjectTaskTemplate - Unified task templates supporting status-based, date-relative, and recurring triggers
3. NOTScheduledTask - Tracks generated tasks for recalculation when dates change
4. NOTTemplateSetApplication - Tracks which template sets have been applied to a NOT

The system allows proactive scheduling of operational tasks (admin, marketing, recruitment, etc.)
based on qualification type, contract duration, project type, and funder type.
"""
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta, date
from decimal import Decimal
import logging

from .tasks import Task, TaskCategory, TaskPriority

logger = logging.getLogger(__name__)


# =====================================================
# ENUMS AND CHOICES
# =====================================================

class TriggerType(models.TextChoices):
    """Types of triggers for task creation"""
    STATUS_CHANGE = 'status', 'Status Change'
    DATE_RELATIVE = 'date', 'Date Relative'
    RECURRING = 'recurring', 'Recurring'


class DateReferencePoint(models.TextChoices):
    """Reference points for date-relative task scheduling"""
    PLANNED_START = 'planned_start', 'Planned Start Date'
    PLANNED_END = 'planned_end', 'Planned End Date'
    ACTUAL_START = 'actual_start', 'Actual Start Date'
    ACTUAL_END = 'actual_end', 'Actual End Date'
    APPROVAL_DATE = 'approval', 'Approval Date'


class RecurringInterval(models.TextChoices):
    """Intervals for recurring tasks"""
    DAILY = 'daily', 'Daily'
    WEEKLY = 'weekly', 'Weekly'
    BIWEEKLY = 'biweekly', 'Bi-Weekly'
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'


class OperationalCategory(models.TextChoices):
    """Categories for operational (non-academic) tasks"""
    ADMIN = 'admin', 'Administrative'
    FINANCE = 'finance', 'Finance'
    MARKETING = 'marketing', 'Marketing'
    RECRUITMENT = 'recruitment', 'Recruitment'
    COMPLIANCE = 'compliance', 'Compliance/Regulatory'
    LOGISTICS = 'logistics', 'Logistics'
    QUALITY = 'quality', 'Quality Assurance'
    CLIENT = 'client', 'Client Relations'
    HR = 'hr', 'Human Resources'
    REPORTING = 'reporting', 'Reporting'


# =====================================================
# MODELS
# =====================================================

class ProjectTemplateSet(models.Model):
    """
    A group of project task templates that can be applied together.
    Supports inheritance through parent_set for reusable base configurations.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Inheritance support
    parent_set = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='child_sets',
        help_text="Inherit templates from a parent set"
    )
    
    # Applicability filters (JSON arrays for flexibility)
    # Empty array means "applies to all"
    project_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Project types this set applies to (empty = all). Use NOT PROJECT_TYPE_CHOICES values."
    )
    funder_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Funder types this set applies to (empty = all). Use NOT FUNDER_CHOICES values."
    )
    qualification_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Qualification types (OC, NC, ND, PQ, SP, LP) this set applies to (empty = all)."
    )
    
    # Duration filtering (in months)
    min_duration_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Minimum contract duration (months) for this set to apply"
    )
    max_duration_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum contract duration (months) for this set to apply"
    )
    
    # Auto-apply
    auto_apply = models.BooleanField(
        default=True,
        help_text="Automatically apply this set when NOT matches criteria"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'core.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_template_sets'
    )
    
    # Track version for notification on updates
    version = models.PositiveIntegerField(default=1)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Project Template Set'
        verbose_name_plural = 'Project Template Sets'
    
    def __str__(self):
        if self.parent_set:
            return f"{self.name} (extends {self.parent_set.name})"
        return self.name
    
    def save(self, *args, **kwargs):
        # Increment version on update for notifications
        if self.pk:
            self.version += 1
        super().save(*args, **kwargs)
    
    def get_all_templates(self):
        """
        Get all templates including inherited ones from parent sets.
        Child templates override parent templates with the same name.
        """
        templates = {}
        
        # First, collect parent templates
        if self.parent_set:
            parent_templates = self.parent_set.get_all_templates()
            for name, template in parent_templates.items():
                templates[name] = template
        
        # Then, add/override with own templates
        for template in self.templates.filter(is_active=True):
            templates[template.name] = template
        
        return templates
    
    def matches_not(self, training_notification):
        """
        Check if this template set should apply to a given TrainingNotification.
        """
        # Check project type
        if self.project_types and training_notification.project_type not in self.project_types:
            return False
        
        # Check funder type
        if self.funder_types and training_notification.funder not in self.funder_types:
            return False
        
        # Check qualification type
        if self.qualification_types and training_notification.qualification:
            if training_notification.qualification.qualification_type not in self.qualification_types:
                return False
        
        # Check duration
        duration = training_notification.duration_months
        if duration:
            if self.min_duration_months and duration < self.min_duration_months:
                return False
            if self.max_duration_months and duration > self.max_duration_months:
                return False
        
        return True


class ProjectTaskTemplate(models.Model):
    """
    Unified task template supporting status-based, date-relative, and recurring triggers.
    Replaces the simpler NOTTaskTemplate with enhanced scheduling capabilities.
    """
    
    TRIGGER_STATUS_CHOICES = [
        ('DRAFT', 'Draft Created'),
        ('PLANNING', 'Planning Started'),
        ('IN_MEETING', 'In Planning Meeting'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('NOTIFICATIONS_SENT', 'Notifications Sent'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('ON_HOLD', 'On Hold'),
    ]
    
    ROLE_CHOICES = [
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
    
    # Relationship to template set
    template_set = models.ForeignKey(
        ProjectTemplateSet,
        on_delete=models.CASCADE,
        related_name='templates'
    )
    
    # Template identification
    name = models.CharField(max_length=100, help_text="Internal name for the template")
    
    # Trigger configuration
    trigger_type = models.CharField(
        max_length=20,
        choices=TriggerType.choices,
        default=TriggerType.STATUS_CHANGE
    )
    
    # For STATUS_CHANGE triggers
    trigger_status = models.CharField(
        max_length=30,
        choices=TRIGGER_STATUS_CHOICES,
        blank=True,
        help_text="NOT status that triggers this task (for status-based triggers)"
    )
    
    # For DATE_RELATIVE triggers
    date_reference = models.CharField(
        max_length=20,
        choices=DateReferencePoint.choices,
        blank=True,
        help_text="Reference date to calculate from (for date-relative triggers)"
    )
    offset_days = models.IntegerField(
        default=0,
        help_text="Days from reference date (negative = before, positive = after)"
    )
    
    # For RECURRING triggers
    recurring_interval = models.CharField(
        max_length=20,
        choices=RecurringInterval.choices,
        blank=True,
        help_text="How often the task recurs"
    )
    recurring_start_status = models.CharField(
        max_length=30,
        choices=TRIGGER_STATUS_CHOICES,
        blank=True,
        help_text="Start recurring when NOT reaches this status"
    )
    recurring_end_status = models.CharField(
        max_length=30,
        choices=TRIGGER_STATUS_CHOICES,
        blank=True,
        help_text="Stop recurring when NOT reaches this status"
    )
    
    # Task details
    task_title_template = models.CharField(
        max_length=200,
        help_text="Use {reference_number}, {title}, {qualification}, {learner_count}, {client_name}, {due_date}"
    )
    task_description_template = models.TextField(
        blank=True,
        help_text="Use same placeholders as title"
    )
    
    task_category = models.CharField(
        max_length=20,
        choices=TaskCategory.choices,
        default=TaskCategory.ACTION
    )
    task_priority = models.CharField(
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.MEDIUM
    )
    
    # Operational category for non-academic tasks
    operational_category = models.CharField(
        max_length=20,
        choices=OperationalCategory.choices,
        blank=True,
        help_text="Category for operational (non-academic) tasks"
    )
    
    # Assignment - by role in NOTStakeholder
    assigned_role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        help_text="Role from NOTStakeholder to assign task to"
    )
    
    # Fallback assignment if no stakeholder with role
    fallback_campus_role = models.CharField(
        max_length=50,
        blank=True,
        help_text="Fallback role from campus staff (e.g., 'REGISTRAR', 'ACADEMIC_COORDINATOR')"
    )
    
    # Due date calculation (for status-based triggers)
    due_days_offset = models.PositiveIntegerField(
        default=7,
        help_text="Days from trigger when task is due (for status-based triggers)"
    )
    
    # Recalculation support
    recalculate_on_date_change = models.BooleanField(
        default=True,
        help_text="Recalculate task due dates when NOT dates change"
    )
    
    # Ordering
    sequence = models.PositiveIntegerField(
        default=1,
        help_text="Order of task creation for same trigger"
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['template_set', 'trigger_type', 'sequence']
        verbose_name = 'Project Task Template'
        verbose_name_plural = 'Project Task Templates'
        unique_together = ['template_set', 'name']
    
    def __str__(self):
        return f"{self.template_set.name} - {self.name}"
    
    def format_title(self, training_notification, due_date=None):
        """Format task title with NOT data"""
        context = self._get_format_context(training_notification, due_date)
        return self.task_title_template.format(**context)
    
    def format_description(self, training_notification, due_date=None):
        """Format task description with NOT data"""
        if not self.task_description_template:
            return ""
        context = self._get_format_context(training_notification, due_date)
        return self.task_description_template.format(**context)
    
    def _get_format_context(self, training_notification, due_date=None):
        """Get formatting context dict for templates"""
        return {
            'reference_number': training_notification.reference_number,
            'title': training_notification.title,
            'qualification': training_notification.qualification.short_title if training_notification.qualification else 'N/A',
            'learner_count': training_notification.expected_learner_count,
            'client_name': training_notification.client_name or training_notification.corporate_client.name if training_notification.corporate_client else 'N/A',
            'due_date': due_date.strftime('%Y-%m-%d') if due_date else 'TBD',
        }
    
    def calculate_due_date(self, training_notification, trigger_date=None):
        """
        Calculate the due date for a task based on trigger type.
        
        Args:
            training_notification: The NOT this task is for
            trigger_date: Optional override for the trigger date (for status triggers)
        
        Returns:
            date or None if cannot calculate
        """
        if self.trigger_type == TriggerType.STATUS_CHANGE:
            base_date = trigger_date or timezone.now().date()
            return base_date + timedelta(days=self.due_days_offset)
        
        elif self.trigger_type == TriggerType.DATE_RELATIVE:
            ref_date = self._get_reference_date(training_notification)
            if ref_date:
                return ref_date + timedelta(days=self.offset_days)
            return None
        
        elif self.trigger_type == TriggerType.RECURRING:
            # For recurring, first occurrence is on interval from start
            return timezone.now().date() + timedelta(days=self._interval_to_days())
        
        return None
    
    def _get_reference_date(self, training_notification):
        """Get the reference date based on date_reference field"""
        mapping = {
            DateReferencePoint.PLANNED_START: training_notification.planned_start_date,
            DateReferencePoint.PLANNED_END: training_notification.planned_end_date,
            DateReferencePoint.ACTUAL_START: training_notification.actual_start_date,
            DateReferencePoint.ACTUAL_END: training_notification.actual_end_date,
            DateReferencePoint.APPROVAL_DATE: training_notification.approved_date.date() if training_notification.approved_date else None,
        }
        return mapping.get(self.date_reference)
    
    def _interval_to_days(self):
        """Convert recurring interval to days"""
        intervals = {
            RecurringInterval.DAILY: 1,
            RecurringInterval.WEEKLY: 7,
            RecurringInterval.BIWEEKLY: 14,
            RecurringInterval.MONTHLY: 30,
            RecurringInterval.QUARTERLY: 90,
        }
        return intervals.get(self.recurring_interval, 7)


class NOTScheduledTask(models.Model):
    """
    Tracks tasks that have been generated from templates for a specific NOT.
    Enables recalculation of due dates when NOT dates change.
    """
    training_notification = models.ForeignKey(
        'core.TrainingNotification',
        on_delete=models.CASCADE,
        related_name='scheduled_tasks'
    )
    
    template = models.ForeignKey(
        ProjectTaskTemplate,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_tasks'
    )
    
    task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
        related_name='scheduled_task_record'
    )
    
    # Track the original calculation basis
    original_due_date = models.DateField(null=True, blank=True)
    trigger_date = models.DateField(
        null=True,
        blank=True,
        help_text="The date that triggered this task creation"
    )
    
    # For recurring tasks
    recurrence_number = models.PositiveIntegerField(
        default=1,
        help_text="Which occurrence this is (for recurring tasks)"
    )
    
    # Status
    auto_generated = models.BooleanField(default=True)
    recalculated_count = models.PositiveIntegerField(default=0)
    last_recalculated = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'NOT Scheduled Task'
        verbose_name_plural = 'NOT Scheduled Tasks'
    
    def __str__(self):
        return f"{self.training_notification.reference_number} - {self.task.title}"
    
    def recalculate_due_date(self):
        """
        Recalculate the task due date based on current NOT dates.
        Only applies if template has recalculate_on_date_change=True.
        """
        if not self.template or not self.template.recalculate_on_date_change:
            return False
        
        # Only recalculate date-relative tasks
        if self.template.trigger_type != TriggerType.DATE_RELATIVE:
            return False
        
        # Calculate new due date
        new_due_date = self.template.calculate_due_date(self.training_notification)
        
        if new_due_date and new_due_date != self.task.due_date:
            old_due_date = self.task.due_date
            self.task.due_date = new_due_date
            self.task.save(update_fields=['due_date', 'updated_at'])
            
            self.recalculated_count += 1
            self.last_recalculated = timezone.now()
            self.save(update_fields=['recalculated_count', 'last_recalculated'])
            
            logger.info(
                f"Recalculated task due date for {self.task.title}: "
                f"{old_due_date} -> {new_due_date}"
            )
            return True
        
        return False


class NOTTemplateSetApplication(models.Model):
    """
    Tracks which template sets have been applied to a specific NOT.
    Used for notifications when template sets are updated.
    """
    training_notification = models.ForeignKey(
        'core.TrainingNotification',
        on_delete=models.CASCADE,
        related_name='applied_template_sets'
    )
    
    template_set = models.ForeignKey(
        ProjectTemplateSet,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    
    # Version tracking for update notifications
    applied_version = models.PositiveIntegerField(
        help_text="Version of template set when applied"
    )
    
    applied_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.ForeignKey(
        'core.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='template_set_applications'
    )
    
    # Notification tracking
    update_notification_sent = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['training_notification', 'template_set']
        verbose_name = 'NOT Template Set Application'
        verbose_name_plural = 'NOT Template Set Applications'
    
    def __str__(self):
        return f"{self.training_notification.reference_number} <- {self.template_set.name}"
    
    def needs_update_notification(self):
        """Check if this application needs notification about template set updates"""
        return self.applied_version < self.template_set.version


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def get_matching_template_sets(training_notification):
    """
    Find all active template sets that match a given TrainingNotification.
    
    Args:
        training_notification: TrainingNotification instance
    
    Returns:
        QuerySet of matching ProjectTemplateSet instances
    """
    matching = []
    
    for template_set in ProjectTemplateSet.objects.filter(is_active=True, auto_apply=True):
        if template_set.matches_not(training_notification):
            matching.append(template_set.pk)
    
    return ProjectTemplateSet.objects.filter(pk__in=matching)


def apply_template_set(template_set, training_notification, user=None, trigger_status=None):
    """
    Apply a template set to a TrainingNotification, creating scheduled tasks.
    
    Args:
        template_set: ProjectTemplateSet to apply
        training_notification: TrainingNotification to apply to
        user: User performing the action
        trigger_status: Current status (for status-based templates)
    
    Returns:
        List of created NOTScheduledTask instances
    """
    from core.models import NOTStakeholder
    
    created_tasks = []
    templates = template_set.get_all_templates()
    
    # Track application
    application, app_created = NOTTemplateSetApplication.objects.get_or_create(
        training_notification=training_notification,
        template_set=template_set,
        defaults={
            'applied_version': template_set.version,
            'applied_by': user,
        }
    )
    
    if not app_created:
        application.applied_version = template_set.version
        application.save(update_fields=['applied_version'])
    
    for name, template in templates.items():
        # Check if this template should be triggered
        should_create = False
        
        if template.trigger_type == TriggerType.STATUS_CHANGE:
            if trigger_status and template.trigger_status == trigger_status:
                should_create = True
        
        elif template.trigger_type == TriggerType.DATE_RELATIVE:
            # Date-relative tasks are created immediately and scheduled for their due date
            ref_date = template._get_reference_date(training_notification)
            if ref_date:
                should_create = True
        
        elif template.trigger_type == TriggerType.RECURRING:
            # Recurring tasks start when NOT reaches start status
            if trigger_status and template.recurring_start_status == trigger_status:
                should_create = True
        
        if not should_create:
            continue
        
        # Check for existing task from this template
        existing = NOTScheduledTask.objects.filter(
            training_notification=training_notification,
            template=template,
        ).exists()
        
        if existing and template.trigger_type != TriggerType.RECURRING:
            continue  # Don't create duplicate non-recurring tasks
        
        # Find assignee
        assignee = None
        stakeholder = NOTStakeholder.objects.filter(
            training_notification=training_notification,
            role_in_project=template.assigned_role
        ).first()
        
        if stakeholder:
            assignee = stakeholder.user
        elif template.fallback_campus_role and training_notification.delivery_campus:
            # Try campus staff role
            from tenants.models import CampusStaff
            campus_staff = CampusStaff.objects.filter(
                campus=training_notification.delivery_campus,
                role=template.fallback_campus_role,
                is_primary=True
            ).first()
            if campus_staff:
                assignee = campus_staff.user
        
        # Calculate due date
        trigger_date = timezone.now().date()
        due_date = template.calculate_due_date(training_notification, trigger_date)
        
        # Create the task
        task = Task.objects.create(
            title=template.format_title(training_notification, due_date),
            description=template.format_description(training_notification, due_date),
            category=template.task_category,
            priority=template.task_priority,
            assigned_to=assignee,
            due_date=due_date,
            content_type=ContentType.objects.get_for_model(training_notification),
            object_id=training_notification.pk,
            created_by=user,
        )
        
        # Create scheduled task record
        scheduled_task = NOTScheduledTask.objects.create(
            training_notification=training_notification,
            template=template,
            task=task,
            original_due_date=due_date,
            trigger_date=trigger_date,
        )
        
        created_tasks.append(scheduled_task)
        
        logger.info(
            f"Created scheduled task '{task.title}' for NOT {training_notification.reference_number} "
            f"from template '{template.name}'"
        )
    
    return created_tasks


def recalculate_scheduled_tasks(training_notification):
    """
    Recalculate due dates for all date-relative scheduled tasks when NOT dates change.
    
    Args:
        training_notification: TrainingNotification with changed dates
    
    Returns:
        Number of tasks that were recalculated
    """
    count = 0
    
    for scheduled_task in training_notification.scheduled_tasks.filter(
        template__trigger_type=TriggerType.DATE_RELATIVE,
        template__recalculate_on_date_change=True,
    ).select_related('task', 'template'):
        if scheduled_task.recalculate_due_date():
            count += 1
    
    if count > 0:
        logger.info(
            f"Recalculated {count} task due dates for NOT {training_notification.reference_number}"
        )
    
    return count


def notify_template_set_update(template_set, user=None):
    """
    Create notifications for project managers when a template set they use is updated.
    
    Args:
        template_set: ProjectTemplateSet that was updated
        user: User who made the update (excluded from notifications)
    
    Returns:
        Number of notifications created
    """
    from core.models import NOTStakeholder
    
    # Find NOTs using this template set that haven't been notified
    applications = NOTTemplateSetApplication.objects.filter(
        template_set=template_set,
        update_notification_sent=False,
    ).select_related('training_notification')
    
    notified_count = 0
    
    for application in applications:
        if application.needs_update_notification():
            not_obj = application.training_notification
            
            # Find project leads/managers to notify
            stakeholders = NOTStakeholder.objects.filter(
                training_notification=not_obj,
                role_in_project__in=['PROJECT_LEAD', 'PROJECT_MANAGER']
            ).exclude(user=user)
            
            for stakeholder in stakeholders:
                # Create notification task
                Task.objects.create(
                    title=f"Template Set Updated: {template_set.name}",
                    description=(
                        f"The task template set '{template_set.name}' used by project "
                        f"'{not_obj.reference_number}' has been updated. "
                        f"New templates or changed configurations may apply to this project. "
                        f"Review the project tasks to ensure alignment."
                    ),
                    category=TaskCategory.REVIEW,
                    priority=TaskPriority.MEDIUM,
                    assigned_to=stakeholder.user,
                    due_date=timezone.now().date() + timedelta(days=3),
                    content_type=ContentType.objects.get_for_model(not_obj),
                    object_id=not_obj.pk,
                )
                notified_count += 1
            
            application.update_notification_sent = True
            application.save(update_fields=['update_notification_sent'])
    
    if notified_count > 0:
        logger.info(
            f"Created {notified_count} notifications for template set '{template_set.name}' update"
        )
    
    return notified_count


def process_not_status_change_with_templates(training_notification, old_status, new_status, user=None):
    """
    Process NOT status change with the new template system.
    Finds matching template sets and applies status-triggered templates.
    
    Args:
        training_notification: TrainingNotification instance
        old_status: Previous status
        new_status: New status
        user: User who made the change
    
    Returns:
        List of created NOTScheduledTask instances
    """
    all_created_tasks = []
    
    # Get matching template sets
    template_sets = get_matching_template_sets(training_notification)
    
    for template_set in template_sets:
        created = apply_template_set(
            template_set,
            training_notification,
            user=user,
            trigger_status=new_status
        )
        all_created_tasks.extend(created)
    
    logger.info(
        f"NOT {training_notification.reference_number} status changed: {old_status} -> {new_status}. "
        f"Created {len(all_created_tasks)} tasks from {template_sets.count()} template sets."
    )
    
    return all_created_tasks
