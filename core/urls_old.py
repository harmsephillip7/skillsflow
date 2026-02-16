"""
Core URL Configuration
Single Sign-On and Authentication Routes
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # SSO Login
    path('login/', views.SSOLoginView.as_view(), name='login'),
    path('logout/', views.sso_logout, name='logout'),
    
    # Dashboard Hub
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
]
