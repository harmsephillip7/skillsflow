"""
Trade Tests URL Configuration
"""
from django.urls import path
from . import views

app_name = 'trade_tests'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Applications
    path('applications/', views.ApplicationListView.as_view(), name='application_list'),
    path('applications/create/', views.application_create, name='application_create'),
    path('applications/create/<str:source>/', views.application_create, name='application_create_source'),
    path('applications/<int:pk>/', views.ApplicationDetailView.as_view(), name='application_detail'),
    path('applications/<int:pk>/edit/', views.ApplicationUpdateView.as_view(), name='application_update'),
    path('applications/<int:pk>/submit/', views.submit_to_namb, name='submit_to_namb'),
    
    # Bookings
    path('bookings/', views.BookingListView.as_view(), name='booking_list'),
    path('bookings/<int:pk>/', views.BookingDetailView.as_view(), name='booking_detail'),
    path('bookings/<int:pk>/schedule/', views.schedule_booking, name='schedule_booking'),
    path('bookings/<int:pk>/result/', views.record_result, name='record_result'),
    
    # Bulk schedule entry
    path('schedule/', views.bulk_schedule_entry, name='bulk_schedule'),
    
    # Centres
    path('centres/', views.CentreListView.as_view(), name='centre_list'),
    path('centres/create/', views.CentreCreateView.as_view(), name='centre_create'),
    path('centres/<int:pk>/', views.CentreDetailView.as_view(), name='centre_detail'),
    path('centres/<int:pk>/edit/', views.CentreUpdateView.as_view(), name='centre_update'),
    
    # Trades
    path('trades/', views.TradeListView.as_view(), name='trade_list'),
    path('trades/<int:pk>/', views.TradeDetailView.as_view(), name='trade_detail'),
    
    # ARPL
    path('arpl/', views.ARPLListView.as_view(), name='arpl_list'),
    path('arpl/<int:pk>/', views.ARPLDetailView.as_view(), name='arpl_detail'),
    path('arpl/<int:pk>/assess/', views.arpl_assess, name='arpl_assess'),
    
    # Candidate history
    path('candidate/<int:learner_id>/history/', views.candidate_history, name='candidate_history'),
    
    # Reports
    path('reports/', views.reports_dashboard, name='reports'),
    path('reports/pass-rates/', views.pass_rate_report, name='pass_rate_report'),
    
    # Appeals
    path('appeals/', views.AppealListView.as_view(), name='appeal_list'),
    
    # API endpoints for AJAX
    path('api/trades-for-qualification/<int:qualification_id>/', 
         views.api_trades_for_qualification, name='api_trades_for_qualification'),
    path('api/centres-for-trade/<int:trade_id>/', 
         views.api_centres_for_trade, name='api_centres_for_trade'),
]
