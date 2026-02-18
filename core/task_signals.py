"""
Task Signals

Auto-generate tasks from business events.
Listens to model signals and creates appropriate tasks.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta
import logging

from .tasks import Task, TaskCategory, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)


# =====================================================
# NOT (NOTIFICATION OF TRAINING) SIGNALS
# =====================================================

@receiver(pre_save, sender='core.TrainingNotification')
def track_not_status_change(sender, instance, **kwargs):
    """Track status changes and date changes on TrainingNotification for automation"""
    if instance.pk:
        try:
            from .models import TrainingNotification
            old_instance = TrainingNotification.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
            # Track date changes for task recalculation
            instance._old_planned_start_date = old_instance.planned_start_date
            instance._old_planned_end_date = old_instance.planned_end_date
            instance._old_actual_start_date = old_instance.actual_start_date
            instance._old_actual_end_date = old_instance.actual_end_date
        except Exception:
            instance._old_status = None
            instance._old_planned_start_date = None
            instance._old_planned_end_date = None
            instance._old_actual_start_date = None
            instance._old_actual_end_date = None
    else:
        instance._old_status = None
        instance._old_planned_start_date = None
        instance._old_planned_end_date = None
        instance._old_actual_start_date = None
        instance._old_actual_end_date = None


@receiver(post_save, sender='core.TrainingNotification')
def handle_not_status_change(sender, instance, created, **kwargs):
    """
    Handle NOT status changes - trigger automation.
    Creates tranches, GrantProject, and tasks when status changes.
    Also recalculates scheduled tasks when dates change.
    """
    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status
    
    # Check for date changes (for task recalculation)
    dates_changed = False
    if not created:
        old_dates = (
            getattr(instance, '_old_planned_start_date', None),
            getattr(instance, '_old_planned_end_date', None),
            getattr(instance, '_old_actual_start_date', None),
            getattr(instance, '_old_actual_end_date', None),
        )
        new_dates = (
            instance.planned_start_date,
            instance.planned_end_date,
            instance.actual_start_date,
            instance.actual_end_date,
        )
        dates_changed = old_dates != new_dates
    
    # Recalculate scheduled tasks if dates changed
    if dates_changed:
        try:
            from .project_templates import recalculate_scheduled_tasks
            recalculated = recalculate_scheduled_tasks(instance)
            if recalculated > 0:
                logger.info(
                    f"NOT {instance.reference_number}: Recalculated {recalculated} task due dates after date change"
                )
        except Exception as e:
            logger.error(f"Error recalculating tasks for NOT {instance.reference_number}: {e}")
    
    # Only process status change automation if status actually changed or if newly created
    if created or (old_status and old_status != new_status):
        try:
            from .not_automation import process_not_status_change
            
            # Get the user who made the change (from updated_by if available)
            user = getattr(instance, 'updated_by', None) or getattr(instance, 'created_by', None)
            
            result = process_not_status_change(instance, old_status, new_status, user)
            
            # Log summary
            logger.info(
                f"NOT {instance.reference_number} automation complete: "
                f"{len(result.get('tranches', []))} tranches, "
                f"{'1 GrantProject' if result.get('grant_project') else '0 GrantProject'}, "
                f"{len(result.get('tasks', []))} tasks, "
                f"{len(result.get('scheduled_tasks', []))} scheduled tasks created"
            )
        except Exception as e:
            logger.error(f"Error processing NOT status change for {instance.reference_number}: {e}")


# =====================================================
# DOCUMENT SIGNALS
# =====================================================

# Note: Document signal will be connected when LearnerDocument model is verified
# @receiver(post_save, sender='learners.LearnerDocument')
# def create_document_verification_task(sender, instance, created, **kwargs):
#     """When a document is uploaded, create verification task"""
#     if created and instance.verification_status == 'PENDING':
#         Task.create_task(
#             title=f'Verify document: {instance.document_type} for {instance.learner}',
#             description=f'Document uploaded needs verification.',
#             category=TaskCategory.DOCUMENT_VERIFICATION,
#             assigned_role='REGISTRAR',
#             due_date=timezone.now().date() + timedelta(days=2),
#             priority=TaskPriority.MEDIUM,
#             related_object=instance,
#             action_url=f'/admin/learners/learnerdocument/{instance.pk}/change/',
#             is_auto=True,
#             source_event='document_uploaded'
#         )


# =====================================================
# ENROLLMENT SIGNALS
# =====================================================

@receiver(post_save, sender='academics.Enrollment')
def create_enrollment_tasks(sender, instance, created, **kwargs):
    """When enrollment is created or status changes"""
    if created:
        # Create SETA registration task
        Task.create_task(
            title=f'Register with SETA: {instance.learner}',
            description=f'New enrollment for {instance.qualification.title} needs SETA registration.',
            category=TaskCategory.REGISTRATION_SETA,
            assigned_role='REGISTRAR',
            due_date=timezone.now().date() + timedelta(days=5),
            priority=TaskPriority.HIGH,
            related_object=instance,
            action_url=f'/admin/academics/enrollment/{instance.pk}/change/',
            is_auto=True,
            source_event='enrollment_created'
        )
        
        # Create invoice task if self-funded
        if instance.funding_type == 'SELF':
            Task.create_task(
                title=f'Create invoice: {instance.learner}',
                description=f'Generate invoice for enrollment in {instance.qualification.short_title}.',
                category=TaskCategory.INVOICE_CREATE,
                assigned_role='FINANCE_CLERK',
                due_date=timezone.now().date() + timedelta(days=3),
                priority=TaskPriority.MEDIUM,
                related_object=instance,
                action_url=f'/admin/finance/invoice/add/?enrollment={instance.pk}',
                is_auto=True,
                source_event='enrollment_created'
            )


# =====================================================
# ASSESSMENT SIGNALS
# =====================================================

@receiver(post_save, sender='assessments.AssessmentResult')
def create_assessment_tasks(sender, instance, created, **kwargs):
    """When assessment result is submitted or needs moderation"""
    if instance.status == 'SUBMITTED':
        # Create marking task
        Task.create_task(
            title=f'Mark assessment: {instance.enrollment.learner} - {instance.activity.name}',
            description=f'Assessment submitted and needs grading.',
            category=TaskCategory.ASSESSMENT_MARK,
            assigned_to=instance.assessor,
            due_date=timezone.now().date() + timedelta(days=3),
            priority=TaskPriority.HIGH,
            related_object=instance,
            action_url=f'/portal/facilitator/assess/{instance.pk}/',
            is_auto=True,
            source_event='assessment_submitted'
        )
    
    elif instance.status == 'PENDING_MOD':
        # Create moderation task
        Task.create_task(
            title=f'Moderate assessment: {instance.enrollment.learner} - {instance.activity.name}',
            description=f'Assessment has been marked and needs moderation.',
            category=TaskCategory.ASSESSMENT_MODERATE,
            assigned_role='MODERATOR',
            due_date=timezone.now().date() + timedelta(days=5),
            priority=TaskPriority.MEDIUM,
            related_object=instance,
            action_url=f'/portal/facilitator/moderate/{instance.pk}/',
            is_auto=True,
            source_event='assessment_needs_moderation'
        )


@receiver(post_save, sender='assessments.PoESubmission')
def create_poe_review_task(sender, instance, created, **kwargs):
    """When PoE is submitted"""
    if created:
        Task.create_task(
            title=f'Review PoE: {instance.enrollment.learner}',
            description=f'Portfolio of Evidence submitted for {instance.enrollment.qualification.short_title}.',
            category=TaskCategory.POE_REVIEW,
            assigned_role='ASSESSOR',
            due_date=timezone.now().date() + timedelta(days=7),
            priority=TaskPriority.MEDIUM,
            related_object=instance,
            action_url=f'/admin/assessments/poesubmission/{instance.pk}/change/',
            is_auto=True,
            source_event='poe_submitted'
        )


# =====================================================
# FINANCE SIGNALS
# =====================================================

@receiver(post_save, sender='finance.Invoice')
def create_invoice_tasks(sender, instance, **kwargs):
    """When invoice becomes overdue or needs follow-up"""
    today = timezone.now().date()
    
    # Check if just became overdue
    if instance.status == 'SENT' and instance.due_date < today:
        # Check if overdue task already exists
        existing = Task.objects.filter(
            content_type=ContentType.objects.get_for_model(instance),
            object_id=instance.pk,
            category=TaskCategory.PAYMENT_OVERDUE,
            status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        ).exists()
        
        if not existing:
            Task.create_task(
                title=f'Overdue invoice: {instance.invoice_number}',
                description=f'Invoice {instance.invoice_number} is overdue. Balance: R{instance.balance_due}',
                category=TaskCategory.PAYMENT_OVERDUE,
                assigned_role='FINANCE_CLERK',
                due_date=today,
                priority=TaskPriority.URGENT,
                related_object=instance,
                action_url=f'/admin/finance/invoice/{instance.pk}/change/',
                is_auto=True,
                source_event='invoice_overdue'
            )


# =====================================================
# ATTENDANCE SIGNALS
# =====================================================

@receiver(post_save, sender='logistics.ScheduleSession')
def create_attendance_task(sender, instance, created, **kwargs):
    """Create attendance capture task after session date"""
    today = timezone.now().date()
    
    if instance.date <= today and not instance.is_cancelled:
        # Check if attendance already recorded
        if not instance.attendance_records.exists():
            # Check if task already exists
            existing = Task.objects.filter(
                content_type=ContentType.objects.get_for_model(instance),
                object_id=instance.pk,
                category=TaskCategory.ATTENDANCE_CAPTURE,
                status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
            ).exists()
            
            if not existing:
                Task.create_task(
                    title=f'Capture attendance: {instance.cohort.code} - {instance.date}',
                    description=f'Session for {instance.module.title} needs attendance capture.',
                    category=TaskCategory.ATTENDANCE_CAPTURE,
                    assigned_to=instance.facilitator,
                    due_date=instance.date + timedelta(days=1),
                    priority=TaskPriority.HIGH,
                    related_object=instance,
                    action_url=f'/capture/attendance/{instance.pk}/',
                    is_auto=True,
                    source_event='session_completed'
                )


# =====================================================
# GRANT/PROJECT SIGNALS
# =====================================================

@receiver(post_save, sender='corporate.GrantProject')
def create_grant_tasks(sender, instance, **kwargs):
    """Create tasks for grant milestones"""
    today = timezone.now().date()
    
    if instance.status == 'ACTIVE':
        # Check for upcoming reporting deadlines
        if instance.end_date and (instance.end_date - today).days <= 30:
            existing = Task.objects.filter(
                content_type=ContentType.objects.get_for_model(instance),
                object_id=instance.pk,
                category=TaskCategory.REPORT_DUE,
                status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
            ).exists()
            
            if not existing:
                Task.create_task(
                    title=f'Project completion report: {instance.project_name}',
                    description=f'Project end date approaching. Prepare completion report.',
                    category=TaskCategory.REPORT_DUE,
                    assigned_to=instance.project_manager,
                    due_date=instance.end_date - timedelta(days=7),
                    priority=TaskPriority.HIGH,
                    related_object=instance,
                    action_url=f'/admin/corporate/grantproject/{instance.pk}/change/',
                    is_auto=True,
                    source_event='grant_ending_soon'
                )


# =====================================================
# LEARNER AT-RISK SIGNALS
# =====================================================

def check_learner_at_risk(enrollment):
    """Check if learner is at risk and create intervention task"""
    from assessments.models import AssessmentResult
    from django.db.models import Count, Q
    
    # Count NYC results
    nyc_count = AssessmentResult.objects.filter(
        enrollment=enrollment,
        result='NYC'
    ).count()
    
    if nyc_count >= 2:
        # Check if task already exists
        existing = Task.objects.filter(
            content_type=ContentType.objects.get_for_model(enrollment),
            object_id=enrollment.pk,
            category=TaskCategory.LEARNER_AT_RISK,
            status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        ).exists()
        
        if not existing:
            Task.create_task(
                title=f'At-risk learner: {enrollment.learner}',
                description=f'Learner has {nyc_count} NYC results. Intervention required.',
                category=TaskCategory.LEARNER_AT_RISK,
                assigned_to=enrollment.cohort.facilitator if enrollment.cohort else None,
                assigned_role='FACILITATOR' if not enrollment.cohort else '',
                due_date=timezone.now().date() + timedelta(days=3),
                priority=TaskPriority.HIGH,
                related_object=enrollment,
                action_url=f'/admin/academics/enrollment/{enrollment.pk}/change/',
                is_auto=True,
                source_event='learner_at_risk'
            )


# Connect the at-risk check to assessment results
@receiver(post_save, sender='assessments.AssessmentResult')
def check_at_risk_on_assessment(sender, instance, **kwargs):
    """After NYC result, check if learner is at risk"""
    if instance.result == 'NYC':
        check_learner_at_risk(instance.enrollment)


# =====================================================
# UTILITY FUNCTIONS
# =====================================================

def complete_related_tasks(model_instance, category=None):
    """
    Mark all pending tasks related to a model instance as complete.
    Called when the underlying action is completed.
    """
    content_type = ContentType.objects.get_for_model(model_instance)
    tasks = Task.objects.filter(
        content_type=content_type,
        object_id=model_instance.pk,
        status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
    )
    
    if category:
        tasks = tasks.filter(category=category)
    
    tasks.update(
        status=TaskStatus.COMPLETED,
        completed_at=timezone.now()
    )


def create_reminder_tasks():
    """
    Scheduled task to create reminder tasks for upcoming deadlines.
    Should be run daily via cron/celery.
    """
    from academics.models import Enrollment
    from finance.models import Invoice
    from assessments.models import AssessmentActivity
    
    today = timezone.now().date()
    
    # Assessment due reminders
    upcoming_assessments = AssessmentActivity.objects.filter(
        due_date=today + timedelta(days=3),
        is_active=True
    )
    
    for activity in upcoming_assessments:
        # Create task for each enrolled learner
        for enrollment in activity.module.qualification.enrollments.filter(status='ACTIVE'):
            Task.create_task(
                title=f'Assessment due soon: {activity.name}',
                description=f'Assessment due in 3 days.',
                category=TaskCategory.ASSESSMENT_DUE,
                assigned_to=enrollment.learner.user if hasattr(enrollment.learner, 'user') else None,
                due_date=activity.due_date,
                priority=TaskPriority.MEDIUM,
                related_object=activity,
                is_auto=True,
                source_event='assessment_reminder'
            )
    
    # Invoice payment reminders
    invoices_due_soon = Invoice.objects.filter(
        due_date=today + timedelta(days=7),
        status='SENT'
    )
    
    for invoice in invoices_due_soon:
        Task.create_task(
            title=f'Payment due soon: {invoice.invoice_number}',
            description=f'Invoice due in 7 days. Amount: R{invoice.balance_due}',
            category=TaskCategory.PAYMENT_FOLLOW_UP,
            assigned_role='FINANCE_CLERK',
            due_date=invoice.due_date,
            priority=TaskPriority.MEDIUM,
            related_object=invoice,
            is_auto=True,
            source_event='payment_reminder'
        )


# =====================================================
# NOT INTAKE - IMPLEMENTATION PLAN AUTO-CREATION
# =====================================================

@receiver(pre_save, sender='core.NOTIntake')
def track_notintake_cohort_change(sender, instance, **kwargs):
    """Track cohort changes on NOTIntake for implementation plan auto-creation"""
    if instance.pk:
        try:
            from .models import NOTIntake
            old_instance = NOTIntake.objects.get(pk=instance.pk)
            instance._old_cohort_id = old_instance.cohort_id
        except Exception:
            instance._old_cohort_id = None
    else:
        instance._old_cohort_id = None


@receiver(post_save, sender='core.NOTIntake')
def auto_create_cohort_implementation_plan(sender, instance, created, **kwargs):
    """
    Auto-create CohortImplementationPlan when cohort is linked to NOTIntake.
    Uses the qualification's default active ImplementationPlan template.
    """
    old_cohort_id = getattr(instance, '_old_cohort_id', None)
    
    # Only process if cohort was just linked (wasn't before, is now)
    if not instance.cohort:
        return
    
    # Check if this is a new cohort link
    if old_cohort_id == instance.cohort_id:
        return  # No change
    
    # Check if implementation plan already exists for this cohort
    if hasattr(instance.cohort, 'implementation_plan'):
        logger.info(f"Cohort {instance.cohort.code} already has an implementation plan")
        return
    
    # Find the qualification from the NOT
    qualification = instance.training_notification.qualification
    if not qualification:
        logger.warning(f"NOT {instance.training_notification.reference_number} has no qualification linked")
        return
    
    # Find the default active implementation plan template
    from academics.models import ImplementationPlan
    
    template = ImplementationPlan.objects.filter(
        qualification=qualification,
        is_default=True,
        status='ACTIVE'
    ).first()
    
    if not template:
        logger.info(
            f"No active default implementation plan template found for "
            f"qualification {qualification.saqa_id}. Skipping auto-creation."
        )
        return
    
    # Get the user who made the change
    user = getattr(instance, 'updated_by', None) or getattr(instance, 'created_by', None)
    
    try:
        # Create the cohort implementation plan from template
        cohort_plan = template.copy_to_cohort(instance.cohort, created_by=user)
        
        logger.info(
            f"Auto-created implementation plan '{cohort_plan.name}' for "
            f"cohort {instance.cohort.code} from template '{template.name}'"
        )
        
        # Auto-generate schedule sessions from the implementation plan
        try:
            sessions = cohort_plan.generate_schedule_sessions()
            logger.info(
                f"Auto-generated {len(sessions)} schedule sessions for "
                f"cohort {instance.cohort.code}"
            )
        except Exception as schedule_error:
            logger.error(
                f"Error generating schedule sessions for cohort "
                f"{instance.cohort.code}: {schedule_error}"
            )
            
    except Exception as e:
        logger.error(
            f"Error auto-creating implementation plan for cohort "
            f"{instance.cohort.code}: {e}"
        )
