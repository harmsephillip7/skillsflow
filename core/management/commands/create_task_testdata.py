"""
Management command to create test tasks for development
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from core.tasks import Task, TaskCategory, TaskStatus, TaskPriority
from tenants.models import Campus
from learners.models import Learner


class Command(BaseCommand):
    help = 'Creates sample tasks for testing the Task Hub'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=30,
            help='Number of tasks to create (default: 30)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing tasks before creating new ones'
        )

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get admin user
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write(self.style.ERROR('No superuser found. Create a superuser first.'))
            return
        
        # Get campus
        campus = Campus.objects.first()
        if not campus:
            self.stderr.write(self.style.ERROR('No campus found. Create a campus first.'))
            return
        
        # Clear existing if requested
        if options['clear']:
            deleted_count, _ = Task.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted_count} existing tasks'))
        
        count = options['count']
        today = timezone.now().date()
        
        # Sample task data - comprehensive SETA/training provider tasks
        task_templates = [
            # Document Verification tasks
            {
                'category': TaskCategory.DOCUMENT_VERIFICATION,
                'titles': [
                    'Verify ID document for {learner}',
                    'Check qualification certificates for {learner}',
                    'Validate proof of residence for {learner}',
                    'Review uploaded documents for {learner}',
                    'Verify matric certificate for {learner}',
                    'Check SARS tax number documentation',
                    'Validate bank confirmation letter',
                ],
            },
            # Assessment marking tasks
            {
                'category': TaskCategory.ASSESSMENT_MARK,
                'titles': [
                    'Mark Unit Standard 12345 submissions',
                    'Grade formative assessment batch #23',
                    'Review POE submissions for Module 1',
                    'Mark practical assessment recordings',
                    'Mark Business Communication assessments',
                    'Grade Generic Management summative',
                    'Review workplace logbooks for {learner}',
                ],
            },
            # Moderation tasks
            {
                'category': TaskCategory.ASSESSMENT_MODERATE,
                'titles': [
                    'Moderate marked assessments for cohort A',
                    'QA review of assessment results',
                    'Internal moderation batch review',
                    'Pre-moderation sampling check',
                    'QC 10% sample for external moderation',
                    'Prepare PoE files for ETQA visit',
                    'Complete assessor consistency review',
                ],
            },
            # Enrollment tasks
            {
                'category': TaskCategory.ENROLLMENT_PROCESS,
                'titles': [
                    'Process pending enrollment application',
                    'Complete registration for {learner}',
                    'Verify enrollment prerequisites',
                    'Finalize cohort placement',
                    'Link learners to Cohort B2024-03',
                    'Register learners on SETA portal',
                    'Process transfer request for {learner}',
                ],
            },
            # SETA Registration/Submission tasks
            {
                'category': TaskCategory.REGISTRATION_SETA,
                'titles': [
                    'Submit NOT to SERVICES SETA',
                    'Upload Tranche 1 evidence to MERSETA',
                    'Submit learner achievements to ETDPSETA',
                    'Register learners on INSETA system',
                    'Submit ATR report for corporate client',
                    'Respond to QCTO evidence query',
                    'Upload PoE to FASSET portal',
                ],
            },
            # Payment tasks
            {
                'category': TaskCategory.PAYMENT_FOLLOW_UP,
                'titles': [
                    'Follow up on overdue invoice INV-2024-0032',
                    'Process payment allocation',
                    'Reconcile stipend payments',
                    'Generate monthly payment report',
                    'Follow up SETA Tranche 2 payment',
                    'Process employer stipend contribution',
                    'Reconcile learner allowance payments',
                ],
            },
            # Reporting tasks
            {
                'category': TaskCategory.REPORT_DUE,
                'titles': [
                    'Generate weekly progress report',
                    'Compile NOT submission data',
                    'Prepare tranche claim evidence',
                    'Submit monthly compliance report',
                    'Complete WSP/ATR submission',
                    'Generate BBBEE training report',
                    'Compile monthly training statistics',
                ],
            },
            # Communication tasks
            {
                'category': TaskCategory.FOLLOW_UP,
                'titles': [
                    'Send batch notification to learners',
                    'Follow up with absent students',
                    'Contact corporate client re: WSP',
                    'Distribute assessment timetable',
                    'Follow up: Host employer site visit',
                    'Request outstanding documents from {learner}',
                    'Confirm external moderator visit date',
                ],
            },
            # Attendance tasks
            {
                'category': TaskCategory.ATTENDANCE_CAPTURE,
                'titles': [
                    'Capture attendance for {date}',
                    'Enter session register',
                    'Update attendance records',
                    'Verify attendance data',
                    'Upload signed attendance register',
                    'Reconcile weekly attendance',
                ],
            },
            # Action tasks
            {
                'category': TaskCategory.ACTION,
                'titles': [
                    'Update qualification database',
                    'Configure new academic program',
                    'Set up new user account',
                    'Archive completed records',
                    'Create new SETA project',
                    'Register new assessors with HWSETA',
                    'Update QCTO registration details',
                ],
            },
            # Review tasks
            {
                'category': TaskCategory.REVIEW,
                'titles': [
                    'Prepare SETA audit evidence',
                    'Complete self-assessment checklist',
                    'Review policy documentation',
                    'Update compliance register',
                    'Review learner PoE files for completeness',
                    'QA check certification request pack',
                    'Verify document authenticity batch',
                ],
            },
            # At-Risk Intervention tasks
            {
                'category': TaskCategory.LEARNER_AT_RISK,
                'titles': [
                    'Contact at-risk learner {learner}',
                    'Schedule support session for struggling learners',
                    'Follow up on learner non-attendance',
                    'Provide learner feedback on NYC results',
                    'Arrange remedial assessment for {learner}',
                ],
            },
        ]
        
        # Get a list of learners for personalization
        learners = list(Learner.objects.values_list('first_name', 'last_name')[:20])
        if not learners:
            learners = [('John', 'Smith'), ('Jane', 'Doe'), ('Mike', 'Johnson')]
        
        created_tasks = []
        
        for i in range(count):
            # Pick random category
            template = random.choice(task_templates)
            category = template['category']
            title_template = random.choice(template['titles'])
            
            # Personalize title
            if '{learner}' in title_template:
                learner = random.choice(learners)
                title = title_template.format(learner=f'{learner[0]} {learner[1]}')
            elif '{date}' in title_template:
                date = today - timedelta(days=random.randint(0, 5))
                title = title_template.format(date=date.strftime('%d %b'))
            else:
                title = title_template
            
            # Random priority (weighted towards medium/low)
            priority = random.choices(
                [TaskPriority.URGENT, TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW],
                weights=[5, 15, 50, 30]
            )[0]
            
            # Random status (weighted towards pending)
            status = random.choices(
                [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.WAITING, TaskStatus.COMPLETED],
                weights=[50, 25, 10, 15]
            )[0]
            
            # Random due date
            due_offset = random.randint(-7, 14)  # Some overdue, some upcoming
            due_date = today + timedelta(days=due_offset)
            
            # Set completed_at for completed tasks
            completed_at = None
            completed_by = None
            if status == TaskStatus.COMPLETED:
                completed_at = timezone.now() - timedelta(days=random.randint(0, 3))
                completed_by = admin
            
            task = Task.objects.create(
                title=title,
                description=f'Automatically generated test task.\n\nCategory: {category}\nPriority: {priority}',
                category=category,
                priority=priority,
                status=status,
                due_date=due_date,
                due_time=None,
                assigned_to=admin,
                assigned_role='staff',
                assigned_campus=campus,
                created_by=admin,
                completed_at=completed_at,
                completed_by=completed_by,
            )
            created_tasks.append(task)
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n✅ Created {len(created_tasks)} test tasks!'))
        
        # Stats
        pending = sum(1 for t in created_tasks if t.status == TaskStatus.PENDING)
        in_progress = sum(1 for t in created_tasks if t.status == TaskStatus.IN_PROGRESS)
        completed = sum(1 for t in created_tasks if t.status == TaskStatus.COMPLETED)
        overdue = sum(1 for t in created_tasks if t.due_date < today and t.status != TaskStatus.COMPLETED)
        
        self.stdout.write(f'  📋 Pending: {pending}')
        self.stdout.write(f'  🔄 In Progress: {in_progress}')
        self.stdout.write(f'  ✅ Completed: {completed}')
        self.stdout.write(f'  ⚠️  Overdue: {overdue}')
        
        self.stdout.write(self.style.SUCCESS('\nDone! Visit /tasks/ to see the Task Hub.'))
