from django.urls import path
from . import views

app_name = 'corporate'

urlpatterns = [
    # Dashboard
    path('', views.corporate_dashboard, name='dashboard'),
    
    # CRM Dashboard & Pipeline
    path('crm/', views.crm_dashboard, name='crm_dashboard'),
    
    # WSP/ATR Clients Dashboard - Overview of all WSP/ATR clients
    path('wspatr-clients/', views.wspatr_clients_dashboard, name='wspatr_clients_dashboard'),
    
    # Corporate Clients
    path('clients/', views.CorporateClientListView.as_view(), name='client_list'),
    path('clients/create/', views.CorporateClientCreateView.as_view(), name='client_create'),
    path('clients/<int:pk>/', views.CorporateClientDetailView.as_view(), name='client_detail'),
    path('clients/<int:pk>/edit/', views.CorporateClientUpdateView.as_view(), name='client_update'),
    path('clients/<int:pk>/360/', views.client_360_view, name='client_360'),
    path('clients/<int:pk>/360/<str:tab>/', views.client_360_tab, name='client_360_tab'),
    
    # ==========================================================================
    # CLIENT ONBOARDING
    # ==========================================================================
    path('clients/<int:pk>/onboarding/', views.client_onboarding_wizard, name='client_onboarding'),
    path('clients/<int:pk>/onboarding/step/<int:step>/', views.client_onboarding_step, name='client_onboarding_step'),
    path('clients/<int:client_pk>/services/<int:pk>/onboarding/', views.service_onboarding_wizard, name='service_onboarding'),
    path('clients/<int:client_pk>/services/<int:pk>/onboarding/step/<int:step>/', views.service_onboarding_step, name='service_onboarding_step'),
    
    # Portal Invitations
    path('clients/<int:client_pk>/contacts/invite/', views.contact_invite, name='contact_invite'),
    path('invitations/<uuid:token>/', views.portal_invitation_accept, name='portal_invitation_accept'),
    path('invitations/<int:pk>/resend/', views.portal_invitation_resend, name='portal_invitation_resend'),
    path('invitations/<int:pk>/revoke/', views.portal_invitation_revoke, name='portal_invitation_revoke'),
    
    # CRM Pipeline (Kanban View)
    path('crm/pipeline/', views.crm_pipeline, name='crm_pipeline'),
    path('crm/pipeline/update-stage/', views.crm_pipeline_update_stage, name='crm_pipeline_update_stage'),
    
    # Service Subscriptions
    path('clients/<int:client_pk>/add-service/', views.add_subscription, name='add_subscription'),
    path('subscriptions/<int:pk>/status/', views.update_subscription_status, name='update_subscription_status'),
    
    # Service Offerings
    path('services/', views.ServiceOfferingListView.as_view(), name='service_list'),
    path('services/<int:pk>/', views.ServiceOfferingDetailView.as_view(), name='service_detail'),
    
    # Opportunities
    path('opportunities/', views.OpportunityListView.as_view(), name='opportunity_list'),
    path('opportunities/create/', views.OpportunityCreateView.as_view(), name='opportunity_create'),
    path('opportunities/<int:pk>/', views.OpportunityDetailView.as_view(), name='opportunity_detail'),
    path('opportunities/<int:pk>/edit/', views.OpportunityUpdateView.as_view(), name='opportunity_update'),
    path('opportunities/<int:pk>/stage/', views.update_opportunity_stage, name='opportunity_stage'),
    path('opportunities/<int:pk>/convert/', views.convert_opportunity, name='opportunity_convert'),
    
    # Activities
    path('opportunities/<int:opportunity_pk>/activity/', views.add_activity, name='add_opportunity_activity'),
    path('clients/<int:client_pk>/activity/', views.add_activity, name='add_client_activity'),
    path('activities/<int:pk>/complete/', views.complete_activity, name='complete_activity'),
    
    # Proposals
    path('proposals/', views.ProposalListView.as_view(), name='proposal_list'),
    path('proposals/create/', views.ProposalCreateView.as_view(), name='proposal_create'),
    path('proposals/<int:pk>/', views.ProposalDetailView.as_view(), name='proposal_detail'),
    path('proposals/<int:pk>/edit/', views.ProposalUpdateView.as_view(), name='proposal_edit'),
    path('proposals/<int:pk>/status/', views.update_proposal_status, name='proposal_status'),
    
    # Service Delivery Projects
    path('projects/', views.DeliveryProjectListView.as_view(), name='delivery_project_list'),
    path('projects/<int:pk>/', views.DeliveryProjectDetailView.as_view(), name='delivery_project_detail'),
    path('projects/<int:project_pk>/milestone/', views.add_milestone, name='add_milestone'),
    path('subscriptions/<int:subscription_pk>/create-project/', views.create_delivery_project, name='create_delivery_project'),
    path('milestones/<int:pk>/status/', views.update_milestone_status, name='milestone_status'),
    
    # Task Management (Deliverables)
    path('milestones/<int:milestone_pk>/tasks/add/', views.add_milestone_task, name='add_milestone_task'),
    path('tasks/<int:pk>/edit/', views.edit_task, name='edit_task'),
    path('tasks/<int:pk>/delete/', views.delete_task, name='delete_task'),
    path('tasks/<int:pk>/status/', views.update_task_status, name='update_task_status'),
    path('tasks/<int:pk>/evidence/', views.add_task_evidence, name='add_task_evidence'),
    path('task-evidence/<int:pk>/delete/', views.delete_task_evidence, name='delete_task_evidence'),
    
    # Host Employers
    path('host-employers/', views.HostEmployerListView.as_view(), name='host_employer_list'),
    path('host-employers/create/', views.HostEmployerCreateView.as_view(), name='host_employer_create'),
    path('host-employers/<int:pk>/', views.HostEmployerDetailView.as_view(), name='host_employer_detail'),
    path('host-employers/<int:pk>/edit/', views.HostEmployerUpdateView.as_view(), name='host_employer_update'),
    
    # Workplace Placements
    path('placements/', views.WorkplacePlacementListView.as_view(), name='placement_list'),
    path('host-employers/<int:host_employer_pk>/placements/create/', views.create_placement, name='create_placement'),
    
    # Legacy Trade Tests (new trade test functionality moved to trade_tests app)
    path('trade-tests/', views.LegacyTradeTestBookingListView.as_view(), name='trade_test_list'),
    path('trade-tests/venues/', views.LegacyTradeTestVenueListView.as_view(), name='trade_test_venue_list'),
    path('trade-tests/create/', views.LegacyTradeTestBookingCreateView.as_view(), name='trade_test_create'),
    path('trade-tests/<int:pk>/', views.LegacyTradeTestBookingDetailView.as_view(), name='trade_test_booking_detail'),
    path('trade-tests/<int:booking_pk>/result/', views.record_legacy_trade_test_result, name='record_trade_test_result'),
    
    # WSP/ATR Management
    path('wsp-atr/', views.wsp_atr_dashboard, name='wsp_atr_dashboard'),
    path('wsp/<int:pk>/', views.wsp_detail, name='wsp_detail'),
    path('atr/<int:pk>/', views.atr_detail, name='atr_detail'),
    path('wsp-atr/<int:pk>/<str:submission_type>/evidence/', views.evidence_upload, name='wsp_atr_evidence'),
    
    # Committee Meetings
    path('clients/<int:client_pk>/meetings/', views.committee_meetings, name='committee_meetings'),
    path('meetings/<int:pk>/', views.meeting_detail, name='meeting_detail'),
    path('clients/<int:client_pk>/meetings/create/', views.meeting_create, name='meeting_create'),
    path('meetings/<int:pk>/add-action/', views.meeting_add_action_item, name='meeting_add_action'),
    path('actions/<int:pk>/status/', views.update_action_item_status, name='action_status'),
    
    # Employee Database & Qualifications
    path('clients/<int:client_pk>/employees/', views.employee_database, name='employee_database'),
    path('clients/<int:client_pk>/employees/add/', views.employee_add, name='employee_add'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/add-qualification/', views.add_employee_qualification, name='add_qualification'),
    
    # Individual Development Plans (IDP)
    path('employees/<int:employee_pk>/idps/', views.employee_idp_list, name='employee_idp_list'),
    path('employees/<int:employee_pk>/idps/create/', views.employee_idp_create, name='employee_idp_create'),
    path('idps/<int:pk>/', views.employee_idp_detail, name='employee_idp_detail'),
    path('idps/<int:pk>/sign-off/', views.employee_idp_sign_off, name='employee_idp_sign_off'),
    path('idps/<int:idp_pk>/add-need/', views.idp_add_training_need, name='idp_add_need'),
    path('wspatr-years/<int:service_year_pk>/sync-idp/', views.sync_idp_to_wsp, name='sync_idp_to_wsp'),
    
    # Service Delivery Tracking
    path('service-delivery/', views.service_delivery_dashboard, name='service_delivery_dashboard'),
    path('service-delivery/<int:pk>/', views.service_delivery_detail, name='service_delivery_detail'),
    path('activities/<int:pk>/update/', views.activity_update, name='activity_update'),
    
    # Evidence Management
    path('evidence/<int:pk>/review/', views.evidence_review, name='evidence_review'),
    path('evidence/<int:pk>/delete/', views.evidence_delete, name='evidence_delete'),
    
    # WSP/ATR Service Management (Simplified Flow)
    path('clients/<int:client_pk>/wspatr/', views.wspatr_service_management, name='wspatr_management'),
    path('clients/<int:client_pk>/wspatr/meetings/<int:meeting_pk>/', views.wspatr_meeting_detail, name='wspatr_meeting_detail'),
    path('clients/<int:client_pk>/wspatr/meetings/<int:meeting_pk>/update/', views.wspatr_update_meeting, name='wspatr_update_meeting'),
    path('clients/<int:client_pk>/wspatr/meetings/create/', views.wspatr_create_meeting, name='wspatr_create_meeting'),
    path('clients/<int:client_pk>/wspatr/meetings/<int:meeting_pk>/attendance/', views.wspatr_record_attendance, name='wspatr_record_attendance'),
    path('clients/<int:client_pk>/wspatr/meetings/<int:meeting_pk>/action/', views.wspatr_add_action_item, name='wspatr_add_action_item'),
    path('clients/<int:client_pk>/wspatr/meetings/<int:meeting_pk>/invite/', views.wspatr_send_meeting_invite, name='wspatr_send_meeting_invite'),
    path('clients/<int:client_pk>/wspatr/actions/<int:action_pk>/', views.wspatr_update_action_item, name='wspatr_update_action_item'),
    path('clients/<int:client_pk>/wspatr/committee/add/', views.wspatr_add_committee_member, name='wspatr_add_committee_member'),
    path('clients/<int:client_pk>/wspatr/committee/<int:member_pk>/remove/', views.wspatr_remove_committee_member, name='wspatr_remove_committee_member'),
    path('clients/<int:client_pk>/wspatr/year/create/', views.wspatr_create_service_year, name='wspatr_create_service_year'),
    path('clients/<int:client_pk>/wspatr/schedule-meetings/', views.wspatr_schedule_meetings, name='wspatr_schedule_meetings'),
    path('clients/<int:client_pk>/wspatr/assign-sdf/', views.wspatr_assign_sdf, name='wspatr_assign_sdf'),
    
    # WSP/ATR Document Management
    path('clients/<int:client_pk>/wspatr/<int:year_pk>/documents/', views.wspatr_documents, name='wspatr_documents'),
    path('clients/<int:client_pk>/wspatr/<int:year_pk>/documents/upload/', views.wspatr_upload_document, name='wspatr_upload_document'),
    path('clients/<int:client_pk>/wspatr/<int:year_pk>/documents/<int:doc_pk>/delete/', views.wspatr_delete_document, name='wspatr_delete_document'),
    path('clients/<int:client_pk>/wspatr/<int:year_pk>/documents/add/', views.wspatr_add_document_requirement, name='wspatr_add_document_requirement'),
    path('clients/<int:client_pk>/wspatr/<int:year_pk>/documents/initialize/', views.wspatr_initialize_documents, name='wspatr_initialize_documents'),
    path('clients/<int:client_pk>/wspatr/<int:year_pk>/approval-letter/', views.wspatr_upload_approval_letter, name='wspatr_upload_approval_letter'),
    path('clients/<int:client_pk>/wspatr/<int:year_pk>/status/', views.wspatr_update_status, name='wspatr_update_status'),
    
    # ==========================================================================
    # WORKPLACE SERVICES - Mentor Management
    # ==========================================================================
    path('host-employers/<int:host_employer_pk>/mentors/', views.mentor_list, name='mentor_list'),
    path('host-employers/<int:host_employer_pk>/mentors/<int:mentor_pk>/', views.mentor_detail, name='mentor_detail'),
    path('host-employers/<int:host_employer_pk>/mentors/<int:mentor_pk>/approve/', views.mentor_approve, name='mentor_approve'),
    path('host-employers/<int:host_employer_pk>/mentors/<int:mentor_pk>/deactivate/', views.mentor_deactivate, name='mentor_deactivate'),
    
    # Mentor Invitations
    path('host-employers/<int:host_employer_pk>/invitations/', views.mentor_invitation_list, name='mentor_invitation_list'),
    path('host-employers/<int:host_employer_pk>/invitations/create/', views.mentor_invitation_create, name='mentor_invitation_create'),
    path('host-employers/<int:host_employer_pk>/invitations/<int:invitation_pk>/resend/', views.mentor_invitation_resend, name='mentor_invitation_resend'),
    
    # Placement Invoices
    path('host-employers/<int:host_employer_pk>/invoices/', views.invoice_list, name='invoice_list'),
    path('host-employers/<int:host_employer_pk>/placements/<int:placement_pk>/invoices/create/', views.invoice_create, name='invoice_create'),
    path('host-employers/<int:host_employer_pk>/invoices/<int:invoice_pk>/', views.invoice_detail, name='invoice_detail'),
    path('host-employers/<int:host_employer_pk>/invoices/<int:invoice_pk>/approve/', views.invoice_approve, name='invoice_approve'),
    path('host-employers/<int:host_employer_pk>/invoices/<int:invoice_pk>/reject/', views.invoice_reject, name='invoice_reject'),
    
    # ==========================================================================
    # EMPLOYMENT EQUITY (EE) SERVICES
    # ==========================================================================
    
    # EE Clients Dashboard - Overview of all EE Consulting clients
    path('ee-clients/', views.ee_clients_dashboard, name='ee_clients_dashboard'),
    
    # EE Service Management (per client)
    path('clients/<int:client_pk>/ee/', views.ee_service_management, name='ee_service_management'),
    path('clients/<int:client_pk>/ee/year/create/', views.ee_create_service_year, name='ee_create_service_year'),
    
    # EE Workforce Profile
    path('clients/<int:client_pk>/ee/<int:year_pk>/workforce/', views.ee_workforce_profile, name='ee_workforce_profile'),
    
    # EE Numerical Goals
    path('clients/<int:client_pk>/ee/<int:year_pk>/goals/', views.ee_numerical_goals, name='ee_numerical_goals'),
    path('clients/<int:client_pk>/ee/<int:year_pk>/goals/add/', views.ee_add_numerical_goal, name='ee_add_numerical_goal'),
    
    # EE Barriers Analysis
    path('clients/<int:client_pk>/ee/<int:year_pk>/barriers/', views.ee_barriers_analysis, name='ee_barriers_analysis'),
    path('clients/<int:client_pk>/ee/<int:year_pk>/barriers/add/', views.ee_add_barrier, name='ee_add_barrier'),
    
    # EE Income Differential
    path('clients/<int:client_pk>/ee/<int:year_pk>/income/', views.ee_income_differential, name='ee_income_differential'),
    path('clients/<int:client_pk>/ee/<int:year_pk>/income/add/', views.ee_add_income_differential, name='ee_add_income_differential'),
    
    # EE Documents
    path('clients/<int:client_pk>/ee/<int:year_pk>/documents/', views.ee_documents, name='ee_documents'),
    path('clients/<int:client_pk>/ee/<int:year_pk>/documents/upload/', views.ee_upload_document, name='ee_upload_document'),
    
    # EE Plans
    path('clients/<int:client_pk>/ee/plans/', views.ee_plan_management, name='ee_plan_management'),
    path('clients/<int:client_pk>/ee/plans/create/', views.ee_create_plan, name='ee_create_plan'),
    
    # EE Committee Meetings
    path('clients/<int:client_pk>/ee/meetings/create/', views.ee_create_meeting, name='ee_create_meeting'),
    path('clients/<int:client_pk>/ee/meetings/<int:meeting_pk>/', views.ee_meeting_detail, name='ee_meeting_detail'),
    
    # ==========================================================================
    # B-BBEE SERVICE ROUTES
    # ==========================================================================
    
    # B-BBEE Clients Dashboard - Overview of all B-BBEE Consulting clients
    path('bbbee-clients/', views.bbbee_clients_dashboard, name='bbbee_clients_dashboard'),
    
    # B-BBEE Service Management (per client)
    path('clients/<int:client_pk>/bbbee/', views.bbbee_service_management, name='bbbee_service_management'),
    path('clients/<int:client_pk>/bbbee/year/create/', views.bbbee_create_service_year, name='bbbee_create_service_year'),
    path('clients/<int:client_pk>/bbbee/<int:year_pk>/status/', views.bbbee_update_status, name='bbbee_update_status'),
    
    # B-BBEE Scorecard Elements
    path('clients/<int:client_pk>/bbbee/<int:year_pk>/ownership/', views.bbbee_ownership, name='bbbee_ownership'),
    path('clients/<int:client_pk>/bbbee/<int:year_pk>/management/', views.bbbee_management_control, name='bbbee_management_control'),
    path('clients/<int:client_pk>/bbbee/<int:year_pk>/skills/', views.bbbee_skills_development, name='bbbee_skills_development'),
    path('clients/<int:client_pk>/bbbee/<int:year_pk>/esd/', views.bbbee_esd, name='bbbee_esd'),
    path('clients/<int:client_pk>/bbbee/<int:year_pk>/sed/', views.bbbee_sed, name='bbbee_sed'),
    path('clients/<int:client_pk>/bbbee/<int:year_pk>/scorecard/', views.bbbee_scorecard_summary, name='bbbee_scorecard_summary'),
    
    # B-BBEE Documents
    path('clients/<int:client_pk>/bbbee/<int:year_pk>/documents/', views.bbbee_documents, name='bbbee_documents'),
    path('clients/<int:client_pk>/bbbee/<int:year_pk>/documents/upload/', views.bbbee_upload_document, name='bbbee_upload_document'),
]
