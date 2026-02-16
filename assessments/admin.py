"""Assessments app admin configuration"""
from django.contrib import admin
from .models import (
    AssessmentActivity, AQP, AssessmentResult, ModerationRecord,
    PoESubmission, PoEDocument, ExternalAssessment, AppealRecord
)

admin.site.register(AssessmentActivity)
admin.site.register(AQP)
admin.site.register(AssessmentResult)
admin.site.register(ModerationRecord)
admin.site.register(PoESubmission)
admin.site.register(PoEDocument)
admin.site.register(ExternalAssessment)
admin.site.register(AppealRecord)
