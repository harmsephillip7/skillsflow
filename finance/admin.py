"""Finance app admin configuration"""
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    PriceList, PriceListItem, Quote, QuoteLineItem, Invoice, InvoiceLineItem,
    Payment, CreditNote, PaymentPlan, PaymentPlanInstallment, SageIntacctConfig, SageSyncLog,
    # Course Pricing models
    PricingStrategy, CoursePricing, CoursePricingYear, CoursePricingOverride,
    PaymentTerm, CoursePricingPaymentTerm, CoursePricingHistory,
    FuturePricingSchedule, FuturePricingYear,
    # Billing Schedule models
    BillingScheduleTemplate, ProjectBillingSchedule, ScheduledInvoice, FunderCollectionMetrics,
    # Quote Template models
    PaymentOption, QuoteTemplate,
)

# Original simple registrations
admin.site.register(PriceList)
admin.site.register(PriceListItem)
admin.site.register(Quote)
admin.site.register(QuoteLineItem)
admin.site.register(Invoice)
admin.site.register(InvoiceLineItem)
admin.site.register(Payment)
admin.site.register(CreditNote)
admin.site.register(PaymentPlan)
admin.site.register(PaymentPlanInstallment)
admin.site.register(SageIntacctConfig)
admin.site.register(SageSyncLog)


# =====================================================
# PAYMENT OPTION & QUOTE TEMPLATE ADMIN
# =====================================================

@admin.register(PaymentOption)
class PaymentOptionAdmin(admin.ModelAdmin):
    """Admin for managing global payment options."""
    
    list_display = ['name', 'code', 'installments', 'deposit_percent', 'monthly_term', 'sort_order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['sort_order', 'name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description')
        }),
        ('Payment Structure', {
            'fields': ('installments', 'deposit_percent', 'monthly_term')
        }),
        ('Display', {
            'fields': ('sort_order', 'is_active')
        }),
    )


@admin.register(QuoteTemplate)
class QuoteTemplateAdmin(admin.ModelAdmin):
    """Admin for managing quote templates with campus inheritance."""
    
    list_display = ['name', 'code', 'campus', 'parent_template', 'validity_hours', 'sort_order', 'is_active']
    list_filter = ['is_active', 'campus']
    search_fields = ['name', 'code', 'description']
    ordering = ['sort_order', 'name']
    raw_id_fields = ['parent_template', 'campus']
    filter_horizontal = ['payment_options']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'is_active', 'sort_order')
        }),
        ('Template Content', {
            'fields': ('header_text', 'default_terms', 'footer_text')
        }),
        ('Inheritance', {
            'fields': ('parent_template', 'campus'),
            'description': 'Leave campus blank for global templates. Set parent_template to inherit from another template.'
        }),
        ('Settings', {
            'fields': ('payment_options', 'validity_hours')
        }),
    )


# =====================================================
# BILLING SCHEDULE ADMIN CONFIGURATION
# =====================================================

@admin.register(BillingScheduleTemplate)
class BillingScheduleTemplateAdmin(admin.ModelAdmin):
    """Admin for managing default billing templates per funder type."""
    
    list_display = [
        'funder_type', 'default_schedule', 'invoice_type',
        'payment_terms_days', 'billing_day_of_month', 'is_active'
    ]
    list_filter = ['funder_type', 'default_schedule', 'is_active']
    search_fields = ['funder_type', 'name']
    ordering = ['funder_type']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'funder_type', 'is_active')
        }),
        ('Billing Settings', {
            'fields': ('default_schedule', 'invoice_type', 'auto_convert_on_payment',
                      'payment_terms_days', 'billing_day_of_month')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


class ScheduledInvoiceInline(admin.TabularInline):
    """Inline for viewing scheduled invoices."""
    model = ScheduledInvoice
    extra = 0
    fields = ['period_number', 'scheduled_date', 'due_date', 'amount', 
              'status', 'invoice']
    readonly_fields = ['invoice']
    ordering = ['period_number']
    
    def has_add_permission(self, request, obj=None):
        return False  # Don't allow manual additions


@admin.register(ProjectBillingSchedule)
class ProjectBillingScheduleAdmin(admin.ModelAdmin):
    """Admin for managing project-specific billing schedules."""
    
    list_display = [
        'training_notification', 'schedule_type', 'total_contract_value',
        'amount_per_period', 'auto_generate', 'created_at'
    ]
    list_filter = ['schedule_type', 'invoice_type', 'auto_generate']
    search_fields = ['training_notification__not_number', 
                    'training_notification__qualification__title']
    raw_id_fields = ['training_notification']
    date_hierarchy = 'created_at'
    inlines = [ScheduledInvoiceInline]
    
    fieldsets = (
        (None, {
            'fields': ('training_notification',)
        }),
        ('Schedule Configuration', {
            'fields': ('schedule_type', 'invoice_type', 'auto_convert_on_payment',
                      'total_contract_value', 'amount_per_period')
        }),
        ('Timing', {
            'fields': ('billing_start_date', 'billing_end_date', 
                      'billing_day_of_month', 'payment_terms_days')
        }),
        ('Automation', {
            'fields': ('auto_generate', 'last_invoice_generated', 'next_invoice_date')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('training_notification')


@admin.register(ScheduledInvoice)
class ScheduledInvoiceAdmin(admin.ModelAdmin):
    """Admin for viewing and managing scheduled invoices."""
    
    list_display = [
        'billing_schedule', 'period_number', 'scheduled_date', 'due_date',
        'amount', 'status', 'invoice'
    ]
    list_filter = ['status', 'scheduled_date']
    search_fields = ['billing_schedule__training_notification__not_number']
    raw_id_fields = ['billing_schedule', 'invoice']
    date_hierarchy = 'scheduled_date'
    ordering = ['billing_schedule', 'period_number']
    
    fieldsets = (
        (None, {
            'fields': ('billing_schedule', 'period_number')
        }),
        ('Schedule Details', {
            'fields': ('scheduled_date', 'due_date', 'amount')
        }),
        ('Status', {
            'fields': ('status', 'invoice', 'generated_at')
        }),
        ('Deliverable (if applicable)', {
            'fields': ('deliverable',),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(FunderCollectionMetrics)
class FunderCollectionMetricsAdmin(admin.ModelAdmin):
    """Admin for viewing collection and persistency metrics."""
    
    list_display = [
        'entity_type', 'get_entity_name', 'period_type',
        'collection_rate_display', 'persistency_rate_display',
        'risk_rating', 'is_good_business', 'calculated_at'
    ]
    list_filter = ['entity_type', 'period_type', 'funder_type', 
                  'is_good_business', 'risk_rating']
    search_fields = ['training_notification__not_number', 
                    'corporate_client__name']
    date_hierarchy = 'calculated_at'
    
    fieldsets = (
        ('Entity', {
            'fields': ('entity_type', 'funder_type', 'training_notification',
                      'corporate_client', 'learner')
        }),
        ('Period', {
            'fields': ('period_type', 'period_start', 'period_end')
        }),
        ('Amounts', {
            'fields': ('total_invoiced', 'total_collected', 'total_outstanding', 'total_bad_debt')
        }),
        ('Rates', {
            'fields': ('collection_rate', 'persistency_rate', 'bad_debt_ratio', 'average_days_to_payment')
        }),
        ('Invoice Counts', {
            'fields': ('invoices_issued', 'invoices_paid_on_time', 
                      'invoices_paid_late', 'invoices_outstanding'),
            'classes': ('collapse',)
        }),
        ('Aging Breakdown', {
            'fields': ('aging_current', 'aging_30_days', 
                      'aging_60_days', 'aging_90_days', 'aging_over_90'),
            'classes': ('collapse',)
        }),
        ('Assessment', {
            'fields': ('is_good_business', 'risk_rating')
        }),
    )
    readonly_fields = ['calculated_at']
    
    def get_entity_name(self, obj):
        """Display the entity name based on type."""
        if obj.entity_type == 'PROJECT' and obj.training_notification:
            return obj.training_notification.not_number
        elif obj.entity_type == 'CORPORATE' and obj.corporate_client:
            return obj.corporate_client.name
        elif obj.entity_type == 'LEARNER' and obj.learner:
            return obj.learner.get_full_name()
        elif obj.entity_type == 'FUNDER_TYPE':
            return f"Funder Type: {obj.funder_type}"
        return "-"
    get_entity_name.short_description = "Entity"
    
    def collection_rate_display(self, obj):
        """Color-coded collection rate."""
        rate = obj.collection_rate or 0
        if rate >= 80:
            color = 'green'
        elif rate >= 60:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    collection_rate_display.short_description = "Collection Rate"
    
    def persistency_rate_display(self, obj):
        """Color-coded persistency rate."""
        rate = obj.persistency_rate or 0
        if rate >= 90:
            color = 'green'
        elif rate >= 70:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    persistency_rate_display.short_description = "Persistency Rate"


# =====================================================
# COURSE PRICING ADMIN CONFIGURATION
# =====================================================

@admin.register(PricingStrategy)
class PricingStrategyAdmin(admin.ModelAdmin):
    """Admin for managing pricing strategies."""
    
    list_display = [
        'code', 'name', 'brand', 'strategy_type', 'priority',
        'region', 'campus', 'corporate_client', 'is_default', 'is_active'
    ]
    list_filter = ['brand', 'strategy_type', 'is_active', 'is_default']
    search_fields = ['name', 'code', 'description']
    ordering = ['brand', '-priority', 'name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'strategy_type', 'brand')
        }),
        ('Scope', {
            'fields': ('region', 'campus', 'corporate_client'),
            'description': 'Define the scope for this strategy based on its type.'
        }),
        ('Settings', {
            'fields': ('priority', 'is_default', 'is_active')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'brand', 'region', 'campus', 'corporate_client'
        )


class CoursePricingYearInline(admin.TabularInline):
    """Inline for multi-year pricing breakdown."""
    model = CoursePricingYear
    extra = 0
    fields = ['year_number', 'year_label', 'tuition_fee', 'material_fee', 
              'assessment_fee', 'other_fees', 'credits']


class CoursePricingPaymentTermInline(admin.TabularInline):
    """Inline for available payment terms."""
    model = CoursePricingPaymentTerm
    extra = 0
    fields = ['payment_term', 'is_default', 'is_available', 
              'override_discount', 'override_instalments', 'override_admin_fee']
    autocomplete_fields = ['payment_term']


class CoursePricingOverrideInline(admin.TabularInline):
    """Inline for price overrides."""
    model = CoursePricingOverride
    extra = 0
    fields = ['target_strategy', 'override_type', 'override_price', 
              'modifier_percent', 'discount_amount', 'discount_percent', 'is_active']
    autocomplete_fields = ['target_strategy']


@admin.register(CoursePricing)
class CoursePricingAdmin(admin.ModelAdmin):
    """Admin for managing course pricing with workflow."""
    
    list_display = [
        'qualification', 'pricing_strategy', 'version', 'status_badge',
        'total_price_display', 'deposit_display', 'effective_dates', 
        'is_current_badge'
    ]
    list_filter = [
        'status', 'pricing_strategy__brand', 'pricing_strategy__strategy_type',
        'effective_from', 'deposit_required'
    ]
    search_fields = [
        'qualification__name', 'qualification__short_name',
        'pricing_strategy__name', 'version_notes'
    ]
    date_hierarchy = 'effective_from'
    ordering = ['-effective_from', '-version']
    readonly_fields = [
        'version', 'total_price_vat_inclusive', 'calculated_deposit',
        'balance_after_deposit', 'tuition_fee', 'vat_amount',
        'submitted_by', 'submitted_at', 'approved_by', 'approved_at',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    autocomplete_fields = ['qualification', 'pricing_strategy', 'previous_version']
    inlines = [CoursePricingYearInline, CoursePricingPaymentTermInline, CoursePricingOverrideInline]
    
    fieldsets = (
        (None, {
            'fields': ('qualification', 'pricing_strategy', 'version', 'version_notes')
        }),
        ('Status & Validity', {
            'fields': ('status', 'effective_from', 'effective_to')
        }),
        ('Pricing', {
            'fields': (
                'total_price', 'total_price_vat_inclusive', 'vat_amount',
                'vat_rate', 'prices_include_vat'
            )
        }),
        ('Deposit', {
            'fields': (
                'deposit_required', 'deposit_type', 'deposit_amount', 
                'deposit_percentage', 'calculated_deposit', 'balance_after_deposit'
            )
        }),
        ('Fee Breakdown', {
            'fields': (
                'tuition_fee', 'registration_fee', 'material_fee',
                'assessment_fee', 'certification_fee'
            ),
            'description': 'Individual fees should sum to total price (tuition is calculated as remainder)'
        }),
        ('Early Bird / Promotional', {
            'fields': ('early_bird_discount_percent', 'early_bird_deadline_days'),
            'classes': ['collapse']
        }),
        ('Approval Workflow', {
            'fields': (
                'submitted_by', 'submitted_at', 'approved_by', 'approved_at',
                'rejection_reason', 'previous_version'
            ),
            'classes': ['collapse']
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ['collapse']
        }),
    )
    
    actions = ['submit_for_approval', 'approve_selected', 'activate_selected', 'create_new_version']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'qualification', 'pricing_strategy', 'pricing_strategy__brand',
            'submitted_by', 'approved_by'
        )
    
    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            'DRAFT': 'gray',
            'PENDING_APPROVAL': 'orange',
            'APPROVED': 'blue',
            'ACTIVE': 'green',
            'SUPERSEDED': 'purple',
            'ARCHIVED': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def total_price_display(self, obj):
        """Display total price with VAT info."""
        vat_label = 'incl.' if obj.prices_include_vat else 'excl.'
        return f"R{obj.total_price:,.2f} ({vat_label} VAT)"
    total_price_display.short_description = 'Total Price'
    
    def deposit_display(self, obj):
        """Display deposit amount."""
        if not obj.deposit_required:
            return '-'
        return f"R{obj.calculated_deposit:,.2f}"
    deposit_display.short_description = 'Deposit'
    
    def effective_dates(self, obj):
        """Display effective date range."""
        if obj.effective_to:
            return f"{obj.effective_from} → {obj.effective_to}"
        return f"{obj.effective_from} →"
    effective_dates.short_description = 'Effective'
    
    def is_current_badge(self, obj):
        """Display if pricing is currently active."""
        if obj.is_current:
            return format_html('<span style="color: green;">✓ Current</span>')
        elif obj.is_future:
            return format_html('<span style="color: blue;">📅 Future</span>')
        return ''
    is_current_badge.short_description = ''
    
    @admin.action(description='Submit selected for approval')
    def submit_for_approval(self, request, queryset):
        count = 0
        for pricing in queryset.filter(status='DRAFT'):
            try:
                pricing.submit_for_approval(request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, f'{count} pricing record(s) submitted for approval.')
    
    @admin.action(description='Approve selected')
    def approve_selected(self, request, queryset):
        count = 0
        for pricing in queryset.filter(status='PENDING_APPROVAL'):
            try:
                pricing.approve(request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, f'{count} pricing record(s) approved.')
    
    @admin.action(description='Activate selected')
    def activate_selected(self, request, queryset):
        count = 0
        for pricing in queryset.filter(status__in=['APPROVED', 'DRAFT']):
            try:
                pricing.activate(request.user)
                count += 1
            except ValueError:
                pass
        self.message_user(request, f'{count} pricing record(s) activated.')
    
    @admin.action(description='Create new version from selected')
    def create_new_version(self, request, queryset):
        from .models import CoursePricing
        count = 0
        for pricing in queryset:
            CoursePricing.create_new_version(pricing, request.user)
            count += 1
        self.message_user(request, f'{count} new version(s) created.')


@admin.register(PaymentTerm)
class PaymentTermAdmin(admin.ModelAdmin):
    """Admin for managing payment terms."""
    
    list_display = [
        'name', 'code', 'payment_type', 'number_of_instalments',
        'discount_percentage', 'interest_rate', 'is_active'
    ]
    list_filter = ['payment_type', 'is_active', 'available_for_self_funded', 'available_for_sponsored']
    search_fields = ['name', 'code', 'description']
    ordering = ['name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'payment_type')
        }),
        ('Instalment Configuration', {
            'fields': (
                'number_of_instalments', 'instalment_frequency_days',
                'deposit_with_application', 'balance_due_before_start', 'balance_due_days'
            )
        }),
        ('Discounts & Charges', {
            'fields': ('discount_percentage', 'admin_fee', 'interest_rate')
        }),
        ('Availability', {
            'fields': (
                'is_active', 'available_for_self_funded', 'available_for_sponsored',
                'min_course_value', 'max_course_value'
            )
        }),
    )


@admin.register(CoursePricingHistory)
class CoursePricingHistoryAdmin(admin.ModelAdmin):
    """Read-only admin for viewing pricing history."""
    
    list_display = [
        'pricing', 'change_type', 'changed_at', 'changed_by',
        'price_change_display', 'new_status'
    ]
    list_filter = ['change_type', 'changed_at']
    search_fields = ['pricing__qualification__name', 'change_reason']
    date_hierarchy = 'changed_at'
    ordering = ['-changed_at']
    readonly_fields = [
        'pricing', 'change_type', 'changed_at', 'changed_by',
        'old_total_price', 'new_total_price', 'old_status', 'new_status',
        'snapshot', 'change_reason'
    ]
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def price_change_display(self, obj):
        """Display price change if any."""
        if obj.old_total_price and obj.new_total_price:
            diff = obj.new_total_price - obj.old_total_price
            if diff > 0:
                return format_html('<span style="color: green;">+R{:,.2f}</span>', diff)
            elif diff < 0:
                return format_html('<span style="color: red;">-R{:,.2f}</span>', abs(diff))
        return '-'
    price_change_display.short_description = 'Price Change'


class FuturePricingYearInline(admin.TabularInline):
    """Inline for future pricing year configuration."""
    model = FuturePricingYear
    extra = 0
    fields = ['year', 'year_offset', 'escalation_percent', 'is_manually_set', 
              'is_locked', 'is_applied', 'notes']
    readonly_fields = ['is_applied', 'applied_at']


@admin.register(FuturePricingSchedule)
class FuturePricingScheduleAdmin(admin.ModelAdmin):
    """Admin for managing future pricing schedules."""
    
    list_display = [
        'name', 'brand', 'base_strategy', 'base_year', 
        'escalation_type', 'default_escalation_percent', 'status', 'is_active'
    ]
    list_filter = ['brand', 'escalation_type', 'status', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['-base_year']
    readonly_fields = ['approved_by', 'approved_at']
    autocomplete_fields = ['brand', 'base_strategy']
    inlines = [FuturePricingYearInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'brand', 'base_strategy')
        }),
        ('Year Configuration', {
            'fields': ('base_year', 'apply_from_month', 'apply_from_day')
        }),
        ('Escalation Rules', {
            'fields': ('escalation_type', 'default_escalation_percent'),
            'description': 'Set the default escalation. Individual years can override this.'
        }),
        ('Status', {
            'fields': ('status', 'is_active', 'approved_by', 'approved_at')
        }),
    )
    
    actions = ['generate_years', 'apply_schedule']
    
    @admin.action(description='Generate year entries (4 years)')
    def generate_years(self, request, queryset):
        for schedule in queryset:
            schedule.generate_years(4)
        self.message_user(request, f'Year entries generated for {queryset.count()} schedule(s).')
    
    @admin.action(description='Apply schedule to create future pricing')
    def apply_schedule(self, request, queryset):
        total_created = 0
        for schedule in queryset.filter(status='APPROVED'):
            count = schedule.apply_to_pricing(request.user)
            total_created += count
        self.message_user(request, f'{total_created} future pricing record(s) created.')

