"""Logistics app admin configuration"""
from django.contrib import admin
from .models import Cohort, Venue, ScheduleSession, Attendance, LogbookTracker, LogbookMovement


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    """Admin for Cohort model with search support"""
    list_display = ['name', 'code', 'qualification', 'start_date', 'end_date', 'status', 'current_count', 'max_capacity']
    list_filter = ['status', 'qualification', 'start_date']
    search_fields = ['name', 'code', 'qualification__title', 'qualification__saqa_id']
    autocomplete_fields = ['qualification', 'facilitator']
    date_hierarchy = 'start_date'
    ordering = ['-start_date', 'name']


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    """Admin for Venue model"""
    list_display = ['name', 'campus', 'capacity', 'venue_type']
    list_filter = ['campus', 'venue_type']
    search_fields = ['name', 'campus__name']


@admin.register(ScheduleSession)
class ScheduleSessionAdmin(admin.ModelAdmin):
    """Admin for ScheduleSession model"""
    list_display = ['cohort', 'date', 'start_time', 'end_time', 'venue']
    list_filter = ['cohort', 'date']
    search_fields = ['cohort__name', 'cohort__code']
    date_hierarchy = 'date'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    """Admin for Attendance model"""
    list_display = ['session', 'enrollment', 'status', 'check_in_time']
    list_filter = ['status', 'session__cohort']
    search_fields = ['enrollment__learner__first_name', 'enrollment__learner__last_name', 'session__cohort__name']


@admin.register(LogbookTracker)
class LogbookTrackerAdmin(admin.ModelAdmin):
    """Admin for LogbookTracker model"""
    list_display = ['enrollment', 'logbook_number', 'status', 'last_status_change']
    list_filter = ['status']
    search_fields = ['enrollment__learner__first_name', 'enrollment__learner__last_name', 'logbook_number']


@admin.register(LogbookMovement)
class LogbookMovementAdmin(admin.ModelAdmin):
    """Admin for LogbookMovement model"""
    list_display = ['logbook', 'from_status', 'to_status', 'moved_by', 'created_at']
    list_filter = ['from_status', 'to_status']
    search_fields = ['logbook__logbook_number', 'logbook__enrollment__learner__first_name']
