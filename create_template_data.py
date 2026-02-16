"""
Create sample data for Project Template Sets and Standard Blocks
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.project_templates import (
    ProjectTemplateSet, ProjectTaskTemplate, TriggerType, 
    DateReferencePoint, OperationalCategory
)
from core.tasks import TaskCategory, TaskPriority
from academics.models import StandardBlock, StandardBlockModule

print("=" * 60)
print("Creating Project Template Sets")
print("=" * 60)

# Create a base template set
base_set, created = ProjectTemplateSet.objects.get_or_create(
    name='Base Training Project Tasks',
    defaults={
        'description': 'Core tasks for all training projects',
        'auto_apply': True,
        'is_active': True
    }
)
print(f"{'Created' if created else 'Found'}: {base_set}")

# Create SETA-specific template set that inherits from base
seta_set, created = ProjectTemplateSet.objects.get_or_create(
    name='SETA-Funded Project Tasks',
    defaults={
        'description': 'Additional tasks for SETA-funded projects',
        'parent_set': base_set,
        'funder_types': ['SETA', 'CORPORATE_DG'],
        'auto_apply': True,
        'is_active': True
    }
)
print(f"{'Created' if created else 'Found'}: {seta_set}")

# Create OC-specific template set
oc_set, created = ProjectTemplateSet.objects.get_or_create(
    name='Occupational Certificate Tasks',
    defaults={
        'description': 'Tasks specific to OC qualifications',
        'parent_set': base_set,
        'qualification_types': ['OC'],
        'auto_apply': True,
        'is_active': True
    }
)
print(f"{'Created' if created else 'Found'}: {oc_set}")

# Create sample task templates
print("\n" + "=" * 60)
print("Creating Task Templates")
print("=" * 60)

# Status-triggered: Setup project folder (base set)
task1, created = ProjectTaskTemplate.objects.get_or_create(
    template_set=base_set,
    name='setup_project_folder',
    defaults={
        'trigger_type': TriggerType.STATUS_CHANGE,
        'trigger_status': 'APPROVED',
        'task_title_template': 'Setup project folder for {reference_number}',
        'task_description_template': 'Create project folder structure and setup documentation for {title}',
        'task_category': TaskCategory.ACTION,
        'task_priority': TaskPriority.HIGH,
        'operational_category': OperationalCategory.ADMIN,
        'assigned_role': 'PROJECT_MANAGER',
        'due_days_offset': 3,
        'sequence': 1
    }
)
print(f"{'Created' if created else 'Found'}: {task1}")

# Status-triggered: Finance setup (base set)
task2, created = ProjectTaskTemplate.objects.get_or_create(
    template_set=base_set,
    name='finance_setup',
    defaults={
        'trigger_type': TriggerType.STATUS_CHANGE,
        'trigger_status': 'APPROVED',
        'task_title_template': 'Setup billing for {reference_number}',
        'task_description_template': 'Configure invoicing schedule and payment tracking for {title}',
        'task_category': TaskCategory.ACTION,
        'task_priority': TaskPriority.MEDIUM,
        'operational_category': OperationalCategory.FINANCE,
        'assigned_role': 'FINANCE_LEAD',
        'due_days_offset': 5,
        'sequence': 2
    }
)
print(f"{'Created' if created else 'Found'}: {task2}")

# Date-relative: Marketing recruitment launch (base set)
task3, created = ProjectTaskTemplate.objects.get_or_create(
    template_set=base_set,
    name='marketing_recruitment_launch',
    defaults={
        'trigger_type': TriggerType.DATE_RELATIVE,
        'date_reference': DateReferencePoint.PLANNED_START,
        'offset_days': -30,  # 30 days before start
        'task_title_template': 'Launch recruitment campaign for {reference_number}',
        'task_description_template': 'Start marketing and recruitment activities for {title}. Target {learner_count} learners.',
        'task_category': TaskCategory.ACTION,
        'task_priority': TaskPriority.HIGH,
        'operational_category': OperationalCategory.RECRUITMENT,
        'assigned_role': 'RECRUITER',
        'recalculate_on_date_change': True,
        'sequence': 1
    }
)
print(f"{'Created' if created else 'Found'}: {task3}")

# Date-relative: Venue preparation (base set)
task4, created = ProjectTaskTemplate.objects.get_or_create(
    template_set=base_set,
    name='venue_preparation',
    defaults={
        'trigger_type': TriggerType.DATE_RELATIVE,
        'date_reference': DateReferencePoint.PLANNED_START,
        'offset_days': -7,  # 7 days before start
        'task_title_template': 'Prepare training venue for {reference_number}',
        'task_description_template': 'Ensure venue is ready with equipment, materials, and signage for {title}',
        'task_category': TaskCategory.ACTION,
        'task_priority': TaskPriority.HIGH,
        'operational_category': OperationalCategory.LOGISTICS,
        'assigned_role': 'LOGISTICS_LEAD',
        'recalculate_on_date_change': True,
        'sequence': 2
    }
)
print(f"{'Created' if created else 'Found'}: {task4}")

# Date-relative: Project completion report (base set)
task5, created = ProjectTaskTemplate.objects.get_or_create(
    template_set=base_set,
    name='completion_report',
    defaults={
        'trigger_type': TriggerType.DATE_RELATIVE,
        'date_reference': DateReferencePoint.PLANNED_END,
        'offset_days': 14,  # 14 days after end
        'task_title_template': 'Submit completion report for {reference_number}',
        'task_description_template': 'Complete and submit final project report with outcomes and lessons learned for {title}',
        'task_category': TaskCategory.REPORT_DUE,
        'task_priority': TaskPriority.MEDIUM,
        'operational_category': OperationalCategory.REPORTING,
        'assigned_role': 'PROJECT_MANAGER',
        'recalculate_on_date_change': True,
        'sequence': 3
    }
)
print(f"{'Created' if created else 'Found'}: {task5}")

# SETA-specific: MOA submission
task6, created = ProjectTaskTemplate.objects.get_or_create(
    template_set=seta_set,
    name='seta_moa_submission',
    defaults={
        'trigger_type': TriggerType.STATUS_CHANGE,
        'trigger_status': 'APPROVED',
        'task_title_template': 'Submit MOA to SETA for {reference_number}',
        'task_description_template': 'Prepare and submit Memorandum of Agreement to SETA for {qualification} project',
        'task_category': TaskCategory.APPROVAL,
        'task_priority': TaskPriority.HIGH,
        'operational_category': OperationalCategory.COMPLIANCE,
        'assigned_role': 'COMPLIANCE_LEAD',
        'due_days_offset': 7,
        'sequence': 1
    }
)
print(f"{'Created' if created else 'Found'}: {task6}")

# SETA-specific: Learner registration
task7, created = ProjectTaskTemplate.objects.get_or_create(
    template_set=seta_set,
    name='seta_learner_registration',
    defaults={
        'trigger_type': TriggerType.STATUS_CHANGE,
        'trigger_status': 'IN_PROGRESS',
        'task_title_template': 'Register learners with SETA for {reference_number}',
        'task_description_template': 'Complete SETA learner registration for {learner_count} learners on {qualification}',
        'task_category': TaskCategory.REGISTRATION_SETA,
        'task_priority': TaskPriority.HIGH,
        'operational_category': OperationalCategory.COMPLIANCE,
        'assigned_role': 'COMPLIANCE_LEAD',
        'due_days_offset': 14,
        'sequence': 2
    }
)
print(f"{'Created' if created else 'Found'}: {task7}")

# OC-specific: EISA preparation
task8, created = ProjectTaskTemplate.objects.get_or_create(
    template_set=oc_set,
    name='eisa_preparation',
    defaults={
        'trigger_type': TriggerType.DATE_RELATIVE,
        'date_reference': DateReferencePoint.PLANNED_END,
        'offset_days': -60,  # 60 days before end
        'task_title_template': 'Schedule EISA for {reference_number}',
        'task_description_template': 'Coordinate with AQP to schedule External Integrated Summative Assessment for {qualification}',
        'task_category': TaskCategory.ASSESSMENT_DUE,
        'task_priority': TaskPriority.HIGH,
        'operational_category': OperationalCategory.QUALITY,
        'assigned_role': 'QUALITY_LEAD',
        'recalculate_on_date_change': True,
        'sequence': 1
    }
)
print(f"{'Created' if created else 'Found'}: {task8}")

print("\n" + "=" * 60)
print("Creating Standard Blocks")
print("=" * 60)

# Create standard institutional block
inst_block, created = StandardBlock.objects.get_or_create(
    code='INST-FND-8W',
    defaults={
        'name': 'Standard 8-Week Foundational Knowledge Block',
        'description': 'Standard foundational knowledge institutional block for OC qualifications',
        'block_type': 'INSTITUTIONAL',
        'duration_weeks': 8,
        'contact_days_per_week': 5,
        'hours_per_day': 6,
        'classroom_hours_per_day': 2,
        'practical_hours_per_day': 4,
        'status': 'ACTIVE',
        'applicable_qualification_types': ['OC', 'NC'],
        'color': 'blue'
    }
)
print(f"{'Created' if created else 'Found'}: {inst_block}")

# Create standard workplace block
work_block, created = StandardBlock.objects.get_or_create(
    code='WORK-STD-12W',
    defaults={
        'name': 'Standard 12-Week Workplace Stint',
        'description': 'Standard workplace stint for OC qualifications',
        'block_type': 'WORKPLACE',
        'duration_weeks': 12,
        'workplace_days_per_week': 5,
        'workplace_hours_per_day': 8,
        'status': 'ACTIVE',
        'applicable_qualification_types': ['OC'],
        'color': 'green'
    }
)
print(f"{'Created' if created else 'Found'}: {work_block}")

# Create short skills programme block
skills_block, created = StandardBlock.objects.get_or_create(
    code='INST-SKILLS-4W',
    defaults={
        'name': 'Standard 4-Week Skills Programme Block',
        'description': 'Standard block for short skills programmes',
        'block_type': 'INSTITUTIONAL',
        'duration_weeks': 4,
        'contact_days_per_week': 5,
        'hours_per_day': 6,
        'classroom_hours_per_day': 2,
        'practical_hours_per_day': 4,
        'status': 'ACTIVE',
        'applicable_qualification_types': ['SP', 'LP'],
        'color': 'purple'
    }
)
print(f"{'Created' if created else 'Found'}: {skills_block}")

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print(f"Total Template Sets: {ProjectTemplateSet.objects.count()}")
print(f"Total Task Templates: {ProjectTaskTemplate.objects.count()}")
print(f"Total Standard Blocks: {StandardBlock.objects.count()}")

# Show inheritance for SETA set
print(f"\n{seta_set.name} effective templates (including inherited):")
for name, t in seta_set.get_all_templates().items():
    print(f"  - {name}: {t.get_trigger_type_display()}")

print("\nDone!")
