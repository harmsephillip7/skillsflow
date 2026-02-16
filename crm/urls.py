"""
CRM URL Configuration
"""
from django.urls import path, include
from . import views
from . import inbox_views
from . import pipeline_views
from . import pipeline_settings_views
from . import campaign_views
from . import analytics_views
from . import webhook_views
from . import quote_views
from . import scanner_views
from . import webform_views
from . import webform_settings_views
from . import marketing_dashboard_views
from . import settings_views

app_name = 'crm'

urlpatterns = [
    # Dashboard
    path('', views.CRMDashboardView.as_view(), name='dashboard'),
    
    # Marketing Analytics Dashboard
    path('marketing/', marketing_dashboard_views.marketing_dashboard, name='marketing_dashboard'),
    path('marketing/social/', marketing_dashboard_views.social_analytics, name='social_analytics'),
    path('marketing/content/', marketing_dashboard_views.content_analytics, name='content_analytics'),
    path('marketing/web/', marketing_dashboard_views.web_analytics, name='web_analytics'),
    
    # Marketing API endpoints (for charts)
    path('marketing/api/social-trend/', marketing_dashboard_views.api_social_trend, name='api_social_trend'),
    path('marketing/api/web-trend/', marketing_dashboard_views.api_web_trend, name='api_web_trend'),
    path('marketing/api/engagement-breakdown/', marketing_dashboard_views.api_engagement_breakdown, name='api_engagement_breakdown'),
    path('marketing/api/traffic-sources/', marketing_dashboard_views.api_traffic_sources, name='api_traffic_sources'),
    
    # Pipeline Settings (Configuration)
    path('settings/pipelines/', pipeline_settings_views.PipelineSettingsListView.as_view(), name='pipeline_settings'),
    path('settings/pipelines/create/', pipeline_settings_views.PipelineCreateView.as_view(), name='pipeline_create'),
    path('settings/pipelines/<int:pk>/', pipeline_settings_views.PipelineDetailView.as_view(), name='pipeline_detail_settings'),
    path('settings/pipelines/<int:pk>/update/', pipeline_settings_views.PipelineUpdateView.as_view(), name='pipeline_update'),
    path('settings/pipelines/<int:pk>/delete/', pipeline_settings_views.PipelineDeleteView.as_view(), name='pipeline_delete'),
    path('settings/pipelines/<int:pipeline_pk>/stages/create/', pipeline_settings_views.StageCreateView.as_view(), name='stage_create'),
    path('settings/pipelines/<int:pipeline_pk>/stages/reorder/', pipeline_settings_views.StageReorderView.as_view(), name='stage_reorder'),
    path('settings/stages/<int:pk>/update/', pipeline_settings_views.StageUpdateView.as_view(), name='stage_update'),
    path('settings/stages/<int:pk>/delete/', pipeline_settings_views.StageDeleteView.as_view(), name='stage_delete'),
    path('settings/stages/<int:stage_pk>/blueprint/', pipeline_settings_views.BlueprintUpdateView.as_view(), name='blueprint_update'),
    path('settings/stages/<int:stage_pk>/transitions/', pipeline_settings_views.StageTransitionRulesView.as_view(), name='stage_transitions'),
    
    # Pipeline Hub (Unified - NEW!)
    path('pipeline-hub/', views.PipelineHubView.as_view(), name='pipeline_hub'),
    
    # Sales Pipeline Dashboard (Legacy - still functional)
    path('pipeline/', views.SalesPipelineView.as_view(), name='sales_pipeline'),
    path('pipeline/move-stage/', views.PipelineStageUpdateView.as_view(), name='pipeline_move_stage'),
    path('pipeline/move-stage-by-code/', views.PipelineMoveStageByCodeView.as_view(), name='pipeline_move_stage_by_code'),
    path('pipeline/quick-actions/', views.LeadQuickActionsView.as_view(), name='lead_quick_actions'),
    path('pipeline/pre-approve/', views.LeadPreApproveView.as_view(), name='lead_pre_approve'),
    
    # Pipeline Stage Update (for AJAX drag-drop)
    path('api/pipeline/stage-update/', views.PipelineStageUpdateView.as_view(), name='pipeline_stage_update'),
    
    # Notifications
    path('notifications/', views.AgentNotificationsView.as_view(), name='notifications'),
    path('api/notifications/', views.NotificationAPIView.as_view(), name='notifications_api'),
    
    # Analytics
    path('analytics/', analytics_views.AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    path('analytics/api/<str:metric_type>/', analytics_views.AnalyticsAPIView.as_view(), name='analytics_api'),
    
    # Leads
    path('leads/', views.LeadListView.as_view(), name='lead_list'),
    path('leads/add/', views.LeadCreateView.as_view(), name='lead_create'),
    path('leads/<int:pk>/', views.LeadDetailView.as_view(), name='lead_detail'),
    path('leads/<int:pk>/edit/', views.LeadUpdateView.as_view(), name='lead_update'),
    
    # Lead Actions (AJAX)
    path('leads/<int:pk>/status/', views.lead_quick_status, name='lead_quick_status'),
    path('leads/<int:pk>/activity/', views.lead_add_activity, name='lead_add_activity'),
    path('leads/<int:pk>/assign/', views.lead_assign, name='lead_assign'),
    path('leads/<int:pk>/follow-up/', views.lead_set_follow_up, name='lead_set_follow_up'),
    
    # Quotes
    path('quotes/', quote_views.QuoteListView.as_view(), name='quote_list'),
    path('quotes/<int:pk>/', quote_views.QuoteDetailView.as_view(), name='quote_detail'),
    path('quotes/<int:pk>/download/', quote_views.download_quote_pdf, name='download_quote_pdf'),
    path('quotes/<int:pk>/send-email/', quote_views.send_quote_email, name='send_quote_email'),
    path('quotes/<int:pk>/send-whatsapp/', quote_views.send_quote_whatsapp, name='send_quote_whatsapp'),
    path('leads/<int:lead_pk>/create-quote/', quote_views.QuoteCreateView.as_view(), name='quote_create_for_lead'),
    path('leads/<int:lead_pk>/quick-quote/', quote_views.QuickQuoteView.as_view(), name='quick_quote'),
    
    # Quote AJAX endpoints
    path('api/intake-details/', quote_views.get_intake_details, name='get_intake_details'),
    path('api/qualification-pricing/', quote_views.get_qualification_pricing, name='get_qualification_pricing'),
    path('api/template-payment-options/', quote_views.get_template_payment_options, name='get_template_payment_options'),
    path('api/leads/<int:lead_pk>/quick-quote-data/', quote_views.quick_quote_data, name='quick_quote_data'),
    path('api/leads/<int:lead_pk>/quick-quote-create/', quote_views.quick_quote_create, name='quick_quote_create'),
    
    # Bulk Messaging
    path('bulk-messaging/', views.BulkMessagingListView.as_view(), name='bulk_messaging'),
    
    # Lead Sources
    path('sources/', views.LeadSourceListView.as_view(), name='source_list'),
    path('sources/add/', views.LeadSourceCreateView.as_view(), name='source_create'),
    
    # Omnichannel Inbox
    path('inbox/', inbox_views.InboxListView.as_view(), name='inbox_list'),
    path('inbox/stats/', inbox_views.InboxStatsView.as_view(), name='inbox_stats'),
    path('inbox/search-leads/', inbox_views.SearchLeadsView.as_view(), name='inbox_search_leads'),
    path('inbox/<uuid:pk>/', inbox_views.ConversationDetailView.as_view(), name='conversation_detail'),
    path('inbox/<uuid:pk>/send/', inbox_views.SendMessageView.as_view(), name='send_message'),
    path('inbox/<uuid:pk>/assign/', inbox_views.AssignConversationView.as_view(), name='assign_conversation'),
    path('inbox/<uuid:pk>/status/', inbox_views.UpdateConversationStatusView.as_view(), name='update_conversation_status'),
    path('inbox/<uuid:pk>/tags/', inbox_views.AddTagView.as_view(), name='conversation_tags'),
    path('inbox/<uuid:pk>/link-lead/', inbox_views.LinkLeadView.as_view(), name='link_lead'),
    
    # Opportunity Pipeline
    path('opportunities/', pipeline_views.OpportunityBoardView.as_view(), name='opportunity_board'),
    path('opportunities/list/', pipeline_views.OpportunityListView.as_view(), name='opportunity_list'),
    path('opportunities/add/', pipeline_views.OpportunityCreateView.as_view(), name='opportunity_create'),
    path('opportunities/<uuid:pk>/', pipeline_views.OpportunityDetailView.as_view(), name='opportunity_detail'),
    path('opportunities/<uuid:pk>/edit/', pipeline_views.OpportunityUpdateView.as_view(), name='opportunity_update'),
    path('opportunities/<uuid:pk>/stage/', pipeline_views.OpportunityStageUpdateView.as_view(), name='opportunity_stage_update'),
    path('opportunities/<uuid:pk>/convert/', pipeline_views.ConvertToApplicationView.as_view(), name='opportunity_convert'),
    
    # Applications
    path('applications/', pipeline_views.ApplicationListView.as_view(), name='application_list'),
    path('applications/<uuid:pk>/', pipeline_views.ApplicationDetailView.as_view(), name='application_detail'),
    path('applications/<uuid:pk>/status/', pipeline_views.ApplicationStatusUpdateView.as_view(), name='application_status_update'),
    
    # Campaigns
    path('campaigns/', campaign_views.CampaignListView.as_view(), name='campaign_list'),
    path('campaigns/add/', campaign_views.CampaignCreateView.as_view(), name='campaign_create'),
    path('campaigns/<uuid:pk>/', campaign_views.CampaignDetailView.as_view(), name='campaign_detail'),
    path('campaigns/<uuid:pk>/edit/', campaign_views.CampaignUpdateView.as_view(), name='campaign_update'),
    path('campaigns/<uuid:pk>/recipients/', campaign_views.CampaignAddRecipientsView.as_view(), name='campaign_add_recipients'),
    path('campaigns/<uuid:pk>/submit/', campaign_views.CampaignSubmitForApprovalView.as_view(), name='campaign_submit_approval'),
    path('campaigns/<uuid:pk>/approval/', campaign_views.CampaignApprovalView.as_view(), name='campaign_approval'),
    path('campaigns/<uuid:pk>/schedule/', campaign_views.CampaignScheduleView.as_view(), name='campaign_schedule'),
    path('campaigns/<uuid:pk>/send/', campaign_views.CampaignSendView.as_view(), name='campaign_send'),
    
    # Message Templates
    path('templates/', campaign_views.TemplateListView.as_view(), name='template_list'),
    path('templates/add/', campaign_views.TemplateCreateView.as_view(), name='template_create'),
    path('templates/<uuid:pk>/edit/', campaign_views.TemplateUpdateView.as_view(), name='template_update'),
    path('templates/<uuid:pk>/preview/', campaign_views.TemplatePreviewView.as_view(), name='template_preview'),
    
    # Webhooks (external callbacks)
    path('webhooks/meta/', webhook_views.MetaWebhookView.as_view(), name='meta_webhook'),
    path('webhooks/sms/<str:provider>/', webhook_views.SMSWebhookView.as_view(), name='sms_webhook'),
    path('webhooks/microsoft/', webhook_views.MicrosoftWebhookView.as_view(), name='microsoft_webhook'),
    path('webhooks/track/<str:tracking_type>/', webhook_views.EngagementTrackingView.as_view(), name='engagement_tracking'),
    path('webhooks/quote-view/', webhook_views.QuoteViewTrackingView.as_view(), name='quote_view_tracking'),
    
    # Web Form Webhooks (Gravity Forms, etc.)
    path('webhooks/web-forms/<uuid:source_id>/', webform_views.WebFormWebhookView.as_view(), name='webform_webhook'),
    path('webhooks/web-forms/<uuid:source_id>/test/', webform_views.WebFormTestView.as_view(), name='webform_webhook_test'),
    
    # Web Form Settings (UI for managing integrations)
    path('settings/webforms/', webform_settings_views.WebFormSourceListView.as_view(), name='webform_sources'),
    path('settings/webforms/create/', webform_settings_views.WebFormSourceCreateView.as_view(), name='webform_source_create'),
    path('settings/webforms/sources/<uuid:pk>/', webform_settings_views.WebFormSourceDetailView.as_view(), name='webform_source_detail'),
    path('settings/webforms/sources/<uuid:pk>/edit/', webform_settings_views.WebFormSourceUpdateView.as_view(), name='webform_source_update'),
    path('settings/webforms/sources/<uuid:pk>/delete/', webform_settings_views.WebFormSourceDeleteView.as_view(), name='webform_source_delete'),
    path('settings/webforms/sources/<uuid:pk>/regenerate-secret/', webform_settings_views.WebFormSourceRegenerateSecretView.as_view(), name='webform_source_regenerate_secret'),
    path('settings/webforms/sources/<uuid:source_pk>/mappings/create/', webform_settings_views.WebFormMappingCreateView.as_view(), name='webform_mapping_create'),
    path('settings/webforms/mappings/<uuid:pk>/update/', webform_settings_views.WebFormMappingUpdateView.as_view(), name='webform_mapping_update'),
    path('settings/webforms/mappings/<uuid:pk>/delete/', webform_settings_views.WebFormMappingDeleteView.as_view(), name='webform_mapping_delete'),
    path('settings/webforms/submissions/', webform_settings_views.WebFormSubmissionListView.as_view(), name='webform_submissions'),
    
    # Public Pre-Approval Portal (NO LOGIN REQUIRED)
    path('portal/pre-approval/<uuid:token>/', views.PreApprovalPortalView.as_view(), name='pre_approval_portal'),
    path('portal/pre-approval/<uuid:token>/accept/', views.PreApprovalAcceptView.as_view(), name='pre_approval_accept'),
    path('portal/pre-approval/<uuid:token>/parent-consent/', views.PreApprovalParentConsentView.as_view(), name='pre_approval_parent_consent'),
    path('portal/pre-approval/<uuid:token>/success/', views.PreApprovalSuccessView.as_view(), name='pre_approval_success'),
    path('portal/pre-approval/<uuid:token>/download/', views.PreApprovalPDFDownloadView.as_view(), name='pre_approval_download'),
    
    # Public Document Upload Portal (NO LOGIN REQUIRED)
    path('portal/documents/<uuid:token>/', views.DocumentUploadPortalView.as_view(), name='document_upload_portal'),
    path('portal/documents/<uuid:token>/upload/', views.DocumentUploadSubmitView.as_view(), name='document_upload_submit'),
    path('portal/documents/<uuid:token>/success/', views.DocumentUploadSuccessView.as_view(), name='document_upload_success'),
    
    # Send Document Upload Link (AJAX - requires login)
    path('leads/<int:pk>/send-document-link/', views.SendDocumentUploadLinkView.as_view(), name='send_document_link'),
    
    # Card Scanner
    path('scan-card/', scanner_views.card_scanner_view, name='card_scanner'),
    path('api/scan-card/', scanner_views.scan_card_api, name='scan_card_api'),
    path('api/create-lead-from-scan/', scanner_views.create_lead_from_scan, name='create_lead_from_scan'),
    path('api/create-leads-batch/', scanner_views.create_leads_batch, name='create_leads_batch'),
    path('api/check-duplicate-lead/', scanner_views.check_duplicate_lead, name='check_duplicate_lead'),
    
    # Compliance Alerts Dashboard
    path('compliance-alerts/', views.ComplianceAlertsDashboardView.as_view(), name='compliance_alerts'),
    
    # Sales Commission Dashboard
    path('commission-dashboard/', views.SalesCommissionDashboardView.as_view(), name='commission_dashboard'),
    path('commission-dashboard/export/', views.SalesCommissionExportView.as_view(), name='commission_export'),
    
    # Lead Sales Assignment API
    path('api/leads/<int:lead_id>/sales-assignments/', views.LeadSalesAssignmentView.as_view(), name='lead_sales_assignments'),
    
    # Lead Pipeline Assignment API
    path('api/leads/<int:lead_id>/pipeline/', views.LeadPipelineAssignmentView.as_view(), name='lead_pipeline_assignment'),
    
    # CRM Settings (User-friendly admin replacement)
    path('settings/', settings_views.CRMSettingsView.as_view(), name='crm_settings'),
    path('settings/api/lead-sources/', settings_views.LeadSourceAPIView.as_view(), name='settings_lead_sources_api'),
    path('settings/api/required-documents/', settings_views.RequiredDocumentAPIView.as_view(), name='settings_required_documents_api'),
    path('settings/api/required-documents/reorder/', settings_views.RequiredDocumentReorderView.as_view(), name='settings_required_documents_reorder'),
]
