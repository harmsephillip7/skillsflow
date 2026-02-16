"""
Management command to create StaffProfile records for all staff users.
Links User accounts to HR StaffProfile for employee management.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import User
from hr.models import StaffProfile


class Command(BaseCommand):
    help = 'Create StaffProfile records for all staff users that don\'t have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get all users that don't have a staff profile
        users_without_profile = User.objects.filter(
            staff_profile__isnull=True
        ).exclude(
            email__in=['admin@skillsflow.co.za', 'superuser@skillsflow.co.za']
        )
        
        created_count = 0
        skipped_count = 0
        
        for user in users_without_profile:
            # Generate employee number based on email prefix or sequential
            email_prefix = user.email.split('@')[0].replace('.', '').replace('-', '').replace('_', '')[:10].upper()
            
            # Check if employee number already exists
            base_emp_num = f"EMP-{email_prefix}"
            emp_num = base_emp_num
            counter = 1
            while StaffProfile.objects.filter(employee_number=emp_num).exists():
                emp_num = f"{base_emp_num}-{counter}"
                counter += 1
            
            if dry_run:
                self.stdout.write(f"  Would create profile for: {user.get_full_name()} <{user.email}> - {emp_num}")
            else:
                StaffProfile.objects.create(
                    user=user,
                    employee_number=emp_num,
                    employment_type='FULL_TIME',
                    employment_status='ACTIVE',
                    date_joined=timezone.now().date(),
                )
                self.stdout.write(self.style.SUCCESS(
                    f"  Created: {user.get_full_name()} <{user.email}> - {emp_num}"
                ))
            
            created_count += 1
        
        # Count existing profiles
        existing_count = StaffProfile.objects.count() - created_count if not dry_run else StaffProfile.objects.count()
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDRY RUN - Would create {created_count} staff profiles"))
            self.stdout.write(f"Existing profiles: {existing_count}")
        else:
            self.stdout.write(self.style.SUCCESS(f"\nCreated: {created_count} staff profiles"))
            self.stdout.write(f"Total profiles now: {StaffProfile.objects.count()}")
