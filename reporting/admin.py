"""Reporting app admin configuration"""
from django.contrib import admin
from .models import (
    ReportTemplate, SETAExportTemplate, QCTOExportConfig, ExportJob,
    NLRDSubmission, NLRDSubmissionRecord, GeneratedDocument, ScheduledReport,
    PowerBIConfig, PowerBIDataset, DashboardWidget, Dashboard, DashboardWidgetPlacement
)

admin.site.register(ReportTemplate)
admin.site.register(SETAExportTemplate)
admin.site.register(QCTOExportConfig)
admin.site.register(ExportJob)
admin.site.register(NLRDSubmission)
admin.site.register(NLRDSubmissionRecord)
admin.site.register(GeneratedDocument)
admin.site.register(ScheduledReport)
admin.site.register(PowerBIConfig)
admin.site.register(PowerBIDataset)
admin.site.register(DashboardWidget)
admin.site.register(Dashboard)
admin.site.register(DashboardWidgetPlacement)
