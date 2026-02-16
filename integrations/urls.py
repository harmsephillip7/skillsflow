# integrations/urls.py

from django.urls import path
from . import views

app_name = "integrations"

urlpatterns = [
    # Main pages
    path('', views.integration_hub, name='hub'),
    path('marketplace/', views.marketplace, name='marketplace'),

    # Provider pages
    path("provider/<str:provider_slug>/", views.provider_detail, name="provider_detail"),
    path("provider/<str:provider_slug>/connect/", views.connect_provider, name="connect_provider"),
    path("provider/<str:provider_slug>/disconnect/", views.disconnect_provider, name="disconnect_provider"),

    # Connection pages/actions (UUIDs)
    path("connection/<uuid:connection_id>/", views.connection_detail, name="connection_detail"),
    path("connection/<uuid:connection_id>/sync/", views.connection_sync, name="connection_sync"),
    path("connection/<uuid:connection_id>/test/", views.connection_test, name="connection_test"),


       # Webhooks
    path('connection/<int:connection_id>/webhooks/', views.webhook_list, name='webhook_list'),
    path('connection/<int:connection_id>/webhooks/create/', views.webhook_create, name='webhook_create'),
    path('webhook/<uuid:webhook_id>/receive/', views.webhook_receive, name='webhook_receive'),
    path('webhook/<uuid:webhook_id>/logs/', views.webhook_logs, name='webhook_logs'),
    
    # Sync Logs
    path('logs/', views.sync_logs, name='sync_logs'),
    path('logs/<int:connection_id>/', views.sync_logs, name='connection_logs'),

    # API Endpoints
    path('api/connections/', views.api_connections, name='api_connections'),
    path('api/health-check/', views.api_health_check, name='api_health_check'),

]
''' path('', views.integration_hub, name='hub'),
    path('marketplace/', views.marketplace, name='marketplace'),
    
    # Provider Connection
    path('provider/<slug:provider_slug>/', views.provider_detail, name='provider_detail'),
    path('provider/<slug:provider_slug>/connect/', views.connect_provider, name='connect_provider'),
    path('provider/<slug:provider_slug>/disconnect/', views.disconnect_provider, name='disconnect_provider'),
    path('provider/<slug:provider_slug>/callback/', views.oauth_callback, name='oauth_callback'),
    
    # Connection Management
    path('connection/<int:connection_id>/', views.connection_detail, name='connection_detail'),
    path('connection/<int:connection_id>/sync/', views.connection_sync, name='connection_sync'),
    path('connection/<int:connection_id>/test/', views.connection_test, name='connection_test'),
    path('connection/<int:connection_id>/settings/', views.connection_settings, name='connection_settings'),
    
    # Webhooks
    path('connection/<int:connection_id>/webhooks/', views.webhook_list, name='webhook_list'),
    path('connection/<int:connection_id>/webhooks/create/', views.webhook_create, name='webhook_create'),
    path('webhook/<uuid:webhook_id>/receive/', views.webhook_receive, name='webhook_receive'),
    path('webhook/<uuid:webhook_id>/logs/', views.webhook_logs, name='webhook_logs'),
    
    # Sync Logs
    path('logs/', views.sync_logs, name='sync_logs'),
    path('logs/<int:connection_id>/', views.sync_logs, name='connection_logs'),
    
    # API Endpoints
    path('api/connections/', views.api_connections, name='api_connections'),
    path('api/health-check/', views.api_health_check, name='api_health_check'),
] '''
