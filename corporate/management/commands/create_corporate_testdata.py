"""
Management command to create test data for the corporate CRM module.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import random

from corporate.models import (
    CorporateClient, CorporateContact, ServiceCategory, ServiceOffering,
    ClientServiceSubscription, LeadSource, CorporateOpportunity, 
    CorporateActivity, ServiceProposal, ProposalLineItem,
    ServiceDeliveryProject, ProjectMilestone, MilestoneTask,
    HostEmployer, HostMentor
)
from core.models import User
from tenants.models import Brand, Campus


class Command(BaseCommand):
    help = 'Create test data for corporate CRM module'

    def handle(self, *args, **options):
        self.stdout.write('Creating corporate test data...')
        
        # Get or create a test brand and campus
        brand, _ = Brand.objects.get_or_create(
            code='SKILLSFLOW',
            defaults={
                'name': 'SkillsFlow Training',
                'is_active': True,
            }
        )
        
        campus, _ = Campus.objects.get_or_create(
            brand=brand,
            code='HQ',
            defaults={
                'name': 'Head Office',
                'campus_type': 'HEAD_OFFICE',
                'is_active': True,
            }
        )
        self.stdout.write(f'  Using campus: {campus.name}')
        
        # Get or create a test user for assignments
        user, created = User.objects.get_or_create(
            email='corporate@skillsflow.co.za',
            defaults={
                'first_name': 'Corporate',
                'last_name': 'Manager',
                'is_staff': True,
            }
        )
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(f'  Created user: {user.email}')
        
        # Create Lead Sources
        self.stdout.write('Creating lead sources...')
        lead_sources_data = [
            ('WEBSITE', 'Website Inquiry'),
            ('REFERRAL', 'Client Referral'),
            ('EVENT', 'Trade Show/Event'),
            ('COLD_CALL', 'Cold Call'),
            ('LINKEDIN', 'LinkedIn'),
            ('PARTNER', 'Partner Referral'),
        ]
        lead_sources = {}
        for code, name in lead_sources_data:
            ls, _ = LeadSource.objects.get_or_create(
                code=code,
                defaults={'name': name, 'is_active': True}
            )
            lead_sources[code] = ls
        
        # Create Service Categories
        self.stdout.write('Creating service categories...')
        categories_data = [
            ('WSP_ATR', 'WSP/ATR Services', 1),
            ('HOST_EMP', 'Host Employment', 2),
            ('DG_APPS', 'Discretionary Grant Applications', 3),
            ('EE_CONS', 'Employment Equity Consulting', 4),
            ('BEE_CONS', 'B-BBEE Consulting', 5),
            ('TRAINING', 'Training Products', 6),
            ('TRADE_TEST', 'Trade Test Administration', 7),
            ('TRANCHE', 'Tranche Administration', 8),
        ]
        categories = {}
        for code, name, order in categories_data:
            cat, _ = ServiceCategory.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'display_order': order,
                    'is_active': True
                }
            )
            categories[code] = cat
        
        # Create Service Offerings
        self.stdout.write('Creating service offerings...')
        services_data = [
            ('WSP_ATR', 'WSP Submission', 'WSP-001', 'WSP_ATR', 'Annual WSP submission to SETA', Decimal('15000.00'), 'ANNUAL'),
            ('WSP_ATR', 'ATR Submission', 'ATR-001', 'WSP_ATR', 'Annual Training Report submission', Decimal('10000.00'), 'ANNUAL'),
            ('WSP_ATR', 'WSP/ATR Bundle', 'WSPATR-001', 'WSP_ATR', 'Combined WSP and ATR service', Decimal('22000.00'), 'ANNUAL'),
            ('HOST_EMP', 'Host Employer Setup', 'HOST-001', 'HOST_EMPLOYMENT', 'Complete host employer setup and registration', Decimal('5000.00'), 'PROJECT'),
            ('HOST_EMP', 'Learner Placement', 'HOST-002', 'HOST_EMPLOYMENT', 'Per-learner workplace placement service', Decimal('1500.00'), 'PER_LEARNER'),
            ('DG_APPS', 'DG Application - Small', 'DG-001', 'DG_APPLICATION', 'Discretionary Grant application (up to R500k)', Decimal('25000.00'), 'PROJECT'),
            ('DG_APPS', 'DG Application - Medium', 'DG-002', 'DG_APPLICATION', 'Discretionary Grant application (R500k - R2m)', Decimal('45000.00'), 'PROJECT'),
            ('DG_APPS', 'DG Application - Large', 'DG-003', 'DG_APPLICATION', 'Discretionary Grant application (R2m+)', Decimal('75000.00'), 'PROJECT'),
            ('EE_CONS', 'EE Plan Development', 'EE-001', 'EE_CONSULTING', 'Employment Equity plan development', Decimal('20000.00'), 'PROJECT'),
            ('EE_CONS', 'EE Annual Reporting', 'EE-002', 'EE_CONSULTING', 'Annual EE report submission', Decimal('8000.00'), 'ANNUAL'),
            ('BEE_CONS', 'B-BBEE Verification', 'BEE-001', 'BEE_CONSULTING', 'B-BBEE scorecard verification support', Decimal('35000.00'), 'ANNUAL'),
            ('BEE_CONS', 'B-BBEE Strategy', 'BEE-002', 'BEE_CONSULTING', 'B-BBEE improvement strategy', Decimal('50000.00'), 'PROJECT'),
            ('TRAINING', 'Skills Program - Basic', 'SKL-001', 'SKILLS_PROGRAMME', 'Basic skills program delivery', Decimal('3500.00'), 'PER_LEARNER'),
            ('TRAINING', 'Skills Program - Advanced', 'SKL-002', 'SKILLS_PROGRAMME', 'Advanced skills program delivery', Decimal('7500.00'), 'PER_LEARNER'),
            ('TRAINING', 'Learnership - Full', 'LRN-001', 'LEARNERSHIP', 'Full learnership program', Decimal('25000.00'), 'PER_LEARNER'),
            ('TRADE_TEST', 'Trade Test Booking', 'TT-001', 'TRADE_TEST_ADMIN', 'Trade test booking and administration', Decimal('2500.00'), 'ONCE_OFF'),
            ('TRADE_TEST', 'Trade Test Preparation', 'TT-002', 'TRADE_TEST_ADMIN', 'Trade test preparation coaching', Decimal('5000.00'), 'ONCE_OFF'),
            ('TRANCHE', 'Tranche Administration', 'TRN-001', 'TRANCHE_ADMIN', 'Full tranche payment administration', Decimal('15000.00'), 'PROJECT'),
        ]
        services = {}
        for cat_code, name, code, service_type, desc, price, billing_type in services_data:
            svc, _ = ServiceOffering.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'category': categories[cat_code],
                    'service_type': service_type,
                    'description': desc,
                    'base_price': price,
                    'billing_type': billing_type,
                    'is_active': True
                }
            )
            services[name] = svc
        
        # Create Corporate Clients
        self.stdout.write('Creating corporate clients...')
        clients_data = [
            {
                'company_name': 'Acme Mining Corporation',
                'trading_name': 'Acme Mining',
                'registration_number': '2015/123456/07',
                'vat_number': '4123456789',
                'phone': '011 123 4567',
                'email': 'info@acmemining.co.za',
                'physical_address': '123 Mining Road, Sandton, Johannesburg, 2196',
                'industry': 'Mining',
                'seta_number': 'L/12345/2020',
                'employee_count': 2500,
                'status': 'ACTIVE',
                'client_tier': 'STRATEGIC',
                'lead_source': lead_sources['REFERRAL'],
            },
            {
                'company_name': 'TechPro Solutions (Pty) Ltd',
                'trading_name': 'TechPro',
                'registration_number': '2018/789012/07',
                'vat_number': '4987654321',
                'phone': '012 345 6789',
                'email': 'contact@techpro.co.za',
                'physical_address': '456 Innovation Park, Pretoria, 0001',
                'industry': 'Information Technology',
                'seta_number': 'L/67890/2021',
                'employee_count': 450,
                'status': 'ACTIVE',
                'client_tier': 'KEY',
                'lead_source': lead_sources['WEBSITE'],
            },
            {
                'company_name': 'GreenGrow Agriculture',
                'trading_name': 'GreenGrow',
                'registration_number': '2010/456789/07',
                'vat_number': '4567891234',
                'phone': '021 876 5432',
                'email': 'info@greengrow.co.za',
                'physical_address': '789 Farm Road, Stellenbosch, 7600',
                'industry': 'Agriculture',
                'seta_number': 'L/11111/2019',
                'employee_count': 1200,
                'status': 'ACTIVE',
                'client_tier': 'KEY',
                'lead_source': lead_sources['EVENT'],
            },
            {
                'company_name': 'BuildRight Construction',
                'trading_name': 'BuildRight',
                'registration_number': '2012/321654/07',
                'vat_number': '4321654987',
                'phone': '031 234 5678',
                'email': 'projects@buildright.co.za',
                'physical_address': '321 Builder Street, Durban, 4001',
                'industry': 'Construction',
                'seta_number': 'L/22222/2020',
                'employee_count': 850,
                'status': 'ACTIVE',
                'client_tier': 'STANDARD',
                'lead_source': lead_sources['COLD_CALL'],
            },
            {
                'company_name': 'Healthcare Plus Medical Group',
                'trading_name': 'Healthcare Plus',
                'registration_number': '2008/654321/07',
                'vat_number': '4654321987',
                'phone': '011 987 6543',
                'email': 'admin@healthcareplus.co.za',
                'physical_address': '654 Medical Park, Johannesburg, 2000',
                'industry': 'Healthcare',
                'seta_number': 'L/33333/2018',
                'employee_count': 3200,
                'status': 'ACTIVE',
                'client_tier': 'STRATEGIC',
                'lead_source': lead_sources['PARTNER'],
            },
            {
                'company_name': 'RetailMax Holdings',
                'trading_name': 'RetailMax',
                'registration_number': '2016/987654/07',
                'vat_number': '4789456123',
                'phone': '010 456 7890',
                'email': 'hr@retailmax.co.za',
                'physical_address': '987 Shopping Centre, Sandton, 2196',
                'industry': 'Retail',
                'seta_number': 'L/44444/2021',
                'employee_count': 5500,
                'status': 'ACTIVE',
                'client_tier': 'KEY',
                'lead_source': lead_sources['LINKEDIN'],
            },
            {
                'company_name': 'FutureFinance Bank',
                'trading_name': 'FutureFinance',
                'registration_number': '2005/111222/07',
                'vat_number': '4111222333',
                'phone': '011 555 1234',
                'email': 'training@futurefinance.co.za',
                'physical_address': '111 Finance Tower, Sandton, 2196',
                'industry': 'Financial Services',
                'seta_number': 'L/55555/2017',
                'employee_count': 8000,
                'status': 'ACTIVE',
                'client_tier': 'STRATEGIC',
                'lead_source': lead_sources['REFERRAL'],
            },
            {
                'company_name': 'NewStart Manufacturing',
                'trading_name': 'NewStart',
                'registration_number': '2020/333444/07',
                'vat_number': '4333444555',
                'phone': '041 333 4444',
                'email': 'info@newstart.co.za',
                'physical_address': '333 Industrial Park, Port Elizabeth, 6001',
                'industry': 'Manufacturing',
                'employee_count': 200,
                'status': 'PROSPECT',
                'client_tier': 'EMERGING',
                'lead_source': lead_sources['WEBSITE'],
            },
        ]
        
        clients = []
        for data in clients_data:
            # Add campus to client data
            data['campus'] = campus
            client, _ = CorporateClient.objects.get_or_create(
                company_name=data['company_name'],
                campus=campus,
                defaults=data
            )
            clients.append(client)
        
        # Create Contacts for each client
        self.stdout.write('Creating contacts...')
        contact_roles = ['HR_MANAGER', 'TRAINING_MANAGER', 'FINANCE', 'CEO', 'COO']
        first_names = ['John', 'Sarah', 'Michael', 'Emma', 'David', 'Lisa', 'James', 'Rachel']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller', 'Davis', 'Garcia']
        
        for client in clients:
            for i in range(random.randint(2, 4)):
                contact, _ = CorporateContact.objects.get_or_create(
                    client=client,
                    email=f'{first_names[i % len(first_names)].lower()}.{last_names[i % len(last_names)].lower()}@{client.company_name.lower().replace(" ", "").replace("(pty)ltd", "")[:10]}.co.za',
                    defaults={
                        'first_name': first_names[i % len(first_names)],
                        'last_name': last_names[i % len(last_names)],
                        'phone': f'08{random.randint(10000000, 99999999)}',
                        'role': contact_roles[i % len(contact_roles)],
                        'is_primary': i == 0,
                        'is_active': True,
                        'influence_level': random.choice(['HIGH', 'MEDIUM', 'LOW']),
                    }
                )
        
        # Create Service Subscriptions for active clients
        self.stdout.write('Creating service subscriptions...')
        active_clients = [c for c in clients if c.status == 'ACTIVE']
        
        for client in active_clients:
            # Each client gets 2-4 random services
            client_services = random.sample(list(services.values()), random.randint(2, 4))
            for svc in client_services:
                sub, _ = ClientServiceSubscription.objects.get_or_create(
                    client=client,
                    service=svc,
                    campus=campus,
                    defaults={
                        'campus': campus,
                        'start_date': date.today() - timedelta(days=random.randint(30, 365)),
                        'end_date': date.today() + timedelta(days=random.randint(30, 365)),
                        'agreed_price': svc.base_price * Decimal(random.uniform(0.9, 1.1)) if svc.base_price else Decimal('10000.00'),
                        'status': 'ACTIVE',
                    }
                )
        
        # Create Opportunities
        self.stdout.write('Creating opportunities...')
        stages = ['IDENTIFIED', 'QUALIFIED', 'NEEDS_ANALYSIS', 'PROPOSAL', 'NEGOTIATION', 'CLOSED_WON', 'CLOSED_LOST']
        opportunity_titles = [
            'WSP 2025 Submission',
            'Host Employment Program',
            'DG Application 2025',
            'B-BBEE Improvement Project',
            'Skills Development Program',
            'Learnership Program',
            'EE Compliance Project',
            'Training Needs Analysis',
        ]
        
        for client in clients:
            # Create 1-3 opportunities per client
            for _ in range(random.randint(1, 3)):
                stage = random.choice(stages)
                opp, created = CorporateOpportunity.objects.get_or_create(
                    client=client,
                    title=random.choice(opportunity_titles) + f' - {client.company_name[:20]}',
                    campus=campus,
                    defaults={
                        'campus': campus,
                        'description': f'Opportunity for {client.company_name}',
                        'opportunity_type': random.choice(['NEW_BUSINESS', 'UPSELL', 'CROSS_SELL', 'RENEWAL']),
                        'stage': stage,
                        'priority': random.choice(['LOW', 'MEDIUM', 'HIGH', 'URGENT']),
                        'estimated_value': Decimal(random.randint(10000, 500000)),
                        'probability': random.choice([10, 25, 50, 75, 90]) if stage not in ['CLOSED_WON', 'CLOSED_LOST'] else (100 if stage == 'CLOSED_WON' else 0),
                        'expected_close_date': date.today() + timedelta(days=random.randint(30, 180)),
                        'actual_close_date': date.today() - timedelta(days=random.randint(1, 60)) if stage in ['CLOSED_WON', 'CLOSED_LOST'] else None,
                        'lead_source': random.choice(list(lead_sources.values())),
                        'sales_owner': user,
                    }
                )
                
                # Add proposed services
                if created:
                    opp.proposed_services.set(random.sample(list(services.values()), random.randint(1, 3)))
        
        # Create Activities
        self.stdout.write('Creating activities...')
        activity_types = ['CALL', 'MEETING', 'EMAIL', 'PRESENTATION', 'SITE_VISIT', 'FOLLOW_UP']
        outcomes = ['POSITIVE', 'NEUTRAL', 'NEGATIVE', 'SCHEDULED_FOLLOWUP']
        
        opportunities = CorporateOpportunity.objects.all()
        for opp in opportunities:
            # Create 2-5 activities per opportunity
            for i in range(random.randint(2, 5)):
                activity_date = timezone.now() - timedelta(days=random.randint(1, 90))
                CorporateActivity.objects.get_or_create(
                    opportunity=opp,
                    client=opp.client,
                    activity_date=activity_date,
                    activity_type=random.choice(activity_types),
                    defaults={
                        'subject': f'{random.choice(activity_types)} with {opp.client.company_name}',
                        'description': f'Activity {i+1} for opportunity',
                        'outcome': random.choice(outcomes),
                        'is_completed': random.choice([True, True, True, False]),
                        'next_action': 'Follow up next week' if random.choice([True, False]) else '',
                        'next_action_date': (activity_date + timedelta(days=7)).date() if random.choice([True, False]) else None,
                    }
                )
        
        # Create Proposals for some opportunities
        self.stdout.write('Creating proposals...')
        proposal_opportunities = CorporateOpportunity.objects.filter(
            stage__in=['PROPOSAL', 'NEGOTIATION', 'CLOSED_WON']
        )[:10]
        
        for opp in proposal_opportunities:
            proposal, created = ServiceProposal.objects.get_or_create(
                opportunity=opp,
                client=opp.client,
                campus=campus,
                defaults={
                    'campus': campus,
                    'title': f'Proposal: {opp.title}',
                    'introduction': f'Thank you for the opportunity to present our proposal for {opp.client.company_name}.',
                    'status': 'ACCEPTED' if opp.stage == 'CLOSED_WON' else ('SENT' if opp.stage in ['PROPOSAL', 'NEGOTIATION'] else 'DRAFT'),
                    'valid_until': date.today() + timedelta(days=30),
                    'prepared_by': user,
                    'sent_date': timezone.now() - timedelta(days=random.randint(1, 30)) if opp.stage in ['PROPOSAL', 'NEGOTIATION', 'CLOSED_WON'] else None,
                    'response_date': timezone.now() - timedelta(days=random.randint(1, 15)) if opp.stage == 'CLOSED_WON' else None,
                    'discount_percentage': Decimal(random.choice([0, 5, 10, 15])),
                    'vat_percentage': Decimal('15.00'),
                    'terms_and_conditions': 'Payment terms: 30 days from invoice date.\nValidity: 30 days from proposal date.',
                }
            )
            
            # Add line items
            if created:
                for svc in opp.proposed_services.all():
                    ProposalLineItem.objects.create(
                        proposal=proposal,
                        service=svc,
                        description=svc.description,
                        quantity=random.randint(1, 10),
                        unit_price=svc.base_price if svc.base_price else Decimal('10000.00')
                    )
                proposal.calculate_totals()
        
        # Create Delivery Projects for accepted proposals
        self.stdout.write('Creating delivery projects...')
        accepted_subscriptions = ClientServiceSubscription.objects.filter(status='ACTIVE')[:8]
        
        for sub in accepted_subscriptions:
            project, created = ServiceDeliveryProject.objects.get_or_create(
                subscription=sub,
                client=sub.client,
                campus=campus,
                defaults={
                    'campus': campus,
                    'name': f'{sub.service.name} - {sub.client.company_name}',
                    'description': f'Delivery of {sub.service.name} for {sub.client.company_name}',
                    'status': random.choice(['SETUP', 'PLANNING', 'IN_PROGRESS', 'IN_PROGRESS', 'IN_PROGRESS']),
                    'health': random.choice(['GREEN', 'GREEN', 'GREEN', 'AMBER', 'RED']),
                    'planned_start_date': date.today() - timedelta(days=random.randint(30, 90)),
                    'planned_end_date': date.today() + timedelta(days=random.randint(30, 180)),
                    'actual_start_date': date.today() - timedelta(days=random.randint(15, 60)),
                    'project_manager': user,
                    'budget': sub.agreed_price,
                }
            )
            
            # Create milestones
            if created:
                milestones = [
                    ('Kickoff', 10),
                    ('Discovery & Analysis', 20),
                    ('Development', 30),
                    ('Review & Approval', 20),
                    ('Delivery & Handover', 20),
                ]
                
                for seq, (name, weight) in enumerate(milestones, 1):
                    milestone_status = 'COMPLETED' if seq <= 2 else ('IN_PROGRESS' if seq == 3 else 'NOT_STARTED')
                    ms = ProjectMilestone.objects.create(
                        project=project,
                        name=name,
                        sequence=seq,
                        status=milestone_status,
                        weight=weight,
                        planned_start_date=project.planned_start_date + timedelta(days=(seq-1)*14),
                        planned_end_date=project.planned_start_date + timedelta(days=seq*14),
                        actual_start_date=project.actual_start_date + timedelta(days=(seq-1)*14) if seq <= 3 else None,
                        actual_end_date=project.actual_start_date + timedelta(days=seq*14) if seq <= 2 else None,
                    )
                    
                    # Add tasks to milestones
                    task_names = [f'Task {i+1} for {name}' for i in range(random.randint(2, 4))]
                    for task_name in task_names:
                        MilestoneTask.objects.create(
                            milestone=ms,
                            title=task_name,
                            status='DONE' if milestone_status == 'COMPLETED' else ('IN_PROGRESS' if milestone_status == 'IN_PROGRESS' and random.choice([True, False]) else 'TODO'),
                            priority=random.choice(['LOW', 'MEDIUM', 'HIGH']),
                            assigned_to=user,
                        )
                
                project.update_progress()
        
        # Create Host Employers
        self.stdout.write('Creating host employers...')
        for client in active_clients[:4]:
            host, _ = HostEmployer.objects.get_or_create(
                company_name=f'{client.company_name} Host Division',
                campus=campus,
                defaults={
                    'campus': campus,
                    'trading_name': client.trading_name,
                    'registration_number': client.registration_number,
                    'physical_address': client.physical_address,
                    'contact_person': 'HR Manager',
                    'contact_email': client.email,
                    'contact_phone': client.phone,
                    'max_placement_capacity': random.randint(10, 50),
                    'status': 'APPROVED',
                }
            )
            
            # Add mentors
            for i in range(random.randint(2, 4)):
                HostMentor.objects.get_or_create(
                    host=host,
                    email=f'mentor{i+1}@{client.email.split("@")[1]}',
                    defaults={
                        'first_name': first_names[i % len(first_names)],
                        'last_name': last_names[i % len(last_names)],
                        'phone': f'08{random.randint(10000000, 99999999)}',
                        'is_active': True,
                    }
                )
        
        self.stdout.write(self.style.SUCCESS('Corporate test data created successfully!'))
        self.stdout.write(f'  - Lead Sources: {LeadSource.objects.count()}')
        self.stdout.write(f'  - Service Categories: {ServiceCategory.objects.count()}')
        self.stdout.write(f'  - Service Offerings: {ServiceOffering.objects.count()}')
        self.stdout.write(f'  - Clients: {CorporateClient.objects.count()}')
        self.stdout.write(f'  - Contacts: {CorporateContact.objects.count()}')
        self.stdout.write(f'  - Subscriptions: {ClientServiceSubscription.objects.count()}')
        self.stdout.write(f'  - Opportunities: {CorporateOpportunity.objects.count()}')
        self.stdout.write(f'  - Activities: {CorporateActivity.objects.count()}')
        self.stdout.write(f'  - Proposals: {ServiceProposal.objects.count()}')
        self.stdout.write(f'  - Delivery Projects: {ServiceDeliveryProject.objects.count()}')
        self.stdout.write(f'  - Host Employers: {HostEmployer.objects.count()}')
