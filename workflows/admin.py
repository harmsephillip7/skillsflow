"""
SOP (Standard Operating Procedures) Admin Configuration
"""
from django.contrib import admin
from .models import (
    SOPCategory, SOP, SOPStep, Task,
    ProcessFlow, ProcessStage, ProcessStageTransition, TransitionAttemptLog
)


# =====================================================
# SOP ADMIN
# =====================================================

class SOPStepInline(admin.TabularInline):
    model = SOPStep
    extra = 0
    ordering = ['order']
    fields = ['order', 'title', 'app_url_name', 'app_url_label', 'responsible_role', 'is_optional']


@admin.register(SOPCategory)
class SOPCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'color', 'sort_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'description']
    ordering = ['sort_order', 'name']


@admin.register(SOP)
class SOPAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'version', 'is_published', 'created_at']
    list_filter = ['category', 'is_published']
    search_fields = ['name', 'code', 'description', 'purpose']
    date_hierarchy = 'created_at'
    inlines = [SOPStepInline]
    
    fieldsets = (
        (None, {
            'fields': ('category', 'name', 'code', 'description', 'purpose')
        }),
        ('Metadata', {
            'fields': ('owner', 'version', 'effective_date', 'estimated_duration', 'icon')
        }),
        ('Status', {
            'fields': ('is_published',)
        }),
    )


@admin.register(SOPStep)
class SOPStepAdmin(admin.ModelAdmin):
    list_display = ['sop', 'order', 'title', 'app_url_name', 'responsible_role', 'is_optional']
    list_filter = ['sop__category', 'is_optional']
    search_fields = ['title', 'description', 'app_url_name']
    ordering = ['sop', 'order']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'assigned_to', 'status', 'priority', 'due_date', 'created_at']
    list_filter = ['status', 'priority']
    search_fields = ['name', 'description', 'assigned_to__email']
    date_hierarchy = 'created_at'
    raw_id_fields = ['assigned_to', 'created_by', 'sop', 'sop_step']


# =====================================================
# PROCESS FLOW ADMIN
# =====================================================

class ProcessStageInline(admin.TabularInline):
    model = ProcessStage
    extra = 0
    ordering = ['sequence_order']
    fields = ['code', 'name', 'stage_type', 'sequence_order', 'color', 'icon', 'requires_reason_on_entry']


class ProcessStageTransitionInline(admin.TabularInline):
    model = ProcessStageTransition
    extra = 0
    fk_name = 'process_flow'
    fields = ['from_stage', 'to_stage', 'is_allowed', 'requires_reason', 'requires_approval']
    autocomplete_fields = ['from_stage', 'to_stage']


@admin.register(ProcessFlow)
class ProcessFlowAdmin(admin.ModelAdmin):
    list_display = ['name', 'entity_type', 'version', 'is_active', 'created_at']
    list_filter = ['entity_type', 'is_active']
    search_fields = ['name', 'description']
    inlines = [ProcessStageInline]
    
    fieldsets = (
        (None, {
            'fields': ('entity_type', 'name', 'description')
        }),
        ('Version Control', {
            'fields': ('version', 'is_active')
        }),
    )


@admin.register(ProcessStage)
class ProcessStageAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'process_flow', 'stage_type', 'sequence_order', 'color']
    list_filter = ['process_flow', 'stage_type']
    search_fields = ['name', 'code', 'description']
    ordering = ['process_flow', 'sequence_order']
    
    def get_search_results(self, request, queryset, search_term):
        """Enable autocomplete for inline admin"""
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct


@admin.register(ProcessStageTransition)
class ProcessStageTransitionAdmin(admin.ModelAdmin):
    list_display = ['process_flow', 'from_stage', 'to_stage', 'is_allowed', 'requires_reason', 'requires_approval']
    list_filter = ['process_flow', 'is_allowed', 'requires_reason', 'requires_approval']
    autocomplete_fields = ['process_flow', 'from_stage', 'to_stage']


@admin.register(TransitionAttemptLog)
class TransitionAttemptLogAdmin(admin.ModelAdmin):
    list_display = ['entity_type', 'entity_id', 'from_stage', 'to_stage', 'was_allowed', 'was_blocked', 'attempted_by', 'attempted_at']
    list_filter = ['entity_type', 'was_allowed', 'was_blocked', 'attempted_at']
    search_fields = ['entity_id', 'from_stage', 'to_stage', 'block_reason']
    date_hierarchy = 'attempted_at'
    readonly_fields = ['process_flow', 'entity_type', 'entity_id', 'from_stage', 'to_stage', 
                       'was_allowed', 'was_blocked', 'block_reason', 'attempted_by', 
                       'attempted_at', 'ip_address', 'reason_provided']
