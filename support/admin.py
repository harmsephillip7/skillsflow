from django.contrib import admin
from .models import (
    SupportCategory, KnowledgeBaseArticle, ArticleFeedback,
    TrainingGuide, GuideProgress,
    SupportTicket, TicketMessage, TicketAttachment
)


@admin.register(SupportCategory)
class SupportCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "updated_at")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order", "name")


@admin.register(KnowledgeBaseArticle)
class KnowledgeBaseArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_published", "is_featured", "view_count", "updated_at")
    list_filter = ("is_published", "is_featured", "category")
    search_fields = ("title", "summary", "body")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category",)


@admin.register(ArticleFeedback)
class ArticleFeedbackAdmin(admin.ModelAdmin):
    list_display = ("article", "user", "is_helpful", "created_at")
    list_filter = ("is_helpful",)
    search_fields = ("article__title", "user__username", "comment")


@admin.register(TrainingGuide)
class TrainingGuideAdmin(admin.ModelAdmin):
    list_display = ("title", "difficulty", "estimated_minutes", "is_published", "is_featured", "updated_at")
    list_filter = ("difficulty", "is_published", "is_featured")
    search_fields = ("title", "summary", "content")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(GuideProgress)
class GuideProgressAdmin(admin.ModelAdmin):
    list_display = ("guide", "user", "is_completed", "last_viewed_at", "updated_at")
    list_filter = ("is_completed", "guide")


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    fields = ("sender", "body", "is_internal_note", "created_at")
    readonly_fields = ("created_at",)


class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 0
    fields = ("uploaded_by", "original_name", "file", "created_at")
    readonly_fields = ("created_at",)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "requester", "status", "priority", "assigned_to", "last_activity_at")
    list_filter = ("status", "priority")
    search_fields = ("subject", "description", "requester__username", "requester__email")
    autocomplete_fields = ("requester", "assigned_to", "category")
    inlines = [TicketMessageInline, TicketAttachmentInline]
