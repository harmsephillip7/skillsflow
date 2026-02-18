"""
Assessment URL Configuration
API endpoints for assessment capture, scheduling, and offline sync.
"""
from django.urls import path
from . import api_views

app_name = 'assessments'

urlpatterns = [
    # =====================================================
    # Assessment Schedule APIs
    # =====================================================
    path('api/schedules/', api_views.AssessmentScheduleListAPI.as_view(), name='api_schedule_list'),
    path('api/schedules/<int:schedule_id>/reschedule/', api_views.AssessmentScheduleRescheduleAPI.as_view(), name='api_reschedule'),
    path('api/schedules/generate/', api_views.GenerateSchedulesAPI.as_view(), name='api_generate_schedules'),
    path('api/today/', api_views.TodaysAssessmentsAPI.as_view(), name='api_today_assessments'),
    
    # =====================================================
    # Batch Assessment Capture APIs
    # =====================================================
    path('api/batch/<int:schedule_id>/', api_views.BatchAssessmentDataAPI.as_view(), name='api_batch_data'),
    path('api/quick-save/', api_views.QuickSaveResultAPI.as_view(), name='api_quick_save'),
    path('api/bulk-sync/', api_views.BulkSyncResultsAPI.as_view(), name='api_bulk_sync'),
    path('api/bulk-sign/', api_views.BulkSignOffAPI.as_view(), name='api_bulk_sign'),
    
    # =====================================================
    # Evidence Upload APIs
    # =====================================================
    path('api/evidence/', api_views.EvidenceUploadAPI.as_view(), name='api_evidence_upload'),
]
