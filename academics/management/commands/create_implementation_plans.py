"""
Management command to create template implementation plans for qualifications.

Implementation Plan Rules:
- 3-Year Qualifications (OC - Occupational Certificate with 360 credits):
  - Phase 1 (Year 1): 4 months institutional (includes induction week)
  - Phase 2 (Year 1-2): 12 months WIL (Work Integrated Learning)
  - Phase 3 (Year 2): 3 months institutional
  - Phase 4 (Year 2-3): 6-8 months WIL
  - Phase 5 (Year 3): 3 months trade test prep & completion

- Skills Programme (SP):
  - 1 day induction
  - Credits × 10 = notional hours
  - 1/3 time = institutional (6-hour class days)
  - 2/3 time = workplace

- National Certificate (NC) / Learnership:
  - Typically 12-18 months
  - 30% institutional (includes 1 week induction)
  - 70% workplace
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from academics.models import Qualification, ImplementationPlan, ImplementationPhase
from core.models import User
import math


class Command(BaseCommand):
    help = 'Create template implementation plans for all qualifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Recreate plans even if they already exist',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        # Get or create a system user for created_by
        system_user = User.objects.filter(is_superuser=True).first()
        if not system_user:
            self.stdout.write(self.style.ERROR('No superuser found. Please create one first.'))
            return

        qualifications = Qualification.objects.all()
        created_count = 0
        skipped_count = 0

        for qual in qualifications:
            # Check if plan already exists
            existing = qual.implementation_plans.filter(is_default=True).first()
            if existing and not force:
                self.stdout.write(f'  Skipping {qual.short_title} - already has default plan')
                skipped_count += 1
                continue

            if force and existing:
                if not dry_run:
                    # Delete existing phases first
                    for plan in qual.implementation_plans.all():
                        plan.phases.all().delete()
                    qual.implementation_plans.all().delete()
                self.stdout.write(f'  Removing existing plans for {qual.short_title}')

            # Create plan based on qualification type
            if qual.qualification_type == 'OC':
                plan_data = self.create_oc_plan(qual)
            elif qual.qualification_type == 'SP':
                plan_data = self.create_sp_plan(qual)
            else:  # NC, ND, LP, PQ - Learnerships/National Certificates
                plan_data = self.create_nc_plan(qual)

            if dry_run:
                self.stdout.write(self.style.SUCCESS(f'\n[DRY RUN] Would create plan for {qual.short_title}:'))
                self.stdout.write(f"  Name: {plan_data['name']}")
                self.stdout.write(f"  Total weeks: {plan_data['total_weeks']}")
                self.stdout.write(f"  Phases:")
                for phase in plan_data['phases']:
                    self.stdout.write(f"    - {phase['name']}: {phase['duration_weeks']} weeks ({phase['phase_type']})")
            else:
                # Create the implementation plan
                plan = ImplementationPlan.objects.create(
                    qualification=qual,
                    name=plan_data['name'],
                    description=plan_data['description'],
                    delivery_mode=plan_data.get('delivery_mode', 'FULL_TIME'),
                    total_weeks=plan_data['total_weeks'],
                    contact_days_per_week=plan_data.get('contact_days_per_week', 5),
                    hours_per_day=plan_data.get('hours_per_day', 6),
                    classroom_hours_per_day=plan_data.get('classroom_hours_per_day', 2),
                    practical_hours_per_day=plan_data.get('practical_hours_per_day', 4),
                    is_default=True,
                    status='ACTIVE',
                    version='1.0',
                    effective_from=timezone.now().date(),
                    created_by=system_user
                )

                # Create phases
                for i, phase_data in enumerate(plan_data['phases'], start=1):
                    ImplementationPhase.objects.create(
                        implementation_plan=plan,
                        phase_type=phase_data['phase_type'],
                        name=phase_data['name'],
                        sequence=i,
                        duration_weeks=phase_data['duration_weeks'],
                        year_level=phase_data.get('year_level', 1),
                        description=phase_data.get('description', ''),
                        color=phase_data.get('color', 'blue'),
                        created_by=system_user
                    )

                self.stdout.write(self.style.SUCCESS(f'  Created plan for {qual.short_title}: {plan.name}'))
                created_count += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Created: {created_count} plans'))
        self.stdout.write(f'Skipped: {skipped_count} plans (already exist)')

    def create_oc_plan(self, qual):
        """
        Create implementation plan for 3-year Occupational Certificate.
        Structure:
        - Year 1: 4 months (17 weeks) institutional (includes induction)
        - Year 1-2: 12 months (52 weeks) WIL Stint 1
        - Year 2: 3 months (13 weeks) institutional  
        - Year 2-3: 7 months (30 weeks) WIL Stint 2
        - Year 3: 3 months (13 weeks) trade test prep & completion
        Total: ~125 weeks (approx 29 months)
        """
        # Determine if it's a 3-year trade (360 credits) or shorter OC
        if qual.credits >= 300:
            # Full 3-year trade qualification
            phases = [
                {
                    'name': 'Induction & Institutional Phase 1',
                    'phase_type': 'INSTITUTIONAL',
                    'duration_weeks': 17,  # 4 months
                    'year_level': 1,
                    'description': 'Includes 1-week induction, foundation theory and practical training',
                    'color': 'blue'
                },
                {
                    'name': 'Workplace Integrated Learning - Stint 1',
                    'phase_type': 'WORKPLACE',
                    'duration_weeks': 52,  # 12 months
                    'year_level': 1,
                    'description': 'First workplace placement for practical experience',
                    'color': 'green'
                },
                {
                    'name': 'Institutional Phase 2',
                    'phase_type': 'INSTITUTIONAL',
                    'duration_weeks': 13,  # 3 months
                    'year_level': 2,
                    'description': 'Advanced theory and practical modules',
                    'color': 'blue'
                },
                {
                    'name': 'Workplace Integrated Learning - Stint 2',
                    'phase_type': 'WORKPLACE',
                    'duration_weeks': 30,  # ~7 months
                    'year_level': 2,
                    'description': 'Second workplace placement for advanced experience',
                    'color': 'green'
                },
                {
                    'name': 'Trade Test Preparation & Completion',
                    'phase_type': 'TRADE_TEST',
                    'duration_weeks': 13,  # 3 months
                    'year_level': 3,
                    'description': 'Gap training, trade test preparation, POE completion, and final assessments',
                    'color': 'purple'
                }
            ]
            total_weeks = sum(p['duration_weeks'] for p in phases)
            
            return {
                'name': f'Standard 3-Year Full-Time ({qual.credits} credits)',
                'description': f'Standard implementation plan for {qual.short_title}. Includes induction, two institutional phases, two WIL stints, and trade test preparation.',
                'delivery_mode': 'FULL_TIME',
                'total_weeks': total_weeks,
                'contact_days_per_week': 5,
                'hours_per_day': 6,
                'classroom_hours_per_day': 2,
                'practical_hours_per_day': 4,
                'phases': phases
            }
        else:
            # Shorter OC (e.g., Bookkeeper, Financial Markets - 180-200 credits)
            # Typically 18-30 months
            institutional_weeks = int(qual.minimum_duration_months * 0.35 * 4.33)  # 35% institutional
            workplace_weeks = int(qual.minimum_duration_months * 0.65 * 4.33)  # 65% workplace
            
            phases = [
                {
                    'name': 'Induction & Institutional Phase 1',
                    'phase_type': 'INSTITUTIONAL',
                    'duration_weeks': max(8, institutional_weeks // 2),
                    'year_level': 1,
                    'description': 'Includes 1-week induction, foundation theory and practical training',
                    'color': 'blue'
                },
                {
                    'name': 'Workplace Integrated Learning',
                    'phase_type': 'WORKPLACE',
                    'duration_weeks': workplace_weeks,
                    'year_level': 1,
                    'description': 'Workplace placement for practical experience',
                    'color': 'green'
                },
                {
                    'name': 'Institutional Phase 2 & Assessment',
                    'phase_type': 'INSTITUTIONAL',
                    'duration_weeks': max(4, institutional_weeks - institutional_weeks // 2),
                    'year_level': 2,
                    'description': 'Final modules, POE completion, and assessments',
                    'color': 'blue'
                }
            ]
            total_weeks = sum(p['duration_weeks'] for p in phases)
            
            return {
                'name': f'Standard Full-Time ({qual.credits} credits)',
                'description': f'Standard implementation plan for {qual.short_title}.',
                'delivery_mode': 'FULL_TIME',
                'total_weeks': total_weeks,
                'contact_days_per_week': 5,
                'hours_per_day': 6,
                'classroom_hours_per_day': 2,
                'practical_hours_per_day': 4,
                'phases': phases
            }

    def create_sp_plan(self, qual):
        """
        Create implementation plan for Skills Programme.
        Formula:
        - Notional hours = credits × 10
        - Institutional time = 1/3 of notional hours
        - Workplace time = 2/3 of notional hours
        - Class day = 6 hours
        - 1 day induction
        """
        notional_hours = qual.credits * 10
        institutional_hours = notional_hours / 3
        workplace_hours = notional_hours * 2 / 3
        
        # Calculate days (6-hour class day)
        hours_per_day = 6
        institutional_days = math.ceil(institutional_hours / hours_per_day)
        
        # Workplace: assume 8-hour work day
        workplace_days = math.ceil(workplace_hours / 8)
        
        # Convert to weeks (5 days per week)
        induction_days = 1
        institutional_weeks = max(1, math.ceil((institutional_days - induction_days) / 5))
        workplace_weeks = max(1, math.ceil(workplace_days / 5))
        
        phases = [
            {
                'name': 'Induction',
                'phase_type': 'INDUCTION',
                'duration_weeks': 1,  # 1 day but minimum is 1 week for tracking
                'year_level': 1,
                'description': '1-day orientation and programme overview',
                'color': 'yellow'
            },
            {
                'name': 'Institutional Training',
                'phase_type': 'INSTITUTIONAL',
                'duration_weeks': institutional_weeks,
                'year_level': 1,
                'description': f'Theory and practical training ({institutional_days} training days)',
                'color': 'blue'
            },
            {
                'name': 'Workplace Learning',
                'phase_type': 'WORKPLACE',
                'duration_weeks': workplace_weeks,
                'year_level': 1,
                'description': f'On-the-job training ({workplace_days} working days)',
                'color': 'green'
            }
        ]
        
        total_weeks = sum(p['duration_weeks'] for p in phases)
        
        return {
            'name': f'Skills Programme ({qual.credits} credits)',
            'description': f'Skills programme implementation for {qual.short_title}. {notional_hours:.0f} notional hours: {institutional_hours:.0f}h institutional, {workplace_hours:.0f}h workplace.',
            'delivery_mode': 'BLENDED',
            'total_weeks': total_weeks,
            'contact_days_per_week': 5,
            'hours_per_day': 6,
            'classroom_hours_per_day': 2,
            'practical_hours_per_day': 4,
            'phases': phases
        }

    def create_nc_plan(self, qual):
        """
        Create implementation plan for National Certificate / Learnership.
        Typically:
        - 30% institutional (includes induction)
        - 70% workplace
        - Duration: 12-24 months based on minimum_duration_months
        """
        total_months = qual.minimum_duration_months
        total_weeks = int(total_months * 4.33)
        
        # Calculate phase durations
        induction_weeks = 1
        institutional_weeks = max(4, int(total_weeks * 0.30) - induction_weeks)  # 30% minus induction
        workplace_weeks = total_weeks - institutional_weeks - induction_weeks  # Remainder
        
        # Split institutional if long enough
        if institutional_weeks >= 8:
            inst1_weeks = institutional_weeks // 2
            inst2_weeks = institutional_weeks - inst1_weeks
            workplace1_weeks = workplace_weeks // 2
            workplace2_weeks = workplace_weeks - workplace1_weeks
            
            phases = [
                {
                    'name': 'Induction',
                    'phase_type': 'INDUCTION',
                    'duration_weeks': induction_weeks,
                    'year_level': 1,
                    'description': 'Programme orientation, documentation, and learner registration',
                    'color': 'yellow'
                },
                {
                    'name': 'Institutional Phase 1',
                    'phase_type': 'INSTITUTIONAL',
                    'duration_weeks': inst1_weeks,
                    'year_level': 1,
                    'description': 'Foundation modules and practical training',
                    'color': 'blue'
                },
                {
                    'name': 'Workplace Phase 1',
                    'phase_type': 'WORKPLACE',
                    'duration_weeks': workplace1_weeks,
                    'year_level': 1,
                    'description': 'On-the-job training and workplace evidence collection',
                    'color': 'green'
                },
                {
                    'name': 'Institutional Phase 2',
                    'phase_type': 'INSTITUTIONAL',
                    'duration_weeks': inst2_weeks,
                    'year_level': 1,
                    'description': 'Advanced modules, assessments, and POE completion',
                    'color': 'blue'
                },
                {
                    'name': 'Workplace Phase 2',
                    'phase_type': 'WORKPLACE',
                    'duration_weeks': workplace2_weeks,
                    'year_level': 1,
                    'description': 'Final workplace experience and evidence collection',
                    'color': 'green'
                }
            ]
        else:
            # Simpler structure for shorter programmes
            phases = [
                {
                    'name': 'Induction',
                    'phase_type': 'INDUCTION',
                    'duration_weeks': induction_weeks,
                    'year_level': 1,
                    'description': 'Programme orientation, documentation, and learner registration',
                    'color': 'yellow'
                },
                {
                    'name': 'Institutional Training',
                    'phase_type': 'INSTITUTIONAL',
                    'duration_weeks': institutional_weeks,
                    'year_level': 1,
                    'description': 'Theory and practical training',
                    'color': 'blue'
                },
                {
                    'name': 'Workplace Learning',
                    'phase_type': 'WORKPLACE',
                    'duration_weeks': workplace_weeks,
                    'year_level': 1,
                    'description': 'On-the-job training and workplace evidence collection',
                    'color': 'green'
                }
            ]
        
        total_weeks = sum(p['duration_weeks'] for p in phases)
        
        return {
            'name': f'Standard Learnership ({qual.credits} credits, {total_months} months)',
            'description': f'Standard implementation plan for {qual.short_title}. 30% institutional, 70% workplace.',
            'delivery_mode': 'BLENDED',
            'total_weeks': total_weeks,
            'contact_days_per_week': 5,
            'hours_per_day': 6,
            'classroom_hours_per_day': 2,
            'practical_hours_per_day': 4,
            'phases': phases
        }
