"""
Tenants URL Configuration

URLs for managing tenant-level configurations:
- Brand social account integrations
- OAuth callbacks for social platforms
"""
from django.urls import path
from . import views

app_name = 'tenants'

urlpatterns = [
    # Brand Social Integrations
    path('brands/<int:brand_id>/integrations/', views.brand_integrations, name='brand_integrations'),
    path('brands/<int:brand_id>/integrations/<uuid:account_id>/', views.brand_integration_detail, name='brand_integration_detail'),
    path('brands/<int:brand_id>/integrations/connect/', views.connect_social_account, name='connect_social_account'),
    path('brands/<int:brand_id>/integrations/<uuid:account_id>/update/', views.update_social_account, name='update_social_account'),
    path('brands/<int:brand_id>/integrations/<uuid:account_id>/disconnect/', views.disconnect_social_account, name='disconnect_social_account'),
    path('brands/<int:brand_id>/integrations/<uuid:account_id>/sync/', views.trigger_sync, name='trigger_sync'),
    path('brands/<int:brand_id>/integrations/<uuid:account_id>/backfill/', views.trigger_backfill, name='trigger_backfill'),
    path('brands/<int:brand_id>/integrations/<uuid:account_id>/ga4-property/', views.update_social_account, name='update_ga4_property'),
    
    # OAuth Callback (shared across platforms)
    path('oauth/callback/', views.social_oauth_callback, name='social_oauth_callback'),
]
