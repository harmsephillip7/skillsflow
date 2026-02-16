"""
Management command to calculate monthly stipends for all active placements.

Usage:
    python manage.py calculate_monthly_stipends --month 12 --year 2025
    python manage.py calculate_monthly_stipends --month 12 --year 2025 --placement-id 123
    python manage.py calculate_monthly_stipends  # Calculates for previous month
    python manage.py calculate_monthly_stipends --dry-run  # Preview without saving
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q
from datetime import date, timedelta
from decimal import Decimal

from learners.models import WorkplacePlacement, StipendCalculation
from learners.services import StipendCalculator


class Command(BaseCommand):
    help = 'Calculate monthly stipends for active workplace placements'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=int,
            help='Month to calculate (1-12). Defaults to previous month.'
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Year to calculate. Defaults to current year (or previous if month wraps).'
        )
        parser.add_argument(
            '--placement-id',
            type=int,
            help='Calculate for a specific placement ID only'
        )
        parser.add_argument(
            '--campus-id',
            type=int,
            help='Calculate for placements at a specific campus only'
        )
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Recalculate even if calculation already exists'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview calculations without saving to database'
        )
        parser.add_argument(
            '--min-rate',
            type=float,
            help='Only calculate for placements with daily rate >= this amount'
        )
        parser.add_argument(
            '--status',
            choices=['ACTIVE', 'COMPLETED', 'SUSPENDED', 'TERMINATED'],
            help='Filter placements by status (default: ACTIVE)'
        )
    
    def handle(self, *args, **options):
        # Determine period
        month = options.get('month')
        year = options.get('year')
        
        if not month or not year:
            # Default to previous month
            today = date.today()
            if month is None:
                month = today.month - 1
                if month == 0:
                    month = 12
                    year = today.year - 1 if year is None else year
            if year is None:
                year = today.year
        
        # Validate month
        if not 1 <= month <= 12:
            raise CommandError(f'Invalid month: {month}. Must be between 1 and 12.')
        
        self.stdout.write(f'\n{self.style.HTTP_INFO}="=" * 60}')
        self.stdout.write(f'{self.style.HTTP_INFO}Calculating Stipends for {date(year, month, 1).strftime("%B %Y")}')
        self.stdout.write(f'{self.style.HTTP_INFO}="=" * 60}\n')
        
        # Build placement queryset
        placements = WorkplacePlacement.objects.select_related(
            'learner', 'host__employer', 'leave_policy', 'qualification'
        ).prefetch_related('attendance_records')
        
        # Apply filters
        if options.get('placement_id'):
            placements = placements.filter(id=options['placement_id'])
            if not placements.exists():
                raise CommandError(f'Placement {options["placement_id"]} not found.')
        else:
            # Filter by status (default to ACTIVE)
            status = options.get('status', 'ACTIVE')
            placements = placements.filter(status=status)
        
        if options.get('campus_id'):
            placements = placements.filter(learner__campus_id=options['campus_id'])
        
        if options.get('min_rate'):
            min_rate = Decimal(str(options['min_rate']))
            placements = placements.filter(stipend_daily_rate__gte=min_rate)
        
        # Filter out placements without stipend rates
        placements = placements.filter(stipend_daily_rate__isnull=False, stipend_daily_rate__gt=0)
        
        # Filter by start date (must have started before the month)
        month_start = date(year, month, 1)
        placements = placements.filter(start_date__lt=month_start)
        
        # Exclude if already calculated (unless recalculate flag is set)
        if not options.get('recalculate'):
            already_calculated = StipendCalculation.objects.filter(
                month=month,
                year=year
            ).values_list('placement_id', flat=True)
            placements = placements.exclude(id__in=already_calculated)
        
        placement_count = placements.count()
        
        if placement_count == 0:
            self.stdout.write(self.style.WARNING('No placements found matching criteria.'))
            return
        
        self.stdout.write(f'Found {placement_count} placement(s) to calculate.\n')
        
        # Perform calculations
        calculations = []
        success_count = 0
        error_count = 0
        total_amount = Decimal('0')
        
        for placement in placements:
            try:
                calculator = StipendCalculator(placement, month, year)
                
                if options.get('dry_run'):
                    # Preview mode - don't save
                    calculation = calculator.calculate(save=False)
                    self.stdout.write(
                        f'{self.style.SUCCESS("✓")} {placement.learner.get_full_name():40} '
                        f'R{calculation.net_amount:>10,.2f} '
                        f'({calculation.days_present} days)'
                    )
                else:
                    # Save to database
                    calculation = calculator.calculate(save=True)
                    calculations.append(calculation)
                    total_amount += calculation.net_amount
                    success_count += 1
                    
                    self.stdout.write(
                        f'{self.style.SUCCESS("✓")} {placement.learner.get_full_name():40} '
                        f'R{calculation.net_amount:>10,.2f} '
                        f'({calculation.days_present} days) '
                        f'[{calculation.status}]'
                    )
                
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    f'{self.style.ERROR("✗")} {placement.learner.get_full_name():40} '
                    f'ERROR: {str(e)}'
                )
        
        # Summary
        self.stdout.write(f'\n{self.style.HTTP_INFO}="=" * 60}')
        self.stdout.write(f'{self.style.HTTP_INFO}Summary')
        self.stdout.write(f'{self.style.HTTP_INFO}="=" * 60}')
        
        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING('DRY RUN - No records saved to database'))
        
        self.stdout.write(f'Total placements: {placement_count}')
        self.stdout.write(f'{self.style.SUCCESS(f"Successful: {success_count}")}')
        
        if error_count > 0:
            self.stdout.write(f'{self.style.ERROR(f"Errors: {error_count}")}')
        
        if not options.get('dry_run') and success_count > 0:
            self.stdout.write(f'\nTotal stipend amount: {self.style.SUCCESS(f"R{total_amount:,.2f}")}')
            
            # Update verification stats for all calculations
            if calculations:
                self.stdout.write('\nUpdating verification statistics...')
                for calc in calculations:
                    calc.update_verification_stats()
                self.stdout.write(self.style.SUCCESS('✓ Verification stats updated'))
        
        self.stdout.write(f'\n{self.style.SUCCESS("Complete!")}\n')
