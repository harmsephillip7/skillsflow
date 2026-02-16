"""
Admin configuration for Tender Management module.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    TenderSegment, TenderSource, Tender, TenderQualification,
    TenderApplication, TenderDocument, TenderNote, TenderNotificationRule
)


@admin.register(TenderSegment)
class TenderSegmentAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'segment_type', 'decay_model', 'initial_probability',
        'historical_success_rate_display', 'total_applications',
        'total_value_won_display'
    ]
    list_filter = ['segment_type', 'decay_model']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'segment_type', 'description')
        }),
        ('Probability Configuration', {
            'fields': (
                'decay_model', 'initial_probability', 'decay_rate',
                'floor_probability', 'expected_response_days', 'step_thresholds'
            )
        }),
        ('Statistics', {
            'fields': (
                'total_applications', 'successful_applications',
                'total_value_applied', 'total_value_won'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def historical_success_rate_display(self, obj):
        rate = obj.historical_success_rate
        if rate is None:
            return '-'
        return f"{rate:.1%}"
    historical_success_rate_display.short_description = 'Success Rate'
    
    def total_value_won_display(self, obj):
        return f"R {obj.total_value_won:,.2f}"
    total_value_won_display.short_description = 'Value Won'


@admin.register(TenderSource)
class TenderSourceAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'scraper_type', 'status', 'status_color',
        'last_scraped_at', 'total_tenders_found', 'last_tenders_found'
    ]
    list_filter = ['status', 'scraper_type']
    search_fields = ['name', 'base_url']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = [
        'last_scraped_at', 'next_scrape_at', 'consecutive_failures',
        'total_tenders_found', 'last_tenders_found', 'status_message'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'base_url', 'default_segment')
        }),
        ('Scraper Configuration', {
            'fields': ('scraper_type', 'scrape_config', 'scrape_frequency_hours')
        }),
        ('Status', {
            'fields': (
                'status', 'status_message', 'consecutive_failures',
                'max_failures_before_pause'
            )
        }),
        ('Statistics', {
            'fields': (
                'last_scraped_at', 'next_scrape_at',
                'total_tenders_found', 'last_tenders_found'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def status_color(self, obj):
        colors = {
            'ACTIVE': 'green',
            'PAUSED': 'orange',
            'ERROR': 'red',
            'DISABLED': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {};">●</span>',
            color
        )
    status_color.short_description = ''


class TenderQualificationInline(admin.TabularInline):
    model = TenderQualification
    extra = 0
    autocomplete_fields = ['qualification']


class TenderDocumentInline(admin.TabularInline):
    model = TenderDocument
    extra = 0


@admin.register(Tender)
class TenderAdmin(admin.ModelAdmin):
    list_display = [
        'reference_number', 'title_short', 'funder', 'status',
        'closing_date', 'days_until_closing', 'estimated_value_display'
    ]
    list_filter = ['status', 'priority', 'segment', 'source']
    search_fields = ['reference_number', 'title', 'funder', 'description']
    date_hierarchy = 'closing_date'
    autocomplete_fields = ['segment', 'source', 'assigned_to', 'seta']
    inlines = [TenderQualificationInline, TenderDocumentInline]
    
    fieldsets = (
        (None, {
            'fields': (
                'reference_number', 'title', 'description', 'source_url'
            )
        }),
        ('Classification', {
            'fields': (
                'source', 'segment', 'funder', 'funder_type',
                'region', 'seta', 'priority', 'tags'
            )
        }),
        ('Dates', {
            'fields': (
                'published_date', 'opening_date', 'closing_date',
                'expected_award_date'
            )
        }),
        ('Value', {
            'fields': ('estimated_value', 'currency')
        }),
        ('Requirements', {
            'fields': ('requirements_summary', 'eligibility_notes')
        }),
        ('Assignment', {
            'fields': ('status', 'assigned_to', 'notes', 'campus')
        }),
    )
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Title'
    
    def days_until_closing(self, obj):
        days = obj.days_until_closing
        if days is None:
            return '-'
        if days < 0:
            return format_html('<span style="color: gray;">Closed</span>')
        if days <= 7:
            return format_html('<span style="color: red;">{} days</span>', days)
        return f"{days} days"
    days_until_closing.short_description = 'Closes In'
    
    def estimated_value_display(self, obj):
        if obj.estimated_value:
            return f"R {obj.estimated_value:,.2f}"
        return '-'
    estimated_value_display.short_description = 'Value'


@admin.register(TenderApplication)
class TenderApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'tender', 'status', 'total_learners', 'total_amount_display',
        'current_probability', 'expected_revenue_display', 'submitted_at'
    ]
    list_filter = ['status']
    search_fields = ['tender__reference_number', 'tender__title']
    date_hierarchy = 'submitted_at'
    autocomplete_fields = ['tender']
    inlines = [TenderDocumentInline]
    
    fieldsets = (
        (None, {
            'fields': ('tender', 'status')
        }),
        ('Dates', {
            'fields': (
                'preparation_started_at', 'submitted_at',
                'acknowledged_at', 'acknowledgement_reference', 'decision_at'
            )
        }),
        ('Application Details', {
            'fields': (
                'total_learners', 'total_amount', 'course_types'
            )
        }),
        ('Outcome', {
            'fields': (
                'approved_learners', 'approved_amount', 'rejection_reason'
            )
        }),
        ('Probability', {
            'fields': (
                'current_probability', 'probability_override',
                'expected_revenue', 'last_probability_update'
            )
        }),
        ('Contact', {
            'fields': (
                'funder_contact_name', 'funder_contact_email',
                'funder_contact_phone'
            )
        }),
    )
    
    readonly_fields = ['expected_revenue', 'last_probability_update']
    
    def total_amount_display(self, obj):
        return f"R {obj.total_amount:,.2f}"
    total_amount_display.short_description = 'Amount'
    
    def expected_revenue_display(self, obj):
        return f"R {obj.expected_revenue:,.2f}"
    expected_revenue_display.short_description = 'Expected Revenue'


@admin.register(TenderDocument)
class TenderDocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'tender', 'category', 'file_size', 'is_required', 'is_submitted']
    list_filter = ['category', 'is_required', 'is_submitted']
    search_fields = ['name', 'tender__reference_number']


@admin.register(TenderNote)
class TenderNoteAdmin(admin.ModelAdmin):
    list_display = ['tender', 'note_type', 'content_short', 'created_by', 'created_at']
    list_filter = ['note_type']
    search_fields = ['content', 'tender__reference_number']
    date_hierarchy = 'created_at'
    
    def content_short(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_short.short_description = 'Content'


@admin.register(TenderNotificationRule)
class TenderNotificationRuleAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'trigger', 'channel', 'is_active',
        'last_triggered_at', 'total_triggered'
    ]
    list_filter = ['trigger', 'channel', 'is_active']
    search_fields = ['name']
