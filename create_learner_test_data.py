"""
Create test data for learner portal testing.
Run: ./venv/bin/python create_learner_test_data.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from datetime import date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from core.models import User
from learners.models import (
    Learner, WorkplaceAttendance, 
    DailyLogbookEntry, DailyTaskCompletion
)
from corporate.models import HostEmployer, WorkplacePlacement
from academics.models import Qualification, Enrollment, Module, WorkplaceModuleOutcome
from tenants.models import Brand, Campus

print("=" * 60)
print("Creating Test Learner Data")
print("=" * 60)

# Get a campus for tenant awareness (use first Johannesburg campus)
campus = Campus.objects.filter(name__icontains='Johannesburg').first()
if not campus:
    campus = Campus.objects.first()
if not campus:
    print("ERROR: No campus found. Please create at least one Campus first.")
    sys.exit(1)
print(f"✓ Campus: {campus.name} ({campus.brand.name})")

# Create or get test user
test_email = "testlearner@skillsflow.test"
test_user, created = User.objects.get_or_create(
    email=test_email,
    defaults={
        'first_name': 'Test',
        'last_name': 'Learner',
        'is_active': True,
    }
)
if created:
    test_user.set_password('test1234')
    test_user.save()
    print(f"✓ Created user: {test_email} (password: test1234)")
else:
    print(f"✓ User exists: {test_email}")

# Get or create a host employer
host, _ = HostEmployer.objects.get_or_create(
    company_name="Test Workplace Company",
    defaults={
        'trading_name': 'Test Corp',
        'registration_number': 'TEST123456',
        'contact_person': 'John Contact',
        'contact_email': 'contact@testcompany.com',
        'contact_phone': '0821234567',
        'physical_address': '123 Test Street, Test City',
        'status': 'APPROVED',
        'campus': campus,
        'gps_latitude': Decimal('-26.2041'),
        'gps_longitude': Decimal('28.0473'),
        'geofence_radius_meters': 5000,
    }
)
print(f"✓ Host Employer: {host.company_name}")

# Get or create a programme/qualification
qualification = Qualification.objects.first()
print(f"✓ Qualification: {qualification.title if qualification else 'None found'}")

# Create W (Workplace) modules and outcomes for the qualification
if qualification:
    print("\nCreating Workplace Modules and Outcomes...")
    
    # Define workplace modules
    wm_modules_data = [
        {
            'code': 'WM1',
            'title': 'Workplace Communication',
            'credits': 10,
            'notional_hours': 100,
            'outcomes': [
                ('WM1.1', 'Communicate effectively in a workplace environment'),
                ('WM1.2', 'Write professional emails and reports'),
                ('WM1.3', 'Participate in team meetings and discussions'),
                ('WM1.4', 'Present information to colleagues and supervisors'),
            ]
        },
        {
            'code': 'WM2', 
            'title': 'Professional Practice',
            'credits': 15,
            'notional_hours': 150,
            'outcomes': [
                ('WM2.1', 'Apply workplace health and safety procedures'),
                ('WM2.2', 'Demonstrate professional ethics and conduct'),
                ('WM2.3', 'Manage time effectively and meet deadlines'),
                ('WM2.4', 'Work independently and as part of a team'),
                ('WM2.5', 'Solve problems in a workplace context'),
            ]
        },
        {
            'code': 'WM3',
            'title': 'Technical Skills Application',
            'credits': 20,
            'notional_hours': 200,
            'outcomes': [
                ('WM3.1', 'Apply technical knowledge to workplace tasks'),
                ('WM3.2', 'Use relevant software and tools'),
                ('WM3.3', 'Follow standard operating procedures'),
                ('WM3.4', 'Document work processes and outcomes'),
                ('WM3.5', 'Maintain quality standards in work output'),
                ('WM3.6', 'Troubleshoot common technical issues'),
            ]
        },
    ]
    
    for seq, wm_data in enumerate(wm_modules_data, 1):
        module, created = Module.objects.get_or_create(
            qualification=qualification,
            code=wm_data['code'],
            defaults={
                'title': wm_data['title'],
                'module_type': 'W',
                'credits': wm_data['credits'],
                'notional_hours': wm_data['notional_hours'],
                'sequence_order': seq,
                'is_active': True,
            }
        )
        if created:
            print(f"  ✓ Created module: {module.code} - {module.title}")
        else:
            print(f"  ✓ Module exists: {module.code}")
        
        # Create outcomes for this module
        for outcome_num, (outcome_code, outcome_title) in enumerate(wm_data['outcomes'], 1):
            outcome, oc = WorkplaceModuleOutcome.objects.get_or_create(
                module=module,
                outcome_code=outcome_code,
                defaults={
                    'outcome_number': outcome_num,
                    'title': outcome_title,
                    'estimated_hours': 10,
                    'is_active': True,
                }
            )
            if oc:
                print(f"    ✓ Created outcome: {outcome_code}")
    
    print(f"✓ Workplace modules and outcomes created")

# Create or get learner profile
# First generate a learner number
import random
learner_number = f"TL{random.randint(100000, 999999)}"

learner, created = Learner.objects.get_or_create(
    user=test_user,
    defaults={
        'learner_number': learner_number,
        'sa_id_number': '9501015800085',
        'first_name': 'Test',
        'last_name': 'Learner',
        'date_of_birth': date(1995, 1, 1),
        'gender': 'M',
        'population_group': 'B',
        'citizenship': 'SA',
        'home_language': 'English',
        'email': test_email,
        'phone_mobile': '0821234567',
        'province_code': 'GP',
        'campus': campus,
    }
)
if created:
    print(f"✓ Created learner profile for {test_user.get_full_name()}")
else:
    print(f"✓ Learner profile exists for {test_user.get_full_name()}")

# Set date variables
today = date.today()
placement_start = today - timedelta(days=60)  # Started 2 months ago
placement_end = today + timedelta(days=120)   # Ends in 4 months

# Get or create enrollment
enrollment = None
if qualification:
    enrollment_number = f"EN{random.randint(100000, 999999)}"
    enrollment, _ = Enrollment.objects.get_or_create(
        learner=learner,
        qualification=qualification,
        defaults={
            'enrollment_number': enrollment_number,
            'application_date': today - timedelta(days=90),
            'enrollment_date': today - timedelta(days=80),
            'start_date': placement_start,
            'expected_completion': placement_end + timedelta(days=30),
            'status': 'ACTIVE',
            'campus': campus,
        }
    )
    print(f"✓ Enrollment: {enrollment}")

# Create workplace placement
placement = None
if enrollment:
    placement_ref = f"WPL-TEST{random.randint(1000, 9999)}"
    placement, created = WorkplacePlacement.objects.get_or_create(
        learner=learner,
        enrollment=enrollment,
        host=host,
        defaults={
            'placement_reference': placement_ref,
            'start_date': placement_start,
            'expected_end_date': placement_end,
            'status': 'ACTIVE',
            'campus': campus,
        }
    )
    if created:
        print(f"✓ Created placement at {host.company_name}")
    else:
        # Ensure placement is active
        placement.status = 'ACTIVE'
        placement.save()
        print(f"✓ Placement exists at {host.company_name}")
else:
    print("⚠ No enrollment found, trying to find existing placement...")
    placement = WorkplacePlacement.objects.filter(learner=learner, status='ACTIVE').first()
    if not placement:
        print("ERROR: Cannot create placement without enrollment")

# Create attendance records for the past 30 days
if placement:
    print("\nCreating attendance records...")
    attendance_count = 0
    for i in range(30):
        record_date = today - timedelta(days=i)
        
        # Skip weekends
        if record_date.weekday() >= 5:
            continue
        
        # Determine attendance type
        if i % 10 == 0:
            att_type = 'SICK'
            clock_in = None
            clock_out = None
            hours = None
        elif i % 7 == 0:
            att_type = 'ANNUAL'
            clock_in = None
            clock_out = None
            hours = None
        elif i % 5 == 0:
            att_type = 'PRESENT'  # Late arrival
            clock_in = time(9, 15)
            clock_out = time(17, 0)
            hours = Decimal('7.75')
        else:
            att_type = 'PRESENT'
            clock_in = time(8, 0)
            clock_out = time(17, 0)
            hours = Decimal('9.0')
        
        att, created = WorkplaceAttendance.objects.get_or_create(
            placement=placement,
            date=record_date,
            defaults={
                'attendance_type': att_type,
                'clock_in': clock_in,
                'clock_out': clock_out,
                'hours_worked': hours,
                'notes': f'Test attendance for {record_date}',
                'mentor_verified': i % 3 == 0,
            }
        )
        if created:
            attendance_count += 1

    print(f"✓ Created {attendance_count} attendance records")

    # Create daily logbook entries with tasks
    print("\nCreating daily logbook entries with tasks...")
    entry_count = 0
    task_count = 0

    task_descriptions = [
        ("Code review", "Reviewed pull requests from team members"),
        ("Bug fixing", "Fixed login page validation issues"),
        ("Feature development", "Implemented user profile page"),
        ("Documentation", "Updated API documentation"),
        ("Testing", "Wrote unit tests for authentication module"),
        ("Meeting", "Daily standup and sprint planning"),
        ("Training", "Completed online Python course module"),
        ("Database work", "Optimized database queries"),
        ("UI/UX", "Improved mobile responsiveness"),
        ("Deployment", "Assisted with staging deployment"),
    ]

    for i in range(20):
        entry_date = today - timedelta(days=i)
        
        # Skip weekends
        if entry_date.weekday() >= 5:
            continue
        
        # Create daily entry
        entry, created = DailyLogbookEntry.objects.get_or_create(
            placement=placement,
            entry_date=entry_date,
            defaults={
                'attendance_status': 'PRESENT',
                'clock_in': time(8, 0),
                'clock_out': time(17, 0),
                'daily_summary': f'Productive day working on various tasks.',
                'learner_signed': True,
                'learner_signed_at': timezone.now(),
            }
        )
        if created:
            entry_count += 1
            
            # Add 2-4 tasks per entry
            num_tasks = (i % 3) + 2
            for j in range(num_tasks):
                task_idx = (i + j) % len(task_descriptions)
                task_name, task_desc = task_descriptions[task_idx]
                
                DailyTaskCompletion.objects.create(
                    daily_entry=entry,
                    module_code=f'WM{task_idx + 1}',
                    task_description=f'{task_name}: {task_desc}',
                    hours_spent=Decimal(str(1.5 + (j * 0.5))),
                )
                task_count += 1

    print(f"✓ Created {entry_count} daily logbook entries")
    print(f"✓ Created {task_count} task completions")
else:
    print("\n⚠ Skipping attendance and logbook records (no placement)")

print("\n" + "=" * 60)
print("TEST LEARNER CREDENTIALS")
print("=" * 60)
print(f"Email: {test_email}")
print(f"Password: test1234")
print(f"Learner ID: {learner.id}")
if placement:
    print(f"Placement: {placement.host.company_name}")
print("=" * 60)
print("\nYou can now log in to the learner portal with these credentials.")
print("Portal URL: /portal/student/")
print("=" * 60)
