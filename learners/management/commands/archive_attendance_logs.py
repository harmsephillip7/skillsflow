"""
Management command to archive old attendance audit logs.

Archives routine VERIFY/REJECT logs older than 3 years while retaining:
- Latest OVERRIDE per field (for audit trail)
- Latest EDIT per field (for change history)
- All CREATE actions (permanent record)

Usage:
    python manage.py archive_attendance_logs [--dry-run] [--years=3]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models
from django.db.models import OuterRef, Subquery, Q, F
from datetime import timedelta
from learners.models import AttendanceAuditLog


class Command(BaseCommand):
    help = 'Archive old attendance audit logs while retaining critical override records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be archived without making changes',
        )
        parser.add_argument(
            '--years',
            type=int,
            default=3,
            help='Archive logs older than this many years (default: 3)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        years = options['years']
        
        cutoff_date = timezone.now() - timedelta(days=years * 365)
        
        self.stdout.write(self.style.NOTICE(
            f"Archiving attendance audit logs older than {cutoff_date.date()}"
        ))
        
        # Step 1: Get IDs of latest OVERRIDE per attendance+field (to keep)
        latest_overrides = AttendanceAuditLog.objects.filter(
            attendance=OuterRef('attendance'),
            field_changed=OuterRef('field_changed'),
            action__in=['OVERRIDE', 'EDIT']
        ).order_by('-changed_at').values('id')[:1]
        
        latest_override_ids = list(
            AttendanceAuditLog.objects.filter(
                action__in=['OVERRIDE', 'EDIT'],
                field_changed__isnull=False
            ).annotate(
                latest_id=Subquery(latest_overrides)
            ).filter(
                id=F('latest_id')
            ).values_list('id', flat=True)
        )
        
        self.stdout.write(f"Found {len(latest_override_ids)} latest override/edit records to preserve")
        
        # Step 2: Identify logs to archive
        logs_to_archive = AttendanceAuditLog.objects.filter(
            Q(changed_at__lt=cutoff_date) &
            Q(archived=False) &
            (
                # Archive routine VERIFY/REJECT actions
                Q(action__in=['VERIFY', 'REJECT']) |
                # Archive old OVERRIDE/EDIT that are NOT the latest
                (Q(action__in=['OVERRIDE', 'EDIT']) & ~Q(id__in=latest_override_ids))
            )
        ).exclude(
            # Never archive CREATE actions
            action='CREATE'
        )
        
        count = logs_to_archive.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No logs to archive'))
            return
        
        # Show breakdown by action type
        self.stdout.write("\nLogs to archive by action type:")
        for action, _ in AttendanceAuditLog.ACTION_CHOICES:
            action_count = logs_to_archive.filter(action=action).count()
            if action_count > 0:
                self.stdout.write(f"  {action}: {action_count}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n[DRY RUN] Would archive {count} logs"
            ))
        else:
            # Perform archival
            logs_to_archive.update(archived=True)
            
            self.stdout.write(self.style.SUCCESS(
                f"\nSuccessfully archived {count} logs"
            ))
            
            # Show summary
            total_archived = AttendanceAuditLog.objects.filter(archived=True).count()
            total_active = AttendanceAuditLog.objects.filter(archived=False).count()
            
            self.stdout.write(f"\nSummary:")
            self.stdout.write(f"  Total archived logs: {total_archived}")
            self.stdout.write(f"  Total active logs: {total_active}")
