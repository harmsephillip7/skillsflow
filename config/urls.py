"""SkillsFlow URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

# Import capture and tranche URLs
from core.urls import capture_urlpatterns, tranche_urlpatterns

# Import HR admin URLs
from hr.urls import hr_admin_urlpatterns

# Import public mentor registration view
from corporate.views import mentor_registration


def home_redirect(request):
    """Redirect home to SSO login or dashboard"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return redirect('core:login')


urlpatterns = [
    # Custom Admin with unified theme (management interface)
    path('admin/', include('core.admin_urls')),
    
    # Home - redirect to login or dashboard
    path('', home_redirect, name='home'),
    
    # Core authentication (SSO)
    path('', include('core.urls', namespace='core')),
    
    # API Authentication (JWT + 2FA)
    path('api/auth/', include('core.api_auth_urls')),
    
    # Django auth views (password reset, etc.)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Portal routes
    path('portal/', include('portals.urls', namespace='portals')),
    
    # Workflow routes
    path('workflows/', include('workflows.urls', namespace='workflows')),
    
    # Learner management routes
    path('learners/', include('learners.urls', namespace='learners')),
    
    # Quick data capture routes
    path('capture/', include((capture_urlpatterns, 'capture'), namespace='capture')),
    
    # Notification of Training (NOT) routes
    path('not/', include('core.not_urls')),
    
    # Tranche Payment & Evidence Management routes
    path('tranches/', include((tranche_urlpatterns, 'tranches'), namespace='tranches')),
    
    # Corporate Client Management routes
    path('corporate/', include('corporate.urls', namespace='corporate')),
    
    # Academics - Qualifications & Compliance Management
    path('academics/', include('academics.urls', namespace='academics')),
    
    # Trade Tests - Trade test applications, bookings, and results
    path('trade-tests/', include('trade_tests.urls', namespace='trade_tests')),
    
    # Intakes - Intake and enrollment management
    path('intakes/', include('intakes.urls', namespace='intakes')),
    
    # LMS Integration - Moodle sync and assessment mapping
    path('lms/', include('lms_sync.urls', namespace='lms_sync')),
    
    # Integration Hub - External service integrations
    path('integrations/', include('integrations.urls', namespace='integrations')),
    
    # Tender Management - Web scraping and revenue forecasting
    path('tenders/', include('tenders.urls', namespace='tenders')),
    
    # HR Management - Departments, Positions, Staff
    path('hr/', include('hr.urls', namespace='hr')),
    
    # HR Admin - Custom admin views for HR
    path('admin/hr/', include((hr_admin_urlpatterns, 'hr_admin'), namespace='hr_admin')),
    
    # CRM - Sales leads and pipeline management
    path('crm/', include('crm.urls', namespace='crm')),
    
    # Tenants - Brand management and social integrations
    path('tenants/', include('tenants.urls', namespace='tenants')),
    
    # Finance - Quotes, invoices, payments (public endpoints)
    path('finance/', include('finance.urls', namespace='finance')),

    # Support - Ticketing, knowledge base, onboarding
    path('support/', include('support.urls', namespace='support')),

    path('register/mentor/<uuid:token>/', mentor_registration, name='mentor_registration'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
