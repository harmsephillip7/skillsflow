"""
Learner Management URLs
"""
from django.urls import path
from . import views

app_name = 'learners'

urlpatterns = [
    # List and Detail views
    path('', views.LearnerListView.as_view(), name='list'),
    path('<int:pk>/', views.LearnerDetailView.as_view(), name='detail'),
    
    # Kanban view
    path('kanban/', views.LearnerKanbanView.as_view(), name='kanban'),
    path('kanban/update-status/', views.kanban_update_status, name='kanban_update_status'),
    
    # Pivot table view
    path('pivot/', views.LearnerPivotView.as_view(), name='pivot'),
    
    # Timetable view
    path('timetable/', views.TimetableView.as_view(), name='timetable'),
    
    # Performance dashboard
    path('performance/', views.PerformanceDashboardView.as_view(), name='performance'),
    
    # Import/Export (single view with tabs)
    path('import-export/', views.BulkImportView.as_view(), name='bulk_import'),
    path('import/template/<str:template_type>/', views.download_import_template, name='download_template'),
    
    # SETA exports
    path('export/', views.ExportTemplatesView.as_view(), name='export_templates'),
    path('export/<str:template_id>/', views.export_seta_data, name='export_seta_data'),
    
    # Daily Logbook
    path('logbook/<int:placement_id>/calendar/', views.daily_logbook_calendar_view, name='logbook_calendar'),
    path('logbook/<int:placement_id>/export/<int:year>/<int:month>/', views.monthly_logbook_export, name='logbook_export'),
]
