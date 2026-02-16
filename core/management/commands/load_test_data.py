"""
Management command to load comprehensive test data for:
- Facilitator Portal
- Learner Portal  
- Tranche Payment System

Run with: python manage.py load_test_data
"""
import random
from datetime import date, timedelta, datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.db.models.signals import post_save, pre_save

from core.models import (
    User, Role, UserRole, 
    TrainingNotification, TrancheSchedule, TrancheEvidenceRequirement,
    TrancheEvidence, TrancheSubmission, TrancheComment
)
from tenants.models import Brand, Campus
from learners.models import Learner, Address, SETA, Employer, LearnerEmployment
from academics.models import (
    Qualification, Module, UnitStandard, Enrollment, EnrollmentStatusHistory
)
from logistics.models import Cohort, Venue, ScheduleSession, Attendance
from assessments.models import AssessmentActivity, AssessmentResult
from portals.models import Announcement, Notification


class Command(BaseCommand):
    help = 'Load comprehensive test data for portals and tranches'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing test data before loading new data',
        )

    def handle(self, *args, **options):
        self.stdout.write('Loading test data...\n')
        
        # Disconnect task signals temporarily to avoid auto-task creation issues
        from core import task_signals
        
        # Store receivers to reconnect later
        enrollment_receivers = post_save.receivers.copy()
        session_receivers = post_save.receivers.copy()
        
        # Disconnect all post_save signals for affected models
        post_save.receivers = [
            r for r in post_save.receivers 
            if not (hasattr(r[1], '__self__') and 
                   r[1].__self__.__module__ == 'core.task_signals')
        ]
        
        # Alternative: just clear receivers for specific senders
        try:
            post_save.disconnect(dispatch_uid='enrollment_task_signal')
        except:
            pass
        try:
            post_save.disconnect(dispatch_uid='session_task_signal')
        except:
            pass
        
        with transaction.atomic():
            # Create base data
            brand = self.create_brand()
            campus = self.create_campus(brand)
            seta = self.create_seta()
            
            # Create users
            facilitator_user = self.create_facilitator_user(campus)
            learner_users = self.create_learner_users(campus)
            
            # Create qualification and modules
            qualification = self.create_qualification(seta)
            modules = self.create_modules(qualification)
            
            # Create assessment activities
            activities = self.create_assessment_activities(modules)
            
            # Create cohort
            cohort = self.create_cohort(qualification, facilitator_user, campus)
            
            # Create venue
            venue = self.create_venue(campus)
            
            # Create learners and enrollments
            learners = self.create_learners(learner_users, campus)
            enrollments = self.create_enrollments(learners, qualification, cohort)
            
            # Create employer and placements
            employer = self.create_employer(seta)
            self.create_employments(learners, employer)
            
            # Create schedule sessions for facilitator
            sessions = self.create_schedule_sessions(cohort, modules, venue, facilitator_user)
            
            # Create attendance records
            self.create_attendance_records(sessions, enrollments, facilitator_user)
            
            # Create assessment results
            self.create_assessment_results(enrollments, activities, facilitator_user)
            
            # Create Training Notification (NOT) and Tranches
            not_record = self.create_training_notification(qualification, campus)
            tranches = self.create_tranches(not_record)
            
            # Create tranche evidence requirements
            self.create_evidence_requirements(tranches)
            
            # Create tranche submissions and comments
            self.create_tranche_submissions(tranches, facilitator_user)
            self.create_tranche_comments(tranches, facilitator_user)
            
            # Create announcements
            self.create_announcements(brand, campus)
            
            # Create notifications for users
            self.create_notifications(facilitator_user, learner_users)
        
        self.stdout.write(self.style.SUCCESS('\n✅ Test data loaded successfully!'))
        self.stdout.write('\nTest Accounts Created:')
        self.stdout.write(f'  Facilitator: facilitator@test.com / testpass123')
        self.stdout.write(f'  Learners: learner1@test.com to learner10@test.com / testpass123')
        self.stdout.write(f'\nTraining Notification: {not_record.reference_number}')
        self.stdout.write(f'Tranches created: {len(tranches)}')

    def create_brand(self):
        """Create test brand"""
        brand, created = Brand.objects.get_or_create(
            code='SKILLS',
            defaults={
                'name': 'SkillsFlow Training Institute',
                'legal_name': 'SkillsFlow Training (Pty) Ltd',
                'accreditation_number': 'ACC-2024-001',
                'seta_registration': 'SETA-REG-2024-001',
                'email': 'info@skillsflow.co.za',
                'phone': '+27 11 123 4567',
                'website': 'https://skillsflow.co.za',
                'primary_color': '#1a56db',
                'secondary_color': '#7e3af2',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  Created brand: {brand.name}')
        return brand

    def create_campus(self, brand):
        """Create test campus"""
        campus, created = Campus.objects.get_or_create(
            code='JHB-MAIN',
            defaults={
                'brand': brand,
                'name': 'Johannesburg Main Campus',
                'campus_type': 'CAMPUS',
                'region': 'Gauteng',
                'address_line1': '123 Training Street',
                'suburb': 'Sandton',
                'city': 'Johannesburg',
                'province': 'Gauteng',
                'postal_code': '2196',
                'email': 'jhb@skillsflow.co.za',
                'phone': '+27 11 123 4567',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  Created campus: {campus.name}')
        return campus

    def create_seta(self):
        """Create test SETA"""
        seta, created = SETA.objects.get_or_create(
            code='MERSETA',
            defaults={
                'name': 'Manufacturing, Engineering and Related Services SETA',
                'description': 'Skills development for manufacturing and engineering sectors',
                'website': 'https://www.merseta.org.za',
                'email': 'info@merseta.org.za',
                'phone': '+27 11 484 8000',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  Created SETA: {seta.name}')
        return seta

    def create_facilitator_user(self, campus):
        """Create facilitator user"""
        user, created = User.objects.get_or_create(
            email='facilitator@test.com',
            defaults={
                'first_name': 'John',
                'last_name': 'Facilitator',
                'phone': '+27 82 111 2222',
                'is_active': True,
                'email_verified': True,
            }
        )
        if created:
            user.set_password('testpass123')
            user.save()
            
            # Create facilitator role
            role, _ = Role.objects.get_or_create(
                code='FACILITATOR',
                defaults={
                    'name': 'Facilitator',
                    'description': 'Training facilitator',
                    'access_level': 'CAMPUS',
                    'is_active': True,
                }
            )
            UserRole.objects.get_or_create(
                user=user,
                role=role,
                campus=campus,
                defaults={'is_active': True}
            )
            self.stdout.write(f'  Created facilitator: {user.email}')
        return user

    def create_learner_users(self, campus):
        """Create learner users"""
        learner_users = []
        role, _ = Role.objects.get_or_create(
            code='STUDENT',
            defaults={
                'name': 'Student',
                'description': 'Enrolled learner',
                'access_level': 'SELF',
                'is_active': True,
            }
        )
        
        names = [
            ('Thabo', 'Molefe'), ('Sipho', 'Ndlovu'), ('Nomsa', 'Dlamini'),
            ('Bongani', 'Nkosi'), ('Thandiwe', 'Zulu'), ('Mandla', 'Mahlangu'),
            ('Lerato', 'Mokoena'), ('Kagiso', 'Motsepe'), ('Naledi', 'Khumalo'),
            ('Themba', 'Mthembu')
        ]
        
        for i, (first, last) in enumerate(names, 1):
            user, created = User.objects.get_or_create(
                email=f'learner{i}@test.com',
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'phone': f'+27 82 {i:03d} {1000+i:04d}',
                    'is_active': True,
                    'email_verified': True,
                }
            )
            if created:
                user.set_password('testpass123')
                user.save()
                UserRole.objects.get_or_create(
                    user=user, role=role, campus=campus,
                    defaults={'is_active': True}
                )
            learner_users.append(user)
        
        self.stdout.write(f'  Created {len(learner_users)} learner users')
        return learner_users

    def create_qualification(self, seta):
        """Create test qualification"""
        qual, created = Qualification.objects.get_or_create(
            saqa_id='671510001',
            defaults={
                'title': 'Occupational Certificate: Millwright',
                'short_title': 'Millwright',
                'nqf_level': 4,
                'credits': 360,
                'qualification_type': 'OC',
                'seta': seta,
                'minimum_duration_months': 36,
                'maximum_duration_months': 48,
                'registration_start': date(2020, 1, 1),
                'registration_end': date(2027, 12, 31),
                'last_enrollment_date': date(2026, 12, 31),
                'accreditation_number': 'ACC-MIL-2024',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  Created qualification: {qual.short_title}')
        return qual

    def create_modules(self, qualification):
        """Create modules for qualification"""
        module_data = [
            ('K101', 'Engineering Fundamentals', 'K', 30, 300),
            ('K102', 'Mechanical Engineering Theory', 'K', 40, 400),
            ('K103', 'Electrical Systems Theory', 'K', 35, 350),
            ('P101', 'Mechanical Fitting', 'P', 50, 500),
            ('P102', 'Electrical Installation', 'P', 45, 450),
            ('P103', 'Hydraulics & Pneumatics', 'P', 40, 400),
            ('W101', 'Workplace Experience 1', 'W', 60, 600),
            ('W102', 'Workplace Experience 2', 'W', 60, 600),
        ]
        
        modules = []
        for i, (code, title, mtype, credits, hours) in enumerate(module_data, 1):
            module, created = Module.objects.get_or_create(
                qualification=qualification,
                code=code,
                defaults={
                    'title': title,
                    'module_type': mtype,
                    'credits': credits,
                    'notional_hours': hours,
                    'sequence_order': i,
                    'is_compulsory': True,
                    'is_active': True,
                }
            )
            modules.append(module)
        
        self.stdout.write(f'  Created {len(modules)} modules')
        return modules

    def create_assessment_activities(self, modules):
        """Create assessment activities for modules"""
        activities = []
        activity_types = [
            ('TEST', 'Knowledge Test'),
            ('PRACTICAL', 'Practical Assessment'),
            ('ASSIGNMENT', 'Assignment'),
        ]
        
        for module in modules:
            for j, (atype, aname) in enumerate(activity_types[:2], 1):  # 2 activities per module
                activity, _ = AssessmentActivity.objects.get_or_create(
                    module=module,
                    code=f'{module.code}-A{j}',
                    defaults={
                        'title': f'{module.title} - {aname}',
                        'activity_type': atype,
                        'weight': Decimal('50.00'),
                        'max_attempts': 3,
                        'sequence_order': j,
                        'is_active': True,
                    }
                )
                activities.append(activity)
        
        self.stdout.write(f'  Created {len(activities)} assessment activities')
        return activities

    def create_cohort(self, qualification, facilitator, campus):
        """Create training cohort"""
        cohort, created = Cohort.objects.get_or_create(
            code='MIL-2024-01',
            defaults={
                'campus': campus,
                'name': 'Millwright Cohort - January 2024',
                'qualification': qualification,
                'start_date': date(2024, 1, 15),
                'end_date': date(2027, 1, 14),
                'max_capacity': 20,
                'current_count': 10,
                'status': 'ACTIVE',
                'facilitator': facilitator,
                'description': 'First cohort of millwright apprentices for 2024',
            }
        )
        if created:
            self.stdout.write(f'  Created cohort: {cohort.name}')
        return cohort

    def create_venue(self, campus):
        """Create training venue"""
        venue, created = Venue.objects.get_or_create(
            campus=campus,
            code='WS-01',
            defaults={
                'name': 'Workshop 1',
                'venue_type': 'WORKSHOP',
                'capacity': 25,
                'equipment': ['Lathes', 'Milling Machines', 'Welding Stations', 'Tool Cabinets'],
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  Created venue: {venue.name}')
        return venue

    def create_learners(self, users, campus):
        """Create learner profiles"""
        learners = []
        provinces = ['GP', 'KZN', 'WC', 'EC', 'LP']
        
        for i, user in enumerate(users):
            # Generate SA ID-like number (not real validation)
            year = random.randint(90, 99)
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            sa_id = f'{year:02d}{month:02d}{day:02d}5088088'
            
            # Create address
            address, _ = Address.objects.get_or_create(
                line_1=f'{100 + i} Test Street',
                defaults={
                    'suburb': 'Suburb',
                    'city': 'Johannesburg',
                    'province': 'Gauteng',
                    'postal_code': f'{2000 + i}',
                    'country': 'South Africa',
                }
            )
            
            learner, created = Learner.objects.get_or_create(
                learner_number=f'LRN-2024-{i+1:04d}',
                defaults={
                    'campus': campus,
                    'user': user,
                    'sa_id_number': sa_id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'date_of_birth': date(1990 + i % 10, (i % 12) + 1, 15),
                    'gender': random.choice(['M', 'F']),
                    'population_group': random.choice(['A', 'C', 'I', 'W']),
                    'citizenship': 'SA',
                    'home_language': random.choice(['Zulu', 'English', 'Sotho', 'Xhosa']),
                    'disability_status': 'N',
                    'socio_economic_status': 'U',
                    'highest_qualification': '4',
                    'email': user.email,
                    'phone_mobile': user.phone,
                    'physical_address': address,
                    'province_code': random.choice(provinces),
                    'popia_consent_given': True,
                    'popia_consent_date': timezone.now(),
                }
            )
            learners.append(learner)
        
        self.stdout.write(f'  Created {len(learners)} learner profiles')
        return learners

    def create_enrollments(self, learners, qualification, cohort):
        """Create enrollments for learners - using bulk_create to bypass signals"""
        enrollments = []
        statuses = ['ACTIVE', 'ACTIVE', 'ACTIVE', 'ENROLLED', 'COMPLETED']
        
        enrollments_to_create = []
        for i, learner in enumerate(learners):
            enrollment_number = f'ENR-2024-{i+1:04d}'
            if not Enrollment.objects.filter(enrollment_number=enrollment_number).exists():
                enrollments_to_create.append(Enrollment(
                    enrollment_number=enrollment_number,
                    campus=cohort.campus,
                    learner=learner,
                    qualification=qualification,
                    cohort=cohort,
                    application_date=date(2023, 11, 1),
                    enrollment_date=date(2024, 1, 10),
                    start_date=date(2024, 1, 15),
                    expected_completion=date(2027, 1, 14),
                    status=random.choice(statuses),
                    funding_type='LEARNERSHIP',
                    funding_source='MERSETA Discretionary Grant',
                    agreement_signed=True,
                    agreement_date=date(2024, 1, 8),
                ))
        
        # Use bulk_create to bypass signals
        if enrollments_to_create:
            Enrollment.objects.bulk_create(enrollments_to_create, ignore_conflicts=True)
        
        # Get all enrollments
        enrollments = list(Enrollment.objects.filter(cohort=cohort))
        
        self.stdout.write(f'  Created {len(enrollments_to_create)} enrollments')
        return enrollments

    def create_employer(self, seta):
        """Create employer for workplace placements"""
        employer, created = Employer.objects.get_or_create(
            name='Industrial Engineering Solutions',
            defaults={
                'trading_name': 'IES Engineering',
                'registration_number': '2015/123456/07',
                'vat_number': '4012345678',
                'sdl_number': 'SDL-2015-001',
                'sic_code': '29100',
                'seta': seta,
                'contact_person': 'Sarah Engineering',
                'contact_email': 'hr@ieseng.co.za',
                'contact_phone': '+27 11 987 6543',
                'workplace_approved': True,
                'approval_date': date(2023, 6, 1),
                'approval_expiry': date(2026, 5, 31),
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'  Created employer: {employer.name}')
        return employer

    def create_employments(self, learners, employer):
        """Create learner employment records"""
        for learner in learners:
            LearnerEmployment.objects.get_or_create(
                learner=learner,
                employer=employer,
                defaults={
                    'position': 'Apprentice Millwright',
                    'department': 'Maintenance',
                    'start_date': date(2024, 4, 1),
                    'is_current': True,
                    'mentor_name': 'Mike Mentor',
                    'mentor_email': 'mike@ieseng.co.za',
                    'mentor_phone': '+27 82 555 6666',
                    'mentor_position': 'Senior Millwright',
                }
            )
        self.stdout.write(f'  Created {len(learners)} employment records')

    def create_schedule_sessions(self, cohort, modules, venue, facilitator):
        """Create schedule sessions for facilitator - using bulk_create to avoid signals"""
        sessions = []
        today = date.today()
        
        sessions_to_create = []
        
        # Create sessions for the next 4 weeks
        for week in range(4):
            for day_offset in [0, 2, 4]:  # Mon, Wed, Fri
                session_date = today + timedelta(days=(week * 7) + day_offset)
                if session_date.weekday() >= 5:  # Skip weekends
                    continue
                
                module = modules[week % len(modules)]
                
                # Check if already exists
                if not ScheduleSession.objects.filter(
                    cohort=cohort, module=module, venue=venue, date=session_date
                ).exists():
                    sessions_to_create.append(ScheduleSession(
                        cohort=cohort,
                        module=module,
                        venue=venue,
                        date=session_date,
                        facilitator=facilitator,
                        start_time='08:00',
                        end_time='16:00',
                        session_type='LECTURE' if module.module_type == 'K' else 'PRACTICAL',
                        topic=f'{module.title} - Week {week + 1}',
                        description=f'Training session for {module.title}',
                    ))
        
        # Create some past sessions too
        for week in range(1, 5):
            for day_offset in [0, 2, 4]:
                session_date = today - timedelta(days=(week * 7) - day_offset)
                if session_date.weekday() >= 5:
                    continue
                
                module = modules[(week + 4) % len(modules)]
                
                if not ScheduleSession.objects.filter(
                    cohort=cohort, module=module, venue=venue, date=session_date
                ).exists():
                    sessions_to_create.append(ScheduleSession(
                        cohort=cohort,
                        module=module,
                        venue=venue,
                        date=session_date,
                        facilitator=facilitator,
                        start_time='08:00',
                        end_time='16:00',
                        session_type='LECTURE' if module.module_type == 'K' else 'PRACTICAL',
                        topic=f'{module.title} - Week {week}',
                    ))
        
        # Use bulk_create to bypass signals
        if sessions_to_create:
            ScheduleSession.objects.bulk_create(sessions_to_create, ignore_conflicts=True)
        
        # Get all sessions
        sessions = list(ScheduleSession.objects.filter(cohort=cohort))
        
        self.stdout.write(f'  Created {len(sessions_to_create)} schedule sessions')
        return sessions

    def create_attendance_records(self, sessions, enrollments, facilitator):
        """Create attendance records"""
        count = 0
        statuses = ['PRESENT', 'PRESENT', 'PRESENT', 'PRESENT', 'LATE', 'ABSENT']
        
        for session in sessions:
            if session.date <= date.today():  # Only past sessions
                for enrollment in enrollments:
                    status = random.choice(statuses)
                    Attendance.objects.get_or_create(
                        session=session,
                        enrollment=enrollment,
                        defaults={
                            'status': status,
                            'check_in_method': 'MANUAL',
                            'check_in_time': timezone.now().replace(
                                hour=8, minute=random.randint(0, 30)
                            ) if status != 'ABSENT' else None,
                            'recorded_by': facilitator,
                        }
                    )
                    count += 1
        
        self.stdout.write(f'  Created {count} attendance records')

    def create_assessment_results(self, enrollments, activities, facilitator):
        """Create assessment results"""
        count = 0
        results = ['C', 'C', 'C', 'NYC']  # 75% pass rate
        
        for enrollment in enrollments[:7]:  # Only first 7 learners have results
            for activity in activities[:6]:  # First 6 activities
                result = random.choice(results)
                AssessmentResult.objects.get_or_create(
                    enrollment=enrollment,
                    activity=activity,
                    attempt_number=1,
                    defaults={
                        'assessor': facilitator,
                        'result': result,
                        'percentage_score': Decimal(random.randint(50, 95)) if result == 'C' else Decimal(random.randint(30, 49)),
                        'assessment_date': date.today() - timedelta(days=random.randint(7, 60)),
                        'feedback': 'Good work!' if result == 'C' else 'Needs improvement on practical skills.',
                        'status': 'FINALIZED',
                        'locked': True,
                    }
                )
                count += 1
        
        self.stdout.write(f'  Created {count} assessment results')

    def create_training_notification(self, qualification, campus):
        """Create Training Notification (NOT)"""
        # First ensure we have a corporate client
        from corporate.models import CorporateClient
        client, _ = CorporateClient.objects.get_or_create(
            company_name='Mining Corp SA',
            defaults={
                'campus': campus,
                'trading_name': 'Mining Corp',
                'registration_number': '2010/987654/07',
                'vat_number': '4098765432',
                'status': 'ACTIVE',
            }
        )
        
        not_record, created = TrainingNotification.objects.get_or_create(
            reference_number='NOT-2024-0001',
            defaults={
                'title': 'Millwright Apprenticeship Programme - Mining Corp',
                'project_type': 'OC_APPRENTICESHIP',
                'funder': 'CORPORATE_DG',
                'description': '''
                    36-month apprenticeship programme for 10 millwright apprentices.
                    Funded through MERSETA Discretionary Grant with co-funding from Mining Corp SA.
                    Training includes theory, practical, and workplace components.
                ''',
                'status': 'IN_PROGRESS',
                'priority': 'HIGH',
                'client_name': 'Mining Corp SA',
                'corporate_client': client,
                'tender_reference': 'MERSETA-DG-2023-1234',
                'contract_value': Decimal('2500000.00'),
                'qualification': qualification,
                'expected_learner_count': 10,
                'learner_source': 'NEW_RECRUITMENT',
            }
        )
        if created:
            self.stdout.write(f'  Created NOT: {not_record.reference_number}')
        return not_record

    def create_tranches(self, not_record):
        """Create tranche schedules"""
        today = date.today()
        
        tranche_data = [
            # (seq, type, name, months_offset, status, amount, percentage)
            (1, 'COMMENCEMENT', 'Tranche 1 - Commencement', -6, 'PAID', 375000, 15),
            (2, 'REGISTRATION', 'Tranche 2 - SETA Registration', -4, 'PAID', 250000, 10),
            (3, 'PPE_ISSUE', 'Tranche 3 - PPE & Toolbox Issue', -2, 'APPROVED', 250000, 10),
            (4, 'YEAR1_PROGRESS', 'Tranche 4 - Year 1 Progress', 0, 'SUBMITTED', 375000, 15),
            (5, 'PLACEMENT', 'Tranche 5 - Workplace Placement', 3, 'EVIDENCE_COLLECTION', 250000, 10),
            (6, 'YEAR2_PROGRESS', 'Tranche 6 - Year 2 Progress', 12, 'SCHEDULED', 375000, 15),
            (7, 'MODERATION', 'Tranche 7 - Internal Moderation', 24, 'SCHEDULED', 250000, 10),
            (8, 'TRADE_TEST', 'Tranche 8 - Trade Test', 33, 'SCHEDULED', 187500, 7.5),
            (9, 'CERTIFICATION', 'Tranche 9 - Certification', 36, 'SCHEDULED', 187500, 7.5),
        ]
        
        tranches = []
        for seq, ttype, name, months, status, amount, pct in tranche_data:
            due_date = today + timedelta(days=months * 30)
            
            tranche, created = TrancheSchedule.objects.get_or_create(
                training_notification=not_record,
                sequence_number=seq,
                defaults={
                    'tranche_type': ttype,
                    'name': name,
                    'description': f'Evidence and claim for {name.lower()}',
                    'status': status,
                    'priority': 'HIGH' if months <= 0 else 'MEDIUM',
                    'due_date': due_date,
                    'reminder_date': due_date - timedelta(days=14),
                    'amount': Decimal(amount),
                    'learner_count_target': 10,
                    'learner_count_actual': 10 if status in ['PAID', 'APPROVED', 'SUBMITTED'] else 0,
                }
            )
            
            # Update status-specific dates
            if status == 'PAID':
                tranche.evidence_submitted_date = due_date - timedelta(days=30)
                tranche.submitted_to_funder_date = due_date - timedelta(days=25)
                tranche.funder_approved_date = due_date - timedelta(days=10)
                tranche.payment_received_date = due_date
                tranche.actual_amount_received = Decimal(amount)
                tranche.funder_reference = f'MERSETA-PAY-{seq:03d}'
                tranche.save()
            elif status == 'APPROVED':
                tranche.evidence_submitted_date = due_date - timedelta(days=20)
                tranche.submitted_to_funder_date = due_date - timedelta(days=15)
                tranche.funder_approved_date = due_date - timedelta(days=5)
                tranche.funder_reference = f'MERSETA-APP-{seq:03d}'
                tranche.save()
            elif status == 'SUBMITTED':
                tranche.evidence_submitted_date = due_date - timedelta(days=10)
                tranche.submitted_to_funder_date = due_date - timedelta(days=7)
                tranche.save()
            
            tranches.append(tranche)
        
        self.stdout.write(f'  Created {len(tranches)} tranches')
        return tranches

    def create_evidence_requirements(self, tranches):
        """Create evidence requirements for tranches"""
        requirements_map = {
            'COMMENCEMENT': [
                ('LEARNER_LIST', 'Signed Learner Register', True),
                ('LEARNER_AGREEMENTS', 'Learner Agreements', True),
                ('ID_COPIES', 'Certified ID Copies', True),
                ('TRAINING_SCHEDULE', 'Training Schedule', True),
            ],
            'REGISTRATION': [
                ('SETA_REGISTRATION', 'SETA Registration Confirmation', True),
                ('NLRD_REGISTRATION', 'NLRD Upload Proof', True),
                ('ENROLLMENT_PROOF', 'Provider Registration', True),
            ],
            'PPE_ISSUE': [
                ('PPE_ISSUE_REGISTER', 'PPE Issue Register', True),
                ('TOOLBOX_ISSUE_REGISTER', 'Toolbox Issue Register', True),
                ('EQUIPMENT_PHOTOS', 'Issue Photographs', False),
                ('DELIVERY_NOTES', 'Supplier Delivery Notes', True),
            ],
            'YEAR1_PROGRESS': [
                ('ATTENDANCE_REGISTERS', 'Attendance Registers', True),
                ('ASSESSMENT_RESULTS', 'Assessment Results Summary', True),
                ('COMPETENCY_MATRIX', 'Competency Achievement Matrix', True),
                ('FACILITATOR_REPORTS', 'Facilitator Progress Reports', True),
            ],
            'PLACEMENT': [
                ('PLACEMENT_LETTERS', 'Workplace Placement Letters', True),
                ('WORKPLACE_AGREEMENTS', 'Workplace Agreements', True),
                ('MENTOR_ASSIGNMENTS', 'Mentor Assignment Records', True),
            ],
            'YEAR2_PROGRESS': [
                ('ATTENDANCE_REGISTERS', 'Year 2 Attendance', True),
                ('LOGBOOKS', 'Workplace Logbooks', True),
                ('WORKPLACE_REPORTS', 'Workplace Progress Reports', True),
            ],
            'MODERATION': [
                ('MODERATION_REPORTS', 'Internal Moderation Reports', True),
                ('POE_SAMPLES', 'POE Sample Documents', True),
                ('ASSESSMENT_TOOLS', 'Assessment Instruments', False),
            ],
            'TRADE_TEST': [
                ('TRADE_TEST_BOOKINGS', 'Trade Test Booking Confirmations', True),
                ('TRADE_TEST_RESULTS', 'Trade Test Results', True),
            ],
            'CERTIFICATION': [
                ('CERTIFICATES', 'Learner Certificates', True),
                ('CERTIFICATE_REGISTER', 'Certificate Issue Register', True),
                ('CEREMONY_PHOTOS', 'Graduation Ceremony Photos', False),
            ],
        }
        
        count = 0
        for tranche in tranches:
            reqs = requirements_map.get(tranche.tranche_type, [])
            for ev_type, ev_name, mandatory in reqs:
                TrancheEvidenceRequirement.objects.get_or_create(
                    tranche=tranche,
                    evidence_type=ev_type,
                    defaults={
                        'name': ev_name,
                        'description': f'Required: {ev_name} for {tranche.name}',
                        'is_mandatory': mandatory,
                        'expected_count': 10 if ev_type in ['ID_COPIES', 'LEARNER_AGREEMENTS'] else 1,
                        'deadline': tranche.due_date,
                    }
                )
                count += 1
        
        self.stdout.write(f'  Created {count} evidence requirements')

    def create_tranche_submissions(self, tranches, user):
        """Create tranche submissions"""
        count = 0
        for tranche in tranches:
            if tranche.status in ['SUBMITTED', 'APPROVED', 'PAID']:
                submission, created = TrancheSubmission.objects.get_or_create(
                    tranche=tranche,
                    defaults={
                        'status': 'PAID' if tranche.status == 'PAID' else (
                            'APPROVED' if tranche.status == 'APPROVED' else 'SUBMITTED'
                        ),
                        'submission_method': 'PORTAL',
                        'submitted_by': user,
                        'submission_date': timezone.now() - timedelta(days=random.randint(5, 30)),
                        'portal_reference': f'MERSETA-{tranche.sequence_number:03d}',
                        'qc_checklist_completed': True,
                        'qc_completed_by': user,
                        'qc_completed_date': timezone.now() - timedelta(days=random.randint(30, 45)),
                        'claimed_amount': tranche.amount,
                        'approved_amount': tranche.amount if tranche.status in ['APPROVED', 'PAID'] else None,
                        'notes': 'All evidence verified and submitted.',
                    }
                )
                if created:
                    count += 1
        
        self.stdout.write(f'  Created {count} tranche submissions')

    def create_tranche_comments(self, tranches, user):
        """Create tranche comments"""
        count = 0
        comment_templates = [
            ('INTERNAL', 'Evidence collection in progress. Following up with admin team.'),
            ('QC_NOTE', 'QC check completed. All documents verified.'),
            ('STATUS_UPDATE', 'Status updated. Ready for funder submission.'),
            ('FUNDER_QUERY', 'Funder requested additional documentation for PPE issue.'),
            ('FUNDER_RESPONSE', 'Additional documentation submitted as requested.'),
        ]
        
        for tranche in tranches:
            if tranche.status not in ['SCHEDULED']:
                for i in range(random.randint(1, 3)):
                    ctype, comment_text = random.choice(comment_templates)
                    TrancheComment.objects.get_or_create(
                        tranche=tranche,
                        comment_type=ctype,
                        comment=comment_text,
                        defaults={
                            'created_by': user,
                        }
                    )
                    count += 1
        
        self.stdout.write(f'  Created {count} tranche comments')

    def create_announcements(self, brand, campus):
        """Create portal announcements"""
        announcements_data = [
            ('Welcome to the New Academic Year', 'NORMAL', 'ALL', 
             'Welcome back to all learners and staff. We look forward to a successful year of training.'),
            ('Assessment Schedule Update', 'HIGH', 'LEARNERS',
             'Please note the updated assessment schedule for Q1. Check your portal for dates.'),
            ('Safety Training Reminder', 'URGENT', 'LEARNERS',
             'All learners must complete mandatory safety training before entering workshop areas.'),
            ('Facilitator Meeting', 'NORMAL', 'FACILITATORS',
             'Monthly facilitator meeting scheduled for Friday at 14:00 in the boardroom.'),
        ]
        
        for title, priority, audience, content in announcements_data:
            Announcement.objects.get_or_create(
                brand=brand,
                title=title,
                defaults={
                    'campus': campus,
                    'content': content,
                    'audience': audience,
                    'priority': priority,
                    'is_pinned': priority == 'URGENT',
                    'publish_at': timezone.now() - timedelta(days=random.randint(1, 7)),
                    'is_published': True,
                }
            )
        
        self.stdout.write(f'  Created {len(announcements_data)} announcements')

    def create_notifications(self, facilitator_user, learner_users):
        """Create notifications for users"""
        # Facilitator notifications
        facilitator_notifs = [
            ('Assessment Due', 'You have 5 assessments pending review.', 'ASSESSMENT', 'REMINDER'),
            ('Attendance Alert', 'Learner Thabo Molefe has 3 consecutive absences.', 'ATTENDANCE', 'WARNING'),
            ('Schedule Updated', 'Your schedule for next week has been updated.', 'SCHEDULE', 'INFO'),
            ('New Enrollment', 'New learner has been enrolled in your cohort.', 'ENROLLMENT', 'INFO'),
        ]
        
        for title, message, category, ntype in facilitator_notifs:
            Notification.objects.get_or_create(
                user=facilitator_user,
                title=title,
                defaults={
                    'message': message,
                    'category': category,
                    'notification_type': ntype,
                    'is_read': random.choice([True, False]),
                }
            )
        
        # Learner notifications
        learner_notifs = [
            ('Assessment Result', 'Your assessment result for K101-A1 is now available.', 'ASSESSMENT', 'INFO'),
            ('Upcoming Session', 'You have a training session tomorrow at 08:00.', 'SCHEDULE', 'REMINDER'),
            ('Document Required', 'Please upload your updated ID copy.', 'DOCUMENT', 'WARNING'),
        ]
        
        for user in learner_users[:5]:
            for title, message, category, ntype in learner_notifs:
                Notification.objects.get_or_create(
                    user=user,
                    title=title,
                    defaults={
                        'message': message,
                        'category': category,
                        'notification_type': ntype,
                        'is_read': random.choice([True, False]),
                    }
                )
        
        self.stdout.write(f'  Created notifications for facilitator and learners')
