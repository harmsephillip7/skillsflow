"""
Create Implementation Plan for QCTO Occupational Certificate: Electrician (SAQA ID 91761)
Creates a 3-year full-time apprenticeship structure with alternating institutional and workplace phases.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from academics.models import Qualification, Module, ImplementationPlan, ImplementationPhase, ImplementationModuleSlot
from datetime import date


class Command(BaseCommand):
    help = 'Create Implementation Plan for QCTO Electrician qualification'

    def handle(self, *args, **options):
        self.stdout.write('Creating Electrician Implementation Plan...')
        
        # Get the Electrician qualification
        try:
            qualification = Qualification.objects.get(saqa_id='91761')
        except Qualification.DoesNotExist:
            self.stdout.write(self.style.ERROR('Electrician qualification not found. Run import_qcto_electrician first.'))
            return
        
        # Create the Implementation Plan
        plan, created = ImplementationPlan.objects.update_or_create(
            qualification=qualification,
            name='3-Year Full-Time Apprenticeship',
            defaults={
                'description': '''Standard 3-year apprenticeship implementation plan for the Occupational Certificate: Electrician.
                
This plan follows the QCTO curriculum structure with:
- Alternating institutional training and workplace stints
- 6-hour training days (2hr classroom + 4hr practical) during institutional phases
- Knowledge and Practical modules delivered at the training institution
- Workplace modules completed during employer-based stints
- Integration block for EISA preparation and portfolio compilation
- Final trade test preparation phase

Total Duration: 156 weeks (3 years)
Institutional Training: 44 weeks
Workplace Experience: 80 weeks
Integration/Trade Test Prep: 32 weeks''',
                'delivery_mode': 'FULL_TIME',
                'total_weeks': 156,
                'contact_days_per_week': 5,
                'hours_per_day': 6,
                'classroom_hours_per_day': 2,
                'practical_hours_per_day': 4,
                'is_default': True,
                'status': 'ACTIVE',
                'version': '1.0',
                'effective_from': date(2024, 1, 1),
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created plan: {plan.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Updated plan: {plan.name}'))
            plan.phases.all().delete()
        
        # Define the phase structure
        phases_data = [
            # YEAR 1
            {
                'phase_type': 'INSTITUTIONAL',
                'name': 'Institutional Phase 1 - Electrical Fundamentals',
                'sequence': 1,
                'duration_weeks': 12,
                'year_level': 1,
                'color': 'blue',
                'description': 'Foundation electrical theory and basic installation skills. Covers fundamental electrical principles, drawing interpretation, regulations, and basic wiring techniques.',
                'modules': [
                    ('337935', 18),  # Electrical Principles - K
                    ('337936', 12),  # Electrical Drawings - K
                    ('337939', 8),   # Electrical Regulations - K
                    ('337943', 25),  # Install Wiring Systems - P
                    ('337945', 18),  # Install Equipment & Accessories - P
                ]
            },
            {
                'phase_type': 'WORKPLACE_STINT',
                'name': 'Workplace Stint 1 - Residential Foundation',
                'sequence': 2,
                'duration_weeks': 14,
                'year_level': 1,
                'color': 'green',
                'description': 'Initial workplace exposure focusing on residential electrical work, workplace safety protocols, and basic installation tasks under supervision.',
                'modules': []
            },
            {
                'phase_type': 'INSTITUTIONAL',
                'name': 'Institutional Phase 2 - Protection & Motors',
                'sequence': 3,
                'duration_weeks': 12,
                'year_level': 1,
                'color': 'blue',
                'description': 'Electrical protection systems, machines and motors theory, distribution board installation, and motor connection techniques.',
                'modules': [
                    ('337938', 12),  # Electrical Protection Systems - K
                    ('337937', 15),  # Electrical Machines & Motors - K
                    ('337944', 20),  # Install Distribution Boards - P
                    ('337946', 22),  # Install and Connect Motors - P
                ]
            },
            {
                'phase_type': 'WORKPLACE_STINT',
                'name': 'Workplace Stint 2 - Residential & Commercial Intro',
                'sequence': 4,
                'duration_weeks': 14,
                'year_level': 1,
                'color': 'green',
                'description': 'Continued residential experience with introduction to commercial installations. Focus on completing residential competencies and exposure to larger commercial systems.',
                'modules': []
            },
            # YEAR 2
            {
                'phase_type': 'INSTITUTIONAL',
                'name': 'Institutional Phase 3 - Testing & Fault Finding',
                'sequence': 5,
                'duration_weeks': 10,
                'year_level': 2,
                'color': 'purple',
                'description': 'Three-phase systems, electronics fundamentals, testing and commissioning procedures, and systematic fault-finding techniques.',
                'modules': [
                    ('337942', 10),  # Three Phase Systems - K
                    ('337940', 10),  # Electronics Fundamentals - K
                    ('337947', 20),  # Test and Commission - P
                    ('337948', 22),  # Fault Finding - P
                ]
            },
            {
                'phase_type': 'WORKPLACE_STINT',
                'name': 'Workplace Stint 3 - Commercial Systems',
                'sequence': 6,
                'duration_weeks': 16,
                'year_level': 2,
                'color': 'green',
                'description': 'Commercial electrical installation experience including office buildings, retail spaces, and commercial facilities. Introduction to maintenance procedures.',
                'modules': []
            },
            {
                'phase_type': 'INSTITUTIONAL',
                'name': 'Institutional Phase 4 - Industrial Control & PLCs',
                'sequence': 7,
                'duration_weeks': 10,
                'year_level': 2,
                'color': 'purple',
                'description': 'Programmable logic controllers, industrial control systems, advanced automation concepts, and PLC programming and installation.',
                'modules': [
                    ('337941', 12),  # PLCs - K
                    ('337949', 18),  # Install Industrial Control - P
                    ('337950', 15),  # PLC Installation & Programming - P
                ]
            },
            {
                'phase_type': 'WORKPLACE_STINT',
                'name': 'Workplace Stint 4 - Industrial Introduction',
                'sequence': 8,
                'duration_weeks': 16,
                'year_level': 2,
                'color': 'green',
                'description': 'Industrial electrical systems exposure including factory installations, motor control centres, and preventive maintenance programs.',
                'modules': []
            },
            # YEAR 3
            {
                'phase_type': 'WORKPLACE_STINT',
                'name': 'Workplace Stint 5 - Industrial Consolidation',
                'sequence': 9,
                'duration_weeks': 20,
                'year_level': 3,
                'color': 'green',
                'description': 'Extended industrial placement for advanced skills consolidation, complex fault-finding, customer interaction, and documentation practices.',
                'modules': []
            },
            {
                'phase_type': 'INSTITUTIONAL',
                'name': 'Integration Block - EISA Preparation',
                'sequence': 10,
                'duration_weeks': 8,
                'year_level': 3,
                'color': 'orange',
                'description': 'Integrated summative assessment preparation, External Integrated Summative Assessment (EISA) readiness, portfolio compilation, and final knowledge integration.',
                'modules': []
            },
            {
                'phase_type': 'WORKPLACE_STINT',
                'name': 'Trade Test Preparation',
                'sequence': 11,
                'duration_weeks': 24,
                'year_level': 3,
                'color': 'red',
                'description': 'Final workplace consolidation and trade test preparation. Complete all outstanding workplace competencies, practice trade test components, and prepare for final assessment.',
                'modules': []
            },
        ]
        
        # Create phases and module slots
        total_institutional_weeks = 0
        total_workplace_weeks = 0
        slot_count = 0
        
        for phase_data in phases_data:
            phase = ImplementationPhase.objects.create(
                implementation_plan=plan,
                phase_type=phase_data['phase_type'],
                name=phase_data['name'],
                sequence=phase_data['sequence'],
                duration_weeks=phase_data['duration_weeks'],
                year_level=phase_data['year_level'],
                color=phase_data['color'],
                description=phase_data['description'],
            )
            
            if phase_data['phase_type'] == 'INSTITUTIONAL':
                total_institutional_weeks += phase_data['duration_weeks']
            else:
                total_workplace_weeks += phase_data['duration_weeks']
            
            self.stdout.write(f'  Created phase: {phase.name} ({phase_data["duration_weeks"]} weeks)')
            
            # Create module slots for institutional phases
            if phase_data['modules']:
                for seq, (module_code, credits) in enumerate(phase_data['modules'], start=1):
                    try:
                        module = Module.objects.get(qualification=qualification, code=module_code)
                        
                        # Calculate sessions and days based on credits
                        notional_hours = credits * 10
                        total_days = max(1, round(notional_hours / 6))
                        
                        if module.module_type == 'K':
                            classroom_sessions = max(1, round(total_days * 0.6))
                            practical_sessions = max(1, round(total_days * 0.4))
                        else:
                            classroom_sessions = max(1, round(total_days * 0.3))
                            practical_sessions = max(1, round(total_days * 0.7))
                        
                        slot = ImplementationModuleSlot.objects.create(
                            phase=phase,
                            module=module,
                            sequence=seq,
                            classroom_sessions=classroom_sessions,
                            practical_sessions=practical_sessions,
                            total_days=total_days,
                            notes=f'Module delivered during {phase.name}. Total notional hours: {notional_hours}.',
                        )
                        slot_count += 1
                        self.stdout.write(f'    - {module.code}: {module.title} ({total_days} days)')
                        
                    except Module.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'    - Module {module_code} not found!'))
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Implementation Plan Creation Summary'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Plan: {plan.name}')
        self.stdout.write(f'Qualification: {qualification.title}')
        self.stdout.write(f'Total Duration: {plan.total_weeks} weeks (3 years)')
        self.stdout.write('')
        self.stdout.write(f'Phases created: {len(phases_data)}')
        self.stdout.write(f'  - Institutional phases: {sum(1 for p in phases_data if p["phase_type"] == "INSTITUTIONAL")} ({total_institutional_weeks} weeks)')
        self.stdout.write(f'  - Workplace stints: {sum(1 for p in phases_data if p["phase_type"] == "WORKPLACE_STINT")} ({total_workplace_weeks} weeks)')
        self.stdout.write(f'Module slots created: {slot_count}')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Implementation plan created successfully!'))
        self.stdout.write('Next: Run generate_electrician_lesson_plans to create lesson plans.')
