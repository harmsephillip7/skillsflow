"""
Management command to seed the Enrollment Process Flow with stages and transitions.
Run: python manage.py seed_enrollment_process
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from workflows.models import ProcessFlow, ProcessStage, ProcessStageTransition


class Command(BaseCommand):
    help = 'Seeds the enrollment process flow with default stages and transitions'
    
    # Define stages with their properties
    STAGES = [
        {
            'code': 'APPLIED',
            'name': 'Applied',
            'description': 'Initial application received',
            'stage_type': 'START',
            'sequence_order': 10,
            'color': 'info',
            'icon': 'clipboard-list',
        },
        {
            'code': 'DOC_CHECK',
            'name': 'Document Check',
            'description': 'Documents submitted and under review',
            'stage_type': 'PROCESS',
            'sequence_order': 20,
            'color': 'warning',
            'icon': 'file-search',
        },
        {
            'code': 'REGISTERED',
            'name': 'Registered',
            'description': 'Formally registered for the qualification',
            'stage_type': 'PROCESS',
            'sequence_order': 30,
            'color': 'primary',
            'icon': 'user-check',
        },
        {
            'code': 'ENROLLED',
            'name': 'Enrolled',
            'description': 'Fully enrolled and ready to begin',
            'stage_type': 'PROCESS',
            'sequence_order': 40,
            'color': 'success',
            'icon': 'book-open',
        },
        {
            'code': 'ACTIVE',
            'name': 'Active',
            'description': 'Actively participating in the programme',
            'stage_type': 'PROCESS',
            'sequence_order': 50,
            'color': 'success',
            'icon': 'play-circle',
        },
        {
            'code': 'ON_HOLD',
            'name': 'On Hold',
            'description': 'Temporarily paused enrollment',
            'stage_type': 'PROCESS',
            'sequence_order': 55,
            'color': 'warning',
            'icon': 'pause-circle',
            'requires_reason_on_entry': True,
        },
        {
            'code': 'COMPLETED',
            'name': 'Completed',
            'description': 'All requirements completed, awaiting certification',
            'stage_type': 'PROCESS',
            'sequence_order': 60,
            'color': 'info',
            'icon': 'check-circle',
        },
        {
            'code': 'CERTIFIED',
            'name': 'Certified',
            'description': 'Certificate awarded',
            'stage_type': 'END',
            'sequence_order': 70,
            'color': 'success',
            'icon': 'award',
        },
        {
            'code': 'WITHDRAWN',
            'name': 'Withdrawn',
            'description': 'Learner has withdrawn from the programme',
            'stage_type': 'END',
            'sequence_order': 80,
            'color': 'danger',
            'icon': 'user-x',
            'requires_reason_on_entry': True,
        },
        {
            'code': 'TRANSFERRED',
            'name': 'Transferred',
            'description': 'Transferred to another qualification or institution',
            'stage_type': 'END',
            'sequence_order': 85,
            'color': 'secondary',
            'icon': 'arrow-right-circle',
            'requires_reason_on_entry': True,
        },
        {
            'code': 'EXPIRED',
            'name': 'Expired',
            'description': 'Enrollment has expired',
            'stage_type': 'END',
            'sequence_order': 90,
            'color': 'dark',
            'icon': 'clock',
        },
    ]
    
    # Define allowed transitions
    # Format: (from_stage, to_stage, is_allowed, requires_reason, requires_approval, validation_rules)
    TRANSITIONS = [
        # From APPLIED
        ('APPLIED', 'DOC_CHECK', True, False, False, {}),
        ('APPLIED', 'WITHDRAWN', True, True, False, {}),
        
        # From DOC_CHECK
        ('DOC_CHECK', 'APPLIED', True, True, False, {}),  # Return if docs missing
        ('DOC_CHECK', 'REGISTERED', True, False, False, {}),
        ('DOC_CHECK', 'WITHDRAWN', True, True, False, {}),
        
        # From REGISTERED
        ('REGISTERED', 'ENROLLED', True, False, False, {}),
        ('REGISTERED', 'WITHDRAWN', True, True, False, {}),
        
        # From ENROLLED
        ('ENROLLED', 'ACTIVE', True, False, False, {}),
        ('ENROLLED', 'WITHDRAWN', True, True, False, {}),
        
        # From ACTIVE
        ('ACTIVE', 'ON_HOLD', True, True, False, {}),
        ('ACTIVE', 'COMPLETED', True, False, False, {}),
        ('ACTIVE', 'WITHDRAWN', True, True, False, {}),
        ('ACTIVE', 'TRANSFERRED', True, True, True, {}),  # Requires approval
        
        # From ON_HOLD
        ('ON_HOLD', 'ACTIVE', True, False, False, {}),  # Resume
        ('ON_HOLD', 'WITHDRAWN', True, True, False, {}),
        
        # From COMPLETED
        ('COMPLETED', 'CERTIFIED', True, False, False, {
            'required_fields': ['certificate_number', 'certificate_date'],
        }),
        ('COMPLETED', 'ACTIVE', True, True, False, {}),  # Revert if error
        
        # From terminal states - generally no transitions, but allow corrections
        ('WITHDRAWN', 'APPLIED', True, True, True, {}),  # Re-enroll requires approval
        
        # Expired handling
        ('ACTIVE', 'EXPIRED', True, False, False, {}),
        ('ON_HOLD', 'EXPIRED', True, False, False, {}),
        ('ENROLLED', 'EXPIRED', True, False, False, {}),
    ]
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of process flow even if it exists',
        )
    
    def handle(self, *args, **options):
        force = options.get('force', False)
        
        with transaction.atomic():
            # Check if process flow already exists
            existing = ProcessFlow.objects.filter(
                entity_type='enrollment',
                is_active=True
            ).first()
            
            if existing and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f'Enrollment process flow already exists (v{existing.version}). '
                        'Use --force to recreate.'
                    )
                )
                return
            
            if existing and force:
                # Deactivate the old flow
                existing.is_active = False
                new_version = existing.version + 1
                existing.save()
                self.stdout.write(f'Deactivated existing process flow v{existing.version}')
            else:
                new_version = 1
            
            # Create the process flow
            process_flow = ProcessFlow.objects.create(
                entity_type='enrollment',
                name='Enrollment Lifecycle',
                description='Standard enrollment process from application to certification',
                version=new_version,
                is_active=True,
            )
            self.stdout.write(f'Created process flow: {process_flow.name} v{new_version}')
            
            # Create stages
            stage_map = {}
            for stage_data in self.STAGES:
                stage = ProcessStage.objects.create(
                    process_flow=process_flow,
                    **stage_data
                )
                stage_map[stage.code] = stage
                self.stdout.write(f'  + Stage: {stage.name}')
            
            # Create transitions
            transition_count = 0
            for from_code, to_code, is_allowed, requires_reason, requires_approval, rules in self.TRANSITIONS:
                from_stage = stage_map.get(from_code)
                to_stage = stage_map.get(to_code)
                
                if from_stage and to_stage:
                    ProcessStageTransition.objects.create(
                        process_flow=process_flow,
                        from_stage=from_stage,
                        to_stage=to_stage,
                        is_allowed=is_allowed,
                        requires_reason=requires_reason,
                        requires_approval=requires_approval,
                        validation_rules=rules,
                    )
                    transition_count += 1
            
            self.stdout.write(f'  + Created {transition_count} transitions')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully seeded enrollment process flow with '
                    f'{len(self.STAGES)} stages and {transition_count} transitions'
                )
            )
