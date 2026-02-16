"""
Management command to create NOT task templates for automation
"""
from django.core.management.base import BaseCommand

from core.not_automation import NOTTaskTemplate
from core.tasks import TaskCategory, TaskPriority


class Command(BaseCommand):
    help = 'Creates standard NOT task templates for automatic task generation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing templates before creating new ones'
        )

    def handle(self, *args, **options):
        if options['clear']:
            deleted_count, _ = NOTTaskTemplate.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted_count} existing templates'))
        
        self.stdout.write('\n📋 Creating NOT Task Templates...\n')
        
        # =====================================================
        # APPROVED STATUS TASKS
        # =====================================================
        approved_tasks = [
            {
                'name': 'Generate Tranche Schedule',
                'task_title_template': 'Generate tranches for {reference_number}',
                'task_description_template': 'Review and confirm auto-generated tranche schedule for project "{title}". Verify due dates and amounts are correct.',
                'task_category': TaskCategory.TRANCHE_CLAIM,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'COMPLIANCE_LEAD',
                'fallback_campus_role': 'SDF',
                'due_days_offset': 2,
                'sequence': 1,
            },
            {
                'name': 'Submit NOT to SETA',
                'task_title_template': 'Submit NOT {reference_number} to SETA',
                'task_description_template': 'Submit Notification of Training for {learner_count} learners - "{title}" to the relevant SETA portal. Ensure all supporting documentation is included.',
                'task_category': TaskCategory.REGISTRATION_SETA,
                'task_priority': TaskPriority.URGENT,
                'assigned_role': 'COMPLIANCE_LEAD',
                'fallback_campus_role': 'SDF',
                'due_days_offset': 7,
                'sequence': 2,
            },
            {
                'name': 'Create Learner Recruitment Plan',
                'task_title_template': 'Create recruitment plan for {reference_number}',
                'task_description_template': 'Develop learner recruitment strategy and timeline for "{title}". Target: {learner_count} learners. Coordinate with {client_name} if applicable.',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'RECRUITER',
                'fallback_campus_role': 'REGISTRAR',
                'due_days_offset': 5,
                'sequence': 3,
            },
            {
                'name': 'Confirm Facilitator Assignment',
                'task_title_template': 'Confirm facilitator for {reference_number}',
                'task_description_template': 'Confirm facilitator availability and assignment for "{title}" ({qualification}). Verify qualifications and capacity.',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'FACILITATOR',
                'fallback_campus_role': 'ACADEMIC_COORDINATOR',
                'due_days_offset': 5,
                'sequence': 4,
            },
            {
                'name': 'Prepare Learning Materials',
                'task_title_template': 'Prepare materials for {reference_number}',
                'task_description_template': 'Prepare and organize all learning materials, learner guides, and assessment instruments for "{qualification}". Ensure materials are ready for {learner_count} learners.',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.MEDIUM,
                'assigned_role': 'FACILITATOR',
                'fallback_campus_role': 'ACADEMIC_COORDINATOR',
                'due_days_offset': 14,
                'sequence': 5,
            },
            {
                'name': 'Schedule Planning Kickoff',
                'task_title_template': 'Schedule kickoff meeting for {reference_number}',
                'task_description_template': 'Schedule and send invites for project kickoff meeting with all stakeholders for "{title}".',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'PROJECT_LEAD',
                'fallback_campus_role': 'CAMPUS_ADMIN',
                'due_days_offset': 3,
                'sequence': 6,
            },
            {
                'name': 'Verify Venue Availability',
                'task_title_template': 'Confirm venue for {reference_number}',
                'task_description_template': 'Verify and book venue/classroom for "{title}" delivery at {campus}. Ensure capacity for {learner_count} learners.',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.MEDIUM,
                'assigned_role': 'LOGISTICS_LEAD',
                'fallback_campus_role': 'CAMPUS_ADMIN',
                'due_days_offset': 5,
                'sequence': 7,
            },
            {
                'name': 'Create Session Timetable',
                'task_title_template': 'Create timetable for {reference_number}',
                'task_description_template': 'Develop detailed session timetable and training schedule for "{qualification}". Include all modules, assessments, and workplace components.',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.MEDIUM,
                'assigned_role': 'PROJECT_MANAGER',
                'fallback_campus_role': 'ACADEMIC_COORDINATOR',
                'due_days_offset': 7,
                'sequence': 8,
            },
            {
                'name': 'Notify Corporate Client',
                'task_title_template': 'Notify client of approval: {reference_number}',
                'task_description_template': 'Inform {client_name} that project "{title}" has been approved. Confirm next steps and learner nomination timeline.',
                'task_category': TaskCategory.FOLLOW_UP,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'CLIENT_LIAISON',
                'fallback_campus_role': 'SALES_REP',
                'due_days_offset': 2,
                'sequence': 9,
            },
        ]
        
        # =====================================================
        # IN_PROGRESS STATUS TASKS
        # =====================================================
        in_progress_tasks = [
            {
                'name': 'Create Cohort in System',
                'task_title_template': 'Create cohort for {reference_number}',
                'task_description_template': 'Set up cohort/class group in the system for "{title}". Link to qualification "{qualification}" and assign facilitator.',
                'task_category': TaskCategory.ENROLLMENT_PROCESS,
                'task_priority': TaskPriority.URGENT,
                'assigned_role': 'RECRUITER',
                'fallback_campus_role': 'REGISTRAR',
                'due_days_offset': 2,
                'sequence': 1,
            },
            {
                'name': 'Register Learners on SETA Portal',
                'task_title_template': 'Register learners on SETA: {reference_number}',
                'task_description_template': 'Capture all {learner_count} learner registrations on the SETA online portal for "{title}".',
                'task_category': TaskCategory.REGISTRATION_SETA,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'COMPLIANCE_LEAD',
                'fallback_campus_role': 'SDF',
                'due_days_offset': 7,
                'sequence': 2,
            },
            {
                'name': 'Verify Learner Documents',
                'task_title_template': 'Verify learner documents: {reference_number}',
                'task_description_template': 'Verify all learner documentation (IDs, qualifications, proof of residence) for "{title}" enrollment. Flag any outstanding items.',
                'task_category': TaskCategory.DOCUMENT_VERIFICATION,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'RECRUITER',
                'fallback_campus_role': 'REGISTRAR',
                'due_days_offset': 14,
                'sequence': 3,
            },
            {
                'name': 'Send Learner Welcome Packs',
                'task_title_template': 'Send welcome packs: {reference_number}',
                'task_description_template': 'Distribute welcome packs, learner guides, and orientation materials to all {learner_count} learners for "{title}".',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.MEDIUM,
                'assigned_role': 'RECRUITER',
                'fallback_campus_role': 'REGISTRAR',
                'due_days_offset': 3,
                'sequence': 4,
            },
            {
                'name': 'Setup Attendance Tracking',
                'task_title_template': 'Setup attendance for {reference_number}',
                'task_description_template': 'Configure attendance tracking, registers, and QR codes for "{title}" training sessions.',
                'task_category': TaskCategory.ATTENDANCE_CAPTURE,
                'task_priority': TaskPriority.MEDIUM,
                'assigned_role': 'FACILITATOR',
                'fallback_campus_role': 'CAMPUS_ADMIN',
                'due_days_offset': 2,
                'sequence': 5,
            },
            {
                'name': 'Conduct Orientation Session',
                'task_title_template': 'Conduct orientation: {reference_number}',
                'task_description_template': 'Deliver learner orientation session for "{title}". Cover program overview, expectations, assessment requirements, and support services.',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'FACILITATOR',
                'fallback_campus_role': 'ACADEMIC_COORDINATOR',
                'due_days_offset': 5,
                'sequence': 6,
            },
            {
                'name': 'Link Learners to Host Employers',
                'task_title_template': 'Link to employers: {reference_number}',
                'task_description_template': 'Match and link learners to their workplace placement employers for "{title}". Ensure workplace agreements are in place.',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'LOGISTICS_LEAD',
                'fallback_campus_role': 'CAMPUS_ADMIN',
                'due_days_offset': 14,
                'sequence': 7,
            },
        ]
        
        # =====================================================
        # COMPLETED STATUS TASKS
        # =====================================================
        completed_tasks = [
            {
                'name': 'Submit Final Achievements to SETA',
                'task_title_template': 'Submit achievements: {reference_number}',
                'task_description_template': 'Submit all learner achievements and results to SETA for certification. Ensure all PoE files are complete and uploaded.',
                'task_category': TaskCategory.REGISTRATION_SETA,
                'task_priority': TaskPriority.URGENT,
                'assigned_role': 'COMPLIANCE_LEAD',
                'fallback_campus_role': 'SDF',
                'due_days_offset': 14,
                'sequence': 1,
            },
            {
                'name': 'Generate Completion Report',
                'task_title_template': 'Generate completion report: {reference_number}',
                'task_description_template': 'Compile project completion report for "{title}" including learner outcomes, pass rates, and lessons learned.',
                'task_category': TaskCategory.REPORT_DUE,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'PROJECT_MANAGER',
                'fallback_campus_role': 'CAMPUS_ADMIN',
                'due_days_offset': 7,
                'sequence': 2,
            },
            {
                'name': 'Archive Project Documentation',
                'task_title_template': 'Archive project files: {reference_number}',
                'task_description_template': 'Archive all project documentation, PoE files, and learner records according to retention policy for "{title}".',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.LOW,
                'assigned_role': 'PROJECT_MANAGER',
                'fallback_campus_role': 'CAMPUS_ADMIN',
                'due_days_offset': 30,
                'sequence': 3,
            },
            {
                'name': 'Close Out Project Finances',
                'task_title_template': 'Close finances: {reference_number}',
                'task_description_template': 'Finalize all project finances for "{title}". Ensure all tranche claims are submitted and payments received.',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'FINANCE_LEAD',
                'fallback_campus_role': 'FINANCE_CLERK',
                'due_days_offset': 14,
                'sequence': 4,
            },
            {
                'name': 'Collect Learner Feedback',
                'task_title_template': 'Collect feedback: {reference_number}',
                'task_description_template': 'Distribute and collect learner feedback surveys for "{title}". Compile feedback for continuous improvement.',
                'task_category': TaskCategory.FOLLOW_UP,
                'task_priority': TaskPriority.MEDIUM,
                'assigned_role': 'FACILITATOR',
                'fallback_campus_role': 'ACADEMIC_COORDINATOR',
                'due_days_offset': 7,
                'sequence': 5,
            },
            {
                'name': 'Client Satisfaction Survey',
                'task_title_template': 'Client survey: {reference_number}',
                'task_description_template': 'Send satisfaction survey to {client_name} regarding "{title}" delivery. Document feedback and follow-up actions.',
                'task_category': TaskCategory.FOLLOW_UP,
                'task_priority': TaskPriority.MEDIUM,
                'assigned_role': 'CLIENT_LIAISON',
                'fallback_campus_role': 'SALES_REP',
                'due_days_offset': 7,
                'sequence': 6,
            },
        ]
        
        # =====================================================
        # NOTIFICATIONS_SENT STATUS TASKS
        # =====================================================
        notifications_sent_tasks = [
            {
                'name': 'Confirm Stakeholder Acknowledgement',
                'task_title_template': 'Confirm acknowledgements: {reference_number}',
                'task_description_template': 'Follow up with stakeholders who have not acknowledged their notification for "{title}". Ensure all team members are aware of their responsibilities.',
                'task_category': TaskCategory.FOLLOW_UP,
                'task_priority': TaskPriority.MEDIUM,
                'assigned_role': 'PROJECT_LEAD',
                'fallback_campus_role': 'CAMPUS_ADMIN',
                'due_days_offset': 3,
                'sequence': 1,
            },
            {
                'name': 'Finalize Resource Allocation',
                'task_title_template': 'Finalize resources: {reference_number}',
                'task_description_template': 'Confirm all resource allocations and resolve any outstanding shortages for "{title}" before project start.',
                'task_category': TaskCategory.ACTION,
                'task_priority': TaskPriority.HIGH,
                'assigned_role': 'PROJECT_MANAGER',
                'fallback_campus_role': 'CAMPUS_ADMIN',
                'due_days_offset': 5,
                'sequence': 2,
            },
        ]
        
        # =====================================================
        # PENDING_APPROVAL STATUS TASKS
        # =====================================================
        pending_approval_tasks = [
            {
                'name': 'Review and Approve NOT',
                'task_title_template': 'Review NOT for approval: {reference_number}',
                'task_description_template': 'Review Notification of Training "{title}" for approval. Verify resource availability, budget, and stakeholder assignments.',
                'task_category': TaskCategory.APPROVAL,
                'task_priority': TaskPriority.URGENT,
                'assigned_role': 'PROJECT_LEAD',
                'fallback_campus_role': 'CAMPUS_PRINCIPAL',
                'due_days_offset': 5,
                'sequence': 1,
            },
        ]
        
        # Create all templates
        all_templates = [
            ('APPROVED', approved_tasks),
            ('IN_PROGRESS', in_progress_tasks),
            ('COMPLETED', completed_tasks),
            ('NOTIFICATIONS_SENT', notifications_sent_tasks),
            ('PENDING_APPROVAL', pending_approval_tasks),
        ]
        
        created_count = 0
        updated_count = 0
        
        for trigger_status, tasks in all_templates:
            self.stdout.write(f'\n  📌 {trigger_status} Tasks:')
            
            for task_data in tasks:
                template, created = NOTTaskTemplate.objects.update_or_create(
                    trigger_status=trigger_status,
                    name=task_data['name'],
                    defaults={
                        'task_title_template': task_data['task_title_template'],
                        'task_description_template': task_data['task_description_template'],
                        'task_category': task_data['task_category'],
                        'task_priority': task_data['task_priority'],
                        'assigned_role': task_data['assigned_role'],
                        'fallback_campus_role': task_data.get('fallback_campus_role', ''),
                        'due_days_offset': task_data['due_days_offset'],
                        'sequence': task_data['sequence'],
                        'is_active': True,
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f'    ✅ Created: {task_data["name"]}')
                else:
                    updated_count += 1
                    self.stdout.write(f'    🔄 Updated: {task_data["name"]}')
        
        self.stdout.write(self.style.SUCCESS(f'''
✨ NOT Task Templates Complete!
   
   ✅ Created: {created_count}
   🔄 Updated: {updated_count}
   📋 Total: {NOTTaskTemplate.objects.count()}
   
When a NOT status changes, tasks will be automatically created
for the appropriate stakeholders based on these templates.
'''))
