"""
Management command to assign existing leads to pipelines.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Lead, Pipeline, PipelineStage
from crm.services.pipeline import PipelineService


class Command(BaseCommand):
    help = 'Assign existing leads to appropriate pipelines based on their characteristics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get all leads without pipeline
        leads = Lead.objects.filter(pipeline__isnull=True)
        total = leads.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('All leads already have pipelines assigned!'))
            return
        
        self.stdout.write(f'Found {total} leads without pipeline assignment')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        assigned = 0
        skipped = 0
        
        for lead in leads:
            if not dry_run:
                # Use PipelineService to assign pipeline (handles all logic)
                pipeline = PipelineService.assign_pipeline(lead)
                
                if pipeline:
                    assigned += 1
                else:
                    skipped += 1
                    self.stdout.write(self.style.WARNING(
                        f'  SKIP: {lead.get_full_name()} - No pipeline found'
                    ))
            else:
                # Dry run - just check what pipeline would be assigned
                # Find pipeline for lead type
                pipeline = Pipeline.objects.filter(
                    campus=lead.campus,
                    is_active=True
                ).first()
                
                if pipeline:
                    self.stdout.write(
                        f'  Would assign: {lead.get_full_name()} -> {pipeline.name}'
                    )
                    assigned += 1
                else:
                    skipped += 1
            
            if assigned % 20 == 0 and assigned > 0:
                self.stdout.write(f'  Progress: {assigned}/{total}...')
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'Would assign {assigned} leads to pipelines ({skipped} skipped)'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Successfully assigned {assigned} leads to pipelines ({skipped} skipped)'
            ))
