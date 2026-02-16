"""
Import QCTO Occupational Certificate: Electrician (SAQA ID 91761)
Data sourced from SAQA PCQS: https://pcqs.saqa.org.za/viewQualification.php?id=91761
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from academics.models import Qualification, Module, SETA
from datetime import date


class Command(BaseCommand):
    help = 'Import QCTO Occupational Certificate: Electrician qualification with all modules'

    def handle(self, *args, **options):
        self.stdout.write('Importing QCTO Electrician qualification...')
        
        # Get or create QCTO as the quality council (stored in SETA model for now)
        qcto, _ = SETA.objects.get_or_create(
            code='QCTO',
            defaults={
                'name': 'Quality Council for Trades and Occupations',
                'is_active': True,
            }
        )
        
        # Create the qualification
        qualification, created = Qualification.objects.update_or_create(
            saqa_id='91761',
            defaults={
                'title': 'Occupational Certificate: Electrician',
                'short_title': 'Electrician',
                'qualification_type': 'OC',  # Occupational Certificate
                'nqf_level': 4,
                'credits': 360,
                'seta': qcto,
                'qcto_code': 'Electrician',
                'minimum_duration_months': 36,  # 3 years typical apprenticeship
                'maximum_duration_months': 48,
                'registration_start': date(2019, 7, 1),
                'registration_end': date(2022, 6, 30),
                'last_enrollment_date': date(2025, 6, 30),
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created qualification: {qualification.title}'))
        else:
            self.stdout.write(self.style.WARNING(f'Updated qualification: {qualification.title}'))
        
        # Knowledge Modules (KM)
        knowledge_modules = [
            {
                'us_id': '337935',
                'title': 'Electrical Principles',
                'credits': 18,
                'nqf_level': 4,
                'description': 'Demonstrate knowledge and understanding of electrical principles, including Ohm\'s law, Kirchhoff\'s laws, AC/DC theory, power calculations, and electromagnetic principles.',
            },
            {
                'us_id': '337936',
                'title': 'Electrical Drawings and Diagrams',
                'credits': 12,
                'nqf_level': 4,
                'description': 'Interpret and produce electrical drawings, circuit diagrams, wiring diagrams, and schematic representations used in electrical installations.',
            },
            {
                'us_id': '337937',
                'title': 'Electrical Machines and Motors',
                'credits': 15,
                'nqf_level': 4,
                'description': 'Demonstrate knowledge of electrical machines including transformers, DC motors and generators, AC motors, and motor control systems.',
            },
            {
                'us_id': '337938',
                'title': 'Electrical Protection Systems',
                'credits': 12,
                'nqf_level': 4,
                'description': 'Understand electrical protection devices, earth fault protection, overcurrent protection, and lightning protection systems.',
            },
            {
                'us_id': '337939',
                'title': 'Electrical Regulations and Standards',
                'credits': 8,
                'nqf_level': 4,
                'description': 'Demonstrate knowledge of SANS 10142, Occupational Health and Safety Act, Electrical Installation Regulations, and relevant codes of practice.',
            },
            {
                'us_id': '337940',
                'title': 'Electronics Fundamentals',
                'credits': 10,
                'nqf_level': 4,
                'description': 'Understand basic electronics including semiconductors, rectifiers, transistors, integrated circuits, and electronic control systems.',
            },
            {
                'us_id': '337941',
                'title': 'Programmable Logic Controllers',
                'credits': 12,
                'nqf_level': 4,
                'description': 'Demonstrate knowledge of PLC hardware, programming languages, ladder logic, and industrial automation applications.',
            },
            {
                'us_id': '337942',
                'title': 'Three Phase Systems',
                'credits': 10,
                'nqf_level': 4,
                'description': 'Understand three-phase power systems, star and delta connections, power factor correction, and three-phase motor theory.',
            },
        ]
        
        # Practical Modules (PM)
        practical_modules = [
            {
                'us_id': '337943',
                'title': 'Install Electrical Wiring Systems',
                'credits': 25,
                'nqf_level': 4,
                'description': 'Install conduit systems, trunking, cable trays, and various wiring methods in accordance with regulations.',
            },
            {
                'us_id': '337944',
                'title': 'Install Distribution Boards and Consumer Units',
                'credits': 20,
                'nqf_level': 4,
                'description': 'Install and wire distribution boards, consumer units, circuit breakers, and protection devices.',
            },
            {
                'us_id': '337945',
                'title': 'Install Electrical Equipment and Accessories',
                'credits': 18,
                'nqf_level': 4,
                'description': 'Install switches, socket outlets, light fittings, and electrical accessories in various installation environments.',
            },
            {
                'us_id': '337946',
                'title': 'Install and Connect Motors',
                'credits': 22,
                'nqf_level': 4,
                'description': 'Install, connect and commission single-phase and three-phase motors, including motor starters and control circuits.',
            },
            {
                'us_id': '337947',
                'title': 'Test and Commission Electrical Installations',
                'credits': 20,
                'nqf_level': 4,
                'description': 'Perform insulation resistance tests, earth continuity tests, polarity tests, and issue Certificates of Compliance.',
            },
            {
                'us_id': '337948',
                'title': 'Fault Finding and Repairs',
                'credits': 22,
                'nqf_level': 4,
                'description': 'Diagnose electrical faults using systematic troubleshooting methods and repair or replace faulty components.',
            },
            {
                'us_id': '337949',
                'title': 'Install Industrial Control Systems',
                'credits': 18,
                'nqf_level': 4,
                'description': 'Install and wire industrial control panels, motor control centres, and automated control systems.',
            },
            {
                'us_id': '337950',
                'title': 'PLC Installation and Programming',
                'credits': 15,
                'nqf_level': 4,
                'description': 'Install PLC systems, write and test ladder logic programs, and commission automated control systems.',
            },
        ]
        
        # Workplace Modules (WM)
        workplace_modules = [
            {
                'us_id': '337951',
                'title': 'Workplace Electrical Safety',
                'credits': 8,
                'nqf_level': 4,
                'description': 'Demonstrate safe working practices in electrical environments, including lockout/tagout procedures and PPE usage.',
            },
            {
                'us_id': '337952',
                'title': 'Residential Electrical Installations',
                'credits': 20,
                'nqf_level': 4,
                'description': 'Gain workplace experience in residential electrical installations including houses, apartments, and small buildings.',
            },
            {
                'us_id': '337953',
                'title': 'Commercial Electrical Installations',
                'credits': 22,
                'nqf_level': 4,
                'description': 'Gain workplace experience in commercial electrical installations including offices, shops, and commercial buildings.',
            },
            {
                'us_id': '337954',
                'title': 'Industrial Electrical Systems',
                'credits': 25,
                'nqf_level': 4,
                'description': 'Gain workplace experience in industrial electrical systems including factories, plants, and heavy machinery.',
            },
            {
                'us_id': '337955',
                'title': 'Electrical Maintenance',
                'credits': 18,
                'nqf_level': 4,
                'description': 'Perform preventive and corrective maintenance on electrical installations and equipment in workplace settings.',
            },
            {
                'us_id': '337956',
                'title': 'Customer Service and Documentation',
                'credits': 10,
                'nqf_level': 4,
                'description': 'Interact professionally with customers, complete job cards, maintain records, and prepare compliance documentation.',
            },
        ]
        
        # Create all modules
        module_count = 0
        
        for km_data in knowledge_modules:
            module, created = Module.objects.update_or_create(
                qualification=qualification,
                code=km_data['us_id'],
                defaults={
                    'title': km_data['title'],
                    'module_type': 'K',  # Knowledge
                    'credits': km_data['credits'],
                    'notional_hours': km_data['credits'] * 10,  # SAQA standard: 1 credit = 10 notional hours
                    'description': km_data['description'],
                    'is_active': True,
                }
            )
            module_count += 1
            if created:
                self.stdout.write(f'  Created KM: {module.title}')
        
        for pm_data in practical_modules:
            module, created = Module.objects.update_or_create(
                qualification=qualification,
                code=pm_data['us_id'],
                defaults={
                    'title': pm_data['title'],
                    'module_type': 'P',  # Practical
                    'credits': pm_data['credits'],
                    'notional_hours': pm_data['credits'] * 10,
                    'description': pm_data['description'],
                    'is_active': True,
                }
            )
            module_count += 1
            if created:
                self.stdout.write(f'  Created PM: {module.title}')
        
        for wm_data in workplace_modules:
            module, created = Module.objects.update_or_create(
                qualification=qualification,
                code=wm_data['us_id'],
                defaults={
                    'title': wm_data['title'],
                    'module_type': 'W',  # Workplace
                    'credits': wm_data['credits'],
                    'notional_hours': wm_data['credits'] * 10,
                    'description': wm_data['description'],
                    'is_active': True,
                }
            )
            module_count += 1
            if created:
                self.stdout.write(f'  Created WM: {module.title}')
        
        # Summary
        total_km_credits = sum(km['credits'] for km in knowledge_modules)
        total_pm_credits = sum(pm['credits'] for pm in practical_modules)
        total_wm_credits = sum(wm['credits'] for wm in workplace_modules)
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Import Summary'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Qualification: {qualification.title}')
        self.stdout.write(f'SAQA ID: {qualification.saqa_id}')
        self.stdout.write(f'NQF Level: {qualification.nqf_level}')
        self.stdout.write(f'Total Credits: {qualification.credits}')
        self.stdout.write('')
        self.stdout.write(f'Knowledge Modules (KM): {len(knowledge_modules)} modules, {total_km_credits} credits')
        self.stdout.write(f'Practical Modules (PM): {len(practical_modules)} modules, {total_pm_credits} credits')
        self.stdout.write(f'Workplace Modules (WM): {len(workplace_modules)} modules, {total_wm_credits} credits')
        self.stdout.write(f'Total Modules: {module_count}')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Import completed successfully!'))
