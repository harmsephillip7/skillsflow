"""
URL Configuration for LMS Sync app
"""
from django.urls import path
from . import views

app_name = 'lms_sync'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Setup
    path('setup/', views.setup_wizard, name='setup_wizard'),
    path('tutorial/', views.moodle_tutorial, name='moodle_tutorial'),
    
    # Mappings
    path('review/', views.review_mappings, name='review_mappings'),
    
    # AJAX endpoints
    path('api/test-connection/', views.test_connection, name='test_connection'),
    path('api/trigger-sync/', views.trigger_sync, name='trigger_sync'),
]
