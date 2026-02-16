"""
Finance URL Configuration
"""
from django.urls import path
from crm import quote_views

app_name = 'finance'

urlpatterns = [
    # Public quote views (no login required)
    path('quotes/public/<uuid:token>/', quote_views.QuotePublicView.as_view(), name='quote_public_view'),
    path('quotes/public/<uuid:token>/accept/', quote_views.accept_quote_public, name='quote_accept_public'),
    path('quotes/public/<uuid:token>/reject/', quote_views.reject_quote_public, name='quote_reject_public'),
]
