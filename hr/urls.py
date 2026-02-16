"""
HR URL Configuration for SkillsFlow ERP
"""
from django.urls import path
from . import views
from . import admin_views

app_name = 'hr'

urlpatterns = [
    # URLs will be added as views are implemented
    # path('departments/', views.department_list, name='department_list'),
    # path('positions/', views.position_list, name='position_list'),
    # path('staff/', views.staff_list, name='staff_list'),
    # path('org-chart/', views.org_chart, name='org_chart'),
]

# HR Admin URLs - separate namespace for admin section
hr_admin_urlpatterns = [
    # Org Chart
    path('org-chart/', admin_views.OrgChartView.as_view(), name='org_chart'),
    path('org-chart/data/', admin_views.OrgChartDataView.as_view(), name='org_chart_data'),
    
    # Departments
    path('departments/', admin_views.DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', admin_views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/', admin_views.DepartmentDetailView.as_view(), name='department_detail'),
    path('departments/<int:pk>/edit/', admin_views.DepartmentUpdateView.as_view(), name='department_edit'),
    path('departments/<int:pk>/delete/', admin_views.DepartmentDeleteView.as_view(), name='department_delete'),
    
    # Positions
    path('positions/', admin_views.PositionListView.as_view(), name='position_list'),
    path('positions/create/', admin_views.PositionCreateView.as_view(), name='position_create'),
    path('positions/<int:pk>/', admin_views.PositionDetailView.as_view(), name='position_detail'),
    path('positions/<int:pk>/edit/', admin_views.PositionUpdateView.as_view(), name='position_edit'),
    path('positions/<int:pk>/delete/', admin_views.PositionDeleteView.as_view(), name='position_delete'),
    
    # Staff Profiles
    path('staff/', admin_views.StaffProfileListView.as_view(), name='staff_list'),
    path('staff/create/', admin_views.StaffProfileCreateView.as_view(), name='staff_create'),
    path('staff/<int:pk>/', admin_views.StaffProfileDetailView.as_view(), name='staff_detail'),
    path('staff/<int:pk>/edit/', admin_views.StaffProfileUpdateView.as_view(), name='staff_edit'),
    path('staff/<int:pk>/delete/', admin_views.StaffProfileDeleteView.as_view(), name='staff_delete'),
    
    # Position Tasks
    path('tasks/create/', admin_views.PositionTaskCreateView.as_view(), name='task_create'),
    path('tasks/<int:pk>/edit/', admin_views.PositionTaskUpdateView.as_view(), name='task_edit'),
    path('tasks/<int:pk>/delete/', admin_views.PositionTaskDeleteView.as_view(), name='task_delete'),
]
