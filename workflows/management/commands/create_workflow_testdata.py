"""
Management command to create test workflow definitions and instances
"""
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from workflows.models import (
    WorkflowDefinition, WorkflowInstance, WorkflowStageHistory,
    Task, UserJourney, Milestone, MilestoneCompletion, WorkflowType
)


class Command(BaseCommand):
    help = 'Creates sample workflow definitions, instances, and milestones'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing workflow data before creating new ones'
        )

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get admin user
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write(self.style.ERROR('No superuser found. Create a superuser first.'))
            return
        
        # Clear existing if requested
        if options['clear']:
            WorkflowStageHistory.objects.all().delete()
            WorkflowInstance.objects.all().delete()
            WorkflowDefinition.objects.all().delete()
            MilestoneCompletion.objects.all().delete()
            UserJourney.objects.all().delete()
            Milestone.objects.all().delete()
            Task.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared existing workflow data'))
        
        # Create Workflow Definitions
        self.stdout.write('\n📋 Creating Workflow Definitions...')
        
        definitions = []
        
        # 1. Learner Onboarding Workflow
        learner_onboarding, created = WorkflowDefinition.objects.update_or_create(
            workflow_type=WorkflowType.LEARNER_ONBOARDING,
            defaults={
                'name': 'Learner Onboarding',
                'description': 'Complete process for onboarding a new learner from registration to active enrollment',
                'is_active': True,
                'stages': [
                    {'name': 'registration', 'display_name': 'Registration', 'order': 1, 'is_final': False},
                    {'name': 'document_collection', 'display_name': 'Document Collection', 'order': 2, 'is_final': False},
                    {'name': 'document_verification', 'display_name': 'Document Verification', 'order': 3, 'is_final': False},
                    {'name': 'seta_registration', 'display_name': 'SETA Registration', 'order': 4, 'is_final': False},
                    {'name': 'cohort_assignment', 'display_name': 'Cohort Assignment', 'order': 5, 'is_final': False},
                    {'name': 'orientation', 'display_name': 'Orientation Complete', 'order': 6, 'is_final': True},
                ],
                'transitions': [
                    {'from_stage': 'registration', 'to_stage': 'document_collection'},
                    {'from_stage': 'document_collection', 'to_stage': 'document_verification'},
                    {'from_stage': 'document_verification', 'to_stage': 'seta_registration'},
                    {'from_stage': 'seta_registration', 'to_stage': 'cohort_assignment'},
                    {'from_stage': 'cohort_assignment', 'to_stage': 'orientation'},
                ],
                'created_by': admin,
            }
        )
        definitions.append(learner_onboarding)
        self.stdout.write(f'  ✅ {learner_onboarding.name}')
        
        # 2. Assessment Journey Workflow
        assessment, created = WorkflowDefinition.objects.update_or_create(
            workflow_type=WorkflowType.ASSESSMENT,
            defaults={
                'name': 'Assessment Journey',
                'description': 'Track assessment from scheduling through moderation to certification',
                'is_active': True,
                'stages': [
                    {'name': 'scheduled', 'display_name': 'Assessment Scheduled', 'order': 1, 'is_final': False},
                    {'name': 'submitted', 'display_name': 'Evidence Submitted', 'order': 2, 'is_final': False},
                    {'name': 'marked', 'display_name': 'Marked', 'order': 3, 'is_final': False},
                    {'name': 'moderated', 'display_name': 'Moderated', 'order': 4, 'is_final': False},
                    {'name': 'verified', 'display_name': 'Verified', 'order': 5, 'is_final': True},
                ],
                'transitions': [
                    {'from_stage': 'scheduled', 'to_stage': 'submitted'},
                    {'from_stage': 'submitted', 'to_stage': 'marked'},
                    {'from_stage': 'marked', 'to_stage': 'moderated'},
                    {'from_stage': 'moderated', 'to_stage': 'verified'},
                    {'from_stage': 'marked', 'to_stage': 'submitted'},  # Return for rework
                ],
                'created_by': admin,
            }
        )
        definitions.append(assessment)
        self.stdout.write(f'  ✅ {assessment.name}')
        
        # 3. Corporate Client Onboarding
        corporate, created = WorkflowDefinition.objects.update_or_create(
            workflow_type=WorkflowType.CORPORATE_ONBOARDING,
            defaults={
                'name': 'Corporate Client Onboarding',
                'description': 'Process for onboarding a new corporate client from lead to active account',
                'is_active': True,
                'stages': [
                    {'name': 'lead', 'display_name': 'Lead Captured', 'order': 1, 'is_final': False},
                    {'name': 'qualification', 'display_name': 'Lead Qualified', 'order': 2, 'is_final': False},
                    {'name': 'proposal', 'display_name': 'Proposal Sent', 'order': 3, 'is_final': False},
                    {'name': 'negotiation', 'display_name': 'Negotiation', 'order': 4, 'is_final': False},
                    {'name': 'contracted', 'display_name': 'Contract Signed', 'order': 5, 'is_final': False},
                    {'name': 'active', 'display_name': 'Account Active', 'order': 6, 'is_final': True},
                ],
                'transitions': [
                    {'from_stage': 'lead', 'to_stage': 'qualification'},
                    {'from_stage': 'qualification', 'to_stage': 'proposal'},
                    {'from_stage': 'proposal', 'to_stage': 'negotiation'},
                    {'from_stage': 'negotiation', 'to_stage': 'contracted'},
                    {'from_stage': 'contracted', 'to_stage': 'active'},
                    {'from_stage': 'negotiation', 'to_stage': 'proposal'},  # Back to proposal
                ],
                'created_by': admin,
            }
        )
        definitions.append(corporate)
        self.stdout.write(f'  ✅ {corporate.name}')
        
        # 4. Grant Application Workflow
        grant, created = WorkflowDefinition.objects.update_or_create(
            workflow_type=WorkflowType.GRANT_APPLICATION,
            defaults={
                'name': 'Grant Application',
                'description': 'SETA grant application process from submission to approval',
                'is_active': True,
                'stages': [
                    {'name': 'draft', 'display_name': 'Application Draft', 'order': 1, 'is_final': False},
                    {'name': 'submitted', 'display_name': 'Submitted to SETA', 'order': 2, 'is_final': False},
                    {'name': 'under_review', 'display_name': 'Under Review', 'order': 3, 'is_final': False},
                    {'name': 'additional_info', 'display_name': 'Additional Info Requested', 'order': 4, 'is_final': False},
                    {'name': 'approved', 'display_name': 'Approved', 'order': 5, 'is_final': True},
                ],
                'transitions': [
                    {'from_stage': 'draft', 'to_stage': 'submitted'},
                    {'from_stage': 'submitted', 'to_stage': 'under_review'},
                    {'from_stage': 'under_review', 'to_stage': 'additional_info'},
                    {'from_stage': 'additional_info', 'to_stage': 'under_review'},
                    {'from_stage': 'under_review', 'to_stage': 'approved'},
                ],
                'created_by': admin,
            }
        )
        definitions.append(grant)
        self.stdout.write(f'  ✅ {grant.name}')
        
        # Create sample workflow instances
        self.stdout.write('\n📊 Creating Workflow Instances...')
        
        # Learner onboarding instances at different stages
        stages_for_instances = [
            ('registration', 'in_progress'),
            ('document_collection', 'in_progress'),
            ('document_verification', 'in_progress'),
            ('seta_registration', 'active'),
            ('orientation', 'completed'),
        ]
        
        for idx, (stage, status) in enumerate(stages_for_instances, 1):
            instance, created = WorkflowInstance.objects.get_or_create(
                definition=learner_onboarding,
                entity_type='learner',
                entity_id=idx,  # Different entity IDs
                defaults={
                    'current_stage': stage,
                    'status': 'completed' if stage == 'orientation' else 'active',
                    'context_data': {'learner_name': f'Sample Learner {stage.title()}'},
                    'created_by': admin,
                }
            )
            
            if created:
                # Add stage history
                WorkflowStageHistory.objects.create(
                    workflow_instance=instance,
                    from_stage='',
                    to_stage='registration',
                    transitioned_by=admin,
                    notes='Workflow started',
                )
                
                if stage != 'registration':
                    WorkflowStageHistory.objects.create(
                        workflow_instance=instance,
                        from_stage='registration',
                        to_stage=stage,
                        transitioned_by=admin,
                        notes=f'Progressed to {stage}',
                    )
            
            self.stdout.write(f'  ✅ Instance at stage: {stage}')
        
        # Create Milestones for Learner Journey
        self.stdout.write('\n🏆 Creating Journey Milestones...')
        
        learner_milestones = [
            {'name': 'registered', 'display_name': 'Successfully Registered', 'description': 'Complete registration and submit all required documents', 'points': 10, 'icon': 'user-check', 'color': 'blue'},
            {'name': 'documents_approved', 'display_name': 'Documents Approved', 'description': 'All submitted documents have been verified', 'points': 15, 'icon': 'file-check', 'color': 'green'},
            {'name': 'seta_registered', 'display_name': 'SETA Registered', 'description': 'Successfully registered with the SETA', 'points': 20, 'icon': 'award', 'color': 'purple'},
            {'name': 'first_module', 'display_name': 'First Module Complete', 'description': 'Complete your first learning module', 'points': 25, 'icon': 'book-open', 'color': 'yellow'},
            {'name': 'first_assessment', 'display_name': 'First Assessment Passed', 'description': 'Pass your first competency assessment', 'points': 30, 'icon': 'check-circle', 'color': 'green'},
            {'name': 'halfway', 'display_name': 'Halfway There!', 'description': 'Complete 50% of your program requirements', 'points': 40, 'icon': 'trending-up', 'color': 'blue'},
            {'name': 'poe_complete', 'display_name': 'PoE Complete', 'description': 'Complete and submit your Portfolio of Evidence', 'points': 50, 'icon': 'folder-check', 'color': 'purple'},
            {'name': 'certified', 'display_name': 'Certification Achieved!', 'description': 'Successfully achieve your qualification', 'points': 100, 'icon': 'award', 'color': 'gold'},
        ]
        
        for order, milestone_data in enumerate(learner_milestones, 1):
            milestone, created = Milestone.objects.update_or_create(
                journey_type='learner',
                name=milestone_data['name'],
                defaults={
                    'display_name': milestone_data['display_name'],
                    'description': milestone_data['description'],
                    'order': order,
                    'points': milestone_data['points'],
                    'icon': milestone_data['icon'],
                    'color': milestone_data['color'],
                }
            )
            self.stdout.write(f'  ✅ {milestone.display_name}')
        
        # Create sample user journey
        self.stdout.write('\n🚀 Creating Sample User Journey...')
        
        journey, created = UserJourney.objects.update_or_create(
            user=admin,
            journey_type='learner',
            entity_type='enrollment',
            entity_id=1,
            defaults={
                'overall_progress': 37,
                'current_milestone': 'first_assessment',
                'points_earned': 70,
                'badges': ['beginner'],
                'created_by': admin,
            }
        )
        
        # Mark first 3 milestones as complete
        completed_milestones = Milestone.objects.filter(
            journey_type='learner',
            name__in=['registered', 'documents_approved', 'seta_registered']
        )
        for milestone in completed_milestones:
            MilestoneCompletion.objects.get_or_create(
                user_journey=journey,
                milestone=milestone,
            )
        
        self.stdout.write(f'  ✅ User journey created with {completed_milestones.count()} milestones completed')
        
        # Create sample workflow tasks
        self.stdout.write('\n📝 Creating Sample Workflow Tasks...')
        
        # Comprehensive task list for admins and facilitators
        task_data = [
            # === QC / Quality Assurance Tasks ===
            {'name': 'QC Internal Moderation Sample', 'description': 'Select and quality check 10% sample of marked assessments for internal moderation', 'priority': 'high', 'status': 'pending'},
            {'name': 'QC External Moderation Preparation', 'description': 'Prepare PoE files and documentation for upcoming external moderation visit', 'priority': 'urgent', 'status': 'in_progress'},
            {'name': 'QC Assessor Feedback Review', 'description': 'Review and action feedback from QA on assessor marking consistency', 'priority': 'medium', 'status': 'pending'},
            {'name': 'QC Site Visit Checklist', 'description': 'Complete pre-visit QC checklist for workplace site verification', 'priority': 'high', 'status': 'pending'},
            
            # === Learner Management Tasks ===
            {'name': 'Link Learners to Cohort B2024-03', 'description': 'Assign 15 new learners to Business Admin cohort starting next week', 'priority': 'high', 'status': 'pending'},
            {'name': 'Update Learner Contact Details', 'description': 'Verify and update contact information for learners with bounced emails', 'priority': 'medium', 'status': 'pending'},
            {'name': 'Link Learners to Host Employers', 'description': 'Match and link 8 learners to their workplace placement employers', 'priority': 'high', 'status': 'in_progress'},
            {'name': 'Process Learner Transfer Request', 'description': 'Process transfer request for learner moving to different campus', 'priority': 'medium', 'status': 'pending'},
            
            # === Project Management Tasks ===
            {'name': 'Create New SETA Project', 'description': 'Set up new discretionary grant project for CATHSSETA - 50 learners', 'priority': 'urgent', 'status': 'pending'},
            {'name': 'Update Project Milestones', 'description': 'Update milestone completion status for MERSETA learnerships project', 'priority': 'high', 'status': 'pending'},
            {'name': 'Create Corporate Training Project', 'description': 'Set up skills program project for ABC Corporation - Management Development', 'priority': 'medium', 'status': 'pending'},
            {'name': 'Close Out Completed Project', 'description': 'Finalize and close BANKSETA project - generate completion report', 'priority': 'medium', 'status': 'pending'},
            
            # === ETQA / SETA Submissions ===
            {'name': 'Submit NOT to SETA', 'description': 'Submit Notification of Training for 25 new learners to SERVICES SETA', 'priority': 'urgent', 'status': 'pending'},
            {'name': 'Submit Tranche 1 Claim', 'description': 'Compile and submit Tranche 1 evidence package to MERSETA for payment', 'priority': 'urgent', 'status': 'in_progress'},
            {'name': 'Upload PoE to SETA Portal', 'description': 'Upload digitized PoE files to FASSET online submission portal', 'priority': 'high', 'status': 'pending'},
            {'name': 'Submit Learner Achievements', 'description': 'Submit batch of 12 learner achievements for certification to ETDPSETA', 'priority': 'high', 'status': 'pending'},
            {'name': 'Respond to ETQA Query', 'description': 'Address QCTO query regarding assessment evidence for NC: Generic Management', 'priority': 'urgent', 'status': 'pending'},
            {'name': 'Submit ATR Report', 'description': 'Compile and submit Annual Training Report for corporate client', 'priority': 'high', 'status': 'pending'},
            
            # === SETA/QCTO Registration Tasks ===
            {'name': 'Register Learners on SETA System', 'description': 'Capture 20 new learner registrations on INSETA online system', 'priority': 'high', 'status': 'pending'},
            {'name': 'Register with QCTO', 'description': 'Complete QCTO registration for new occupational qualification delivery', 'priority': 'urgent', 'status': 'pending'},
            {'name': 'Update SETA Learner Records', 'description': 'Update completion status for 15 learners on W&RSETA portal', 'priority': 'medium', 'status': 'pending'},
            {'name': 'Register New Assessors with SETA', 'description': 'Submit assessor registration applications to HWSETA for 3 new assessors', 'priority': 'high', 'status': 'pending'},
            {'name': 'Renew ETDP SETA Accreditation', 'description': 'Prepare and submit accreditation renewal application', 'priority': 'urgent', 'status': 'in_progress'},
            
            # === Stakeholder Follow-ups ===
            {'name': 'Follow Up: Corporate Client WSP', 'description': 'Follow up with XYZ Company regarding outstanding WSP submission documents', 'priority': 'high', 'status': 'pending'},
            {'name': 'Follow Up: Host Employer Site Visit', 'description': 'Confirm site visit date with Acme Industries for learner workplace assessment', 'priority': 'medium', 'status': 'pending'},
            {'name': 'Follow Up: SETA Grant Payment', 'description': 'Follow up with TETA regarding delayed Tranche 2 payment', 'priority': 'urgent', 'status': 'pending'},
            {'name': 'Follow Up: Employer Stipend Contribution', 'description': 'Contact employer regarding outstanding learner stipend contribution', 'priority': 'high', 'status': 'pending'},
            {'name': 'Follow Up: External Moderator Report', 'description': 'Request outstanding moderation report from external moderator', 'priority': 'medium', 'status': 'pending'},
            {'name': 'Follow Up: Learner Documents', 'description': 'Contact 5 learners regarding outstanding certified ID copies', 'priority': 'high', 'status': 'pending'},
            
            # === Data Gathering & Reporting ===
            {'name': 'Gather Learner Employment Data', 'description': 'Collect post-training employment status for tracer study report', 'priority': 'medium', 'status': 'pending'},
            {'name': 'Compile Monthly Training Stats', 'description': 'Gather data for monthly training delivery statistics report', 'priority': 'high', 'status': 'pending'},
            {'name': 'Gather WSP/ATR Data', 'description': 'Collect training data from 3 corporate clients for WSP submission', 'priority': 'high', 'status': 'pending'},
            {'name': 'Update Learner Demographics', 'description': 'Verify and update demographic data for BBBEE reporting', 'priority': 'medium', 'status': 'pending'},
            {'name': 'Gather Placement Evidence', 'description': 'Collect workplace placement confirmation letters from 10 host employers', 'priority': 'high', 'status': 'in_progress'},
            
            # === Facilitator Tasks ===
            {'name': 'Prepare Session Materials', 'description': 'Prepare learning materials and handouts for tomorrow\'s Generic Management session', 'priority': 'high', 'status': 'pending'},
            {'name': 'Capture Attendance Register', 'description': 'Upload attendance register for yesterday\'s training session', 'priority': 'urgent', 'status': 'pending'},
            {'name': 'Mark Formative Assessments', 'description': 'Mark 25 formative assessment submissions - Business Communication module', 'priority': 'high', 'status': 'in_progress'},
            {'name': 'Capture Assessment Results', 'description': 'Capture summative assessment results for 18 learners into system', 'priority': 'high', 'status': 'pending'},
            {'name': 'Update Learner Progress', 'description': 'Update module completion status for Cohort A learners', 'priority': 'medium', 'status': 'pending'},
            {'name': 'Provide Learner Feedback', 'description': 'Send individual feedback to 5 learners on NYC assessment results', 'priority': 'high', 'status': 'pending'},
            {'name': 'Complete Logbook Verification', 'description': 'Verify and sign off learner workplace logbooks for month-end', 'priority': 'high', 'status': 'pending'},
            {'name': 'Conduct Learner Support Session', 'description': 'Schedule and conduct support session for at-risk learners', 'priority': 'urgent', 'status': 'pending'},
            {'name': 'Prepare PoE Compilation Guide', 'description': 'Create step-by-step guide for learners on PoE compilation', 'priority': 'medium', 'status': 'pending'},
            {'name': 'Review Learner PoE Files', 'description': 'Review 8 learner PoE files for completeness before submission', 'priority': 'high', 'status': 'pending'},
            {'name': 'Schedule Practical Assessments', 'description': 'Coordinate practical assessment dates with workplace supervisors', 'priority': 'high', 'status': 'pending'},
            {'name': 'Complete Assessor Report', 'description': 'Complete assessor report for external moderation submission', 'priority': 'high', 'status': 'in_progress'},
            
            # === Document Management ===
            {'name': 'Scan and Upload Certificates', 'description': 'Digitize and upload 30 learner qualification certificates', 'priority': 'medium', 'status': 'pending'},
            {'name': 'Archive Completed PoE Files', 'description': 'Archive completed PoE files according to retention policy', 'priority': 'low', 'status': 'pending'},
            {'name': 'Verify Document Authenticity', 'description': 'Verify authenticity of 10 submitted qualification certificates', 'priority': 'high', 'status': 'pending'},
            {'name': 'Prepare Certification Pack', 'description': 'Compile certification request pack for SETA submission', 'priority': 'high', 'status': 'pending'},
        ]
        
        for data in task_data:
            task = Task.objects.create(
                name=data['name'],
                description=data['description'],
                priority=data['priority'],
                status=data['status'],
                assigned_to=admin,
                due_date=timezone.now().date() + timedelta(days=random.randint(1, 14)),
                created_by=admin,
            )
            self.stdout.write(f'  ✅ {task.name}')
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'''
✨ Workflow Test Data Created Successfully!
   
   📋 Workflow Definitions: {len(definitions)}
   📊 Workflow Instances: {WorkflowInstance.objects.count()}
   🏆 Milestones: {Milestone.objects.count()}
   🚀 User Journeys: {UserJourney.objects.count()}
   📝 Workflow Tasks: {Task.objects.count()}
   
Visit:
   - /workflows/instances/ - View workflow instances
   - /workflows/tasks/ - View workflow tasks  
   - /workflows/journey/ - View user journey
'''))
