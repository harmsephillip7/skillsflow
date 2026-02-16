"""
Management command to create WSP/ATR service test data.
Creates service years, training committees, meetings, and documents for testing.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import random

from corporate.models import (
    CorporateClient, CorporateContact, ServiceCategory, ServiceOffering,
    ClientServiceSubscription, WSPATRServiceYear, WSPATRDocument,
    WSPATREmployeeData, TrainingCommittee, TrainingCommitteeMember,
    TrainingCommitteeMeeting, TCMeetingAgendaItem, TCMeetingAttendance,
    TCMeetingActionItem
)
from core.models import User
from tenants.models import Brand, Campus
from learners.models import SETA


class Command(BaseCommand):
    help = 'Create WSP/ATR service test data for corporate module'

    def handle(self, *args, **options):
        self.stdout.write('Creating WSP/ATR test data...')
        
        # Get default campus
        campus = Campus.objects.first()
        if not campus:
            self.stdout.write(self.style.ERROR('No campus found. Please run create_corporate_testdata first.'))
            return
        
        self.stdout.write(f'  Using campus: {campus.name}')
        
        # Get or create test user
        user, _ = User.objects.get_or_create(
            email='wspatr@skillsflow.co.za',
            defaults={
                'first_name': 'WSP/ATR',
                'last_name': 'Consultant',
                'is_staff': True,
            }
        )
        if _:
            user.set_password('testpass123')
            user.save()
        
        # Get or create SETA
        seta, _ = SETA.objects.get_or_create(
            code='MICT',
            defaults={
                'name': 'Media, Information and Communication Technologies SETA',
                'is_active': True
            }
        )
        
        # Get WSP/ATR service category and offering
        wsp_category, _ = ServiceCategory.objects.get_or_create(
            code='WSP_ATR',
            defaults={
                'name': 'WSP/ATR Services',
                'display_order': 1,
                'is_active': True
            }
        )
        
        wsp_service, _ = ServiceOffering.objects.get_or_create(
            code='WSPATR-001',
            defaults={
                'name': 'WSP/ATR Bundle',
                'category': wsp_category,
                'service_type': 'WSP_ATR',
                'description': 'Combined WSP and ATR service package',
                'base_price': Decimal('22000.00'),
                'billing_type': 'ANNUAL',
                'is_active': True
            }
        )
        
        # Get active clients or create test ones
        clients = list(CorporateClient.objects.filter(status='ACTIVE')[:10])
        
        if len(clients) < 3:
            self.stdout.write('  Creating additional test clients...')
            client_names = [
                ('Sunrise Manufacturing', 'Manufacturing'),
                ('Coastal Logistics', 'Transport & Logistics'),
                ('Peak Financial Services', 'Financial Services'),
                ('Metro Healthcare Group', 'Healthcare'),
                ('TechVenture Innovations', 'Information Technology'),
            ]
            
            for company_name, industry in client_names:
                client, _ = CorporateClient.objects.get_or_create(
                    company_name=company_name,
                    campus=campus,
                    defaults={
                        'campus': campus,
                        'trading_name': company_name.split()[0],
                        'registration_number': f'2020/{random.randint(100000,999999)}/07',
                        'phone': f'011 {random.randint(100,999)} {random.randint(1000,9999)}',
                        'email': f'info@{company_name.lower().replace(" ", "")}.co.za',
                        'physical_address': f'{random.randint(1,999)} Business Park, Johannesburg',
                        'industry': industry,
                        'seta': seta,
                        'employee_count': random.randint(100, 5000),
                        'status': 'ACTIVE',
                        'client_tier': random.choice(['STRATEGIC', 'KEY', 'STANDARD']),
                    }
                )
                clients.append(client)
        
        # Create WSP/ATR subscriptions and service years
        self.stdout.write('Creating WSP/ATR subscriptions and service years...')
        
        current_fy = 2025  # Financial year starting May 2025
        
        for client in clients[:7]:  # Process first 7 clients
            # Ensure client has SETA set
            if not client.seta:
                client.seta = seta
                client.save()
            
            # Create or get subscription
            subscription, sub_created = ClientServiceSubscription.objects.get_or_create(
                client=client,
                service=wsp_service,
                campus=campus,
                defaults={
                    'campus': campus,
                    'status': 'ACTIVE',
                    'start_date': date(current_fy - 1, 5, 1),
                    'renewal_date': date(current_fy, 5, 1),
                    'agreed_price': wsp_service.base_price,
                    'assigned_consultant': user,
                }
            )
            
            if sub_created:
                self.stdout.write(f'    Created subscription for {client.company_name}')
            
            # Create service years (current and previous)
            for fy in [current_fy - 1, current_fy]:
                service_year, year_created = WSPATRServiceYear.objects.get_or_create(
                    subscription=subscription,
                    financial_year=fy,
                    defaults={
                        'client': client,
                        'campus': campus,
                        'submission_deadline': date(fy + 1, 4, 30),
                        'status': 'COMPLETED' if fy < current_fy else random.choice(['DATA_COLLECTION', 'DRAFTING', 'INTERNAL_REVIEW']),
                        'outcome': 'APPROVED' if fy < current_fy else 'PENDING',
                        'seta': seta,
                        'assigned_consultant': user,
                        'progress_percentage': 100 if fy < current_fy else random.randint(20, 70),
                    }
                )
                
                if year_created:
                    self.stdout.write(f'    Created service year FY{fy}/{fy+1} for {client.company_name}')
                    
                    # Add employee data
                    self._create_employee_data(service_year)
                    
                    # Create WSP/ATR documents
                    self._create_documents(service_year, fy < current_fy)
            
            # Create Training Committee
            committee, comm_created = TrainingCommittee.objects.get_or_create(
                client=client,
                campus=campus,
                defaults={
                    'campus': campus,
                    'name': f'{client.company_name} Training Committee',
                    'establishment_date': date(current_fy - 2, 1, 15),
                    'is_active': True,
                }
            )
            
            if comm_created:
                self.stdout.write(f'    Created training committee for {client.company_name}')
                # Add committee members
                self._create_committee_members(committee, client, campus)
            
            # Create committee meetings
            current_service_year = WSPATRServiceYear.objects.filter(
                subscription=subscription, 
                financial_year=current_fy
            ).first()
            
            if current_service_year:
                self._create_committee_meetings(committee, current_service_year, user)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\nWSP/ATR test data created successfully!'))
        self.stdout.write(f'  - WSP/ATR Subscriptions: {ClientServiceSubscription.objects.filter(service__service_type="WSP_ATR").count()}')
        self.stdout.write(f'  - Service Years: {WSPATRServiceYear.objects.count()}')
        self.stdout.write(f'  - Training Committees: {TrainingCommittee.objects.count()}')
        self.stdout.write(f'  - Committee Members: {TrainingCommitteeMember.objects.count()}')
        self.stdout.write(f'  - Committee Meetings: {TrainingCommitteeMeeting.objects.count()}')
        self.stdout.write(f'  - WSP/ATR Documents: {WSPATRDocument.objects.count()}')
        self.stdout.write(f'  - Employee Data Records: {WSPATREmployeeData.objects.count()}')
    
    def _create_employee_data(self, service_year):
        """Create sample employee headcount data by occupational level."""
        occupational_levels = [
            ('TOP_MANAGEMENT', 'Top Management'),
            ('SENIOR_MANAGEMENT', 'Senior Management'),
            ('PROFESSIONALLY_QUALIFIED', 'Professionally Qualified'),
            ('SKILLED_TECHNICAL', 'Skilled Technical'),
            ('SEMI_SKILLED', 'Semi-Skilled'),
            ('UNSKILLED', 'Unskilled'),
        ]
        
        for level_code, level_name in occupational_levels:
            # Random distribution of employees
            total = random.randint(10, 200)
            
            WSPATREmployeeData.objects.get_or_create(
                service_year=service_year,
                occupational_level=level_code,
                defaults={
                    'african_male': int(total * random.uniform(0.15, 0.35)),
                    'african_female': int(total * random.uniform(0.15, 0.30)),
                    'coloured_male': int(total * random.uniform(0.05, 0.15)),
                    'coloured_female': int(total * random.uniform(0.05, 0.15)),
                    'indian_male': int(total * random.uniform(0.03, 0.10)),
                    'indian_female': int(total * random.uniform(0.03, 0.10)),
                    'white_male': int(total * random.uniform(0.05, 0.15)),
                    'white_female': int(total * random.uniform(0.05, 0.10)),
                    'foreign_male': int(total * random.uniform(0.01, 0.05)),
                    'foreign_female': int(total * random.uniform(0.01, 0.05)),
                    'disabled_male': int(total * random.uniform(0.01, 0.03)),
                    'disabled_female': int(total * random.uniform(0.01, 0.03)),
                }
            )
    
    def _create_documents(self, service_year, completed=False):
        """Create standard WSP/ATR document requirements."""
        document_types = [
            ('SDL_CERTIFICATE', 'SDL Certificate', True),
            ('COMPANY_REGISTRATION', 'Company Registration (CIPC)', True),
            ('BEE_CERTIFICATE', 'B-BBEE Certificate', True),
            ('EMPLOYEE_LIST', 'Employee List/Headcount', True),
            ('TRAINING_PLAN', 'Training Plan', True),
            ('TRAINING_BUDGET', 'Training Budget', True),
            ('COMMITTEE_MINUTES', 'Training Committee Minutes', True),
            ('COMMITTEE_ATTENDANCE', 'Training Committee Attendance Register', True),
            ('SIGNED_WSP', 'Signed WSP Document', False),
            ('SIGNED_ATR', 'Signed ATR Document', False),
            ('APPROVAL_LETTER', 'SETA Approval Letter', False),
        ]
        
        for doc_type, doc_name, is_required in document_types:
            # For completed years, all required docs are uploaded
            # For current year, random upload status
            has_file = completed or (is_required and random.choice([True, True, False]))
            
            WSPATRDocument.objects.get_or_create(
                service_year=service_year,
                document_type=doc_type,
                defaults={
                    'campus': service_year.campus,
                    'name': doc_name,
                    'is_required': is_required,
                    'status': 'UPLOADED' if has_file else 'PENDING',
                    # Note: Not actually uploading files, just setting status
                }
            )
    
    def _create_committee_members(self, committee, client, campus):
        """Create training committee members from client contacts."""
        roles = [
            ('CHAIRPERSON', 'Chairperson'),
            ('SECRETARY', 'Secretary'),
            ('SDF', 'Skills Development Facilitator'),
            ('EMPLOYER_REP', 'Employer Representative'),
            ('EMPLOYER_REP', 'Employer Representative'),
            ('EMPLOYEE_REP', 'Employee Representative'),
            ('EMPLOYEE_REP', 'Employee Representative'),
            ('UNION_REP', 'Union Representative'),
        ]
        
        first_names = ['John', 'Sarah', 'Michael', 'Lisa', 'David', 'Emma', 'James', 'Thabo']
        last_names = ['Smith', 'Johnson', 'Mokoena', 'Van der Berg', 'Naidoo', 'Williams']
        
        for i, (role_code, role_name) in enumerate(roles):
            first_name = first_names[i % len(first_names)]
            last_name = last_names[i % len(last_names)]
            
            # Create or get contact
            contact, _ = CorporateContact.objects.get_or_create(
                client=client,
                email=f'{first_name.lower()}.{last_name.lower()}@{client.email.split("@")[1]}',
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'job_title': role_name if role_code != 'SDF' else 'Skills Development Facilitator',
                    'phone': f'08{random.randint(10000000, 99999999)}',
                    'is_primary': role_code == 'SDF',
                    'is_active': True,
                }
            )
            
            # Add to committee
            TrainingCommitteeMember.objects.get_or_create(
                committee=committee,
                contact=contact,
                campus=campus,
                defaults={
                    'campus': campus,
                    'role': role_code,
                    'is_active': True,
                    'appointed_date': date.today() - timedelta(days=random.randint(180, 720)),
                }
            )
    
    def _create_committee_meetings(self, committee, service_year, user):
        """Create quarterly committee meetings for the service year."""
        meeting_dates = [
            (date(service_year.financial_year, 5, 15), 'Q1 Training Committee Meeting'),
            (date(service_year.financial_year, 8, 15), 'Q2 Training Committee Meeting'),
            (date(service_year.financial_year, 11, 15), 'Q3 Training Committee Meeting'),
            (date(service_year.financial_year + 1, 2, 15), 'Q4 Training Committee Meeting'),
        ]
        
        today = date.today()
        
        for idx, (meeting_date, title) in enumerate(meeting_dates, 1):
            status = 'COMPLETED' if meeting_date < today else 'SCHEDULED'
            
            meeting, created = TrainingCommitteeMeeting.objects.get_or_create(
                committee=committee,
                service_year=service_year,
                scheduled_date=meeting_date,
                defaults={
                    'campus': committee.campus,
                    'title': title,
                    'meeting_number': idx,
                    'scheduled_time': timezone.now().time().replace(hour=10, minute=0),
                    'location': 'Boardroom / MS Teams',
                    'meeting_type': 'HYBRID',  # IN_PERSON, VIRTUAL, HYBRID
                    'status': status,
                    'actual_start_time': timezone.now().time().replace(hour=10, minute=0) if status == 'COMPLETED' else None,
                    'actual_end_time': timezone.now().time().replace(hour=12, minute=0) if status == 'COMPLETED' else None,
                    'organized_by': user,
                }
            )
            
            if created:
                # Add agenda items
                agenda_items = [
                    'Opening and Welcome',
                    'Confirmation of Previous Minutes',
                    'Matters Arising',
                    'Training Progress Report',
                    'WSP/ATR Update',
                    'Budget Review',
                    'New Training Requests',
                    'General',
                    'Closure',
                ]
                
                for seq, item in enumerate(agenda_items, 1):
                    TCMeetingAgendaItem.objects.create(
                        meeting=meeting,
                        title=item,
                        sequence=seq,
                        duration_minutes=random.choice([5, 10, 15, 20]),
                    )
                
                # Add attendance for completed meetings
                if status == 'COMPLETED':
                    for member in committee.members.filter(is_active=True):
                        attendance_status = random.choice(['ATTENDED', 'ATTENDED', 'ATTENDED', 'APOLOGIES'])  # 75% attendance
                        TCMeetingAttendance.objects.create(
                            meeting=meeting,
                            member=member,
                            status=attendance_status,
                            invite_sent=True,
                            apology_reason='Unable to attend due to prior commitment' if attendance_status == 'APOLOGIES' else '',
                        )
                    
                    # Add action items - assign to a committee member
                    action_items = [
                        'Follow up on outstanding training records',
                        'Update employee skills audit',
                        'Confirm Q2 training budget allocation',
                        'Schedule learnership intake meeting',
                    ]
                    
                    members_list = list(committee.members.filter(is_active=True))
                    for item in random.sample(action_items, k=random.randint(1, 3)):
                        assigned_member = random.choice(members_list) if members_list else None
                        TCMeetingActionItem.objects.create(
                            meeting=meeting,
                            description=item,
                            assigned_to=assigned_member,
                            due_date=meeting_date + timedelta(days=random.randint(7, 30)),
                            status=random.choice(['COMPLETED', 'IN_PROGRESS', 'OPEN']),
                        )
