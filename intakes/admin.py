from django.contrib import admin
from .models import Intake, IntakeEnrollment, IntakeDocument, IntakeCapacitySnapshot


class IntakeEnrollmentInline(admin.TabularInline):
    model = IntakeEnrollment
    extra = 0
    fields = ['learner', 'funding_type', 'status', 'enrollment_number', 'registration_paid']
    readonly_fields = ['enrollment_number']
    show_change_link = True


@admin.register(Intake)
class IntakeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'qualification', 'campus', 'status', 'start_date', 
                    'enrolled_count', 'max_capacity', 'fill_percentage']
    list_filter = ['status', 'campus', 'qualification', 'delivery_mode']
    search_fields = ['code', 'name', 'qualification__name', 'campus__name']
    date_hierarchy = 'start_date'
    ordering = ['-start_date']
    inlines = [IntakeEnrollmentInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description')
        }),
        ('Programme Details', {
            'fields': ('qualification', 'campus', 'delivery_mode')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'enrollment_deadline')
        }),
        ('Capacity', {
            'fields': ('max_capacity', 'min_viable', 'status')
        }),
        ('Fees', {
            'fields': ('registration_fee', 'tuition_fee', 'materials_fee')
        }),
        ('Linked Records', {
            'fields': ('training_notification', 'not_intake', 'cohort', 'facilitator', 'venue'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


class IntakeDocumentInline(admin.TabularInline):
    model = IntakeDocument
    extra = 0
    fields = ['document_type', 'file', 'status', 'reviewed_by']


@admin.register(IntakeEnrollment)
class IntakeEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['enrollment_number', 'learner', 'intake', 'funding_type', 'status', 
                    'registration_paid', 'application_date']
    list_filter = ['status', 'funding_type', 'payment_method', 'registration_paid']
    search_fields = ['enrollment_number', 'learner__first_name', 'learner__last_name', 
                     'learner__id_number', 'intake__name']
    date_hierarchy = 'application_date'
    ordering = ['-application_date']
    inlines = [IntakeDocumentInline]
    raw_id_fields = ['learner', 'intake', 'responsible_payer', 'corporate_client', 
                     'bursary_application', 'debit_order_mandate', 'academic_enrollment']
    
    fieldsets = (
        ('Core Information', {
            'fields': ('intake', 'learner', 'enrollment_number', 'status')
        }),
        ('Funding', {
            'fields': ('funding_type', 'payment_method', 'responsible_payer', 
                       'corporate_client', 'bursary_application')
        }),
        ('Fees', {
            'fields': ('registration_fee', 'tuition_fee', 'materials_fee', 
                       'discount_amount', 'discount_reason')
        }),
        ('Payment Status', {
            'fields': ('registration_paid', 'registration_paid_date', 
                       'registration_payment_reference', 'debit_order_mandate')
        }),
        ('Bursary Contract', {
            'fields': ('bursary_contract_signed', 'bursary_contract_date', 
                       'bursary_contract_file'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('application_date', 'enrollment_date', 'start_date', 
                       'completion_date', 'withdrawal_date', 'withdrawal_reason'),
            'classes': ('collapse',)
        }),
        ('Academic Link', {
            'fields': ('academic_enrollment',),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(IntakeDocument)
class IntakeDocumentAdmin(admin.ModelAdmin):
    list_display = ['enrollment', 'document_type', 'status', 'created_at', 'reviewed_by']
    list_filter = ['document_type', 'status']
    search_fields = ['enrollment__enrollment_number', 'enrollment__learner__first_name', 
                     'enrollment__learner__last_name']
    date_hierarchy = 'created_at'


@admin.register(IntakeCapacitySnapshot)
class IntakeCapacitySnapshotAdmin(admin.ModelAdmin):
    list_display = ['intake', 'snapshot_date', 'enrolled_count', 'max_capacity', 
                    'fill_percentage']
    list_filter = ['intake__campus', 'intake__qualification']
    search_fields = ['intake__code', 'intake__name']
    date_hierarchy = 'snapshot_date'
    ordering = ['-snapshot_date']
