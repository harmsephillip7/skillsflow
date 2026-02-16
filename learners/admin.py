"""Learners app admin configuration"""
from django.contrib import admin
from .models import (
    Address, Learner, Document, SETA, Employer, LearnerEmployment,
    WorkplaceAttendance, AttendanceAuditLog, StipendCalculation
)


@admin.register(Learner)
class LearnerAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'sa_id_number', 'email', 'phone_mobile']
    search_fields = ['first_name', 'last_name', 'sa_id_number', 'email', 'phone_mobile']
    list_filter = ['gender', 'population_group', 'disability_status']


@admin.register(SETA)
class SETAAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']


@admin.register(WorkplaceAttendance)
class WorkplaceAttendanceAdmin(admin.ModelAdmin):
    """Admin for workplace attendance records"""
    list_display = ['placement', 'date', 'attendance_type', 'clock_in', 'clock_out', 
                   'hours_worked', 'mentor_verified', 'facilitator_verified', 'is_fully_verified']
    list_filter = ['attendance_type', 'mentor_verified', 'facilitator_verified', 
                  'offline_created', 'sync_status']
    search_fields = ['placement__learner__first_name', 'placement__learner__last_name', 
                    'placement__host_employer__company_name', 'notes']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at', 'mentor_verified_at', 
                      'facilitator_verified_at', 'gps_timestamp', 'is_fully_verified']
    
    fieldsets = (
        ('Placement & Date', {
            'fields': ('placement', 'date')
        }),
        ('Time & Hours', {
            'fields': ('clock_in', 'clock_out', 'hours_worked')
        }),
        ('Attendance Type', {
            'fields': ('attendance_type', 'leave_document', 'notes')
        }),
        ('Mentor Verification', {
            'fields': ('mentor_verified', 'mentor_verified_at', 'mentor_verified_by'),
            'classes': ('collapse',)
        }),
        ('Facilitator Verification', {
            'fields': ('facilitator_verified', 'facilitator_verified_at', 'facilitator_verified_by'),
            'classes': ('collapse',)
        }),
        ('GPS Location', {
            'fields': ('gps_latitude', 'gps_longitude', 'gps_accuracy', 'gps_timestamp'),
            'classes': ('collapse',)
        }),
        ('Photo & Sync', {
            'fields': ('photo', 'offline_created', 'offline_sync_id', 'client_uuid', 'sync_status'),
            'classes': ('collapse',)
        }),
    )
    
    def is_fully_verified(self, obj):
        return obj.is_fully_verified
    is_fully_verified.boolean = True
    is_fully_verified.short_description = 'Fully Verified'


@admin.register(AttendanceAuditLog)
class AttendanceAuditLogAdmin(admin.ModelAdmin):
    """Admin for attendance audit logs"""
    list_display = ['attendance', 'action', 'field_changed', 'changed_by', 
                   'changed_at', 'archived']
    list_filter = ['action', 'archived', 'changed_at']
    search_fields = ['attendance__placement__learner__first_name', 
                    'attendance__placement__learner__last_name',
                    'changed_by__email', 'notes', 'field_changed']
    date_hierarchy = 'changed_at'
    readonly_fields = ['changed_at']
    
    fieldsets = (
        ('Attendance Record', {
            'fields': ('attendance', 'changed_by', 'changed_at')
        }),
        ('Action Details', {
            'fields': ('action', 'field_changed', 'old_value', 'new_value', 'notes')
        }),
        ('GPS Location', {
            'fields': ('action_gps_latitude', 'action_gps_longitude'),
            'classes': ('collapse',)
        }),
        ('Archival', {
            'fields': ('archived',),
            'classes': ('collapse',)
        }),
    )


@admin.register(StipendCalculation)
class StipendCalculationAdmin(admin.ModelAdmin):
    """Admin for stipend calculations"""
    list_display = ['placement', 'period_display', 'status', 'net_amount', 
                   'verification_percentage', 'can_finalize_display', 'approved_by', 'approved_at']
    list_filter = ['status', 'month', 'year', 'calculated_at', 'approved_at']
    search_fields = ['placement__learner__first_name', 'placement__learner__last_name',
                    'placement__host__employer__name']
    date_hierarchy = 'calculated_at'
    readonly_fields = ['calculated_at', 'calculated_by', 'verified_at', 'verified_by',
                      'approved_at', 'approved_by', 'total_deductions', 'paid_days',
                      'verification_percentage', 'can_finalize']
    
    fieldsets = (
        ('Placement & Period', {
            'fields': ('placement', 'month', 'year', 'status')
        }),
        ('Attendance Breakdown', {
            'fields': (
                'days_present', 'days_absent', 'days_annual_leave', 'days_sick_leave',
                'days_family_leave', 'days_unpaid_leave', 'days_public_holiday', 
                'days_suspended', 'paid_days'
            )
        }),
        ('Financial Calculation', {
            'fields': ('daily_rate', 'gross_amount', 'deductions', 'total_deductions', 'net_amount')
        }),
        ('Verification Progress', {
            'fields': (
                'total_attendance_records', 'dual_verified_records', 
                'mentor_verified_only', 'facilitator_verified_only', 
                'unverified_records', 'verification_percentage', 'can_finalize'
            ),
            'description': 'These fields track the verification status of attendance records for this period.'
        }),
        ('Workflow', {
            'fields': (
                'calculated_at', 'calculated_by',
                'verified_at', 'verified_by', 'verification_notes',
                'approved_at', 'approved_by'
            ),
            'classes': ('collapse',)
        }),
        ('Payment Tracking', {
            'fields': ('payment_reference', 'payment_date'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['update_verification_stats', 'mark_as_approved']
    
    def verification_percentage(self, obj):
        return f"{obj.verification_percentage}%"
    verification_percentage.short_description = 'Verification %'
    
    def can_finalize_display(self, obj):
        return obj.can_finalize
    can_finalize_display.boolean = True
    can_finalize_display.short_description = 'Can Finalize'
    
    def update_verification_stats(self, request, queryset):
        """Update verification statistics for selected stipends"""
        count = 0
        for stipend in queryset:
            stipend.update_verification_stats()
            count += 1
        self.message_user(request, f"Updated verification stats for {count} stipend(s).")
    update_verification_stats.short_description = "Update verification statistics"
    
    def mark_as_approved(self, request, queryset):
        """Mark selected stipends as approved (only if fully verified)"""
        from django.utils import timezone
        approved_count = 0
        blocked_count = 0
        
        for stipend in queryset:
            stipend.update_verification_stats()
            if stipend.can_finalize:
                stipend.status = 'APPROVED'
                stipend.approved_by = request.user
                stipend.approved_at = timezone.now()
                stipend.save()
                approved_count += 1
            else:
                blocked_count += 1
        
        if approved_count:
            self.message_user(request, f"Approved {approved_count} stipend(s).")
        if blocked_count:
            self.message_user(
                request, 
                f"Blocked {blocked_count} stipend(s) - attendance not fully verified.",
                level='WARNING'
            )
    mark_as_approved.short_description = "Approve selected stipends (if fully verified)"


admin.site.register(Address)
admin.site.register(Document)
admin.site.register(Employer)
admin.site.register(LearnerEmployment)


# =============================================================================
# Daily Logbook Admin
# =============================================================================

from .models import DailyLogbookEntry, DailyTaskCompletion


class DailyTaskCompletionInline(admin.TabularInline):
    """Inline for daily task completions"""
    model = DailyTaskCompletion
    extra = 1
    fields = ['workplace_outcome', 'module_code', 'task_description', 'hours_spent', 'competency_rating']
    autocomplete_fields = ['workplace_outcome']


@admin.register(DailyLogbookEntry)
class DailyLogbookEntryAdmin(admin.ModelAdmin):
    """Admin for Daily Logbook Entries"""
    list_display = [
        'entry_date', 'placement', 'attendance_status', 
        'clock_in', 'clock_out', 'hours_worked_display', 'tasks_count',
        'learner_signed', 'mentor_signed'
    ]
    list_filter = ['attendance_status', 'learner_signed', 'mentor_signed', 'entry_date']
    search_fields = [
        'placement__learner__first_name',
        'placement__learner__last_name',
        'daily_summary'
    ]
    date_hierarchy = 'entry_date'
    inlines = [DailyTaskCompletionInline]
    autocomplete_fields = ['placement', 'mentor_signed_by']
    
    fieldsets = (
        ('Entry Info', {
            'fields': ('placement', 'entry_date')
        }),
        ('Attendance', {
            'fields': ('attendance_status', 'clock_in', 'clock_out', 'break_minutes')
        }),
        ('Daily Summary', {
            'fields': ('daily_summary', 'challenges_faced', 'lessons_learned')
        }),
        ('Mentor Feedback', {
            'fields': ('mentor_feedback',),
            'classes': ('collapse',)
        }),
        ('Sign-off', {
            'fields': (
                ('learner_signed', 'learner_signed_at'),
                ('mentor_signed', 'mentor_signed_at', 'mentor_signed_by')
            )
        }),
    )
    
    def hours_worked_display(self, obj):
        return f"{obj.hours_worked:.1f}h" if obj.hours_worked else '-'
    hours_worked_display.short_description = 'Hours'
    
    def tasks_count(self, obj):
        return obj.tasks_count
    tasks_count.short_description = 'Tasks'


@admin.register(DailyTaskCompletion)
class DailyTaskCompletionAdmin(admin.ModelAdmin):
    """Admin for Daily Task Completions"""
    list_display = [
        'daily_entry', 'outcome_code', 'module_code', 
        'task_description_short', 'hours_spent', 'competency_rating'
    ]
    list_filter = ['competency_rating', 'daily_entry__entry_date']
    search_fields = [
        'task_description',
        'daily_entry__placement__learner__first_name',
        'daily_entry__placement__learner__last_name',
        'module_code'
    ]
    autocomplete_fields = ['daily_entry', 'workplace_outcome']
    
    fieldsets = (
        ('Entry', {
            'fields': ('daily_entry',)
        }),
        ('Task', {
            'fields': ('workplace_outcome', 'module_code', 'task_description', 'hours_spent')
        }),
        ('Assessment', {
            'fields': ('competency_rating', 'evidence_notes', 'evidence_file')
        }),
    )
    
    def task_description_short(self, obj):
        return obj.task_description[:50] + '...' if len(obj.task_description) > 50 else obj.task_description
    task_description_short.short_description = 'Task'

