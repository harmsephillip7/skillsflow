"""
Management command to seed ServiceDeliveryTemplate with predefined milestones
for each service type.
"""
from django.core.management.base import BaseCommand
from corporate.models import (
    ServiceDeliveryTemplate, ServiceDeliveryTemplateMilestone, ServiceOffering
)


class Command(BaseCommand):
    help = 'Seed ServiceDeliveryTemplate with predefined milestones for each service type'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of templates (deletes existing)',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        
        # Define templates for each service type
        templates = self.get_template_definitions()
        
        created_count = 0
        updated_count = 0
        
        for service_type, template_data in templates.items():
            existing = ServiceDeliveryTemplate.objects.filter(service_type=service_type).first()
            
            if existing and not force:
                self.stdout.write(f"  Template for {service_type} already exists, skipping")
                continue
            
            if existing and force:
                existing.delete()
                self.stdout.write(f"  Deleted existing template for {service_type}")
            
            # Create the template
            template = ServiceDeliveryTemplate.objects.create(
                service_type=service_type,
                name=template_data['name'],
                description=template_data['description'],
                default_duration_days=template_data['duration_days'],
                is_active=True
            )
            
            # Create milestones
            for i, milestone in enumerate(template_data['milestones'], 1):
                ServiceDeliveryTemplateMilestone.objects.create(
                    template=template,
                    name=milestone['name'],
                    description=milestone.get('description', ''),
                    sequence=i,
                    days_from_start=milestone.get('days_from_start', 0),
                    duration_days=milestone.get('duration_days', 7),
                    weight=milestone.get('weight', 1),
                    requires_evidence=milestone.get('requires_evidence', False),
                    evidence_description=milestone.get('evidence_description', ''),
                )
            
            created_count += 1
            self.stdout.write(self.style.SUCCESS(
                f"  Created template: {template_data['name']} with {len(template_data['milestones'])} milestones"
            ))
        
        self.stdout.write(self.style.SUCCESS(
            f"\nSeed completed: {created_count} templates created"
        ))

    def get_template_definitions(self):
        """Return predefined templates for each service type."""
        return {
            # =========== TRAINING SERVICES ===========
            'LEARNERSHIP': {
                'name': 'Learnership Delivery',
                'description': 'Standard milestones for learnership programme delivery',
                'duration_days': 365,
                'milestones': [
                    {
                        'name': 'Learner Recruitment & Selection',
                        'description': 'Recruit, screen and select learners for the programme',
                        'days_from_start': 0,
                        'duration_days': 14,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Selection criteria, interview records, selection report',
                    },
                    {
                        'name': 'Learner Registration & SETA Upload',
                        'description': 'Register learners and upload to SETA system',
                        'days_from_start': 14,
                        'duration_days': 7,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'SETA registration confirmations, learner agreements',
                    },
                    {
                        'name': 'Induction & Onboarding',
                        'description': 'Conduct learner induction and workplace onboarding',
                        'days_from_start': 21,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Induction attendance register, learner handbook acknowledgement',
                    },
                    {
                        'name': 'Phase 1 Training Delivery',
                        'description': 'Deliver first phase of institutional training',
                        'days_from_start': 26,
                        'duration_days': 60,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Attendance registers, assessment results, POE samples',
                    },
                    {
                        'name': 'Workplace Integration 1',
                        'description': 'First workplace experience period with mentor support',
                        'days_from_start': 86,
                        'duration_days': 45,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Workplace logbook, mentor reports, workplace visit reports',
                    },
                    {
                        'name': 'Phase 2 Training Delivery',
                        'description': 'Deliver second phase of institutional training',
                        'days_from_start': 131,
                        'duration_days': 60,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Attendance registers, assessment results, POE samples',
                    },
                    {
                        'name': 'Workplace Integration 2',
                        'description': 'Second workplace experience period',
                        'days_from_start': 191,
                        'duration_days': 45,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Workplace logbook, mentor reports, workplace visit reports',
                    },
                    {
                        'name': 'Phase 3 Training Delivery',
                        'description': 'Deliver final phase of institutional training',
                        'days_from_start': 236,
                        'duration_days': 60,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Attendance registers, assessment results, POE samples',
                    },
                    {
                        'name': 'Final Workplace Integration',
                        'description': 'Final workplace experience and consolidation',
                        'days_from_start': 296,
                        'duration_days': 45,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Workplace logbook, mentor reports, competency signoff',
                    },
                    {
                        'name': 'External Moderation',
                        'description': 'Submit learner POEs for external moderation',
                        'days_from_start': 341,
                        'duration_days': 14,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Moderation reports, corrective action (if applicable)',
                    },
                    {
                        'name': 'Certification & Closeout',
                        'description': 'Request certificates and close out learner files',
                        'days_from_start': 355,
                        'duration_days': 10,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Certificate requests, learner completion report',
                    },
                ]
            },
            
            'SKILLS_PROGRAMME': {
                'name': 'Skills Programme Delivery',
                'description': 'Standard milestones for skills programme delivery',
                'duration_days': 90,
                'milestones': [
                    {
                        'name': 'Learner Registration',
                        'description': 'Register learners and complete enrollment documentation',
                        'days_from_start': 0,
                        'duration_days': 7,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Registration forms, ID copies, learner agreements',
                    },
                    {
                        'name': 'SETA Upload & Confirmation',
                        'description': 'Upload learners to SETA and confirm registration',
                        'days_from_start': 7,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'SETA upload confirmation, learner numbers',
                    },
                    {
                        'name': 'Training Delivery',
                        'description': 'Deliver skills programme training',
                        'days_from_start': 12,
                        'duration_days': 45,
                        'weight': 3,
                        'requires_evidence': True,
                        'evidence_description': 'Attendance registers, daily sign-in sheets',
                    },
                    {
                        'name': 'Formative Assessment',
                        'description': 'Conduct formative assessments',
                        'days_from_start': 57,
                        'duration_days': 10,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Assessment instruments, learner submissions, marking rubrics',
                    },
                    {
                        'name': 'Summative Assessment',
                        'description': 'Conduct summative assessments and compile POEs',
                        'days_from_start': 67,
                        'duration_days': 10,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Assessment results, POE files, declaration forms',
                    },
                    {
                        'name': 'Internal Moderation',
                        'description': 'Complete internal moderation of assessments',
                        'days_from_start': 77,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Internal moderation reports, sample selection',
                    },
                    {
                        'name': 'Certification Request',
                        'description': 'Submit certification request and complete closeout',
                        'days_from_start': 82,
                        'duration_days': 8,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Certification request, completion report',
                    },
                ]
            },
            
            'APPRENTICESHIP': {
                'name': 'Apprenticeship Delivery',
                'description': 'Standard milestones for apprenticeship programme delivery',
                'duration_days': 1095,  # 3 years
                'milestones': [
                    {
                        'name': 'Apprentice Selection & Contracting',
                        'description': 'Select apprentices and register contracts',
                        'days_from_start': 0,
                        'duration_days': 21,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Selection report, apprentice contracts, NAMB registration',
                    },
                    {
                        'name': 'Year 1 - Phase 1 Training',
                        'description': 'First institutional training block',
                        'days_from_start': 21,
                        'duration_days': 90,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Attendance, assessments, competency records',
                    },
                    {
                        'name': 'Year 1 - Workplace Experience',
                        'description': 'First year workplace practical experience',
                        'days_from_start': 111,
                        'duration_days': 254,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Logbook, mentor reports, workplace assessments',
                    },
                    {
                        'name': 'Year 2 - Phase 2 Training',
                        'description': 'Second institutional training block',
                        'days_from_start': 365,
                        'duration_days': 90,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Attendance, assessments, competency records',
                    },
                    {
                        'name': 'Year 2 - Workplace Experience',
                        'description': 'Second year workplace practical experience',
                        'days_from_start': 455,
                        'duration_days': 275,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Logbook, mentor reports, workplace assessments',
                    },
                    {
                        'name': 'Year 3 - Phase 3 Training',
                        'description': 'Third institutional training block',
                        'days_from_start': 730,
                        'duration_days': 90,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Attendance, assessments, competency records',
                    },
                    {
                        'name': 'Year 3 - Final Workplace Experience',
                        'description': 'Final year workplace practical experience',
                        'days_from_start': 820,
                        'duration_days': 245,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Logbook, mentor reports, workplace assessments',
                    },
                    {
                        'name': 'Trade Test Preparation',
                        'description': 'Prepare apprentice for trade test',
                        'days_from_start': 1065,
                        'duration_days': 14,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Readiness assessment, trade test application',
                    },
                    {
                        'name': 'Trade Test & Certification',
                        'description': 'Complete trade test and obtain certification',
                        'days_from_start': 1079,
                        'duration_days': 16,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Trade test result, certificate',
                    },
                ]
            },
            
            'INTERNSHIP': {
                'name': 'Internship Programme Delivery',
                'description': 'Standard milestones for internship programme delivery',
                'duration_days': 365,
                'milestones': [
                    {
                        'name': 'Intern Selection & Placement',
                        'description': 'Select interns and match to host departments',
                        'days_from_start': 0,
                        'duration_days': 14,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Selection report, placement letters',
                    },
                    {
                        'name': 'Onboarding & Orientation',
                        'description': 'Conduct intern induction and workplace orientation',
                        'days_from_start': 14,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Induction register, workplace orientation checklist',
                    },
                    {
                        'name': 'Q1 - Workplace Experience',
                        'description': 'First quarter workplace experience',
                        'days_from_start': 19,
                        'duration_days': 71,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Monthly reports, supervisor feedback',
                    },
                    {
                        'name': 'Q2 - Workplace Experience',
                        'description': 'Second quarter workplace experience',
                        'days_from_start': 90,
                        'duration_days': 91,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Monthly reports, supervisor feedback, mid-year review',
                    },
                    {
                        'name': 'Q3 - Workplace Experience',
                        'description': 'Third quarter workplace experience',
                        'days_from_start': 181,
                        'duration_days': 92,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Monthly reports, supervisor feedback',
                    },
                    {
                        'name': 'Q4 - Workplace Experience',
                        'description': 'Fourth quarter workplace experience',
                        'days_from_start': 273,
                        'duration_days': 77,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Monthly reports, supervisor feedback, final review',
                    },
                    {
                        'name': 'Completion & Closeout',
                        'description': 'Complete internship and issue completion letter',
                        'days_from_start': 350,
                        'duration_days': 15,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Completion report, experience letter',
                    },
                ]
            },
            
            # =========== CONSULTING SERVICES ===========
            'WSP_ATR': {
                'name': 'WSP/ATR Submission',
                'description': 'Standard milestones for WSP/ATR compilation and submission',
                'duration_days': 60,
                'milestones': [
                    {
                        'name': 'Data Collection',
                        'description': 'Collect employment and training data from client',
                        'days_from_start': 0,
                        'duration_days': 14,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Employee data spreadsheet, training records',
                    },
                    {
                        'name': 'Skills Gap Analysis',
                        'description': 'Conduct skills audit and gap analysis',
                        'days_from_start': 14,
                        'duration_days': 10,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Skills audit report, gap analysis',
                    },
                    {
                        'name': 'WSP Compilation',
                        'description': 'Compile Workplace Skills Plan document',
                        'days_from_start': 24,
                        'duration_days': 10,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Draft WSP document',
                    },
                    {
                        'name': 'ATR Compilation',
                        'description': 'Compile Annual Training Report document',
                        'days_from_start': 24,
                        'duration_days': 10,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Draft ATR document',
                    },
                    {
                        'name': 'Client Review & Approval',
                        'description': 'Client reviews and approves WSP/ATR documents',
                        'days_from_start': 34,
                        'duration_days': 7,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Signed approval form',
                    },
                    {
                        'name': 'SETA Submission',
                        'description': 'Submit WSP/ATR to SETA before deadline',
                        'days_from_start': 41,
                        'duration_days': 5,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'SETA submission confirmation, reference number',
                    },
                    {
                        'name': 'Grant Application',
                        'description': 'Complete and submit discretionary grant application if applicable',
                        'days_from_start': 46,
                        'duration_days': 14,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Grant application, supporting documents',
                    },
                ]
            },
            
            'EE_REPORTING': {
                'name': 'Employment Equity Reporting',
                'description': 'Standard milestones for EE plan and reporting',
                'duration_days': 45,
                'milestones': [
                    {
                        'name': 'Workforce Analysis',
                        'description': 'Analyse current workforce demographics',
                        'days_from_start': 0,
                        'duration_days': 7,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Workforce analysis report',
                    },
                    {
                        'name': 'EE Committee Consultation',
                        'description': 'Consult with EE committee on findings and targets',
                        'days_from_start': 7,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Committee meeting minutes',
                    },
                    {
                        'name': 'EE Plan Development',
                        'description': 'Develop/update Employment Equity Plan',
                        'days_from_start': 12,
                        'duration_days': 10,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Draft EE Plan',
                    },
                    {
                        'name': 'EEA2/EEA4 Compilation',
                        'description': 'Compile statutory EE reports',
                        'days_from_start': 22,
                        'duration_days': 10,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'EEA2 and EEA4 forms',
                    },
                    {
                        'name': 'Client Review & Signoff',
                        'description': 'Client reviews and signs off reports',
                        'days_from_start': 32,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Signed declaration',
                    },
                    {
                        'name': 'DOL Submission',
                        'description': 'Submit EE reports to Department of Labour',
                        'days_from_start': 37,
                        'duration_days': 8,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Submission confirmation',
                    },
                ]
            },
            
            'BBBEE_VERIFICATION': {
                'name': 'BBBEE Verification',
                'description': 'Standard milestones for BBBEE verification process',
                'duration_days': 30,
                'milestones': [
                    {
                        'name': 'Document Collection',
                        'description': 'Collect all required BBBEE supporting documents',
                        'days_from_start': 0,
                        'duration_days': 10,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Document checklist, collected documents',
                    },
                    {
                        'name': 'Pre-assessment Review',
                        'description': 'Review documents and identify gaps',
                        'days_from_start': 10,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Gap analysis report',
                    },
                    {
                        'name': 'Verification Agency Engagement',
                        'description': 'Engage SANAS-accredited verification agency',
                        'days_from_start': 15,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Agency engagement letter',
                    },
                    {
                        'name': 'Verification Process',
                        'description': 'Complete verification with agency',
                        'days_from_start': 20,
                        'duration_days': 7,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Verification worksheets',
                    },
                    {
                        'name': 'Certificate Issuance',
                        'description': 'Receive BBBEE certificate',
                        'days_from_start': 27,
                        'duration_days': 3,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'BBBEE certificate',
                    },
                ]
            },
            
            'GRANT_MANAGEMENT': {
                'name': 'SETA Grant Management',
                'description': 'Standard milestones for discretionary grant management',
                'duration_days': 365,
                'milestones': [
                    {
                        'name': 'Grant Application',
                        'description': 'Prepare and submit grant application',
                        'days_from_start': 0,
                        'duration_days': 14,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Application form, supporting documents',
                    },
                    {
                        'name': 'Grant Approval & Contracting',
                        'description': 'Receive approval and sign grant agreement',
                        'days_from_start': 14,
                        'duration_days': 30,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Approval letter, signed MOA',
                    },
                    {
                        'name': 'Tranche 1 Claim',
                        'description': 'Submit first tranche claim (commencement)',
                        'days_from_start': 44,
                        'duration_days': 14,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Tranche 1 claim, registration evidence',
                    },
                    {
                        'name': 'Progress Reporting - Q1',
                        'description': 'Submit first quarterly progress report',
                        'days_from_start': 90,
                        'duration_days': 7,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Progress report, attendance records',
                    },
                    {
                        'name': 'Progress Reporting - Q2',
                        'description': 'Submit second quarterly progress report',
                        'days_from_start': 180,
                        'duration_days': 7,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Progress report, attendance records',
                    },
                    {
                        'name': 'Tranche 2 Claim',
                        'description': 'Submit second tranche claim (completion)',
                        'days_from_start': 270,
                        'duration_days': 14,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Tranche 2 claim, completion evidence',
                    },
                    {
                        'name': 'Final Report & Closeout',
                        'description': 'Submit final report and close grant project',
                        'days_from_start': 350,
                        'duration_days': 15,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Final report, financial reconciliation',
                    },
                ]
            },
            
            # =========== OTHER SERVICES ===========
            'FACILITATION': {
                'name': 'Training Facilitation',
                'description': 'Standard milestones for facilitated training delivery',
                'duration_days': 30,
                'milestones': [
                    {
                        'name': 'Training Preparation',
                        'description': 'Prepare training materials and venue',
                        'days_from_start': 0,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Materials checklist, venue confirmation',
                    },
                    {
                        'name': 'Training Delivery',
                        'description': 'Deliver training sessions',
                        'days_from_start': 5,
                        'duration_days': 15,
                        'weight': 3,
                        'requires_evidence': True,
                        'evidence_description': 'Attendance registers, session photos',
                    },
                    {
                        'name': 'Assessment & Evaluation',
                        'description': 'Conduct assessments and training evaluation',
                        'days_from_start': 20,
                        'duration_days': 5,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Assessment results, evaluation forms',
                    },
                    {
                        'name': 'Reporting & Closeout',
                        'description': 'Compile training report and close out',
                        'days_from_start': 25,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Training report, attendance summary',
                    },
                ]
            },
            
            'CONSULTING': {
                'name': 'General Consulting',
                'description': 'Standard milestones for consulting engagements',
                'duration_days': 45,
                'milestones': [
                    {
                        'name': 'Discovery & Scoping',
                        'description': 'Understand client needs and define scope',
                        'days_from_start': 0,
                        'duration_days': 7,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Discovery notes, scope document',
                    },
                    {
                        'name': 'Analysis & Research',
                        'description': 'Conduct analysis and research',
                        'days_from_start': 7,
                        'duration_days': 14,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Analysis report, findings summary',
                    },
                    {
                        'name': 'Solution Development',
                        'description': 'Develop recommendations and solutions',
                        'days_from_start': 21,
                        'duration_days': 10,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Recommendations document',
                    },
                    {
                        'name': 'Client Presentation',
                        'description': 'Present findings and recommendations to client',
                        'days_from_start': 31,
                        'duration_days': 5,
                        'weight': 1,
                        'requires_evidence': True,
                        'evidence_description': 'Presentation slides, meeting notes',
                    },
                    {
                        'name': 'Implementation Support',
                        'description': 'Support client with implementation',
                        'days_from_start': 36,
                        'duration_days': 9,
                        'weight': 2,
                        'requires_evidence': True,
                        'evidence_description': 'Implementation plan, support log',
                    },
                ]
            },
        }
