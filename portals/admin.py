"""Portals app admin configuration"""
from django.contrib import admin
from .models import (
    PortalConfiguration, PortalWidget, PortalMenuItem, Announcement, AnnouncementRead,
    Notification, NotificationPreference, PushSubscription, PortalMessage, 
    MessageAttachment, UserActivity
)

admin.site.register(PortalConfiguration)
admin.site.register(PortalWidget)
admin.site.register(PortalMenuItem)
admin.site.register(Announcement)
admin.site.register(AnnouncementRead)
admin.site.register(Notification)
admin.site.register(NotificationPreference)
admin.site.register(PushSubscription)
admin.site.register(PortalMessage)
admin.site.register(MessageAttachment)
admin.site.register(UserActivity)
