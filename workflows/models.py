"""
SOP (Standard Operating Procedures) and Process Flow Models

This module provides:
1. SOP system - Step-by-step procedures with links to app locations
2. ProcessFlow system - Business process validation for entity status transitions
"""
from django.db import models
from django.conf import settings
from django.urls import reverse, NoReverseMatch
from core.models import AuditedModel


# =====================================================
# SOP (STANDARD OPERATING PROCEDURES) MODELS
# =====================================================

class SOPCategory(AuditedModel):
    """Categories for organizing SOPs (e.g., Training, Finance, HR)"""
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, default='folder')
    color = models.CharField(max_length=20, blank=True, default='gray')
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "SOP Category"
        verbose_name_plural = "SOP Categories"
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_active_sops(self):
        """Return all published SOPs in this category"""
        return self.sops.filter(is_published=True)


class SOP(AuditedModel):
    """Standard Operating Procedure - defines a business process with steps"""
    category = models.ForeignKey(
        SOPCategory, on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='sops'
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    purpose = models.TextField(blank=True, help_text="Why this SOP exists and when to use it")
    owner = models.CharField(
        max_length=100, blank=True,
        help_text="Department or role responsible for maintaining this SOP"
    )
    version = models.CharField(max_length=20, default='1.0')
    effective_date = models.DateField(null=True, blank=True)
    
    # Status
    is_published = models.BooleanField(default=False)
    
    # Visual
    icon = models.CharField(max_length=50, blank=True, default='document-text')
    estimated_duration = models.CharField(max_length=50, blank=True, help_text="e.g., '15 minutes', '1 hour'")
    
    class Meta:
        verbose_name = "SOP"
        verbose_name_plural = "SOPs"
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.code}: {self.name}"
    
    def get_steps(self):
        """Return all steps in order"""
        return self.steps.all().order_by('order')
    
    def get_absolute_url(self):
        return reverse('workflows:sop_detail', kwargs={'code': self.code})


class SOPStep(AuditedModel):
    """Individual step within an SOP with optional link to app location"""
    sop = models.ForeignKey(SOP, on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, help_text="Detailed instructions for this step")
    
    # App navigation - Django URL name (e.g., 'core:enrollment_list')
    app_url_name = models.CharField(
        max_length=200, blank=True,
        help_text="Django URL name to link to, e.g., 'core:enrollment_list'"
    )
    app_url_label = models.CharField(
        max_length=100, blank=True,
        help_text="Button text, e.g., 'Go to Enrollments'"
    )
    
    # Alternative: External URL
    external_url = models.URLField(blank=True, help_text="External link if not an app location")
    
    # Step metadata
    responsible_role = models.CharField(max_length=100, blank=True, help_text="e.g., 'Admin', 'Finance'")
    tips = models.TextField(blank=True, help_text="Pro tips or common mistakes to avoid")
    
    # Flags
    is_optional = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "SOP Step"
        verbose_name_plural = "SOP Steps"
        ordering = ['sop', 'order']
    
    def __str__(self):
        return f"{self.sop.code} Step {self.order}: {self.title}"
    
    def get_app_url(self):
        """Resolve the Django URL name to an actual URL"""
        if not self.app_url_name:
            return None
        try:
            return reverse(self.app_url_name)
        except NoReverseMatch:
            return None
    
    def get_link(self):
        """Return the appropriate link (app URL or external)"""
        if self.app_url_name:
            return self.get_app_url()
        elif self.external_url:
            return self.external_url
        return None
    
    def get_link_label(self):
        """Return the appropriate link label"""
        if self.app_url_name:
            return self.app_url_label or "Go to Step"
        elif self.external_url:
            return "Open Link"
        return None


class Task(AuditedModel):
    """Individual tasks assigned to users, optionally linked to SOPs"""
    # Optional SOP linkage
    sop = models.ForeignKey(SOP, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    sop_step = models.ForeignKey(SOPStep, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='workflow_assigned_tasks'
    )
    assigned_role = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'), ('in_progress', 'In Progress'),
        ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('overdue', 'Overdue'),
    ], default='pending')
    priority = models.CharField(max_length=20, choices=[
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent'),
    ], default='medium')
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='workflow_completed_tasks'
    )
    related_entity_type = models.CharField(max_length=50, blank=True)
    related_entity_id = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-priority', 'due_date']
        indexes = [
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['status', 'due_date']),
        ]
    
    def __str__(self):
        return self.name


# =====================================================
# BUSINESS PROCESS FLOW MODELS
# =====================================================

class ProcessFlow(AuditedModel):
    """
    Defines a business process flow with configurable stages and transitions.
    Global rules initially, with campus-specific overrides to be added later.
    """
    ENTITY_TYPE_CHOICES = [
        ('enrollment', 'Enrollment'),
        ('learner', 'Learner'),
        ('corporate_client', 'Corporate Client'),
        ('training_notification', 'Training Notification'),
        ('invoice', 'Invoice'),
        ('assessment', 'Assessment'),
        ('poe_submission', 'PoE Submission'),
        ('grant_project', 'Grant Project'),
    ]
    
    name = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=50, choices=ENTITY_TYPE_CHOICES, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    
    # Future: Campus-specific overrides
    # campus = models.ForeignKey('tenants.Campus', null=True, blank=True, on_delete=models.SET_NULL)
    
    class Meta:
        verbose_name = "Process Flow"
        verbose_name_plural = "Process Flows"
        ordering = ['entity_type']
    
    def __str__(self):
        return f"{self.name} (v{self.version})"
    
    def get_stage(self, stage_code):
        """Get a specific stage by code"""
        return self.stages.filter(code=stage_code).first()
    
    def get_allowed_transitions_from(self, from_stage_code):
        """Get all allowed transitions from a given stage"""
        return ProcessStageTransition.objects.filter(
            process_flow=self,
            from_stage__code=from_stage_code,
            is_allowed=True
        ).select_related('to_stage')
    
    def can_transition(self, from_stage_code, to_stage_code):
        """Check if a transition is allowed"""
        return ProcessStageTransition.objects.filter(
            process_flow=self,
            from_stage__code=from_stage_code,
            to_stage__code=to_stage_code,
            is_allowed=True
        ).exists()
    
    def get_transition(self, from_stage_code, to_stage_code):
        """Get transition object if it exists"""
        return ProcessStageTransition.objects.filter(
            process_flow=self,
            from_stage__code=from_stage_code,
            to_stage__code=to_stage_code
        ).first()


class ProcessStage(AuditedModel):
    """
    Defines a stage within a process flow.
    Normalized model for better queryability than JSONField.
    """
    STAGE_TYPE_CHOICES = [
        ('initial', 'Initial Stage'),
        ('intermediate', 'Intermediate Stage'),
        ('terminal_success', 'Terminal (Success)'),
        ('terminal_failure', 'Terminal (Failure)'),
    ]
    
    process_flow = models.ForeignKey(ProcessFlow, on_delete=models.CASCADE, related_name='stages')
    code = models.CharField(max_length=30, help_text="Internal code matching model status field")
    name = models.CharField(max_length=100, help_text="Display name")
    description = models.TextField(blank=True)
    stage_type = models.CharField(max_length=20, choices=STAGE_TYPE_CHOICES, default='intermediate')
    sequence_order = models.PositiveIntegerField(default=0)
    
    # Visual properties
    color = models.CharField(max_length=20, default='gray', help_text="Tailwind color class")
    icon = models.CharField(max_length=50, blank=True, help_text="Icon name")
    
    # Behavior flags
    is_active = models.BooleanField(default=True)
    requires_reason_on_entry = models.BooleanField(default=False, help_text="Require reason when entering this stage")
    auto_tasks = models.JSONField(default=list, blank=True, help_text="Tasks to auto-create when entering stage")
    notifications = models.JSONField(default=list, blank=True, help_text="Notifications to send when entering stage")
    
    class Meta:
        verbose_name = "Process Stage"
        verbose_name_plural = "Process Stages"
        ordering = ['process_flow', 'sequence_order']
        unique_together = ['process_flow', 'code']
    
    def __str__(self):
        return f"{self.process_flow.entity_type}: {self.name}"


class ProcessStageTransition(AuditedModel):
    """
    Defines allowed transitions between stages with validation rules.
    """
    process_flow = models.ForeignKey(ProcessFlow, on_delete=models.CASCADE, related_name='transitions')
    from_stage = models.ForeignKey(ProcessStage, on_delete=models.CASCADE, related_name='outgoing_transitions')
    to_stage = models.ForeignKey(ProcessStage, on_delete=models.CASCADE, related_name='incoming_transitions')
    
    # Transition rules
    is_allowed = models.BooleanField(default=True)
    requires_reason = models.BooleanField(default=False, help_text="Require reason for this transition")
    requires_approval = models.BooleanField(default=False, help_text="Requires approval from supervisor")
    approval_role = models.CharField(max_length=50, blank=True, help_text="Role required for approval")
    
    # Validation rules (JSON for flexibility)
    validation_rules = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Custom validation rules, e.g., {'required_fields': ['certificate_number']}"
    )
    
    # Optional: Conditions for automatic transitions
    auto_transition = models.BooleanField(default=False, help_text="Automatically transition when conditions met")
    auto_transition_conditions = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Stage Transition"
        verbose_name_plural = "Stage Transitions"
        unique_together = ['process_flow', 'from_stage', 'to_stage']
    
    def __str__(self):
        status = "✓" if self.is_allowed else "✗"
        return f"{status} {self.from_stage.code} → {self.to_stage.code}"
    
    def validate_transition(self, instance):
        """
        Validate if a transition is allowed for a given instance.
        Returns (is_valid, error_message)
        """
        if not self.is_allowed:
            return False, f"Transition from {self.from_stage.name} to {self.to_stage.name} is not allowed"
        
        # Check validation rules
        rules = self.validation_rules
        errors = []
        
        # Check required fields
        required_fields = rules.get('required_fields', [])
        for field in required_fields:
            value = getattr(instance, field, None)
            if not value:
                errors.append(f"{field.replace('_', ' ').title()} is required for this transition")
        
        # Check date requirements
        date_checks = rules.get('date_checks', {})
        for field, check in date_checks.items():
            value = getattr(instance, field, None)
            if check == 'must_be_set' and not value:
                errors.append(f"{field.replace('_', ' ').title()} must be set for this transition")
        
        if errors:
            return False, "; ".join(errors)
        
        return True, None


class TransitionAttemptLog(models.Model):
    """
    Audit log for transition attempts, especially blocked ones.
    Helps identify training needs or process issues.
    """
    process_flow = models.ForeignKey(ProcessFlow, on_delete=models.CASCADE, related_name='transition_logs')
    entity_type = models.CharField(max_length=50)
    entity_id = models.PositiveIntegerField()
    from_stage = models.CharField(max_length=30)
    to_stage = models.CharField(max_length=30)
    
    # Result
    was_allowed = models.BooleanField()
    was_blocked = models.BooleanField(default=False)
    block_reason = models.TextField(blank=True)
    
    # Context
    attempted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='transition_attempts'
    )
    attempted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    reason_provided = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Transition Attempt Log"
        verbose_name_plural = "Transition Attempt Logs"
        ordering = ['-attempted_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['was_blocked', 'attempted_at']),
        ]
    
    def __str__(self):
        status = "Allowed" if self.was_allowed else "Blocked"
        return f"{self.entity_type}#{self.entity_id}: {self.from_stage} → {self.to_stage} ({status})"
