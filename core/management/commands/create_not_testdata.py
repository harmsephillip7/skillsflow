"""
Management command to create test data for the NOT (Notification of Training) section.
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import (
    User, TrainingNotification, NOTStakeholder, 
    NOTResourceRequirement, NOTDeliverable, NOTMeetingMinutes
)
from tenants.models import Campus


class Command(BaseCommand):
    help = 'Creates test data for the NOT (Notification of Training) section'

    def handle(self, *args, **options):
        self.stdout.write('Creating NOT test data...')
        
        # Get or create required objects
        campus = Campus.objects.first()
        if not campus:
            self.stdout.write(self.style.ERROR('No campus found. Please create a campus first.'))
            return
        
        # Get admin user
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(self.style.ERROR('No admin user found.'))
            return
        
        # Create additional test users for stakeholders
        test_users = []
        user_roles = [
            ('academic.manager@skillsflow.co.za', 'Academic', 'Manager'),
            ('finance.manager@skillsflow.co.za', 'Finance', 'Manager'),
            ('sales.rep@skillsflow.co.za', 'Sales', 'Representative'),
            ('recruitment@skillsflow.co.za', 'Recruitment', 'Officer'),
            ('logistics@skillsflow.co.za', 'Logistics', 'Coordinator'),
            ('facilitator1@skillsflow.co.za', 'John', 'Facilitator'),
            ('facilitator2@skillsflow.co.za', 'Sarah', 'Trainer'),
        ]
        
        for email, first_name, last_name in user_roles:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_active': True,
                }
            )
            if created:
                user.set_password('testpass123')
                user.save()
            test_users.append(user)
        
        self.stdout.write(f'  Created/found {len(test_users)} test users')
        
        # Project templates for realistic data
        projects = [
            {
                'title': 'Mining Operations Learnership Programme 2025',
                'project_type': 'OC_LEARNERSHIP',
                'funder': 'CORPORATE_DG',
                'client_name': 'Anglo American Platinum',
                'expected_learner_count': 50,
                'contract_value': Decimal('2500000.00'),
                'status': 'IN_PROGRESS',
                'priority': 'HIGH',
            },
            {
                'title': 'Electrical Engineering Apprenticeship',
                'project_type': 'OC_APPRENTICESHIP',
                'funder': 'PRIVATE',
                'client_name': 'Eskom Holdings',
                'expected_learner_count': 30,
                'contract_value': Decimal('1800000.00'),
                'status': 'APPROVED',
                'priority': 'MEDIUM',
            },
            {
                'title': 'Business Administration Skills Programme',
                'project_type': 'SKILLS_PROGRAMME',
                'funder': 'CORPORATE',
                'client_name': 'Standard Bank',
                'expected_learner_count': 100,
                'contract_value': Decimal('950000.00'),
                'status': 'PLANNING',
                'priority': 'MEDIUM',
            },
            {
                'title': 'Municipal Water Treatment Training',
                'project_type': 'SHORT_COURSE',
                'funder': 'MUNICIPALITY',
                'client_name': 'City of Johannesburg',
                'expected_learner_count': 25,
                'contract_value': Decimal('450000.00'),
                'status': 'PENDING_APPROVAL',
                'priority': 'HIGH',
            },
            {
                'title': 'Youth Employment Programme - Retail Sector',
                'project_type': 'OC_LEARNERSHIP',
                'funder': 'GOVERNMENT',
                'client_name': 'Department of Labour',
                'expected_learner_count': 200,
                'contract_value': Decimal('5000000.00'),
                'status': 'IN_PROGRESS',
                'priority': 'URGENT',
            },
            {
                'title': 'IT Support Technician Learnership',
                'project_type': 'OC_LEARNERSHIP',
                'funder': 'CORPORATE_DG',
                'client_name': 'MTN South Africa',
                'expected_learner_count': 40,
                'contract_value': Decimal('1200000.00'),
                'status': 'APPROVED',
                'priority': 'MEDIUM',
            },
            {
                'title': 'Healthcare Worker Training Programme',
                'project_type': 'SKILLS_PROGRAMME',
                'funder': 'GOVERNMENT',
                'client_name': 'Department of Health',
                'expected_learner_count': 150,
                'contract_value': Decimal('3500000.00'),
                'status': 'DRAFT',
                'priority': 'HIGH',
            },
            {
                'title': 'Financial Services Compliance Training',
                'project_type': 'SHORT_COURSE',
                'funder': 'CORPORATE',
                'client_name': 'Nedbank Limited',
                'expected_learner_count': 60,
                'contract_value': Decimal('720000.00'),
                'status': 'PLANNING',
                'priority': 'LOW',
            },
            {
                'title': 'Automotive Mechanics Apprenticeship',
                'project_type': 'LEGACY_APPRENTICESHIP',
                'funder': 'PRIVATE',
                'client_name': 'Toyota South Africa',
                'expected_learner_count': 20,
                'contract_value': Decimal('900000.00'),
                'status': 'IN_PROGRESS',
                'priority': 'MEDIUM',
            },
            {
                'title': 'Hospitality Management Programme',
                'project_type': 'LEGACY_LEARNERSHIP',
                'funder': 'CORPORATE_DG',
                'client_name': 'Sun International',
                'expected_learner_count': 35,
                'contract_value': Decimal('680000.00'),
                'status': 'COMPLETED',
                'priority': 'LOW',
            },
            {
                'title': 'Construction Safety Awareness',
                'project_type': 'SHORT_COURSE',
                'funder': 'CORPORATE',
                'client_name': 'Murray & Roberts',
                'expected_learner_count': 80,
                'contract_value': Decimal('320000.00'),
                'status': 'PENDING_APPROVAL',
                'priority': 'MEDIUM',
            },
            {
                'title': 'Telecommunications Network Engineer',
                'project_type': 'OC_APPRENTICESHIP',
                'funder': 'CORPORATE_DG',
                'client_name': 'Vodacom',
                'expected_learner_count': 25,
                'contract_value': Decimal('1500000.00'),
                'status': 'APPROVED',
                'priority': 'HIGH',
            },
        ]
        
        delivery_modes = ['ON_CAMPUS', 'OFF_SITE', 'ONLINE', 'BLENDED', 'WORKPLACE']
        learner_sources = ['NEW_RECRUITMENT', 'CLIENT_PROVIDED', 'EXISTING_PIPELINE', 'MIXED']
        
        created_nots = []
        for project_data in projects:
            start_date = timezone.now().date() + timedelta(days=random.randint(-60, 60))
            
            not_obj, created = TrainingNotification.objects.get_or_create(
                title=project_data['title'],
                defaults={
                    'project_type': project_data['project_type'],
                    'funder': project_data['funder'],
                    'client_name': project_data['client_name'],
                    'description': f"Training programme for {project_data['client_name']} covering essential skills development and certification.",
                    'status': project_data['status'],
                    'priority': project_data['priority'],
                    'expected_learner_count': project_data['expected_learner_count'],
                    'contract_value': project_data['contract_value'],
                    'learner_source': random.choice(learner_sources),
                    'planned_start_date': start_date,
                    'planned_end_date': start_date + timedelta(days=random.randint(90, 365)),
                    'duration_months': random.randint(3, 12),
                    'delivery_mode': random.choice(delivery_modes),
                    'delivery_campus': campus,
                    'planning_meeting_date': timezone.now() + timedelta(days=random.randint(1, 30)) if project_data['status'] in ['PLANNING', 'IN_MEETING'] else None,
                    'planning_meeting_venue': random.choice(['Conference Room A', 'Board Room', 'Training Centre', 'Client Offices', 'Virtual (MS Teams)']),
                    'created_by': admin_user,
                }
            )
            created_nots.append(not_obj)
            
            if created:
                self.stdout.write(f'  Created NOT: {not_obj.reference_number}')
        
        self.stdout.write(f'  Created/found {len(created_nots)} Training Notifications')
        
        # Create stakeholders for each NOT
        stakeholder_count = 0
        department_roles = {
            'EXECUTIVE': ['Project Sponsor', 'Executive Oversight', 'Final Sign-off'],
            'ACADEMIC': ['Curriculum Design', 'Training Delivery', 'Assessment Management'],
            'FINANCE': ['Budget Management', 'Invoice Processing', 'Financial Reporting'],
            'SALES': ['Client Relationship', 'Contract Negotiation', 'Upselling'],
            'RECRUITMENT': ['Learner Selection', 'Documentation', 'Onboarding'],
            'LOGISTICS': ['Venue Coordination', 'Resource Allocation', 'Schedule Management'],
            'QA': ['Quality Assurance', 'Compliance Monitoring', 'Audit Preparation'],
            'CLIENT': ['Client Representative', 'Learner Supervision', 'Feedback Provider'],
        }
        
        for not_obj in created_nots:
            # Add 3-5 stakeholders per NOT
            num_stakeholders = random.randint(3, 5)
            selected_users = random.sample(test_users + [admin_user], min(num_stakeholders, len(test_users) + 1))
            
            for i, user in enumerate(selected_users):
                dept = random.choice(['EXECUTIVE', 'ACADEMIC', 'FINANCE', 'SALES', 'RECRUITMENT', 'LOGISTICS', 'QUALITY', 'COMPLIANCE'])
                role = random.choice(['PROJECT_LEAD', 'PROJECT_MANAGER', 'FACILITATOR', 'ASSESSOR', 'RECRUITER', 'FINANCE_LEAD', 'LOGISTICS_LEAD'])
                
                stakeholder, created = NOTStakeholder.objects.get_or_create(
                    training_notification=not_obj,
                    user=user,
                    defaults={
                        'department': dept,
                        'role_in_project': role,
                        'responsibilities': random.choice(department_roles.get(dept, ['General Support'])),
                        'invited_to_meeting': True,
                        'attended_meeting': random.choice([True, False]),
                        'notification_sent': i == 0,
                        'created_by': admin_user,
                    }
                )
                if created:
                    stakeholder_count += 1
        
        self.stdout.write(f'  Created {stakeholder_count} stakeholders')
        
        # Create resource requirements
        resource_count = 0
        resource_types = [
            ('FACILITATOR', 'Facilitator', 1, 3),
            ('ASSESSOR', 'Assessor', 1, 2),
            ('MODERATOR', 'Moderator', 1, 1),
            ('VENUE', 'Training Venue', 1, 2),
            ('EQUIPMENT', 'Training Equipment', 5, 20),
            ('MATERIALS', 'Learning Materials', 10, 100),
            ('SOFTWARE', 'Computers/Laptops', 10, 50),
        ]
        
        for not_obj in created_nots:
            # Add 2-4 resource requirements per NOT
            num_resources = random.randint(2, 4)
            selected_resources = random.sample(resource_types, num_resources)
            
            for res_type, description, min_qty, max_qty in selected_resources:
                required = random.randint(min_qty, max_qty)
                available = random.randint(0, required + 2)
                
                resource, created = NOTResourceRequirement.objects.get_or_create(
                    training_notification=not_obj,
                    resource_type=res_type,
                    defaults={
                        'description': f"{description} for {not_obj.title}",
                        'quantity_required': required,
                        'quantity_available': available,
                        'is_available': available >= required,
                        'status': 'AVAILABLE' if available >= required else 'REQUIRED',
                        'procurement_notes': f"Requirement based on {not_obj.expected_learner_count} learners",
                        'created_by': admin_user,
                    }
                )
                if created:
                    resource_count += 1
        
        self.stdout.write(f'  Created {resource_count} resource requirements')
        
        # Create deliverables
        deliverable_count = 0
        deliverable_templates = [
            ('Project Charter', 'SUBMISSION', 'Complete project charter document'),
            ('Training Schedule', 'MILESTONE', 'Finalized training schedule and calendar'),
            ('Learner Registration', 'REGISTRATION', 'Complete learner registration on SETA systems'),
            ('Learning Materials', 'MILESTONE', 'Prepare and distribute learning materials'),
            ('Assessment Pack', 'SUBMISSION', 'Complete assessment documentation'),
            ('Venue Setup', 'MILESTONE', 'Training venue ready and equipped'),
            ('Equipment Check', 'MILESTONE', 'All training equipment tested and ready'),
            ('Progress Report', 'REPORT', 'Monthly progress report submission'),
            ('POE Collection', 'SUBMISSION', 'Portfolio of Evidence collection'),
            ('Final Assessment', 'ASSESSMENT', 'Complete all summative assessments'),
            ('Certification', 'CERTIFICATION', 'Process learner certifications'),
            ('Project Closeout', 'REPORT', 'Final project closeout report'),
        ]
        
        for not_obj in created_nots:
            # Add 4-8 deliverables per NOT
            num_deliverables = random.randint(4, 8)
            selected_deliverables = random.sample(deliverable_templates, num_deliverables)
            base_date = timezone.now().date()
            
            for i, (title, del_type, desc) in enumerate(selected_deliverables):
                due = base_date + timedelta(days=i * 14 + random.randint(-7, 14))
                is_completed = random.random() < 0.3
                status = 'COMPLETED' if is_completed else random.choice(['PENDING', 'IN_PROGRESS'])
                
                deliverable, created = NOTDeliverable.objects.get_or_create(
                    training_notification=not_obj,
                    title=title,
                    defaults={
                        'deliverable_type': del_type,
                        'description': desc,
                        'due_date': due,
                        'responsible_department': random.choice(['ACADEMIC', 'FINANCE', 'RECRUITMENT', 'LOGISTICS', 'QUALITY']),
                        'status': status,
                        'completed_date': due - timedelta(days=random.randint(1, 5)) if is_completed else None,
                        'notes': f"Deliverable for {not_obj.reference_number}",
                        'created_by': admin_user,
                    }
                )
                if created:
                    deliverable_count += 1
        
        self.stdout.write(f'  Created {deliverable_count} deliverables')
        
        # Create some meeting minutes for projects in planning or further
        minutes_count = 0
        for not_obj in created_nots:
            if not_obj.status not in ['DRAFT']:
                # Check if meeting minutes already exists
                existing_minutes = NOTMeetingMinutes.objects.filter(
                    training_notification=not_obj,
                    meeting_type='PLANNING'
                ).first()
                
                if not existing_minutes:
                    minutes = NOTMeetingMinutes.objects.create(
                        training_notification=not_obj,
                        meeting_type='PLANNING',
                        meeting_date=timezone.now() - timedelta(days=random.randint(1, 30)),
                        agenda=f"1. Project Overview\n2. Resource Planning\n3. Timeline Discussion\n4. Risk Assessment\n5. Action Items",
                        minutes=f"Discussed project scope and requirements for {not_obj.title}. Identified key milestones and resource needs.",
                        decisions="Approved timeline and resource allocation. Assigned project roles.",
                        action_items=f"1. Finalize learner recruitment plan\n2. Confirm venue availability\n3. Prepare training materials\n4. Schedule assessment dates",
                        next_meeting_date=timezone.now() + timedelta(days=random.randint(7, 30)),
                        created_by=admin_user,
                    )
                    # Add attendees through M2M
                    attendees = random.sample(test_users, min(4, len(test_users)))
                    minutes.attendees.set(attendees)
                    minutes_count += 1
        
        self.stdout.write(f'  Created {minutes_count} meeting minutes')
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'''
╔══════════════════════════════════════════════════════════╗
║          NOT TEST DATA CREATED SUCCESSFULLY              ║
╠══════════════════════════════════════════════════════════╣
║  Training Notifications: {len(created_nots):>4}                            ║
║  Stakeholders:           {stakeholder_count:>4}                            ║
║  Resource Requirements:  {resource_count:>4}                            ║
║  Deliverables:           {deliverable_count:>4}                            ║
║  Meeting Minutes:        {minutes_count:>4}                            ║
╠══════════════════════════════════════════════════════════╣
║  View dashboard: http://localhost:8000/not/dashboard/    ║
╚══════════════════════════════════════════════════════════╝
'''))
