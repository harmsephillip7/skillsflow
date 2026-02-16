"""
URL configuration for Tender Management module.
"""

from django.urls import path
from . import views

app_name = 'tenders'

urlpatterns = [
    # Dashboard
    path('', views.tender_dashboard, name='dashboard'),
    
    # Tender management
    path('tenders/', views.tender_list, name='tender_list'),
    path('tenders/create/', views.tender_create, name='tender_create'),
    path('tenders/<uuid:pk>/', views.tender_detail, name='tender_detail'),
    path('tenders/<uuid:pk>/edit/', views.tender_edit, name='tender_edit'),
    path('tenders/<uuid:pk>/status/', views.tender_update_status, name='tender_update_status'),
    path('tenders/<uuid:pk>/status/', views.tender_update_status, name='update_status'),  # Alias for templates
    path('tenders/<uuid:pk>/note/', views.add_note, name='add_note'),  # Form-based note add
    path('tenders/<uuid:tender_pk>/apply/', views.create_application, name='create_application'),
    
    # Applications
    path('applications/<uuid:pk>/', views.application_detail, name='application_detail'),
    path('applications/<uuid:pk>/submit/', views.application_submit, name='application_submit'),
    path('applications/<uuid:pk>/acknowledge/', views.application_acknowledge, name='application_acknowledge'),
    path('applications/<uuid:pk>/approve/', views.application_approve, name='application_approve'),
    path('applications/<uuid:pk>/reject/', views.application_reject, name='application_reject'),
    
    # Source management (scraping configuration)
    path('sources/', views.source_list, name='source_list'),
    path('sources/create/', views.source_create, name='source_create'),
    path('sources/<int:pk>/', views.source_detail, name='source_detail'),
    path('sources/<int:pk>/test/', views.source_test, name='source_test'),
    path('sources/<int:pk>/scrape/', views.source_scrape, name='source_scrape'),
    path('sources/<int:pk>/scrape/', views.source_scrape, name='scrape_source'),  # Alias for templates
    path('sources/<int:pk>/toggle/', views.toggle_source, name='toggle_source'),  # Toggle active state
    
    # Segment management
    path('segments/', views.segment_list, name='segment_list'),
    path('segments/create/', views.segment_create, name='segment_create'),
    path('segments/<int:pk>/', views.segment_detail, name='segment_detail'),
    
    # Analytics
    path('analytics/', views.analytics, name='analytics'),
    
    # API endpoints
    path('api/pipeline/', views.api_pipeline_data, name='api_pipeline_data'),
    path('api/segments/<int:segment_id>/probability/', views.api_probability_curve, name='api_probability_curve'),
    path('api/tenders/<uuid:tender_pk>/notes/', views.api_add_note, name='api_add_note'),
]
