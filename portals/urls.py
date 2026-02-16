"""
Portal URL Configuration
URL routing for all portal views (Learner/Student, Corporate, Facilitator, Mentor, Workplace Officer, etc.)
"""
from django.urls import path
from . import views
from . import student_views
from . import facilitator_views
from . import corporate_views
from . import mentor_views
from . import mentor_bulk_views
from . import workplace_officer_views
from . import dispute_views
from . import profile_views

app_name = 'portals'

urlpatterns = [
    # =====================================================
    # Student/Learner Portal URLs (New Easy Views)
    # =====================================================
    path('student/', student_views.StudentDashboardView.as_view(), name='student_dashboard'),
    path('student/enrollments/', student_views.StudentEnrollmentsView.as_view(), name='student_enrollments'),
    path('student/course/<int:pk>/', student_views.StudentCourseDetailView.as_view(), name='student_course_detail'),
    path('student/assessment/', student_views.StudentAssessmentView.as_view(), name='student_assessment'),
    path('student/marks/', student_views.StudentMarksView.as_view(), name='student_marks'),
    path('student/materials/', student_views.StudentMaterialsView.as_view(), name='student_materials'),
    path('student/timetable/', student_views.StudentTimetableView.as_view(), name='student_timetable'),
    path('student/schedule/', student_views.StudentScheduleView.as_view(), name='student_schedule'),
    
    # Student WBL URLs
    path('student/wbl/', student_views.StudentAttendanceHomeView.as_view(), name='student_wbl_dashboard'),
    path('student/wbl/home/', student_views.StudentAttendanceHomeView.as_view(), name='student_attendance_home'),
    path('student/wbl/dashboard/', student_views.StudentWBLDashboardView.as_view(), name='student_wbl_full_dashboard'),
    path('student/wbl/attendance/', student_views.StudentAttendanceView.as_view(), name='student_attendance'),
    path('student/wbl/attendance/submit-new/', student_views.StudentAttendanceSubmitView.as_view(), name='student_attendance_submit_page'),
    path('student/wbl/attendance/submit/', student_views.student_attendance_submit, name='student_attendance_submit'),
    path('student/wbl/logbook/', student_views.StudentLogbookView.as_view(), name='student_logbook'),
    path('student/wbl/logbook/<int:pk>/', student_views.StudentLogbookDetailView.as_view(), name='student_logbook_detail'),
    path('student/wbl/logbook/create/', student_views.student_logbook_create, name='student_logbook_create'),
    path('student/wbl/logbook/<int:logbook_id>/update/', student_views.student_logbook_update, name='student_logbook_update'),
    
    # Daily Entry & Task Evidence URLs (enhanced workflow)
    path('student/wbl/daily/', student_views.StudentDailyEntryListView.as_view(), name='student_daily_entries'),
    path('student/wbl/daily/new/', student_views.StudentDailyEntryCreateView.as_view(), name='student_daily_entry_create'),
    path('student/wbl/daily/<int:pk>/', student_views.StudentDailyEntryDetailView.as_view(), name='student_daily_entry_detail'),
    path('student/wbl/daily/<int:entry_id>/task/add/', student_views.student_add_task, name='student_add_task'),
    path('student/wbl/daily/<int:entry_id>/task/<int:task_id>/delete/', student_views.student_delete_task, name='student_delete_task'),
    path('student/wbl/daily/<int:entry_id>/sign/', student_views.student_sign_daily_entry, name='student_sign_daily_entry'),
    path('student/wbl/daily/<int:entry_id>/update/', student_views.student_update_daily_entry, name='student_update_daily_entry'),
    path('student/wbl/workplace-outcomes/', student_views.get_workplace_outcomes, name='get_workplace_outcomes'),
    
    # Task Quick Add (separate flow from attendance)
    path('student/wbl/tasks/quick-add/', student_views.StudentTaskQuickAddView.as_view(), name='student_task_quick_add'),
    path('student/wbl/tasks/quick-add/api/', student_views.student_quick_add_task, name='student_quick_add_task'),
    
    path('student/wbl/messages/', student_views.StudentMessagesView.as_view(), name='student_messages'),
    path('student/wbl/messages/<int:pk>/', student_views.StudentMessageThreadView.as_view(), name='student_message_thread'),
    path('student/wbl/messages/<int:thread_id>/send/', student_views.student_message_send, name='student_message_send'),
    path('student/wbl/messages/new/', student_views.student_new_message, name='student_new_message'),
    path('student/wbl/stipends/', student_views.StudentStipendHistoryView.as_view(), name='student_stipend_history'),
    path('student/wbl/stipends/<int:pk>/', student_views.StudentStipendDetailView.as_view(), name='student_stipend_detail'),
    path('student/wbl/sync/', student_views.student_wbl_sync, name='student_wbl_sync'),
    
    # Student Calendar URLs
    path('student/calendar/', student_views.StudentCalendarView.as_view(), name='student_calendar'),
    path('student/calendar/events/', student_views.calendar_events_api, name='calendar_events_api'),
    
    # Student Enhanced Stipend Dashboard URLs
    path('student/wbl/stipend-dashboard/', student_views.StudentStipendDashboardView.as_view(), name='student_stipend_dashboard'),
    path('student/wbl/stipend/preview/', student_views.stipend_calculate_preview, name='stipend_calculate_preview'),
    path('student/wbl/stipend/what-if/', student_views.stipend_what_if_calculator, name='stipend_what_if_calculator'),
    
    # Student Dispute URLs
    path('student/disputes/', dispute_views.StudentDisputeListView.as_view(), name='student_dispute_list'),
    path('student/disputes/<int:pk>/', dispute_views.StudentDisputeDetailView.as_view(), name='student_dispute_detail'),
    path('student/disputes/submit/<int:calculation_id>/', dispute_views.student_submit_dispute, name='student_submit_dispute'),
    
    # Student Profile Management URLs
    path('student/profile/', profile_views.StudentProfileView.as_view(), name='student_profile'),
    path('student/profile/edit/', profile_views.StudentProfileEditView.as_view(), name='student_profile_edit'),
    path('student/profile/photo/upload/', profile_views.student_profile_photo_upload, name='student_profile_photo_upload'),
    path('student/documents/', profile_views.StudentDocumentsView.as_view(), name='student_documents'),
    path('student/documents/upload/', profile_views.student_document_upload, name='student_document_upload'),
    path('student/documents/<int:document_id>/delete/', profile_views.student_document_delete, name='student_document_delete'),
    path('student/card/', profile_views.StudentCardView.as_view(), name='student_card'),
    path('student/card/download/', profile_views.download_student_card, name='download_student_card'),
    path('student/signature/', profile_views.StudentSignatureView.as_view(), name='student_signature'),
    path('student/signature/api/', profile_views.student_signature_capture_api, name='student_signature_api'),
    
    # =====================================================
    # Mentor Portal URLs (Host Employer Mentors)
    # =====================================================
    path('mentor/', mentor_views.mentor_dashboard, name='mentor_dashboard'),
    path('mentor/learners/', mentor_views.learner_list, name='mentor_learners'),
    path('mentor/learners/<int:placement_id>/', mentor_views.learner_detail, name='mentor_learner_detail'),
    path('mentor/attendance/<int:placement_id>/', mentor_views.attendance_entry, name='mentor_attendance_entry'),
    path('mentor/attendance/<int:placement_id>/calendar/', mentor_views.attendance_calendar, name='mentor_attendance_calendar'),
    path('mentor/logbooks/', mentor_views.logbook_list, name='mentor_logbooks'),
    path('mentor/logbooks/<int:logbook_id>/', mentor_views.logbook_detail, name='mentor_logbook_detail'),
    path('mentor/logbooks/<int:logbook_id>/sign/', mentor_views.logbook_sign, name='mentor_logbook_sign'),
    path('mentor/modules/<int:placement_id>/', mentor_views.module_completions, name='mentor_modules'),
    # Bulk verification
    path('mentor/attendance/bulk-verify/', mentor_bulk_views.attendance_bulk_verify, name='mentor_bulk_verify'),
    path('mentor/attendance/bulk-verify/submit/', mentor_bulk_views.attendance_bulk_verify_submit, name='mentor_bulk_verify_submit'),
    path('mentor/messages/', mentor_views.messages_inbox, name='mentor_messages'),
    path('mentor/messages/<int:thread_id>/', mentor_views.message_thread, name='mentor_thread'),
    path('mentor/messages/new/', mentor_views.new_message, name='mentor_new_message'),
    path('mentor/messages/new/<int:placement_id>/', mentor_views.new_message, name='mentor_new_message_placement'),
    # Mentor API endpoints
    path('mentor/api/sync/', mentor_views.api_attendance_sync, name='mentor_api_sync'),
    path('mentor/api/placements/', mentor_views.api_placements, name='mentor_api_placements'),
    # Mentor Signature
    path('mentor/signature/', mentor_views.mentor_signature, name='mentor_signature'),
    path('mentor/signature/api/', mentor_views.mentor_signature_api, name='mentor_signature_api'),
    
    # =====================================================
    # Workplace Officer Portal URLs (SkillsFlow Staff)
    # =====================================================
    path('officer/', workplace_officer_views.officer_dashboard, name='officer_dashboard'),
    path('officer/placements/', workplace_officer_views.placement_list, name='officer_placements'),
    path('officer/placements/<int:placement_id>/', workplace_officer_views.placement_detail, name='officer_placement_detail'),
    # Officer Dispute URLs
    path('officer/disputes/', dispute_views.OfficerDisputeListView.as_view(), name='officer_dispute_list'),
    path('officer/disputes/<int:pk>/', dispute_views.OfficerDisputeDetailView.as_view(), name='officer_dispute_detail'),
    path('officer/disputes/<int:dispute_id>/respond/', dispute_views.officer_dispute_respond, name='officer_dispute_respond'),
    path('officer/disputes/bulk-action/', dispute_views.officer_dispute_bulk_action, name='officer_dispute_bulk_action'),
    # Disciplinary
    path('officer/disciplinary/', workplace_officer_views.disciplinary_list, name='officer_disciplinary'),
    path('officer/disciplinary/<int:record_id>/', workplace_officer_views.disciplinary_detail, name='officer_disciplinary_detail'),
    path('officer/disciplinary/create/<int:placement_id>/', workplace_officer_views.disciplinary_create, name='officer_disciplinary_create'),
    path('officer/disciplinary/<int:record_id>/action/', workplace_officer_views.disciplinary_action, name='officer_disciplinary_action'),
    # Stipends
    path('officer/stipends/', workplace_officer_views.stipend_list, name='officer_stipends'),
    path('officer/stipends/<int:stipend_id>/', workplace_officer_views.stipend_detail, name='officer_stipend_detail'),
    path('officer/stipends/<int:stipend_id>/verify/', workplace_officer_views.stipend_verify, name='officer_stipend_verify'),
    path('officer/stipends/calculate/', workplace_officer_views.stipend_calculate_all, name='officer_stipend_calculate'),
    # Support Notes
    path('officer/support-notes/', workplace_officer_views.support_note_list, name='officer_support_notes'),
    path('officer/support-notes/create/<int:placement_id>/', workplace_officer_views.support_note_create, name='officer_support_note_create'),
    # Logbooks
    path('officer/logbooks/', workplace_officer_views.logbook_list, name='officer_logbooks'),
    path('officer/logbooks/<int:logbook_id>/sign/', workplace_officer_views.logbook_sign, name='officer_logbook_sign'),
    # Messages
    path('officer/messages/', workplace_officer_views.messages_inbox, name='officer_messages'),
    path('officer/messages/<int:thread_id>/', workplace_officer_views.message_thread, name='officer_thread'),
    # Officer Signature
    path('officer/signature/', workplace_officer_views.officer_signature, name='officer_signature'),
    path('officer/signature/api/', workplace_officer_views.officer_signature_api, name='officer_signature_api'),
    
    # =====================================================
    # Facilitator Portal URLs (New Easy Views)
    # =====================================================
    path('facilitator/', facilitator_views.FacilitatorDashboardView.as_view(), name='facilitator_dashboard'),
    path('facilitator/schedule/', facilitator_views.FacilitatorScheduleView.as_view(), name='facilitator_schedule'),
    path('facilitator/classes/', facilitator_views.FacilitatorClassListView.as_view(), name='facilitator_classes'),
    path('facilitator/class/<int:cohort_id>/', facilitator_views.FacilitatorClassListView.as_view(), name='facilitator_class'),
    path('facilitator/cohort/<int:cohort_id>/', facilitator_views.FacilitatorCohortDetailView.as_view(), name='facilitator_cohort_detail'),
    path('facilitator/assessments/', facilitator_views.FacilitatorPendingAssessmentsView.as_view(), name='facilitator_assessments'),
    path('facilitator/assessments/pending/', facilitator_views.FacilitatorPendingAssessmentsView.as_view(), name='facilitator_pending_assessments'),  # Alias
    path('facilitator/assess/<int:enrollment_id>/<int:activity_id>/', facilitator_views.AssessLearnerView.as_view(), name='facilitator_assess_learner'),
    path('facilitator/moderate/<int:result_id>/', facilitator_views.ModerateLearnerView.as_view(), name='facilitator_moderate'),
    path('facilitator/learner/<int:learner_id>/enrollment/<int:enrollment_id>/', facilitator_views.FacilitatorCohortDetailView.as_view(), name='facilitator_learner_detail'),
    path('facilitator/learner/<int:enrollment_id>/progress/', facilitator_views.FacilitatorLearnerYearProgressView.as_view(), name='facilitator_learner_progress'),
    path('facilitator/batch-grade/<int:cohort_id>/<int:activity_id>/', facilitator_views.FacilitatorLearnerProgressView.as_view(), name='facilitator_batch_grade'),
    
    # Facilitator Attendance Verification
    path('facilitator/attendance/', facilitator_views.FacilitatorAttendanceView.as_view(), name='facilitator_attendance'),
    path('facilitator/attendance/verify/', facilitator_views.facilitator_bulk_verify_attendance, name='facilitator_bulk_verify_attendance'),
    # Facilitator Signature
    path('facilitator/signature/', facilitator_views.FacilitatorSignatureView.as_view(), name='facilitator_signature'),
    path('facilitator/signature/api/', facilitator_views.facilitator_signature_api, name='facilitator_signature_api'),
    
    # =====================================================
    # Legacy Learner Portal URLs
    # =====================================================
    path('learner/', views.LearnerDashboardView.as_view(), name='learner_dashboard'),
    path('learner/enrollments/', views.LearnerEnrollmentsView.as_view(), name='learner_enrollments'),
    path('learner/documents/', views.LearnerDocumentsView.as_view(), name='learner_documents'),
    
    # =====================================================
    # Corporate Portal URLs (New Service Delivery Portal)
    # =====================================================
    path('corporate/', corporate_views.CorporatePortalDashboardView.as_view(), name='corporate_dashboard'),
    path('corporate/services/', corporate_views.CorporateServiceListView.as_view(), name='corporate_services'),
    path('corporate/services/<int:subscription_id>/', corporate_views.CorporateServiceDetailView.as_view(), name='corporate_service_detail'),
    path('corporate/learners/', corporate_views.CorporateLearnerListView.as_view(), name='corporate_learners'),
    path('corporate/learners/<int:learner_id>/', corporate_views.CorporateLearnerDetailView.as_view(), name='corporate_learner_detail'),
    path('corporate/deadlines/', corporate_views.CorporateDeadlinesView.as_view(), name='corporate_deadlines'),
    path('corporate/meetings/', corporate_views.CorporateMeetingsView.as_view(), name='corporate_meetings'),
    path('corporate/meetings/<int:meeting_id>/', corporate_views.CorporateMeetingDetailView.as_view(), name='corporate_meeting_detail'),
    path('corporate/documents/', corporate_views.CorporateDocumentsView.as_view(), name='corporate_documents'),
    path('corporate/grants/', corporate_views.CorporateGrantsView.as_view(), name='corporate_grants'),
    path('corporate/grants/<int:grant_id>/', corporate_views.CorporateGrantDetailView.as_view(), name='corporate_grant_detail'),
    # SDF Task Management
    path('corporate/tasks/<int:pk>/complete/', corporate_views.mark_task_complete, name='corporate_task_complete'),
    path('corporate/tasks/<int:pk>/evidence/', corporate_views.upload_task_evidence, name='corporate_task_evidence'),
    # Legacy employees URL (redirects to learners)
    path('corporate/employees/', views.CorporateEmployeesView.as_view(), name='corporate_employees'),
    
    # =====================================================
    # Host Employer Portal URLs
    # =====================================================
    path('host-employer/', views.HostEmployerDashboardView.as_view(), name='host_employer_dashboard'),
    
    # =====================================================
    # Staff Portal URLs
    # =====================================================
    path('staff/', views.StaffDashboardView.as_view(), name='staff_dashboard'),
]
