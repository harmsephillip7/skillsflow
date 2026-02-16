import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


# -----------------------------
# Shared / Helpers
# -----------------------------
class TimestampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SupportModule(models.TextChoices):
    CRM = "crm", "CRM / Leads"
    TENDERS = "tenders", "Tenders"
    LMS = "lms", "LMS / Sync"
    HR = "hr", "HR"
    FINANCE = "finance", "Finance"
    OTHER = "other", "Other"


# -----------------------------
# Knowledge Base / Guides
# -----------------------------
class SupportCategory(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=80,
        blank=True,
        help_text="Optional icon name / identifier."
    )
    sort_order = models.PositiveIntegerField(default=0)

    # Optional: bind a category to a module for better recommendations
    module = models.CharField(
        max_length=30,
        choices=SupportModule.choices,
        default=SupportModule.OTHER,
    )

    class Meta:
        ordering = ["sort_order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class KnowledgeBaseArticle(TimestampedModel):
    category = models.ForeignKey(SupportCategory, on_delete=models.PROTECT, related_name="articles")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.TextField(blank=True)
    body = models.TextField(help_text="Use Markdown-style formatting.")
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)

    # For “recommended articles”
    module = models.CharField(
        max_length=30,
        choices=SupportModule.choices,
        default=SupportModule.OTHER,
    )

    # quick keyword tags for matching e.g. "lead, pipeline, enrollment"
    keywords = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords.")

    class Meta:
        ordering = ["-is_featured", "-updated_at", "title"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ArticleFeedback(TimestampedModel):
    article = models.ForeignKey(KnowledgeBaseArticle, on_delete=models.CASCADE, related_name="feedback")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="article_feedback")
    is_helpful = models.BooleanField()
    comment = models.TextField(blank=True)

    class Meta:
        unique_together = ("article", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} -> {self.article} ({'helpful' if self.is_helpful else 'not helpful'})"


class TrainingGuide(TimestampedModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.TextField(blank=True)
    content = models.TextField(help_text="Guide content (Markdown).")
    estimated_minutes = models.PositiveIntegerField(default=10)
    difficulty = models.CharField(
        max_length=20,
        choices=[("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")],
        default="beginner",
    )
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    module = models.CharField(
        max_length=30,
        choices=SupportModule.choices,
        default=SupportModule.OTHER,
    )

    class Meta:
        ordering = ["-is_featured", "difficulty", "title"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class GuideProgress(TimestampedModel):
    guide = models.ForeignKey(TrainingGuide, on_delete=models.CASCADE, related_name="progress")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="guide_progress")
    is_completed = models.BooleanField(default=False)
    last_viewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("guide", "user")
        ordering = ["-updated_at"]


# -----------------------------
# Ticketing + Routing + SLA
# -----------------------------
class SupportSLAConfig(TimestampedModel):
    """
    SLA rules by module + priority.
    Example: CRM urgent -> first_response 30 min, resolution 4h
    """
    module = models.CharField(max_length=30, choices=SupportModule.choices, default=SupportModule.CRM)
    priority = models.CharField(max_length=20, default="normal")
    first_response_minutes = models.PositiveIntegerField(default=240)  # 4h
    resolution_minutes = models.PositiveIntegerField(default=2880)     # 48h
    auto_escalate_on_breach = models.BooleanField(default=True)

    class Meta:
        unique_together = ("module", "priority")
        ordering = ["module", "priority"]

    def __str__(self):
        return f"{self.module}:{self.priority}"


class SupportRoutingRule(TimestampedModel):
    """
    Simple routing: module -> group name -> (optional) fallback user
    """
    module = models.CharField(max_length=30, choices=SupportModule.choices, unique=True)
    group_name = models.CharField(max_length=150, help_text="Django Group name, e.g. 'Support - CRM'")
    fallback_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="support_routing_fallbacks"
    )

    def __str__(self):
        return f"{self.module} -> {self.group_name}"


class SupportTicket(TimestampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        WAITING_ON_USER = "waiting_on_user", "Waiting on User"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_tickets")

    module = models.CharField(
        max_length=30,
        choices=SupportModule.choices,
        default=SupportModule.CRM,  # CRM is critical, default here
    )

    subject = models.CharField(max_length=200)
    category = models.ForeignKey(SupportCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets")
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    description = models.TextField()

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
    )

    last_activity_at = models.DateTimeField(default=timezone.now)

    # SLA timestamps
    first_response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # breach flags
    first_response_breached = models.BooleanField(default=False)
    resolution_breached = models.BooleanField(default=False)

    class Meta:
        ordering = ["-last_activity_at", "-created_at"]

    def touch(self):
        self.last_activity_at = timezone.now()
        self.save(update_fields=["last_activity_at", "updated_at"])

    def __str__(self):
        return f"{self.subject} ({self.get_status_display()})"


class TicketMessage(TimestampedModel):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ticket_messages")
    body = models.TextField()
    is_internal_note = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]


class TicketAttachment(TimestampedModel):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="attachments")
    message = models.ForeignKey("TicketMessage", null=True, blank=True, on_delete=models.SET_NULL, related_name="attachments")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to="support_attachments/%Y/%m/")
    original_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.original_name and self.file:
            self.original_name = getattr(self.file, "name", "")[:255]
        super().save(*args, **kwargs)


class SLAEvent(TimestampedModel):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="sla_events")
    event_type = models.CharField(max_length=50)  # e.g. "first_response_breach"
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


# -----------------------------
# Guided Tours (Onboarding)
# -----------------------------
class OnboardingChecklist(TimestampedModel):
    """
    One checklist per role (use Group name as role label, e.g. "CRM Officer")
    """
    role_name = models.CharField(max_length=150, unique=True)
    module = models.CharField(max_length=30, choices=SupportModule.choices, default=SupportModule.CRM)
    title = models.CharField(max_length=200, default="Getting started")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.role_name} ({self.module})"


class OnboardingItem(TimestampedModel):
    checklist = models.ForeignKey(OnboardingChecklist, on_delete=models.CASCADE, related_name="items")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    link_url = models.CharField(max_length=255, blank=True)  # internal URL or external doc
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class UserOnboardingProgress(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="onboarding_progress")
    item = models.ForeignKey(OnboardingItem, on_delete=models.CASCADE, related_name="user_progress")
    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "item")
        ordering = ["-updated_at"]
