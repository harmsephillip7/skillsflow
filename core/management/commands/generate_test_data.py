"""
Management command to populate the database with comprehensive test data.
This creates realistic data across all apps for testing purposes.
"""
import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Populate database with comprehensive test data for all apps'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing test data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting test data generation...')
        
        with transaction.atomic():
            # Create data in dependency order
            self.create_users()
            self.create_brands_and_campuses()
            self.create_setas()
            self.create_qualifications()
            self.create_venues()
            self.create_cohorts()
            self.create_learners()
            self.create_corporate_clients()
            self.create_training_notifications()
            self.create_intakes()
            self.create_enrollments()
            self.create_trade_test_data()
            self.create_finance_data()
        
        self.stdout.write(self.style.SUCCESS('✅ Test data generation complete!'))

    def create_users(self):
        """Create test users with various roles"""
        from core.models import User
        
        self.stdout.write('  Creating users...')
        
        users_data = [
            {'email': 'admin@skillsflow.co.za', 'first_name': 'System', 'last_name': 'Admin', 'is_superuser': True, 'is_staff': True},
            {'email': 'principal@skillsflow.co.za', 'first_name': 'John', 'last_name': 'Mokoena', 'is_staff': True},
            {'email': 'registrar@skillsflow.co.za', 'first_name': 'Sarah', 'last_name': 'Van Der Berg', 'is_staff': True},
            {'email': 'facilitator1@skillsflow.co.za', 'first_name': 'David', 'last_name': 'Nkosi', 'is_staff': True},
            {'email': 'facilitator2@skillsflow.co.za', 'first_name': 'Thandi', 'last_name': 'Dlamini', 'is_staff': True},
            {'email': 'assessor@skillsflow.co.za', 'first_name': 'Peter', 'last_name': 'Botha', 'is_staff': True},
            {'email': 'finance@skillsflow.co.za', 'first_name': 'Linda', 'last_name': 'Govender', 'is_staff': True},
            {'email': 'corporate@skillsflow.co.za', 'first_name': 'Michael', 'last_name': 'Smith', 'is_staff': True},
            {'email': 'academic@skillsflow.co.za', 'first_name': 'Nomsa', 'last_name': 'Zulu', 'is_staff': True},
            {'email': 'wbl.officer@skillsflow.co.za', 'first_name': 'James', 'last_name': 'Molefe', 'is_staff': True},
        ]
        
        self.users = {}
        for user_data in users_data:
            user, created = User.objects.get_or_create(
                email=user_data['email'],
                defaults={
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'is_superuser': user_data.get('is_superuser', False),
                    'is_staff': user_data.get('is_staff', False),
                }
            )
            if created:
                user.set_password('testpass123')
                user.save()
            self.users[user_data['email'].split('@')[0]] = user
        
        self.stdout.write(f'    Created {len(users_data)} users')

    def create_brands_and_campuses(self):
        """Create brands and campuses"""
        from tenants.models import Brand, Campus
        
        self.stdout.write('  Creating brands and campuses...')
        
        brands_data = [
            {'code': 'SKF', 'name': 'SkillsFlow Training Institute', 'primary_color': '#0891b2'},
            {'code': 'TTA', 'name': 'Technical Training Academy', 'primary_color': '#7c3aed'},
            {'code': 'PTS', 'name': 'Professional Training Solutions', 'primary_color': '#059669'},
        ]
        
        self.brands = {}
        for brand_data in brands_data:
            brand, _ = Brand.objects.get_or_create(
                code=brand_data['code'],
                defaults=brand_data
            )
            self.brands[brand_data['code']] = brand
        
        campuses_data = [
            {'brand': 'SKF', 'code': 'SKF-JHB', 'name': 'Johannesburg Campus', 'city': 'Johannesburg', 'province': 'Gauteng', 'campus_type': 'CAMPUS'},
            {'brand': 'SKF', 'code': 'SKF-CPT', 'name': 'Cape Town Campus', 'city': 'Cape Town', 'province': 'Western Cape', 'campus_type': 'CAMPUS'},
            {'brand': 'SKF', 'code': 'SKF-DBN', 'name': 'Durban Campus', 'city': 'Durban', 'province': 'KwaZulu-Natal', 'campus_type': 'CAMPUS'},
            {'brand': 'SKF', 'code': 'SKF-HO', 'name': 'Head Office', 'city': 'Johannesburg', 'province': 'Gauteng', 'campus_type': 'HEAD_OFFICE'},
            {'brand': 'TTA', 'code': 'TTA-PTA', 'name': 'Pretoria Campus', 'city': 'Pretoria', 'province': 'Gauteng', 'campus_type': 'CAMPUS'},
            {'brand': 'TTA', 'code': 'TTA-BLM', 'name': 'Bloemfontein Campus', 'city': 'Bloemfontein', 'province': 'Free State', 'campus_type': 'CAMPUS'},
            {'brand': 'PTS', 'code': 'PTS-PE', 'name': 'Port Elizabeth Campus', 'city': 'Gqeberha', 'province': 'Eastern Cape', 'campus_type': 'CAMPUS'},
        ]
        
        self.campuses = {}
        for campus_data in campuses_data:
            brand = self.brands[campus_data.pop('brand')]
            campus, _ = Campus.objects.get_or_create(
                code=campus_data['code'],
                defaults={**campus_data, 'brand': brand}
            )
            self.campuses[campus_data['code']] = campus
        
        self.stdout.write(f'    Created {len(brands_data)} brands and {len(campuses_data)} campuses')

    def create_setas(self):
        """Create SETA records"""
        from learners.models import SETA
        
        self.stdout.write('  Creating SETAs...')
        
        setas_data = [
            {'code': 'MERSETA', 'name': 'Manufacturing, Engineering and Related Services SETA'},
            {'code': 'MICT', 'name': 'Media, Information and Communication Technologies SETA'},
            {'code': 'SERVICES', 'name': 'Services SETA'},
            {'code': 'CETA', 'name': 'Construction Education and Training Authority'},
            {'code': 'EWSETA', 'name': 'Energy and Water SETA'},
            {'code': 'TETA', 'name': 'Transport Education and Training Authority'},
            {'code': 'W&RSETA', 'name': 'Wholesale and Retail SETA'},
            {'code': 'BANKSETA', 'name': 'Banking Sector Education and Training Authority'},
        ]
        
        self.setas = {}
        for seta_data in setas_data:
            seta, _ = SETA.objects.get_or_create(
                code=seta_data['code'],
                defaults={'name': seta_data['name'], 'is_active': True}
            )
            self.setas[seta_data['code']] = seta
        
        self.stdout.write(f'    Created {len(setas_data)} SETAs')

    def create_qualifications(self):
        """Create qualifications/programmes"""
        from academics.models import Qualification
        
        self.stdout.write('  Creating qualifications...')
        
        today = date.today()
        qualifications_data = [
            {
                'saqa_id': '94941',
                'title': 'Occupational Certificate: Electrician',
                'short_title': 'Electrician',
                'nqf_level': 4,
                'credits': 360,
                'qualification_type': 'OC',
                'seta': 'EWSETA',
                'minimum_duration_months': 36,
            },
            {
                'saqa_id': '67465',
                'title': 'National Certificate: Welding Application',
                'short_title': 'Welding',
                'nqf_level': 3,
                'credits': 120,
                'qualification_type': 'NC',
                'seta': 'MERSETA',
                'minimum_duration_months': 12,
            },
            {
                'saqa_id': '49652',
                'title': 'National Certificate: Project Management',
                'short_title': 'Project Management',
                'nqf_level': 5,
                'credits': 120,
                'qualification_type': 'NC',
                'seta': 'SERVICES',
                'minimum_duration_months': 12,
            },
            {
                'saqa_id': '57712',
                'title': 'National Certificate: IT Systems Support',
                'short_title': 'IT Support',
                'nqf_level': 5,
                'credits': 131,
                'qualification_type': 'NC',
                'seta': 'MICT',
                'minimum_duration_months': 12,
            },
            {
                'saqa_id': '94022',
                'title': 'Occupational Certificate: Plumber',
                'short_title': 'Plumber',
                'nqf_level': 4,
                'credits': 360,
                'qualification_type': 'OC',
                'seta': 'CETA',
                'minimum_duration_months': 36,
            },
            {
                'saqa_id': '78964',
                'title': 'National Certificate: Business Administration Services',
                'short_title': 'Business Admin',
                'nqf_level': 4,
                'credits': 140,
                'qualification_type': 'NC',
                'seta': 'SERVICES',
                'minimum_duration_months': 12,
            },
            {
                'saqa_id': '59201',
                'title': 'National Certificate: Generic Management',
                'short_title': 'Management',
                'nqf_level': 5,
                'credits': 162,
                'qualification_type': 'NC',
                'seta': 'SERVICES',
                'minimum_duration_months': 18,
            },
            {
                'saqa_id': '93997',
                'title': 'Occupational Certificate: Boilermaker',
                'short_title': 'Boilermaker',
                'nqf_level': 4,
                'credits': 360,
                'qualification_type': 'OC',
                'seta': 'MERSETA',
                'minimum_duration_months': 36,
            },
        ]
        
        self.qualifications = {}
        for q_data in qualifications_data:
            seta = self.setas[q_data.pop('seta')]
            qual, _ = Qualification.objects.get_or_create(
                saqa_id=q_data['saqa_id'],
                defaults={
                    **q_data,
                    'seta': seta,
                    'maximum_duration_months': q_data['minimum_duration_months'] + 12,
                    'registration_start': today - timedelta(days=365*2),
                    'registration_end': today + timedelta(days=365*3),
                    'last_enrollment_date': today + timedelta(days=365*2),
                    'is_active': True,
                }
            )
            self.qualifications[q_data['saqa_id']] = qual
        
        self.stdout.write(f'    Created {len(qualifications_data)} qualifications')

    def create_venues(self):
        """Create training venues"""
        from logistics.models import Venue
        
        self.stdout.write('  Creating venues...')
        
        venue_types = [
            ('CLASSROOM', 30), ('LAB', 20), ('WORKSHOP', 15), ('BOARDROOM', 12)
        ]
        
        count = 0
        for campus_code, campus in self.campuses.items():
            if campus.campus_type == 'HEAD_OFFICE':
                continue
            for i, (venue_type, capacity) in enumerate(venue_types, 1):
                Venue.objects.get_or_create(
                    campus=campus,
                    code=f'{campus_code}-{venue_type[:3]}{i}',
                    defaults={
                        'name': f'{venue_type.title()} {i}',
                        'venue_type': venue_type,
                        'capacity': capacity,
                    }
                )
                count += 1
        
        self.stdout.write(f'    Created {count} venues')

    def create_cohorts(self):
        """Create training cohorts"""
        from logistics.models import Cohort
        
        self.stdout.write('  Creating cohorts...')
        
        today = date.today()
        cohort_configs = [
            ('ACTIVE', -60, 180),    # Started 2 months ago, 6 months remaining
            ('ACTIVE', -120, 240),   # Started 4 months ago, 8 months remaining
            ('PLANNED', 30, 365),    # Starts in 1 month
            ('PLANNED', 60, 365),    # Starts in 2 months
            ('COMPLETED', -400, -35),# Completed last month
        ]
        
        self.cohorts = []
        count = 0
        for campus_code, campus in self.campuses.items():
            if campus.campus_type == 'HEAD_OFFICE':
                continue
            for qual in list(self.qualifications.values())[:4]:
                for status, start_offset, end_offset in cohort_configs[:2]:  # 2 cohorts per qual
                    cohort, created = Cohort.objects.get_or_create(
                        code=f'{campus_code}-{qual.short_title[:4].upper()}-{count:03d}',
                        defaults={
                            'name': f'{qual.short_title} - {campus.name}',
                            'qualification': qual,
                            'campus': campus,
                            'start_date': today + timedelta(days=start_offset),
                            'end_date': today + timedelta(days=end_offset),
                            'max_capacity': 25,
                            'current_count': random.randint(10, 22) if status == 'ACTIVE' else 0,
                            'status': status,
                            'facilitator': self.users.get('facilitator1'),
                        }
                    )
                    self.cohorts.append(cohort)
                    count += 1
        
        self.stdout.write(f'    Created {count} cohorts')

    def create_learners(self):
        """Create test learners"""
        from learners.models import Learner, Guardian
        
        self.stdout.write('  Creating learners...')
        
        first_names_male = ['Sipho', 'Thabo', 'John', 'David', 'Michael', 'Peter', 'James', 'William', 'Robert', 'Joseph', 'Bongani', 'Mandla', 'Lucky', 'Emmanuel', 'Jacob']
        first_names_female = ['Nomsa', 'Thandi', 'Sarah', 'Mary', 'Patricia', 'Jennifer', 'Elizabeth', 'Linda', 'Barbara', 'Susan', 'Precious', 'Grace', 'Mpho', 'Lerato', 'Palesa']
        last_names = ['Nkosi', 'Dlamini', 'Zulu', 'Mthembu', 'Ndlovu', 'Mokoena', 'Khumalo', 'Sithole', 'Van Der Berg', 'Botha', 'Smith', 'Williams', 'Johnson', 'Govender', 'Pillay']
        
        provinces = ['GP', 'KZN', 'WC', 'EC', 'MP', 'LP', 'FS', 'NW', 'NC']
        
        self.learners = []
        campus_list = [c for c in self.campuses.values() if c.campus_type != 'HEAD_OFFICE']
        
        for i in range(150):
            gender = random.choice(['M', 'F'])
            first_name = random.choice(first_names_male if gender == 'M' else first_names_female)
            last_name = random.choice(last_names)
            
            # Generate SA ID-like number (not real validation)
            birth_year = random.randint(1985, 2005)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            id_suffix = f'{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}'
            gender_digit = random.randint(5, 9) if gender == 'M' else random.randint(0, 4)
            id_number = f'{birth_year%100:02d}{birth_month:02d}{birth_day:02d}{gender_digit}{id_suffix}08{random.randint(0,9)}'
            
            campus = random.choice(campus_list)
            learner, created = Learner.objects.get_or_create(
                learner_number=f'LRN{2024000 + i:07d}',
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'sa_id_number': id_number,
                    'gender': gender,
                    'date_of_birth': date(birth_year, birth_month, birth_day),
                    'email': f'{first_name.lower()}.{last_name.lower()}{i}@email.co.za',
                    'phone_mobile': f'07{random.randint(10000000, 99999999)}',
                    'population_group': random.choice(['A', 'C', 'I', 'W']),
                    'citizenship': 'SA',
                    'home_language': random.choice(['Zulu', 'Xhosa', 'English', 'Afrikaans', 'Sotho', 'Tswana']),
                    'province_code': random.choice(provinces),
                    'disability_status': random.choices(['N', '1', '2', '3', '4', '5'], weights=[90, 2, 2, 2, 2, 2])[0],
                    'socio_economic_status': random.choice(['E', 'U', 'S', 'N']),
                    'highest_qualification': random.choice(['3', '4', '5', '6']),
                    'campus': campus,
                }
            )
            self.learners.append(learner)
            
            # Create guardian for some learners
            if created and random.random() < 0.3:
                guardian_first = random.choice(first_names_male + first_names_female)
                Guardian.objects.create(
                    learner=learner,
                    relationship=random.choice(['PARENT', 'GUARDIAN', 'SPONSOR']),
                    first_name=guardian_first,
                    last_name=last_name,
                    email=f'{guardian_first.lower()}.{last_name.lower()}@email.co.za',
                    phone_mobile=f'08{random.randint(10000000, 99999999)}',
                    is_financially_responsible=True,
                )
        
        self.stdout.write(f'    Created {len(self.learners)} learners')

    def create_corporate_clients(self):
        """Create corporate clients"""
        from corporate.models import CorporateClient, CorporateContact
        
        self.stdout.write('  Creating corporate clients...')
        
        clients_data = [
            {'company_name': 'Eskom Holdings SOC Ltd', 'industry': 'Energy', 'employee_count': 42000, 'seta': 'EWSETA'},
            {'company_name': 'Sasol Limited', 'industry': 'Petrochemical', 'employee_count': 30000, 'seta': 'MERSETA'},
            {'company_name': 'ArcelorMittal South Africa', 'industry': 'Steel Manufacturing', 'employee_count': 8000, 'seta': 'MERSETA'},
            {'company_name': 'Transnet SOC Ltd', 'industry': 'Transport & Logistics', 'employee_count': 55000, 'seta': 'TETA'},
            {'company_name': 'Shoprite Holdings', 'industry': 'Retail', 'employee_count': 140000, 'seta': 'W&RSETA'},
            {'company_name': 'MTN South Africa', 'industry': 'Telecommunications', 'employee_count': 5000, 'seta': 'MICT'},
            {'company_name': 'Standard Bank Group', 'industry': 'Banking', 'employee_count': 50000, 'seta': 'BANKSETA'},
            {'company_name': 'Murray & Roberts', 'industry': 'Construction', 'employee_count': 12000, 'seta': 'CETA'},
            {'company_name': 'Pick n Pay Stores', 'industry': 'Retail', 'employee_count': 85000, 'seta': 'W&RSETA'},
            {'company_name': 'Vodacom Group', 'industry': 'Telecommunications', 'employee_count': 7500, 'seta': 'MICT'},
            {'company_name': 'WBHO Construction', 'industry': 'Construction', 'employee_count': 9000, 'seta': 'CETA'},
            {'company_name': 'Denel SOC Ltd', 'industry': 'Defence Manufacturing', 'employee_count': 4000, 'seta': 'MERSETA'},
        ]
        
        self.corporate_clients = []
        campus = list(self.campuses.values())[0]
        
        for client_data in clients_data:
            seta = self.setas.get(client_data.pop('seta'))
            client, created = CorporateClient.objects.get_or_create(
                company_name=client_data['company_name'],
                defaults={
                    **client_data,
                    'seta': seta,
                    'campus': campus,
                    'status': random.choice(['ACTIVE', 'ACTIVE', 'ACTIVE', 'PROSPECT']),
                    'client_tier': random.choice(['STRATEGIC', 'KEY', 'STANDARD']),
                    'phone': f'011{random.randint(1000000, 9999999)}',
                    'email': f'training@{client_data["company_name"].lower().replace(" ", "").replace("&", "")[:15]}.co.za',
                    'physical_address': f'{random.randint(1, 999)} Business Park, Sandton, Gauteng',
                    'is_host_employer': random.random() < 0.7,
                    'account_manager': self.users.get('corporate'),
                }
            )
            self.corporate_clients.append(client)
            
            # Create contacts
            if created:
                for j in range(random.randint(1, 3)):
                    CorporateContact.objects.create(
                        client=client,
                        first_name=random.choice(['John', 'Mary', 'Peter', 'Sarah', 'David']),
                        last_name=random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones']),
                        job_title=random.choice(['HR Manager', 'Training Coordinator', 'Skills Development Facilitator', 'HR Director']),
                        email=f'contact{j}@{client.company_name.lower().replace(" ", "")[:10]}.co.za',
                        phone=f'08{random.randint(10000000, 99999999)}',
                        is_primary=j == 0,
                    )
        
        self.stdout.write(f'    Created {len(clients_data)} corporate clients')

    def create_training_notifications(self):
        """Create Training Notifications (NOTs)"""
        from core.models import TrainingNotification, NOTIntake, NOTDeliverable
        
        self.stdout.write('  Creating Training Notifications (NOTs)...')
        
        today = date.today()
        
        self.nots = []
        for i, client in enumerate(self.corporate_clients[:8]):
            qual = list(self.qualifications.values())[i % len(self.qualifications)]
            campus_list = [c for c in self.campuses.values() if c.campus_type != 'HEAD_OFFICE']
            campus = campus_list[i % len(campus_list)]
            
            not_obj = TrainingNotification.objects.create(
                title=f'{qual.short_title} Training - {client.company_name}',
                corporate_client=client,
                qualification=qual,
                delivery_campus=campus,
                project_type=random.choice(['OC_APPRENTICESHIP', 'OC_LEARNERSHIP', 'SKILLS_PROGRAMME']),
                funder=random.choice(['PRIVATE', 'CORPORATE_DG', 'CORPORATE', 'GOVERNMENT']),
                contract_value=Decimal(random.randint(500000, 5000000)),
                expected_learner_count=random.randint(15, 50),
                planned_start_date=today + timedelta(days=random.randint(-30, 60)),
                planned_end_date=today + timedelta(days=random.randint(180, 540)),
                status=random.choice(['DRAFT', 'PLANNING', 'APPROVED', 'IN_PROGRESS']),
                description=f'Training programme for {client.company_name} in {qual.short_title}',
                client_name=client.company_name,
                priority=random.choice(['LOW', 'MEDIUM', 'HIGH']),
            )
            self.nots.append(not_obj)
            
            # Create intake phases
            for phase in range(1, random.randint(2, 4)):
                intake = NOTIntake.objects.create(
                    training_notification=not_obj,
                    intake_number=phase,
                    original_cohort_size=random.randint(10, 25),
                    intake_date=today + timedelta(days=30 * phase),
                    status='PLANNED' if phase > 1 else 'ACTIVE',
                )
            
            # Create deliverables
            deliverables = [
                ('Learner Enrollment List', 'REGISTRATION', 7),
                ('POE Collection - Month 1', 'SUBMISSION', 30),
                ('POE Collection - Month 3', 'SUBMISSION', 90),
                ('Formative Assessment Report', 'ASSESSMENT', 60),
                ('Summative Assessment Report', 'ASSESSMENT', 120),
                ('Tranche 1 Claim', 'PAYMENT', 45),
                ('Tranche 2 Claim', 'PAYMENT', 100),
                ('Completion Report', 'MILESTONE', 180),
            ]
            
            for title, del_type, offset in deliverables:
                NOTDeliverable.objects.create(
                    training_notification=not_obj,
                    title=title,
                    deliverable_type=del_type,
                    due_date=today + timedelta(days=offset),
                    status=random.choices(['PENDING', 'IN_PROGRESS', 'COMPLETED'], weights=[50, 30, 20])[0],
                )
        
        self.stdout.write(f'    Created {len(self.nots)} Training Notifications')

    def create_intakes(self):
        """Create intake buckets"""
        from intakes.models import Intake, IntakeEnrollment
        from finance.models import BursaryProvider
        
        self.stdout.write('  Creating intakes...')
        
        today = date.today()
        
        # Create bursary providers
        bursary_providers = [
            'NSFAS', 'Funza Lushaka', 'MERSETA Bursary Fund', 'EWSETA Bursary',
            'Sasol Foundation', 'Allan Gray Orbis Foundation'
        ]
        
        for i, provider_name in enumerate(bursary_providers):
            code = provider_name.upper().replace(' ', '_')[:15]
            BursaryProvider.objects.get_or_create(
                code=f'{code}_{i}',
                defaults={
                    'name': provider_name,
                    'provider_type': random.choice(['NSFAS', 'SETA', 'CORPORATE', 'FOUNDATION']),
                    'is_active': True
                }
            )
        
        self.intakes = []
        count = 0
        for campus_code, campus in self.campuses.items():
            if campus.campus_type == 'HEAD_OFFICE':
                continue
            
            for qual in list(self.qualifications.values())[:4]:
                # Create 2-3 intakes per qualification per campus
                for j in range(random.randint(2, 3)):
                    start_offset = random.randint(-60, 90)
                    intake, created = Intake.objects.get_or_create(
                        code=f'INT-{today.year}-{count:04d}',
                        defaults={
                            'name': f'{qual.short_title} Intake {j+1} - {campus.name}',
                            'description': f'Intake for {qual.title} at {campus.name}',
                            'qualification': qual,
                            'campus': campus,
                            'delivery_mode': random.choice(['ON_CAMPUS', 'BLENDED', 'WORKPLACE']),
                            'start_date': today + timedelta(days=start_offset),
                            'end_date': today + timedelta(days=start_offset + qual.minimum_duration_months * 30),
                            'enrollment_deadline': today + timedelta(days=start_offset - 14),
                            'max_capacity': random.randint(20, 35),
                            'min_viable': 10,
                            'status': random.choice(['PLANNED', 'RECRUITING', 'ENROLLMENT_OPEN', 'ACTIVE']),
                            'registration_fee': Decimal(random.randint(500, 2000)),
                            'tuition_fee': Decimal(random.randint(15000, 50000)),
                            'materials_fee': Decimal(random.randint(1000, 5000)),
                            'created_by': self.users.get('admin'),
                        }
                    )
                    self.intakes.append(intake)
                    count += 1
        
        self.stdout.write(f'    Created {count} intakes')

    def create_enrollments(self):
        """Create intake enrollments"""
        from intakes.models import Intake, IntakeEnrollment
        
        self.stdout.write('  Creating intake enrollments...')
        
        today = date.today()
        funding_types = ['SELF_FUNDED', 'PARENT_FUNDED', 'EMPLOYER_FUNDED', 'BURSARY', 'SETA_FUNDED']
        
        count = 0
        for intake in self.intakes:
            # Enroll random learners
            num_enrollments = random.randint(5, min(20, intake.max_capacity))
            available_learners = [l for l in self.learners if l.campus == intake.campus]
            
            if len(available_learners) < num_enrollments:
                available_learners = self.learners
            
            for learner in random.sample(available_learners, min(num_enrollments, len(available_learners))):
                if IntakeEnrollment.objects.filter(intake=intake, learner=learner).exists():
                    continue
                
                funding_type = random.choice(funding_types)
                IntakeEnrollment.objects.create(
                    intake=intake,
                    learner=learner,
                    funding_type=funding_type,
                    payment_method=random.choice(['FULL_UPFRONT', 'INSTALMENT', 'DEBIT_ORDER', 'CORPORATE_INVOICE', 'SETA_TRANCHE']),
                    status=random.choice(['APPLIED', 'ENROLLED', 'ACTIVE']),
                    registration_paid=random.random() < 0.7,
                    registration_paid_date=today - timedelta(days=random.randint(1, 30)) if random.random() < 0.7 else None,
                    created_by=self.users.get('admin'),
                )
                count += 1
        
        self.stdout.write(f'    Created {count} intake enrollments')

    def create_trade_test_data(self):
        """Create trade test applications and bookings"""
        from trade_tests.models import TradeTestCentre, Trade, TradeTestApplication
        
        self.stdout.write('  Creating trade test data...')
        
        today = date.today()
        
        # Create trade test centres
        centres_data = [
            {'name': 'Olifantsfontein Trade Test Centre', 'code': 'OLI', 'city': 'Olifantsfontein', 'province': 'GP', 'address': '123 Industrial Road'},
            {'name': 'Westlake Trade Test Centre', 'code': 'WES', 'city': 'Cape Town', 'province': 'WC', 'address': '456 Westlake Drive'},
            {'name': 'Durban Trade Test Centre', 'code': 'DUR', 'city': 'Durban', 'province': 'KZN', 'address': '789 Trade Street'},
            {'name': 'Pretoria Trade Test Centre', 'code': 'PTA', 'city': 'Pretoria', 'province': 'GP', 'address': '321 Skills Avenue'},
        ]
        
        self.centres = []
        for centre_data in centres_data:
            centre, _ = TradeTestCentre.objects.get_or_create(
                code=centre_data['code'],
                defaults={**centre_data, 'is_active': True}
            )
            self.centres.append(centre)
        
        # Create trades linked to qualifications
        trades_data = [
            {'name': 'Electrician', 'namb_code': 'E01'},
            {'name': 'Plumber', 'namb_code': 'P01'},
            {'name': 'Boilermaker', 'namb_code': 'B01'},
            {'name': 'Welder', 'namb_code': 'W01'},
            {'name': 'Fitter and Turner', 'namb_code': 'F01'},
            {'name': 'Millwright', 'namb_code': 'M01'},
        ]
        
        self.trades = []
        for trade_data in trades_data:
            trade, _ = Trade.objects.get_or_create(
                namb_code=trade_data['namb_code'],
                defaults={**trade_data, 'is_active': True}
            )
            self.trades.append(trade)
        
        # Create applications - get first campus
        campus = list(self.campuses.values())[0]
        
        count = 0
        for i in range(30):
            learner = random.choice(self.learners)
            trade = random.choice(self.trades)
            centre = random.choice(self.centres)
            
            try:
                app = TradeTestApplication.objects.create(
                    learner=learner,
                    trade=trade,
                    centre=centre,
                    candidate_source=random.choice(['INTERNAL', 'EXTERNAL', 'ARPL']),
                    status=random.choice(['DRAFT', 'SUBMITTED', 'DOCUMENTS_PENDING', 'READY_FOR_NAMB', 'SCHEDULED', 'COMPLETED']),
                    campus=campus,
                )
                count += 1
            except Exception as e:
                pass  # Skip duplicates
        
        self.stdout.write(f'    Created {count} trade test applications')

    def create_finance_data(self):
        """Create finance records - invoices"""
        from finance.models import Invoice, InvoiceLineItem
        
        self.stdout.write('  Creating finance data...')
        
        today = date.today()
        
        # Get a campus for context
        campus = list(self.campuses.values())[0]
        
        count = 0
        invoice_num = 1
        for client in self.corporate_clients[:6]:
            for i in range(random.randint(2, 5)):
                invoice_date = today - timedelta(days=random.randint(1, 180))
                due_date = invoice_date + timedelta(days=30)
                amount = Decimal(random.randint(10000, 500000))
                status = random.choice(['DRAFT', 'SENT', 'PAID', 'OVERDUE'])
                
                invoice, created = Invoice.objects.get_or_create(
                    invoice_number=f'INV-{today.year}-{invoice_num:05d}',
                    defaults={
                        'invoice_type': 'CORPORATE',
                        'corporate_client': client,
                        'invoice_date': invoice_date,
                        'due_date': due_date,
                        'billing_name': client.company_name,
                        'billing_address': client.physical_address or 'Address on file',
                        'subtotal': amount,
                        'vat_amount': amount * Decimal('0.15'),
                        'total': amount * Decimal('1.15'),
                        'amount_paid': amount * Decimal('1.15') if status == 'PAID' else Decimal('0'),
                        'status': status,
                        'campus': campus,
                    }
                )
                
                if created:
                    # Add line items
                    InvoiceLineItem.objects.create(
                        invoice=invoice,
                        description=f'Training services for {client.company_name}',
                        quantity=1,
                        unit_price=amount,
                    )
                
                invoice_num += 1
                count += 1
        
        self.stdout.write(f'    Created {count} invoices')
