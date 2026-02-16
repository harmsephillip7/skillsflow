"""
Custom Admin URLs with Unified Theme
Routes for all model management
"""
from django.urls import path
from .admin_views import (
    # Dashboard
    AdminDashboardView,
    # Users
    UserListView, UserDetailView, UserCreateView, UserUpdateView, UserDeleteView,
    # Learners
    LearnerListView, LearnerDetailView, LearnerCreateView, LearnerUpdateView, LearnerDeleteView,
    LearnerProfileEditView, LearnerSignatureUnlockView,
    # Qualifications
    QualificationListView, QualificationDetailView, QualificationCreateView, QualificationUpdateView, QualificationDeleteView,
    # Qualification Pricing
    QualificationPricingListView, QualificationPricingCreateView, QualificationPricingUpdateView, QualificationPricingDeleteView,
    # Modules
    ModuleListView, ModuleDetailView, ModuleCreateView, ModuleUpdateView, ModuleDeleteView,
    # Unit Standards
    UnitStandardListView, UnitStandardDetailView, UnitStandardCreateView, UnitStandardUpdateView, UnitStandardDeleteView,
    # Enrollments
    EnrollmentListView, EnrollmentDetailView, EnrollmentCreateView, EnrollmentUpdateView, EnrollmentDeleteView,
    EnhancedEnrollmentEditView,
    # Corporate Clients
    CorporateClientListView, CorporateClientDetailView, CorporateClientCreateView, CorporateClientUpdateView, CorporateClientDeleteView,
    # Corporate Contacts
    CorporateContactListView, CorporateContactDetailView, CorporateContactCreateView, CorporateContactUpdateView, CorporateContactDeleteView,
    # Grant Projects
    GrantProjectListView, GrantProjectDetailView, GrantProjectCreateView, GrantProjectUpdateView, GrantProjectDeleteView,
    # Cohorts
    CohortListView, CohortDetailView, CohortCreateView, CohortUpdateView, CohortDeleteView,
    # Venues
    VenueListView, VenueDetailView, VenueCreateView, VenueUpdateView, VenueDeleteView,
    # Schedule Sessions (renamed from TrainingSession)
    ScheduleSessionListView, ScheduleSessionDetailView, ScheduleSessionCreateView, ScheduleSessionUpdateView, ScheduleSessionDeleteView,
    # Assessment Activities
    AssessmentActivityListView, AssessmentActivityDetailView, AssessmentActivityCreateView, AssessmentActivityUpdateView, AssessmentActivityDeleteView,
    # Assessment Results
    AssessmentResultListView, AssessmentResultDetailView, AssessmentResultCreateView, AssessmentResultUpdateView, AssessmentResultDeleteView,
    # PoE Submissions
    PoESubmissionListView, PoESubmissionDetailView, PoESubmissionCreateView, PoESubmissionUpdateView, PoESubmissionDeleteView,
    # Invoices
    InvoiceListView, InvoiceDetailView, InvoiceCreateView, InvoiceUpdateView, InvoiceDeleteView,
    # Payments
    PaymentListView, PaymentDetailView, PaymentCreateView, PaymentUpdateView, PaymentDeleteView,
    # Quotes (renamed from Quotation)
    QuoteListView, QuoteDetailView, QuoteCreateView, QuoteUpdateView, QuoteDeleteView,
    # SETAs
    SETAListView, SETADetailView, SETACreateView, SETAUpdateView, SETADeleteView,
    # Employers
    EmployerListView, EmployerDetailView, EmployerCreateView, EmployerUpdateView, EmployerDeleteView,
    # Brands
    BrandListView, BrandDetailView, BrandCreateView, BrandUpdateView, BrandDeleteView,
    # Campuses
    CampusListView, CampusDetailView, CampusCreateView, CampusUpdateView, CampusDeleteView,
    # Contracts
    ContractListView, ContractDetailView, ContractCreateView, ContractUpdateView, ContractDeleteView,
    TerminateLearnerView, AddReplacementLearnerView, AddLearnerToContractView,
    # Enrollment Wizard
    EnrollmentWizardView, EnrollmentWizardStartView, check_sa_id,
)

# Template Management Views
from .template_admin_views import (
    TemplateSetListView, TemplateSetDetailView, TemplateSetCreateView,
    TemplateSetUpdateView, TemplateSetArchiveView, TemplateSetRestoreView,
    TaskTemplateCreateView, TaskTemplateUpdateView, TaskTemplateArchiveView, TaskTemplateRestoreView,
)

app_name = 'admin'

urlpatterns = [
    # Dashboard
    path('', AdminDashboardView.as_view(), name='dashboard'),
    
    # =====================================================
    # USERS
    # =====================================================
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/create/', UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/edit/', UserUpdateView.as_view(), name='user_edit'),
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user_delete'),
    
    # =====================================================
    # LEARNERS
    # =====================================================
    path('learners/', LearnerListView.as_view(), name='learner_list'),
    path('learners/create/', LearnerCreateView.as_view(), name='learner_create'),
    path('learners/<int:pk>/', LearnerDetailView.as_view(), name='learner_detail'),
    path('learners/<int:pk>/edit/', LearnerUpdateView.as_view(), name='learner_edit'),
    path('learners/<int:pk>/profile-edit/', LearnerProfileEditView.as_view(), name='learner_profile_edit'),
    path('learners/<int:pk>/unlock-signature/', LearnerSignatureUnlockView.as_view(), name='learner_signature_unlock'),
    path('learners/<int:pk>/delete/', LearnerDeleteView.as_view(), name='learner_delete'),
    
    # =====================================================
    # QUALIFICATIONS
    # =====================================================
    path('qualifications/', QualificationListView.as_view(), name='qualification_list'),
    path('qualifications/create/', QualificationCreateView.as_view(), name='qualification_create'),
    path('qualifications/<int:pk>/', QualificationDetailView.as_view(), name='qualification_detail'),
    path('qualifications/<int:pk>/edit/', QualificationUpdateView.as_view(), name='qualification_edit'),
    path('qualifications/<int:pk>/delete/', QualificationDeleteView.as_view(), name='qualification_delete'),
    
    # Qualification Pricing
    path('qualifications/<int:qualification_id>/pricing/', QualificationPricingListView.as_view(), name='qualificationpricing_list'),
    path('qualifications/<int:qualification_id>/pricing/add/', QualificationPricingCreateView.as_view(), name='qualificationpricing_create'),
    path('pricing/<int:pk>/edit/', QualificationPricingUpdateView.as_view(), name='qualificationpricing_edit'),
    path('pricing/<int:pk>/delete/', QualificationPricingDeleteView.as_view(), name='qualificationpricing_delete'),
    
    # =====================================================
    # MODULES
    # =====================================================
    path('modules/', ModuleListView.as_view(), name='module_list'),
    path('modules/create/', ModuleCreateView.as_view(), name='module_create'),
    path('modules/<int:pk>/', ModuleDetailView.as_view(), name='module_detail'),
    path('modules/<int:pk>/edit/', ModuleUpdateView.as_view(), name='module_edit'),
    path('modules/<int:pk>/delete/', ModuleDeleteView.as_view(), name='module_delete'),
    
    # =====================================================
    # UNIT STANDARDS
    # =====================================================
    path('unit-standards/', UnitStandardListView.as_view(), name='unitstandard_list'),
    path('unit-standards/create/', UnitStandardCreateView.as_view(), name='unitstandard_create'),
    path('unit-standards/<int:pk>/', UnitStandardDetailView.as_view(), name='unitstandard_detail'),
    path('unit-standards/<int:pk>/edit/', UnitStandardUpdateView.as_view(), name='unitstandard_edit'),
    path('unit-standards/<int:pk>/delete/', UnitStandardDeleteView.as_view(), name='unitstandard_delete'),
    
    # =====================================================
    # ENROLLMENTS
    # =====================================================
    path('enrollments/', EnrollmentListView.as_view(), name='enrollment_list'),
    path('enrollments/wizard/', EnrollmentWizardView.as_view(), name='enrollment_wizard'),
    path('enrollments/wizard/start/', EnrollmentWizardStartView.as_view(), name='enrollment_wizard_start'),
    path('enrollments/create/', EnrollmentWizardStartView.as_view(), name='enrollment_create'),  # Redirect to wizard
    path('enrollments/<int:pk>/', EnrollmentDetailView.as_view(), name='enrollment_detail'),
    path('enrollments/<int:pk>/edit/', EnhancedEnrollmentEditView.as_view(), name='enrollment_edit'),
    path('enrollments/<int:pk>/quick-edit/', EnrollmentUpdateView.as_view(), name='enrollment_quick_edit'),  # Legacy simple form
    path('enrollments/<int:pk>/delete/', EnrollmentDeleteView.as_view(), name='enrollment_delete'),
    
    # SA ID Check API
    path('api/check-sa-id/', check_sa_id, name='check_sa_id'),
    
    # =====================================================
    # CORPORATE CLIENTS
    # =====================================================
    path('corporate-clients/', CorporateClientListView.as_view(), name='corporateclient_list'),
    path('corporate-clients/create/', CorporateClientCreateView.as_view(), name='corporateclient_create'),
    path('corporate-clients/<int:pk>/', CorporateClientDetailView.as_view(), name='corporateclient_detail'),
    path('corporate-clients/<int:pk>/edit/', CorporateClientUpdateView.as_view(), name='corporateclient_edit'),
    path('corporate-clients/<int:pk>/delete/', CorporateClientDeleteView.as_view(), name='corporateclient_delete'),
    
    # =====================================================
    # CORPORATE CONTACTS
    # =====================================================
    path('corporate-contacts/', CorporateContactListView.as_view(), name='corporatecontact_list'),
    path('corporate-contacts/create/', CorporateContactCreateView.as_view(), name='corporatecontact_create'),
    path('corporate-contacts/<int:pk>/', CorporateContactDetailView.as_view(), name='corporatecontact_detail'),
    path('corporate-contacts/<int:pk>/edit/', CorporateContactUpdateView.as_view(), name='corporatecontact_edit'),
    path('corporate-contacts/<int:pk>/delete/', CorporateContactDeleteView.as_view(), name='corporatecontact_delete'),
    
    # =====================================================
    # GRANT PROJECTS
    # =====================================================
    path('grant-projects/', GrantProjectListView.as_view(), name='grantproject_list'),
    path('grant-projects/create/', GrantProjectCreateView.as_view(), name='grantproject_create'),
    path('grant-projects/<int:pk>/', GrantProjectDetailView.as_view(), name='grantproject_detail'),
    path('grant-projects/<int:pk>/edit/', GrantProjectUpdateView.as_view(), name='grantproject_edit'),
    path('grant-projects/<int:pk>/delete/', GrantProjectDeleteView.as_view(), name='grantproject_delete'),
    
    # =====================================================
    # COHORTS
    # =====================================================
    path('cohorts/', CohortListView.as_view(), name='cohort_list'),
    path('cohorts/create/', CohortCreateView.as_view(), name='cohort_create'),
    path('cohorts/<int:pk>/', CohortDetailView.as_view(), name='cohort_detail'),
    path('cohorts/<int:pk>/edit/', CohortUpdateView.as_view(), name='cohort_edit'),
    path('cohorts/<int:pk>/delete/', CohortDeleteView.as_view(), name='cohort_delete'),
    
    # =====================================================
    # VENUES
    # =====================================================
    path('venues/', VenueListView.as_view(), name='venue_list'),
    path('venues/create/', VenueCreateView.as_view(), name='venue_create'),
    path('venues/<int:pk>/', VenueDetailView.as_view(), name='venue_detail'),
    path('venues/<int:pk>/edit/', VenueUpdateView.as_view(), name='venue_edit'),
    path('venues/<int:pk>/delete/', VenueDeleteView.as_view(), name='venue_delete'),
    
    # =====================================================
    # SCHEDULE SESSIONS (renamed from Training Sessions)
    # =====================================================
    path('sessions/', ScheduleSessionListView.as_view(), name='schedulesession_list'),
    path('sessions/create/', ScheduleSessionCreateView.as_view(), name='schedulesession_create'),
    path('sessions/<int:pk>/', ScheduleSessionDetailView.as_view(), name='schedulesession_detail'),
    path('sessions/<int:pk>/edit/', ScheduleSessionUpdateView.as_view(), name='schedulesession_edit'),
    path('sessions/<int:pk>/delete/', ScheduleSessionDeleteView.as_view(), name='schedulesession_delete'),
    
    # =====================================================
    # ASSESSMENT ACTIVITIES
    # =====================================================
    path('assessment-activities/', AssessmentActivityListView.as_view(), name='assessmentactivity_list'),
    path('assessment-activities/create/', AssessmentActivityCreateView.as_view(), name='assessmentactivity_create'),
    path('assessment-activities/<int:pk>/', AssessmentActivityDetailView.as_view(), name='assessmentactivity_detail'),
    path('assessment-activities/<int:pk>/edit/', AssessmentActivityUpdateView.as_view(), name='assessmentactivity_edit'),
    path('assessment-activities/<int:pk>/delete/', AssessmentActivityDeleteView.as_view(), name='assessmentactivity_delete'),
    
    # =====================================================
    # ASSESSMENT RESULTS
    # =====================================================
    path('assessment-results/', AssessmentResultListView.as_view(), name='assessmentresult_list'),
    path('assessment-results/create/', AssessmentResultCreateView.as_view(), name='assessmentresult_create'),
    path('assessment-results/<int:pk>/', AssessmentResultDetailView.as_view(), name='assessmentresult_detail'),
    path('assessment-results/<int:pk>/edit/', AssessmentResultUpdateView.as_view(), name='assessmentresult_edit'),
    path('assessment-results/<int:pk>/delete/', AssessmentResultDeleteView.as_view(), name='assessmentresult_delete'),
    
    # =====================================================
    # POE SUBMISSIONS
    # =====================================================
    path('poe-submissions/', PoESubmissionListView.as_view(), name='poesubmission_list'),
    path('poe-submissions/create/', PoESubmissionCreateView.as_view(), name='poesubmission_create'),
    path('poe-submissions/<int:pk>/', PoESubmissionDetailView.as_view(), name='poesubmission_detail'),
    path('poe-submissions/<int:pk>/edit/', PoESubmissionUpdateView.as_view(), name='poesubmission_edit'),
    path('poe-submissions/<int:pk>/delete/', PoESubmissionDeleteView.as_view(), name='poesubmission_delete'),
    
    # =====================================================
    # INVOICES
    # =====================================================
    path('invoices/', InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/create/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/edit/', InvoiceUpdateView.as_view(), name='invoice_edit'),
    path('invoices/<int:pk>/delete/', InvoiceDeleteView.as_view(), name='invoice_delete'),
    
    # =====================================================
    # PAYMENTS
    # =====================================================
    path('payments/', PaymentListView.as_view(), name='payment_list'),
    path('payments/create/', PaymentCreateView.as_view(), name='payment_create'),
    path('payments/<int:pk>/', PaymentDetailView.as_view(), name='payment_detail'),
    path('payments/<int:pk>/edit/', PaymentUpdateView.as_view(), name='payment_edit'),
    path('payments/<int:pk>/delete/', PaymentDeleteView.as_view(), name='payment_delete'),
    
    # =====================================================
    # QUOTES (renamed from Quotations)
    # =====================================================
    path('quotes/', QuoteListView.as_view(), name='quote_list'),
    path('quotes/create/', QuoteCreateView.as_view(), name='quote_create'),
    path('quotes/<int:pk>/', QuoteDetailView.as_view(), name='quote_detail'),
    path('quotes/<int:pk>/edit/', QuoteUpdateView.as_view(), name='quote_edit'),
    path('quotes/<int:pk>/delete/', QuoteDeleteView.as_view(), name='quote_delete'),
    
    # =====================================================
    # SETAs
    # =====================================================
    path('setas/', SETAListView.as_view(), name='seta_list'),
    path('setas/create/', SETACreateView.as_view(), name='seta_create'),
    path('setas/<int:pk>/', SETADetailView.as_view(), name='seta_detail'),
    path('setas/<int:pk>/edit/', SETAUpdateView.as_view(), name='seta_edit'),
    path('setas/<int:pk>/delete/', SETADeleteView.as_view(), name='seta_delete'),
    
    # =====================================================
    # EMPLOYERS
    # =====================================================
    path('employers/', EmployerListView.as_view(), name='employer_list'),
    path('employers/create/', EmployerCreateView.as_view(), name='employer_create'),
    path('employers/<int:pk>/', EmployerDetailView.as_view(), name='employer_detail'),
    path('employers/<int:pk>/edit/', EmployerUpdateView.as_view(), name='employer_edit'),
    path('employers/<int:pk>/delete/', EmployerDeleteView.as_view(), name='employer_delete'),
    
    # =====================================================
    # PROJECT TEMPLATE SETS
    # =====================================================
    path('template-sets/', TemplateSetListView.as_view(), name='templateset_list'),
    path('template-sets/create/', TemplateSetCreateView.as_view(), name='templateset_create'),
    path('template-sets/<int:pk>/', TemplateSetDetailView.as_view(), name='templateset_detail'),
    path('template-sets/<int:pk>/edit/', TemplateSetUpdateView.as_view(), name='templateset_edit'),
    path('template-sets/<int:pk>/archive/', TemplateSetArchiveView.as_view(), name='templateset_archive'),
    path('template-sets/<int:pk>/restore/', TemplateSetRestoreView.as_view(), name='templateset_restore'),
    
    # =====================================================
    # PROJECT TASK TEMPLATES
    # =====================================================
    path('template-sets/<int:set_pk>/tasks/create/', TaskTemplateCreateView.as_view(), name='tasktemplate_create'),
    path('task-templates/<int:pk>/edit/', TaskTemplateUpdateView.as_view(), name='tasktemplate_edit'),
    path('task-templates/<int:pk>/archive/', TaskTemplateArchiveView.as_view(), name='tasktemplate_archive'),
    path('task-templates/<int:pk>/restore/', TaskTemplateRestoreView.as_view(), name='tasktemplate_restore'),
    
    # =====================================================
    # BRANDS
    # =====================================================
    path('brands/', BrandListView.as_view(), name='brand_list'),
    path('brands/create/', BrandCreateView.as_view(), name='brand_create'),
    path('brands/<int:pk>/', BrandDetailView.as_view(), name='brand_detail'),
    path('brands/<int:pk>/edit/', BrandUpdateView.as_view(), name='brand_edit'),
    path('brands/<int:pk>/delete/', BrandDeleteView.as_view(), name='brand_delete'),
    
    # =====================================================
    # CAMPUSES
    # =====================================================
    path('campuses/', CampusListView.as_view(), name='campus_list'),
    path('campuses/create/', CampusCreateView.as_view(), name='campus_create'),
    path('campuses/<int:pk>/', CampusDetailView.as_view(), name='campus_detail'),
    path('campuses/<int:pk>/edit/', CampusUpdateView.as_view(), name='campus_edit'),
    path('campuses/<int:pk>/delete/', CampusDeleteView.as_view(), name='campus_delete'),
    
    # =====================================================
    # CONTRACTS
    # =====================================================
    path('contracts/', ContractListView.as_view(), name='contract_list'),
    path('contracts/create/', ContractCreateView.as_view(), name='contract_create'),
    path('contracts/<int:pk>/', ContractDetailView.as_view(), name='contract_detail'),
    path('contracts/<int:pk>/edit/', ContractUpdateView.as_view(), name='contract_edit'),
    path('contracts/<int:pk>/delete/', ContractDeleteView.as_view(), name='contract_delete'),
    path('contracts/<int:contract_pk>/add-learner/', AddLearnerToContractView.as_view(), name='contract_add_learner'),
    path('contracts/<int:contract_pk>/add-replacement/', AddReplacementLearnerView.as_view(), name='contract_add_replacement'),
    path('contracts/<int:contract_pk>/terminate/<int:enrollment_pk>/', TerminateLearnerView.as_view(), name='contract_terminate_learner'),
]
