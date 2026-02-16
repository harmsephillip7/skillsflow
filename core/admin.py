"""Core app admin configuration"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Role, UserRole, AuditLog, SystemConfiguration, FacilitatorProfile,
    TrancheSchedule, TrancheEvidenceRequirement, TrancheEvidence, TrancheSubmission, TrancheComment,
    AccessRequest, AccessRequestSection, AccessRequestSectionChoice,
    TrainingNotification, NOTQualificationStipendRate,
    NOTDeliverableEvidenceRequirement, NOTDeliverableEvidence,
    RequiredDocumentConfig
)
from .not_automation import NOTTaskTemplate

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['email']
    list_display = ['email', 'first_name', 'last_name', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),
    )

admin.site.register(Role)
admin.site.register(UserRole)
admin.site.register(AuditLog)
admin.site.register(SystemConfiguration)
admin.site.register(RequiredDocumentConfig)


@admin.register(FacilitatorProfile)
class FacilitatorProfileAdmin(admin.ModelAdmin):
    """Admin for managing facilitator campus assignments"""
    list_display = ['user', 'primary_campus', 'employee_number', 'campus_count']
    list_filter = ['primary_campus', 'campuses']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'employee_number']
    filter_horizontal = ['campuses']
    autocomplete_fields = ['user', 'primary_campus']
    
    fieldsets = (
        ('Facilitator', {
            'fields': ('user', 'employee_number')
        }),
        ('Campus Assignment', {
            'fields': ('campuses', 'primary_campus'),
            'description': 'Assign this facilitator to multiple campuses. The primary campus is used for reporting and as the default filter.'
        }),
        ('Details', {
            'fields': ('specializations',),
            'classes': ('collapse',)
        }),
    )
    
    def campus_count(self, obj):
        return obj.campuses.count()
    campus_count.short_description = 'Campuses'


# Tranche Management Admin
class TrancheEvidenceRequirementInline(admin.TabularInline):
    model = TrancheEvidenceRequirement
    extra = 1
    fields = ['name', 'evidence_type', 'is_mandatory', 'expected_count']


class TrancheSubmissionInline(admin.TabularInline):
    model = TrancheSubmission
    extra = 0
    fields = ['submission_date', 'submission_method', 'status', 'submitted_by']
    readonly_fields = ['submitted_by']


class TrancheCommentInline(admin.TabularInline):
    model = TrancheComment
    extra = 0
    fields = ['comment_type', 'comment', 'created_by', 'created_at']
    readonly_fields = ['created_by', 'created_at']


@admin.register(TrancheSchedule)
class TrancheScheduleAdmin(admin.ModelAdmin):
    list_display = ['reference_number', 'training_notification', 'tranche_type', 'name', 'due_date', 'amount', 'status', 'priority']
    list_filter = ['status', 'tranche_type', 'priority']
    search_fields = ['reference_number', 'name', 'training_notification__title', 'training_notification__reference_number']
    date_hierarchy = 'due_date'
    ordering = ['due_date']
    inlines = [TrancheEvidenceRequirementInline, TrancheSubmissionInline, TrancheCommentInline]
    
    fieldsets = (
        (None, {
            'fields': ('training_notification', 'reference_number', 'name', 'description')
        }),
        ('Schedule', {
            'fields': ('sequence_number', 'tranche_type', 'due_date', 'status', 'priority')
        }),
        ('Financial', {
            'fields': ('amount', 'actual_amount_received', 'invoice', 'payment_received_date')
        }),
        ('Learner Tracking', {
            'fields': ('learner_count_target', 'learner_count_actual')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['reference_number']


@admin.register(TrancheEvidenceRequirement)
class TrancheEvidenceRequirementAdmin(admin.ModelAdmin):
    list_display = ['name', 'tranche', 'evidence_type', 'is_mandatory', 'expected_count', 'deadline']
    list_filter = ['evidence_type', 'is_mandatory', 'requires_verification']
    search_fields = ['name', 'tranche__reference_number', 'tranche__training_notification__title']
    ordering = ['tranche', 'evidence_type']


@admin.register(TrancheEvidence)
class TrancheEvidenceAdmin(admin.ModelAdmin):
    list_display = ['title', 'requirement', 'status', 'verified_by', 'verified_at']
    list_filter = ['status', 'verified_at']
    search_fields = ['title', 'requirement__tranche__reference_number', 'description']
    date_hierarchy = 'created_at'


@admin.register(NOTDeliverableEvidenceRequirement)
class NOTDeliverableEvidenceRequirementAdmin(admin.ModelAdmin):
    """Admin for QC templates - defining what evidence is required per deliverable type"""
    list_display = ['name', 'deliverable_type', 'is_mandatory', 'order']
    list_filter = ['deliverable_type', 'is_mandatory']
    search_fields = ['name', 'description', 'acceptance_criteria']
    ordering = ['deliverable_type', 'order', 'name']
    list_editable = ['order', 'is_mandatory']


@admin.register(NOTDeliverableEvidence)
class NOTDeliverableEvidenceAdmin(admin.ModelAdmin):
    """Admin for deliverable evidence files"""
    list_display = ['title', 'deliverable', 'original_filename', 'status', 'verified_by', 'verified_at']
    list_filter = ['status', 'deliverable__deliverable_type', 'verified_at']
    search_fields = ['title', 'original_filename', 'deliverable__title', 'deliverable__training_notification__reference_number']
    date_hierarchy = 'created_at'
    readonly_fields = ['original_filename', 'file_size', 'created_at', 'created_by']
    raw_id_fields = ['deliverable', 'verified_by', 'requirement']


@admin.register(TrancheSubmission)
class TrancheSubmissionAdmin(admin.ModelAdmin):
    list_display = ['tranche', 'submission_date', 'submission_method', 'status', 'submitted_by', 'qc_checklist_completed']
    list_filter = ['status', 'submission_method', 'qc_checklist_completed', 'submission_date']
    search_fields = ['tranche__reference_number', 'notes']
    date_hierarchy = 'submission_date'
    
    fieldsets = (
        ('Submission Details', {
            'fields': ('tranche', 'submission_date', 'submission_method', 'submitted_by')
        }),
        ('Status', {
            'fields': ('status', 'funder_response_date', 'funder_reference', 'funder_notes')
        }),
        ('Quality Control', {
            'fields': ('qc_checklist_completed', 'qc_completed_by', 'qc_completed_date', 'qc_notes')
        }),
        ('Payment', {
            'fields': ('claimed_amount', 'approved_amount', 'payment_date', 'payment_reference', 'payment_amount'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['submitted_by', 'qc_completed_by', 'qc_completed_date']


@admin.register(TrancheComment)
class TrancheCommentAdmin(admin.ModelAdmin):
    list_display = ['tranche', 'comment_type', 'comment', 'created_by', 'created_at']
    list_filter = ['comment_type', 'created_at']
    search_fields = ['tranche__reference_number', 'comment']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_by', 'created_at']


# =====================================================
# NOT AUTOMATION ADMIN
# =====================================================

@admin.register(NOTTaskTemplate)
class NOTTaskTemplateAdmin(admin.ModelAdmin):
    """Admin for managing NOT task automation templates"""
    list_display = [
        'name', 'trigger_status', 'assigned_role', 'task_category', 
        'task_priority', 'due_days_offset', 'sequence', 'is_active'
    ]
    list_filter = ['trigger_status', 'task_category', 'task_priority', 'assigned_role', 'is_active']
    search_fields = ['name', 'task_title_template', 'task_description_template']
    ordering = ['trigger_status', 'sequence']
    
    fieldsets = (
        ('Trigger Conditions', {
            'fields': ('trigger_status', 'project_type', 'funder_type', 'is_active')
        }),
        ('Task Details', {
            'fields': ('name', 'task_title_template', 'task_description_template', 'task_category', 'task_priority')
        }),
        ('Assignment', {
            'fields': ('assigned_role', 'fallback_campus_role')
        }),
        ('Timing', {
            'fields': ('due_days_offset', 'sequence')
        }),
    )
    
    list_editable = ['is_active', 'sequence']


# ==============================================
# ACCESS REQUEST ADMIN
# ==============================================
class AccessRequestSectionChoiceInline(admin.TabularInline):
    model = AccessRequestSectionChoice
    extra = 0


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ['email', 'full_name', 'status', 'requested_brand', 'requested_at', 'reviewed_by', 'reviewed_at']
    list_filter = ['status', 'requested_brand', 'requested_campus', 'email_verified']
    search_fields = ['email', 'first_name', 'last_name', 'employee_number']
    date_hierarchy = 'requested_at'
    ordering = ['-requested_at']
    readonly_fields = ['password_hash', 'verification_token', 'created_user', 'requested_at']
    filter_horizontal = ['requested_roles', 'approved_roles']
    inlines = [AccessRequestSectionChoiceInline]
    
    fieldsets = (
        ('Applicant', {
            'fields': ('email', 'first_name', 'last_name', 'phone', 'password_hash')
        }),
        ('Employment', {
            'fields': ('employee_number', 'job_title', 'department')
        }),
        ('Organization', {
            'fields': ('requested_brand', 'requested_campus')
        }),
        ('Requested Access', {
            'fields': ('requested_roles', 'access_justification')
        }),
        ('Status', {
            'fields': ('status', 'requested_at', 'expires_at', 'email_verified', 'verification_token')
        }),
        ('Review', {
            'fields': ('reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Approved', {
            'fields': ('approved_roles', 'approved_brand', 'approved_campus', 'created_user')
        }),
    )


@admin.register(AccessRequestSection)
class AccessRequestSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'order', 'is_active']
    list_filter = ['is_active', 'min_access_level']
    search_fields = ['name', 'code']
    ordering = ['order', 'name']
    filter_horizontal = ['default_roles']


# NOT Stipend Configuration Admin

class NOTQualificationStipendRateInline(admin.TabularInline):
    """Inline for managing qualification-specific stipend rates"""
    model = NOTQualificationStipendRate
    extra = 1
    fields = ['qualification', 'year_level', 'daily_rate', 'effective_from_month', 
              'effective_to_month', 'auto_escalate', 'escalation_percentage']
    autocomplete_fields = ['qualification']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('qualification')


@admin.register(TrainingNotification)
class TrainingNotificationAdmin(admin.ModelAdmin):
    """Admin for Training Notification with stipend configuration"""
    list_display = ['reference_number', 'title', 'project_type', 'status', 'has_stipend', 
                   'stipend_daily_rate', 'expected_learner_count', 'planned_start_date']
    list_filter = ['status', 'project_type', 'funder', 'has_stipend', 'priority']
    search_fields = ['reference_number', 'title', 'client_name', 'description']
    date_hierarchy = 'planned_start_date'
    readonly_fields = ['reference_number']
    inlines = [NOTQualificationStipendRateInline]
    autocomplete_fields = ['corporate_client', 'qualification', 'delivery_campus', 
                          'approved_by', 'cohort']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('reference_number', 'title', 'project_type', 'funder', 
                      'description', 'status', 'priority')
        }),
        ('Client/Funding', {
            'fields': ('client_name', 'corporate_client', 'tender_reference', 'contract_value')
        }),
        ('Program Details', {
            'fields': ('qualification', 'program_description')
        }),
        ('Learner Information', {
            'fields': ('expected_learner_count', 'learner_source', 'recruitment_notes')
        }),
        ('Timeline', {
            'fields': (
                'planned_start_date', 'planned_end_date', 'duration_months',
                'actual_start_date', 'actual_end_date'
            )
        }),
        ('Location & Delivery', {
            'fields': ('delivery_campus', 'delivery_mode', 'delivery_address')
        }),
        ('Stipend Configuration', {
            'fields': (
                'has_stipend', 'stipend_daily_rate', 'stipend_frequency',
                'stipend_start_month', 'stipend_escalation_percentage', 'stipend_notes'
            ),
            'description': 'Configure default stipend settings. Use the Qualification Stipend Rates section below to set specific rates per qualification or year level.',
            'classes': ('collapse',)
        }),
        ('Planning Meeting', {
            'fields': (
                'planning_meeting_date', 'planning_meeting_venue',
                'planning_meeting_notes', 'planning_meeting_completed'
            ),
            'classes': ('collapse',)
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_date', 'approval_notes', 'notifications_sent_date'),
            'classes': ('collapse',)
        }),
        ('Related Project', {
            'fields': ('cohort',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['enable_stipends', 'disable_stipends', 'apply_standard_escalation']
    
    def enable_stipends(self, request, queryset):
        """Enable stipends for selected NOTs"""
        updated = queryset.update(has_stipend=True)
        self.message_user(request, f"Enabled stipends for {updated} project(s).")
    enable_stipends.short_description = "Enable stipends for selected NOTs"
    
    def disable_stipends(self, request, queryset):
        """Disable stipends for selected NOTs"""
        updated = queryset.update(has_stipend=False)
        self.message_user(request, f"Disabled stipends for {updated} project(s).")
    disable_stipends.short_description = "Disable stipends for selected NOTs"
    
    def apply_standard_escalation(self, request, queryset):
        """Apply standard 6% escalation to selected NOTs"""
        from decimal import Decimal
        updated = queryset.update(stipend_escalation_percentage=Decimal('6.00'))
        self.message_user(request, f"Applied 6% escalation to {updated} project(s).")
    apply_standard_escalation.short_description = "Apply 6% escalation to selected NOTs"


@admin.register(NOTQualificationStipendRate)
class NOTQualificationStipendRateAdmin(admin.ModelAdmin):
    """Admin for qualification-specific stipend rates"""
    list_display = ['training_notification', 'qualification', 'year_level', 'daily_rate',
                   'effective_from_month', 'effective_to_month', 'auto_escalate']
    list_filter = ['auto_escalate', 'year_level', 'training_notification__status']
    search_fields = ['training_notification__reference_number', 'training_notification__title',
                    'qualification__short_title', 'qualification__title']
    autocomplete_fields = ['training_notification', 'qualification']
    
    fieldsets = (
        ('Project & Qualification', {
            'fields': ('training_notification', 'qualification', 'year_level')
        }),
        ('Rate Configuration', {
            'fields': ('daily_rate', 'effective_from_month', 'effective_to_month')
        }),
        ('Escalation', {
            'fields': ('auto_escalate', 'escalation_percentage'),
            'description': 'Auto-escalation will apply the specified percentage annually.'
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['enable_escalation', 'disable_escalation']
    
    def enable_escalation(self, request, queryset):
        """Enable auto-escalation for selected rates"""
        updated = queryset.update(auto_escalate=True)
        self.message_user(request, f"Enabled auto-escalation for {updated} rate(s).")
    enable_escalation.short_description = "Enable auto-escalation"
    
    def disable_escalation(self, request, queryset):
        """Disable auto-escalation for selected rates"""
        updated = queryset.update(auto_escalate=False)
        self.message_user(request, f"Disabled auto-escalation for {updated} rate(s).")
    disable_escalation.short_description = "Disable auto-escalation"


# NOT Document Management Admin
from .models_not_documents import NOTLearnerDocumentType, NOTLearnerDocument, NOTProjectDocument


@admin.register(NOTLearnerDocumentType)
class NOTLearnerDocumentTypeAdmin(admin.ModelAdmin):
    """Admin for configuring learner document types"""
    list_display = ['name', 'code', 'category', 'is_required', 'has_expiry', 'is_active']
    list_filter = ['category', 'is_required', 'has_expiry', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering = ['category', 'order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'category', 'description', 'order')
        }),
        ('Requirements', {
            'fields': ('is_required', 'required_for_project_types', 'required_for_funders')
        }),
        ('Expiry Configuration', {
            'fields': ('has_expiry', 'default_validity_days', 'expiry_warning_days')
        }),
        ('File Settings', {
            'fields': ('accepted_file_types', 'max_file_size_mb')
        }),
        ('Status', {
            'fields': ('is_active', 'archived_at')
        }),
    )
    
    actions = ['archive_types', 'restore_types']
    
    def archive_types(self, request, queryset):
        for doc_type in queryset:
            doc_type.archive()
        self.message_user(request, f"Archived {queryset.count()} document type(s).")
    archive_types.short_description = "Archive selected document types"
    
    def restore_types(self, request, queryset):
        for doc_type in queryset:
            doc_type.restore()
        self.message_user(request, f"Restored {queryset.count()} document type(s).")
    restore_types.short_description = "Restore selected document types"


@admin.register(NOTLearnerDocument)
class NOTLearnerDocumentAdmin(admin.ModelAdmin):
    """Admin for managing learner documents"""
    list_display = ['learner', 'document_type', 'training_notification', 'status', 'expiry_date', 'is_expiring_display']
    list_filter = ['status', 'document_type', 'training_notification']
    search_fields = ['learner__user__first_name', 'learner__user__last_name', 'learner__user__email',
                    'training_notification__reference_number', 'reference_number']
    autocomplete_fields = ['training_notification', 'learner', 'document_type', 'verified_by']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Document', {
            'fields': ('training_notification', 'learner', 'document_type')
        }),
        ('File', {
            'fields': ('file', 'original_filename', 'file_size')
        }),
        ('Status', {
            'fields': ('status', 'reference_number', 'issue_date', 'expiry_date', 'notes')
        }),
        ('Verification', {
            'fields': ('verified_by', 'verified_at', 'verification_notes', 'rejection_reason')
        }),
        ('Expiry Tracking', {
            'fields': ('expiry_warning_sent', 'expiry_warning_sent_at', 'expiry_task_created'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['original_filename', 'file_size', 'verified_at', 'expiry_warning_sent_at']
    
    def is_expiring_display(self, obj):
        if obj.is_expired:
            return '⚠️ Expired'
        elif obj.is_expiring_soon:
            return f'⏰ {obj.days_until_expiry} days'
        return '✓'
    is_expiring_display.short_description = 'Expiry Status'


@admin.register(NOTProjectDocument)
class NOTProjectDocumentAdmin(admin.ModelAdmin):
    """Admin for managing project-level documents"""
    list_display = ['title', 'training_notification', 'document_type', 'status', 'version', 'created_at']
    list_filter = ['document_type', 'status', 'training_notification']
    search_fields = ['title', 'training_notification__reference_number', 'reference_number']
    autocomplete_fields = ['training_notification', 'reviewed_by', 'supersedes']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Document', {
            'fields': ('training_notification', 'document_type', 'title', 'description')
        }),
        ('File', {
            'fields': ('file', 'original_filename', 'file_size')
        }),
        ('Details', {
            'fields': ('reference_number', 'issue_date', 'expiry_date', 'status')
        }),
        ('Review', {
            'fields': ('reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Versioning', {
            'fields': ('version', 'supersedes')
        }),
    )
    
    readonly_fields = ['original_filename', 'file_size', 'reviewed_at', 'version']


# =====================================================
# DIGITAL SIGNATURE ADMIN
# =====================================================

from .models import SignatureCapture

@admin.register(SignatureCapture)
class SignatureCaptureAdmin(admin.ModelAdmin):
    """Admin for managing digital signatures with unlock capability"""
    list_display = ['user', 'captured_at', 'is_locked', 'popia_consent_given', 'ip_address']
    list_filter = ['is_locked', 'popia_consent_given', 'captured_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'ip_address']
    readonly_fields = [
        'user', 'signature_image', 'signature_hash', 'captured_at', 'ip_address', 
        'user_agent', 'popia_consent_text', 'popia_consent_given', 'popia_consent_at',
        'unlocked_by', 'unlocked_at', 'unlock_reason'
    ]
    date_hierarchy = 'captured_at'
    
    fieldsets = (
        ('Signature', {
            'fields': ('user', 'signature_image', 'signature_hash')
        }),
        ('Capture Details', {
            'fields': ('captured_at', 'ip_address', 'user_agent')
        }),
        ('POPIA Consent', {
            'fields': ('popia_consent_given', 'popia_consent_at', 'popia_consent_text'),
        }),
        ('Lock Status', {
            'fields': ('is_locked', 'unlocked_by', 'unlocked_at', 'unlock_reason'),
        }),
    )
    
    actions = ['unlock_signatures']
    
    @admin.action(description='Unlock selected signatures (requires reason)')
    def unlock_signatures(self, request, queryset):
        """Admin action to unlock signatures for re-capture"""
        from django.contrib import messages as admin_messages
        from core.services.signature_service import SignatureService
        
        # Get unlock reason from POST data or use default
        unlock_reason = request.POST.get('unlock_reason', 'Admin unlock via Django admin')
        
        service = SignatureService()
        unlocked_count = 0
        
        for signature in queryset.filter(is_locked=True):
            signature.unlock(request.user, unlock_reason)
            unlocked_count += 1
            
            # Also unlock the associated profile signature
            user = signature.user
            # Check learner
            if hasattr(user, 'learner_profile') and user.learner_profile:
                user.learner_profile.signature_locked = False
                user.learner_profile.save(update_fields=['signature_locked'])
            # Check facilitator
            if hasattr(user, 'facilitator_profile') and user.facilitator_profile:
                user.facilitator_profile.signature_locked = False
                user.facilitator_profile.save(update_fields=['signature_locked'])
            # Check mentor
            if hasattr(user, 'mentor_profile') and user.mentor_profile:
                user.mentor_profile.signature_locked = False
                user.mentor_profile.save(update_fields=['signature_locked'])
            # Check workplace officer
            if hasattr(user, 'workplace_officer_profile') and user.workplace_officer_profile:
                user.workplace_officer_profile.signature_locked = False
                user.workplace_officer_profile.save(update_fields=['signature_locked'])
        
        admin_messages.success(
            request, 
            f'Successfully unlocked {unlocked_count} signature(s). Users can now provide new signatures.'
        )
    
    def has_add_permission(self, request):
        # Signatures should be captured through the portal, not added via admin
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete signatures
        return request.user.is_superuser


# =============================================================================
# Training Class & Facilitator Assignment Admin
# =============================================================================

from .models import TrainingClass, LearnerClassAssignment, ExternalModerationRequest


class LearnerClassAssignmentInline(admin.TabularInline):
    """Inline for viewing learners assigned to a class"""
    model = LearnerClassAssignment
    fk_name = 'training_class'  # Specify which FK to use
    extra = 0
    fields = ['enrollment', 'assigned_from', 'is_active', 'transfer_reason']
    readonly_fields = ['assigned_from']
    autocomplete_fields = ['enrollment']


@admin.register(TrainingClass)
class TrainingClassAdmin(admin.ModelAdmin):
    """Admin for Training Classes"""
    list_display = [
        'name', 'training_notification', 'facilitator', 
        'enrolled_count', 'max_capacity', 'available_capacity', 'is_active'
    ]
    list_filter = ['is_active', 'training_notification__status']
    search_fields = [
        'name', 
        'training_notification__reference_number',
        'facilitator__user__first_name',
        'facilitator__user__last_name'
    ]
    autocomplete_fields = ['training_notification', 'facilitator']  # Removed intake
    raw_id_fields = ['intake']  # Use raw_id instead of autocomplete
    inlines = [LearnerClassAssignmentInline]
    
    fieldsets = (
        (None, {
            'fields': ('training_notification', 'intake', 'name', 'group_number')
        }),
        ('Facilitator', {
            'fields': ('facilitator',)
        }),
        ('Capacity', {
            'fields': ('max_capacity',)
        }),
        ('Schedule', {
            'fields': ('schedule_notes',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    actions = ['auto_create_classes']
    
    def enrolled_count(self, obj):
        return obj.enrolled_count
    enrolled_count.short_description = 'Enrolled'
    
    def available_capacity(self, obj):
        return obj.available_capacity
    available_capacity.short_description = 'Available'
    
    def auto_create_classes(self, request, queryset):
        """Auto-create classes for selected NOTs"""
        from django.contrib import messages as admin_messages
        total_created = 0
        for training_class in queryset:
            # This doesn't quite work - we'd want to call it on TrainingNotification
            pass
        admin_messages.success(request, f'Use auto_create_classes method on TrainingNotification model instead.')
    auto_create_classes.short_description = "Auto-create classes (see model method)"


@admin.register(LearnerClassAssignment)
class LearnerClassAssignmentAdmin(admin.ModelAdmin):
    """Admin for Learner Class Assignments"""
    list_display = [
        'enrollment', 'training_class', 'facilitator_name',
        'assigned_from', 'is_active'
    ]
    list_filter = ['is_active', 'training_class__training_notification']
    search_fields = [
        'enrollment__learner__first_name',
        'enrollment__learner__last_name',
        'training_class__name'
    ]
    autocomplete_fields = ['enrollment', 'training_class', 'previous_class']
    date_hierarchy = 'assigned_from'
    
    fieldsets = (
        (None, {
            'fields': ('enrollment', 'training_class')
        }),
        ('Assignment Period', {
            'fields': ('assigned_from', 'assigned_until', 'is_active')
        }),
        ('Transfer Info', {
            'fields': ('previous_class', 'transfer_reason'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def facilitator_name(self, obj):
        return obj.facilitator_name
    facilitator_name.short_description = 'Facilitator'


# =============================================================================
# External Moderation Request Admin
# =============================================================================

@admin.register(ExternalModerationRequest)
class ExternalModerationRequestAdmin(admin.ModelAdmin):
    """Admin for External Moderation Requests"""
    list_display = [
        'reference_number', 'training_notification', 'etqa_name',
        'status', 'result', 'days_waiting', 'scheduled_date', 'is_overdue'
    ]
    list_filter = ['status', 'result', 'etqa_name']
    search_fields = [
        'reference_number',
        'title',
        'training_notification__reference_number',
        'etqa_name',
        'etqa_contact_name'
    ]
    autocomplete_fields = ['training_notification', 'assigned_to']  # Removed deliverable
    raw_id_fields = ['deliverable']  # Use raw_id instead
    filter_horizontal = ['learners_for_moderation']
    date_hierarchy = 'created_at'
    readonly_fields = ['reference_number', 'days_waiting']
    
    fieldsets = (
        ('Request Info', {
            'fields': ('reference_number', 'training_notification', 'deliverable', 'title')
        }),
        ('ETQA Contact', {
            'fields': ('etqa_name', 'etqa_contact_name', 'etqa_contact_email', 'etqa_contact_phone')
        }),
        ('Learner Selection', {
            'fields': ('learners_for_moderation', 'sample_size'),
            'description': 'Select learners to be included in the moderation sample'
        }),
        ('Status & Workflow', {
            'fields': ('status', 'assigned_to')
        }),
        ('Key Dates', {
            'fields': ('ready_date', 'one_month_reminder_sent', 'submitted_date', 'scheduled_date', 'completed_date')
        }),
        ('Request Documents', {
            'fields': ('request_document', 'request_notes'),
            'classes': ('collapse',)
        }),
        ('ETQA Response', {
            'fields': ('response_document', 'response_notes', 'response_date'),
            'classes': ('collapse',)
        }),
        ('Result', {
            'fields': ('result', 'result_document', 'result_notes')
        }),
        ('Tracking', {
            'fields': ('days_waiting', 'escalation_notes'),
            'classes': ('collapse',)
        }),
    )
    
    def is_overdue(self, obj):
        return '⚠️ Yes' if obj.is_overdue else 'No'
    is_overdue.short_description = 'Overdue?'
    
    actions = ['mark_submitted', 'mark_completed']
    
    def mark_submitted(self, request, queryset):
        from django.utils import timezone
        from datetime import date
        updated = queryset.filter(status='READY').update(
            status='SUBMITTED',
            submitted_date=date.today()
        )
        self.message_user(request, f'{updated} request(s) marked as submitted.')
    mark_submitted.short_description = "Mark selected as submitted to ETQA"
    
    def mark_completed(self, request, queryset):
        from datetime import date
        updated = queryset.filter(status__in=['SUBMITTED', 'ACKNOWLEDGED', 'SCHEDULED', 'IN_PROGRESS']).update(
            status='COMPLETED',
            completed_date=date.today()
        )
        self.message_user(request, f'{updated} request(s) marked as completed.')
    mark_completed.short_description = "Mark selected as completed"


# =====================================================
# PROJECT TEMPLATE SYSTEM ADMIN
# =====================================================

from .project_templates import (
    ProjectTemplateSet,
    ProjectTaskTemplate,
    NOTScheduledTask,
    NOTTemplateSetApplication
)


class ProjectTaskTemplateInline(admin.TabularInline):
    model = ProjectTaskTemplate
    extra = 1
    fields = ['name', 'trigger_type', 'trigger_status', 'task_title_template', 'assigned_role', 'sequence', 'is_active']
    ordering = ['trigger_type', 'sequence']


@admin.register(ProjectTemplateSet)
class ProjectTemplateSetAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent_set', 'auto_apply', 'is_active', 'version', 'template_count']
    list_filter = ['is_active', 'auto_apply']
    search_fields = ['name', 'description']
    ordering = ['name']
    inlines = [ProjectTaskTemplateInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'description', 'parent_set')
        }),
        ('Applicability Filters', {
            'fields': ('project_types', 'funder_types', 'qualification_types'),
            'description': 'Leave empty to apply to all. Use JSON arrays like ["SETA", "CORPORATE"]'
        }),
        ('Duration Filters', {
            'fields': ('min_duration_months', 'max_duration_months'),
        }),
        ('Settings', {
            'fields': ('auto_apply', 'is_active', 'version'),
        }),
    )
    readonly_fields = ['version']
    
    def template_count(self, obj):
        return obj.templates.filter(is_active=True).count()
    template_count.short_description = 'Active Templates'


@admin.register(ProjectTaskTemplate)
class ProjectTaskTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_set', 'trigger_type', 'trigger_status', 'assigned_role', 'sequence', 'is_active']
    list_filter = ['template_set', 'trigger_type', 'trigger_status', 'assigned_role', 'is_active']
    search_fields = ['name', 'task_title_template', 'template_set__name']
    ordering = ['template_set', 'trigger_type', 'sequence']
    
    fieldsets = (
        ('Template Info', {
            'fields': ('template_set', 'name', 'sequence', 'is_active')
        }),
        ('Trigger Configuration', {
            'fields': ('trigger_type', 'trigger_status', 'date_reference', 'offset_days'),
            'description': 'For status triggers: use trigger_status. For date triggers: use date_reference and offset_days.'
        }),
        ('Recurring Configuration', {
            'fields': ('recurring_interval', 'recurring_start_status', 'recurring_end_status'),
            'classes': ('collapse',),
            'description': 'Only for recurring trigger type.'
        }),
        ('Task Details', {
            'fields': ('task_title_template', 'task_description_template', 'task_category', 'task_priority', 'operational_category')
        }),
        ('Assignment', {
            'fields': ('assigned_role', 'fallback_campus_role', 'due_days_offset')
        }),
        ('Recalculation', {
            'fields': ('recalculate_on_date_change',)
        }),
    )


@admin.register(NOTScheduledTask)
class NOTScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ['training_notification', 'task', 'template', 'original_due_date', 'recalculated_count', 'created_at']
    list_filter = ['auto_generated', 'created_at']
    search_fields = ['training_notification__reference_number', 'task__title']
    date_hierarchy = 'created_at'
    readonly_fields = ['training_notification', 'template', 'task', 'original_due_date', 'trigger_date', 'recurrence_number', 'auto_generated', 'recalculated_count', 'last_recalculated', 'created_at']


@admin.register(NOTTemplateSetApplication)
class NOTTemplateSetApplicationAdmin(admin.ModelAdmin):
    list_display = ['training_notification', 'template_set', 'applied_version', 'applied_at', 'update_notification_sent']
    list_filter = ['template_set', 'update_notification_sent', 'applied_at']
    search_fields = ['training_notification__reference_number', 'template_set__name']
    readonly_fields = ['applied_at']
