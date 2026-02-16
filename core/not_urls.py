"""
Notification of Training (NOT) URL Configuration
"""
from django.urls import path
from . import not_views

urlpatterns = [
    # Dashboard
    path('', not_views.NOTDashboardView.as_view(), name='not_dashboard'),
    
    # Intakes Calendar (3-year view)
    path('intakes/', not_views.NOTIntakeCalendarView.as_view(), name='not_intakes'),
    
    # List and CRUD
    path('list/', not_views.NOTListView.as_view(), name='not_list'),
    path('create/', not_views.NOTCreateView.as_view(), name='not_create'),
    
    # AJAX endpoint for campus-filtered users
    path('api/users-by-campus/', not_views.NOTUsersByCampusView.as_view(), name='not_users_by_campus'),
    
    # Multi-step Wizard for Creating NOTs
    path('wizard/', not_views.NOTWizardStartView.as_view(), name='not_wizard'),
    path('wizard/step/<int:step>/', not_views.NOTCreateWizardView.as_view(), name='not_wizard_step'),
    
    path('<int:pk>/', not_views.NOTDetailView.as_view(), name='not_detail'),
    path('<int:pk>/edit/', not_views.NOTUpdateView.as_view(), name='not_edit'),
    path('<int:pk>/timeline/', not_views.NOTTimelineView.as_view(), name='not_timeline'),
    
    # Intakes Management
    path('<int:pk>/add-intake/', not_views.NOTAddIntakeView.as_view(), name='not_add_intake'),
    path('<int:pk>/intake/<int:intake_pk>/edit/', not_views.NOTIntakeUpdateView.as_view(), name='not_edit_intake'),
    path('<int:pk>/intake/<int:intake_pk>/delete/', not_views.NOTIntakeDeleteView.as_view(), name='not_delete_intake'),
    
    # Planning Meeting
    path('<int:pk>/schedule-meeting/', not_views.NOTScheduleMeetingView.as_view(), name='not_schedule_meeting'),
    path('<int:pk>/record-meeting/', not_views.NOTRecordMeetingView.as_view(), name='not_record_meeting'),
    
    # Stakeholders
    path('<int:pk>/add-stakeholder/', not_views.NOTAddStakeholderView.as_view(), name='not_add_stakeholder'),
    path('<int:pk>/stakeholder/<int:stakeholder_pk>/edit/', not_views.NOTEditStakeholderView.as_view(), name='not_edit_stakeholder'),
    
    # Resources
    path('<int:pk>/add-resource/', not_views.NOTAddResourceView.as_view(), name='not_add_resource'),
    
    # Delivery Team
    path('<int:pk>/add-delivery-team/', not_views.NOTAddDeliveryTeamView.as_view(), name='not_add_delivery_team'),
    path('<int:pk>/delivery-team/<int:resource_pk>/edit/', not_views.NOTEditDeliveryTeamView.as_view(), name='not_edit_delivery_team'),
    
    # Deliverables
    path('<int:pk>/add-deliverable/', not_views.NOTAddDeliverableView.as_view(), name='not_add_deliverable'),
    path('<int:pk>/deliverable/<int:deliverable_pk>/edit/', not_views.NOTEditDeliverableView.as_view(), name='not_edit_deliverable'),
    
    # Workflow Actions
    path('<int:pk>/approve/', not_views.NOTApproveView.as_view(), name='not_approve'),
    path('<int:pk>/send-notifications/', not_views.NOTSendNotificationsView.as_view(), name='not_send_notifications'),
    path('<int:pk>/start-project/', not_views.NOTStartProjectView.as_view(), name='not_start_project'),
    
    # Learner Tracking
    path('<int:pk>/learners/', not_views.NOTLearnersView.as_view(), name='not_learners'),
    path('<int:pk>/learners/<int:learner_pk>/', not_views.NOTLearnerDetailView.as_view(), name='not_learner_detail'),
    path('<int:pk>/learners/<int:learner_pk>/documents/', not_views.NOTLearnerDocumentsView.as_view(), name='not_learner_documents'),
    path('<int:pk>/documents/<int:document_pk>/verify/', not_views.NOTVerifyDocumentView.as_view(), name='not_verify_document'),
    
    # Project Documents
    path('<int:pk>/documents/', not_views.NOTProjectDocumentsView.as_view(), name='not_project_documents'),
    
    # Document Type Settings (Admin)
    path('settings/document-types/', not_views.NOTDocumentTypeSettingsView.as_view(), name='not_document_type_settings'),
    
    # Expiring Documents Dashboard
    path('expiring-documents/', not_views.NOTExpiringDocumentsView.as_view(), name='not_expiring_documents'),
    
    # Attendance Register
    path('<int:pk>/attendance/', not_views.NOTAttendanceRegisterSelectView.as_view(), name='not_attendance_select'),
    path('<int:pk>/attendance/<int:year>/<int:month>/', not_views.NOTAttendanceRegisterView.as_view(), name='not_attendance_register'),
    path('<int:pk>/attendance/<int:year>/<int:month>/export/<str:format>/', not_views.NOTAttendanceRegisterExportView.as_view(), name='not_attendance_register_export'),
    path('<int:pk>/attendance/<int:year>/<int:month>/generate-deliverable/', not_views.NOTGenerateAttendanceDeliverableView.as_view(), name='not_generate_attendance_deliverable'),
    path('<int:pk>/attendance/setup-deliverables/', not_views.NOTSetupAttendanceDeliverables.as_view(), name='not_setup_attendance_deliverables'),
]