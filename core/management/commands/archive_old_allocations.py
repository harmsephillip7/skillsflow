"""
Management command to archive old resource allocations.
Archives ResourceAllocationPeriod records where end_date is older than 3 years.
Should be run periodically (e.g., via cron job monthly).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import ResourceAllocationPeriod


class Command(BaseCommand):
    help = 'Archive resource allocation periods older than 3 years'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be archived without actually archiving',
        )
        parser.add_argument(
            '--years',
            type=int,
            default=3,
            help='Number of years after which to archive (default: 3)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        years = options['years']
        
        cutoff_date = timezone.now().date() - timedelta(days=years * 365)
        
        # Find allocations to archive
        allocations_to_archive = ResourceAllocationPeriod.objects.filter(
            is_archived=False,
            end_date__lt=cutoff_date
        )
        
        count = allocations_to_archive.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS(
                f'No allocations found older than {years} years (cutoff: {cutoff_date})'
            ))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN: Would archive {count} allocation(s) older than {cutoff_date}'
            ))
            
            # Show sample of what would be archived
            for allocation in allocations_to_archive[:10]:
                self.stdout.write(f'  - {allocation}')
            
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
        else:
            # Actually archive the records
            now = timezone.now()
            updated = allocations_to_archive.update(
                is_archived=True,
                archived_at=now
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'Successfully archived {updated} allocation(s) older than {cutoff_date}'
            ))
