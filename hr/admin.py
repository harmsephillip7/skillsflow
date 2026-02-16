from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Department, Position, PositionTask, StaffProfile,
    StaffPositionHistory, StaffTaskAssignment, PerformanceReview
)


class PositionTaskInline(admin.TabularInline):
    """Inline admin for position tasks"""
    model = PositionTask
    extra = 1
    fields = ['title', 'priority', 'weight', 'frequency', 'sort_order', 'is_active']
    ordering = ['sort_order', '-priority']


class StaffPositionHistoryInline(admin.TabularInline):
    """Inline admin for staff position history"""
    model = StaffPositionHistory
    extra = 0
    fields = ['position', 'department', 'start_date', 'end_date', 'change_reason', 'salary_at_time']
    readonly_fields = ['start_date', 'end_date', 'change_reason']
    ordering = ['-start_date']
    can_delete = False


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin for Department model"""
    list_display = ['code', 'name', 'parent', 'head', 'is_active', 'staff_count']
    list_filter = ['is_active', 'parent']
    search_fields = ['code', 'name', 'description']
    ordering = ['sort_order', 'name']
    autocomplete_fields = ['parent', 'head']
    
    fieldsets = (
        (None, {
            'fields': ('code', 'name', 'description')
        }),
        ('Hierarchy', {
            'fields': ('parent', 'head', 'sort_order')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def staff_count(self, obj):
        """Get count of staff in department"""
        return obj.staff_members.filter(is_deleted=False).count()
    staff_count.short_description = 'Staff Count'


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    """Admin for Position model"""
    list_display = ['code', 'title', 'department', 'salary_band', 'salary_range', 'is_active', 'staff_count']
    list_filter = ['is_active', 'salary_band', 'department']
    search_fields = ['code', 'title', 'job_description_text']
    ordering = ['department__name', 'title']
    autocomplete_fields = ['department', 'reports_to']
    inlines = [PositionTaskInline]
    
    fieldsets = (
        (None, {
            'fields': ('code', 'title', 'department', 'reports_to')
        }),
        ('Job Description', {
            'fields': ('job_description', 'job_description_text')
        }),
        ('Requirements', {
            'fields': ('minimum_qualifications', 'preferred_qualifications', 'experience_required')
        }),
        ('Compensation', {
            'fields': ('salary_band', 'salary_min', 'salary_max')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def salary_range(self, obj):
        """Display formatted salary range"""
        return obj.get_salary_range_display()
    salary_range.short_description = 'Salary Range'
    
    def staff_count(self, obj):
        """Get count of staff in position"""
        return obj.staff_members.filter(is_deleted=False).count()
    staff_count.short_description = 'Staff Count'


@admin.register(PositionTask)
class PositionTaskAdmin(admin.ModelAdmin):
    """Admin for PositionTask model"""
    list_display = ['title', 'position', 'priority', 'weight', 'frequency', 'is_active']
    list_filter = ['is_active', 'priority', 'frequency', 'position__department']
    search_fields = ['title', 'description', 'position__title']
    ordering = ['position', 'sort_order', '-priority']
    autocomplete_fields = ['position']


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    """Admin for StaffProfile model"""
    list_display = [
        'employee_number', 'get_full_name', 'position', 'department',
        'employment_type', 'employment_status', 'date_joined', 'get_primary_location'
    ]
    list_filter = ['employment_status', 'employment_type', 'department', 'position', 'primary_work_location']
    search_fields = [
        'employee_number', 'user__first_name', 'user__last_name',
        'user__email', 'position__title'
    ]
    ordering = ['user__last_name', 'user__first_name']
    autocomplete_fields = ['user', 'position', 'department', 'reports_to', 'primary_work_location']
    filter_horizontal = ['work_locations']
    inlines = [StaffPositionHistoryInline]
    date_hierarchy = 'date_joined'
    
    fieldsets = (
        ('Employee Information', {
            'fields': ('user', 'employee_number')
        }),
        ('Position & Department', {
            'fields': ('position', 'department', 'reports_to')
        }),
        ('Work Locations', {
            'fields': ('primary_work_location', 'work_locations'),
            'description': 'Assign staff to one or more work locations (campuses). Primary location is required for reporting.'
        }),
        ('Employment Details', {
            'fields': ('employment_type', 'employment_status', 'date_joined', 'probation_end_date', 'termination_date')
        }),
        ('Compensation', {
            'fields': ('current_salary',),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        """Get staff full name"""
        return obj.user.get_full_name()
    get_full_name.short_description = 'Name'
    get_full_name.admin_order_field = 'user__last_name'
    
    def get_primary_location(self, obj):
        """Get primary work location"""
        if obj.primary_work_location:
            return obj.primary_work_location.name
        return format_html('<span style="color: orange;">⚠ Not set</span>')
    get_primary_location.short_description = 'Primary Location'
    
    def save_model(self, request, obj, form, change):
        """Save model and show warning messages"""
        super().save_model(request, obj, form, change)
        
        # Show warning messages for missing fields
        from django.contrib import messages
        warnings = []
        if not obj.reports_to:
            warnings.append("Line Manager (Reports To) is not set")
        if not obj.primary_work_location:
            warnings.append("Primary Work Location is not set")
        
        if warnings:
            messages.warning(request, f"⚠ Profile saved but missing: {', '.join(warnings)}. Please update when available.")


@admin.register(StaffPositionHistory)
class StaffPositionHistoryAdmin(admin.ModelAdmin):
    """Admin for StaffPositionHistory model"""
    list_display = ['staff', 'position', 'department', 'start_date', 'end_date', 'change_reason', 'is_current_display']
    list_filter = ['change_reason', 'department', 'position']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'position__title']
    ordering = ['-start_date']
    autocomplete_fields = ['staff', 'position', 'department']
    date_hierarchy = 'start_date'
    
    def is_current_display(self, obj):
        """Display if this is current position"""
        if obj.is_current:
            return format_html('<span style="color: green;">✓ Current</span>')
        return format_html('<span style="color: gray;">Past</span>')
    is_current_display.short_description = 'Status'


@admin.register(StaffTaskAssignment)
class StaffTaskAssignmentAdmin(admin.ModelAdmin):
    """Admin for StaffTaskAssignment model"""
    list_display = [
        'staff', 'task', 'period_start', 'period_end', 'status',
        'self_rating', 'manager_rating'
    ]
    list_filter = ['status', 'task__position', 'period_start']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'task__title']
    ordering = ['-period_start']
    autocomplete_fields = ['staff', 'task', 'assessed_by']
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('Assignment', {
            'fields': ('staff', 'task', 'period_start', 'period_end')
        }),
        ('Status', {
            'fields': ('status', 'completion_date')
        }),
        ('Self Assessment', {
            'fields': ('self_rating', 'self_comments')
        }),
        ('Manager Assessment', {
            'fields': ('manager_rating', 'manager_comments', 'assessed_by', 'assessed_at')
        }),
    )


@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    """Admin for PerformanceReview model"""
    list_display = [
        'staff', 'review_type', 'review_period_start', 'review_period_end',
        'overall_rating', 'status', 'reviewed_by'
    ]
    list_filter = ['status', 'review_type', 'review_period_end']
    search_fields = ['staff__user__first_name', 'staff__user__last_name']
    ordering = ['-review_period_end']
    autocomplete_fields = ['staff', 'reviewed_by']
    date_hierarchy = 'review_period_end'
    
    fieldsets = (
        ('Review Details', {
            'fields': ('staff', 'review_type', 'review_period_start', 'review_period_end')
        }),
        ('Rating', {
            'fields': ('overall_rating',)
        }),
        ('Comments', {
            'fields': ('achievements', 'areas_for_improvement', 'goals_next_period', 'manager_comments', 'employee_comments')
        }),
        ('Workflow', {
            'fields': ('status', 'reviewed_by', 'review_date', 'acknowledged_at')
        }),
    )
