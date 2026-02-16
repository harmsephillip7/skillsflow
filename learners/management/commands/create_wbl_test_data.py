"""
Management command to create test data for the WBL (Workplace-Based Learning) system.
Creates sample placements, attendance, logbooks, stipends, and disciplinary records.
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from corporate.models import (
    CorporateClient, CorporateContact, HostEmployer, HostMentor, 
    WorkplacePlacement, LeavePolicy
)
from learners.models import (
    Learner, WorkplaceAttendance, WorkplaceLogbookEntry,
    WorkplaceModuleCompletion, StipendCalculation, DisciplinaryRecord,
    DisciplinaryAction, LearnerSupportNote
)
from core.models import (
    User, WorkplaceOfficerProfile, MessageThread,
    Message, ThreadParticipant, Notification
)
from tenants.models import Campus
from academics.models import Qualification


User = get_user_model()


class Command(BaseCommand):
    help = 'Creates test data for the WBL system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing WBL test data before creating new data',
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Creating WBL test data...\n')
        
        # Get or create campus
        campus = Campus.objects.first()
        if not campus:
            campus = Campus.objects.create(
                name='Main Campus',
                code='MAIN',
                is_active=True
            )
            self.stdout.write(f'Created campus: {campus.name}')
        
        if options['clear']:
            self.clear_data()
        
        # Create leave policy
        leave_policy = self.create_leave_policy(campus)
        
        # Create host employers
        host_employers = self.create_host_employers(campus)
        
        # Create workplace officers
        officers = self.create_workplace_officers(campus)
        
        # Create learner users and profiles
        learners = self.create_learners(campus)
        
        # Create placements
        placements = self.create_placements(
            learners, host_employers, officers, leave_policy, campus
        )
        
        # Create attendance records
        self.create_attendance_records(placements, campus)
        
        # Create logbook entries
        self.create_logbook_entries(placements, campus)
        
        # Create module completions
        self.create_module_completions(placements, campus)
        
        # Create stipend calculations
        self.create_stipend_calculations(placements, campus)
        
        # Create disciplinary records (for a few learners)
        self.create_disciplinary_records(placements[:3], officers[0], campus)
        
        # Create support notes
        self.create_support_notes(placements, officers, campus)
        
        # Create message threads
        self.create_messages(placements, campus)
        
        self.stdout.write(self.style.SUCCESS('\nWBL test data created successfully!'))
        self.print_summary()
    
    def clear_data(self):
        """Clear existing WBL test data."""
        self.stdout.write('Clearing existing WBL data...')
        
        Message.objects.filter(thread__thread_type='LEARNER_SUPPORT').delete()
        MessageThread.objects.filter(thread_type='LEARNER_SUPPORT').delete()
        LearnerSupportNote.objects.all().delete()
        DisciplinaryAction.objects.all().delete()
        DisciplinaryRecord.objects.all().delete()
        StipendCalculation.objects.all().delete()
        WorkplaceModuleCompletion.objects.all().delete()
        WorkplaceLogbookEntry.objects.all().delete()
        WorkplaceAttendance.objects.all().delete()
        WorkplacePlacement.objects.filter(
            learner__learner_number__startswith='WBL'
        ).delete()
        
        # Delete test learners
        Learner.objects.filter(learner_number__startswith='WBL').delete()
        User.objects.filter(email__startswith='wbl.learner').delete()
        
        # Delete test host employers
        HostMentor.objects.filter(
            employer__company_name__startswith='Test Host'
        ).delete()
        CorporateContact.objects.filter(
            employer__company_name__startswith='Test Host'
        ).delete()
        CorporateClient.objects.filter(
            company_name__startswith='Test Host'
        ).delete()
        
        # Delete test officers
        User.objects.filter(email__startswith='wbl.officer').delete()
        
        self.stdout.write('Cleared existing data.')
    
    def create_leave_policy(self, campus):
        """Create a standard leave policy."""
        policy, created = LeavePolicy.objects.get_or_create(
            name='Standard Learner Leave Policy',
            defaults={
                'annual_leave_days_per_year': 15,
                'sick_leave_days_per_month': 2,
                'family_responsibility_days_per_year': 3,
                'sick_leave_requires_documentation_after_days': 2,
                'is_active': True,
                'is_default': True,
            }
        )
        
        if created:
            self.stdout.write(f'Created leave policy: {policy.name}')
        
        return policy
    
    def create_host_employers(self, campus):
        """Create test host employer companies with mentors."""
        host_data = [
            {
                'company': 'Test Host Engineering Ltd',
                'contact': ('John', 'Smith', 'john.smith@testhosteng.co.za'),
            },
            {
                'company': 'Test Host Tech Solutions',
                'contact': ('Sarah', 'Johnson', 'sarah.johnson@testhosttech.co.za'),
            },
            {
                'company': 'Test Host Manufacturing',
                'contact': ('Mike', 'Williams', 'mike.williams@testhostmfg.co.za'),
            },
        ]
        
        mentors = []
        
        for data in host_data:
            first, last, email = data['contact']
            
            # Create host employer
            host, _ = HostEmployer.objects.get_or_create(
                company_name=data['company'],
                defaults={
                    'registration_number': f'REG{random.randint(100000, 999999)}',
                    'status': 'APPROVED',
                    'contact_person': f'{first} {last}',
                    'contact_email': email,
                    'contact_phone': f'0{random.randint(11, 89)}{random.randint(1000000, 9999999)}',
                    'physical_address': '123 Test Street, Johannesburg',
                    'max_placement_capacity': 10,
                    'safety_requirements_met': True,
                    'campus': campus,
                }
            )
            
            # Create user for mentor
            mentor_user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'is_active': True,
                }
            )
            
            if created:
                mentor_user.set_password('testpass123')
                mentor_user.save()
            
            # Create host mentor
            mentor, _ = HostMentor.objects.get_or_create(
                host=host,
                email=email,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'phone': f'0{random.randint(11, 89)}{random.randint(1000000, 9999999)}',
                    'job_title': 'Training Mentor',
                    'user': mentor_user,
                    'is_active': True,
                    'max_mentees': 5,
                }
            )
            
            mentors.append(mentor)
            self.stdout.write(f'Created host employer: {host.company_name}')
        
        return mentors
    
    def create_workplace_officers(self, campus):
        """Create workplace officer users."""
        officers = []
        
        officer_data = [
            ('Linda', 'Brown', 'wbl.officer1@skillsflow.co.za'),
            ('David', 'Taylor', 'wbl.officer2@skillsflow.co.za'),
        ]
        
        for first, last, email in officer_data:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'is_staff': True,
                    'is_active': True,
                }
            )
            
            if created:
                user.set_password('testpass123')
                user.save()
            
            # Create profile
            profile, _ = WorkplaceOfficerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'employee_number': f'EMP{random.randint(1000, 9999)}',
                    'is_active': True,
                }
            )
            
            officers.append(user)
            self.stdout.write(f'Created workplace officer: {user.get_full_name()}')
        
        return officers
    
    def create_learners(self, campus):
        """Create test learner users and profiles."""
        learners = []
        
        learner_data = [
            ('Thabo', 'Mokoena', 'wbl.learner1@test.co.za'),
            ('Nomsa', 'Dlamini', 'wbl.learner2@test.co.za'),
            ('Sipho', 'Nkosi', 'wbl.learner3@test.co.za'),
            ('Lindiwe', 'Mthembu', 'wbl.learner4@test.co.za'),
            ('Bongani', 'Zulu', 'wbl.learner5@test.co.za'),
            ('Thembi', 'Khumalo', 'wbl.learner6@test.co.za'),
            ('Mandla', 'Ndlovu', 'wbl.learner7@test.co.za'),
            ('Zanele', 'Mbeki', 'wbl.learner8@test.co.za'),
        ]
        
        for i, (first, last, email) in enumerate(learner_data, 1):
            # Create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'is_active': True,
                }
            )
            
            if created:
                user.set_password('testpass123')
                user.save()
            
            # Create learner profile
            learner, _ = Learner.objects.get_or_create(
                user=user,
                defaults={
                    'learner_number': f'WBL{i:04d}',
                    'first_name': first,
                    'last_name': last,
                    'email': email,
                    'sa_id_number': f'{random.randint(8000000000000, 9999999999999)}',
                    'phone_mobile': f'0{random.randint(71, 84)}{random.randint(1000000, 9999999)}',
                    'date_of_birth': date.today() - timedelta(days=random.randint(7300, 9125)),  # 20-25 years old
                    'gender': random.choice(['M', 'F']),
                    'population_group': random.choice(['A', 'C', 'I', 'W']),
                    'citizenship': 'SA',
                    'campus': campus,
                }
            )
            
            learners.append(learner)
        
        self.stdout.write(f'Created {len(learners)} learners')
        return learners
    
    def create_placements(self, learners, mentors, officers, leave_policy, campus):
        """Create workplace placements."""
        placements = []
        
        qualification = Qualification.objects.first()
        
        today = date.today()
        
        for i, learner in enumerate(learners):
            mentor = mentors[i % len(mentors)]
            officer = officers[i % len(officers)]
            
            # Placement started 3-6 months ago
            start_date = today - timedelta(days=random.randint(90, 180))
            end_date = start_date + timedelta(days=365)  # 1 year placement
            
            # Get or create an enrollment for this learner
            from academics.models import Enrollment
            enrollment = Enrollment.objects.filter(learner=learner).first()
            if not enrollment and qualification:
                enrollment = Enrollment.objects.create(
                    learner=learner,
                    qualification=qualification,
                    enrollment_number=f'ENR-{today.year}-{i+1:04d}',
                    status='ACTIVE',
                    application_date=start_date - timedelta(days=30),
                    expected_completion=end_date + timedelta(days=90),
                    campus=campus,
                )
            
            if not enrollment:
                self.stdout.write(f'  Skipping {learner} - no enrollment available')
                continue
            
            # Generate unique placement reference
            placement_ref = f'WBL-{today.year}-{i+1:04d}'
            
            placement, created = WorkplacePlacement.objects.get_or_create(
                learner=learner,
                host=mentor.host,
                defaults={
                    'enrollment': enrollment,
                    'mentor': mentor,
                    'placement_reference': placement_ref,
                    'start_date': start_date,
                    'expected_end_date': end_date,
                    'position': random.choice([
                        'Engineering Intern',
                        'Technical Trainee',
                        'Manufacturing Learner',
                        'IT Support Intern',
                    ]),
                    'department': random.choice([
                        'Engineering',
                        'Operations',
                        'Technical Support',
                        'Production',
                    ]),
                    'status': 'ACTIVE',
                    'workplace_officer': officer,
                    'stipend_daily_rate': Decimal('350.00'),
                    'stipend_payment_day': 25,
                    'leave_policy': leave_policy,
                    'campus': campus,
                }
            )
            
            placements.append(placement)
        
        self.stdout.write(f'Created {len(placements)} placements')
        return placements
    
    def create_attendance_records(self, placements, campus):
        """Create attendance records for the past 3 months."""
        from datetime import time
        today = date.today()
        
        attendance_types = ['PRESENT'] * 18 + ['ANNUAL'] + ['SICK'] + ['UNPAID']
        
        total_records = 0
        
        for placement in placements:
            # Start from 3 months ago or placement start, whichever is later
            start = max(
                placement.start_date,
                today - timedelta(days=90)
            )
            
            current = start
            while current <= today:
                # Skip weekends
                if current.weekday() < 5:
                    # Random attendance type
                    att_type = random.choice(attendance_types)
                    
                    clock_in = None
                    clock_out = None
                    hours = None
                    
                    if att_type == 'PRESENT':
                        # Vary arrival and departure times
                        hour_in = random.randint(7, 9)
                        hour_out = random.randint(16, 18)
                        clock_in = time(hour_in, random.randint(0, 59))
                        clock_out = time(hour_out, random.randint(0, 59))
                        hours = Decimal(str(hour_out - hour_in))
                    
                    WorkplaceAttendance.objects.get_or_create(
                        placement=placement,
                        date=current,
                        defaults={
                            'attendance_type': att_type,
                            'clock_in': clock_in,
                            'clock_out': clock_out,
                            'hours_worked': hours,
                        }
                    )
                    total_records += 1
                
                current += timedelta(days=1)
        
        self.stdout.write(f'Created {total_records} attendance records')
    
    def create_logbook_entries(self, placements, campus):
        """Create logbook entries for past months."""
        today = date.today()
        
        total = 0
        
        for placement in placements:
            # Create entries for last 3 months
            for months_ago in range(3, 0, -1):
                month = today.month - months_ago
                year = today.year
                
                if month <= 0:
                    month += 12
                    year -= 1
                
                # Determine sign-off status
                if months_ago >= 2:
                    mentor_signed = True
                    facilitator_signed = True
                    learner_signed = True
                elif months_ago == 1:
                    mentor_signed = random.choice([True, False])
                    facilitator_signed = False
                    learner_signed = True
                else:
                    mentor_signed = False
                    facilitator_signed = False
                    learner_signed = False
                
                from calendar import monthrange
                _, days_in_month = monthrange(year, month)
                
                logbook, created = WorkplaceLogbookEntry.objects.get_or_create(
                    placement=placement,
                    month=month,
                    year=year,
                    defaults={
                        'tasks_completed': [
                            'Assisted with daily operations',
                            'Completed assigned technical tasks',
                            'Attended training sessions',
                        ],
                        'skills_developed': 'Technical proficiency, time management, teamwork.',
                        'challenges_faced': 'Initial challenges adapting to new equipment, resolved through mentorship.',
                        'learning_outcomes': f'Completed training on various technical skills.',
                        'total_hours_worked': Decimal('160.00'),
                        'total_days_present': random.randint(18, 22),
                        'learner_signed': learner_signed,
                        'learner_signed_at': timezone.now() if learner_signed else None,
                        'mentor_signed': mentor_signed,
                        'mentor_signed_at': timezone.now() if mentor_signed else None,
                        'mentor_rating': random.randint(3, 5) if mentor_signed else None,
                        'facilitator_signed': facilitator_signed,
                        'facilitator_signed_at': timezone.now() if facilitator_signed else None,
                    }
                )
                
                if created:
                    total += 1
        
        self.stdout.write(f'Created {total} logbook entries')
    
    def create_module_completions(self, placements, campus):
        """Create workplace module completion records."""
        modules = [
            ('WM001', 'Workplace Safety'),
            ('WM002', 'Communication Skills'),
            ('WM003', 'Basic Technical Skills'),
            ('WM004', 'Quality Control'),
            ('WM005', 'Problem Solving'),
        ]
        
        total = 0
        today = date.today()
        
        for placement in placements:
            # Complete 2-4 modules per learner
            num_modules = random.randint(2, 4)
            selected = random.sample(modules, num_modules)
            
            for code, name in selected:
                started_date = today - timedelta(days=random.randint(60, 120))
                completed_date = today - timedelta(days=random.randint(7, 50))
                
                WorkplaceModuleCompletion.objects.get_or_create(
                    placement=placement,
                    module_code=code,
                    defaults={
                        'module_name': name,
                        'started_date': started_date,
                        'completed_date': completed_date,
                        'mentor_signed': True,
                        'mentor_signed_at': timezone.now(),
                        'facilitator_signed': True,
                        'facilitator_signed_at': timezone.now(),
                    }
                )
                total += 1
        
        self.stdout.write(f'Created {total} module completions')
    
    def create_stipend_calculations(self, placements, campus):
        """Create stipend calculation records."""
        today = date.today()
        total = 0
        
        for placement in placements:
            # Calculate for past 2 months
            for months_ago in range(2, 0, -1):
                month = today.month - months_ago
                year = today.year
                
                if month <= 0:
                    month += 12
                    year -= 1
                
                # Get attendance counts
                from calendar import monthrange
                _, days_in_month = monthrange(year, month)
                
                attendance = WorkplaceAttendance.objects.filter(
                    placement=placement,
                    date__year=year,
                    date__month=month
                )
                
                days_present = attendance.filter(attendance_type='PRESENT').count()
                days_annual = attendance.filter(attendance_type='ANNUAL').count()
                days_sick = attendance.filter(attendance_type='SICK').count()
                days_absent = attendance.filter(attendance_type='ABSENT').count()
                days_unpaid = attendance.filter(attendance_type='UNPAID').count()
                
                # Calculate working days in month
                working_days = 0
                for day in range(1, days_in_month + 1):
                    if date(year, month, day).weekday() < 5:
                        working_days += 1
                
                daily_rate = placement.stipend_daily_rate or Decimal('350.00')
                paid_days = days_present + min(days_annual, 1) + min(days_sick, 2)
                gross = daily_rate * paid_days
                
                status = 'APPROVED' if months_ago == 2 else 'CALCULATED'
                
                StipendCalculation.objects.get_or_create(
                    placement=placement,
                    month=month,
                    year=year,
                    defaults={
                        'total_working_days': working_days,
                        'days_present': days_present,
                        'days_annual_leave': days_annual,
                        'days_sick_leave': days_sick,
                        'days_unpaid_leave': days_unpaid,
                        'days_absent': days_absent,
                        'daily_rate': daily_rate,
                        'gross_amount': gross,
                        'total_deductions': Decimal('0'),
                        'net_amount': gross,
                        'status': status,
                        'calculated_at': timezone.now(),
                    }
                )
                total += 1
        
        self.stdout.write(f'Created {total} stipend calculations')
    
    def create_disciplinary_records(self, placements, officer, campus):
        """Create disciplinary records for some learners."""
        import uuid
        steps = ['VERBAL_WARNING', 'WRITTEN_WARNING', 'FINAL_WARNING']
        offence_types = ['Late Arrival', 'Absent Without Leave', 'Workplace Misconduct']
        
        created_count = 0
        for i, placement in enumerate(placements):
            opened_date = date.today() - timedelta(days=random.randint(14, 30))
            offence_date = opened_date - timedelta(days=random.randint(1, 7))
            
            # Check if record already exists for this learner/placement
            existing = DisciplinaryRecord.objects.filter(
                learner=placement.learner,
                placement=placement
            ).first()
            
            if existing:
                continue
            
            # Generate unique case number to avoid collision
            unique_case = f"DISC-TEST-{uuid.uuid4().hex[:8].upper()}"
            
            record = DisciplinaryRecord.objects.create(
                learner=placement.learner,
                placement=placement,
                case_number=unique_case,
                current_step=steps[i % len(steps)],
                opened_date=opened_date,
                status='OPEN' if i == 0 else 'RESOLVED',
                assigned_officer=officer,  # officer is already a User
                notes='Disciplinary case opened due to workplace incident.',
            )
            created_count += 1
            
            # Add action for resolved cases
            if record.status == 'RESOLVED':
                DisciplinaryAction.objects.create(
                    record=record,
                    step=record.current_step,
                    action_date=opened_date + timedelta(days=3),
                    issued_by=officer,  # officer is already a User
                    offence_type=offence_types[i % len(offence_types)],
                    offence_date=offence_date,
                    offence_description='Repeated violations of workplace policy.',
                    learner_response='Learner acknowledged the warning.',
                    learner_acknowledged=True,
                    learner_acknowledged_at=timezone.now(),
                    notes='Warning issued and acknowledged by learner.',
                )
                
                record.resolved_date = date.today() - timedelta(days=7)
                record.resolution_summary = 'Warning issued, learner acknowledged.'
                record.save()
        
        self.stdout.write(f'Created {created_count} disciplinary records')
    
    def create_support_notes(self, placements, officers, campus):
        """Create support notes."""
        categories = ['CAREER', 'PERSONAL', 'WORKPLACE', 'ACADEMIC']
        
        total = 0
        
        for placement in placements[:5]:
            officer = random.choice(officers)
            
            LearnerSupportNote.objects.create(
                learner=placement.learner,
                placement=placement,
                category=random.choice(categories),
                date=date.today() - timedelta(days=random.randint(1, 30)),
                summary=f'Support session with {placement.learner.get_full_name()}',
                details='Met with learner to discuss progress and any challenges. Learner is adapting well to the workplace environment.',
                advice_given='Continue with current approach, stay focused on learning objectives.',
                recorded_by=officer,
            )
            total += 1
        
        self.stdout.write(f'Created {total} support notes')
    
    def create_messages(self, placements, campus):
        """Create message threads between learners and mentors."""
        total_threads = 0
        
        for placement in placements[:4]:
            # Check if mentor has a user account
            if not placement.mentor or not placement.mentor.user:
                continue
            
            if not placement.learner.user:
                continue
            
            thread = MessageThread.objects.create(
                subject=f'Check-in with {placement.learner.get_full_name()}',
                thread_type='LEARNER_SUPPORT',
                related_placement=placement,
            )
            
            # Add participants
            ThreadParticipant.objects.create(
                thread=thread,
                user=placement.learner.user,
                role_label='LEARNER'
            )
            
            ThreadParticipant.objects.create(
                thread=thread,
                user=placement.mentor.user,
                role_label='MENTOR'
            )
            
            # Add some messages
            Message.objects.create(
                thread=thread,
                sender=placement.mentor.user,
                content=f"Hi {placement.learner.first_name}, how are you settling in? Let me know if you have any questions.",
            )
            
            msg2 = Message.objects.create(
                thread=thread,
                sender=placement.learner.user,
                content="Thank you! Everything is going well. I'm enjoying the learning opportunities.",
            )
            # Mark as read
            msg2.mark_read_by(placement.mentor.user)
            
            total_threads += 1
        
        self.stdout.write(f'Created {total_threads} message threads')
    
    def print_summary(self):
        """Print a summary of created data."""
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write('WBL TEST DATA SUMMARY')
        self.stdout.write('=' * 50)
        
        self.stdout.write(f'Host Employers: {HostEmployer.objects.count()}')
        self.stdout.write(f'Mentors: {HostMentor.objects.count()}')
        self.stdout.write(f'Workplace Officers: {WorkplaceOfficerProfile.objects.count()}')
        self.stdout.write(f'Learners: {Learner.objects.filter(learner_number__startswith="WBL").count()}')
        self.stdout.write(f'Placements: {WorkplacePlacement.objects.filter(learner__learner_number__startswith="WBL").count()}')
        self.stdout.write(f'Attendance Records: {WorkplaceAttendance.objects.count()}')
        self.stdout.write(f'Logbook Entries: {WorkplaceLogbookEntry.objects.count()}')
        self.stdout.write(f'Module Completions: {WorkplaceModuleCompletion.objects.count()}')
        self.stdout.write(f'Stipend Calculations: {StipendCalculation.objects.count()}')
        self.stdout.write(f'Disciplinary Records: {DisciplinaryRecord.objects.count()}')
        self.stdout.write(f'Support Notes: {LearnerSupportNote.objects.count()}')
        self.stdout.write(f'Message Threads: {MessageThread.objects.filter(thread_type="LEARNER_SUPPORT").count()}')
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write('TEST LOGIN CREDENTIALS')
        self.stdout.write('=' * 50)
        self.stdout.write('Mentor: john.smith@testhosteng.co.za / testpass123')
        self.stdout.write('Officer: wbl.officer1@skillsflow.co.za / testpass123')
        self.stdout.write('Learner: wbl.learner1@test.co.za / testpass123')
        self.stdout.write('=' * 50)
