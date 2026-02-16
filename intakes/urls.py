from django.urls import path
from . import views

app_name = 'intakes'

urlpatterns = [
    # Dashboard
    path('', views.IntakeDashboardView.as_view(), name='dashboard'),
    
    # Intake management
    path('buckets/', views.IntakeBucketListView.as_view(), name='bucket_list'),
    path('create/', views.IntakeCreateView.as_view(), name='create'),
    path('<int:pk>/', views.IntakeDetailView.as_view(), name='detail'),
    path('<int:pk>/enroll/', views.IntakeEnrollView.as_view(), name='enroll'),
    
    # Enrollment management
    path('enrollment/<int:pk>/', views.IntakeEnrollmentDetailView.as_view(), name='enrollment_detail'),
    
    # Reports
    path('reports/capacity/', views.IntakeCapacityReportView.as_view(), name='capacity_report'),
    
    # API endpoints
    path('api/learners/search/', views.LearnerSearchAPIView.as_view(), name='learner_search'),
]
