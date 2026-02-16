"""Academics app admin configuration"""
from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from .models import (
    Qualification, Module, UnitStandard, ModuleUnitStandard, 
    Enrollment, EnrollmentStatusHistory,
    AccreditationChecklistItem, AccreditationChecklistProgress,
    ComplianceDocument, AccreditationAlert,
    PersonnelRegistration, QualificationCampusAccreditation,
    LearningMaterial, LearnerModuleProgress,
    QCTOSyncLog, QCTOQualificationChange,
    QualificationPricing,
)


# Define inline first so it can be referenced by QualificationAdmin
class QualificationCampusAccreditationInline(admin.TabularInline):
    """Inline for managing campus accreditations within Qualification admin"""
    model = QualificationCampusAccreditation
    extra = 0
    fields = ['campus', 'letter_reference', 'letter_date', 'accredited_from', 'accredited_until', 'status', 'learner_capacity', 'is_active']
    readonly_fields = []
    ordering = ['campus', '-accredited_until']
    
    def get_queryset(self, request):
        # Update expired statuses when loading
        QualificationCampusAccreditation.objects.update_expired_statuses()
        return super().get_queryset(request)


class QualificationPricingInline(admin.TabularInline):
    """Inline for managing pricing history within Qualification admin"""
    model = QualificationPricing
    extra = 0
    fields = ['academic_year', 'effective_from', 'effective_to', 'total_price', 'registration_fee', 'tuition_fee', 'materials_fee', 'is_active']
    ordering = ['-academic_year', '-effective_from']


@admin.register(Qualification)
class QualificationAdmin(admin.ModelAdmin):
    list_display = ['saqa_id', 'title', 'nqf_level', 'credits', 'seta', 'is_active']
    list_filter = ['nqf_level', 'seta', 'is_active']
    search_fields = ['saqa_id', 'title', 'short_title']
    ordering = ['saqa_id']
    inlines = [QualificationCampusAccreditationInline, QualificationPricingInline]


@admin.register(QualificationPricing)
class QualificationPricingAdmin(admin.ModelAdmin):
    """Admin for managing qualification pricing with history"""
    list_display = ['qualification', 'academic_year', 'total_price', 'effective_from', 'effective_to', 'is_current', 'is_active']
    list_filter = ['academic_year', 'is_active', 'qualification__seta']
    search_fields = ['qualification__title', 'qualification__saqa_id']
    ordering = ['-academic_year', '-effective_from']
    date_hierarchy = 'effective_from'
    raw_id_fields = ['qualification']
    
    fieldsets = (
        (None, {
            'fields': ('qualification', 'academic_year', 'is_active')
        }),
        ('Effective Dates', {
            'fields': ('effective_from', 'effective_to'),
            'description': 'Leave effective_to blank for current pricing'
        }),
        ('Pricing', {
            'fields': ('total_price',),
            'description': 'Total all-inclusive price shown to learners'
        }),
        ('Internal Breakdown (for accounting)', {
            'fields': ('registration_fee', 'tuition_fee', 'materials_fee'),
            'classes': ('collapse',),
            'description': 'Internal breakdown - not shown on quotes'
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'qualification', 'module_type', 'year_level', 'component_phase', 'credits', 'sequence_order', 'is_active']
    list_filter = ['qualification', 'module_type', 'year_level', 'component_phase', 'is_compulsory', 'is_active']
    search_fields = ['code', 'title', 'qualification__title']
    ordering = ['qualification', 'year_level', 'sequence_order']
    list_editable = ['year_level', 'sequence_order']
    
    fieldsets = (
        (None, {
            'fields': ('qualification', 'code', 'title', 'description')
        }),
        ('Classification', {
            'fields': ('module_type', 'credits', 'notional_hours')
        }),
        ('QCTO Structure', {
            'fields': ('year_level', 'component_phase'),
            'description': 'component_phase is auto-set based on module_type (K/P = Institutional, W = Workplace)'
        }),
        ('Ordering', {
            'fields': ('sequence_order', 'is_compulsory', 'prerequisites')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


@admin.register(UnitStandard)
class UnitStandardAdmin(admin.ModelAdmin):
    list_display = ['saqa_id', 'title', 'nqf_level', 'credits', 'is_active']
    list_filter = ['nqf_level', 'is_active']
    search_fields = ['saqa_id', 'title']


@admin.register(ModuleUnitStandard)
class ModuleUnitStandardAdmin(admin.ModelAdmin):
    list_display = ['module', 'unit_standard']
    list_filter = ['module__qualification']
    search_fields = ['module__code', 'unit_standard__saqa_id']


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['enrollment_number', 'learner', 'qualification', 'status', 'application_date', 'funding_type']
    list_filter = ['status', 'funding_type', 'qualification', 'cohort']
    search_fields = ['enrollment_number', 'learner__user__first_name', 'learner__user__last_name', 'learner__id_number']
    date_hierarchy = 'application_date'
    raw_id_fields = ['learner', 'qualification', 'cohort']


@admin.register(EnrollmentStatusHistory)
class EnrollmentStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['enrollment', 'from_status', 'to_status', 'changed_by', 'changed_at']
    list_filter = ['to_status']
    search_fields = ['enrollment__enrollment_number']
    date_hierarchy = 'changed_at'


@admin.register(LearnerModuleProgress)
class LearnerModuleProgressAdmin(admin.ModelAdmin):
    list_display = [
        'enrollment', 'module', 'overall_status', 'formative_status', 
        'summative_status', 'is_manually_overridden', 'updated_at'
    ]
    list_filter = [
        'overall_status', 'formative_status', 'summative_status', 
        'is_manually_overridden', 'module__year_level', 'module__component_phase'
    ]
    search_fields = [
        'enrollment__enrollment_number', 'enrollment__learner__user__first_name',
        'enrollment__learner__user__last_name', 'module__code', 'module__title'
    ]
    raw_id_fields = ['enrollment', 'module', 'overridden_by']
    readonly_fields = ['formative_competent_count', 'formative_total_count', 
                       'summative_competent_count', 'summative_total_count',
                       'overridden_at', 'formative_completed_at', 'summative_completed_at',
                       'overall_completed_at']
    
    fieldsets = (
        (None, {
            'fields': ('enrollment', 'module')
        }),
        ('Formative Assessment Progress', {
            'fields': ('formative_status', 'formative_competent_count', 
                       'formative_total_count', 'formative_completed_at')
        }),
        ('Summative Assessment Progress', {
            'fields': ('summative_status', 'summative_competent_count', 
                       'summative_total_count', 'summative_completed_at')
        }),
        ('Overall Status', {
            'fields': ('overall_status', 'overall_completed_at', 'notes')
        }),
        ('Manual Override', {
            'fields': ('is_manually_overridden', 'override_reason', 
                       'overridden_by', 'overridden_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['recalculate_progress', 'clear_overrides']
    
    @admin.action(description='Recalculate progress (skip overridden)')
    def recalculate_progress(self, request, queryset):
        count = 0
        for progress in queryset.filter(is_manually_overridden=False):
            progress.calculate_progress(save=True)
            count += 1
        self.message_user(request, f'Recalculated progress for {count} records')
    
    @admin.action(description='Clear manual overrides and recalculate')
    def clear_overrides(self, request, queryset):
        count = 0
        for progress in queryset.filter(is_manually_overridden=True):
            progress.clear_manual_override()
            count += 1
        self.message_user(request, f'Cleared {count} overrides')


@admin.register(AccreditationChecklistItem)
class AccreditationChecklistItemAdmin(admin.ModelAdmin):
    list_display = ['qualification', 'title', 'category', 'is_required', 'sequence_order']
    list_filter = ['qualification', 'category', 'is_required']
    search_fields = ['title', 'qualification__title']


@admin.register(AccreditationChecklistProgress)
class AccreditationChecklistProgressAdmin(admin.ModelAdmin):
    list_display = ['checklist_item', 'completed', 'completed_by', 'completed_at']
    list_filter = ['completed', 'checklist_item__qualification']


@admin.register(ComplianceDocument)
class ComplianceDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'document_type', 'campus', 'expiry_date', 'issue_date']
    list_filter = ['document_type', 'campus']
    search_fields = ['title']


@admin.register(AccreditationAlert)
class AccreditationAlertAdmin(admin.ModelAdmin):
    list_display = ['qualification', 'compliance_document', 'alert_type', 'alert_date', 'acknowledged', 'resolved']
    list_filter = ['alert_type', 'acknowledged', 'resolved']
    search_fields = ['qualification__title', 'compliance_document__title']


@admin.register(PersonnelRegistration)
class PersonnelRegistrationAdmin(admin.ModelAdmin):
    list_display = ['user', 'personnel_type', 'registration_number', 'seta', 'expiry_date', 'is_active']
    list_filter = ['personnel_type', 'is_active', 'seta']
    search_fields = ['user__first_name', 'user__last_name', 'registration_number']
    filter_horizontal = ['qualifications']


@admin.register(QualificationCampusAccreditation)
class QualificationCampusAccreditationAdmin(admin.ModelAdmin):
    list_display = ['qualification', 'campus', 'letter_reference', 'accredited_from', 'accredited_until', 'status', 'is_expiring_soon_display', 'is_active']
    list_filter = ['status', 'is_active', 'campus', 'qualification']
    search_fields = ['qualification__title', 'qualification__saqa_id', 'campus__name', 'letter_reference']
    date_hierarchy = 'accredited_until'
    ordering = ['qualification', 'campus', '-accredited_until']
    
    fieldsets = (
        ('Qualification & Campus', {
            'fields': ('qualification', 'campus')
        }),
        ('Accreditation Letter Details', {
            'fields': ('letter_reference', 'letter_date', 'accreditation_document')
        }),
        ('Accreditation Period', {
            'fields': ('accredited_from', 'accredited_until', 'learner_capacity')
        }),
        ('Status', {
            'fields': ('status', 'is_active', 'notes')
        }),
    )
    
    def is_expiring_soon_display(self, obj):
        """Display warning if expiring within 6 months"""
        if obj.is_expiring_soon:
            return '⚠️ Expiring Soon'
        elif obj.status == 'EXPIRED':
            return '🔴 Expired'
        elif obj.status == 'SUPERSEDED':
            return '🔵 Superseded'
        return '✅ OK'
    is_expiring_soon_display.short_description = 'Status'
    
    def get_queryset(self, request):
        # Update expired statuses when loading the admin list
        QualificationCampusAccreditation.objects.update_expired_statuses()
        return super().get_queryset(request)


@admin.register(LearningMaterial)
class LearningMaterialAdmin(admin.ModelAdmin):
    list_display = ['qualification', 'material_type', 'title', 'version', 'is_current', 'approved']
    list_filter = ['material_type', 'is_current', 'approved', 'qualification']
    search_fields = ['title', 'qualification__title']


@admin.register(QCTOSyncLog)
class QCTOSyncLogAdmin(admin.ModelAdmin):
    """Admin for QCTO sync logs with manual trigger action"""
    list_display = ['synced_at', 'trigger_type', 'status', 'qualifications_checked', 
                    'qualifications_updated', 'triggered_by', 'duration_display']
    list_filter = ['status', 'trigger_type']
    search_fields = ['triggered_by__first_name', 'triggered_by__last_name']
    date_hierarchy = 'synced_at'
    readonly_fields = ['synced_at', 'trigger_type', 'triggered_by', 'status',
                       'qualifications_checked', 'qualifications_updated', 
                       'changes_detected', 'error_message', 'started_at', 
                       'completed_at']
    
    actions = ['trigger_manual_sync']
    
    def duration_display(self, obj):
        """Display sync duration"""
        if obj.duration_seconds:
            return f"{obj.duration_seconds:.1f}s"
        return "-"
    duration_display.short_description = "Duration"
    
    def has_add_permission(self, request):
        # Prevent manual addition - syncs should be created via action or cron
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Allow deleting old sync logs
        return True
    
    @admin.action(description='🔄 Trigger manual QCTO sync (max 2/month)')
    def trigger_manual_sync(self, request, queryset):
        """Trigger a manual QCTO sync (max 2 per month)"""
        # Check if manual sync is allowed
        if not QCTOSyncLog.can_trigger_manual_sync():
            remaining = 2 - QCTOSyncLog.get_manual_sync_count_this_month()
            self.message_user(
                request,
                f"Manual sync limit reached. You have {remaining}/2 manual syncs remaining this month. Wait for the 15th scheduled sync.",
                level=messages.ERROR
            )
            return
        
        # Create sync log
        sync_log = QCTOSyncLog.objects.create(
            trigger_type='MANUAL',
            triggered_by=request.user,
            status='PENDING'
        )
        
        # Run sync (in production, you'd want to use Celery or similar for async)
        try:
            from academics.services.qcto_sync import QCTOScraper
            scraper = QCTOScraper()
            
            sync_log.status = 'RUNNING'
            sync_log.started_at = timezone.now()
            sync_log.save()
            
            # Sync all active qualifications
            qualifications = Qualification.objects.filter(is_active=True)
            total_checked = 0
            total_changes = 0
            
            for qual in qualifications:
                total_checked += 1
                qcto_data = scraper.fetch_qualification_details(qual.saqa_id)
                
                if qcto_data:
                    # Check for changes (simplified - full implementation in sync_qcto command)
                    changes = []
                    field_mapping = {'title': 'title', 'nqf_level': 'nqf_level', 'credits': 'credits'}
                    
                    for model_field, qcto_field in field_mapping.items():
                        if qcto_field in qcto_data:
                            current = getattr(qual, model_field)
                            new_val = qcto_data[qcto_field]
                            if str(current) != str(new_val):
                                QCTOQualificationChange.objects.create(
                                    sync_log=sync_log,
                                    qualification=qual,
                                    field_name=model_field,
                                    old_value=str(current),
                                    new_value=str(new_val),
                                    status='PENDING'
                                )
                                total_changes += 1
            
            sync_log.qualifications_checked = total_checked
            sync_log.qualifications_updated = total_changes
            sync_log.status = 'COMPLETED'
            sync_log.completed_at = timezone.now()
            sync_log.save()
            
            remaining = 2 - QCTOSyncLog.get_manual_sync_count_this_month()
            self.message_user(
                request,
                f"✅ QCTO sync completed! Checked {total_checked} qualifications, found {total_changes} changes. {remaining}/2 manual syncs remaining this month.",
                level=messages.SUCCESS
            )
            
        except Exception as e:
            sync_log.status = 'FAILED'
            sync_log.error_message = str(e)
            sync_log.completed_at = timezone.now()
            sync_log.save()
            
            self.message_user(
                request,
                f"❌ QCTO sync failed: {str(e)}",
                level=messages.ERROR
            )


@admin.register(QCTOQualificationChange)
class QCTOQualificationChangeAdmin(admin.ModelAdmin):
    """Admin for reviewing QCTO detected changes"""
    list_display = ['qualification', 'field_name', 'old_value_truncated', 
                    'new_value_truncated', 'status', 'sync_log', 'created_at']
    list_filter = ['status', 'field_name', 'sync_log']
    search_fields = ['qualification__saqa_id', 'qualification__title']
    readonly_fields = ['sync_log', 'qualification', 'field_name', 'old_value', 
                       'new_value', 'created_at']
    list_editable = ['status']
    
    actions = ['mark_acknowledged', 'mark_applied', 'mark_dismissed']
    
    def old_value_truncated(self, obj):
        """Truncate old value for display"""
        if len(obj.old_value) > 50:
            return obj.old_value[:50] + "..."
        return obj.old_value
    old_value_truncated.short_description = "Old Value"
    
    def new_value_truncated(self, obj):
        """Truncate new value for display"""
        if len(obj.new_value) > 50:
            return obj.new_value[:50] + "..."
        return obj.new_value
    new_value_truncated.short_description = "New Value"
    
    @admin.action(description='✅ Mark as Acknowledged')
    def mark_acknowledged(self, request, queryset):
        count = queryset.update(
            status='ACKNOWLEDGED',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f'{count} change(s) marked as acknowledged.')
    
    @admin.action(description='🔄 Mark as Applied to System')
    def mark_applied(self, request, queryset):
        count = queryset.update(
            status='APPLIED',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f'{count} change(s) marked as applied.')
    
    @admin.action(description='❌ Dismiss changes')
    def mark_dismissed(self, request, queryset):
        count = queryset.update(
            status='DISMISSED',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f'{count} change(s) dismissed.')


# =============================================================================
# Workplace Module Outcome Admin
# =============================================================================

from .models import WorkplaceModuleOutcome


@admin.register(WorkplaceModuleOutcome)
class WorkplaceModuleOutcomeAdmin(admin.ModelAdmin):
    """Admin for SAQA Workplace Module Outcomes"""
    list_display = [
        'outcome_code', 'title_short', 'module', 'outcome_number',
        'estimated_hours', 'is_active'
    ]
    list_filter = ['module__qualification', 'module', 'outcome_group', 'is_active']
    search_fields = [
        'outcome_code', 'title', 'description',
        'module__code', 'module__title'
    ]
    ordering = ['module', 'outcome_number']
    list_editable = ['outcome_number', 'is_active']
    autocomplete_fields = ['module']
    
    fieldsets = (
        ('Outcome Info', {
            'fields': ('module', 'outcome_code', 'outcome_number', 'title')
        }),
        ('Details', {
            'fields': ('description', 'range_statement', 'assessment_criteria')
        }),
        ('Classification', {
            'fields': ('estimated_hours', 'outcome_group')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Import Tracking', {
            'fields': ('saqa_source', 'imported_at'),
            'classes': ('collapse',)
        }),
    )
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'


# =============================================================================
# Standard Block Admin
# =============================================================================

from .models import StandardBlock, StandardBlockModule, ImplementationPlanBlock


class StandardBlockModuleInline(admin.TabularInline):
    model = StandardBlockModule
    extra = 1
    fields = ['module', 'sequence', 'classroom_sessions', 'practical_sessions', 'total_days']
    ordering = ['sequence']
    autocomplete_fields = ['module']


@admin.register(StandardBlock)
class StandardBlockAdmin(admin.ModelAdmin):
    """Admin for reusable standard blocks for implementation plans"""
    list_display = [
        'code', 'name', 'block_type', 'duration_weeks', 
        'total_training_days', 'status', 'module_count'
    ]
    list_filter = ['block_type', 'status']
    search_fields = ['code', 'name', 'description']
    ordering = ['block_type', 'code']
    inlines = [StandardBlockModuleInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('code', 'name', 'description', 'block_type', 'status', 'version')
        }),
        ('Duration', {
            'fields': ('duration_weeks',)
        }),
        ('Applicability', {
            'fields': ('applicable_qualification_types',),
            'description': 'Leave empty to apply to all qualification types. Use JSON array like ["OC", "NC"]'
        }),
        ('Institutional Settings', {
            'fields': ('contact_days_per_week', 'hours_per_day', 'classroom_hours_per_day', 'practical_hours_per_day'),
            'classes': ('collapse',),
            'description': 'Only relevant for INSTITUTIONAL blocks'
        }),
        ('Workplace Settings', {
            'fields': ('workplace_days_per_week', 'workplace_hours_per_day'),
            'classes': ('collapse',),
            'description': 'Only relevant for WORKPLACE blocks'
        }),
        ('Display', {
            'fields': ('color',),
            'classes': ('collapse',)
        }),
    )
    
    def module_count(self, obj):
        return obj.modules.count()
    module_count.short_description = 'Modules'


@admin.register(StandardBlockModule)
class StandardBlockModuleAdmin(admin.ModelAdmin):
    """Admin for modules within standard blocks"""
    list_display = ['block', 'module', 'sequence', 'classroom_sessions', 'practical_sessions', 'total_days']
    list_filter = ['block']
    search_fields = ['block__code', 'block__name', 'module__code', 'module__title']
    ordering = ['block', 'sequence']
    autocomplete_fields = ['block', 'module']


@admin.register(ImplementationPlanBlock)
class ImplementationPlanBlockAdmin(admin.ModelAdmin):
    """Admin for blocks used in implementation plans"""
    list_display = ['implementation_plan', 'standard_block', 'sequence', 'year_level', 'effective_name', 'generated_phase']
    list_filter = ['implementation_plan__qualification', 'standard_block', 'year_level']
    search_fields = ['implementation_plan__name', 'standard_block__code', 'custom_name']
    ordering = ['implementation_plan', 'sequence']
    autocomplete_fields = ['standard_block']
    raw_id_fields = ['implementation_plan']
    
    fieldsets = (
        ('Assignment', {
            'fields': ('implementation_plan', 'standard_block', 'sequence', 'year_level')
        }),
        ('Customization', {
            'fields': ('custom_name', 'custom_duration_weeks'),
            'description': 'Override standard block settings for this specific usage'
        }),
        ('Generated Phase', {
            'fields': ('generated_phase',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['generated_phase']
