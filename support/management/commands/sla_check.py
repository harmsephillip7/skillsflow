from django.core.management.base import BaseCommand
from django.utils import timezone
from support.models import SupportTicket, SupportSLAConfig, SLAEvent


class Command(BaseCommand):
    help = "Check SLA breaches and optionally auto-escalate."

    def handle(self, *args, **options):
        now = timezone.now()
        changed = 0

        qs = SupportTicket.objects.filter(status__in=[
            SupportTicket.Status.OPEN,
            SupportTicket.Status.IN_PROGRESS,
            SupportTicket.Status.WAITING_ON_USER,
        ])

        for t in qs:
            cfg = SupportSLAConfig.objects.filter(module=t.module, priority=t.priority).first()

            # First response breach
            if t.first_response_at is None and t.first_response_due_at and now > t.first_response_due_at and not t.first_response_breached:
                t.first_response_breached = True
                SLAEvent.objects.create(ticket=t, event_type="first_response_breach", notes="First response SLA breached.")
                changed += 1

                if cfg and cfg.auto_escalate_on_breach and t.priority != SupportTicket.Priority.URGENT:
                    t.priority = SupportTicket.Priority.URGENT
                    SLAEvent.objects.create(ticket=t, event_type="auto_escalated", notes="Auto-escalated to URGENT.")

            # Resolution breach
            if t.resolved_at is None and t.resolution_due_at and now > t.resolution_due_at and not t.resolution_breached:
                t.resolution_breached = True
                SLAEvent.objects.create(ticket=t, event_type="resolution_breach", notes="Resolution SLA breached.")
                changed += 1

                if cfg and cfg.auto_escalate_on_breach and t.priority != SupportTicket.Priority.URGENT:
                    t.priority = SupportTicket.Priority.URGENT
                    SLAEvent.objects.create(ticket=t, event_type="auto_escalated", notes="Auto-escalated to URGENT.")

            if changed:
                t.save()

        self.stdout.write(self.style.SUCCESS(f"SLA check complete. Updated tickets: {changed}"))
