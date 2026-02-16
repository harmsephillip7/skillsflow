"""
Signals for the academics app
Auto-updates LearnerModuleProgress when assessment results are finalized
Auto-updates CohortImplementationPhase dates based on learner progress
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='assessments.AssessmentResult')
def update_learner_module_progress(sender, instance, created, **kwargs):
    """
    Auto-update LearnerModuleProgress when an AssessmentResult is saved
    Only triggers for FINALIZED results to avoid premature updates
    """
    # Only process finalized results
    if instance.status != 'FINALIZED':
        return
    
    from academics.models import LearnerModuleProgress
    
    enrollment = instance.enrollment
    module = instance.activity.module
    
    # Get or create the progress record
    progress, _ = LearnerModuleProgress.objects.get_or_create(
        enrollment=enrollment,
        module=module
    )
    
    # Calculate progress (respects manual override internally)
    progress.calculate_progress(save=True)


@receiver(post_save, sender='academics.Enrollment')
def create_module_progress_records(sender, instance, created, **kwargs):
    """
    Create LearnerModuleProgress records when enrollment becomes ACTIVE
    This pre-creates the progress tracking records for all modules
    """
    if instance.status not in ['ACTIVE', 'ENROLLED']:
        return
    
    from academics.models import LearnerModuleProgress, Module
    
    # Get all modules for this qualification
    modules = Module.objects.filter(
        qualification=instance.qualification,
        is_active=True
    )
    
    # Create progress records for any missing modules
    for module in modules:
        LearnerModuleProgress.objects.get_or_create(
            enrollment=instance,
            module=module
        )


@receiver(post_save, sender='academics.LearnerModuleProgress')
def update_implementation_phase_from_progress(sender, instance, **kwargs):
    """
    Update CohortImplementationPhase dates when learner module progress changes.
    When modules in a phase start/complete, update the phase actual dates.
    """
    if instance.overall_status not in ['IN_PROGRESS', 'COMPETENT']:
        return
    
    try:
        # Get the enrollment's cohort
        enrollment = instance.enrollment
        if not enrollment or not hasattr(enrollment, 'cohort') or not enrollment.cohort:
            return
        
        cohort = enrollment.cohort
        
        # Check if cohort has an implementation plan
        if not hasattr(cohort, 'implementation_plan'):
            return
        
        implementation_plan = cohort.implementation_plan
        module = instance.module
        
        # Find the phase containing this module
        from logistics.models import CohortImplementationModuleSlot
        
        module_slots = CohortImplementationModuleSlot.objects.filter(
            cohort_implementation_phase__cohort_implementation_plan=implementation_plan,
            module=module
        )
        
        for slot in module_slots:
            phase = slot.cohort_implementation_phase
            
            # Update slot status if module is competent
            if instance.overall_status == 'COMPETENT' and slot.status != 'COMPLETED':
                from django.utils import timezone
                slot.status = 'COMPLETED'
                if not slot.actual_end_date:
                    slot.actual_end_date = timezone.now().date()
                slot.save()
            elif instance.overall_status == 'IN_PROGRESS' and slot.status == 'PENDING':
                from django.utils import timezone
                slot.status = 'IN_PROGRESS'
                if not slot.actual_start_date:
                    slot.actual_start_date = timezone.now().date()
                slot.save()
            
            # Update phase dates from slot progress
            phase.update_dates_from_progress()
            
    except Exception as e:
        logger.error(f"Error updating implementation phase from progress: {e}")
