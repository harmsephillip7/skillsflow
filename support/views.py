from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Q, F, Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import TicketCreateForm, TicketMessageForm
from .models import (
    SupportCategory, KnowledgeBaseArticle, ArticleFeedback,
    TrainingGuide, GuideProgress,
    SupportTicket, TicketMessage, TicketAttachment,
    SupportRoutingRule, SupportSLAConfig, SLAEvent,
    OnboardingChecklist, OnboardingItem, UserOnboardingProgress,
    SupportModule
)


# -----------------------------
# Helpers: Routing + SLA
# -----------------------------
def _pick_least_loaded_agent(users_qs):
    """
    Pick agent with least open tickets assigned (rough load balancing).
    """
    users = list(users_qs)
    if not users:
        return None
    # annotate load
    best = None
    best_count = None
    for u in users:
        c = SupportTicket.objects.filter(assigned_to=u, status__in=[
            SupportTicket.Status.OPEN,
            SupportTicket.Status.IN_PROGRESS,
            SupportTicket.Status.WAITING_ON_USER,
        ]).count()
        if best is None or c < best_count:
            best = u
            best_count = c
    return best


def auto_assign_ticket(ticket: SupportTicket):
    """
    Role-based routing:
      - If module=CRM -> group "Support - CRM"
      - Else module-specific group set in SupportRoutingRule
    """
    rule = SupportRoutingRule.objects.filter(module=ticket.module).first()

    # Default conventions if rule not created
    group_name = rule.group_name if rule else {
        SupportModule.CRM: "Support - CRM",
        SupportModule.TENDERS: "Support - Tenders",
        SupportModule.LMS: "Support - LMS",
        SupportModule.HR: "Support - HR",
        SupportModule.FINANCE: "Support - Finance",
    }.get(ticket.module, "Support - General")

    group = Group.objects.filter(name=group_name).first()
    if group:
        agents = group.user_set.filter(is_active=True, is_staff=True)
        assignee = _pick_least_loaded_agent(agents)
        if assignee:
            ticket.assigned_to = assignee
            ticket.save(update_fields=["assigned_to", "updated_at"])
            return

    # fallback if group missing
    if rule and rule.fallback_assignee:
        ticket.assigned_to = rule.fallback_assignee
        ticket.save(update_fields=["assigned_to", "updated_at"])
        return

    # last resort: any staff
    any_staff = _pick_least_loaded_agent(
        type(ticket.requester).objects.filter(is_staff=True, is_active=True)  # works with custom User
    )
    if any_staff:
        ticket.assigned_to = any_staff
        ticket.save(update_fields=["assigned_to", "updated_at"])


def apply_sla(ticket: SupportTicket):
    """
    Sets first_response_due_at and resolution_due_at from SupportSLAConfig.
    """
    cfg = SupportSLAConfig.objects.filter(module=ticket.module, priority=ticket.priority).first()
    if not cfg:
        # reasonable defaults
        first_minutes = 240
        resolution_minutes = 2880
    else:
        first_minutes = cfg.first_response_minutes
        resolution_minutes = cfg.resolution_minutes

    now = timezone.now()
    ticket.first_response_due_at = now + timezone.timedelta(minutes=first_minutes)
    ticket.resolution_due_at = now + timezone.timedelta(minutes=resolution_minutes)
    ticket.save(update_fields=["first_response_due_at", "resolution_due_at", "updated_at"])


def sla_update_on_message(ticket: SupportTicket, sender_is_agent: bool):
    """
    If an agent posts the first response, stamp first_response_at.
    """
    if sender_is_agent and ticket.first_response_at is None:
        ticket.first_response_at = timezone.now()
        ticket.save(update_fields=["first_response_at", "updated_at"])


# -----------------------------
# Recommended Articles
# -----------------------------
def recommended_articles_for(module: str, category_slug: str | None, subject_hint: str | None = None):
    qs = KnowledgeBaseArticle.objects.filter(is_published=True)

    # module boost
    mod_qs = qs.filter(module=module)

    # category boost if present
    if category_slug:
        mod_qs = mod_qs.filter(category__slug=category_slug)

    # keyword/subject matching
    if subject_hint:
        tokens = [t.strip().lower() for t in subject_hint.split() if len(t.strip()) >= 4]
        if tokens:
            kw_q = Q()
            for t in tokens[:8]:
                kw_q |= Q(title__icontains=t) | Q(summary__icontains=t) | Q(keywords__icontains=t)
            mod_qs = mod_qs.filter(kw_q)

    # rank: featured + view_count + helpful feedback ratio (approx)
    mod_qs = mod_qs.annotate(helpful=Count("feedback", filter=Q(feedback__is_helpful=True)))
    return mod_qs.order_by("-is_featured", "-helpful", "-view_count", "-updated_at")[:6]


# -----------------------------
# Views
# -----------------------------
@login_required
def help_center(request):
    query = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()
    module = (request.GET.get("module") or SupportModule.CRM).strip()

    categories = SupportCategory.objects.all()

    articles = KnowledgeBaseArticle.objects.filter(is_published=True)
    if category_slug:
        articles = articles.filter(category__slug=category_slug)

    if query:
        articles = articles.filter(
            Q(title__icontains=query) |
            Q(summary__icontains=query) |
            Q(body__icontains=query) |
            Q(category__name__icontains=query)
        )

    featured = KnowledgeBaseArticle.objects.filter(is_published=True, is_featured=True)[:6]
    recommended = recommended_articles_for(module=module, category_slug=category_slug or None, subject_hint=query or None)

    context = {
        "categories": categories,
        "articles": articles.select_related("category")[:50],
        "featured": featured.select_related("category"),
        "recommended": recommended.select_related("category"),
        "query": query,
        "category_slug": category_slug,
        "module": module,
        "modules": SupportModule.choices,
    }
    return render(request, "support/help_center.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def article_detail(request, slug):
    article = get_object_or_404(KnowledgeBaseArticle, slug=slug, is_published=True)

    KnowledgeBaseArticle.objects.filter(pk=article.pk).update(view_count=F("view_count") + 1)
    article.refresh_from_db(fields=["view_count"])

    existing_feedback = ArticleFeedback.objects.filter(article=article, user=request.user).first()

    if request.method == "POST":
        is_helpful = request.POST.get("is_helpful")
        comment = (request.POST.get("comment") or "").strip()

        if is_helpful not in {"true", "false"}:
            messages.error(request, "Please choose whether this article was helpful.")
            return redirect("support:article_detail", slug=article.slug)

        ArticleFeedback.objects.update_or_create(
            article=article,
            user=request.user,
            defaults={"is_helpful": is_helpful == "true", "comment": comment},
        )
        messages.success(request, "Thanks — your feedback helps us improve the knowledge base.")
        return redirect("support:article_detail", slug=article.slug)

    helpful_count = article.feedback.filter(is_helpful=True).count()
    not_helpful_count = article.feedback.filter(is_helpful=False).count()

    context = {
        "article": article,
        "existing_feedback": existing_feedback,
        "helpful_count": helpful_count,
        "not_helpful_count": not_helpful_count,
    }
    return render(request, "support/article_detail.html", context)


@login_required
def training_guides(request):
    query = (request.GET.get("q") or "").strip()
    difficulty = (request.GET.get("difficulty") or "").strip()
    module = (request.GET.get("module") or "").strip()

    guides = TrainingGuide.objects.filter(is_published=True)
    if module in {m[0] for m in SupportModule.choices}:
        guides = guides.filter(module=module)

    if difficulty in {"beginner", "intermediate", "advanced"}:
        guides = guides.filter(difficulty=difficulty)

    if query:
        guides = guides.filter(
            Q(title__icontains=query) |
            Q(summary__icontains=query) |
            Q(content__icontains=query)
        )

    progress_map = {p.guide_id: p for p in GuideProgress.objects.filter(user=request.user, guide__in=guides)}

    context = {
        "guides": guides[:80],
        "progress_map": progress_map,
        "query": query,
        "difficulty": difficulty,
        "module": module,
        "modules": SupportModule.choices,
    }
    return render(request, "support/training_guides.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def guide_detail(request, slug):
    guide = get_object_or_404(TrainingGuide, slug=slug, is_published=True)

    progress, _ = GuideProgress.objects.get_or_create(guide=guide, user=request.user)
    progress.last_viewed_at = timezone.now()
    progress.save(update_fields=["last_viewed_at", "updated_at"])

    if request.method == "POST":
        if request.POST.get("action") == "toggle_complete":
            progress.is_completed = not progress.is_completed
            progress.save(update_fields=["is_completed", "updated_at"])
            messages.success(request, "Progress updated.")
        return redirect("support:guide_detail", slug=guide.slug)

    return render(request, "support/guide_detail.html", {"guide": guide, "progress": progress})


@login_required
@require_http_methods(["GET", "POST"])
def contact_support(request):
    if request.method == "POST":
        form = TicketCreateForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.requester = request.user
            ticket.save()

            # SLA + routing
            apply_sla(ticket)
            auto_assign_ticket(ticket)

            # attachments (ticket-level)
            for f in request.FILES.getlist("attachments"):
                TicketAttachment.objects.create(
                    ticket=ticket,
                    uploaded_by=request.user,
                    file=f,
                    original_name=getattr(f, "name", "")[:255],
                )

            messages.success(request, "Ticket submitted. Our team will respond shortly.")
            return redirect("support:ticket_detail", ticket_id=str(ticket.id))
    else:
        form = TicketCreateForm(initial={"module": SupportModule.CRM})

    tickets = SupportTicket.objects.filter(requester=request.user)[:25]

    # Recommend KB from CRM by default (because CRM critical)
    recommended = recommended_articles_for(module=SupportModule.CRM, category_slug=None, subject_hint=None)

    return render(request, "support/contact_support.html", {"form": form, "tickets": tickets, "recommended": recommended})


@login_required
@require_http_methods(["GET", "POST"])
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)

    if ticket.requester != request.user and not request.user.is_staff and ticket.assigned_to != request.user:
        raise Http404()

    if request.method == "POST":
        form = TicketMessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.ticket = ticket
            msg.sender = request.user
            msg.save()

            # reply attachments
            for f in request.FILES.getlist("attachments"):
                TicketAttachment.objects.create(
                    ticket=ticket,
                    message=msg,
                    uploaded_by=request.user,
                    file=f,
                    original_name=getattr(f, "name", "")[:255],
                )

            # SLA stamp for first agent response
            sender_is_agent = bool(request.user.is_staff) or (ticket.assigned_to_id == request.user.id)
            sla_update_on_message(ticket, sender_is_agent=sender_is_agent)

            ticket.touch()
            messages.success(request, "Reply sent.")
            return redirect("support:ticket_detail", ticket_id=str(ticket.id))
    else:
        form = TicketMessageForm()

    # show module-driven recommendations based on ticket subject
    recommended = recommended_articles_for(module=ticket.module, category_slug=ticket.category.slug if ticket.category else None, subject_hint=ticket.subject)

    return render(request, "support/ticket_detail.html", {
        "ticket": ticket,
        "messages": ticket.messages.select_related("sender").all(),
        "attachments": ticket.attachments.select_related("uploaded_by").all(),
        "form": form,
        "recommended": recommended,
    })


# -----------------------------
# Guided tours (onboarding)
# -----------------------------
@login_required
def guided_tours(request):
    # Role = first group name, fallback "General"
    role_name = request.user.groups.first().name if request.user.groups.exists() else "General"
    checklists = OnboardingChecklist.objects.filter(is_active=True, role_name=role_name)

    # if none, show CRM default if exists
    if not checklists.exists():
        checklists = OnboardingChecklist.objects.filter(is_active=True, module=SupportModule.CRM)

    items = OnboardingItem.objects.filter(checklist__in=checklists)
    prog = {p.item_id: p for p in UserOnboardingProgress.objects.filter(user=request.user, item__in=items)}

    return render(request, "support/guided_tours.html", {
        "role_name": role_name,
        "checklists": checklists,
        "items": items,
        "progress": prog,
    })


@login_required
@require_http_methods(["POST"])
def toggle_onboarding_item(request, item_id):
    item = get_object_or_404(OnboardingItem, id=item_id)
    p, _ = UserOnboardingProgress.objects.get_or_create(user=request.user, item=item)
    p.is_done = not p.is_done
    p.done_at = timezone.now() if p.is_done else None
    p.save(update_fields=["is_done", "done_at", "updated_at"])
    return redirect("support:guided_tours")
