"""
Script to create test attendance data for NOT projects.
This will:
1. Create learners
2. Create workplace placements linked to a NOT project
3. Create attendance records for the current and previous months
4. Create stipend calculations
"""
import os
import sys
import django
import random
from datetime import date, timedelta
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.utils import timezone
from core.models import TrainingNotification, User
from learners.models import Learner, WorkplaceAttendance, StipendCalculation, Employer
from corporate.models import WorkplacePlacement, HostEmployer, HostMentor
from academics.models import Qualification, Enrollment
from logistics.models import Cohort

def create_test_data():
    print("=" * 60)
    print("Creating Attendance Test Data")
    print("=" * 60)
    
    # Find an active project or use the first one
    project = TrainingNotification.objects.filter(
        is_deleted=False,
        status__in=['APPROVED', 'ACTIVE', 'IN_PROGRESS', 'NOTIFICATIONS_SENT']
    ).first()
    
    if not project:
        # Use any project
        project = TrainingNotification.objects.filter(is_deleted=False).first()
        if project:
            project.status = 'ACTIVE'
            project.save()
            print(f"Set project {project.reference_number} to ACTIVE status")
    
    if not project:
        print("ERROR: No projects found! Please create a project first.")
        return
    
    print(f"\nUsing project: {project.reference_number} - {project.title}")
    print(f"Project ID: {project.pk}")
    
    # Get an existing host employer (use first one)
    host = HostEmployer.objects.first()
    if not host:
        print("ERROR: No host employers found! Please create one first.")
        return
    print(f"Using host employer: {host.company_name}")
    
    # Get a campus (use the project's campus or the first available)
    from tenants.models import Campus
    campus = project.campus if hasattr(project, 'campus') and project.campus else Campus.objects.first()
    if not campus:
        print("ERROR: No campuses found!")
        return
    print(f"Using campus: {campus.name}")
    
    # Get or create a mentor user
    mentor_user, created = User.objects.get_or_create(
        email='mentor@testcompany.com',
        defaults={
            'first_name': 'Mike',
            'last_name': 'Mentor',
            'is_active': True,
        }
    )
    if created:
        mentor_user.set_password('test123')
        mentor_user.save()
        print(f"Created mentor user: {mentor_user.email}")
    
    # Get or create mentor for this host
    mentor, created = HostMentor.objects.get_or_create(
        user=mentor_user,
        host=host,
        defaults={
            'is_active': True,
            'first_name': 'Mike',
            'last_name': 'Mentor',
            'email': 'mentor@testcompany.com',
            'phone': '0111234567',
        }
    )
    if created:
        print(f"Created mentor: {mentor}")
    
    # Get an existing qualification and cohort
    qual = Qualification.objects.first()
    if not qual:
        print("ERROR: No qualifications found!")
        return
    print(f"Using qualification: {qual.title}")
    
    # Get or use an existing cohort
    cohort = Cohort.objects.filter(qualification=qual).first()
    if not cohort:
        cohort = Cohort.objects.first()
    if not cohort:
        print("ERROR: No cohorts found!")
        return
    print(f"Using cohort: {cohort.name}")
    
    # Use existing learners that have enrollments
    learners_with_enrollments = Learner.objects.filter(
        enrollments__isnull=False
    ).distinct()[:8]
    
    if not learners_with_enrollments:
        print("ERROR: No learners with enrollments found!")
        return
    
    print(f"Found {learners_with_enrollments.count()} learners with enrollments")
    
    placements_created = 0
    attendance_created = 0
    
    for idx, learner in enumerate(learners_with_enrollments):
        # Get an enrollment for this learner
        enrollment = learner.enrollments.first()
        
        if not enrollment:
            print(f"  Skipping {learner.first_name} {learner.last_name} - no enrollment")
            continue
        
        # Create workplace placement
        placement, created = WorkplacePlacement.objects.get_or_create(
            learner=learner,
            enrollment=enrollment,
            training_notification=project,
            defaults={
                'campus': campus,  # Required!
                'host': host,
                'mentor': mentor,
                'placement_reference': f'WPL-TEST-{2026}{idx+1:04d}',
                'start_date': date(2025, 7, 1),
                'expected_end_date': date(2026, 6, 30),
                'status': 'ACTIVE',
                'stipend_daily_rate': Decimal('350.00'),
            }
        )
        
        if created:
            placements_created += 1
            print(f"  Created placement for: {learner.first_name} {learner.last_name}")
        
        # Create attendance records for December 2025 and January 2026
        today = date.today()
        
        for month_offset in [1, 0]:  # Previous month and current month
            if month_offset == 1:
                # December 2025
                year, month = 2025, 12
                start_date = date(2025, 12, 1)
                end_date = date(2025, 12, 31)
            else:
                # January 2026
                year, month = 2026, 1
                start_date = date(2026, 1, 1)
                end_date = min(today, date(2026, 1, 31))
            
            current_date = start_date
            days_present = 0
            days_absent = 0
            days_leave = 0
            
            while current_date <= end_date:
                # Skip weekends
                if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                    # Randomly assign attendance type
                    rand = random.random()
                    if rand < 0.75:  # 75% present
                        attendance_type = 'PRESENT'
                        days_present += 1
                    elif rand < 0.85:  # 10% annual leave
                        attendance_type = 'ANNUAL_LEAVE'
                        days_leave += 1
                    elif rand < 0.92:  # 7% sick leave
                        attendance_type = 'SICK_LEAVE'
                        days_leave += 1
                    else:  # 8% absent
                        attendance_type = 'ABSENT'
                        days_absent += 1
                    
                    # Randomly verify some attendance (80% verified by mentor)
                    mentor_verified = random.random() < 0.80
                    facilitator_verified = random.random() < 0.60
                    
                    # Create attendance record
                    att, created = WorkplaceAttendance.objects.get_or_create(
                        placement=placement,
                        date=current_date,
                        defaults={
                            'attendance_type': attendance_type,
                            'clock_in': timezone.now().replace(hour=8, minute=random.randint(0, 30)),
                            'clock_out': timezone.now().replace(hour=17, minute=random.randint(0, 30)) if attendance_type == 'PRESENT' else None,
                            'hours_worked': Decimal('8.0') if attendance_type == 'PRESENT' else Decimal('0'),
                            'mentor_verified': mentor_verified,
                            'mentor_verified_at': timezone.now() if mentor_verified else None,
                            'mentor_verified_by': mentor_user if mentor_verified else None,  # Use User, not HostMentor
                            'facilitator_verified': facilitator_verified,
                            'notes': '' if attendance_type == 'PRESENT' else f'{attendance_type} on {current_date}',
                        }
                    )
                    if created:
                        attendance_created += 1
                
                current_date += timedelta(days=1)
            
            # Create stipend calculation for the month
            working_days = 22 if month == 12 else 23  # Approximate working days
            stipend, created = StipendCalculation.objects.get_or_create(
                placement=placement,
                year=year,
                month=month,
                defaults={
                    'total_working_days': working_days,
                    'days_present': days_present,
                    'days_annual_leave': days_leave // 2,
                    'days_sick_leave': days_leave - (days_leave // 2),
                    'days_family_leave': 0,
                    'days_unpaid_leave': 0,
                    'days_public_holiday': 1 if month == 12 else 0,
                    'days_absent': days_absent,
                    'days_suspended': 0,
                    'daily_rate': Decimal('350.00'),
                    'gross_amount': Decimal('350.00') * days_present,
                    'total_deductions': Decimal('0.00'),
                    'net_amount': Decimal('350.00') * days_present,
                    'status': 'CALCULATED',
                }
            )
    
    print(f"\n{'=' * 60}")
    print(f"Test Data Created Successfully!")
    print(f"{'=' * 60}")
    print(f"Project: {project.reference_number} (ID: {project.pk})")
    print(f"Placements created: {placements_created}")
    print(f"Attendance records created: {attendance_created}")
    print(f"\nTo view the attendance register:")
    print(f"1. Go to http://127.0.0.1:8001/not/")
    print(f"2. Click on project: {project.reference_number}")
    print(f"3. Click the 'Attendance Register' tab")
    print(f"4. Select a month (December 2025 or January 2026)")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    create_test_data()
