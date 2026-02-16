"""
SOP (Standard Operating Procedures) URL Configuration

URL routing for SOP management and process flow views.
"""
from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'workflows'

urlpatterns = [
    # =====================================================
    # SOP (STANDARD OPERATING PROCEDURES)
    # =====================================================
    
    # Root redirect to SOP list
    path('', RedirectView.as_view(pattern_name='workflows:sop_list', permanent=False), name='index'),
    
    # SOP browsing
    path('sops/', views.SOPListView.as_view(), name='sop_list'),
    path('sops/category/<str:category_code>/', views.SOPCategoryView.as_view(), name='sop_category'),
    path('sops/<str:code>/', views.SOPDetailView.as_view(), name='sop_detail'),
    
    # Task management
    path('tasks/', views.TaskListView.as_view(), name='task_list'),
    path('tasks/<int:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('tasks/<int:pk>/complete/', views.complete_task, name='complete_task'),
    
    # =====================================================
    # SOP ADMIN
    # =====================================================
    path('admin/sops/', views.SOPAdminListView.as_view(), name='sop_admin_list'),
    path('admin/sops/create/', views.SOPCreateView.as_view(), name='sop_create'),
    path('admin/sops/<int:pk>/edit/', views.SOPUpdateView.as_view(), name='sop_update'),
    path('admin/sops/<int:pk>/delete/', views.sop_delete, name='sop_delete'),
    path('admin/sops/<int:pk>/toggle-publish/', views.sop_toggle_publish, name='sop_toggle_publish'),
    
    # SOP Step management
    path('admin/sops/<int:sop_pk>/steps/create/', views.sop_step_create, name='sop_step_create'),
    path('admin/steps/<int:pk>/edit/', views.sop_step_update, name='sop_step_update'),
    path('admin/steps/<int:pk>/delete/', views.sop_step_delete, name='sop_step_delete'),
    
    # SOP Category admin
    path('admin/categories/', views.SOPCategoryAdminListView.as_view(), name='category_admin_list'),
    path('admin/categories/create/', views.SOPCategoryCreateView.as_view(), name='category_create'),
    path('admin/categories/<int:pk>/edit/', views.SOPCategoryUpdateView.as_view(), name='category_update'),
    
    # =====================================================
    # BUSINESS PROCESS FLOW ADMIN
    # =====================================================
    path('process-flows/', views.ProcessFlowListView.as_view(), name='processflow_list'),
    path('process-flows/create/', views.ProcessFlowCreateView.as_view(), name='processflow_create'),
    path('process-flows/<int:pk>/', views.ProcessFlowDetailView.as_view(), name='processflow_detail'),
    path('process-flows/<int:pk>/toggle-active/', views.processflow_toggle_active, name='processflow_toggle'),
    path('process-flows/<int:pk>/stages/', views.ProcessStageEditView.as_view(), name='processstage_edit'),
    path('process-flows/<int:pk>/stages/create/', views.stage_create, name='stage_create'),
    path('process-flows/<int:pk>/transitions/toggle/', views.transition_toggle, name='transition_toggle'),
    
    # Stage operations
    path('stages/<int:pk>/update/', views.stage_update, name='stage_update'),
    path('stages/<int:pk>/delete/', views.stage_delete, name='stage_delete'),
    
    # Transition log
    path('transition-log/', views.TransitionAttemptLogListView.as_view(), name='transition_log'),
]
