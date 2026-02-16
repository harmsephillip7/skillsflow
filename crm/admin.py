"""CRM app admin configuration"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Lead, LeadSource, LeadActivity, SETAFundingOpportunity, FundingApplication,
    WhatsAppConfig, WhatsAppMessage, WhatsAppIntakeForm, WhatsAppIntakeSession,
    Pipeline, PipelineStage, StageBlueprint, CommunicationCycle, LeadEngagement, 
    AgentNotification, PreApprovalLetter,
    WebFormSource, WebFormMapping, WebFormSubmission
)


# Pipeline Admin - Simple registration first
admin.site.register(Pipeline)
admin.site.register(PipelineStage)
admin.site.register(StageBlueprint)
admin.site.register(CommunicationCycle)
admin.site.register(LeadEngagement)
admin.site.register(AgentNotification)
admin.site.register(PreApprovalLetter)

# Original admin registrations
admin.site.register(LeadSource)
admin.site.register(Lead)
admin.site.register(LeadActivity)
admin.site.register(SETAFundingOpportunity)
admin.site.register(FundingApplication)
admin.site.register(WhatsAppConfig)
admin.site.register(WhatsAppMessage)
admin.site.register(WhatsAppIntakeForm)
admin.site.register(WhatsAppIntakeSession)


# =============================================================================
# WEB FORM INTEGRATION ADMIN
# =============================================================================

class WebFormMappingInline(admin.TabularInline):
    """Inline admin for form mappings within a source."""
    model = WebFormMapping
    extra = 1
    fields = ['form_id', 'form_name', 'campus', 'lead_type', 'qualification', 'pipeline', 'auto_assign_to', 'is_active']
    raw_id_fields = ['campus', 'qualification', 'pipeline', 'auto_assign_to']
    readonly_fields = ['leads_created', 'duplicates_updated', 'last_submission_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('campus', 'qualification', 'pipeline')


@admin.register(WebFormSource)
class WebFormSourceAdmin(admin.ModelAdmin):
    """Admin for Web Form Sources (website integrations)."""
    list_display = ['name', 'domain', 'brand', 'default_campus', 'is_active', 'webhook_url_display', 'stats_display']
    list_filter = ['is_active', 'brand']
    search_fields = ['name', 'domain']
    readonly_fields = ['webhook_url_display', 'webhook_secret_display', 'total_leads_created', 'total_duplicates_updated', 'last_submission_at', 'created_at', 'updated_at']
    raw_id_fields = ['default_campus', 'default_lead_source']
    inlines = [WebFormMappingInline]
    
    fieldsets = (
        ('Source Details', {
            'fields': ('name', 'domain', 'description', 'brand', 'is_active')
        }),
        ('Webhook Configuration', {
            'fields': ('webhook_url_display', 'webhook_secret_display'),
            'description': 'Copy the webhook URL to your Gravity Forms settings. Include the secret in the X-Webhook-Secret header.'
        }),
        ('Defaults', {
            'fields': ('default_campus', 'default_lead_source'),
            'description': 'Default values used when a form mapping doesn\'t specify them.'
        }),
        ('Statistics', {
            'fields': ('total_leads_created', 'total_duplicates_updated', 'last_submission_at'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def webhook_url_display(self, obj):
        """Display the webhook URL with copy button."""
        if obj.pk:
            url = obj.get_webhook_url()
            return format_html(
                '<code style="background:#f5f5f5;padding:5px 10px;border-radius:4px;font-size:12px;">{}</code>'
                '<br><small class="text-muted">Full URL: https://your-domain.com{}</small>',
                url, url
            )
        return '-'
    webhook_url_display.short_description = 'Webhook URL'
    
    def webhook_secret_display(self, obj):
        """Display the webhook secret."""
        if obj.pk and obj.webhook_secret:
            return format_html(
                '<code style="background:#f5f5f5;padding:5px 10px;border-radius:4px;font-size:11px;">{}</code>'
                '<br><small>Send this in the <b>X-Webhook-Secret</b> header</small>',
                obj.webhook_secret
            )
        return '-'
    webhook_secret_display.short_description = 'Webhook Secret'
    
    def stats_display(self, obj):
        """Display statistics."""
        return format_html(
            '<span style="color:green">+{}</span> / <span style="color:blue">↻{}</span>',
            obj.total_leads_created,
            obj.total_duplicates_updated
        )
    stats_display.short_description = 'Created/Updated'
    
    actions = ['regenerate_secrets']
    
    def regenerate_secrets(self, request, queryset):
        """Regenerate webhook secrets for selected sources."""
        for source in queryset:
            source.regenerate_secret()
        self.message_user(request, f"Regenerated secrets for {queryset.count()} source(s).")
    regenerate_secrets.short_description = "Regenerate webhook secrets"


@admin.register(WebFormMapping)
class WebFormMappingAdmin(admin.ModelAdmin):
    """Admin for individual form mappings."""
    list_display = ['form_name', 'form_id', 'source', 'campus', 'lead_type', 'is_active', 'stats_display']
    list_filter = ['is_active', 'lead_type', 'source__brand']
    search_fields = ['form_name', 'form_id', 'source__name']
    raw_id_fields = ['source', 'campus', 'qualification', 'pipeline', 'auto_assign_to']
    readonly_fields = ['leads_created', 'duplicates_updated', 'last_submission_at', 'field_mapping_display']
    
    fieldsets = (
        ('Form Details', {
            'fields': ('source', 'form_id', 'form_name', 'is_active')
        }),
        ('Lead Configuration', {
            'fields': ('campus', 'lead_type', 'qualification', 'pipeline', 'auto_assign_to')
        }),
        ('Field Mapping', {
            'fields': ('field_mapping_display', 'field_mapping'),
            'description': '''
                Map Gravity Forms field IDs to Lead fields.
                Format: {"form_field_id": "lead_field_name"}
                Example: {"1.3": "first_name", "1.6": "last_name", "2": "email", "3": "phone"}
                
                Common Gravity Forms patterns:
                - Name field: 1.3 = First Name, 1.6 = Last Name
                - Email: Usually a single field ID like "2"
                - Phone: Usually a single field ID like "3"
                
                Available Lead fields: first_name, last_name, email, phone, phone_secondary,
                whatsapp_number, date_of_birth, school_name, grade, expected_matric_year,
                parent_name, parent_phone, parent_email, parent_relationship, employer_name,
                highest_qualification, employment_status, notes
            '''
        }),
        ('Default Values', {
            'fields': ('default_values',),
            'description': 'Default values for fields not in the form. Format: {"field_name": "value"}'
        }),
        ('Statistics', {
            'fields': ('leads_created', 'duplicates_updated', 'last_submission_at'),
            'classes': ('collapse',)
        }),
    )
    
    def field_mapping_display(self, obj):
        """Display current field mapping in readable format."""
        if obj.field_mapping:
            import json
            mapping_str = json.dumps(obj.field_mapping, indent=2)
            return format_html('<pre style="background:#f5f5f5;padding:10px;border-radius:4px;max-height:200px;overflow:auto;">{}</pre>', mapping_str)
        return 'No mapping configured'
    field_mapping_display.short_description = 'Current Mapping'
    
    def stats_display(self, obj):
        """Display statistics."""
        return format_html(
            '<span style="color:green">+{}</span> / <span style="color:blue">↻{}</span>',
            obj.leads_created,
            obj.duplicates_updated
        )
    stats_display.short_description = 'Created/Updated'


@admin.register(WebFormSubmission)
class WebFormSubmissionAdmin(admin.ModelAdmin):
    """Admin for viewing form submissions (read-only log)."""
    list_display = ['id', 'source', 'form_mapping', 'status', 'lead_link', 'created_at']
    list_filter = ['status', 'source', 'created_at']
    search_fields = ['id', 'source__name', 'lead__email', 'lead__phone']
    readonly_fields = [
        'id', 'source', 'form_mapping', 'raw_payload', 'mapped_data',
        'status', 'lead', 'error_message', 'ip_address', 'user_agent', 'created_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Submission Details', {
            'fields': ('id', 'source', 'form_mapping', 'status', 'created_at')
        }),
        ('Result', {
            'fields': ('lead', 'error_message')
        }),
        ('Data', {
            'fields': ('raw_payload', 'mapped_data'),
            'classes': ('collapse',)
        }),
        ('Request Info', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    def lead_link(self, obj):
        """Link to the lead if exists."""
        if obj.lead:
            url = reverse('admin:crm_lead_change', args=[obj.lead.pk])
            return format_html('<a href="{}">{}</a>', url, obj.lead.get_full_name())
        return '-'
    lead_link.short_description = 'Lead'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


