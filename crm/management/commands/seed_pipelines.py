"""
Management command to seed simplified sales pipelines.

SIMPLIFIED FLOW:
New Lead → Contacted → Interested → Pre-Approved → Application → Enrolled/Lost

Creates:
- School Leaver pipeline (Grade 9-12)
- Adult Learner pipeline  
- Corporate pipeline

Usage:
    python manage.py seed_pipelines
    python manage.py seed_pipelines --campus=1
    python manage.py seed_pipelines --clear
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from crm.models import Pipeline, PipelineStage, StageBlueprint


class Command(BaseCommand):
    help = 'Seed simplified sales pipelines'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--campus',
            type=int,
            help='Create pipelines only for a specific campus ID'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing pipelines before seeding'
        )
    
    def handle(self, *args, **options):
        campus_id = options.get('campus')
        clear = options.get('clear')
        
        from tenants.models import Campus
        
        # Get campuses
        if campus_id:
            campuses = Campus.objects.filter(pk=campus_id)
            if not campuses.exists():
                raise CommandError(f'Campus with ID {campus_id} not found')
        else:
            campuses = Campus.objects.filter(is_active=True)
        
        if not campuses.exists():
            raise CommandError('No campuses found. Please create at least one campus first.')
        
        if clear:
            self.stdout.write('Clearing existing pipelines...')
            Pipeline.objects.all().delete()
        
        for campus in campuses:
            self.create_pipelines_for_campus(campus)
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded pipelines!'))
    
    @transaction.atomic
    def create_pipelines_for_campus(self, campus):
        campus_name = campus.name
        self.stdout.write(f'Creating pipelines for {campus_name}...')
        
        # 1. School Leaver Pipeline (Gr 9-12)
        school_pipeline, created = Pipeline.objects.update_or_create(
            name='School Leaver',
            campus=campus,
            defaults={
                'description': 'For learners currently in school (Grade 9-12)',
                'learner_type': 'SCHOOL_LEAVER_READY',
                'default_communication_frequency_days': 14,
                'is_active': True,
                'is_default': True,
                'color': '#3B82F6',
                'icon': '🎓',
            }
        )
        if created:
            self.create_standard_stages(school_pipeline, is_school_leaver=True)
            self.stdout.write(f'  ✓ Created: {school_pipeline.name}')
        else:
            self.stdout.write(f'  ✓ Updated: {school_pipeline.name}')
        
        # 2. Adult Learner Pipeline
        adult_pipeline, created = Pipeline.objects.update_or_create(
            name='Adult Learner',
            campus=campus,
            defaults={
                'description': 'For working adults and career changers',
                'learner_type': 'ADULT',
                'default_communication_frequency_days': 14,
                'is_active': True,
                'is_default': True,
                'color': '#10B981',
                'icon': '💼',
            }
        )
        if created:
            self.create_standard_stages(adult_pipeline, is_school_leaver=False)
            self.stdout.write(f'  ✓ Created: {adult_pipeline.name}')
        else:
            self.stdout.write(f'  ✓ Updated: {adult_pipeline.name}')
        
        # 3. Corporate Pipeline (employer-sponsored)
        corporate_pipeline, created = Pipeline.objects.update_or_create(
            name='Corporate',
            campus=campus,
            defaults={
                'description': 'For employer-sponsored learners and corporate clients',
                'learner_type': 'CORPORATE',
                'default_communication_frequency_days': 7,
                'is_active': True,
                'is_default': False,
                'color': '#8B5CF6',
                'icon': '🏢',
            }
        )
        if created:
            self.create_standard_stages(corporate_pipeline, is_school_leaver=False)
            self.stdout.write(f'  ✓ Created: {corporate_pipeline.name}')
        else:
            self.stdout.write(f'  ✓ Updated: {corporate_pipeline.name}')
    
    def create_standard_stages(self, pipeline, is_school_leaver=False):
        """
        Create simplified stages for any pipeline.
        
        Flow: New Lead → Contacted → Interested → Pre-Approved → Application → Enrolled/Lost
        """
        stages = [
            {
                'code': 'NEW',
                'name': 'New Lead',
                'description': 'Fresh inquiry - needs first contact',
                'order': 1,
                'expected_duration_days': 2,
                'communication_frequency_days': 1,
                'win_probability': 10,
                'color': '#9CA3AF',
                'icon': '📥',
                'is_entry_stage': True,
                'blueprint': {
                    'notify_agent_on_entry': True,
                    'auto_schedule_follow_up': True,
                    'recommended_actions': [
                        'Make first contact within 24 hours',
                        'Introduce yourself and the institution',
                        'Ask about their qualification interest',
                    ],
                }
            },
            {
                'code': 'CONTACTED',
                'name': 'Contacted',
                'description': 'Initial contact made - qualifying the lead',
                'order': 2,
                'expected_duration_days': 7,
                'communication_frequency_days': 3,
                'win_probability': 25,
                'color': '#60A5FA',
                'icon': '📞',
                'blueprint': {
                    'notify_agent_on_entry': False,
                    'auto_schedule_follow_up': True,
                    'recommended_actions': [
                        'Understand their career goals',
                        'Confirm current qualification/grade',
                        'Discuss available programmes',
                        'Add parent/guardian details if school leaver',
                    ] if is_school_leaver else [
                        'Understand their career goals',
                        'Confirm current qualifications',
                        'Discuss study mode preferences (FT/PT/Online)',
                        'Check employment status for scheduling',
                    ],
                }
            },
            {
                'code': 'INTERESTED',
                'name': 'Interested',
                'description': 'Confirmed interest - ready for proposal',
                'order': 3,
                'expected_duration_days': 14,
                'communication_frequency_days': 5,
                'win_probability': 50,
                'color': '#FBBF24',
                'icon': '⭐',
                'blueprint': {
                    'notify_agent_on_entry': True,
                    'auto_schedule_follow_up': True,
                    'recommended_actions': [
                        'Send programme information',
                        'Create and send quote',
                        'Discuss payment options',
                        'Confirm entry requirements can be met',
                    ],
                }
            },
            {
                'code': 'PRE_APPROVED',
                'name': 'Pre-Approved',
                'description': 'Entry requirements confirmed - pre-approval letter sent',
                'order': 4,
                'expected_duration_days': 14,
                'communication_frequency_days': 3,
                'win_probability': 75,
                'color': '#34D399',
                'icon': '✅',
                'blueprint': {
                    'notify_agent_on_entry': True,
                    'auto_send_initial_communication': True,
                    'auto_schedule_follow_up': True,
                    'recommended_actions': [
                        'Pre-approval letter sent automatically',
                        'Explain application process',
                        'List required documents',
                        'Set deadline for document submission',
                    ],
                }
            },
            {
                'code': 'APPLICATION',
                'name': 'Application',
                'description': 'Collecting documents - completing application',
                'order': 5,
                'expected_duration_days': 21,
                'communication_frequency_days': 5,
                'win_probability': 85,
                'color': '#F97316',
                'icon': '📋',
                'blueprint': {
                    'notify_agent_on_entry': True,
                    'auto_schedule_follow_up': True,
                    'recommended_actions': [
                        'Track document submissions',
                        'Follow up on missing documents',
                        'Verify document authenticity',
                        'Process application for final approval',
                    ],
                }
            },
            {
                'code': 'ENROLLED',
                'name': 'Enrolled',
                'description': 'Successfully enrolled',
                'order': 6,
                'expected_duration_days': 0,
                'communication_frequency_days': None,
                'win_probability': 100,
                'color': '#22C55E',
                'icon': '🎉',
                'is_won_stage': True,
                'blueprint': {
                    'notify_agent_on_entry': True,
                    'recommended_actions': [
                        'Send welcome pack',
                        'Introduce to student services',
                        'Schedule orientation',
                    ],
                }
            },
            {
                'code': 'LOST',
                'name': 'Lost',
                'description': 'Did not convert',
                'order': 7,
                'expected_duration_days': 0,
                'communication_frequency_days': None,
                'win_probability': 0,
                'color': '#EF4444',
                'icon': '❌',
                'is_lost_stage': True,
                'blueprint': {
                    'notify_agent_on_entry': False,
                    'recommended_actions': [
                        'Record reason for loss',
                        'Consider for future re-engagement',
                    ],
                }
            },
        ]
        
        for stage_data in stages:
            blueprint_data = stage_data.pop('blueprint', {})
            
            stage, _ = PipelineStage.objects.update_or_create(
                pipeline=pipeline,
                code=stage_data['code'],
                defaults={
                    'name': stage_data['name'],
                    'description': stage_data.get('description', ''),
                    'order': stage_data['order'],
                    'expected_duration_days': stage_data.get('expected_duration_days') or 7,
                    'communication_frequency_days': stage_data.get('communication_frequency_days'),
                    'win_probability': stage_data.get('win_probability', 0),
                    'color': stage_data.get('color', '#6B7280'),
                    'icon': stage_data.get('icon', ''),
                    'is_entry_stage': stage_data.get('is_entry_stage', False),
                    'is_won_stage': stage_data.get('is_won_stage', False),
                    'is_lost_stage': stage_data.get('is_lost_stage', False),
                    'is_nurture_stage': stage_data.get('is_nurture_stage', False),
                }
            )
            
            # Create or update blueprint
            StageBlueprint.objects.update_or_create(
                stage=stage,
                defaults={
                    'notify_agent_on_entry': blueprint_data.get('notify_agent_on_entry', True),
                    'notify_agent_on_overdue': True,
                    'auto_send_initial_communication': blueprint_data.get('auto_send_initial_communication', False),
                    'auto_schedule_follow_up': blueprint_data.get('auto_schedule_follow_up', True),
                    'recommended_actions': blueprint_data.get('recommended_actions', []),
                }
            )
