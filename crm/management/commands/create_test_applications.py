"""
Management command to create test CRM applications with opportunities.
Creates realistic application data for testing the application section.
"""
import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from crm.models import Lead, Opportunity, Application
from tenants.models import Campus
from academics.models import Qualification
from intakes.models import Intake
from core.models import User


class Command(BaseCommand):
    help = 'Create test CRM applications with opportunities from existing leads'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=30,
            help='Number of applications to create (default: 30)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing applications and opportunities before creating new ones'
        )

    def handle(self, *args, **options):
        count = options['count']
        clear = options['clear']

        if clear:
            app_deleted, _ = Application.objects.all().delete()
            opp_deleted, _ = Opportunity.objects.all().delete()
            self.stdout.write(f'Cleared {app_deleted} applications and {opp_deleted} opportunities')

        # Get required data
        leads = list(Lead.objects.filter(
            status__in=['NEW', 'CONTACTED', 'QUALIFIED', 'QUOTED', 'ACCEPTED', 'FOLLOW_UP']
        ).exclude(opportunities__isnull=False)[:count * 2])
        
        if not leads:
            self.stdout.write(self.style.ERROR('No available leads found. Please create some leads first.'))
            return

        qualifications = list(Qualification.objects.filter(is_active=True))
        if not qualifications:
            self.stdout.write(self.style.ERROR('No qualifications found. Please create some first.'))
            return

        intakes = list(Intake.objects.filter(status='OPEN'))
        campuses = list(Campus.objects.all())
        users = list(User.objects.filter(is_active=True, is_staff=True))

        self.stdout.write(f'Creating up to {count} test applications...')
        self.stdout.write(f'  Available leads: {len(leads)}')
        self.stdout.write(f'  Qualifications: {len(qualifications)}')
        self.stdout.write(f'  Intakes: {len(intakes)}')
        self.stdout.write(f'  Staff users: {len(users)}')

        created_opportunities = 0
        created_applications = 0
        
        # Application status distribution
        status_weights = {
            'DRAFT': 10,
            'SUBMITTED': 15,
            'DOCUMENTS_PENDING': 20,
            'UNDER_REVIEW': 20,
            'ACCEPTED': 15,
            'WAITLIST': 5,
            'REJECTED': 5,
            'ENROLLED': 8,
            'WITHDRAWN': 2,
        }
        statuses = list(status_weights.keys())
        weights = list(status_weights.values())

        # Opportunity stage distribution
        stage_weights = {
            'DISCOVERY': 10,
            'QUALIFICATION': 15,
            'PROPOSAL': 20,
            'NEGOTIATION': 15,
            'COMMITTED': 25,
            'WON': 10,
            'LOST': 5,
        }
        stages = list(stage_weights.keys())
        stage_weight_values = list(stage_weights.values())

        # Funding types
        funding_types = ['SELF', 'EMPLOYER', 'BURSARY', 'SETA', 'NSFAS', 'LOAN', 'SCHOLARSHIP', 'MIXED']
        funding_weights = [40, 15, 10, 15, 10, 5, 3, 2]

        for i, lead in enumerate(leads[:count]):
            qualification = random.choice(qualifications)
            intake = random.choice(intakes) if intakes else None
            agent = random.choice(users) if users else None
            campus = lead.campus or (random.choice(campuses) if campuses else None)
            
            # Calculate value based on qualification
            base_value = random.randint(15000, 85000)
            
            # Select stage
            stage = random.choices(stages, weights=stage_weight_values)[0]
            
            # Probability based on stage
            probability_map = {
                'DISCOVERY': random.randint(5, 20),
                'QUALIFICATION': random.randint(15, 35),
                'PROPOSAL': random.randint(30, 50),
                'NEGOTIATION': random.randint(50, 70),
                'COMMITTED': random.randint(75, 90),
                'WON': 100,
                'LOST': 0,
            }
            probability = probability_map[stage]
            
            # Select funding type
            funding_type = random.choices(funding_types, weights=funding_weights)[0]
            
            # Create opportunity
            opp_name = f"{lead.first_name} {lead.last_name} - {qualification.short_title}"
            
            try:
                opportunity = Opportunity.objects.create(
                    lead=lead,
                    name=opp_name,
                    qualification=qualification,
                    intake=intake,
                    stage=stage,
                    value=Decimal(base_value),
                    probability=probability,
                    expected_close_date=date.today() + timedelta(days=random.randint(7, 90)),
                    expected_start_date=date.today() + timedelta(days=random.randint(30, 180)),
                    funding_type=funding_type,
                    funding_confirmed=random.random() > 0.6,
                    funding_amount=Decimal(base_value) if random.random() > 0.5 else Decimal(0),
                    assigned_agent=agent,
                    campus=campus,
                    notes=f"Test opportunity for {lead.first_name}",
                )
                created_opportunities += 1
                
                # Create application for committed/won stages or randomly
                if stage in ['COMMITTED', 'WON'] or random.random() > 0.4:
                    app_status = random.choices(statuses, weights=weights)[0]
                    
                    # Adjust status based on stage
                    if stage == 'WON':
                        app_status = random.choice(['ACCEPTED', 'ENROLLED'])
                    elif stage == 'LOST':
                        app_status = random.choice(['REJECTED', 'WITHDRAWN'])
                    
                    # Determine if minor (needs parent consent)
                    is_minor = lead.is_minor if hasattr(lead, 'is_minor') else False
                    
                    # Create application
                    application = Application.objects.create(
                        opportunity=opportunity,
                        status=app_status,
                        campus=campus,
                        required_documents=['ID Document', 'Matric Certificate', 'Proof of Address'],
                        missing_documents=['Matric Certificate'] if app_status == 'DOCUMENTS_PENDING' else [],
                        parent_consent_required=is_minor,
                        parent_consent_received=is_minor and random.random() > 0.3,
                    )
                    
                    # Set dates based on status
                    days_ago = random.randint(1, 60)
                    created_date = timezone.now() - timedelta(days=days_ago)
                    
                    if app_status in ['SUBMITTED', 'DOCUMENTS_PENDING', 'UNDER_REVIEW', 'ACCEPTED', 'REJECTED', 'ENROLLED']:
                        application.submitted_at = created_date + timedelta(days=random.randint(1, 5))
                        application.submitted_by = agent
                    
                    if app_status in ['ACCEPTED', 'REJECTED', 'ENROLLED']:
                        application.reviewed_at = created_date + timedelta(days=random.randint(3, 10))
                        application.reviewed_by = random.choice(users) if users else None
                        if app_status == 'REJECTED':
                            application.decision_notes = random.choice([
                                "Does not meet minimum entry requirements",
                                "Missing required documentation",
                                "Failed entrance assessment",
                                "Application withdrawn by learner",
                            ])
                        elif app_status == 'ACCEPTED':
                            application.decision_notes = "All requirements met. Approved for enrollment."
                    
                    if app_status == 'ENROLLED':
                        application.enrollment_date = date.today() - timedelta(days=random.randint(1, 30))
                    
                    application.next_follow_up = timezone.now() + timedelta(days=random.randint(1, 14))
                    application.save()
                    
                    created_applications += 1
                    
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error creating opportunity for {lead}: {e}'))
                continue
            
            if (i + 1) % 10 == 0:
                self.stdout.write(f'  Processed {i + 1}/{min(count, len(leads))} leads...')

        self.stdout.write(self.style.SUCCESS(
            f'\nCreated {created_opportunities} opportunities and {created_applications} applications'
        ))
        
        # Summary by status
        self.stdout.write('\nApplications by status:')
        for status, label in Application.STATUS_CHOICES:
            count = Application.objects.filter(status=status).count()
            if count > 0:
                self.stdout.write(f'  {label}: {count}')
        
        # Summary by stage
        self.stdout.write('\nOpportunities by stage:')
        for stage, label in Opportunity.STAGE_CHOICES:
            count = Opportunity.objects.filter(stage=stage).count()
            if count > 0:
                self.stdout.write(f'  {label}: {count}')
