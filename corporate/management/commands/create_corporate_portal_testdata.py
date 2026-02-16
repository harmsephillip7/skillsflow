"""
Management command to create comprehensive test data for the Corporate Portal.
Creates service subscriptions, delivery projects, milestones, tasks, documents,
deadlines, meetings, and grant projects.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import random

from core.models import User
from corporate.models import (
    CorporateClient, CorporateContact, CorporateEmployee,
    ClientServiceSubscription, ServiceDeliveryProject, ProjectMilestone, MilestoneTask,
    ProjectDocument, DeadlineReminder, Committee, CommitteeMeeting,
    ServiceOffering, ServiceCategory, GrantProject, GrantClaim,
    ServiceDeliveryTemplate
)
from learners.models import Learner, SETA
from tenants.models import Campus


class Command(BaseCommand):
    help = 'Create comprehensive test data for the Corporate Portal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--client-id',
            type=int,
            help='Specific client ID to create data for',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing portal-related data first',
        )

    def handle(self, *args, **options):
        self.stdout.write('Creating Corporate Portal test data...\n')
        
        # Get or create necessary lookup data
        self.setup_service_offerings()
        
        # Get target client
        client_id = options.get('client_id')
        if client_id:
            client = CorporateClient.objects.get(pk=client_id)
        else:
            # Use first active client or create one
            client = CorporateClient.objects.filter(status='ACTIVE').first()
            if not client:
                client = self.create_sample_client()
        
        self.stdout.write(f'Using client: {client.company_name}')
        
        # Store campus reference for creating tenant-aware objects
        self.campus = client.campus
        
        # Create test data
        self.create_service_subscriptions(client)
        self.create_delivery_projects(client)
        self.create_deadlines(client)
        self.create_committees_and_meetings(client)
        self.create_grant_projects(client)
        self.link_employees_to_learners(client)
        
        self.stdout.write(self.style.SUCCESS('\nCorporate Portal test data created successfully!'))
        self.stdout.write(f'\nTest the portal at: /portal/corporate/?client_id={client.id}')

    def setup_service_offerings(self):
        """Ensure service categories and offerings exist."""
        # Create categories
        categories = [
            ('TRAINING', 'Training Services'),
            ('CONSULTING', 'Consulting Services'),
            ('COMPLIANCE', 'Compliance Services'),
        ]
        
        for code, name in categories:
            ServiceCategory.objects.get_or_create(
                code=code,
                defaults={'name': name, 'description': f'{name} for corporate clients'}
            )
        
        # Create service offerings
        training_cat = ServiceCategory.objects.get(code='TRAINING')
        consulting_cat = ServiceCategory.objects.get(code='CONSULTING')
        
        offerings = [
            (training_cat, 'LEARNERSHIP', 'Learnership Programme', 'LEARNERSHIP', Decimal('45000.00')),
            (training_cat, 'SKILLS_PROGRAMME', 'Skills Programme', 'SKILLS_PROG', Decimal('15000.00')),
            (training_cat, 'INTERNSHIP', 'Internship Programme', 'INTERNSHIP', Decimal('25000.00')),
            (consulting_cat, 'WSP_ATR', 'WSP/ATR Compilation', 'WSP_ATR', Decimal('8500.00')),
            (consulting_cat, 'EE_CONSULTING', 'Employment Equity Reporting', 'EE_CONSULT', Decimal('6500.00')),
            (consulting_cat, 'BEE_CONSULTING', 'BBBEE Verification', 'BBBEE_VERIF', Decimal('12000.00')),
            (consulting_cat, 'DG_APPLICATION', 'Grant Management', 'GRANT_MGMT', Decimal('35000.00')),
        ]
        
        for cat, service_type, name, code, price in offerings:
            ServiceOffering.objects.get_or_create(
                code=code,
                defaults={
                    'category': cat,
                    'service_type': service_type,
                    'name': name,
                    'description': f'{name} service for corporate clients',
                    'base_price': price,
                    'is_active': True,
                }
            )
        
        self.stdout.write('  ✓ Service offerings ready')

    def create_sample_client(self):
        """Create a sample client if none exists."""
        seta = SETA.objects.first()
        
        client = CorporateClient.objects.create(
            company_name='Demo Training Solutions (Pty) Ltd',
            trading_name='Demo Training',
            registration_number='2020/123456/07',
            vat_number='4123456789',
            phone='011 123 4567',
            email='info@demotraining.co.za',
            physical_address='123 Main Road, Sandton, Johannesburg, 2196',
            industry='Professional Services',
            seta=seta,
            employee_count=150,
            status='ACTIVE',
            client_tier='KEY',
        )
        
        # Create primary contact
        CorporateContact.objects.create(
            client=client,
            first_name='Sarah',
            last_name='Johnson',
            job_title='HR Director',
            role='HR_MANAGER',
            email='sarah@demotraining.co.za',
            phone='011 123 4567',
            mobile='082 123 4567',
            is_primary=True,
        )
        
        self.stdout.write(f'  ✓ Created sample client: {client.company_name}')
        return client

    def create_service_subscriptions(self, client):
        """Create service subscriptions for the client."""
        offerings = ServiceOffering.objects.filter(is_active=True)
        consultant = User.objects.filter(is_staff=True).first()
        campus = Campus.objects.first()  # Get default campus for tenant-aware models
        
        if not campus:
            self.stdout.write('  ⚠ No campus found, cannot create subscriptions')
            return
        
        statuses = ['ACTIVE', 'ACTIVE', 'ACTIVE', 'PENDING', 'EXPIRED']
        
        created = 0
        for i, offering in enumerate(offerings[:5]):
            # Check if subscription already exists
            existing = ClientServiceSubscription.objects.filter(
                client=client,
                service=offering
            ).first()
            
            if existing:
                continue
            
            start_date = date.today() - timedelta(days=random.randint(30, 180))
            
            ClientServiceSubscription.objects.create(
                campus=campus,
                client=client,
                service=offering,
                status=statuses[i % len(statuses)],
                start_date=start_date,
                end_date=start_date + timedelta(days=365),
                agreed_price=offering.base_price * Decimal(str(random.randint(5, 20))) if offering.base_price else None,
                assigned_consultant=consultant,
                notes=f'Subscription for {offering.name}',
            )
            created += 1
        
        self.stdout.write(f'  ✓ Created {created} service subscriptions')

    def create_delivery_projects(self, client):
        """Create delivery projects with milestones and tasks."""
        subscriptions = ClientServiceSubscription.objects.filter(
            client=client,
            status='ACTIVE'
        )
        
        project_manager = User.objects.filter(is_staff=True).first()
        campus = Campus.objects.first()
        
        if not campus or not project_manager:
            self.stdout.write('  ⚠ Missing campus or project manager, skipping delivery projects')
            return
        
        created_projects = 0
        created_milestones = 0
        created_tasks = 0
        
        for subscription in subscriptions:
            # Check if project exists
            existing = ServiceDeliveryProject.objects.filter(subscription=subscription).first()
            if existing:
                continue
            
            # Create project
            project = ServiceDeliveryProject.objects.create(
                campus=campus,
                subscription=subscription,
                client=client,
                name=f'{subscription.service.name} - {client.company_name}',
                description=f'Delivery project for {subscription.service.name}',
                project_manager=project_manager,
                planned_start_date=subscription.start_date,
                planned_end_date=subscription.end_date,
                status='IN_PROGRESS',
                health='GREEN',
            )
            created_projects += 1
            
            # Get template milestones or create default ones
            template = ServiceDeliveryTemplate.objects.filter(
                service_type=subscription.service.service_type
            ).first()
            
            if template:
                # Use template milestones
                template.create_project_milestones(project)
                milestones = project.milestones.all()
                created_milestones += milestones.count()
            else:
                # Create default milestones
                milestone_names = [
                    ('Kickoff & Planning', 'NOT_STARTED', 0),
                    ('Data Collection', 'NOT_STARTED', 7),
                    ('Analysis & Development', 'NOT_STARTED', 21),
                    ('Review & Approval', 'NOT_STARTED', 35),
                    ('Implementation', 'NOT_STARTED', 49),
                    ('Closeout', 'NOT_STARTED', 63),
                ]
                
                for seq, (name, status, days_offset) in enumerate(milestone_names, 1):
                    start_date = project.planned_start_date + timedelta(days=days_offset) if project.planned_start_date else date.today() + timedelta(days=days_offset)
                    milestone = ProjectMilestone.objects.create(
                        project=project,
                        name=name,
                        description=f'{name} phase for {project.name}',
                        sequence=seq,
                        status=status,
                        planned_start_date=start_date,
                        planned_end_date=start_date + timedelta(days=7),
                        weight=1,
                    )
                    created_milestones += 1
            
            # Update some milestones to show progress
            milestones = list(project.milestones.all().order_by('sequence'))
            if len(milestones) >= 3:
                # First milestone completed
                milestones[0].status = 'COMPLETED'
                milestones[0].actual_end_date = (project.planned_start_date or date.today()) + timedelta(days=5)
                milestones[0].save()
                
                # Second milestone in progress
                milestones[1].status = 'IN_PROGRESS'
                milestones[1].save()
            
            # Create tasks for in-progress milestone
            in_progress_milestone = project.milestones.filter(status='IN_PROGRESS').first()
            if in_progress_milestone:
                task_names = [
                    ('Gather requirements', 'DONE', 'HIGH'),
                    ('Schedule meetings', 'DONE', 'MEDIUM'),
                    ('Compile documentation', 'IN_PROGRESS', 'HIGH'),
                    ('Review with stakeholders', 'TODO', 'MEDIUM'),
                    ('Finalize deliverables', 'TODO', 'HIGH'),
                ]
                
                for title, status, priority in task_names:
                    MilestoneTask.objects.create(
                        milestone=in_progress_milestone,
                        title=title,
                        description=f'{title} for {in_progress_milestone.name}',
                        status=status,
                        priority=priority,
                        due_date=date.today() + timedelta(days=random.randint(1, 14)),
                        assigned_to=project_manager,
                    )
                    created_tasks += 1
        
        self.stdout.write(f'  ✓ Created {created_projects} projects, {created_milestones} milestones, {created_tasks} tasks')

    def create_deadlines(self, client):
        """Create deadline reminders for the client."""
        deadline_types = [
            ('WSP', 'WSP Submission Deadline', 30),
            ('ATR', 'ATR Submission Deadline', 45),
            ('EE', 'EE Report Submission', 60),
            ('BBBEE', 'BBBEE Certificate Renewal', 90),
            ('GRANT', 'Grant Claim Submission', 21),
            ('CLAIM', 'Quarterly Progress Report', 14),
            ('CONTRACT', 'Contract Renewal Review', 120),
        ]
        
        created = 0
        for reminder_type, title, days_ahead in deadline_types:
            # Check if similar deadline exists
            existing = DeadlineReminder.objects.filter(
                client=client,
                reminder_type=reminder_type
            ).first()
            
            if existing:
                continue
            
            DeadlineReminder.objects.create(
                client=client,
                reminder_type=reminder_type,
                title=title,
                description=f'{title} - Action required',
                deadline_date=date.today() + timedelta(days=days_ahead),
                reminder_days_before=[30, 14, 7, 1],
                is_completed=False,
            )
            created += 1
        
        # Create a completed deadline
        DeadlineReminder.objects.get_or_create(
            client=client,
            reminder_type='CUSTOM',
            title='Previous Quarter Report',
            defaults={
                'description': 'Q3 progress report submitted',
                'deadline_date': date.today() - timedelta(days=15),
                'reminder_days_before': [7, 1],
                'is_completed': True,
                'completed_date': date.today() - timedelta(days=16),
            }
        )
        created += 1
        
        self.stdout.write(f'  ✓ Created {created} deadline reminders')

    def create_committees_and_meetings(self, client):
        """Create committees and meeting records."""
        # Create training committee
        committee, created = Committee.objects.get_or_create(
            client=client,
            committee_type='TRAINING',
            defaults={
                'campus': self.campus,
                'name': f'{client.company_name} Training Committee',
                'meeting_frequency': 'Quarterly',
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(f'  ✓ Created Training Committee')
        
        # Create past meetings with minutes
        meeting_dates = [
            date.today() - timedelta(days=90),
            date.today() - timedelta(days=180),
            date.today() - timedelta(days=270),
        ]
        
        meeting_count = 0
        for i, meeting_date in enumerate(meeting_dates):
            existing = CommitteeMeeting.objects.filter(
                committee=committee,
                meeting_date=meeting_date
            ).first()
            
            if existing:
                continue
            
            CommitteeMeeting.objects.create(
                committee=committee,
                meeting_date=meeting_date,
                venue='Boardroom',
                agenda=f'''
1. Welcome and Apologies
2. Confirmation of Previous Minutes
3. Training Progress Report
4. Skills Development Budget Review
5. New Training Initiatives
6. General
7. Date of Next Meeting
                '''.strip(),
                minutes=f'''
TRAINING COMMITTEE MEETING MINUTES
Date: {meeting_date.strftime('%d %B %Y')}

1. WELCOME
   The Chairperson welcomed all present to the Q{4-i} Training Committee meeting.

2. PREVIOUS MINUTES
   The minutes of the previous meeting were confirmed as a true reflection.

3. TRAINING PROGRESS
   - {random.randint(10, 25)} learners currently enrolled in programmes
   - {random.randint(5, 15)} learners completed qualifications this quarter
   - Overall completion rate: {random.randint(75, 95)}%

4. BUDGET REVIEW
   - YTD spend: R{random.randint(500, 900)},000
   - Remaining budget: R{random.randint(100, 400)},000
   - On track for annual targets

5. NEW INITIATIVES
   - Proposed new skills programme for middle management
   - Digital skills training rollout planned for Q{(5-i) % 4 + 1}

6. NEXT MEETING
   Scheduled for {(meeting_date + timedelta(days=90)).strftime('%d %B %Y')}
                '''.strip(),
            )
            meeting_count += 1
        
        # Create upcoming meeting
        upcoming_meeting, created = CommitteeMeeting.objects.get_or_create(
            committee=committee,
            meeting_date=date.today() + timedelta(days=14),
            defaults={
                'venue': 'Boardroom',
                'agenda': '''
1. Welcome and Apologies
2. Confirmation of Previous Minutes  
3. Training Progress Report
4. Skills Development Budget Review
5. WSP/ATR Planning
6. General
7. Date of Next Meeting
                '''.strip(),
            }
        )
        
        if created:
            meeting_count += 1
        
        self.stdout.write(f'  ✓ Created {meeting_count} committee meetings')

    def create_grant_projects(self, client):
        """Create grant projects with claims."""
        seta = client.seta or SETA.objects.first()
        
        if not seta:
            self.stdout.write('  ⚠ No SETA found, skipping grant projects')
            return
        
        # Check if grants already exist
        existing = GrantProject.objects.filter(client=client).count()
        if existing >= 2:
            self.stdout.write(f'  ✓ Grant projects already exist ({existing})')
            return
        
        grant_manager = User.objects.filter(is_staff=True).first()
        
        # Create active grant
        grant1 = GrantProject.objects.create(
            client=client,
            campus=self.campus,
            seta=seta,
            project_name=f'Discretionary Grant - {client.company_name}',
            project_number=f'DG-{date.today().year}-{random.randint(1000, 9999)}',
            status='ACTIVE',
            application_date=date.today() - timedelta(days=150),
            approval_date=date.today() - timedelta(days=130),
            start_date=date.today() - timedelta(days=120),
            end_date=date.today() + timedelta(days=245),
            target_learners=20,
            enrolled_learners=18,
            completed_learners=8,
            approved_amount=Decimal('450000.00'),
            claimed_amount=Decimal('180000.00'),
            received_amount=Decimal('180000.00'),
            project_manager=grant_manager,
        )
        
        # Create claims for grant1
        GrantClaim.objects.create(
            project=grant1,
            claim_type='TRANCHE_1',
            claim_number=f'{grant1.project_number}-C1',
            claim_amount=Decimal('180000.00'),
            approved_amount=Decimal('180000.00'),
            submission_date=date.today() - timedelta(days=90),
            status='PAID',
        )
        
        GrantClaim.objects.create(
            project=grant1,
            claim_type='TRANCHE_2',
            claim_number=f'{grant1.project_number}-C2',
            claim_amount=Decimal('135000.00'),
            submission_date=date.today() - timedelta(days=15),
            status='SUBMITTED',
        )
        
        # Create completed grant
        grant2 = GrantProject.objects.create(
            client=client,
            campus=self.campus,
            seta=seta,
            project_name=f'Mandatory Grant - {client.company_name}',
            project_number=f'MG-{date.today().year - 1}-{random.randint(1000, 9999)}',
            status='COMPLETED',
            application_date=date.today() - timedelta(days=450),
            approval_date=date.today() - timedelta(days=420),
            start_date=date.today() - timedelta(days=400),
            end_date=date.today() - timedelta(days=35),
            target_learners=15,
            enrolled_learners=15,
            completed_learners=14,
            approved_amount=Decimal('280000.00'),
            claimed_amount=Decimal('280000.00'),
            received_amount=Decimal('280000.00'),
            project_manager=grant_manager,
        )
        
        # Create claims for grant2
        GrantClaim.objects.create(
            project=grant2,
            claim_type='TRANCHE_1',
            claim_number=f'{grant2.project_number}-C1',
            claim_amount=Decimal('112000.00'),
            approved_amount=Decimal('112000.00'),
            submission_date=date.today() - timedelta(days=350),
            status='PAID',
        )
        
        GrantClaim.objects.create(
            project=grant2,
            claim_type='TRANCHE_2',
            claim_number=f'{grant2.project_number}-C2',
            claim_amount=Decimal('168000.00'),
            approved_amount=Decimal('168000.00'),
            submission_date=date.today() - timedelta(days=60),
            status='PAID',
        )
        
        self.stdout.write(f'  ✓ Created 2 grant projects with claims')

    def link_employees_to_learners(self, client):
        """Link corporate employees to learners for training tracking."""
        # Get learners that aren't already linked
        linked_learner_ids = CorporateEmployee.objects.filter(
            client=client
        ).values_list('learner_id', flat=True)
        
        available_learners = Learner.objects.exclude(
            id__in=linked_learner_ids
        )[:10]
        
        created = 0
        departments = ['Operations', 'Finance', 'HR', 'IT', 'Sales', 'Marketing']
        
        for learner in available_learners:
            CorporateEmployee.objects.create(
                client=client,
                learner=learner,
                employee_number=f'EMP{random.randint(1000, 9999)}',
                department=random.choice(departments),
                job_title=f'{random.choice(["Junior", "Senior", ""])} {random.choice(["Analyst", "Administrator", "Coordinator", "Specialist"])}',
                start_date=date.today() - timedelta(days=random.randint(180, 720)),
                is_current=True,
            )
            created += 1
        
        self.stdout.write(f'  ✓ Linked {created} employees to learners')
