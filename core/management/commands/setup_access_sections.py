"""
Management command to create default access request sections.
"""
from django.core.management.base import BaseCommand
from core.models import AccessRequestSection, Role


class Command(BaseCommand):
    help = 'Create default access request sections for user registration'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing sections before creating new ones'
        )
    
    def handle(self, *args, **options):
        if options['reset']:
            deleted, _ = AccessRequestSection.objects.all().delete()
            self.stdout.write(f'Deleted {deleted} existing sections')
        
        sections = [
            {
                'code': 'LEARNER_MGMT',
                'name': 'Learner Management',
                'description': 'Access to view and manage learner records, enrollments, and progress',
                'icon': '👨‍🎓',
                'order': 1,
                'min_access_level': 'CAMPUS',
                'roles': ['CAMPUS_ADMIN', 'ENROLLMENT_OFFICER']
            },
            {
                'code': 'ACADEMIC',
                'name': 'Academic Administration',
                'description': 'Manage qualifications, curriculum, scheduling, and assessments',
                'icon': '📚',
                'order': 2,
                'min_access_level': 'CAMPUS',
                'roles': ['ACADEMIC_ADMIN', 'FACILITATOR']
            },
            {
                'code': 'FACILITATION',
                'name': 'Facilitation Portal',
                'description': 'Conduct training sessions, track attendance, and submit assessments',
                'icon': '👩‍🏫',
                'order': 3,
                'min_access_level': 'SELF',
                'roles': ['FACILITATOR']
            },
            {
                'code': 'ASSESSMENT',
                'name': 'Assessment & Moderation',
                'description': 'Conduct assessments, moderations, and manage POE',
                'icon': '📋',
                'order': 4,
                'min_access_level': 'SELF',
                'roles': ['ASSESSOR', 'MODERATOR']
            },
            {
                'code': 'CORPORATE',
                'name': 'Corporate Relations',
                'description': 'Manage corporate clients, workplace-based learning, and placements',
                'icon': '🏢',
                'order': 5,
                'min_access_level': 'CAMPUS',
                'roles': ['CORPORATE_LIAISON', 'WBL_COORDINATOR']
            },
            {
                'code': 'FINANCE',
                'name': 'Finance & Billing',
                'description': 'Access to financial records, invoicing, and payment management',
                'icon': '💰',
                'order': 6,
                'min_access_level': 'BRAND',
                'roles': ['FINANCE_MANAGER', 'FINANCE_ADMIN']
            },
            {
                'code': 'SALES',
                'name': 'Sales & CRM',
                'description': 'Manage leads, client relationships, and sales pipeline',
                'icon': '📈',
                'order': 7,
                'min_access_level': 'CAMPUS',
                'roles': ['SALES_REP', 'SALES_MANAGER']
            },
            {
                'code': 'HR',
                'name': 'Staff Management',
                'description': 'Manage staff records, contracts, and workforce planning',
                'icon': '👥',
                'order': 8,
                'min_access_level': 'BRAND',
                'roles': ['HR_MANAGER']
            },
            {
                'code': 'COMPLIANCE',
                'name': 'Compliance & Quality',
                'description': 'Accreditation management, compliance tracking, and audit preparation',
                'icon': '✅',
                'order': 9,
                'min_access_level': 'BRAND',
                'roles': ['QUALITY_ASSURANCE', 'COMPLIANCE_OFFICER']
            },
            {
                'code': 'REPORTS',
                'name': 'Reports & Analytics',
                'description': 'Access to organizational reports and data analytics dashboards',
                'icon': '📊',
                'order': 10,
                'min_access_level': 'CAMPUS',
                'roles': ['CAMPUS_ADMIN', 'HEAD_OFFICE_ADMIN']
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for section_data in sections:
            roles_codes = section_data.pop('roles')
            
            section, created = AccessRequestSection.objects.update_or_create(
                code=section_data['code'],
                defaults=section_data
            )
            
            # Link to roles if they exist
            roles = Role.objects.filter(code__in=roles_codes)
            if roles.exists():
                section.default_roles.set(roles)
            
            if created:
                created_count += 1
                self.stdout.write(f'  ✓ Created: {section.name}')
            else:
                updated_count += 1
                self.stdout.write(f'  ↻ Updated: {section.name}')
        
        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Created {created_count}, updated {updated_count} sections.'
        ))
