"""LMS Sync app admin configuration"""
from django.contrib import admin
from .models import (
    MoodleInstance, MoodleCourse, MoodleUser, MoodleEnrollment,
    MoodleGrade, MoodleSyncLog
)

admin.site.register(MoodleInstance)
admin.site.register(MoodleCourse)
admin.site.register(MoodleUser)
admin.site.register(MoodleEnrollment)
admin.site.register(MoodleGrade)
admin.site.register(MoodleSyncLog)
