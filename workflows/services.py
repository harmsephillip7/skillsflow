"""
SOP (Standard Operating Procedures) Services

Business logic for managing tasks and process flow transitions.
"""
from datetime import date, timedelta
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.utils import timezone

from .models import Task


class TaskService:
    """Service for managing tasks."""
    
    @classmethod
    def create_task(
        cls,
        title: str,
        assigned_to=None,
        assigned_role: str = '',
        due_days: int = 7,
        description: str = '',
        priority: str = 'medium',
        sop=None,
        sop_step=None,
        entity_type: str = '',
        entity_id: int = None,
        user=None
    ) -> Task:
        """Create a new task."""
        due_date = date.today() + timedelta(days=due_days)
        
        return Task.objects.create(
            sop=sop,
            sop_step=sop_step,
            name=title,
            description=description,
            assigned_to=assigned_to,
            assigned_role=assigned_role,
            priority=priority,
            due_date=due_date,
            related_entity_type=entity_type,
            related_entity_id=entity_id,
            created_by=user
        )
    
    @classmethod
    def complete_task(cls, task: Task, user=None, notes: str = '') -> Task:
        """Mark a task as complete."""
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.completed_by = user
        if notes:
            task.notes = notes
        task.save()
        return task
    
    @classmethod
    def get_user_tasks(cls, user, status: str = None) -> List[Task]:
        """Get tasks assigned to a user."""
        queryset = Task.objects.filter(assigned_to=user)
        if status:
            queryset = queryset.filter(status=status)
        return list(queryset.order_by('-priority', 'due_date'))
    
    @classmethod
    def get_overdue_tasks(cls) -> List[Task]:
        """Get all overdue tasks."""
        return list(
            Task.objects.filter(
                status__in=['pending', 'in_progress'],
                due_date__lt=date.today()
            ).order_by('due_date')
        )
    
    @classmethod
    def update_overdue_status(cls):
        """Update status of overdue tasks."""
        Task.objects.filter(
            status__in=['pending', 'in_progress'],
            due_date__lt=date.today()
        ).update(status='overdue')


# =====================================================
# TRANSITION SERVICE
# =====================================================

class TransitionService:
    """
    Service for managing status transitions with business rule enforcement.
    Validates transitions against ProcessFlow configuration and logs attempts.
    """
    
    @classmethod
    def get_process_flow(cls, entity_type: str):
        """Get the ProcessFlow for an entity type"""
        from .models import ProcessFlow
        return ProcessFlow.objects.filter(
            entity_type=entity_type,
            is_active=True
        ).prefetch_related('stages', 'transitions').first()
    
    @classmethod
    def get_allowed_transitions(cls, entity_type: str, from_stage_code: str) -> List[Dict]:
        """
        Get all allowed transitions from a given stage.
        Returns list of dicts with stage info for UI dropdown.
        """
        from .models import ProcessStageTransition
        
        process_flow = cls.get_process_flow(entity_type)
        if not process_flow:
            # No process flow defined - allow all transitions (legacy behavior)
            return None
        
        transitions = ProcessStageTransition.objects.filter(
            process_flow=process_flow,
            from_stage__code=from_stage_code,
            is_allowed=True
        ).select_related('to_stage').order_by('to_stage__sequence_order')
        
        return [
            {
                'code': t.to_stage.code,
                'name': t.to_stage.name,
                'color': t.to_stage.color,
                'requires_reason': t.requires_reason or t.to_stage.requires_reason_on_entry,
                'requires_approval': t.requires_approval,
            }
            for t in transitions
        ]
    
    @classmethod
    def can_transition(cls, entity_type: str, from_stage_code: str, to_stage_code: str) -> bool:
        """Check if a transition is allowed (simple boolean)"""
        process_flow = cls.get_process_flow(entity_type)
        if not process_flow:
            # No process flow defined - allow all transitions
            return True
        
        return process_flow.can_transition(from_stage_code, to_stage_code)
    
    @classmethod
    def validate_and_log_transition(
        cls,
        entity_type: str,
        entity_id: int,
        instance,
        from_stage_code: str,
        to_stage_code: str,
        user=None,
        reason: str = '',
        ip_address: str = None
    ) -> tuple:
        """
        Validate a transition and log the attempt.
        Returns (is_valid, error_message, transition_object)
        """
        from .models import ProcessFlow, ProcessStageTransition, TransitionAttemptLog
        
        process_flow = cls.get_process_flow(entity_type)
        
        # If no process flow is configured, allow all transitions (legacy behavior)
        if not process_flow:
            return True, None, None
        
        # Find the transition rule
        transition = process_flow.get_transition(from_stage_code, to_stage_code)
        
        # Log the attempt
        log_entry = TransitionAttemptLog(
            process_flow=process_flow,
            entity_type=entity_type,
            entity_id=entity_id,
            from_stage=from_stage_code,
            to_stage=to_stage_code,
            attempted_by=user,
            ip_address=ip_address,
            reason_provided=reason
        )
        
        # Check if transition exists and is allowed
        if not transition:
            log_entry.was_allowed = False
            log_entry.was_blocked = True
            log_entry.block_reason = f"No transition rule defined from {from_stage_code} to {to_stage_code}"
            log_entry.save()
            return False, f"Transition from {from_stage_code} to {to_stage_code} is not configured", None
        
        if not transition.is_allowed:
            log_entry.was_allowed = False
            log_entry.was_blocked = True
            log_entry.block_reason = "Transition is explicitly blocked in process flow configuration"
            log_entry.save()
            return False, f"Transition from {from_stage_code} to {to_stage_code} is not allowed", None
        
        # Validate using transition's validation rules
        is_valid, error_message = transition.validate_transition(instance)
        
        if not is_valid:
            log_entry.was_allowed = False
            log_entry.was_blocked = True
            log_entry.block_reason = error_message
            log_entry.save()
            return False, error_message, transition
        
        # Check if reason is required but not provided
        if (transition.requires_reason or 
            (transition.to_stage and transition.to_stage.requires_reason_on_entry)):
            if not reason.strip():
                log_entry.was_allowed = False
                log_entry.was_blocked = True
                log_entry.block_reason = "Reason is required for this transition"
                log_entry.save()
                return False, "Please provide a reason for this status change", transition
        
        # Transition is valid
        log_entry.was_allowed = True
        log_entry.was_blocked = False
        log_entry.save()
        
        return True, None, transition
    
    @classmethod
    def get_stage_info(cls, entity_type: str, stage_code: str) -> Optional[Dict]:
        """Get information about a specific stage"""
        process_flow = cls.get_process_flow(entity_type)
        if not process_flow:
            return None
        
        stage = process_flow.get_stage(stage_code)
        if not stage:
            return None
        
        return {
            'code': stage.code,
            'name': stage.name,
            'description': stage.description,
            'color': stage.color,
            'icon': stage.icon,
            'stage_type': stage.stage_type,
            'sequence_order': stage.sequence_order,
        }
    
    @classmethod
    def get_blocked_attempts(cls, entity_type: str = None, days: int = 30) -> List:
        """Get blocked transition attempts for analysis"""
        from .models import TransitionAttemptLog
        
        cutoff = timezone.now() - timedelta(days=days)
        qs = TransitionAttemptLog.objects.filter(
            was_blocked=True,
            attempted_at__gte=cutoff
        ).select_related('attempted_by', 'process_flow')
        
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        
        return qs.order_by('-attempted_at')
