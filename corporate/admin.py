"""Corporate app admin configuration"""
from django.contrib import admin
from .models import (
    CorporateClient, CorporateContact, CorporateEmployee, WSPYear, WSPSubmission, 
    WSPPlannedTraining, ATRSubmission, ATRCompletedTraining, EEReport, EEWorkforceProfile,
    BBBEEScorecard, GrantProject, GrantClaim, Committee, CommitteeMember, CommitteeMeeting,
    EmployeeIDP, IDPTrainingNeed, ClientProject, ClientProjectTask, DeadlineReminder,
    # Service Catalog models
    ServiceCategory, ServiceOffering, ClientServiceSubscription,
    # Host Employer models
    HostEmployer, HostMentor, WorkplacePlacement, PlacementVisit, WorkplaceStint,
    # Trade Test models (Legacy - deprecated, use trade_tests app)
    TradeTestVenue, LegacyTradeTestBooking, LegacyTradeTestResult, LegacyTradeTestAppeal,
    # CRM Pipeline models
    LeadSource, CorporateOpportunity, CorporateActivity, ServiceProposal, ProposalLineItem,
    # Service Delivery models
    ServiceDeliveryProject, ProjectMilestone, MilestoneTask, ProjectDocument,
    ServiceDeliveryTemplate, ServiceDeliveryTemplateMilestone,
    # WSP/ATR Service Enhancement models
    WSPATRServiceYear, WSPATREmployeeData, WSPATRTrainingData, WSPATRPivotalData,
    # Training Committee models
    TrainingCommittee, TrainingCommitteeMember, MeetingTemplate, 
    TrainingCommitteeMeeting, TCMeetingAgendaItem, MeetingMinutes, 
    TCMeetingAttendance, TCMeetingActionItem,
    # SETA Export models
    SETAExportTemplate,
    # Employment Equity (EE) models
    ClientEmployeeSnapshot, OccupationalLevelData,
    EEServiceYear, EEPlan, EEAnalysis, EEBarrier, EENumericalGoal,
    EEIncomeDifferential, EEDocument,
    # B-BBEE models
    BBBEEServiceYear, BBBEEDocument, OwnershipStructure, Shareholder,
    ManagementControlProfile, SkillsDevelopmentElement, ESDElement, ESDSupplier,
    SEDElement, SEDContribution, TransformationPlan,
    # Onboarding models
    ClientOnboarding, ServiceOnboarding, PortalInvitation,
)


# =============================================================================
# CORPORATE CLIENT ADMIN
# =============================================================================

class CorporateContactInline(admin.TabularInline):
    model = CorporateContact
    extra = 0
    fields = ['first_name', 'last_name', 'job_title', 'role', 'email', 'phone', 'is_primary', 'is_active']


class ClientServiceSubscriptionInline(admin.TabularInline):
    model = ClientServiceSubscription
    extra = 0
    fields = ['service', 'status', 'start_date', 'end_date', 'assigned_consultant']
    readonly_fields = ['service']
    show_change_link = True


class DeadlineReminderInline(admin.TabularInline):
    model = DeadlineReminder
    extra = 0
    fields = ['reminder_type', 'title', 'deadline_date', 'is_completed']


@admin.register(CorporateClient)
class CorporateClientAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'trading_name', 'status', 'seta', 'account_manager', 'employee_count', 'contract_end_date']
    list_filter = ['status', 'seta', 'industry', 'campus']
    search_fields = ['company_name', 'trading_name', 'registration_number', 'seta_number']
    list_editable = ['status']
    date_hierarchy = 'created_at'
    inlines = [CorporateContactInline, ClientServiceSubscriptionInline, DeadlineReminderInline]
    
    fieldsets = (
        ('Company Information', {
            'fields': ('company_name', 'trading_name', 'registration_number', 'vat_number')
        }),
        ('Contact Details', {
            'fields': ('phone', 'email', 'website')
        }),
        ('Address', {
            'fields': ('physical_address', 'postal_address')
        }),
        ('Industry & SETA', {
            'fields': ('sic_code', 'industry', 'seta', 'seta_number')
        }),
        ('Company Size', {
            'fields': ('employee_count', 'annual_revenue')
        }),
        ('Account Management', {
            'fields': ('status', 'account_manager', 'contract_start_date', 'contract_end_date')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Tenant', {
            'fields': ('campus',)
        }),
    )


@admin.register(CorporateContact)
class CorporateContactAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'client', 'role', 'email', 'phone', 'is_primary', 'is_active']
    list_filter = ['role', 'is_primary', 'is_active', 'client']
    search_fields = ['first_name', 'last_name', 'email', 'client__company_name']


@admin.register(CorporateEmployee)
class CorporateEmployeeAdmin(admin.ModelAdmin):
    list_display = ['learner', 'client', 'employee_number', 'job_title', 'ofo_code', 'occupational_level', 'is_current']
    list_filter = ['is_current', 'client', 'occupational_level', 'employment_type']
    search_fields = ['learner__first_name', 'learner__last_name', 'employee_number', 'client__company_name', 'ofo_code']


# =============================================================================
# SERVICE CATALOG ADMIN
# =============================================================================

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active']
    search_fields = ['name', 'code']
    ordering = ['display_order', 'name']


class ServiceOfferingInline(admin.TabularInline):
    model = ServiceOffering
    extra = 0
    fields = ['name', 'code', 'service_type', 'billing_type', 'base_price', 'is_active']


@admin.register(ServiceOffering)
class ServiceOfferingAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'service_type', 'billing_type', 'base_price', 'is_active', 'is_featured']
    list_filter = ['category', 'service_type', 'billing_type', 'is_active', 'is_featured']
    search_fields = ['name', 'code', 'description']
    list_editable = ['is_active', 'is_featured']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'name', 'code', 'service_type', 'description')
        }),
        ('Pricing', {
            'fields': ('billing_type', 'base_price', 'price_description')
        }),
        ('Features', {
            'fields': ('features',)
        }),
        ('SLA', {
            'fields': ('sla_response_hours', 'sla_delivery_days')
        }),
        ('Requirements', {
            'fields': ('requires_qualification', 'requires_seta')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
    )


@admin.register(ClientServiceSubscription)
class ClientServiceSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['client', 'service', 'status', 'start_date', 'end_date', 'renewal_date', 'assigned_consultant']
    list_filter = ['status', 'service__category', 'service', 'auto_renew']
    search_fields = ['client__company_name', 'service__name', 'contract_reference']
    date_hierarchy = 'start_date'
    raw_id_fields = ['client']
    
    fieldsets = (
        ('Client & Service', {
            'fields': ('client', 'service', 'campus')
        }),
        ('Contract', {
            'fields': ('contract_reference', 'start_date', 'end_date', 'renewal_date', 'auto_renew')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Pricing', {
            'fields': ('agreed_price', 'billing_frequency')
        }),
        ('Assignment', {
            'fields': ('assigned_consultant',)
        }),
        ('Scope & Notes', {
            'fields': ('scope_of_work', 'notes'),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# HOST EMPLOYER ADMIN
# =============================================================================

class HostMentorInline(admin.TabularInline):
    model = HostMentor
    extra = 0
    fields = ['first_name', 'last_name', 'job_title', 'email', 'phone', 'mentor_trained', 'max_mentees', 'is_active']


class WorkplacePlacementInline(admin.TabularInline):
    model = WorkplacePlacement
    extra = 0
    fields = ['learner', 'enrollment', 'status', 'start_date', 'expected_end_date', 'mentor']
    readonly_fields = ['placement_reference']
    raw_id_fields = ['learner', 'enrollment']


@admin.register(HostEmployer)
class HostEmployerAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'status', 'contact_person', 'contact_phone', 'max_placement_capacity', 'current_placements', 'available_capacity', 'is_approved']
    list_filter = ['status', 'seta', 'has_workshop', 'safety_requirements_met', 'campus']
    search_fields = ['company_name', 'trading_name', 'contact_person', 'contact_email']
    filter_horizontal = ['approved_qualifications']
    inlines = [HostMentorInline, WorkplacePlacementInline]
    
    fieldsets = (
        ('Company Information', {
            'fields': ('company_name', 'trading_name', 'registration_number', 'employer')
        }),
        ('Contact', {
            'fields': ('contact_person', 'contact_email', 'contact_phone', 'physical_address')
        }),
        ('SETA & Approval', {
            'fields': ('seta', 'status', 'approval_date', 'approval_expiry', 'approval_reference')
        }),
        ('Capacity', {
            'fields': ('max_placement_capacity', 'current_placements')
        }),
        ('Qualifications', {
            'fields': ('approved_qualifications',)
        }),
        ('Facilities', {
            'fields': ('has_workshop', 'has_training_room', 'equipment_available', 'safety_requirements_met')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Tenant', {
            'fields': ('campus',)
        }),
    )


@admin.register(HostMentor)
class HostMentorAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'host', 'job_title', 'trade', 'mentor_trained', 'max_mentees', 'current_mentees', 'is_active']
    list_filter = ['mentor_trained', 'is_active', 'host']
    search_fields = ['first_name', 'last_name', 'email', 'host__company_name', 'trade']


class PlacementVisitInline(admin.TabularInline):
    model = PlacementVisit
    extra = 0
    fields = ['visit_type', 'visit_date', 'visitor', 'learner_progress_rating', 'follow_up_required']
    readonly_fields = ['visit_date']


@admin.register(WorkplacePlacement)
class WorkplacePlacementAdmin(admin.ModelAdmin):
    list_display = ['placement_reference', 'learner', 'host', 'workplace_stint', 'status', 'start_date', 'expected_end_date', 'mentor']
    list_filter = ['status', 'host', 'workplace_stint', 'agreement_signed', 'logbook_issued']
    search_fields = ['placement_reference', 'learner__first_name', 'learner__last_name', 'host__company_name']
    date_hierarchy = 'start_date'
    raw_id_fields = ['learner', 'enrollment', 'training_notification', 'workplace_stint']
    inlines = [PlacementVisitInline]
    
    fieldsets = (
        ('Placement Details', {
            'fields': ('placement_reference', 'learner', 'enrollment', 'training_notification')
        }),
        ('QCTO Stint', {
            'fields': ('workplace_stint',),
            'description': 'Link this placement to a specific workplace stint requirement'
        }),
        ('Host & Mentor', {
            'fields': ('host', 'mentor', 'department', 'position')
        }),
        ('Dates', {
            'fields': ('start_date', 'expected_end_date', 'actual_end_date')
        }),
        ('Status', {
            'fields': ('status', 'termination_reason', 'termination_notes')
        }),
        ('Documentation', {
            'fields': ('placement_letter', 'agreement_signed', 'agreement_date', 'logbook_issued', 'logbook_number')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Tenant', {
            'fields': ('campus',)
        }),
    )


@admin.register(PlacementVisit)
class PlacementVisitAdmin(admin.ModelAdmin):
    list_display = ['placement', 'visit_type', 'visit_date', 'visitor', 'learner_progress_rating', 'follow_up_required']
    list_filter = ['visit_type', 'follow_up_required', 'visitor']
    search_fields = ['placement__learner__first_name', 'placement__learner__last_name', 'placement__host__company_name']
    date_hierarchy = 'visit_date'


# =============================================================================
# TRADE TEST ADMIN
# =============================================================================

@admin.register(TradeTestVenue)
class TradeTestVenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'city', 'province', 'accreditation_expiry', 'is_active']
    list_filter = ['province', 'is_active']
    search_fields = ['name', 'code', 'city']


class LegacyTradeTestResultInline(admin.TabularInline):
    model = LegacyTradeTestResult
    extra = 0
    fields = ['section', 'result', 'score', 'test_date', 'certificate_number']


@admin.register(LegacyTradeTestBooking)
class LegacyTradeTestBookingAdmin(admin.ModelAdmin):
    list_display = ['booking_reference', 'learner', 'trade_code', 'venue', 'scheduled_date', 'status', 'fee_paid']
    list_filter = ['status', 'venue', 'fee_paid', 'trade_code']
    search_fields = ['booking_reference', 'learner__first_name', 'learner__last_name', 'namb_reference', 'trade_code']
    date_hierarchy = 'scheduled_date'
    raw_id_fields = ['learner', 'enrollment', 'training_notification']
    inlines = [LegacyTradeTestResultInline]
    
    fieldsets = (
        ('Learner Information', {
            'fields': ('learner', 'enrollment', 'training_notification')
        }),
        ('Trade & Qualification', {
            'fields': ('qualification', 'trade_code')
        }),
        ('Booking Details', {
            'fields': ('booking_reference', 'venue', 'submission_date', 'scheduled_date', 'scheduled_time')
        }),
        ('Status', {
            'fields': ('status', 'namb_reference', 'confirmation_letter')
        }),
        ('Fees', {
            'fields': ('booking_fee', 'fee_paid', 'fee_payment_date', 'fee_payment_reference')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Tenant', {
            'fields': ('campus',)
        }),
    )


@admin.register(LegacyTradeTestResult)
class LegacyTradeTestResultAdmin(admin.ModelAdmin):
    list_display = ['booking', 'section', 'result', 'score', 'test_date', 'certificate_number']
    list_filter = ['section', 'result']
    search_fields = ['booking__learner__first_name', 'booking__learner__last_name', 'certificate_number']
    date_hierarchy = 'test_date'


@admin.register(LegacyTradeTestAppeal)
class LegacyTradeTestAppealAdmin(admin.ModelAdmin):
    list_display = ['result', 'appeal_date', 'status', 'resolution_date', 'new_result']
    list_filter = ['status']
    search_fields = ['result__booking__learner__first_name', 'result__booking__learner__last_name']
    date_hierarchy = 'appeal_date'


# =============================================================================
# WSP/ATR ADMIN
# =============================================================================

class WSPPlannedTrainingInline(admin.TabularInline):
    model = WSPPlannedTraining
    extra = 0
    fields = ['intervention_type', 'training_description', 'african_male', 'african_female', 'estimated_cost']


@admin.register(WSPYear)
class WSPYearAdmin(admin.ModelAdmin):
    list_display = ['year', 'submission_deadline', 'is_current']
    list_editable = ['is_current']


@admin.register(WSPSubmission)
class WSPSubmissionAdmin(admin.ModelAdmin):
    list_display = ['client', 'wsp_year', 'status', 'seta_reference', 'submitted_date', 'total_learners_planned']
    list_filter = ['status', 'wsp_year']
    search_fields = ['client__company_name', 'seta_reference']
    inlines = [WSPPlannedTrainingInline]


admin.site.register(WSPPlannedTraining)


class ATRCompletedTrainingInline(admin.TabularInline):
    model = ATRCompletedTraining
    extra = 0
    fields = ['intervention_type', 'training_description', 'african_male', 'african_female', 'actual_cost']


@admin.register(ATRSubmission)
class ATRSubmissionAdmin(admin.ModelAdmin):
    list_display = ['client', 'reporting_year', 'status', 'seta_reference', 'submitted_date', 'total_learners_trained']
    list_filter = ['status', 'reporting_year']
    search_fields = ['client__company_name', 'seta_reference']
    inlines = [ATRCompletedTrainingInline]


admin.site.register(ATRCompletedTraining)


# =============================================================================
# EE ADMIN
# =============================================================================

class EEWorkforceProfileInline(admin.TabularInline):
    model = EEWorkforceProfile
    extra = 0


@admin.register(EEReport)
class EEReportAdmin(admin.ModelAdmin):
    list_display = ['client', 'reporting_period_end', 'status', 'submitted_date', 'reference_number']
    list_filter = ['status']
    search_fields = ['client__company_name', 'reference_number']
    inlines = [EEWorkforceProfileInline]


admin.site.register(EEWorkforceProfile)


# =============================================================================
# BBBEE ADMIN
# =============================================================================

@admin.register(BBBEEScorecard)
class BBBEEScorecardAdmin(admin.ModelAdmin):
    list_display = ['client', 'bbbee_level', 'verification_date', 'expiry_date', 'total_score', 'verification_agency']
    list_filter = ['bbbee_level']
    search_fields = ['client__company_name', 'certificate_number', 'verification_agency']
    date_hierarchy = 'verification_date'


# =============================================================================
# GRANT ADMIN
# =============================================================================

class GrantClaimInline(admin.TabularInline):
    model = GrantClaim
    extra = 0
    fields = ['claim_type', 'claim_number', 'status', 'claim_amount', 'submission_date']


@admin.register(GrantProject)
class GrantProjectAdmin(admin.ModelAdmin):
    list_display = ['client', 'project_name', 'seta', 'status', 'approved_amount', 'target_learners', 'completed_learners']
    list_filter = ['status', 'seta']
    search_fields = ['client__company_name', 'project_name', 'project_number']
    inlines = [GrantClaimInline]


@admin.register(GrantClaim)
class GrantClaimAdmin(admin.ModelAdmin):
    list_display = ['project', 'claim_type', 'status', 'claim_amount', 'approved_amount', 'submission_date', 'payment_date']
    list_filter = ['status', 'claim_type']
    search_fields = ['project__project_name', 'claim_number']


# =============================================================================
# COMMITTEE ADMIN
# =============================================================================

class CommitteeMemberInline(admin.TabularInline):
    model = CommitteeMember
    extra = 0


@admin.register(Committee)
class CommitteeAdmin(admin.ModelAdmin):
    list_display = ['client', 'name', 'committee_type', 'meeting_frequency', 'is_active']
    list_filter = ['committee_type', 'is_active']
    search_fields = ['client__company_name', 'name']
    inlines = [CommitteeMemberInline]


admin.site.register(CommitteeMember)
admin.site.register(CommitteeMeeting)


# =============================================================================
# IDP ADMIN
# =============================================================================

class IDPTrainingNeedInline(admin.TabularInline):
    model = IDPTrainingNeed
    extra = 0


@admin.register(EmployeeIDP)
class EmployeeIDPAdmin(admin.ModelAdmin):
    list_display = ['employee', 'period_start', 'period_end', 'status']
    list_filter = ['status']
    search_fields = ['employee__learner__first_name', 'employee__learner__last_name']
    inlines = [IDPTrainingNeedInline]


admin.site.register(IDPTrainingNeed)


# =============================================================================
# CLIENT PROJECT ADMIN
# =============================================================================

class ClientProjectTaskInline(admin.TabularInline):
    model = ClientProjectTask
    extra = 0


@admin.register(ClientProject)
class ClientProjectAdmin(admin.ModelAdmin):
    list_display = ['client', 'name', 'status', 'start_date', 'end_date', 'project_manager']
    list_filter = ['status']
    search_fields = ['client__company_name', 'name']
    inlines = [ClientProjectTaskInline]


admin.site.register(ClientProjectTask)


@admin.register(DeadlineReminder)
class DeadlineReminderAdmin(admin.ModelAdmin):
    list_display = ['client', 'reminder_type', 'title', 'deadline_date', 'is_completed']
    list_filter = ['reminder_type', 'is_completed']
    search_fields = ['client__company_name', 'title']
    date_hierarchy = 'deadline_date'


# =============================================================================
# CRM PIPELINE ADMIN
# =============================================================================

@admin.register(LeadSource)
class LeadSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name', 'code']


class CorporateActivityInline(admin.TabularInline):
    model = CorporateActivity
    extra = 0
    fk_name = 'opportunity'
    fields = ['activity_type', 'subject', 'activity_date', 'outcome', 'is_completed']
    readonly_fields = ['activity_date']


class ServiceProposalInline(admin.TabularInline):
    model = ServiceProposal
    extra = 0
    fields = ['proposal_number', 'title', 'status', 'total_amount', 'valid_until']
    readonly_fields = ['proposal_number']
    show_change_link = True


@admin.register(CorporateOpportunity)
class CorporateOpportunityAdmin(admin.ModelAdmin):
    list_display = ['reference_number', 'title', 'client_name', 'stage', 'estimated_value', 'probability', 'expected_close_date', 'sales_owner']
    list_filter = ['stage', 'opportunity_type', 'priority', 'lead_source', 'sales_owner']
    search_fields = ['reference_number', 'title', 'client__company_name', 'prospect_company_name']
    date_hierarchy = 'created_at'
    filter_horizontal = ['proposed_services']
    inlines = [CorporateActivityInline, ServiceProposalInline]
    
    fieldsets = (
        ('Opportunity Details', {
            'fields': ('reference_number', 'title', 'description', 'opportunity_type', 'priority')
        }),
        ('Client', {
            'fields': ('client', 'prospect_company_name', 'prospect_contact_name', 'prospect_email', 'prospect_phone')
        }),
        ('Pipeline', {
            'fields': ('stage', 'expected_close_date', 'actual_close_date')
        }),
        ('Services', {
            'fields': ('proposed_services',)
        }),
        ('Value', {
            'fields': ('estimated_value', 'probability')
        }),
        ('Source', {
            'fields': ('lead_source', 'referral_source')
        }),
        ('Assignment', {
            'fields': ('sales_owner',)
        }),
        ('Close Details', {
            'fields': ('loss_reason', 'competitor'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Tenant', {
            'fields': ('campus',)
        }),
    )
    readonly_fields = ['reference_number']


@admin.register(CorporateActivity)
class CorporateActivityAdmin(admin.ModelAdmin):
    list_display = ['subject', 'activity_type', 'client', 'opportunity', 'activity_date', 'outcome', 'is_completed']
    list_filter = ['activity_type', 'outcome', 'is_completed', 'created_by']
    search_fields = ['subject', 'client__company_name', 'opportunity__title']
    date_hierarchy = 'activity_date'
    
    fieldsets = (
        ('Activity', {
            'fields': ('activity_type', 'subject', 'description')
        }),
        ('Links', {
            'fields': ('client', 'opportunity', 'contact')
        }),
        ('Timing', {
            'fields': ('activity_date', 'duration_minutes')
        }),
        ('Participants', {
            'fields': ('participants',)
        }),
        ('Outcome', {
            'fields': ('outcome', 'outcome_notes')
        }),
        ('Follow-up', {
            'fields': ('next_action', 'next_action_date', 'follow_up_assigned_to', 'is_completed', 'completed_date')
        }),
    )


class ProposalLineItemInline(admin.TabularInline):
    model = ProposalLineItem
    extra = 1
    fields = ['service', 'description', 'quantity', 'unit', 'unit_price', 'sequence']


@admin.register(ServiceProposal)
class ServiceProposalAdmin(admin.ModelAdmin):
    list_display = ['proposal_number', 'title', 'opportunity', 'client', 'status', 'total_amount', 'valid_until', 'prepared_by']
    list_filter = ['status', 'prepared_by']
    search_fields = ['proposal_number', 'title', 'client__company_name', 'opportunity__title']
    date_hierarchy = 'proposal_date'
    inlines = [ProposalLineItemInline]
    
    fieldsets = (
        ('Proposal Details', {
            'fields': ('proposal_number', 'title', 'opportunity', 'client')
        }),
        ('Content', {
            'fields': ('introduction', 'scope_of_work', 'terms_and_conditions')
        }),
        ('Status', {
            'fields': ('status', 'valid_until', 'sent_date', 'viewed_date', 'response_date')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'discount_percentage', 'discount_amount', 'vat_percentage', 'vat_amount', 'total_amount')
        }),
        ('Contacts', {
            'fields': ('prepared_by', 'contact_person')
        }),
        ('Client Response', {
            'fields': ('rejection_reason', 'client_feedback'),
            'classes': ('collapse',)
        }),
        ('Document', {
            'fields': ('proposal_document',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Tenant', {
            'fields': ('campus',)
        }),
    )
    readonly_fields = ['proposal_number', 'subtotal', 'discount_amount', 'vat_amount', 'total_amount']


# =============================================================================
# SERVICE DELIVERY PROJECT ADMIN
# =============================================================================

class ProjectMilestoneInline(admin.TabularInline):
    model = ProjectMilestone
    extra = 0
    fields = ['name', 'sequence', 'status', 'planned_start_date', 'planned_end_date', 'assigned_to', 'weight']


class ProjectDocumentInline(admin.TabularInline):
    model = ProjectDocument
    extra = 0
    fields = ['name', 'document_type', 'file', 'upload_date', 'uploaded_by']
    readonly_fields = ['upload_date', 'uploaded_by']


@admin.register(ServiceDeliveryProject)
class ServiceDeliveryProjectAdmin(admin.ModelAdmin):
    list_display = ['project_number', 'name', 'client', 'status', 'health', 'progress_percentage', 'planned_end_date', 'project_manager']
    list_filter = ['status', 'health', 'project_manager']
    search_fields = ['project_number', 'name', 'client__company_name', 'subscription__service__name']
    date_hierarchy = 'created_at'
    filter_horizontal = ['team_members']
    inlines = [ProjectMilestoneInline, ProjectDocumentInline]
    
    fieldsets = (
        ('Project Details', {
            'fields': ('project_number', 'name', 'description')
        }),
        ('Links', {
            'fields': ('subscription', 'client', 'training_notification')
        }),
        ('Status', {
            'fields': ('status', 'health', 'health_notes', 'progress_percentage')
        }),
        ('Dates', {
            'fields': ('planned_start_date', 'actual_start_date', 'planned_end_date', 'actual_end_date')
        }),
        ('Team', {
            'fields': ('project_manager', 'team_members', 'client_contact')
        }),
        ('Budget', {
            'fields': ('budget', 'actual_cost')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Tenant', {
            'fields': ('campus',)
        }),
    )
    readonly_fields = ['project_number']


class MilestoneTaskInline(admin.TabularInline):
    model = MilestoneTask
    extra = 0
    fields = ['title', 'status', 'priority', 'assigned_to', 'due_date']


@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
    list_display = ['project', 'name', 'sequence', 'status', 'planned_end_date', 'assigned_to', 'is_overdue']
    list_filter = ['status', 'project']
    search_fields = ['name', 'project__name', 'project__project_number']
    inlines = [MilestoneTaskInline]


@admin.register(MilestoneTask)
class MilestoneTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'milestone', 'status', 'priority', 'assigned_to', 'due_date']
    list_filter = ['status', 'priority', 'assigned_to']
    search_fields = ['title', 'milestone__name', 'milestone__project__name']


@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'document_type', 'upload_date', 'uploaded_by', 'version']
    list_filter = ['document_type', 'uploaded_by']
    search_fields = ['name', 'project__name', 'project__project_number']


class ServiceDeliveryTemplateMilestoneInline(admin.TabularInline):
    model = ServiceDeliveryTemplateMilestone
    extra = 1
    fields = ['name', 'sequence', 'days_from_start', 'duration_days', 'weight', 'requires_evidence']


@admin.register(ServiceDeliveryTemplate)
class ServiceDeliveryTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'service_type', 'default_duration_days', 'is_active']
    list_filter = ['service_type', 'is_active']
    search_fields = ['name']
    inlines = [ServiceDeliveryTemplateMilestoneInline]


# =============================================================================
# WORKPLACE STINT ADMIN (QCTO Structure)
# =============================================================================

@admin.register(WorkplaceStint)
class WorkplaceStintAdmin(admin.ModelAdmin):
    """
    Admin for managing workplace stint requirements per qualification
    QCTO qualifications typically have 3 workplace stints spread across program years
    """
    list_display = ['qualification', 'stint_number', 'year_level', 'duration_days_required', 'duration_weeks', 'is_active']
    list_filter = ['qualification', 'year_level', 'stint_number', 'is_active']
    search_fields = ['qualification__saqa_id', 'qualification__title', 'title', 'description']
    ordering = ['qualification', 'stint_number']
    list_editable = ['duration_days_required', 'year_level']
    raw_id_fields = ['qualification']
    filter_horizontal = ['modules']
    
    fieldsets = (
        ('Qualification', {
            'fields': ('qualification',)
        }),
        ('Stint Details', {
            'fields': ('stint_number', 'title', 'year_level', 'description')
        }),
        ('Duration Requirements', {
            'fields': ('duration_days_required', 'duration_weeks'),
            'description': 'duration_weeks is auto-calculated from days / 5'
        }),
        ('Linked Modules', {
            'fields': ('modules',),
            'description': 'Workplace modules to be completed during this stint'
        }),
        ('Status', {
            'fields': ('sequence_order', 'is_active')
        }),
    )
    
    readonly_fields = ['duration_weeks']


# =============================================================================
# WSP/ATR SERVICE ENHANCEMENT ADMIN
# =============================================================================

class WSPATREmployeeDataInline(admin.TabularInline):
    model = WSPATREmployeeData
    extra = 0
    fields = ['occupational_level', 'african_male', 'african_female', 'coloured_male', 'coloured_female',
              'indian_male', 'indian_female', 'white_male', 'white_female', 'disabled_male', 'disabled_female']


class WSPATRTrainingDataInline(admin.TabularInline):
    model = WSPATRTrainingData
    extra = 0
    fields = ['data_type', 'intervention_type', 'programme_name', 'total_learners', 'estimated_cost']
    readonly_fields = ['total_learners']


class WSPATRPivotalDataInline(admin.TabularInline):
    model = WSPATRPivotalData
    extra = 0
    fields = ['pivotal_type', 'programme_name', 'planned_beneficiaries', 'actual_beneficiaries', 'planned_cost']


@admin.register(WSPATRServiceYear)
class WSPATRServiceYearAdmin(admin.ModelAdmin):
    list_display = ['client', 'financial_year_display', 'status', 'outcome', 'submission_deadline', 
                    'submitted_date', 'progress_percentage', 'assigned_consultant']
    list_filter = ['status', 'outcome', 'financial_year', 'seta']
    search_fields = ['client__company_name', 'seta_reference']
    date_hierarchy = 'submission_deadline'
    list_editable = ['status']
    raw_id_fields = ['client', 'subscription', 'wsp_submission', 'atr_submission']
    inlines = [WSPATREmployeeDataInline, WSPATRTrainingDataInline, WSPATRPivotalDataInline]
    
    fieldsets = (
        ('Client & Subscription', {
            'fields': ('subscription', 'client', 'financial_year')
        }),
        ('Linked Submissions', {
            'fields': ('wsp_submission', 'atr_submission'),
            'classes': ('collapse',)
        }),
        ('Status & Outcome', {
            'fields': ('status', 'outcome', 'progress_percentage')
        }),
        ('Key Dates', {
            'fields': ('submission_deadline', 'submitted_date', 'outcome_date')
        }),
        ('SETA Information', {
            'fields': ('seta', 'seta_reference', 'seta_feedback')
        }),
        ('Assignment', {
            'fields': ('assigned_consultant',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# TRAINING COMMITTEE ADMIN
# =============================================================================

class TrainingCommitteeMemberInline(admin.TabularInline):
    model = TrainingCommitteeMember
    extra = 0
    fields = ['contact', 'name', 'role', 'email', 'is_active', 'receives_meeting_invites']
    raw_id_fields = ['contact']


@admin.register(TrainingCommittee)
class TrainingCommitteeAdmin(admin.ModelAdmin):
    list_display = ['client', 'name', 'meeting_frequency', 'member_count', 'is_active', 'send_calendar_invites']
    list_filter = ['meeting_frequency', 'is_active', 'send_calendar_invites', 'include_zoom_link']
    search_fields = ['client__company_name', 'name']
    inlines = [TrainingCommitteeMemberInline]
    
    fieldsets = (
        ('Client', {
            'fields': ('client', 'name')
        }),
        ('Constitution', {
            'fields': ('constitution_date', 'constitution_document')
        }),
        ('Meeting Settings', {
            'fields': ('meeting_frequency', 'default_meeting_duration_minutes', 
                       'send_calendar_invites', 'include_zoom_link')
        }),
        ('Status', {
            'fields': ('is_active', 'notes')
        }),
    )


@admin.register(TrainingCommitteeMember)
class TrainingCommitteeMemberAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'committee', 'role', 'display_email', 'is_active', 'receives_meeting_invites']
    list_filter = ['role', 'is_active', 'receives_meeting_invites', 'committee__client']
    search_fields = ['name', 'email', 'contact__first_name', 'contact__last_name', 
                     'committee__client__company_name']
    raw_id_fields = ['committee', 'contact']


@admin.register(MeetingTemplate)
class MeetingTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'quarter', 'suggested_month', 'is_active']
    list_filter = ['quarter', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['quarter']


class TCMeetingAgendaItemInline(admin.TabularInline):
    model = TCMeetingAgendaItem
    extra = 0
    fields = ['sequence', 'title', 'duration_minutes', 'presenter', 'is_discussed']
    ordering = ['sequence']


class TCMeetingAttendanceInline(admin.TabularInline):
    model = TCMeetingAttendance
    extra = 0
    fields = ['member', 'status', 'invite_sent', 'arrival_time', 'departure_time']


class TCMeetingActionItemInline(admin.TabularInline):
    model = TCMeetingActionItem
    extra = 0
    fields = ['description', 'assigned_to', 'due_date', 'priority', 'status']


@admin.register(TrainingCommitteeMeeting)
class TrainingCommitteeMeetingAdmin(admin.ModelAdmin):
    list_display = ['title', 'committee', 'scheduled_date', 'scheduled_time', 'meeting_type', 
                    'status', 'meeting_number']
    list_filter = ['status', 'meeting_type', 'committee__client']
    search_fields = ['title', 'committee__client__company_name']
    date_hierarchy = 'scheduled_date'
    raw_id_fields = ['committee', 'service_year', 'template', 'organized_by']
    inlines = [TCMeetingAgendaItemInline, TCMeetingAttendanceInline, TCMeetingActionItemInline]
    
    fieldsets = (
        ('Committee & Context', {
            'fields': ('committee', 'service_year', 'template')
        }),
        ('Meeting Details', {
            'fields': ('title', 'meeting_number', 'status')
        }),
        ('Scheduling', {
            'fields': ('scheduled_date', 'scheduled_time', 'duration_minutes')
        }),
        ('Location', {
            'fields': ('meeting_type', 'location', 'meeting_link', 'meeting_id', 'meeting_password')
        }),
        ('Invitations', {
            'fields': ('organized_by', 'invites_sent_date', 'reminder_sent_date')
        }),
        ('Actual Times', {
            'fields': ('actual_start_time', 'actual_end_time'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['send_meeting_invites', 'send_meeting_reminders']
    
    @admin.action(description='Send meeting invites to all members')
    def send_meeting_invites(self, request, queryset):
        from .meeting_invites import MeetingInviteService
        total_sent = 0
        for meeting in queryset:
            service = MeetingInviteService(meeting)
            result = service.send_invites()
            total_sent += result['sent']
        self.message_user(request, f'Sent {total_sent} invites for {queryset.count()} meeting(s).')
    
    @admin.action(description='Send meeting reminders')
    def send_meeting_reminders(self, request, queryset):
        from .meeting_invites import MeetingInviteService
        total_sent = 0
        for meeting in queryset:
            service = MeetingInviteService(meeting)
            result = service.send_reminder()
            total_sent += result['sent']
        self.message_user(request, f'Sent {total_sent} reminders for {queryset.count()} meeting(s).')


@admin.register(MeetingMinutes)
class MeetingMinutesAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'status', 'approved_date', 'approved_by']
    list_filter = ['status']
    search_fields = ['meeting__title', 'meeting__committee__client__company_name']
    raw_id_fields = ['meeting', 'approved_by']


@admin.register(TCMeetingActionItem)
class TCMeetingActionItemAdmin(admin.ModelAdmin):
    list_display = ['description_short', 'meeting', 'assigned_to', 'due_date', 'priority', 'status']
    list_filter = ['status', 'priority', 'meeting__committee__client']
    search_fields = ['description', 'meeting__title']
    date_hierarchy = 'due_date'
    list_editable = ['status', 'priority']
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Description'


# =============================================================================
# SETA EXPORT TEMPLATE ADMIN
# =============================================================================

@admin.register(SETAExportTemplate)
class SETAExportTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'seta', 'export_type', 'file_format', 'version', 'is_active']
    list_filter = ['seta', 'export_type', 'file_format', 'is_active']
    search_fields = ['name', 'seta__name', 'description']
    
    fieldsets = (
        ('Template Information', {
            'fields': ('seta', 'name', 'description', 'export_type')
        }),
        ('Format', {
            'fields': ('file_format', 'template_file')
        }),
        ('Column Mappings', {
            'fields': ('column_mappings',),
            'description': 'JSON format: [{"source_field": "...", "export_column": "...", "format": "...", "required": true}]'
        }),
        ('Version Control', {
            'fields': ('version', 'effective_date', 'superseded_date', 'is_active')
        }),
    )


# =============================================================================
# EMPLOYMENT EQUITY (EE) ADMIN
# =============================================================================

class OccupationalLevelDataInline(admin.TabularInline):
    model = OccupationalLevelData
    extra = 0
    fields = [
        'occupational_level', 'african_male', 'african_female',
        'coloured_male', 'coloured_female', 'indian_male', 'indian_female',
        'white_male', 'white_female', 'foreign_male', 'foreign_female', 'total_employees'
    ]


@admin.register(ClientEmployeeSnapshot)
class ClientEmployeeSnapshotAdmin(admin.ModelAdmin):
    list_display = ['client', 'snapshot_date', 'snapshot_type', 'total_employees', 'is_verified', 'created_at']
    list_filter = ['snapshot_type', 'is_verified', 'snapshot_date']
    search_fields = ['client__company_name']
    date_hierarchy = 'snapshot_date'
    raw_id_fields = ['client', 'verified_by', 'created_by']
    inlines = [OccupationalLevelDataInline]
    
    fieldsets = (
        ('Snapshot Information', {
            'fields': ('client', 'snapshot_date', 'snapshot_type', 'source_description')
        }),
        ('Total Counts', {
            'fields': ('total_employees', 'total_disabled')
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_by', 'verified_at')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at']


@admin.register(EEServiceYear)
class EEServiceYearAdmin(admin.ModelAdmin):
    list_display = ['client', 'reporting_year', 'status', 'submission_deadline', 'progress_percentage', 'assigned_consultant']
    list_filter = ['status', 'reporting_year']
    search_fields = ['client__company_name']
    date_hierarchy = 'submission_deadline'
    raw_id_fields = ['client', 'subscription', 'employee_snapshot', 'assigned_consultant']
    list_editable = ['status']
    
    fieldsets = (
        ('Service Year Information', {
            'fields': ('client', 'subscription', 'reporting_year')
        }),
        ('Key Dates', {
            'fields': ('submission_deadline', 'submitted_date', 'outcome_date')
        }),
        ('Status & Progress', {
            'fields': ('status', 'outcome', 'progress_percentage')
        }),
        ('Workforce Data', {
            'fields': ('employee_snapshot', 'ee_plan')
        }),
        ('Assignment', {
            'fields': ('assigned_consultant',)
        }),
        ('DEL Reference', {
            'fields': ('del_reference_number', 'ee_certificate_number', 'del_feedback'),
            'classes': ('collapse',)
        }),
    )


class EEBarrierInline(admin.TabularInline):
    model = EEBarrier
    extra = 0
    fields = ['category', 'description', 'status']


@admin.register(EEPlan)
class EEPlanAdmin(admin.ModelAdmin):
    list_display = ['client', 'plan_name', 'start_date', 'end_date', 'duration_years', 'status']
    list_filter = ['status', 'duration_years']
    search_fields = ['client__company_name', 'plan_name']
    date_hierarchy = 'start_date'
    raw_id_fields = ['client']
    
    fieldsets = (
        ('Plan Information', {
            'fields': ('client', 'plan_name', 'duration_years', 'start_date', 'end_date')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Approval', {
            'fields': ('approved_by_name', 'approved_by_designation', 'approval_date')
        }),
        ('Consultation', {
            'fields': ('consultation_completed', 'consultation_date'),
            'classes': ('collapse',)
        }),
        ('Documents', {
            'fields': ('plan_document',)
        }),
    )


@admin.register(EEAnalysis)
class EEAnalysisAdmin(admin.ModelAdmin):
    list_display = ['service_year', 'analysis_start_date', 'analysis_completion_date', 'workforce_analysis_complete']
    search_fields = ['service_year__client__company_name']
    date_hierarchy = 'analysis_start_date'
    raw_id_fields = ['service_year']
    
    fieldsets = (
        ('Analysis Information', {
            'fields': ('service_year', 'analysis_start_date', 'analysis_completion_date')
        }),
        ('Status', {
            'fields': ('workforce_analysis_complete',)
        }),
        ('Findings', {
            'fields': ('policies_reviewed', 'barriers_identified', 'affirmative_measures'),
            'classes': ('collapse',)
        }),
        ('Documents', {
            'fields': ('analysis_document',)
        }),
    )


@admin.register(EEBarrier)
class EEBarrierAdmin(admin.ModelAdmin):
    list_display = ['description_short', 'service_year', 'category', 'status', 'target_date']
    list_filter = ['category', 'status']
    search_fields = ['description', 'service_year__client__company_name']
    list_editable = ['status']
    raw_id_fields = ['service_year']
    
    fieldsets = (
        ('Barrier Information', {
            'fields': ('service_year', 'category', 'description')
        }),
        ('Affected Groups', {
            'fields': ('affects_african', 'affects_coloured', 'affects_indian', 'affects_women', 'affects_disabled')
        }),
        ('Remediation', {
            'fields': ('proposed_measure', 'responsible_person', 'target_date')
        }),
        ('Status', {
            'fields': ('status', 'addressed_date', 'outcome_notes')
        }),
    )
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Description'


@admin.register(EENumericalGoal)
class EENumericalGoalAdmin(admin.ModelAdmin):
    list_display = ['ee_plan', 'occupational_level', 'target_year', 'total_target', 'total_actual']
    list_filter = ['occupational_level', 'target_year']
    search_fields = ['ee_plan__client__company_name']
    raw_id_fields = ['ee_plan']
    
    fieldsets = (
        ('Goal Information', {
            'fields': ('ee_plan', 'occupational_level', 'target_year')
        }),
        ('Targets - African', {
            'fields': ('african_male_target', 'african_female_target')
        }),
        ('Targets - Coloured', {
            'fields': ('coloured_male_target', 'coloured_female_target')
        }),
        ('Targets - Indian', {
            'fields': ('indian_male_target', 'indian_female_target')
        }),
        ('Targets - White', {
            'fields': ('white_male_target', 'white_female_target')
        }),
        ('Targets - Disabled', {
            'fields': ('disabled_target',)
        }),
        ('Actuals', {
            'fields': ('actual_african_male', 'actual_african_female', 'actual_coloured_male', 'actual_coloured_female', 
                       'actual_indian_male', 'actual_indian_female', 'actual_white_male', 'actual_white_female', 'actual_disabled'),
            'classes': ('collapse',)
        }),
    )
    
    def total_target(self, obj):
        return obj.total_target
    total_target.short_description = 'Total Target'
    
    def total_actual(self, obj):
        return obj.total_actual
    total_actual.short_description = 'Total Actual'


@admin.register(EEIncomeDifferential)
class EEIncomeDifferentialAdmin(admin.ModelAdmin):
    list_display = ['service_year', 'occupational_level']
    list_filter = ['occupational_level']
    search_fields = ['service_year__client__company_name']
    raw_id_fields = ['service_year']
    
    fieldsets = (
        ('Information', {
            'fields': ('service_year', 'occupational_level')
        }),
        ('African', {
            'fields': ('african_male_avg', 'african_female_avg')
        }),
        ('Coloured', {
            'fields': ('coloured_male_avg', 'coloured_female_avg')
        }),
        ('Indian', {
            'fields': ('indian_male_avg', 'indian_female_avg')
        }),
        ('White', {
            'fields': ('white_male_avg', 'white_female_avg')
        }),
    )


@admin.register(EEDocument)
class EEDocumentAdmin(admin.ModelAdmin):
    list_display = ['name_display', 'service_year', 'document_type', 'status', 'uploaded_at']
    list_filter = ['document_type', 'status']
    search_fields = ['name', 'service_year__client__company_name']
    raw_id_fields = ['service_year', 'meeting', 'uploaded_by']
    
    fieldsets = (
        ('Document Information', {
            'fields': ('service_year', 'document_type', 'name', 'description')
        }),
        ('File', {
            'fields': ('file', 'status')
        }),
        ('Related Meeting', {
            'fields': ('meeting',),
            'classes': ('collapse',)
        }),
        ('Upload Info', {
            'fields': ('uploaded_by', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['uploaded_at']
    
    def name_display(self, obj):
        return obj.name if obj.name else obj.get_document_type_display()
    name_display.short_description = 'Name'


# =============================================================================
# B-BBEE SERVICE ADMIN
# =============================================================================

class BBBEEDocumentInline(admin.TabularInline):
    model = BBBEEDocument
    extra = 0
    fields = ['document_type', 'name', 'status', 'file', 'is_required']


class OwnershipStructureInline(admin.StackedInline):
    model = OwnershipStructure
    extra = 0
    max_num = 1


class ManagementControlProfileInline(admin.StackedInline):
    model = ManagementControlProfile
    extra = 0
    max_num = 1


class SkillsDevelopmentElementInline(admin.StackedInline):
    model = SkillsDevelopmentElement
    extra = 0
    max_num = 1


class ESDElementInline(admin.StackedInline):
    model = ESDElement
    extra = 0
    max_num = 1


class SEDElementInline(admin.StackedInline):
    model = SEDElement
    extra = 0
    max_num = 1


@admin.register(BBBEEServiceYear)
class BBBEEServiceYearAdmin(admin.ModelAdmin):
    list_display = ['client', 'financial_year', 'enterprise_type', 'status', 'outcome', 
                   'target_verification_date', 'assigned_consultant', 'progress_percentage']
    list_filter = ['enterprise_type', 'status', 'outcome', 'financial_year']
    search_fields = ['client__company_name', 'verification_agency', 'certificate_number']
    raw_id_fields = ['subscription', 'client', 'assigned_consultant', 
                     'employee_snapshot', 'wspatr_service_year', 'ee_service_year', 'scorecard']
    date_hierarchy = 'target_verification_date'
    
    inlines = [
        OwnershipStructureInline,
        ManagementControlProfileInline,
        SkillsDevelopmentElementInline,
        ESDElementInline,
        SEDElementInline,
        BBBEEDocumentInline,
    ]
    
    fieldsets = (
        ('Client & Subscription', {
            'fields': ('subscription', 'client', 'assigned_consultant')
        }),
        ('Financial Year', {
            'fields': ('financial_year', 'year_end_month', 'enterprise_type', 'annual_turnover')
        }),
        ('Ownership (for EME/QSE Auto-Level)', {
            'fields': ('black_ownership_percentage', 'black_women_ownership_percentage'),
            'classes': ('collapse',)
        }),
        ('Status & Outcome', {
            'fields': ('status', 'outcome', 'progress_percentage')
        }),
        ('Key Dates', {
            'fields': ('target_verification_date', 'actual_verification_date', 
                      'certificate_issue_date', 'certificate_expiry_date')
        }),
        ('Verification Agency', {
            'fields': ('verification_agency', 'verification_agency_contact', 
                      'verification_agency_email', 'verification_agency_phone', 'certificate_number'),
            'classes': ('collapse',)
        }),
        ('Linked Data Sources', {
            'fields': ('scorecard', 'employee_snapshot', 'wspatr_service_year', 'ee_service_year'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(BBBEEDocument)
class BBBEEDocumentAdmin(admin.ModelAdmin):
    list_display = ['service_year', 'document_type', 'name', 'status', 'is_required', 'uploaded_at']
    list_filter = ['document_type', 'status', 'is_required']
    search_fields = ['name', 'service_year__client__company_name']
    raw_id_fields = ['service_year', 'uploaded_by']


class ShareholderInline(admin.TabularInline):
    model = Shareholder
    extra = 0
    fields = ['name', 'shareholder_type', 'demographic', 'is_black', 'is_female',
              'voting_rights_percentage', 'economic_interest_percentage', 'is_fully_vested']


@admin.register(OwnershipStructure)
class OwnershipStructureAdmin(admin.ModelAdmin):
    list_display = ['service_year', 'total_black_voting_rights', 'total_black_economic_interest',
                   'black_women_voting_rights', 'has_new_entrants', 'calculated_score']
    list_filter = ['has_new_entrants', 'ownership_fulfilled']
    search_fields = ['service_year__client__company_name']
    raw_id_fields = ['service_year']
    inlines = [ShareholderInline]


@admin.register(Shareholder)
class ShareholderAdmin(admin.ModelAdmin):
    list_display = ['name', 'ownership_structure', 'shareholder_type', 'demographic',
                   'voting_rights_percentage', 'economic_interest_percentage', 'is_black', 'is_female']
    list_filter = ['shareholder_type', 'demographic', 'is_black', 'is_female', 'is_new_entrant']
    search_fields = ['name', 'ownership_structure__service_year__client__company_name']
    raw_id_fields = ['ownership_structure']


@admin.register(ManagementControlProfile)
class ManagementControlProfileAdmin(admin.ModelAdmin):
    list_display = ['service_year', 'board_total', 'board_black', 'exec_total', 'exec_black',
                   'senior_mgmt_total', 'senior_mgmt_black', 'calculated_score']
    search_fields = ['service_year__client__company_name']
    raw_id_fields = ['service_year']
    
    fieldsets = (
        ('Service Year', {
            'fields': ('service_year',)
        }),
        ('Board of Directors', {
            'fields': ('board_total', 'board_black', 'board_black_female', 
                      'board_black_executive', 'board_black_independent')
        }),
        ('Executive Directors/C-Suite', {
            'fields': ('exec_total', 'exec_black', 'exec_black_female')
        }),
        ('Senior Management', {
            'fields': ('senior_mgmt_total', 'senior_mgmt_black', 'senior_mgmt_black_female')
        }),
        ('Middle Management', {
            'fields': ('middle_mgmt_total', 'middle_mgmt_black', 'middle_mgmt_black_female')
        }),
        ('Junior Management', {
            'fields': ('junior_mgmt_total', 'junior_mgmt_black', 'junior_mgmt_black_female')
        }),
        ('Disabilities', {
            'fields': ('disabled_in_management',)
        }),
        ('Score', {
            'fields': ('calculated_score', 'notes')
        }),
    )


@admin.register(SkillsDevelopmentElement)
class SkillsDevelopmentElementAdmin(admin.ModelAdmin):
    list_display = ['service_year', 'leviable_amount', 'total_skills_spend', 
                   'black_skills_spend', 'learnerships_total', 'calculated_score']
    search_fields = ['service_year__client__company_name']
    raw_id_fields = ['service_year']
    
    fieldsets = (
        ('Service Year', {
            'fields': ('service_year', 'leviable_amount')
        }),
        ('Skills Development Spend', {
            'fields': ('total_skills_spend', 'black_skills_spend', 
                      'black_female_skills_spend', 'black_disabled_skills_spend')
        }),
        ('Learnerships', {
            'fields': ('learnerships_total', 'learnerships_black', 'learnerships_black_female',
                      'learnerships_black_disabled', 'learnerships_black_youth')
        }),
        ('Internships', {
            'fields': ('internships_total', 'internships_black', 'internships_absorbed')
        }),
        ('Bursaries', {
            'fields': ('bursaries_total', 'bursaries_black', 'bursaries_spend')
        }),
        ('Score', {
            'fields': ('calculated_score', 'notes')
        }),
    )


class ESDSupplierInline(admin.TabularInline):
    model = ESDSupplier
    extra = 0
    fields = ['supplier_name', 'supplier_type', 'bbbee_level', 'is_eme', 'is_qse',
              'black_ownership_percentage', 'annual_spend', 'development_contribution']


@admin.register(ESDElement)
class ESDElementAdmin(admin.ModelAdmin):
    list_display = ['service_year', 'total_procurement_spend', 'bbbee_procurement_spend',
                   'supplier_dev_spend', 'enterprise_dev_spend', 'calculated_score']
    search_fields = ['service_year__client__company_name']
    raw_id_fields = ['service_year']
    inlines = [ESDSupplierInline]
    
    fieldsets = (
        ('Service Year', {
            'fields': ('service_year', 'npat')
        }),
        ('Preferential Procurement', {
            'fields': ('total_procurement_spend', 'bbbee_procurement_spend', 'qse_eme_spend',
                      'black_owned_spend', 'black_women_owned_spend', 'designated_group_spend')
        }),
        ('Supplier Development', {
            'fields': ('supplier_dev_spend', 'supplier_dev_beneficiaries')
        }),
        ('Enterprise Development', {
            'fields': ('enterprise_dev_spend', 'enterprise_dev_beneficiaries',
                      'graduated_emes', 'graduated_qses')
        }),
        ('Scores', {
            'fields': ('preferential_procurement_score', 'supplier_development_score',
                      'enterprise_development_score', 'calculated_score', 'notes')
        }),
    )


@admin.register(ESDSupplier)
class ESDSupplierAdmin(admin.ModelAdmin):
    list_display = ['supplier_name', 'esd_element', 'supplier_type', 'bbbee_level',
                   'black_ownership_percentage', 'annual_spend', 'development_contribution']
    list_filter = ['supplier_type', 'bbbee_level', 'is_eme', 'is_qse']
    search_fields = ['supplier_name', 'esd_element__service_year__client__company_name']
    raw_id_fields = ['esd_element']


class SEDContributionInline(admin.TabularInline):
    model = SEDContribution
    extra = 0
    fields = ['beneficiary_name', 'contribution_type', 'contribution_date', 
              'monetary_value', 'black_beneficiary_percentage']


@admin.register(SEDElement)
class SEDElementAdmin(admin.ModelAdmin):
    list_display = ['service_year', 'npat', 'total_sed_spend', 
                   'total_beneficiaries', 'black_beneficiaries', 'calculated_score']
    search_fields = ['service_year__client__company_name']
    raw_id_fields = ['service_year']
    inlines = [SEDContributionInline]


@admin.register(SEDContribution)
class SEDContributionAdmin(admin.ModelAdmin):
    list_display = ['beneficiary_name', 'sed_element', 'contribution_type', 
                   'contribution_date', 'monetary_value', 'black_beneficiary_percentage']
    list_filter = ['contribution_type']
    search_fields = ['beneficiary_name', 'sed_element__service_year__client__company_name']
    raw_id_fields = ['sed_element']


@admin.register(TransformationPlan)
class TransformationPlanAdmin(admin.ModelAdmin):
    list_display = ['client', 'name', 'status', 'start_date', 'end_date', 
                   'current_level', 'target_level']
    list_filter = ['status']
    search_fields = ['client__company_name', 'name']
    raw_id_fields = ['client']
    
    fieldsets = (
        ('Plan Information', {
            'fields': ('client', 'name', 'status', 'start_date', 'end_date')
        }),
        ('Current vs Target', {
            'fields': ('current_level', 'target_level')
        }),
        ('Element Targets', {
            'fields': ('ownership_target', 'management_control_target', 
                      'skills_development_target', 'esd_target', 'sed_target'),
            'classes': ('collapse',)
        }),
        ('Strategy Document', {
            'fields': ('strategy_document', 'initiatives', 'notes'),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# ONBOARDING ADMIN
# =============================================================================

class ServiceOnboardingInline(admin.TabularInline):
    model = ServiceOnboarding
    extra = 0
    fields = ['service_type', 'status', 'current_step', 'total_steps']
    show_change_link = True


@admin.register(ClientOnboarding)
class ClientOnboardingAdmin(admin.ModelAdmin):
    list_display = ['client', 'current_step', 'progress_percentage', 
                   'account_manager', 'started_at', 'completed_at']
    list_filter = ['current_step', 'account_manager', 'legacy_onboarding']
    search_fields = ['client__company_name']
    raw_id_fields = ['client', 'account_manager', 'started_by', 'company_verified_by']
    readonly_fields = ['progress_percentage', 'started_at', 'completed_at']
    inlines = [ServiceOnboardingInline]
    
    fieldsets = (
        ('Client', {
            'fields': ('client', 'account_manager', 'started_by')
        }),
        ('Progress', {
            'fields': ('current_step', 'progress_percentage', 'legacy_onboarding')
        }),
        ('Step Completion', {
            'fields': ('company_verified', 'services_configured', 
                      'contacts_invited', 'documents_initialized', 'kickoff_scheduled'),
        }),
        ('Step Details', {
            'fields': ('step_statuses',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(ServiceOnboarding)
class ServiceOnboardingAdmin(admin.ModelAdmin):
    list_display = ['subscription', 'service_type', 'status', 
                   'current_step', 'total_steps', 'progress_percentage']
    list_filter = ['status', 'service_type']
    search_fields = ['subscription__client__company_name', 'subscription__service__name']
    raw_id_fields = ['subscription', 'client_onboarding', 'assigned_to']
    readonly_fields = ['progress_percentage', 'started_at', 'completed_at']
    
    fieldsets = (
        ('Service', {
            'fields': ('subscription', 'client_onboarding', 'service_type', 'assigned_to')
        }),
        ('Progress', {
            'fields': ('status', 'current_step', 'total_steps', 'progress_percentage')
        }),
        ('Step Data', {
            'fields': ('step_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(PortalInvitation)
class PortalInvitationAdmin(admin.ModelAdmin):
    list_display = ['email', 'name', 'client', 'role', 'status', 'invited_at', 'expires_at', 'accepted_at']
    list_filter = ['status', 'role', 'permission_template']
    search_fields = ['email', 'name', 'client__company_name']
    raw_id_fields = ['client', 'contact', 'invited_by']
    readonly_fields = ['token', 'invited_at', 'accepted_at']
    
    fieldsets = (
        ('Invitation Details', {
            'fields': ('client', 'email', 'name', 'role', 'contact')
        }),
        ('Status', {
            'fields': ('status', 'token', 'expires_at')
        }),
        ('Permissions', {
            'fields': ('permission_template', 'personal_message'),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('invited_by', 'invited_at', 'accepted_at'),
            'classes': ('collapse',)
        }),
    )

