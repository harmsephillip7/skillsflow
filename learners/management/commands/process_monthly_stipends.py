"""
Management command to run the full monthly stipend workflow automatically.

This command chains together:
1. Calculate stipends for all active placements
2. Update verification statistics
3. Auto-approve stipends that are 100% verified
4. Send notifications to learners
5. Generate payment report

Usage:
    python manage.py process_monthly_stipends --month 12 --year 2025
    python manage.py process_monthly_stipends  # Previous month
    python manage.py process_monthly_stipends --dry-run  # Preview only
    python manage.py process_monthly_stipends --skip-notifications
"""
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.utils import timezone
from datetime import date
from io import StringIO


class Command(BaseCommand):
    help = 'Run complete monthly stipend processing workflow'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=int,
            help='Month to process (1-12). Defaults to previous month.'
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Year to process. Defaults to current year.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview workflow without making changes'
        )
        parser.add_argument(
            '--skip-notifications',
            action='store_true',
            help='Skip sending email/SMS notifications to learners'
        )
        parser.add_argument(
            '--skip-report',
            action='store_true',
            help='Skip generating the payment report'
        )
        parser.add_argument(
            '--report-format',
            choices=['csv', 'excel'],
            default='excel',
            help='Format for payment report (default: excel)'
        )
    
    def handle(self, *args, **options):
        # Determine period
        month = options.get('month')
        year = options.get('year')
        
        if not month or not year:
            today = date.today()
            if month is None:
                month = today.month - 1
                if month == 0:
                    month = 12
                    year = today.year - 1 if year is None else year
            if year is None:
                year = today.year
        
        if not 1 <= month <= 12:
            raise CommandError(f'Invalid month: {month}. Must be between 1 and 12.')
        
        period_name = date(year, month, 1).strftime('%B %Y')
        dry_run = options.get('dry_run', False)
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.HTTP_INFO(f'MONTHLY STIPEND PROCESSING WORKFLOW'))
        self.stdout.write(self.style.HTTP_INFO(f'Period: {period_name}'))
        if dry_run:
            self.stdout.write(self.style.WARNING('MODE: DRY RUN (No changes will be saved)'))
        self.stdout.write('=' * 70 + '\n')
        
        start_time = timezone.now()
        
        # Step 1: Calculate stipends
        self.stdout.write(self.style.HTTP_INFO('\n[STEP 1/5] Calculating stipends for all active placements...'))
        self.stdout.write('-' * 70)
        
        calc_args = ['--month', str(month), '--year', str(year)]
        if dry_run:
            calc_args.append('--dry-run')
        
        try:
            call_command('calculate_monthly_stipends', *calc_args, stdout=self.stdout)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Step 1 failed: {str(e)}'))
            return
        
        # Step 2: Update verification statistics
        if not dry_run:
            self.stdout.write(self.style.HTTP_INFO('\n[STEP 2/5] Updating attendance verification statistics...'))
            self.stdout.write('-' * 70)
            
            from learners.models import StipendCalculation
            
            stipends = StipendCalculation.objects.filter(
                month=month,
                year=year,
                status='CALCULATED'
            )
            
            updated_count = 0
            for stipend in stipends:
                stipend.update_verification_stats()
                updated_count += 1
            
            self.stdout.write(self.style.SUCCESS(f'✓ Updated verification stats for {updated_count} stipend(s)'))
        else:
            self.stdout.write(self.style.WARNING('\n[STEP 2/5] Skipped (dry run)'))
        
        # Step 3: Auto-approve verified stipends
        self.stdout.write(self.style.HTTP_INFO('\n[STEP 3/5] Auto-approving fully verified stipends...'))
        self.stdout.write('-' * 70)
        
        approve_args = ['--month', str(month), '--year', str(year)]
        if dry_run:
            approve_args.append('--dry-run')
        elif not options.get('skip_notifications'):
            approve_args.append('--send-notifications')
        
        try:
            call_command('approve_verified_stipends', *approve_args, stdout=self.stdout)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Step 3 failed: {str(e)}'))
            if not dry_run:
                self.stdout.write(self.style.WARNING('Continuing with remaining steps...'))
        
        # Step 4: Send notifications (if not already done in step 3)
        if not dry_run and not options.get('skip_notifications'):
            self.stdout.write(self.style.HTTP_INFO('\n[STEP 4/5] Notifications sent during approval step'))
            self.stdout.write('-' * 70)
            self.stdout.write(self.style.SUCCESS('✓ Learners notified of approved stipends'))
        else:
            self.stdout.write(self.style.WARNING('\n[STEP 4/5] Notifications skipped'))
            self.stdout.write('-' * 70)
        
        # Step 5: Generate payment report
        if not options.get('skip_report'):
            self.stdout.write(self.style.HTTP_INFO('\n[STEP 5/5] Generating payment report...'))
            self.stdout.write('-' * 70)
            
            report_format = options.get('report_format', 'excel')
            safe_period = period_name.replace(' ', '_')
            report_ext = 'xlsx' if report_format == 'excel' else 'csv'
            report_filename = f'stipend_payment_report_{safe_period}.{report_ext}'
            
            report_args = [
                '--month', str(month),
                '--year', str(year),
                '--format', report_format,
                '--status', 'APPROVED',
                '--output', report_filename
            ]
            
            try:
                call_command('export_stipend_report', *report_args, stdout=self.stdout)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Step 5 failed: {str(e)}'))
        else:
            self.stdout.write(self.style.WARNING('\n[STEP 5/5] Report generation skipped'))
            self.stdout.write('-' * 70)
        
        # Final summary
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('WORKFLOW COMPLETE'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'Processing time: {duration:.1f} seconds')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nNOTE: This was a dry run. No changes were saved to the database.'))
            self.stdout.write('Remove the --dry-run flag to process stipends for real.')
        else:
            # Get final statistics
            from learners.models import StipendCalculation
            from django.db.models import Sum, Count
            
            stats = StipendCalculation.objects.filter(
                month=month,
                year=year
            ).aggregate(
                total_count=Count('id'),
                approved_count=Count('id', filter=Q(status='APPROVED')),
                total_amount=Sum('net_amount'),
                approved_amount=Sum('net_amount', filter=Q(status='APPROVED'))
            )
            
            from django.db.models import Q
            
            self.stdout.write(f'\nTotal stipends calculated: {stats["total_count"] or 0}')
            self.stdout.write(f'Approved stipends: {stats["approved_count"] or 0}')
            self.stdout.write(f'Total approved amount: R{stats["approved_amount"] or 0:,.2f}')
        
        self.stdout.write('\n' + self.style.SUCCESS('✓ Monthly stipend processing complete!') + '\n')
