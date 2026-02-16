"""
Core URL Configuration
Single Sign-On, Authentication, Task Hub, and Data Capture Routes
"""
from django.urls import path
from . import views
from .dashboard_views import (
    OrganizationalDashboardView, ResourcePlanningView, TrainingProgressView,
    implementation_phase_update, implementation_phase_detail,
    CampusUtilizationAPIView, FacilitatorUtilizationAPIView, VenueUtilizationAPIView
)
from .capacity_views import (
    CapacityDashboardView, CapacityTrendAPIView, CampusCapacityDetailView
)
from .reports_views import ReportsView
from .campus_views import SetCampusView
from .task_views import (
    TaskHubView, TaskListView, TaskListAPIView, TaskDetailView, TaskCreateView,
    task_update_status, task_quick_complete, task_snooze, task_add_comment,
    LearnerDashboardView, FacilitatorDashboardView, AdminDashboardView, StakeholderDashboardView
)
from .capture_views import (
    BulkMarkEntryView, QuickMarkView,
    AttendanceCaptureView, AttendanceQRView,
    LearningPlanWizardView, LearningPlanDetailView,
    StipendCalculatorView, StipendApprovalView
)
from .tranche_views import (
    TrancheDashboardView, TrancheListView, TrancheDetailView,
    TrancheCreateView, TrancheUpdateView, TrancheDeleteView,
    TrancheAddEvidenceRequirementView, TrancheUploadEvidenceView,
    TrancheStartQCView, TrancheCompleteQCView,
    TrancheSubmitToFunderView, TrancheRecordFunderResponseView,
    TrancheRecordPaymentView, TrancheAddCommentView,
    GenerateTranchesFromTemplateView, TrancheCalendarView
)
from .registration_views import (
    SignUpView, SignUpSuccessView, VerifyEmailView, CheckRequestStatusView,
    AccessRequestListView, AccessRequestDetailView,
    ApproveAccessRequestView, RejectAccessRequestView, MarkUnderReviewView,
    get_campuses_for_brand, get_request_count_badge
)
from .project_views import (
    ProjectsDashboardView, ProjectDetailView, ProjectTimelineView,
    ProjectFinanceView, ProjectDeliverablesView, ProjectLearnersView,
    project_stats_api,
    DeliverableEvidenceUploadView, DeliverableEvidenceDeleteView,
    DeliverableEvidenceVerifyView, DeliverableEvidenceListView,
    ProjectBillingScheduleView, GenerateInvoiceView, RecalculateMetricsView,
    FunderMetricsView
)

app_name = 'core'

urlpatterns = [
    # SSO Login
    path('login/', views.SSOLoginView.as_view(), name='login'),
    path('logout/', views.sso_logout, name='logout'),
    
    # Dashboard Hub (SSO landing)
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Organizational Dashboard (comprehensive KPIs)
    path('organization/', OrganizationalDashboardView.as_view(), name='organization_dashboard'),
    path('organization/resources/', ResourcePlanningView.as_view(), name='resource_planning'),
    path('organization/progress/', TrainingProgressView.as_view(), name='training_progress'),
    path('organization/reports/', ReportsView.as_view(), name='reports'),
    
    # Campus Capacity & Utilization Dashboard
    path('dashboard/capacity/', CapacityDashboardView.as_view(), name='capacity_dashboard'),
    path('dashboard/capacity/<int:pk>/', CampusCapacityDetailView.as_view(), name='capacity_detail'),
    path('dashboard/capacity/api/trend/', CapacityTrendAPIView.as_view(), name='capacity_trend_api'),
    
    # Implementation Plan AJAX Endpoints
    path('organization/implementation/phase/update/', implementation_phase_update, name='implementation_phase_update'),
    path('organization/implementation/phase/<int:pk>/', implementation_phase_detail, name='implementation_phase_detail'),
    
    # =====================================================
    # PROJECTS SECTION
    # =====================================================
    path('projects/', ProjectsDashboardView.as_view(), name='projects_dashboard'),
    path('projects/<int:pk>/', ProjectDetailView.as_view(), name='project_detail'),
    path('projects/<int:pk>/timeline/', ProjectTimelineView.as_view(), name='project_timeline'),
    path('projects/<int:pk>/finance/', ProjectFinanceView.as_view(), name='project_finance'),
    path('projects/<int:pk>/deliverables/', ProjectDeliverablesView.as_view(), name='project_deliverables'),
    path('projects/<int:pk>/learners/', ProjectLearnersView.as_view(), name='project_learners'),
    path('projects/<int:pk>/api/stats/', project_stats_api, name='project_stats_api'),
    
    # Deliverable Evidence Management
    path('projects/<int:pk>/deliverables/<int:deliverable_pk>/evidence/', 
         DeliverableEvidenceListView.as_view(), name='deliverable_evidence_list'),
    path('projects/<int:pk>/deliverables/<int:deliverable_pk>/upload/', 
         DeliverableEvidenceUploadView.as_view(), name='deliverable_evidence_upload'),
    path('projects/<int:pk>/evidence/<int:evidence_pk>/delete/', 
         DeliverableEvidenceDeleteView.as_view(), name='deliverable_evidence_delete'),
    path('projects/<int:pk>/evidence/<int:evidence_pk>/verify/', 
         DeliverableEvidenceVerifyView.as_view(), name='deliverable_evidence_verify'),
    
    # Project Billing & Finance Analytics
    path('projects/<int:pk>/billing/', 
         ProjectBillingScheduleView.as_view(), name='project_billing_schedule'),
    path('projects/<int:pk>/billing/generate/<int:scheduled_pk>/', 
         GenerateInvoiceView.as_view(), name='generate_scheduled_invoice'),
    path('projects/<int:pk>/billing/recalculate-metrics/', 
         RecalculateMetricsView.as_view(), name='recalculate_project_metrics'),
    path('projects/api/funder-metrics/', 
         FunderMetricsView.as_view(), name='funder_metrics_api'),
    
    # Campus Switcher
    path('set-campus/', SetCampusView.as_view(), name='set_campus'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    
    # =====================================================
    # TASK HUB
    # =====================================================
    path('tasks/', TaskHubView.as_view(), name='task_hub'),
    path('tasks/list/', TaskListView.as_view(), name='task_list'),
    path('tasks/api/', TaskListAPIView.as_view(), name='task_api'),
    path('tasks/create/', TaskCreateView.as_view(), name='task_create'),
    path('tasks/<int:pk>/', TaskDetailView.as_view(), name='task_detail'),
    path('tasks/<int:pk>/status/', task_update_status, name='task_update_status'),
    path('tasks/<int:pk>/complete/', task_quick_complete, name='task_quick_complete'),
    path('tasks/<int:pk>/snooze/', task_snooze, name='task_snooze'),
    path('tasks/<int:pk>/comment/', task_add_comment, name='task_add_comment'),
    
    # =====================================================
    # ROLE-BASED HOME SCREENS
    # =====================================================
    path('home/learner/', LearnerDashboardView.as_view(), name='learner_home'),
    path('home/facilitator/', FacilitatorDashboardView.as_view(), name='facilitator_home'),
    path('home/admin/', AdminDashboardView.as_view(), name='admin_home'),
    path('home/stakeholder/', StakeholderDashboardView.as_view(), name='stakeholder_home'),
    
    # =====================================================
    # SELF-SERVICE REGISTRATION & ACCESS REQUESTS
    # =====================================================
    # Public registration pages
    path('signup/', SignUpView.as_view(), name='signup'),
    path('signup/success/', SignUpSuccessView.as_view(), name='signup_success'),
    path('signup/verify/<str:token>/', VerifyEmailView.as_view(), name='verify_email'),
    path('signup/status/', CheckRequestStatusView.as_view(), name='check_request_status'),
    
    # Admin access request management
    path('admin/access-requests/', AccessRequestListView.as_view(), name='access_request_list'),
    path('admin/access-requests/<int:pk>/', AccessRequestDetailView.as_view(), name='access_request_detail'),
    path('admin/access-requests/<int:pk>/approve/', ApproveAccessRequestView.as_view(), name='approve_access_request'),
    path('admin/access-requests/<int:pk>/reject/', RejectAccessRequestView.as_view(), name='reject_access_request'),
    path('admin/access-requests/<int:pk>/review/', MarkUnderReviewView.as_view(), name='mark_under_review'),
    
    # AJAX endpoints
    path('api/campuses-for-brand/', get_campuses_for_brand, name='campuses_for_brand'),
    path('api/pending-requests-count/', get_request_count_badge, name='pending_requests_count'),
    
    # =====================================================
    # UTILIZATION API ENDPOINTS
    # =====================================================
    path('api/utilization/', CampusUtilizationAPIView.as_view(), name='all_campuses_utilization'),
    path('api/utilization/campus/<int:campus_id>/', CampusUtilizationAPIView.as_view(), name='campus_utilization'),
    path('api/utilization/facilitator/<int:user_id>/', FacilitatorUtilizationAPIView.as_view(), name='facilitator_utilization'),
    path('api/utilization/venue/<int:venue_id>/', VenueUtilizationAPIView.as_view(), name='venue_utilization'),
]


# =====================================================
# CAPTURE URLS (separate namespace for clarity)
# =====================================================
capture_urlpatterns = [
    # Bulk Assessment Marking
    path('marks/', BulkMarkEntryView.as_view(), name='bulk_marks'),
    path('marks/quick/<int:pk>/', QuickMarkView.as_view(), name='quick_mark'),
    
    # Attendance
    path('attendance/', AttendanceCaptureView.as_view(), name='attendance_list'),
    path('attendance/<int:session_id>/', AttendanceCaptureView.as_view(), name='attendance_capture'),
    path('attendance/<int:session_id>/qr/', AttendanceQRView.as_view(), name='attendance_qr'),
    
    # Learning Plans
    path('learning-plan/', LearningPlanWizardView.as_view(), name='learning_plan_list'),
    path('learning-plan/<int:enrollment_id>/', LearningPlanWizardView.as_view(), name='learning_plan_wizard'),
    path('learning-plan/view/<int:pk>/', LearningPlanDetailView.as_view(), name='learning_plan_detail'),
    
    # Stipends
    path('stipends/', StipendCalculatorView.as_view(), name='stipend_calculator'),
    path('stipends/approval/', StipendApprovalView.as_view(), name='stipend_approval'),
]


# =====================================================
# TRANCHE PAYMENT & EVIDENCE MANAGEMENT URLS
# =====================================================
tranche_urlpatterns = [
    # Dashboard
    path('', TrancheDashboardView.as_view(), name='tranche_dashboard'),
    path('list/', TrancheListView.as_view(), name='tranche_list'),
    path('calendar/', TrancheCalendarView.as_view(), name='tranche_calendar'),
    
    # Tranche CRUD
    path('<int:pk>/', TrancheDetailView.as_view(), name='tranche_detail'),
    path('<int:pk>/edit/', TrancheUpdateView.as_view(), name='tranche_edit'),
    path('<int:pk>/delete/', TrancheDeleteView.as_view(), name='tranche_delete'),
    path('create/<int:not_pk>/', TrancheCreateView.as_view(), name='tranche_create'),
    path('generate/<int:not_pk>/', GenerateTranchesFromTemplateView.as_view(), name='generate_tranches_from_template'),
    
    # Evidence Management
    path('<int:pk>/add-requirement/', TrancheAddEvidenceRequirementView.as_view(), name='tranche_add_requirement'),
    path('<int:pk>/upload/<int:requirement_pk>/', TrancheUploadEvidenceView.as_view(), name='tranche_upload_evidence'),
    
    # QC Workflow
    path('<int:pk>/start-qc/', TrancheStartQCView.as_view(), name='tranche_start_qc'),
    path('<int:pk>/complete-qc/', TrancheCompleteQCView.as_view(), name='tranche_complete_qc'),
    
    # Submission & Payment
    path('<int:pk>/submit/', TrancheSubmitToFunderView.as_view(), name='tranche_submit'),
    path('<int:pk>/funder-response/', TrancheRecordFunderResponseView.as_view(), name='tranche_funder_response'),
    path('<int:pk>/record-payment/', TrancheRecordPaymentView.as_view(), name='tranche_record_payment'),
    
    # Comments
    path('<int:pk>/comment/', TrancheAddCommentView.as_view(), name='tranche_add_comment'),
]
