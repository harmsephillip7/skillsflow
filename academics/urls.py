"""Academics app URL configuration"""
from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.AcademicsDashboardView.as_view(), name='dashboard'),
    
    # Qualifications - List & Detail
    path('', views.qualification_list, name='qualification_list'),
    path('qualifications/<int:pk>/', views.qualification_detail, name='qualification_detail'),
    
    # Qualifications - CRUD
    path('qualifications/create/', views.QualificationCreateView.as_view(), name='qualification_create'),
    path('qualifications/<int:pk>/edit/', views.QualificationUpdateView.as_view(), name='qualification_update'),
    path('qualifications/<int:pk>/delete/', views.QualificationDeleteView.as_view(), name='qualification_delete'),
    
    # Modules - CRUD
    path('qualifications/<int:qualification_pk>/modules/create/', views.ModuleCreateView.as_view(), name='module_create'),
    path('modules/<int:pk>/edit/', views.ModuleUpdateView.as_view(), name='module_update'),
    path('modules/<int:pk>/delete/', views.ModuleDeleteView.as_view(), name='module_delete'),
    
    # Learning Materials - CRUD
    path('qualifications/<int:qualification_pk>/materials/create/', views.LearningMaterialCreateView.as_view(), name='material_create'),
    path('materials/', views.LearningMaterialListView.as_view(), name='material_list'),
    path('materials/<int:pk>/edit/', views.LearningMaterialUpdateView.as_view(), name='material_update'),
    path('materials/<int:pk>/archive/', views.archive_material, name='material_archive'),
    
    # Personnel Registration - CRUD
    path('qualifications/<int:qualification_pk>/personnel/create/', views.PersonnelRegistrationCreateView.as_view(), name='personnel_create'),
    path('personnel/', views.PersonnelRegistrationListView.as_view(), name='personnel_list'),
    path('personnel/add/', views.StandalonePersonnelCreateView.as_view(), name='personnel_add'),
    path('personnel/<int:pk>/edit/', views.PersonnelRegistrationUpdateView.as_view(), name='personnel_update'),
    
    # Checklist
    path('checklist/<int:pk>/toggle/', views.toggle_checklist_item, name='toggle_checklist_item'),
    
    # Compliance
    path('compliance/', views.compliance_dashboard, name='compliance_dashboard'),
    
    # Alerts
    path('alerts/', views.accreditation_alerts, name='accreditation_alerts'),
    
    # QCTO Sync
    path('qcto-sync/', views.QCTOSyncDashboardView.as_view(), name='qcto_sync_dashboard'),
    path('qcto-sync/trigger/', views.trigger_qcto_sync, name='trigger_qcto_sync'),
    path('qcto-sync/change/<int:pk>/review/', views.acknowledge_qcto_change, name='acknowledge_qcto_change'),
    
    # Implementation Plans
    path('qualifications/<int:qualification_pk>/implementation-plans/', views.implementation_plan_list, name='implementation_plan_list'),
    path('qualifications/<int:qualification_pk>/implementation-plans/create/', views.implementation_plan_create, name='implementation_plan_create'),
    path('implementation-plans/<int:pk>/', views.implementation_plan_detail, name='implementation_plan_detail'),
    path('implementation-plans/<int:pk>/edit/', views.implementation_plan_edit, name='implementation_plan_edit'),
    path('implementation-plans/<int:pk>/set-default/', views.implementation_plan_set_default, name='implementation_plan_set_default'),
    path('implementation-plans/<int:pk>/activate/', views.implementation_plan_activate, name='implementation_plan_activate'),
    
    # Implementation Phases
    path('implementation-plans/<int:implementation_plan_pk>/phases/add/', views.implementation_phase_add, name='implementation_phase_add'),
    path('implementation-plans/<int:implementation_plan_pk>/phases/reorder/', views.implementation_phase_reorder, name='implementation_phase_reorder'),
    path('implementation-phases/<int:pk>/edit/', views.implementation_phase_edit, name='implementation_phase_edit'),
    path('implementation-phases/<int:pk>/delete/', views.implementation_phase_delete, name='implementation_phase_delete'),
    
    # Implementation Module Slots
    path('implementation-phases/<int:phase_pk>/modules/add/', views.implementation_module_slot_add, name='implementation_module_slot_add'),
    path('implementation-phases/<int:phase_pk>/modules/reorder/', views.implementation_module_slot_reorder, name='implementation_module_slot_reorder'),
    path('implementation-module-slots/<int:pk>/edit/', views.implementation_module_slot_edit, name='implementation_module_slot_edit'),
    path('implementation-module-slots/<int:pk>/delete/', views.implementation_module_slot_delete, name='implementation_module_slot_delete'),
    
    # Lesson Plans
    path('modules/<int:module_pk>/lesson-plans/', views.lesson_plan_list, name='lesson_plan_list'),
    path('modules/<int:module_pk>/lesson-plans/create/', views.lesson_plan_create, name='lesson_plan_create'),
    path('lesson-plans/<int:pk>/', views.lesson_plan_detail, name='lesson_plan_detail'),
    path('lesson-plans/<int:pk>/edit/', views.lesson_plan_edit, name='lesson_plan_edit'),
    path('lesson-plans/<int:pk>/delete/', views.lesson_plan_delete, name='lesson_plan_delete'),
    path('lesson-plans/<int:pk>/duplicate/', views.lesson_plan_duplicate, name='lesson_plan_duplicate'),
    
    # Campus Accreditations
    path('qualifications/<int:qualification_pk>/campus-accreditation/add/', views.campus_accreditation_add, name='campus_accreditation_add'),
    path('campus-accreditation/<int:pk>/edit/', views.campus_accreditation_edit, name='campus_accreditation_edit'),
    path('campus-accreditation/<int:pk>/delete/', views.campus_accreditation_delete, name='campus_accreditation_delete'),
    
    # Cron endpoints
    path('api/cron/expire-accreditations/', views.expire_accreditations_cron, name='expire_accreditations_cron'),
]
