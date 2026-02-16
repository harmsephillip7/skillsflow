"""
Generate Fake Data for Testing
Creates realistic test data for all major models in the SkillsFlow ERP
"""
import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

User = get_user_model()

# South African first names
SA_FIRST_NAMES_MALE = [
    'Thabo', 'Sipho', 'Johannes', 'Pieter', 'David', 'Michael', 'Bongani',
    'Lucky', 'Joseph', 'William', 'Siyabonga', 'Mandla', 'Jan', 'Andre',
    'Themba', 'Xolani', 'Musa', 'Nhlanhla', 'Sibusiso', 'Vusi', 'Gift',
    'Blessing', 'Thabang', 'Kagiso', 'Tumelo', 'Lethabo', 'Kabelo', 'Mpho'
]

SA_FIRST_NAMES_FEMALE = [
    'Nomvula', 'Zanele', 'Maria', 'Sarah', 'Elizabeth', 'Palesa', 'Thandi',
    'Lerato', 'Nomsa', 'Precious', 'Grace', 'Faith', 'Hope', 'Lindiwe',
    'Ntombi', 'Nokuthula', 'Sibongile', 'Thandiwe', 'Mpumi', 'Naledi',
    'Kelebogile', 'Boitumelo', 'Refilwe', 'Dineo', 'Puleng', 'Masego'
]

SA_SURNAMES = [
    'Nkosi', 'Dlamini', 'Van der Merwe', 'Botha', 'Ndlovu', 'Zulu', 'Sithole',
    'Mkhize', 'Ngcobo', 'Pillay', 'Govender', 'Naidoo', 'Mokoena', 'Molefe',
    'Mahlangu', 'Khumalo', 'Cele', 'Gumede', 'Mthembu', 'Zwane', 'Maseko',
    'Du Plessis', 'Van Niekerk', 'Pretorius', 'Venter', 'Jacobs', 'Williams',
    'Abrahams', 'Petersen', 'Adams', 'Ntuli', 'Radebe', 'Modise', 'Tau'
]

SA_CITIES = [
    ('Johannesburg', 'Gauteng', '2000', 'GP'),
    ('Pretoria', 'Gauteng', '0001', 'GP'),
    ('Cape Town', 'Western Cape', '8000', 'WC'),
    ('Durban', 'KwaZulu-Natal', '4000', 'KZN'),
    ('Port Elizabeth', 'Eastern Cape', '6001', 'EC'),
    ('Bloemfontein', 'Free State', '9301', 'FS'),
    ('East London', 'Eastern Cape', '5201', 'EC'),
    ('Polokwane', 'Limpopo', '0700', 'LP'),
    ('Nelspruit', 'Mpumalanga', '1200', 'MP'),
    ('Kimberley', 'Northern Cape', '8301', 'NC'),
    ('Rustenburg', 'North West', '0300', 'NW'),
    ('Pietermaritzburg', 'KwaZulu-Natal', '3200', 'KZN'),
    ('Sandton', 'Gauteng', '2196', 'GP'),
    ('Midrand', 'Gauteng', '1685', 'GP'),
    ('Centurion', 'Gauteng', '0157', 'GP'),
]

COMPANY_NAMES = [
    'Sasol', 'MTN Group', 'Vodacom', 'Standard Bank', 'FirstRand', 'Absa Group',
    'Shoprite', 'Pick n Pay', 'Woolworths', 'Clicks Group', 'Discovery',
    'Old Mutual', 'Sanlam', 'Nedbank', 'Capitec', 'Tiger Brands', 'Bidvest',
    'Imperial Holdings', 'Barloworld', 'Nampak', 'Sappi', 'Massmart',
    'Truworths', 'Mr Price', 'Foschini', 'Lewis Group', 'Steinhoff',
    'Aspen Pharmacare', 'Mediclinic', 'Netcare', 'Life Healthcare',
    'Tsogo Sun', 'Sun International', 'Famous Brands', 'Spur Corporation'
]

COMPANY_SUFFIXES = ['(Pty) Ltd', 'Holdings', 'Group', 'SA', 'Industries', 'Services']

INDUSTRIES = [
    'Mining', 'Financial Services', 'Retail', 'Healthcare', 'Telecommunications',
    'Manufacturing', 'Construction', 'Agriculture', 'Tourism', 'Education',
    'Information Technology', 'Energy', 'Transport & Logistics', 'Insurance'
]


def generate_sa_id(birth_date, gender):
    """Generate a valid South African ID number"""
    # YYMMDD
    date_part = birth_date.strftime('%y%m%d')
    
    # Gender digit (0-4 female, 5-9 male)
    gender_digit = random.randint(5, 9) if gender == 'M' else random.randint(0, 4)
    
    # Sequence number (3 digits)
    sequence = f"{random.randint(0, 999):03d}"
    
    # Citizenship (0 = SA citizen)
    citizen = '0'
    
    # Usually 8
    digit_8 = '8'
    
    # Calculate checksum using Luhn algorithm
    partial = f"{date_part}{gender_digit}{sequence}{citizen}{digit_8}"
    
    # Luhn checksum
    total = 0
    for i, digit in enumerate(partial):
        d = int(digit)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    
    checksum = (10 - (total % 10)) % 10
    
    return f"{partial}{checksum}"


def generate_learner_number():
    """Generate a unique learner number"""
    year = timezone.now().year
    sequence = random.randint(10000, 99999)
    return f"SKF{year}{sequence}"


def generate_enrollment_number():
    """Generate a unique enrollment number"""
    year = timezone.now().year
    sequence = random.randint(10000, 99999)
    return f"ENR{year}{sequence}"


class Command(BaseCommand):
    help = 'Generate fake data for testing the SkillsFlow ERP'

    def add_arguments(self, parser):
        parser.add_argument(
            '--learners',
            type=int,
            default=50,
            help='Number of learners to create (default: 50)'
        )
        parser.add_argument(
            '--corporates',
            type=int,
            default=15,
            help='Number of corporate clients to create (default: 15)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing test data before generating new data'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('🚀 Starting fake data generation...'))
        
        num_learners = options['learners']
        num_corporates = options['corporates']
        
        with transaction.atomic():
            if options['clear']:
                self.clear_data()
            
            # Create in order of dependencies
            self.create_setas()
            self.create_qualifications()
            self.create_modules()
            self.create_brands_and_campuses()
            self.create_corporate_clients(num_corporates)
            self.create_employers()
            self.create_facilitators()
            self.create_learners(num_learners)
            self.create_enrollments()
            self.create_assessment_activities()
            self.create_assessment_results()
            self.create_invoices()
            self.create_announcements()
            
        self.stdout.write(self.style.SUCCESS('✅ Fake data generation complete!'))

    def clear_data(self):
        """Clear existing test data"""
        self.stdout.write('🗑️  Clearing existing data...')
        
        from learners.models import Learner, Employer
        from academics.models import Enrollment
        from corporate.models import CorporateClient, CorporateContact
        from assessments.models import AssessmentResult, AssessmentActivity
        from finance.models import Invoice, Payment
        from portals.models import Announcement
        
        # Don't delete superusers
        User.objects.filter(is_superuser=False).delete()
        
        Learner.objects.all().delete()
        Enrollment.objects.all().delete()
        CorporateClient.objects.all().delete()
        CorporateContact.objects.all().delete()
        Employer.objects.all().delete()
        AssessmentResult.objects.all().delete()
        AssessmentActivity.objects.all().delete()
        Invoice.objects.all().delete()
        Payment.objects.all().delete()
        Announcement.objects.all().delete()
        
        self.stdout.write(self.style.WARNING('   Data cleared'))

    def create_setas(self):
        """Create SETAs"""
        from learners.models import SETA
        
        setas_data = [
            ('SERVICES', 'Services SETA', 'services@seta.org.za'),
            ('MICT', 'Media, Information and Communication Technologies SETA', 'info@mict.org.za'),
            ('BANKSETA', 'Banking SETA', 'info@bankseta.org.za'),
            ('INSETA', 'Insurance SETA', 'info@inseta.org.za'),
            ('HWSETA', 'Health and Welfare SETA', 'info@hwseta.org.za'),
            ('CETA', 'Construction Education and Training Authority', 'info@ceta.org.za'),
            ('MERSETA', 'Manufacturing, Engineering and Related Services SETA', 'info@merseta.org.za'),
            ('CHIETA', 'Chemical Industries Education and Training Authority', 'info@chieta.org.za'),
            ('ETDP', 'Education, Training and Development Practices SETA', 'info@etdpseta.org.za'),
            ('FASSET', 'Financial and Accounting Services SETA', 'info@fasset.org.za'),
        ]
        
        created = 0
        for code, name, email in setas_data:
            _, is_new = SETA.objects.get_or_create(
                code=code,
                defaults={'name': name, 'email': email}
            )
            if is_new:
                created += 1
        
        self.stdout.write(f'   📋 Created {created} SETAs')

    def create_qualifications(self):
        """Create sample qualifications"""
        from academics.models import Qualification
        from learners.models import SETA
        
        seta = SETA.objects.first()
        if not seta:
            return
        
        qualifications_data = [
            ('SAQA-12345', 'National Certificate: Business Administration Services', 'Business Admin NQF 4', 4, 120, 'NC', 12, 24),
            ('SAQA-23456', 'Further Education and Training Certificate: Generic Management', 'Generic Management NQF 4', 4, 140, 'NC', 12, 24),
            ('SAQA-34567', 'National Certificate: Contact Centre Support', 'Contact Centre NQF 2', 2, 120, 'NC', 6, 12),
            ('SAQA-45678', 'National Certificate: Information Technology: End User Computing', 'IT End User NQF 3', 3, 130, 'NC', 12, 18),
            ('SAQA-56789', 'Occupational Certificate: Financial Markets Practitioner', 'Financial Markets OC', 5, 200, 'OC', 24, 36),
            ('SAQA-67890', 'National Certificate: Wholesale and Retail Operations', 'Retail Operations NQF 3', 3, 120, 'NC', 12, 18),
            ('SAQA-78901', 'Further Education and Training Certificate: Project Management', 'Project Management NQF 4', 4, 140, 'NC', 12, 24),
            ('SAQA-89012', 'National Certificate: New Venture Creation', 'Entrepreneurship NQF 4', 4, 130, 'NC', 12, 24),
            ('SAQA-90123', 'National Certificate: Human Resources Management', 'HR Management NQF 4', 4, 140, 'NC', 12, 24),
            ('SAQA-01234', 'Occupational Certificate: Bookkeeper', 'Bookkeeper OC', 4, 180, 'OC', 18, 30),
        ]
        
        created = 0
        for saqa_id, title, short, nqf, credits, q_type, min_dur, max_dur in qualifications_data:
            _, is_new = Qualification.objects.get_or_create(
                saqa_id=saqa_id,
                defaults={
                    'title': title,
                    'short_title': short,
                    'nqf_level': nqf,
                    'credits': credits,
                    'qualification_type': q_type,
                    'seta': seta,
                    'minimum_duration_months': min_dur,
                    'maximum_duration_months': max_dur,
                    'registration_start': date(2020, 1, 1),
                    'registration_end': date(2027, 12, 31),
                    'last_enrollment_date': date(2026, 12, 31),
                    'is_active': True,
                }
            )
            if is_new:
                created += 1
        
        self.stdout.write(f'   📚 Created {created} qualifications')

    def create_modules(self):
        """Create modules for qualifications"""
        from academics.models import Qualification, Module
        
        module_types = ['K', 'P', 'W']  # Knowledge, Practical, Workplace
        
        created = 0
        for qual in Qualification.objects.all():
            for i in range(1, random.randint(5, 10)):
                mod_type = random.choice(module_types)
                _, is_new = Module.objects.get_or_create(
                    qualification=qual,
                    code=f"{qual.saqa_id[-5:]}-M{i:02d}",
                    defaults={
                        'title': f"Module {i}: {['Fundamentals', 'Principles', 'Application', 'Practice', 'Advanced'][random.randint(0, 4)]} of {qual.short_title}",
                        'module_type': mod_type,
                        'credits': random.randint(5, 20),
                        'notional_hours': random.randint(40, 120),
                        'sequence_order': i,
                        'is_compulsory': random.random() > 0.2,
                    }
                )
                if is_new:
                    created += 1
        
        self.stdout.write(f'   📖 Created {created} modules')

    def create_brands_and_campuses(self):
        """Create brands and campuses"""
        from tenants.models import Brand, Campus
        
        brands_data = [
            ('SKF', 'SkillsFlow Academy', 'primary'),
            ('SKF-CORP', 'SkillsFlow Corporate', 'corporate'),
            ('SKF-ONLINE', 'SkillsFlow Online', 'online'),
        ]
        
        created_brands = 0
        created_campuses = 0
        
        for code, name, brand_type in brands_data:
            brand, is_new = Brand.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'legal_name': f"{name} (Pty) Ltd",
                    'is_active': True,
                }
            )
            if is_new:
                created_brands += 1
            
            # Create campuses for this brand
            for city, province, postal_code, prov_code in random.sample(SA_CITIES, min(3, len(SA_CITIES))):
                _, campus_new = Campus.objects.get_or_create(
                    brand=brand,
                    name=f"{brand.name} - {city}",
                    defaults={
                        'code': f"{code}-{city[:3].upper()}",
                        'address_line1': f"{random.randint(1, 500)} {random.choice(['Main', 'Church', 'Voortrekker', 'Long', 'High'])} Street",
                        'address_line2': '',
                        'suburb': random.choice(['Central', 'CBD', 'Business Park', 'Industrial', 'North', 'South']),
                        'city': city,
                        'province': province,
                        'postal_code': postal_code,
                        'phone': f"+27{random.randint(10, 89)}{random.randint(1000000, 9999999)}",
                        'email': f"{city.lower().replace(' ', '')}@skillsflow.co.za",
                        'is_active': True,
                    }
                )
                if campus_new:
                    created_campuses += 1
        
        self.stdout.write(f'   🏢 Created {created_brands} brands, {created_campuses} campuses')

    def create_corporate_clients(self, count):
        """Create corporate clients"""
        from corporate.models import CorporateClient, CorporateContact
        from learners.models import SETA
        from tenants.models import Campus
        
        seta = SETA.objects.first()
        campus = Campus.objects.first()
        created_clients = 0
        created_contacts = 0
        
        companies_used = random.sample(COMPANY_NAMES, min(count, len(COMPANY_NAMES)))
        
        for company in companies_used:
            city, province, postal_code, prov_code = random.choice(SA_CITIES)
            suffix = random.choice(COMPANY_SUFFIXES)
            
            client, is_new = CorporateClient.objects.get_or_create(
                company_name=f"{company} {suffix}",
                defaults={
                    'campus': campus,
                    'trading_name': company,
                    'registration_number': f"{random.randint(1990, 2023)}/{random.randint(100000, 999999)}/07",
                    'vat_number': f"4{random.randint(100000000, 999999999)}",
                    'phone': f"+27{random.randint(10, 89)}{random.randint(1000000, 9999999)}",
                    'email': f"info@{company.lower().replace(' ', '')}.co.za",
                    'physical_address': f"{random.randint(1, 500)} {random.choice(['Main', 'Corporate', 'Business'])} Road, {city}, {province}, {postal_code}",
                    'industry': random.choice(INDUSTRIES),
                    'seta': seta,
                    'employee_count': random.randint(50, 5000),
                    'status': random.choice(['ACTIVE', 'ACTIVE', 'ACTIVE', 'PROSPECT']),
                    'contract_start_date': date.today() - timedelta(days=random.randint(30, 730)),
                    'contract_end_date': date.today() + timedelta(days=random.randint(180, 1095)),
                }
            )
            if is_new:
                created_clients += 1
            
            # Create 1-3 contacts per client
            for _ in range(random.randint(1, 3)):
                gender = random.choice(['M', 'F'])
                first_name = random.choice(SA_FIRST_NAMES_MALE if gender == 'M' else SA_FIRST_NAMES_FEMALE)
                last_name = random.choice(SA_SURNAMES)
                
                _, contact_new = CorporateContact.objects.get_or_create(
                    client=client,
                    email=f"{first_name.lower()}.{last_name.lower().replace(' ', '')}@{company.lower().replace(' ', '')}.co.za",
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'phone': f"+27{random.randint(60, 89)}{random.randint(1000000, 9999999)}",
                        'role': random.choice(['HR', 'TRAINING', 'SDF', 'FINANCE', 'EXECUTIVE']),
                        'is_primary': True,
                    }
                )
                if contact_new:
                    created_contacts += 1
        
        self.stdout.write(f'   🏭 Created {created_clients} corporate clients, {created_contacts} contacts')

    def create_employers(self):
        """Create host employers"""
        from learners.models import Employer, SETA, Address
        
        seta = SETA.objects.first()
        created = 0
        
        for _ in range(10):
            company = random.choice(COMPANY_NAMES)
            city, province, postal_code, prov_code = random.choice(SA_CITIES)
            
            first_name = random.choice(SA_FIRST_NAMES_MALE + SA_FIRST_NAMES_FEMALE)
            last_name = random.choice(SA_SURNAMES)
            
            # Create address for employer
            employer_address = Address.objects.create(
                line_1=f"{random.randint(1, 500)} Industrial Road",
                line_2=random.choice(['', 'Block A', 'Unit 1', '']),
                suburb=random.choice(['Industrial Area', 'Business Park', 'Commercial Zone']),
                city=city,
                province=province,
                postal_code=postal_code,
            )
            
            _, is_new = Employer.objects.get_or_create(
                name=f"{company} - {city}",
                defaults={
                    'trading_name': company,
                    'registration_number': f"{random.randint(1990, 2023)}/{random.randint(100000, 999999)}/07",
                    'vat_number': f"4{random.randint(100000000, 999999999)}",
                    'sdl_number': f"L{random.randint(10000000, 99999999)}",
                    'seta': seta,
                    'contact_person': f"{first_name} {last_name}",
                    'contact_email': f"{first_name.lower()}.{last_name.lower().replace(' ', '')}@{company.lower().replace(' ', '')}.co.za",
                    'contact_phone': f"+27{random.randint(60, 89)}{random.randint(1000000, 9999999)}",
                    'address': employer_address,
                    'workplace_approved': random.random() > 0.2,
                    'is_active': True,
                }
            )
            if is_new:
                created += 1
        
        self.stdout.write(f'   🏗️  Created {created} host employers')

    def create_facilitators(self):
        """Create facilitators and assessors"""
        from core.models import UserRole, Role
        
        facilitator_role, _ = Role.objects.get_or_create(
            code='FACILITATOR',
            defaults={'name': 'Facilitator', 'description': 'Delivers training'}
        )
        assessor_role, _ = Role.objects.get_or_create(
            code='ASSESSOR',
            defaults={'name': 'Assessor', 'description': 'Conducts assessments'}
        )
        
        created = 0
        for i in range(8):
            gender = random.choice(['M', 'F'])
            first_name = random.choice(SA_FIRST_NAMES_MALE if gender == 'M' else SA_FIRST_NAMES_FEMALE)
            last_name = random.choice(SA_SURNAMES)
            email = f"facilitator{i+1}@skillsflow.co.za"
            
            user, user_new = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_staff': True,
                    'is_active': True,
                }
            )
            if user_new:
                user.set_password('facilitator123')
                user.save()
                created += 1
            
            # Assign role
            UserRole.objects.get_or_create(
                user=user,
                role=random.choice([facilitator_role, assessor_role]),
                defaults={
                    'valid_from': date.today() - timedelta(days=365),
                    'is_active': True,
                }
            )
        
        self.stdout.write(f'   👨‍🏫 Created {created} facilitators/assessors')

    def create_learners(self, count):
        """Create learners"""
        from learners.models import Learner, Address
        from tenants.models import Campus
        
        campus = Campus.objects.first()
        created = 0
        
        for i in range(count):
            gender = random.choice(['M', 'F'])
            first_name = random.choice(SA_FIRST_NAMES_MALE if gender == 'M' else SA_FIRST_NAMES_FEMALE)
            last_name = random.choice(SA_SURNAMES)
            
            # Generate birth date (18-45 years old)
            birth_date = date.today() - timedelta(days=random.randint(18*365, 45*365))
            id_number = generate_sa_id(birth_date, gender)
            
            email = f"{first_name.lower()}.{last_name.lower().replace(' ', '')}.{i}@email.co.za"
            learner_number = generate_learner_number()
            
            # Create user
            user, user_new = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_active': True,
                }
            )
            if user_new:
                user.set_password('learner123')
                user.save()
            
            city, province, postal_code, prov_code = random.choice(SA_CITIES)
            
            # Create address
            address = Address.objects.create(
                line_1=f"{random.randint(1, 999)} {random.choice(['Main', 'Church', 'Station', 'Park', 'Oak'])} Street",
                line_2=random.choice(['', 'Unit 1', 'Flat 2', '']),
                suburb=random.choice(['Central', 'North', 'South', 'East', 'West', 'Suburb', 'Township', 'Extension']),
                city=city,
                province=province,
                postal_code=postal_code,
            )
            
            # Map population group based on surname patterns
            population_groups = ['A', 'A', 'A', 'A', 'C', 'I', 'W']  # Weighted towards African
            
            _, learner_new = Learner.objects.get_or_create(
                sa_id_number=id_number,
                defaults={
                    'user': user,
                    'learner_number': learner_number,
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'phone_mobile': f"+27{random.randint(60, 89)}{random.randint(1000000, 9999999)}",
                    'date_of_birth': birth_date,
                    'gender': gender,
                    'population_group': random.choice(population_groups),
                    'citizenship': 'SA',
                    'home_language': random.choice(['English', 'isiZulu', 'isiXhosa', 'Afrikaans', 'Sesotho', 'Setswana']),
                    'disability_status': 'N' if random.random() > 0.05 else random.choice(['1', '2', '3', '4']),
                    'socio_economic_status': random.choice(['E', 'U', 'S', 'N']),
                    'highest_qualification': random.choice(['4', '5', '6', '7']),  # NQF levels
                    'physical_address': address,
                    'province_code': prov_code,
                    'popia_consent_given': True,
                    'popia_consent_date': timezone.now() - timedelta(days=random.randint(1, 365)),
                    'campus': campus,
                }
            )
            if learner_new:
                created += 1
        
        self.stdout.write(f'   👨‍🎓 Created {created} learners')

    def create_enrollments(self):
        """Create enrollments"""
        from academics.models import Enrollment, Qualification
        from learners.models import Learner
        from tenants.models import Campus
        
        learners = list(Learner.objects.all())
        qualifications = list(Qualification.objects.all())
        campus = Campus.objects.first()
        
        if not learners or not qualifications:
            return
        
        created = 0
        for learner in learners:
            # Each learner gets 1-2 enrollments
            for _ in range(random.randint(1, 2)):
                qual = random.choice(qualifications)
                
                start_date = date.today() - timedelta(days=random.randint(30, 365))
                enrollment_date = start_date - timedelta(days=random.randint(7, 30))
                expected_completion = start_date + timedelta(days=qual.minimum_duration_months * 30)
                
                # Determine status based on expected completion
                if expected_completion < date.today():
                    status = random.choice(['COMPLETED', 'COMPLETED', 'CERTIFIED', 'WITHDRAWN'])
                    actual_completion = expected_completion if status in ['COMPLETED', 'CERTIFIED'] else None
                else:
                    status = random.choice(['ACTIVE', 'ACTIVE', 'ACTIVE', 'ENROLLED', 'ON_HOLD'])
                    actual_completion = None
                
                enrollment_number = generate_enrollment_number()
                
                _, is_new = Enrollment.objects.get_or_create(
                    learner=learner,
                    qualification=qual,
                    defaults={
                        'campus': campus,
                        'enrollment_number': enrollment_number,
                        'application_date': enrollment_date - timedelta(days=random.randint(1, 14)),
                        'enrollment_date': enrollment_date,
                        'start_date': start_date,
                        'expected_completion': expected_completion,
                        'actual_completion': actual_completion,
                        'status': status,
                        'funding_type': random.choice(['SELF', 'EMPLOYER', 'BURSARY', 'LEARNERSHIP', 'SKILLS_PROG']),
                        'agreement_signed': True,
                        'agreement_date': enrollment_date,
                    }
                )
                if is_new:
                    created += 1
        
        self.stdout.write(f'   📝 Created {created} enrollments')

    def create_assessment_activities(self):
        """Create assessment activities"""
        from assessments.models import AssessmentActivity
        from academics.models import Module
        
        modules = list(Module.objects.all()[:20])
        
        created = 0
        for module in modules:
            for activity_num in range(1, random.randint(2, 4)):
                activity_type = random.choice(['FORMATIVE', 'SUMMATIVE', 'IISA', 'ICASS', 'EISA', 'POE'])
                
                _, is_new = AssessmentActivity.objects.get_or_create(
                    module=module,
                    code=f"{module.code}-A{activity_num:02d}",
                    defaults={
                        'title': f"{activity_type.title()} Assessment {activity_num} - {module.title[:30]}",
                        'activity_type': activity_type,
                        'weight': Decimal(str(random.randint(20, 50))),
                        'max_attempts': 3,
                        'sequence_order': activity_num,
                        'is_active': True,
                    }
                )
                if is_new:
                    created += 1
        
        self.stdout.write(f'   📋 Created {created} assessment activities')

    def create_assessment_results(self):
        """Create assessment results"""
        from assessments.models import AssessmentResult, AssessmentActivity
        from academics.models import Enrollment
        from core.models import Role, UserRole
        
        enrollments = list(Enrollment.objects.filter(status__in=['ACTIVE', 'COMPLETED', 'CERTIFIED'])[:30])
        
        # Get assessors (facilitators/assessors created earlier)
        assessor_role = Role.objects.filter(code__in=['ASSESSOR', 'FACILITATOR']).first()
        assessors = []
        if assessor_role:
            assessor_user_roles = UserRole.objects.filter(role=assessor_role, is_active=True)
            assessors = [ur.user for ur in assessor_user_roles]
        
        # If no assessors found, get any staff users
        if not assessors:
            assessors = list(User.objects.filter(is_staff=True)[:5])
        
        if not assessors:
            self.stdout.write(self.style.WARNING('   ⚠️  No assessors found, skipping assessment results'))
            return
        
        created = 0
        for enrollment in enrollments:
            # Get activities for this enrollment's qualification
            activities = list(AssessmentActivity.objects.filter(
                module__qualification=enrollment.qualification
            )[:5])
            
            for activity in activities:
                assessment_date = enrollment.start_date + timedelta(days=random.randint(30, 180))
                
                # Determine result - always use valid choices (C, NYC, ABS, DEF)
                result = random.choices(
                    ['C', 'NYC', 'ABS'],
                    weights=[70, 25, 5]
                )[0]
                
                # Status based on result
                status = 'MODERATED' if result == 'C' else 'PENDING_MOD'
                
                _, is_new = AssessmentResult.objects.get_or_create(
                    enrollment=enrollment,
                    activity=activity,
                    defaults={
                        'attempt_number': random.randint(1, 2),
                        'assessor': random.choice(assessors),
                        'result': result,
                        'percentage_score': Decimal(str(random.randint(50, 95))) if result == 'C' else Decimal(str(random.randint(30, 49))) if result == 'NYC' else None,
                        'assessment_date': assessment_date,
                        'feedback': 'Good effort, keep up the work.' if result == 'C' else 'Additional support required.' if result == 'NYC' else 'Learner was absent.',
                        'status': status,
                    }
                )
                if is_new:
                    created += 1
        
        self.stdout.write(f'   ✅ Created {created} assessment results')

    def create_invoices(self):
        """Create invoices and payments"""
        from finance.models import Invoice, InvoiceLineItem, Payment
        from academics.models import Enrollment
        from tenants.models import Campus
        
        enrollments = list(Enrollment.objects.select_related('learner', 'qualification')[:20])
        campus = Campus.objects.first()
        
        created_invoices = 0
        created_payments = 0
        
        for enrollment in enrollments:
            invoice_date = enrollment.enrollment_date + timedelta(days=random.randint(1, 14))
            due_date = invoice_date + timedelta(days=30)
            
            # Determine billing info
            billing_name = f"{enrollment.learner.first_name} {enrollment.learner.last_name}"
            billing_email = enrollment.learner.email
            
            invoice_number = f"INV-{timezone.now().year}-{random.randint(10000, 99999)}"
            
            invoice, is_new = Invoice.objects.get_or_create(
                enrollment=enrollment,
                defaults={
                    'campus': campus,
                    'invoice_number': invoice_number,
                    'invoice_type': 'TUITION',
                    'learner': enrollment.learner,
                    'invoice_date': invoice_date,
                    'due_date': due_date,
                    'billing_name': billing_name,
                    'billing_email': billing_email,
                    'subtotal': Decimal('0'),
                    'vat_amount': Decimal('0'),
                    'total': Decimal('0'),
                    'amount_paid': Decimal('0'),
                    'status': 'DRAFT',
                }
            )
            
            if is_new:
                # Add invoice line
                unit_price = Decimal(str(random.randint(8000, 25000)))
                vat = unit_price * Decimal('0.15')
                total = unit_price + vat
                
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    description=f"Tuition: {enrollment.qualification.short_title}",
                    quantity=1,
                    unit_price=unit_price,
                    qualification=enrollment.qualification,
                )
                
                invoice.subtotal = unit_price
                invoice.vat_amount = vat
                invoice.total = total
                invoice.status = random.choice(['SENT', 'SENT', 'PAID', 'OVERDUE'])
                invoice.save()
                
                created_invoices += 1
                
                # Maybe create a payment
                if invoice.status in ['PAID', 'SENT'] and random.random() > 0.3:
                    payment_amount = total if invoice.status == 'PAID' else total * Decimal(str(random.uniform(0.3, 0.8)))
                    
                    Payment.objects.create(
                        campus=campus,
                        invoice=invoice,
                        payment_reference=f"PAY-{random.randint(100000, 999999)}",
                        amount=payment_amount,
                        payment_date=invoice_date + timedelta(days=random.randint(5, 30)),
                        payment_method=random.choice(['EFT', 'CARD', 'CASH']),
                        status='COMPLETED',
                    )
                    
                    invoice.amount_paid = payment_amount
                    if payment_amount >= total:
                        invoice.status = 'PAID'
                    invoice.save()
                    
                    created_payments += 1
        
        self.stdout.write(f'   💰 Created {created_invoices} invoices, {created_payments} payments')

    def create_announcements(self):
        """Create portal announcements"""
        from portals.models import Announcement
        from tenants.models import Brand
        
        brand = Brand.objects.first()
        
        announcements_data = [
            ('Welcome to SkillsFlow!', 'We are excited to have you on our learning platform. Start exploring your courses today.', 'ALL', 'NORMAL'),
            ('Assessment Week Coming Up', 'Reminder: Assessment week starts next Monday. Please ensure all POEs are submitted.', 'LEARNER', 'HIGH'),
            ('New Qualification Available', 'We have added a new NQF Level 5 qualification in Project Management. Enquire now!', 'CORPORATE', 'NORMAL'),
            ('System Maintenance', 'The platform will be undergoing maintenance this Saturday from 2 AM to 6 AM.', 'ALL', 'HIGH'),
            ('Facilitator Training', 'Mandatory facilitator training scheduled for Friday. Please confirm attendance.', 'STAFF', 'HIGH'),
            ('SETA Submission Deadline', 'Reminder: SETA quarterly submissions are due by end of month.', 'STAFF', 'URGENT'),
            ('Holiday Schedule', 'The office will be closed for the upcoming public holidays. Online support remains available.', 'ALL', 'NORMAL'),
            ('Certificate Collection', 'Certificates from the previous intake are ready for collection at your campus.', 'LEARNER', 'NORMAL'),
        ]
        
        created = 0
        for title, content, audience, priority in announcements_data:
            _, is_new = Announcement.objects.get_or_create(
                title=title,
                defaults={
                    'brand': brand,
                    'content': content,
                    'audience': audience,
                    'priority': priority,
                    'is_published': True,
                    'publish_at': timezone.now() - timedelta(days=random.randint(0, 30)),
                    'expire_at': timezone.now() + timedelta(days=random.randint(30, 90)),
                }
            )
            if is_new:
                created += 1
        
        self.stdout.write(f'   📢 Created {created} announcements')
