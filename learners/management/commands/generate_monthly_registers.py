"""
Management command to generate monthly attendance register deliverables.

This command automatically creates attendance register PDF deliverables for all
active NOT (Training Notification) projects for the previous month.

Usage:
    # Generate for previous month (default)
    python manage.py generate_monthly_registers
    
    # Generate for a specific month
    python manage.py generate_monthly_registers --year 2024 --month 6
    
    # Generate for a specific project only
    python manage.py generate_monthly_registers --project-id 123
    
    # Dry run (don't create deliverables, just show what would be created)
    python manage.py generate_monthly_registers --dry-run
"""

from datetime import date
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import TrainingNotification
from learners.services import AttendanceRegisterService


class Command(BaseCommand):
    help = 'Generate monthly attendance register deliverables for active NOT projects'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            help='Year for the attendance register (default: previous month\'s year)',
        )
        parser.add_argument(
            '--month',
            type=int,
            help='Month for the attendance register (default: previous month)',
        )
        parser.add_argument(
            '--project-id',
            type=int,
            help='Generate for a specific project ID only',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be generated without actually creating deliverables',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate even if a deliverable already exists for the period',
        )

    def handle(self, *args, **options):
        # Determine the target month
        today = date.today()
        
        if options['year'] and options['month']:
            year = options['year']
            month = options['month']
        else:
            # Default to previous month
            previous_month = today - relativedelta(months=1)
            year = previous_month.year
            month = previous_month.month
        
        dry_run = options['dry_run']
        force = options['force']
        project_id = options.get('project_id')
        
        self.stdout.write(
            self.style.NOTICE(f"Generating attendance registers for {month}/{year}")
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No deliverables will be created"))
        
        # Get active projects
        projects = TrainingNotification.objects.filter(
            status__in=['ACTIVE', 'IN_PROGRESS', 'APPROVED']
        )
        
        if project_id:
            projects = projects.filter(pk=project_id)
            if not projects.exists():
                raise CommandError(f"Project with ID {project_id} not found or not active")
        
        self.stdout.write(f"Found {projects.count()} active project(s)")
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for project in projects:
            self.stdout.write(f"\nProcessing: {project.reference_number} - {project.title}")
            
            try:
                service = AttendanceRegisterService(project, year, month)
                
                # Check if register already exists
                existing = self._check_existing_deliverable(project, year, month)
                
                if existing and not force:
                    self.stdout.write(
                        self.style.WARNING(f"  ⏩ Skipped - Deliverable already exists (use --force to override)")
                    )
                    skipped_count += 1
                    continue
                
                # Get register data to check if there are any learners
                register_data = service.get_register_data()
                
                if not register_data['learners']:
                    self.stdout.write(
                        self.style.WARNING(f"  ⏩ Skipped - No learners found for this project")
                    )
                    skipped_count += 1
                    continue
                
                learner_count = len(register_data['learners'])
                total_records = register_data['summary']['total_present'] + register_data['summary']['total_absent']
                
                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ Would create deliverable ({learner_count} learners, {total_records} attendance records)"
                        )
                    )
                else:
                    with transaction.atomic():
                        deliverable = service.create_deliverable_record()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ Created deliverable: {deliverable.title} "
                                f"({learner_count} learners, {total_records} records)"
                            )
                        )
                
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Error: {str(e)}")
                )
                error_count += 1
        
        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(f"Generated: {success_count}") if success_count else f"Generated: {success_count}"
        )
        self.stdout.write(f"Skipped: {skipped_count}")
        if error_count:
            self.stdout.write(self.style.ERROR(f"Errors: {error_count}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nThis was a dry run. No deliverables were created."))
    
    def _check_existing_deliverable(self, project, year, month):
        """Check if a deliverable already exists for this month."""
        from core.models import NOTDeliverable
        
        month_names = [
            '', 'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        month_name = month_names[month]
        
        # Look for existing attendance register deliverable
        return NOTDeliverable.objects.filter(
            training_notification=project,
            title__icontains=f"Attendance Register - {month_name} {year}"
        ).exists()
