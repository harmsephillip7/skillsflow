"""
Management command to create test CRM leads (potential learners).
Creates realistic South African learner data across different pipelines and stages.
"""
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from crm.models import Lead, LeadSource, Pipeline, PipelineStage, LeadActivity
from tenants.models import Campus
from academics.models import Qualification
from core.models import User


# South African names for realistic data
FIRST_NAMES_MALE = [
    'Sipho', 'Bongani', 'Mpho', 'Kagiso', 'Themba', 'Siyabonga', 'Thabiso', 'Mandla',
    'Sibusiso', 'Vusi', 'Musa', 'Nkosinathi', 'Dumisani', 'Lwazi', 'Thabo', 'Tshepo',
    'Johannes', 'Pieter', 'Willem', 'Johann', 'Andries', 'Hennie', 'Gerhard', 'Francois',
    'Mohamed', 'Ahmed', 'Imran', 'Yusuf', 'Rajan', 'Vikram', 'Sanjay', 'Pravin',
]

FIRST_NAMES_FEMALE = [
    'Thandi', 'Nomvula', 'Lerato', 'Zanele', 'Palesa', 'Nokuthula', 'Lindiwe',
    'Nompumelelo', 'Ayanda', 'Nonhlanhla', 'Precious', 'Thandiwe', 'Ntombi', 'Buhle', 
    'Zinhle', 'Nomsa', 'Nandi', 'Mbali', 'Khethiwe', 'Nosipho', 'Thobile', 'Sindisiwe',
    'Maria', 'Annika', 'Chantelle', 'Liezel', 'Michelle', 'Natasha', 'Samantha', 'Karen',
    'Fatima', 'Ayesha', 'Zarina', 'Priya', 'Sunita', 'Kavitha', 'Deepa', 'Rekha',
]

LAST_NAMES = [
    'Nkosi', 'Dlamini', 'Ndlovu', 'Mthembu', 'Khumalo', 'Zulu', 'Ngcobo', 'Sithole',
    'Cele', 'Mkhize', 'Zungu', 'Molefe', 'Mokoena', 'Maseko', 'Tshabalala', 'Mahlangu',
    'Mabena', 'Shabangu', 'Motaung', 'Radebe', 'Langa', 'Buthelezi', 'Gumede', 'Ntuli',
    'Zwane', 'Sibiya', 'Ngubane', 'Mhlongo', 'Mazibuko', 'Phiri', 'Banda', 'Moyo',
    'van der Merwe', 'Botha', 'Pretorius', 'Joubert', 'Venter', 'du Plessis', 'Steyn',
    'Swanepoel', 'van Wyk', 'Coetzee', 'Kruger', 'Meyer', 'Nel', 'Olivier', 'Fourie',
    'Khan', 'Patel', 'Naidoo', 'Pillay', 'Govender', 'Maharaj', 'Singh', 'Reddy',
]

SCHOOL_NAMES = [
    'Parktown Boys High School', 'Pretoria Boys High School', 'King Edward VII School',
    'Jeppe High School for Boys', 'Northcliff High School', 'Hyde Park High School',
    'Crawford College Sandton', 'St Johns College', 'Roedean School',
    'Kingsmead College', 'St Marys School', 'Parktown Girls High School',
    'Brebner High School', 'Hoerskool Monument', 'Hoerskool Waterkloof',
    'Tshwane Muslim School', 'Pretoria Islamic Academy', 'Laudium Secondary School',
    'Soweto High Schools', 'Orlando West Secondary', 'Morris Isaacson High School',
    'Pace Commercial College', 'Damelin College', 'Boston City Campus',
]

EMPLOYERS = [
    'Sasol', 'Anglo American', 'Eskom', 'Transnet', 'SAB Miller', 'Vodacom', 'MTN',
    'Standard Bank', 'ABSA', 'First National Bank', 'Nedbank', 'Discovery',
    'Pick n Pay', 'Shoprite', 'Woolworths', 'Massmart', 'Tiger Brands',
    'Siemens', 'General Electric', 'ArcelorMittal', 'Sappi', 'Mondi',
    'Clicks', 'Dis-Chem', 'Mediclinic', 'Netcare', 'Life Healthcare',
    'Johannesburg Metro', 'City of Tshwane', 'eThekwini Municipality',
    'Department of Education', 'Department of Health', 'SAPS',
    'Unemployed', 'Self-employed', 'Student',
]

PHONE_PREFIXES = ['060', '061', '062', '063', '064', '065', '066', '067', '068', '069',
                  '071', '072', '073', '074', '076', '078', '079', '081', '082', '083', '084']

ACTIVITY_NOTES = [
    "Initial contact made. Very interested in the programme.",
    "Sent programme brochure and pricing information via email.",
    "Follow-up call scheduled. Learner requested WhatsApp communication.",
    "Discussed payment options. Prefers monthly installment plan.",
    "Requested more information about practical components.",
    "Confirmed interest. Wants to start as soon as possible.",
    "Left voicemail. Will try again tomorrow morning.",
    "WhatsApp chat - answered questions about class schedule and venue.",
    "Meeting scheduled at campus for consultation next week.",
    "Sent formal quotation via email. Awaiting response.",
    "Called back - very interested, needs to discuss with family first.",
    "Submitted online interest form, following up.",
    "Requested call back after work hours (after 5pm).",
    "Confirmed attendance for upcoming open day event.",
    "Discussed employer sponsorship options.",
    "Enquired about NSFAS/bursary funding options.",
    "Asking about accommodation near campus.",
    "Wants to know about job placement assistance after completion.",
    "Comparing with other training providers - price sensitive.",
    "Previous learner referral - already familiar with our programmes.",
]


class Command(BaseCommand):
    help = 'Create test CRM leads (potential learners) with realistic SA data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=100,
            help='Number of leads to create (default: 100)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing leads before creating new ones'
        )

    def handle(self, *args, **options):
        count = options['count']
        clear = options['clear']

        if clear:
            deleted, _ = Lead.objects.all().delete()
            self.stdout.write(f'Cleared {deleted} existing leads')

        # Get required data
        sources = list(LeadSource.objects.filter(is_active=True))
        if not sources:
            self.stdout.write(self.style.ERROR('No lead sources found. Please create some first.'))
            return

        pipelines = list(Pipeline.objects.filter(is_active=True))
        qualifications = list(Qualification.objects.filter(is_active=True))
        campuses = list(Campus.objects.all())
        users = list(User.objects.filter(is_active=True, is_staff=True))

        self.stdout.write(f'Creating {count} test leads...')
        self.stdout.write(f'  Sources: {len(sources)}')
        self.stdout.write(f'  Pipelines: {len(pipelines)}')
        self.stdout.write(f'  Qualifications: {len(qualifications)}')
        self.stdout.write(f'  Campuses: {len(campuses)}')
        self.stdout.write(f'  Staff users: {len(users)}')

        created = 0
        activities_created = 0

        for i in range(count):
            lead_data = self.generate_lead_data(sources, pipelines, qualifications, campuses, users)
            
            lead = Lead.objects.create(**lead_data)
            
            # Set created_at to a random date in the past
            days_ago = random.randint(0, 180)  # Last 6 months
            created_date = timezone.now() - timedelta(days=days_ago)
            Lead.objects.filter(pk=lead.pk).update(created_at=created_date)
            
            # Assign to pipeline and stage
            if lead.pipeline and lead.pipeline.stages.exists():
                self.assign_to_stage(lead)
            
            # Create activities
            num_activities = self.create_activities(lead, created_date)
            activities_created += num_activities
            
            created += 1
            
            if created % 25 == 0:
                self.stdout.write(f'  Created {created}/{count} leads...')

        self.stdout.write(self.style.SUCCESS(f'\nCreated {created} leads and {activities_created} activities'))
        
        # Summary by pipeline
        self.stdout.write('\nLeads by pipeline:')
        for pipeline in pipelines:
            count = Lead.objects.filter(pipeline=pipeline).count()
            self.stdout.write(f'  {pipeline.name}: {count}')

    def generate_lead_data(self, sources, pipelines, qualifications, campuses, users):
        """Generate realistic lead data"""
        # Random gender
        is_female = random.random() > 0.45  # Slightly more female learners
        first_name = random.choice(FIRST_NAMES_FEMALE if is_female else FIRST_NAMES_MALE)
        last_name = random.choice(LAST_NAMES)
        
        # Determine lead type based on age
        lead_type = random.choices(
            ['SCHOOL_LEAVER', 'ADULT', 'CORPORATE', 'REFERRAL'],
            weights=[30, 45, 15, 10]
        )[0]
        
        # Generate date of birth based on lead type
        today = date.today()
        if lead_type == 'SCHOOL_LEAVER':
            # Age 15-19
            age = random.randint(15, 19)
            dob = today - timedelta(days=age * 365 + random.randint(0, 365))
        else:
            # Age 20-45
            age = random.randint(20, 45)
            dob = today - timedelta(days=age * 365 + random.randint(0, 365))
        
        # Generate contact details
        phone = self.generate_phone()
        email = self.generate_email(first_name, last_name)
        
        # Select pipeline based on lead type
        pipeline = None
        if pipelines:
            pipeline_map = {
                'SCHOOL_LEAVER': 'SCHOOL_LEAVER_READY',
                'ADULT': 'ADULT',
                'CORPORATE': 'CORPORATE',
                'REFERRAL': 'REFERRAL',
            }
            target_type = pipeline_map.get(lead_type, 'ADULT')
            matching_pipelines = [p for p in pipelines if p.learner_type == target_type]
            if matching_pipelines:
                pipeline = random.choice(matching_pipelines)
            else:
                pipeline = random.choice(pipelines)
        
        # Status distribution
        status = random.choices(
            ['NEW', 'CONTACTED', 'QUALIFIED', 'PROPOSAL', 'NEGOTIATION', 'REGISTERED', 'LOST'],
            weights=[25, 25, 20, 10, 8, 7, 5]
        )[0]
        
        # Priority based on engagement potential
        priority = random.choices(
            ['LOW', 'MEDIUM', 'HIGH', 'URGENT'],
            weights=[20, 50, 25, 5]
        )[0]
        
        lead_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone': phone,
            'whatsapp_number': phone if random.random() > 0.2 else '',
            'prefers_whatsapp': random.random() > 0.3,
            'preferred_contact_method': random.choices(
                ['WHATSAPP', 'EMAIL', 'PHONE', 'SMS'],
                weights=[50, 30, 15, 5]
            )[0],
            'date_of_birth': dob,
            'lead_type': lead_type,
            'source': random.choice(sources),
            'qualification_interest': random.choice(qualifications) if qualifications and random.random() > 0.15 else None,
            'campus': random.choice(campuses) if campuses else None,
            'assigned_to': random.choice(users) if users and random.random() > 0.4 else None,
            'pipeline': pipeline,
            'status': status,
            'priority': priority,
            'consent_bulk_messaging': random.random() > 0.3,
            'nurture_active': status not in ['REGISTERED', 'LOST'],
            'engagement_score': random.randint(0, 100),
        }
        
        # Add school details for school leavers
        if lead_type == 'SCHOOL_LEAVER':
            lead_data['school_name'] = random.choice(SCHOOL_NAMES)
            lead_data['grade'] = random.choice(['Grade 10', 'Grade 11', 'Grade 12', 'Matric'])
            lead_data['expected_matric_year'] = today.year if lead_data['grade'] in ['Grade 12', 'Matric'] else today.year + 1
            
            # Add parent details for minors
            if age < 18:
                parent_first = random.choice(FIRST_NAMES_FEMALE if random.random() > 0.5 else FIRST_NAMES_MALE)
                lead_data['parent_name'] = f"{parent_first} {last_name}"
                lead_data['parent_phone'] = self.generate_phone()
                lead_data['parent_email'] = self.generate_email(parent_first, last_name)
                lead_data['parent_relationship'] = random.choice(['Mother', 'Father', 'Guardian', 'Aunt', 'Uncle'])
        
        # Add employment details for adults
        if lead_type in ['ADULT', 'CORPORATE']:
            lead_data['employment_status'] = random.choice(['Employed', 'Unemployed', 'Self-employed', 'Part-time'])
            if lead_data['employment_status'] in ['Employed', 'Part-time']:
                lead_data['employer_name'] = random.choice(EMPLOYERS)
        
        # Add notes for some leads
        if random.random() > 0.6:
            notes_options = [
                f"Interested in {lead_data['qualification_interest'].short_title if lead_data.get('qualification_interest') else 'training opportunities'}.",
                "Referred by previous learner. High potential.",
                "Enquired via website contact form.",
                "Met at career fair. Requested follow-up.",
                "Called in for more information.",
                "Responded to Facebook ad campaign.",
                "Looking for funded training options.",
                "Employer may sponsor training.",
            ]
            lead_data['notes'] = random.choice(notes_options)
        
        # Tags
        tags = []
        if lead_type == 'SCHOOL_LEAVER':
            tags.append('school_leaver')
        if lead_data.get('consent_bulk_messaging'):
            tags.append('marketing_consent')
        if priority == 'HIGH':
            tags.append('hot_lead')
        if lead_data.get('employer_name'):
            tags.append('employer_sponsor_potential')
        lead_data['tags'] = tags
        
        return lead_data

    def assign_to_stage(self, lead):
        """Assign lead to appropriate pipeline stage based on status"""
        stages = list(lead.pipeline.stages.all().order_by('order'))
        if not stages:
            return
        
        # Map status to stage selection
        if lead.status == 'NEW':
            # First stage
            stage = stages[0]
        elif lead.status == 'CONTACTED':
            # Second or third stage
            stage = stages[min(1, len(stages) - 1)]
        elif lead.status == 'QUALIFIED':
            # Middle stages
            stage = stages[min(len(stages) // 2, len(stages) - 1)]
        elif lead.status in ['PROPOSAL', 'NEGOTIATION']:
            # Later stages
            stage = stages[min(len(stages) - 2, len(stages) - 1)]
        elif lead.status == 'REGISTERED':
            # Won stage if available
            won_stages = [s for s in stages if s.is_won_stage]
            stage = won_stages[0] if won_stages else stages[-1]
        elif lead.status == 'LOST':
            # Lost stage if available
            lost_stages = [s for s in stages if s.is_lost_stage]
            stage = lost_stages[0] if lost_stages else stages[-1]
        else:
            stage = random.choice(stages)
        
        # Update lead with stage
        Lead.objects.filter(pk=lead.pk).update(
            current_stage=stage,
            stage_entered_at=timezone.now() - timedelta(days=random.randint(1, 30))
        )

    def create_activities(self, lead, created_date):
        """Create activities for the lead"""
        # Number of activities based on status
        status_activity_map = {
            'NEW': (0, 2),
            'CONTACTED': (1, 4),
            'QUALIFIED': (2, 6),
            'PROPOSAL': (3, 7),
            'NEGOTIATION': (4, 8),
            'REGISTERED': (5, 10),
            'LOST': (1, 5),
        }
        min_act, max_act = status_activity_map.get(lead.status, (0, 3))
        num_activities = random.randint(min_act, max_act)
        
        activities = []
        current_date = created_date
        
        activity_types = ['CALL', 'EMAIL', 'SMS', 'WHATSAPP', 'MEETING', 'NOTE']
        
        for _ in range(num_activities):
            # Activity date progresses from lead creation
            days_forward = random.randint(1, 14)
            activity_date = current_date + timedelta(days=days_forward)
            if activity_date > timezone.now():
                activity_date = timezone.now() - timedelta(hours=random.randint(1, 48))
            current_date = activity_date
            
            activity = LeadActivity(
                lead=lead,
                activity_type=random.choice(activity_types),
                description=random.choice(ACTIVITY_NOTES),
            )
            activities.append(activity)
        
        if activities:
            LeadActivity.objects.bulk_create(activities)
            # Update timestamps
            for i, activity in enumerate(activities):
                act_date = created_date + timedelta(days=random.randint(1, 30 + i * 5))
                if act_date > timezone.now():
                    act_date = timezone.now() - timedelta(hours=random.randint(1, 48))
                LeadActivity.objects.filter(pk=activity.pk).update(created_at=act_date)
        
        return len(activities)

    def generate_phone(self):
        """Generate SA phone number"""
        prefix = random.choice(PHONE_PREFIXES)
        number = ''.join([str(random.randint(0, 9)) for _ in range(7)])
        return f"{prefix}{number}"

    def generate_email(self, first_name, last_name):
        """Generate email address"""
        domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'icloud.com', 
                   'hotmail.com', 'webmail.co.za', 'vodamail.co.za', 'mweb.co.za']
        
        # Various email formats
        formats = [
            f"{first_name.lower()}.{last_name.lower().replace(' ', '')}",
            f"{first_name.lower()}{last_name.lower().replace(' ', '')}",
            f"{first_name.lower()[0]}{last_name.lower().replace(' ', '')}",
            f"{first_name.lower()}{random.randint(1, 99)}",
            f"{first_name.lower()}.{last_name.lower().replace(' ', '')}{random.randint(1, 99)}",
        ]
        
        return f"{random.choice(formats)}@{random.choice(domains)}"
