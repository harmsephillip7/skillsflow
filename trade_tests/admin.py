"""
Trade Tests Admin Configuration
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    Trade,
    TradeTestCentre,
    TradeTestCentreCapability,
    TradeTestApplication,
    ARPLToolkitAssessment,
    TradeTestBooking,
    TradeTestResult,
    TradeTestAppeal,
)


# =============================================================================
# INLINES
# =============================================================================

class TradeTestCentreCapabilityInline(admin.TabularInline):
    model = TradeTestCentreCapability
    extra = 1
    autocomplete_fields = ['trade']


class TradeTestBookingInline(admin.TabularInline):
    model = TradeTestBooking
    extra = 0
    readonly_fields = ['booking_reference', 'attempt_number', 'status', 'scheduled_date']
    fields = ['booking_reference', 'attempt_number', 'status', 'scheduled_date', 'centre']
    show_change_link = True


class TradeTestResultInline(admin.TabularInline):
    model = TradeTestResult
    fk_name = 'booking'
    extra = 0
    readonly_fields = ['section', 'result', 'score', 'test_date']
    fields = ['section', 'result', 'score', 'test_date', 'report_reference']


# =============================================================================
# TRADE
# =============================================================================

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = [
        'namb_code', 'name', 'qualification', 'seta',
        'theory_pass_mark', 'practical_pass_mark', 'is_active'
    ]
    list_filter = ['is_active', 'seta']
    search_fields = ['namb_code', 'name', 'qualification__title']
    autocomplete_fields = ['qualification', 'seta']
    
    fieldsets = (
        (None, {
            'fields': ('namb_code', 'name', 'description')
        }),
        ('Linked Qualification', {
            'fields': ('qualification', 'seta'),
            'description': 'Link to qualification for internal learner auto-population'
        }),
        ('Pass Requirements', {
            'fields': ('theory_pass_mark', 'practical_pass_mark')
        }),
        ('Additional Info', {
            'fields': ('typical_duration_months', 'is_active')
        }),
    )


# =============================================================================
# TRADE TEST CENTRE
# =============================================================================

@admin.register(TradeTestCentre)
class TradeTestCentreAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'city', 'province',
        'accreditation_status', 'max_daily_capacity', 'is_active'
    ]
    list_filter = ['province', 'is_active']
    search_fields = ['name', 'code', 'city']
    inlines = [TradeTestCentreCapabilityInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'is_active')
        }),
        ('Location', {
            'fields': (
                'address', 'city', 'province', 'postal_code',
                ('latitude', 'longitude')
            )
        }),
        ('Contact', {
            'fields': ('contact_person', 'contact_email', 'contact_phone')
        }),
        ('Accreditation', {
            'fields': ('accreditation_number', 'accreditation_expiry')
        }),
        ('Capacity', {
            'fields': ('max_daily_capacity',)
        }),
    )
    
    @admin.display(description='Accreditation')
    def accreditation_status(self, obj):
        if obj.is_accreditation_valid:
            days = obj.accreditation_days_remaining
            if days is None:
                return format_html('<span style="color: green;">✓ Valid</span>')
            elif days <= 30:
                return format_html(
                    '<span style="color: orange;">⚠ {} days</span>',
                    days
                )
            return format_html(
                '<span style="color: green;">✓ {} days</span>',
                days
            )
        return format_html('<span style="color: red;">✗ Expired</span>')


@admin.register(TradeTestCentreCapability)
class TradeTestCentreCapabilityAdmin(admin.ModelAdmin):
    list_display = [
        'centre', 'trade', 'max_candidates_per_session',
        'next_available_date', 'is_active'
    ]
    list_filter = ['is_active', 'centre', 'trade']
    autocomplete_fields = ['centre', 'trade']
    search_fields = ['centre__name', 'trade__name']


# =============================================================================
# TRADE TEST APPLICATION
# =============================================================================

@admin.register(TradeTestApplication)
class TradeTestApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'reference_number', 'learner', 'candidate_source', 'trade',
        'centre', 'status', 'application_date', 'attempt_count'
    ]
    list_filter = ['status', 'candidate_source', 'trade', 'centre']
    search_fields = [
        'reference_number', 'learner__first_name', 'learner__last_name',
        'learner__sa_id_number', 'namb_reference'
    ]
    autocomplete_fields = ['learner', 'enrollment', 'trade', 'centre']
    readonly_fields = ['reference_number', 'current_attempt', 'remaining_attempts']
    inlines = [TradeTestBookingInline]
    date_hierarchy = 'application_date'
    
    fieldsets = (
        (None, {
            'fields': ('reference_number', 'status')
        }),
        ('Candidate', {
            'fields': ('candidate_source', 'learner', 'enrollment')
        }),
        ('Trade & Centre', {
            'fields': ('trade', 'centre')
        }),
        ('NAMB Submission', {
            'fields': ('application_date', 'namb_submission_date', 'namb_reference')
        }),
        ('Attempt Tracking', {
            'fields': ('current_attempt', 'remaining_attempts'),
            'classes': ('collapse',)
        }),
        ('External Candidate Details', {
            'fields': ('previous_training_provider', 'years_experience'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes', 'internal_notes'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.display(description='Attempts')
    def attempt_count(self, obj):
        current = obj.current_attempt
        if current == 0:
            return 'No attempts'
        return f"{current}/3"


# =============================================================================
# ARPL TOOLKIT ASSESSMENT
# =============================================================================

@admin.register(ARPLToolkitAssessment)
class ARPLToolkitAssessmentAdmin(admin.ModelAdmin):
    list_display = [
        'application', 'centre', 'scheduled_date', 'status', 'result'
    ]
    list_filter = ['status', 'result', 'centre']
    search_fields = [
        'application__reference_number',
        'application__learner__first_name',
        'application__learner__last_name'
    ]
    autocomplete_fields = ['application', 'centre', 'assessor']
    date_hierarchy = 'scheduled_date'
    
    fieldsets = (
        (None, {
            'fields': ('application', 'status', 'result')
        }),
        ('Scheduling', {
            'fields': ('centre', 'scheduled_date', 'scheduled_time')
        }),
        ('Assessment', {
            'fields': ('assessor', 'result_date', 'assessor_notes')
        }),
        ('Recommendations', {
            'fields': ('training_recommendations',),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# TRADE TEST BOOKING
# =============================================================================

@admin.register(TradeTestBooking)
class TradeTestBookingAdmin(admin.ModelAdmin):
    list_display = [
        'booking_reference', 'learner', 'trade', 'attempt_number',
        'centre', 'scheduled_date', 'status'
    ]
    list_filter = ['status', 'attempt_number', 'trade', 'centre']
    search_fields = [
        'booking_reference', 'namb_reference',
        'learner__first_name', 'learner__last_name',
        'application__reference_number'
    ]
    autocomplete_fields = ['application', 'learner', 'trade', 'centre']
    readonly_fields = ['booking_reference', 'learner', 'trade']
    inlines = [TradeTestResultInline]
    date_hierarchy = 'scheduled_date'
    
    fieldsets = (
        (None, {
            'fields': ('booking_reference', 'application', 'attempt_number', 'status')
        }),
        ('Candidate & Trade', {
            'fields': ('learner', 'trade')
        }),
        ('Scheduling', {
            'fields': ('centre', 'scheduled_date', 'scheduled_time')
        }),
        ('NAMB Details', {
            'fields': ('submission_date', 'namb_reference', 'confirmation_letter')
        }),
        ('Fees', {
            'fields': (
                'booking_fee', 'fee_paid',
                'fee_payment_date', 'fee_payment_reference'
            ),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# TRADE TEST RESULT
# =============================================================================

@admin.register(TradeTestResult)
class TradeTestResultAdmin(admin.ModelAdmin):
    list_display = [
        'booking', 'section', 'result', 'score',
        'test_date', 'report_reference'
    ]
    list_filter = ['section', 'result']
    search_fields = [
        'booking__booking_reference',
        'booking__learner__first_name',
        'booking__learner__last_name',
        'report_reference'
    ]
    autocomplete_fields = ['booking', 'next_attempt_booking']
    date_hierarchy = 'test_date'
    
    fieldsets = (
        (None, {
            'fields': ('booking', 'section', 'result', 'score')
        }),
        ('Dates', {
            'fields': ('test_date', 'result_date')
        }),
        ('Assessment Report', {
            'fields': ('report_reference', 'report_date', 'report_file')
        }),
        ('Assessor', {
            'fields': ('assessor_name', 'assessor_registration', 'assessor_comments')
        }),
        ('Next Attempt', {
            'fields': ('next_attempt_booking',),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# TRADE TEST APPEAL
# =============================================================================

@admin.register(TradeTestAppeal)
class TradeTestAppealAdmin(admin.ModelAdmin):
    list_display = [
        'result', 'appeal_date', 'status', 'resolution_date'
    ]
    list_filter = ['status']
    search_fields = [
        'result__booking__booking_reference',
        'result__booking__learner__first_name',
        'result__booking__learner__last_name'
    ]
    autocomplete_fields = ['result', 'retest_booking']
    date_hierarchy = 'appeal_date'
    
    fieldsets = (
        (None, {
            'fields': ('result', 'status')
        }),
        ('Appeal Details', {
            'fields': ('appeal_date', 'grounds', 'supporting_documents')
        }),
        ('Resolution', {
            'fields': ('resolution_date', 'resolution_notes', 'new_result')
        }),
        ('Re-test', {
            'fields': ('retest_date', 'retest_booking'),
            'classes': ('collapse',)
        }),
    )
