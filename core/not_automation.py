"""
NOT (Notification of Training) Automation Module

Handles automatic creation of:
1. Tranche schedules from templates when NOT is approved
2. Tasks assigned to stakeholders based on status changes
3. GrantProject records for SETA-funded projects
4. Reminders and follow-up tasks
"""
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta
from decimal import Decimal
import logging

from .tasks import Task, TaskCategory, TaskPriority

logger = logging.getLogger(__name__)


class NOTTaskTemplate(models.Model):
    """
    Templates for auto-generating tasks when NOT status changes.
    Tasks are created incrementally as the NOT progresses through statuses.
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
    
    # Trigger conditions
    trigger_status = models.CharField(
        max_length=30,
        choices=TRIGGER_STATUS_CHOICES,
        help_text="NOT status that triggers this task"
    )
    
    project_type = models.CharField(
        max_length=30,
        blank=True,
        help_text="Optional: Only apply to specific project types (leave blank for all)"
    )
    
    funder_type = models.CharField(
        max_length=30,
        blank=True,
        help_text="Optional: Only apply to specific funder types (leave blank for all)"
    )
    
    # Task details
    name = models.CharField(max_length=100)
    task_title_template = models.CharField(
        max_length=200,
        help_text="Use {reference_number}, {title}, {qualification}, {learner_count}, {client_name}"
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
    
    # Due date calculation
    due_days_offset = models.PositiveIntegerField(
        default=7,
        help_text="Days from status change when task is due"
    )
    
    # Ordering
    sequence = models.PositiveIntegerField(
        default=1,
        help_text="Order of task creation for same trigger status"
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['trigger_status', 'sequence']
        verbose_name = 'NOT Task Template'
        verbose_name_plural = 'NOT Task Templates'
        unique_together = ['trigger_status', 'name']
    
    def __str__(self):
        return f"[{self.trigger_status}] {self.name}"


# =====================================================
# AUTOMATION HELPER FUNCTIONS
# =====================================================

def generate_tranches_for_not(training_notification, user=None):
    """
    Auto-generate tranches for a NOT from the best matching template.
    Called when NOT is approved.
    
    Args:
        training_notification: TrainingNotification instance
        user: User performing the action (for audit)
    
    Returns:
        List of created TrancheSchedule instances
    """
    from .models import TrancheTemplate, TrancheSchedule, TrancheEvidenceRequirement
    
    # Find matching template - first try exact match
    template = TrancheTemplate.objects.filter(
        is_active=True,
        project_type=training_notification.project_type,
        funder_type=training_notification.funder
    ).first()
    
    if not template:
        # Try to find template matching just project type
        template = TrancheTemplate.objects.filter(
            is_active=True,
            project_type=training_notification.project_type
        ).first()
    
    if not template:
        # Try any active template
        template = TrancheTemplate.objects.filter(is_active=True).first()
    
    if not template:
        logger.warning(
            f"No tranche template found for NOT {training_notification.reference_number} "
            f"(type: {training_notification.project_type}, funder: {training_notification.funder})"
        )
        return []
    
    # Calculate dates
    start_date = training_notification.planned_start_date or timezone.now().date()
    contract_value = training_notification.contract_value or Decimal('0')
    
    created_tranches = []
    
    for item in template.items.all().order_by('sequence_number'):
        # Calculate due date
        due_date = start_date + timedelta(days=item.months_from_start * 30)
        reminder_date = due_date - timedelta(days=item.days_before_deadline_reminder)
        
        # Calculate amount
        amount = Decimal('0')
        if contract_value > 0:
            amount = (contract_value * item.percentage_of_total / 100).quantize(Decimal('0.01'))
        
        # Create tranche
        tranche, created = TrancheSchedule.objects.update_or_create(
            training_notification=training_notification,
            sequence_number=item.sequence_number,
            defaults={
                'template_item': item,
                'tranche_type': item.tranche_type,
                'name': item.name,
                'description': item.description,
                'status': 'SCHEDULED',
                'priority': 'HIGH' if item.months_from_start <= 1 else 'MEDIUM',
                'due_date': due_date,
                'reminder_date': reminder_date,
                'amount': amount,
                'learner_count_target': training_notification.expected_learner_count or 0,
                'created_by': user,
            }
        )
        
        if created:
            created_tranches.append(tranche)
            
            # Create evidence requirements from template
            for evidence in item.evidence_requirements or []:
                TrancheEvidenceRequirement.objects.create(
                    tranche=tranche,
                    evidence_type=evidence.get('type', 'OTHER'),
                    name=evidence.get('name', 'Evidence'),
                    description=evidence.get('description', ''),
                    is_mandatory=evidence.get('mandatory', True),
                    created_by=user,
                )
    
    logger.info(
        f"Generated {len(created_tranches)} tranches for NOT {training_notification.reference_number} "
        f"using template '{template.name}'"
    )
    
    return created_tranches


def create_grant_project_for_not(training_notification, user=None):
    """
    Create a GrantProject record for SETA-funded NOTs.
    Called when NOT is approved.
    
    Args:
        training_notification: TrainingNotification instance
        user: User performing the action
    
    Returns:
        GrantProject instance or None
    """
    from corporate.models import GrantProject, CorporateClient
    from learners.models import SETA
    
    # Only create for SETA-funded projects (discretionary grants)
    seta_funders = ['CORPORATE_DG', 'PRIVATE']
    if training_notification.funder not in seta_funders:
        logger.info(
            f"NOT {training_notification.reference_number} funder '{training_notification.funder}' "
            f"not eligible for GrantProject creation"
        )
        return None
    
    # Get or create corporate client
    client = training_notification.corporate_client
    if not client:
        # Need campus for CorporateClient (TenantAwareModel)
        campus = training_notification.delivery_campus
        if not campus:
            from tenants.models import Campus
            campus = Campus.objects.first()
        
        if not campus:
            logger.warning(
                f"Cannot create GrantProject for NOT {training_notification.reference_number}: No campus found"
            )
            return None
        
        # Create a placeholder client for private/unknown funders
        client, _ = CorporateClient.objects.get_or_create(
            company_name=training_notification.client_name or 'Private Learners',
            campus=campus,
            defaults={
                'status': 'ACTIVE',
                'phone': 'N/A',
                'email': 'noreply@placeholder.com',
                'physical_address': 'N/A',
            }
        )
    
    # Get SETA from qualification
    seta = None
    if training_notification.qualification:
        seta = training_notification.qualification.seta
    
    if not seta:
        # Try to get default SETA
        seta = SETA.objects.first()
        if not seta:
            logger.warning(
                f"Cannot create GrantProject for NOT {training_notification.reference_number}: No SETA found"
            )
            return None
    
    # Find project manager from stakeholders
    project_manager = None
    pm_stakeholder = training_notification.stakeholders.filter(
        role_in_project__in=['PROJECT_LEAD', 'PROJECT_MANAGER']
    ).first()
    if pm_stakeholder:
        project_manager = pm_stakeholder.user
    
    # Get campus for GrantProject (TenantAwareModel)
    campus = training_notification.delivery_campus
    if not campus:
        from tenants.models import Campus
        campus = Campus.objects.first()
    
    if not campus:
        logger.warning(
            f"Cannot create GrantProject for NOT {training_notification.reference_number}: No campus found"
        )
        return None
    
    # Create grant project
    grant_project, created = GrantProject.objects.update_or_create(
        client=client,
        project_name=training_notification.title,
        seta=seta,
        campus=campus,
        defaults={
            'project_number': training_notification.reference_number,
            'status': 'APPROVED',
            'application_date': training_notification.created_at.date() if training_notification.created_at else None,
            'approval_date': training_notification.approved_date.date() if training_notification.approved_date else timezone.now().date(),
            'start_date': training_notification.planned_start_date,
            'end_date': training_notification.planned_end_date,
            'approved_amount': training_notification.contract_value or Decimal('0'),
            'target_learners': training_notification.expected_learner_count or 0,
            'project_manager': project_manager,
            'notes': f"Auto-created from NOT {training_notification.reference_number}",
        }
    )
    
    if created:
        logger.info(f"Created GrantProject for NOT {training_notification.reference_number}")
    
    return grant_project


def create_intakes_and_cohorts_for_not(training_notification, user=None):
    """
    Create intakes and cohorts for a NOT when it's approved.
    - Creates a default intake if none exist
    - Creates a cohort for the intake
    - Links the cohort to the intake (triggers auto-creation of implementation plan)
    
    Args:
        training_notification: TrainingNotification instance
        user: User performing the action
    
    Returns:
        Dict with created intake and cohort, or None if already exists
    """
    from .models import NOTIntake
    from logistics.models import Cohort
    from tenants.models import Campus
    
    result = {
        'intake': None,
        'cohort': None,
        'implementation_plan': None,
    }
    
    # Check if intakes already exist
    if training_notification.intakes.exists():
        logger.info(
            f"NOT {training_notification.reference_number} already has intakes. Skipping auto-creation."
        )
        return result
    
    # Validate required data
    if not training_notification.qualification:
        logger.warning(
            f"NOT {training_notification.reference_number} has no qualification. Cannot create cohort."
        )
        return result
    
    # Get campus
    campus = training_notification.delivery_campus
    if not campus:
        campus = Campus.objects.first()
        if not campus:
            logger.warning(
                f"No campus available for NOT {training_notification.reference_number}. Cannot create cohort."
            )
            return result
    
    # Determine start date
    start_date = training_notification.planned_start_date
    if not start_date:
        start_date = timezone.now().date() + timedelta(days=30)  # Default 30 days from now
    
    # Create the intake
    intake = NOTIntake.objects.create(
        training_notification=training_notification,
        intake_number=1,
        name="Main Intake",
        status='PLANNED',
        intake_date=start_date,
        original_cohort_size=training_notification.expected_learner_count or 0,
        created_by=user,
    )
    result['intake'] = intake
    logger.info(f"Created intake for NOT {training_notification.reference_number}")
    
    # Generate cohort code
    qual = training_notification.qualification
    year = start_date.year
    month = start_date.strftime('%m')
    
    # Count existing cohorts for this qualification/year to get sequence
    existing_count = Cohort.objects.filter(
        qualification=qual,
        start_date__year=year
    ).count()
    sequence = existing_count + 1
    
    cohort_code = f"{qual.saqa_id}-{year}{month}-{sequence:02d}"
    
    # Get facilitator from stakeholders
    facilitator = None
    facilitator_stakeholder = training_notification.stakeholders.filter(
        role_in_project='FACILITATOR'
    ).first()
    if facilitator_stakeholder:
        facilitator = facilitator_stakeholder.user
    
    # Calculate end date if not provided
    end_date = training_notification.planned_end_date
    if not end_date:
        # Default to 1 year from start
        end_date = start_date + timedelta(days=365)
    
    # Create the cohort
    cohort = Cohort.objects.create(
        code=cohort_code,
        name=f"{qual.short_title} - {training_notification.title}",
        qualification=qual,
        campus=campus,
        start_date=start_date,
        end_date=end_date,
        status='PLANNED',
        max_capacity=training_notification.expected_learner_count or 30,
        facilitator=facilitator,
    )
    result['cohort'] = cohort
    logger.info(f"Created cohort {cohort.code} for NOT {training_notification.reference_number}")
    
    # Link cohort to intake (this triggers the signal to create implementation plan)
    intake.cohort = cohort
    intake.save(update_fields=['cohort'])
    
    # Check if implementation plan was created
    if hasattr(cohort, 'implementation_plan'):
        result['implementation_plan'] = cohort.implementation_plan
        logger.info(f"Implementation plan created for cohort {cohort.code}")
    
    return result


def create_not_tasks(training_notification, new_status, user=None):
    """
    Create tasks based on NOT status change.
    Uses NOTTaskTemplate to determine which tasks to create.
    
    Args:
        training_notification: TrainingNotification instance
        new_status: The new status triggering task creation
        user: User performing the action
    
    Returns:
        List of created Task instances
    """
    # Get applicable templates
    templates = NOTTaskTemplate.objects.filter(
        is_active=True,
        trigger_status=new_status
    ).order_by('sequence')
    
    # Filter by project type if specified
    templates = templates.filter(
        Q(project_type='') | 
        Q(project_type=training_notification.project_type)
    )
    
    # Filter by funder type if specified
    templates = templates.filter(
        Q(funder_type='') | 
        Q(funder_type=training_notification.funder)
    )
    
    created_tasks = []
    
    # Build context for placeholders
    context = {
        'reference_number': training_notification.reference_number,
        'title': training_notification.title,
        'qualification': training_notification.qualification.short_title if training_notification.qualification else 'N/A',
        'learner_count': training_notification.expected_learner_count or 0,
        'client_name': training_notification.client_name or (
            training_notification.corporate_client.company_name if training_notification.corporate_client else 'N/A'
        ),
        'campus': training_notification.delivery_campus.name if training_notification.delivery_campus else 'N/A',
    }
    
    for template in templates:
        # Resolve title and description with placeholders
        try:
            title = template.task_title_template.format(**context)
            description = template.task_description_template.format(**context) if template.task_description_template else ''
        except KeyError as e:
            logger.warning(f"Template placeholder error: {e}")
            title = template.task_title_template
            description = template.task_description_template
        
        # Find assignee
        assigned_to = None
        
        # First try to find stakeholder with matching role
        stakeholder = training_notification.stakeholders.filter(
            role_in_project=template.assigned_role
        ).first()
        
        if stakeholder:
            assigned_to = stakeholder.user
        elif template.fallback_campus_role and training_notification.delivery_campus:
            # Try campus role fallback
            try:
                from core.models import UserRole
                role_assignment = UserRole.objects.filter(
                    campus=training_notification.delivery_campus,
                    role__name=template.fallback_campus_role,
                    is_active=True
                ).first()
                if role_assignment:
                    assigned_to = role_assignment.user
            except Exception as e:
                logger.warning(f"Could not resolve fallback role: {e}")
        
        # Calculate due date
        due_date = timezone.now().date() + timedelta(days=template.due_days_offset)
        
        # Create task
        task = Task.create_task(
            title=title,
            description=description,
            category=template.task_category,
            assigned_to=assigned_to,
            assigned_role=template.fallback_campus_role if not assigned_to else '',
            due_date=due_date,
            priority=template.task_priority,
            related_object=training_notification,
            action_url=f'/not/{training_notification.pk}/',
            is_auto=True,
            source_event=f'not_status_{new_status.lower()}'
        )
        
        if training_notification.delivery_campus:
            task.assigned_campus = training_notification.delivery_campus
            task.save()
        
        created_tasks.append(task)
        logger.info(f"Created task '{title}' for NOT {training_notification.reference_number}")
    
    return created_tasks


def process_not_status_change(training_notification, old_status, new_status, user=None):
    """
    Main entry point for NOT status change automation.
    Orchestrates all automatic actions based on status transitions.
    
    This function now integrates with both:
    1. Legacy NOTTaskTemplate system (for backward compatibility)
    2. New ProjectTemplateSet system (for enhanced task scheduling)
    
    Args:
        training_notification: TrainingNotification instance
        old_status: Previous status
        new_status: New status
        user: User performing the action
    
    Returns:
        Dict with created objects
    """
    from .project_templates import (
        get_matching_template_sets,
        apply_template_set,
        process_not_status_change_with_templates
    )
    
    result = {
        'tranches': [],
        'grant_project': None,
        'intake_cohort': None,
        'tasks': [],
        'scheduled_tasks': [],  # New: from ProjectTemplateSet system
    }
    
    logger.info(
        f"Processing NOT status change: {training_notification.reference_number} "
        f"from '{old_status}' to '{new_status}'"
    )
    
    # On APPROVED status - generate tranches, create grant project, and create intake/cohort
    if new_status == 'APPROVED' and old_status != 'APPROVED':
        # Generate tranche schedule
        result['tranches'] = generate_tranches_for_not(training_notification, user)
        
        # Create GrantProject for SETA-funded projects
        result['grant_project'] = create_grant_project_for_not(training_notification, user)
        
        # Create intake and cohort with implementation plan
        result['intake_cohort'] = create_intakes_and_cohorts_for_not(training_notification, user)
    
    # Create tasks using legacy system (NOTTaskTemplate)
    result['tasks'] = create_not_tasks(training_notification, new_status, user)
    
    # Create tasks using new ProjectTemplateSet system
    try:
        result['scheduled_tasks'] = process_not_status_change_with_templates(
            training_notification, old_status, new_status, user
        )
    except Exception as e:
        logger.error(f"Error processing new template system: {e}")
        # Don't fail the whole operation if new system has issues
    
    return result


# =====================================================
# TRANCHE REMINDER TASKS
# =====================================================

def create_tranche_reminder_tasks():
    """
    Create reminder tasks for upcoming tranche deadlines.
    Should be run daily via scheduled job.
    
    Returns:
        List of created Task instances
    """
    from .models import TrancheSchedule
    
    today = timezone.now().date()
    
    # Find tranches with reminder date = today
    tranches_needing_reminder = TrancheSchedule.objects.filter(
        is_deleted=False,
        status__in=['SCHEDULED', 'EVIDENCE_COLLECTION'],
        reminder_date=today
    ).select_related('training_notification')
    
    created_tasks = []
    
    for tranche in tranches_needing_reminder:
        # Check if reminder task already exists
        ct = ContentType.objects.get_for_model(tranche)
        existing = Task.objects.filter(
            content_type=ct,
            object_id=tranche.pk,
            source_event='tranche_reminder',
            status__in=['pending', 'in_progress']
        ).exists()
        
        if not existing:
            # Find SDF or project manager
            assigned_to = None
            stakeholder = tranche.training_notification.stakeholders.filter(
                role_in_project__in=['COMPLIANCE_LEAD', 'PROJECT_MANAGER']
            ).first()
            if stakeholder:
                assigned_to = stakeholder.user
            
            task = Task.create_task(
                title=f"Tranche Due Soon: {tranche.name}",
                description=f"Tranche {tranche.sequence_number} for {tranche.training_notification.reference_number} "
                           f"is due on {tranche.due_date}. Ensure all evidence is collected and QC completed.",
                category=TaskCategory.TRANCHE_CLAIM,
                assigned_to=assigned_to,
                assigned_role='SDF' if not assigned_to else '',
                due_date=tranche.due_date,
                priority=TaskPriority.HIGH,
                related_object=tranche,
                action_url=f'/tranches/{tranche.pk}/',
                is_auto=True,
                source_event='tranche_reminder'
            )
            created_tasks.append(task)
            logger.info(f"Created tranche reminder task for {tranche.training_notification.reference_number} - {tranche.name}")
    
    return created_tasks
