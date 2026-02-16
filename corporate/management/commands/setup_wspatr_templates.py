"""
Management command to setup WSP/ATR service templates and meeting templates.
Creates:
- ServiceDeliveryTemplate for WSP_ATR service type (if not exists)
- MeetingTemplate records for quarterly meetings (Q1-Q4)
"""
from django.core.management.base import BaseCommand
from corporate.models import (
    ServiceDeliveryTemplate, 
    ServiceDeliveryTemplateMilestone,
    MeetingTemplate
)


class Command(BaseCommand):
    help = 'Setup WSP/ATR service delivery templates and meeting templates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of templates (deletes existing)',
        )
        parser.add_argument(
            '--milestones-only',
            action='store_true',
            help='Only create/update service delivery milestones',
        )
        parser.add_argument(
            '--meetings-only',
            action='store_true',
            help='Only create/update meeting templates',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        milestones_only = options.get('milestones_only', False)
        meetings_only = options.get('meetings_only', False)
        
        # If no specific flag, do both
        do_milestones = not meetings_only
        do_meetings = not milestones_only
        
        self.stdout.write(self.style.NOTICE('\n=== WSP/ATR Template Setup ===\n'))
        
        if do_milestones:
            self.setup_service_delivery_template(force)
        
        if do_meetings:
            self.setup_meeting_templates(force)
        
        self.stdout.write(self.style.SUCCESS('\n✓ WSP/ATR template setup completed!\n'))

    def setup_service_delivery_template(self, force: bool):
        """Create or update the WSP/ATR service delivery template."""
        self.stdout.write('Setting up WSP/ATR Service Delivery Template...')
        
        existing = ServiceDeliveryTemplate.objects.filter(service_type='WSP_ATR').first()
        
        if existing and not force:
            self.stdout.write(self.style.WARNING(
                '  WSP/ATR template already exists. Use --force to recreate.'
            ))
            return
        
        if existing and force:
            existing.delete()
            self.stdout.write('  Deleted existing WSP/ATR template')
        
        # Create the template
        template = ServiceDeliveryTemplate.objects.create(
            service_type='WSP_ATR',
            name='WSP/ATR Annual Submission',
            description='Standard milestones for annual WSP (Workplace Skills Plan) and ATR (Annual Training Report) submission service',
            default_duration_days=365,
            is_active=True
        )
        
        # Define milestones for WSP/ATR delivery
        milestones = [
            {
                'name': 'Client Onboarding & Setup',
                'description': 'Initial client meeting, gather company details, SETA registration verification, setup in system',
                'days_from_start': 0,
                'duration_days': 14,
                'weight': 1,
                'requires_evidence': True,
                'evidence_description': 'Signed service agreement, client information form, SETA registration documents',
            },
            {
                'name': 'Training Committee Establishment',
                'description': 'Establish or verify Training Committee structure, appoint members, document constitution',
                'days_from_start': 14,
                'duration_days': 21,
                'weight': 1,
                'requires_evidence': True,
                'evidence_description': 'Training Committee constitution, member appointment letters, first meeting minutes',
            },
            {
                'name': 'Q1 Training Committee Meeting',
                'description': 'First quarterly Training Committee meeting - WSP planning and previous year ATR review',
                'days_from_start': 30,
                'duration_days': 1,
                'weight': 1,
                'requires_evidence': True,
                'evidence_description': 'Meeting agenda, attendance register, signed minutes',
            },
            {
                'name': 'Employee Data Collection',
                'description': 'Collect current workforce data - headcount by demographics, occupational levels',
                'days_from_start': 45,
                'duration_days': 30,
                'weight': 2,
                'requires_evidence': True,
                'evidence_description': 'Employee data spreadsheet, payroll extracts, organogram',
            },
            {
                'name': 'ATR Data Collection',
                'description': 'Collect data on training conducted in previous year - programmes, attendance, costs',
                'days_from_start': 60,
                'duration_days': 30,
                'weight': 2,
                'requires_evidence': True,
                'evidence_description': 'Training records, attendance registers, certificates, proof of payment',
            },
            {
                'name': 'WSP Training Needs Analysis',
                'description': 'Identify training needs for coming year - skills gaps, strategic priorities, PIVOTAL requirements',
                'days_from_start': 75,
                'duration_days': 21,
                'weight': 2,
                'requires_evidence': True,
                'evidence_description': 'Skills audit, training needs assessment, strategic skills plan',
            },
            {
                'name': 'Q2 Training Committee Meeting',
                'description': 'Second quarterly meeting - Review data collection, approve WSP/ATR content',
                'days_from_start': 120,
                'duration_days': 1,
                'weight': 1,
                'requires_evidence': True,
                'evidence_description': 'Meeting agenda, attendance register, signed minutes, WSP/ATR approval',
            },
            {
                'name': 'WSP/ATR Document Preparation',
                'description': 'Compile WSP and ATR documents according to SETA template requirements',
                'days_from_start': 130,
                'duration_days': 30,
                'weight': 3,
                'requires_evidence': False,
                'evidence_description': '',
            },
            {
                'name': 'Internal Quality Review',
                'description': 'Internal review of WSP/ATR documents for accuracy and completeness',
                'days_from_start': 160,
                'duration_days': 7,
                'weight': 1,
                'requires_evidence': False,
                'evidence_description': '',
            },
            {
                'name': 'Client Review & Sign-off',
                'description': 'Client reviews and approves WSP/ATR for submission',
                'days_from_start': 167,
                'duration_days': 7,
                'weight': 1,
                'requires_evidence': True,
                'evidence_description': 'Signed WSP/ATR approval, CEO/HR Director sign-off',
            },
            {
                'name': 'SETA Submission',
                'description': 'Submit WSP/ATR to SETA before deadline (typically 30 April)',
                'days_from_start': 180,
                'duration_days': 1,
                'weight': 2,
                'requires_evidence': True,
                'evidence_description': 'SETA submission confirmation, reference number, uploaded documents',
            },
            {
                'name': 'Q3 Training Committee Meeting',
                'description': 'Third quarterly meeting - WSP implementation monitoring, training progress review',
                'days_from_start': 210,
                'duration_days': 1,
                'weight': 1,
                'requires_evidence': True,
                'evidence_description': 'Meeting agenda, attendance register, signed minutes',
            },
            {
                'name': 'SETA Feedback & Corrections',
                'description': 'Address any SETA queries or required corrections',
                'days_from_start': 220,
                'duration_days': 30,
                'weight': 1,
                'requires_evidence': True,
                'evidence_description': 'SETA feedback, corrective submissions, final approval',
            },
            {
                'name': 'Q4 Training Committee Meeting',
                'description': 'Fourth quarterly meeting - Year-end review, next year planning',
                'days_from_start': 300,
                'duration_days': 1,
                'weight': 1,
                'requires_evidence': True,
                'evidence_description': 'Meeting agenda, attendance register, signed minutes',
            },
            {
                'name': 'Year-End Reporting',
                'description': 'Compile year-end service delivery report, client feedback, preparation for next cycle',
                'days_from_start': 350,
                'duration_days': 14,
                'weight': 1,
                'requires_evidence': True,
                'evidence_description': 'Service delivery report, client satisfaction feedback',
            },
        ]
        
        for i, milestone in enumerate(milestones, 1):
            ServiceDeliveryTemplateMilestone.objects.create(
                template=template,
                name=milestone['name'],
                description=milestone['description'],
                sequence=i,
                days_from_start=milestone['days_from_start'],
                duration_days=milestone['duration_days'],
                weight=milestone['weight'],
                requires_evidence=milestone['requires_evidence'],
                evidence_description=milestone['evidence_description'],
            )
        
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ Created WSP/ATR template with {len(milestones)} milestones'
        ))

    def setup_meeting_templates(self, force: bool):
        """Create or update the quarterly meeting templates."""
        self.stdout.write('Setting up Training Committee Meeting Templates...')
        
        meeting_templates = [
            {
                'quarter': 'Q1',
                'name': 'Q1 WSP/ATR Implementation Meeting',
                'description': 'First quarterly meeting focused on WSP implementation and previous year submission review',
                'suggested_month': 6,  # June
                'preparation_notes': 'Prepare: SETA submission confirmation, Training Committee constitution, Member appointments',
                'default_agenda': [
                    {
                        'title': 'Welcome & Apologies',
                        'description': 'Record attendance and note apologies',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Confirmation of Previous Minutes',
                        'description': 'Review and approve minutes from previous meeting',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Matters Arising',
                        'description': 'Follow up on action items from previous meeting',
                        'duration_minutes': 15,
                    },
                    {
                        'title': 'ATR Review - Previous Year Training',
                        'description': 'Review training conducted in previous financial year',
                        'duration_minutes': 30,
                    },
                    {
                        'title': 'WSP Planning - Training Needs Analysis',
                        'description': 'Identify training priorities for current year',
                        'duration_minutes': 30,
                    },
                    {
                        'title': 'Data Collection Planning',
                        'description': 'Agree on data requirements and collection timelines',
                        'duration_minutes': 15,
                    },
                    {
                        'title': 'Any Other Business',
                        'description': 'Other matters for discussion',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Next Meeting Date',
                        'description': 'Confirm date for next quarterly meeting',
                        'duration_minutes': 5,
                    },
                ],
            },
            {
                'quarter': 'Q2',
                'name': 'Q2 Implementation Monitoring Meeting',
                'description': 'Second quarterly meeting to monitor WSP implementation and training progress',
                'suggested_month': 9,  # September
                'preparation_notes': 'Prepare: Training progress report, WSP implementation status',
                'default_agenda': [
                    {
                        'title': 'Welcome & Apologies',
                        'description': 'Record attendance and note apologies',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Confirmation of Previous Minutes',
                        'description': 'Review and approve Q1 meeting minutes',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Matters Arising',
                        'description': 'Follow up on action items from Q1 meeting',
                        'duration_minutes': 15,
                    },
                    {
                        'title': 'Employee Data Review',
                        'description': 'Review workforce profile data for WSP/ATR',
                        'duration_minutes': 20,
                    },
                    {
                        'title': 'ATR Content Review',
                        'description': 'Review Annual Training Report content',
                        'duration_minutes': 25,
                    },
                    {
                        'title': 'WSP Content Review',
                        'description': 'Review Workplace Skills Plan content',
                        'duration_minutes': 25,
                    },
                    {
                        'title': 'PIVOTAL Training Review',
                        'description': 'Review planned PIVOTAL training interventions',
                        'duration_minutes': 15,
                    },
                    {
                        'title': 'WSP/ATR Approval',
                        'description': 'Committee approval of WSP/ATR for submission',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Any Other Business',
                        'description': 'Other matters for discussion',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Next Meeting Date',
                        'description': 'Confirm date for next quarterly meeting',
                        'duration_minutes': 5,
                    },
                ],
            },
            {
                'quarter': 'Q3',
                'name': 'Q3 Implementation Monitoring Meeting',
                'description': 'Third quarterly meeting to monitor WSP implementation and training progress',
                'suggested_month': 12,  # December
                'preparation_notes': 'Prepare: Training progress report, WSP implementation status, SETA feedback summary',
                'default_agenda': [
                    {
                        'title': 'Welcome & Apologies',
                        'description': 'Record attendance and note apologies',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Confirmation of Previous Minutes',
                        'description': 'Review and approve Q2 meeting minutes',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Matters Arising',
                        'description': 'Follow up on action items from Q2 meeting',
                        'duration_minutes': 15,
                    },
                    {
                        'title': 'WSP/ATR Submission Outcome',
                        'description': 'Report on SETA submission outcome and any feedback',
                        'duration_minutes': 15,
                    },
                    {
                        'title': 'Training Implementation Progress',
                        'description': 'Review progress on planned training interventions',
                        'duration_minutes': 30,
                    },
                    {
                        'title': 'Budget Utilization',
                        'description': 'Review training budget utilization YTD',
                        'duration_minutes': 15,
                    },
                    {
                        'title': 'Challenges & Corrective Actions',
                        'description': 'Discuss challenges and agree on corrective actions',
                        'duration_minutes': 20,
                    },
                    {
                        'title': 'Any Other Business',
                        'description': 'Other matters for discussion',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Next Meeting Date',
                        'description': 'Confirm date for next quarterly meeting',
                        'duration_minutes': 5,
                    },
                ],
            },
            {
                'quarter': 'Q4',
                'name': 'Q4 WSP/ATR Approval Meeting',
                'description': 'Fourth quarterly meeting to review and approve WSP/ATR content before submission',
                'suggested_month': 3,  # March (before 30 April deadline)
                'preparation_notes': 'Prepare: Draft WSP/ATR documents, Employee data summary, Training plan, PIVOTAL plan',
                'default_agenda': [
                    {
                        'title': 'Welcome & Apologies',
                        'description': 'Record attendance and note apologies',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Confirmation of Previous Minutes',
                        'description': 'Review and approve Q3 meeting minutes',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Matters Arising',
                        'description': 'Follow up on action items from Q3 meeting',
                        'duration_minutes': 15,
                    },
                    {
                        'title': 'Year-End Training Report',
                        'description': 'Summary of all training completed in current year',
                        'duration_minutes': 25,
                    },
                    {
                        'title': 'WSP Achievement Review',
                        'description': 'Review achievement against WSP targets',
                        'duration_minutes': 20,
                    },
                    {
                        'title': 'Preliminary Next Year Planning',
                        'description': 'Initial discussion on training priorities for next year',
                        'duration_minutes': 20,
                    },
                    {
                        'title': 'Committee Term Review',
                        'description': 'Review committee membership and terms',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Any Other Business',
                        'description': 'Other matters for discussion',
                        'duration_minutes': 10,
                    },
                    {
                        'title': 'Next Meeting Date (Q1)',
                        'description': 'Confirm date for first meeting of next year',
                        'duration_minutes': 5,
                    },
                ],
            },
        ]
        
        created_count = 0
        for mt_data in meeting_templates:
            existing = MeetingTemplate.objects.filter(quarter=mt_data['quarter']).first()
            
            if existing and not force:
                self.stdout.write(f"  {mt_data['quarter']} template already exists, skipping")
                continue
            
            if existing and force:
                existing.delete()
            
            MeetingTemplate.objects.create(
                quarter=mt_data['quarter'],
                name=mt_data['name'],
                description=mt_data['description'],
                suggested_month=mt_data['suggested_month'],
                preparation_notes=mt_data['preparation_notes'],
                default_agenda=mt_data['default_agenda'],
                is_active=True,
            )
            created_count += 1
            self.stdout.write(self.style.SUCCESS(
                f'  ✓ Created {mt_data["quarter"]} meeting template: {mt_data["name"]}'
            ))
        
        self.stdout.write(self.style.SUCCESS(
            f'  Created {created_count} meeting templates'
        ))
