"""
Generate fake campus, venue, and grant project data
"""
import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models.signals import post_save
from tenants.models import Brand, Campus
from logistics.models import Venue, Cohort
from corporate.models import CorporateClient, GrantProject
from academics.models import Qualification, Enrollment
from learners.models import SETA
from core.models import User


class Command(BaseCommand):
    help = 'Generate campuses, venues, and grant projects data'
    
    # South African provinces and cities
    LOCATIONS = [
        {'city': 'Johannesburg', 'province': 'Gauteng', 'region': 'Gauteng'},
        {'city': 'Pretoria', 'province': 'Gauteng', 'region': 'Gauteng'},
        {'city': 'Cape Town', 'province': 'Western Cape', 'region': 'Western Cape'},
        {'city': 'Durban', 'province': 'KwaZulu-Natal', 'region': 'KwaZulu-Natal'},
        {'city': 'Port Elizabeth', 'province': 'Eastern Cape', 'region': 'Eastern Cape'},
        {'city': 'Bloemfontein', 'province': 'Free State', 'region': 'Free State'},
        {'city': 'East London', 'province': 'Eastern Cape', 'region': 'Eastern Cape'},
        {'city': 'Polokwane', 'province': 'Limpopo', 'region': 'Limpopo'},
        {'city': 'Nelspruit', 'province': 'Mpumalanga', 'region': 'Mpumalanga'},
        {'city': 'Kimberley', 'province': 'Northern Cape', 'region': 'Northern Cape'},
        {'city': 'Rustenburg', 'province': 'North West', 'region': 'North West'},
        {'city': 'Pietermaritzburg', 'province': 'KwaZulu-Natal', 'region': 'KwaZulu-Natal'},
        {'city': 'Sandton', 'province': 'Gauteng', 'region': 'Gauteng'},
        {'city': 'Midrand', 'province': 'Gauteng', 'region': 'Gauteng'},
        {'city': 'Centurion', 'province': 'Gauteng', 'region': 'Gauteng'},
    ]
    
    VENUE_TYPES = ['CLASSROOM', 'LAB', 'WORKSHOP', 'BOARDROOM']
    
    def handle(self, *args, **options):
        self.stdout.write('Creating brand and campuses...')
        
        # Create brand if not exists
        brand, created = Brand.objects.get_or_create(
            code='SF',
            defaults={
                'name': 'SkillsFlow Academy',
                'legal_name': 'SkillsFlow Training (Pty) Ltd',
                'accreditation_number': 'ACC-2024-001',
                'email': 'info@skillsflow.co.za',
                'phone': '+27 11 123 4567',
                'website': 'https://skillsflow.co.za',
                'primary_color': '#2563eb',
                'secondary_color': '#64748b',
            }
        )
        if created:
            self.stdout.write(f'  Created brand: {brand.name}')
        
        # Create campuses
        campuses = []
        for idx, loc in enumerate(self.LOCATIONS):
            campus_code = f"{loc['city'][:3].upper()}{idx+1:02d}"
            campus, created = Campus.objects.get_or_create(
                code=campus_code,
                defaults={
                    'brand': brand,
                    'name': f"{loc['city']} Campus",
                    'campus_type': 'HEAD_OFFICE' if idx == 0 else 'CAMPUS',
                    'region': loc['region'],
                    'city': loc['city'],
                    'province': loc['province'],
                    'country': 'South Africa',
                    'email': f"{loc['city'].lower()}@skillsflow.co.za",
                    'phone': f"+27 {random.randint(10,99)} {random.randint(100,999)} {random.randint(1000,9999)}",
                    'is_active': True,
                }
            )
            campuses.append(campus)
            if created:
                self.stdout.write(f'  Created campus: {campus.name}')
        
        self.stdout.write(f'\nTotal campuses: {len(campuses)}')
        
        # Create venues for each campus
        self.stdout.write('\nCreating venues...')
        venue_count = 0
        admin_user = User.objects.filter(is_superuser=True).first()
        
        for campus in campuses:
            # Create 3-6 venues per campus
            num_venues = random.randint(3, 6)
            for v in range(num_venues):
                venue_type = random.choice(self.VENUE_TYPES)
                capacity = random.choice([20, 25, 30, 35, 40, 50])
                venue_name = f"{venue_type.title().replace('_', ' ')} {v+1}"
                venue_code = f"{campus.code}-{venue_type[:2]}{v+1:02d}"
                
                venue, created = Venue.objects.get_or_create(
                    campus=campus,
                    code=venue_code,
                    defaults={
                        'name': venue_name,
                        'venue_type': venue_type,
                        'capacity': capacity,
                        'equipment': ['Projector', 'Whiteboard', 'WiFi'],
                        'is_active': True,
                        'created_by': admin_user,
                        'updated_by': admin_user,
                    }
                )
                if created:
                    venue_count += 1
        
        self.stdout.write(f'Created {venue_count} venues')
        
        # Create Grant Projects - disconnect signals temporarily
        self.stdout.write('\nCreating grant projects...')
        project_count = 0
        
        # Disconnect signals temporarily to avoid task creation
        try:
            from core.task_signals import create_grant_tasks
            post_save.disconnect(create_grant_tasks, sender=GrantProject)
        except:
            pass
        
        clients = list(CorporateClient.objects.all())
        qualifications = list(Qualification.objects.all())
        
        # Get or create SETAs
        setas = list(SETA.objects.all())
        if not setas:
            seta_data = [
                ('MICT', 'Media, Information and Communication Technologies SETA'),
                ('SERVICES', 'Services SETA'),
                ('BANKSETA', 'Banking Sector Education and Training Authority'),
                ('INSETA', 'Insurance Sector Education and Training Authority'),
                ('ETDP', 'Education, Training and Development Practices SETA'),
            ]
            for code, name in seta_data:
                seta, _ = SETA.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'is_active': True}
                )
                setas.append(seta)
        
        if clients and setas:
            project_statuses = ['APPLIED', 'APPROVED', 'ACTIVE', 'COMPLETED', 'CONTRACTED']
            
            for i in range(15):
                client = random.choice(clients)
                seta = random.choice(setas)
                status = random.choice(project_statuses)
                
                # Dates
                start_date = date.today() - timedelta(days=random.randint(0, 365))
                end_date = start_date + timedelta(days=random.randint(180, 365))
                application_date = start_date - timedelta(days=random.randint(30, 90))
                approval_date = application_date + timedelta(days=random.randint(14, 45)) if status != 'APPLIED' else None
                
                # Amounts
                approved_amount = Decimal(random.randint(200000, 2000000))
                claimed_amount = approved_amount * Decimal(random.uniform(0.3, 0.9)) if status in ['ACTIVE', 'COMPLETED'] else Decimal(0)
                received_amount = claimed_amount * Decimal(random.uniform(0.5, 1.0)) if status in ['ACTIVE', 'COMPLETED'] else Decimal(0)
                
                # Learner targets
                target_learners = random.randint(20, 100)
                enrolled_learners = int(target_learners * random.uniform(0.7, 1.0)) if status in ['ACTIVE', 'COMPLETED'] else 0
                completed_learners = int(enrolled_learners * random.uniform(0.5, 0.9)) if status == 'COMPLETED' else 0
                
                project, created = GrantProject.objects.get_or_create(
                    project_number=f'GP-{date.today().year}-{i+1:04d}',
                    defaults={
                        'project_name': f"{client.company_name} Skills Development {i+1}",
                        'client': client,
                        'seta': seta,
                        'status': status,
                        'application_date': application_date,
                        'approval_date': approval_date,
                        'start_date': start_date if status != 'APPLIED' else None,
                        'end_date': end_date if status != 'APPLIED' else None,
                        'approved_amount': approved_amount if status != 'APPLIED' else None,
                        'claimed_amount': claimed_amount,
                        'received_amount': received_amount,
                        'target_learners': target_learners,
                        'enrolled_learners': enrolled_learners,
                        'completed_learners': completed_learners,
                        'campus': random.choice(campuses),
                    }
                )
                if created:
                    project_count += 1
        
        self.stdout.write(f'Created {project_count} grant projects')
        
        # Update cohorts to link to campuses
        self.stdout.write('\nUpdating cohorts with campus data...')
        cohorts = Cohort.objects.all()
        for cohort in cohorts:
            if not hasattr(cohort, 'campus') or not cohort.campus:
                cohort.campus = random.choice(campuses)
                cohort.save()
        
        self.stdout.write(self.style.SUCCESS('\n✓ Fake data generation complete!'))
        self.stdout.write(f'  - {Campus.objects.count()} Campuses')
        self.stdout.write(f'  - {Venue.objects.count()} Venues')
        self.stdout.write(f'  - {GrantProject.objects.count()} Grant Projects')
