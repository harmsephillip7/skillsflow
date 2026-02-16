"""
Management command to auto-approve stipends that are fully verified.

Usage:
    python manage.py approve_verified_stipends --month 12 --year 2025
    python manage.py approve_verified_stipends  # Approves for previous month
    python manage.py approve_verified_stipends --dry-run  # Preview without saving
    python manage.py approve_verified_stipends --send-notifications
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import date
from decimal import Decimal

from learners.models import StipendCalculation

User = get_user_model()


class Command(BaseCommand):
    help = 'Auto-approve stipends that have 100% attendance verification'
    
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
            help='Preview approvals without saving to database'
        )
        parser.add_argument(
            '--send-notifications',
            action='store_true',
            help='Send email/SMS notifications to learners after approval'
        )
        parser.add_argument(
            '--auto-user-email',
            type=str,
            default='system@skillsflow.co.za',
            help='Email of user to record as approver (default: system@skillsflow.co.za)'
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
        
        self.stdout.write(f'\n{self.style.HTTP_INFO}="=" * 60}')
        self.stdout.write(f'{self.style.HTTP_INFO}Auto-Approving Verified Stipends for {date(year, month, 1).strftime("%B %Y")}')
        self.stdout.write(f'{self.style.HTTP_INFO}="=" * 60}\n')
        
        # Get system user for auto-approval
        try:
            auto_user = User.objects.get(email=options['auto_user_email'])
        except User.DoesNotExist:
            raise CommandError(
                f'Auto-approval user not found: {options["auto_user_email"]}. '
                f'Create this user or specify a different email with --auto-user-email'
            )
        
        # Get all CALCULATED stipends for the period
        stipends = StipendCalculation.objects.filter(
            month=month,
            year=year,
            status='CALCULATED'
        ).select_related('placement', 'placement__learner')
        
        total_count = stipends.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING('No CALCULATED stipends found for this period.'))
            return
        
        self.stdout.write(f'Found {total_count} calculated stipend(s) to process.\n')
        
        # Update verification stats first
        self.stdout.write('Updating verification statistics...')
        for stipend in stipends:
            stipend.update_verification_stats()
        self.stdout.write(self.style.SUCCESS('✓ Verification stats updated\n'))
        
        # Filter for those that can be finalized (100% verified)
        approved_count = 0
        blocked_count = 0
        total_approved_amount = Decimal('0')
        
        for stipend in stipends:
            learner_name = stipend.placement.learner.get_full_name()
            verification_pct = stipend.verification_percentage
            
            if stipend.can_finalize:
                if options.get('dry_run'):
                    self.stdout.write(
                        f'{self.style.SUCCESS("✓")} {learner_name:40} '
                        f'R{stipend.net_amount:>10,.2f} '
                        f'[{verification_pct}% verified - WOULD APPROVE]'
                    )
                    approved_count += 1
                else:
                    # Approve the stipend
                    stipend.status = 'APPROVED'
                    stipend.approved_by = auto_user
                    stipend.approved_at = timezone.now()
                    stipend.save()
                    
                    total_approved_amount += stipend.net_amount
                    approved_count += 1
                    
                    self.stdout.write(
                        f'{self.style.SUCCESS("✓")} {learner_name:40} '
                        f'R{stipend.net_amount:>10,.2f} '
                        f'[{verification_pct}% verified - APPROVED]'
                    )
                    
                    # Send notification if requested
                    if options.get('send_notifications'):
                        try:
                            from core.services.notifications import notify_stipend_approved
                            notify_stipend_approved(
                                stipend.placement.learner.user,
                                stipend
                            )
                            self.stdout.write(
                                f'  {self.style.SUCCESS("→")} Notification sent to {stipend.placement.learner.user.email}'
                            )
                        except Exception as e:
                            self.stdout.write(
                                f'  {self.style.WARNING("!")} Notification failed: {str(e)}'
                            )
            else:
                blocked_count += 1
                self.stdout.write(
                    f'{self.style.WARNING("✗")} {learner_name:40} '
                    f'R{stipend.net_amount:>10,.2f} '
                    f'[{verification_pct}% verified - BLOCKED]'
                )
        
        # Summary
        self.stdout.write(f'\n{self.style.HTTP_INFO}="=" * 60}')
        self.stdout.write(f'{self.style.HTTP_INFO}Summary')
        self.stdout.write(f'{self.style.HTTP_INFO}="=" * 60}')
        
        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING('DRY RUN - No records saved to database'))
        
        self.stdout.write(f'Total stipends: {total_count}')
        self.stdout.write(f'{self.style.SUCCESS(f"Approved: {approved_count}")}')
        self.stdout.write(f'{self.style.WARNING(f"Blocked (not fully verified): {blocked_count}")}')
        
        if not options.get('dry_run') and approved_count > 0:
            self.stdout.write(f'\nTotal approved amount: {self.style.SUCCESS(f"R{total_approved_amount:,.2f}")}')
            if options.get('send_notifications'):
                self.stdout.write(self.style.SUCCESS('✓ Notifications sent to learners'))
        
        if blocked_count > 0:
            self.stdout.write(
                f'\n{self.style.WARNING("Note:")} {blocked_count} stipend(s) blocked due to incomplete attendance verification.'
            )
            self.stdout.write('Run the facilitator verification portal to verify attendance before re-running this command.')
        
        self.stdout.write(f'\n{self.style.SUCCESS("Complete!")}\n')
