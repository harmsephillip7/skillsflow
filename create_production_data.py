#!/usr/bin/env python
"""
Script to create comprehensive test data for production environment.
Includes SETAs, Qualifications, and Project Template Sets.
"""
import os
import sys
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from core.models import User
from learners.models import SETA
from academics.models import Qualification
from core.project_templates import (
    ProjectTemplateSet, 
    ProjectTaskTemplate,
    TriggerType,
    DateReferencePoint,
    RecurringInterval,
    OperationalCategory
)

print("=" * 60)
print("SkillsFlow Production Data Creator")
print("=" * 60)

# Get admin user
admin_user = User.objects.filter(is_superuser=True).first()
if not admin_user:
    print("ERROR: No superuser found.")
    sys.exit(1)
print(f"Using admin: {admin_user.email}")

# =====================================================
# SETA DATA
# =====================================================
print("\n📚 Creating SETAs...")

SETA_DATA = [
    {'code': 'MERSETA', 'name': 'Manufacturing, Engineering and Related Services SETA'},
    {'code': 'CETA', 'name': 'Construction Education and Training Authority'},
    {'code': 'HWSETA', 'name': 'Health and Welfare SETA'},
    {'code': 'FASSET', 'name': 'Financial and Accounting Services SETA'},
    {'code': 'SERVICES', 'name': 'Services SETA'},
    {'code': 'W&RSETA', 'name': 'Wholesale and Retail SETA'},
    {'code': 'AGRISETA', 'name': 'Agricultural SETA'},
    {'code': 'CATHSSETA', 'name': 'Culture, Arts, Tourism, Hospitality and Sport SETA'},
    {'code': 'ETDP', 'name': 'Education, Training and Development Practices SETA'},
    {'code': 'MICT', 'name': 'Media, Information and Communication Technologies SETA'},
    {'code': 'TETA', 'name': 'Transport Education Training Authority'},
    {'code': 'CHIETA', 'name': 'Chemical Industries Education and Training Authority'},
    {'code': 'MQA', 'name': 'Mining Qualifications Authority'},
]

seta_count = 0
for data in SETA_DATA:
    seta, created = SETA.objects.get_or_create(code=data['code'], defaults={'name': data['name'], 'is_active': True})
    if created:
        seta_count += 1
        print(f"  ✓ Created: {seta.code}")
    else:
        print(f"  - Exists: {seta.code}")

# =====================================================
# QUALIFICATIONS
# =====================================================
print("\n🎓 Creating Qualifications...")

merseta = SETA.objects.filter(code='MERSETA').first()
services = SETA.objects.filter(code='SERVICES').first()
hwseta = SETA.objects.filter(code='HWSETA').first()
ceta = SETA.objects.filter(code='CETA').first()
mict = SETA.objects.filter(code='MICT').first()
fasset = SETA.objects.filter(code='FASSET').first()

today = date.today()
reg_start = today - timedelta(days=365*3)
reg_end = today + timedelta(days=365*5)
last_enroll = today + timedelta(days=365*4)

QUALS = [
    {'saqa_id': '94022', 'title': 'Occupational Certificate: Motor Mechanic', 'short_title': 'Motor Mechanic', 'nqf_level': 4, 'credits': 320, 'qualification_type': 'OC', 'seta': merseta, 'min_months': 36, 'max_months': 48},
    {'saqa_id': '94024', 'title': 'Occupational Certificate: Diesel Mechanic', 'short_title': 'Diesel Mechanic', 'nqf_level': 4, 'credits': 320, 'qualification_type': 'OC', 'seta': merseta, 'min_months': 36, 'max_months': 48},
    {'saqa_id': '94592', 'title': 'Occupational Certificate: Electrician', 'short_title': 'Electrician', 'nqf_level': 4, 'credits': 360, 'qualification_type': 'OC', 'seta': merseta, 'min_months': 36, 'max_months': 48},
    {'saqa_id': '94710', 'title': 'Occupational Certificate: Welder', 'short_title': 'Welder', 'nqf_level': 3, 'credits': 240, 'qualification_type': 'OC', 'seta': merseta, 'min_months': 24, 'max_months': 36},
    {'saqa_id': '96857', 'title': 'Occupational Certificate: Boilermaker', 'short_title': 'Boilermaker', 'nqf_level': 4, 'credits': 360, 'qualification_type': 'OC', 'seta': merseta, 'min_months': 36, 'max_months': 48},
    {'saqa_id': '93998', 'title': 'Occupational Certificate: Plumber', 'short_title': 'Plumber', 'nqf_level': 4, 'credits': 360, 'qualification_type': 'OC', 'seta': ceta, 'min_months': 36, 'max_months': 48},
    {'saqa_id': '94029', 'title': 'Occupational Certificate: Bricklayer', 'short_title': 'Bricklayer', 'nqf_level': 3, 'credits': 241, 'qualification_type': 'OC', 'seta': ceta, 'min_months': 18, 'max_months': 24},
    {'saqa_id': '94723', 'title': 'Occupational Certificate: Carpenter', 'short_title': 'Carpenter', 'nqf_level': 4, 'credits': 360, 'qualification_type': 'OC', 'seta': ceta, 'min_months': 36, 'max_months': 48},
    {'saqa_id': '93985', 'title': 'Occupational Certificate: Enrolled Nurse', 'short_title': 'Enrolled Nurse', 'nqf_level': 5, 'credits': 240, 'qualification_type': 'OC', 'seta': hwseta, 'min_months': 24, 'max_months': 36},
    {'saqa_id': '97538', 'title': 'Occupational Certificate: Community Health Worker', 'short_title': 'Community Health Worker', 'nqf_level': 4, 'credits': 120, 'qualification_type': 'OC', 'seta': hwseta, 'min_months': 12, 'max_months': 18},
    {'saqa_id': '94940', 'title': 'Occupational Certificate: Software Developer', 'short_title': 'Software Developer', 'nqf_level': 5, 'credits': 360, 'qualification_type': 'OC', 'seta': mict, 'min_months': 24, 'max_months': 36},
    {'saqa_id': '96265', 'title': 'Occupational Certificate: Network Technician', 'short_title': 'Network Technician', 'nqf_level': 4, 'credits': 287, 'qualification_type': 'OC', 'seta': mict, 'min_months': 18, 'max_months': 24},
    {'saqa_id': '93994', 'title': 'Occupational Certificate: Accounting Technician', 'short_title': 'Accounting Technician', 'nqf_level': 5, 'credits': 243, 'qualification_type': 'OC', 'seta': fasset, 'min_months': 18, 'max_months': 24},
    {'saqa_id': '50080', 'title': 'FET Certificate: Generic Management', 'short_title': 'Generic Management L4', 'nqf_level': 4, 'credits': 150, 'qualification_type': 'LP', 'seta': services, 'min_months': 12, 'max_months': 18},
    {'saqa_id': '59201', 'title': 'National Certificate: Business Administration', 'short_title': 'Business Admin NQF4', 'nqf_level': 4, 'credits': 140, 'qualification_type': 'LP', 'seta': services, 'min_months': 12, 'max_months': 18},
    {'saqa_id': '67465', 'title': 'National Certificate: Contact Centre Support', 'short_title': 'Contact Centre NQF2', 'nqf_level': 2, 'credits': 120, 'qualification_type': 'LP', 'seta': services, 'min_months': 12, 'max_months': 12},
    {'saqa_id': '93997', 'title': 'Occupational Certificate: Chef', 'short_title': 'Chef', 'nqf_level': 4, 'credits': 399, 'qualification_type': 'OC', 'seta': services, 'min_months': 24, 'max_months': 36},
]

qual_count = 0
for q in QUALS:
    if not q.get('seta'):
        print(f"  ⚠ Skipping {q['short_title']}: No SETA")
        continue
    qual, created = Qualification.objects.get_or_create(
        saqa_id=q['saqa_id'],
        defaults={
            'title': q['title'], 'short_title': q['short_title'], 'nqf_level': q['nqf_level'],
            'credits': q['credits'], 'qualification_type': q['qualification_type'], 'seta': q['seta'],
            'minimum_duration_months': q['min_months'], 'maximum_duration_months': q['max_months'],
            'registration_start': reg_start, 'registration_end': reg_end, 'last_enrollment_date': last_enroll,
            'is_active': True, 'ready_in_person': True, 'created_by': admin_user, 'updated_by': admin_user,
        }
    )
    if created:
        qual_count += 1
        print(f"  ✓ Created: {qual.short_title} (NQF {qual.nqf_level})")
    else:
        print(f"  - Exists: {qual.short_title}")

# =====================================================
# TEMPLATE SETS
# =====================================================
print("\n📋 Creating Template Sets...")

with transaction.atomic():
    # Base set
    base_set, created = ProjectTemplateSet.objects.get_or_create(
        name='Base Project Tasks',
        defaults={'description': 'Core tasks for all projects', 'auto_apply': False, 'is_active': True, 'created_by': admin_user}
    )
    if created:
        print(f"  ✓ Created: {base_set.name}")
        ProjectTaskTemplate.objects.create(template_set=base_set, name='welcome_email', task_title_template='Send welcome email - {reference_number}', task_description_template='Send welcome communication to learners', trigger_type=TriggerType.STATUS_CHANGE, trigger_status='APPROVED', due_days_offset=1, assigned_role='COORDINATOR', task_category='COMMUNICATION', operational_category=OperationalCategory.ADMIN, sequence=10)
        ProjectTaskTemplate.objects.create(template_set=base_set, name='create_class_list', task_title_template='Create class list - {reference_number}', task_description_template='Set up class list and learner groups', trigger_type=TriggerType.STATUS_CHANGE, trigger_status='APPROVED', due_days_offset=3, assigned_role='COORDINATOR', task_category='ADMIN', operational_category=OperationalCategory.ADMIN, sequence=20)
        ProjectTaskTemplate.objects.create(template_set=base_set, name='weekly_report', task_title_template='Weekly progress report - {reference_number}', task_description_template='Complete weekly progress report', trigger_type=TriggerType.RECURRING, recurring_interval=RecurringInterval.WEEKLY, recurring_start_status='IN_PROGRESS', recurring_end_status='COMPLETED', assigned_role='COORDINATOR', task_category='REPORTING', operational_category=OperationalCategory.REPORTING, sequence=100)
    else:
        print(f"  - Exists: {base_set.name}")

    # Learnership set
    lp_set, created = ProjectTemplateSet.objects.get_or_create(
        name='Learnership Projects',
        defaults={'description': 'Learnership-specific tasks', 'parent_set': base_set, 'project_types': ['LEARNERSHIP'], 'qualification_types': ['LP'], 'auto_apply': True, 'is_active': True, 'created_by': admin_user}
    )
    if created:
        print(f"  ✓ Created: {lp_set.name}")
        ProjectTaskTemplate.objects.create(template_set=lp_set, name='seta_registration', task_title_template='Register with SETA - {reference_number}', task_description_template='Complete SETA learnership registration', trigger_type=TriggerType.STATUS_CHANGE, trigger_status='APPROVED', due_days_offset=5, assigned_role='QUALITY_MANAGER', task_category='COMPLIANCE', task_priority='HIGH', operational_category=OperationalCategory.COMPLIANCE, sequence=30)
        ProjectTaskTemplate.objects.create(template_set=lp_set, name='learnership_agreements', task_title_template='Sign learnership agreements - {reference_number}', task_description_template='Collect signed learnership agreements from learners', trigger_type=TriggerType.STATUS_CHANGE, trigger_status='APPROVED', due_days_offset=7, assigned_role='COORDINATOR', task_category='DOCUMENTATION', task_priority='HIGH', operational_category=OperationalCategory.COMPLIANCE, sequence=40)
        ProjectTaskTemplate.objects.create(template_set=lp_set, name='workplace_verification', task_title_template='Verify workplace placements - {reference_number}', task_description_template='Conduct workplace verification visits', trigger_type=TriggerType.DATE_RELATIVE, date_reference=DateReferencePoint.ACTUAL_START, offset_days=30, assigned_role='WORKPLACE_OFFICER', task_category='SITE_VISIT', operational_category=OperationalCategory.QUALITY, sequence=50)
        ProjectTaskTemplate.objects.create(template_set=lp_set, name='monthly_monitoring', task_title_template='Monthly workplace monitoring - {reference_number}', task_description_template='Conduct monthly workplace monitoring', trigger_type=TriggerType.RECURRING, recurring_interval=RecurringInterval.MONTHLY, recurring_start_status='IN_PROGRESS', recurring_end_status='COMPLETED', assigned_role='WORKPLACE_OFFICER', task_category='MONITORING', operational_category=OperationalCategory.QUALITY, sequence=110)
    else:
        print(f"  - Exists: {lp_set.name}")

    # OC set
    oc_set, created = ProjectTemplateSet.objects.get_or_create(
        name='Occupational Certificate Projects',
        defaults={'description': 'Trade/OC specific tasks', 'parent_set': base_set, 'qualification_types': ['OC'], 'auto_apply': True, 'is_active': True, 'created_by': admin_user}
    )
    if created:
        print(f"  ✓ Created: {oc_set.name}")
        ProjectTaskTemplate.objects.create(template_set=oc_set, name='qcto_registration', task_title_template='Register with QCTO - {reference_number}', task_description_template='Complete QCTO learner registration', trigger_type=TriggerType.STATUS_CHANGE, trigger_status='APPROVED', due_days_offset=10, assigned_role='QUALITY_MANAGER', task_category='COMPLIANCE', task_priority='HIGH', operational_category=OperationalCategory.COMPLIANCE, sequence=30)
        ProjectTaskTemplate.objects.create(template_set=oc_set, name='ppe_procurement', task_title_template='Procure PPE - {reference_number}', task_description_template='Order and distribute PPE for apprentices', trigger_type=TriggerType.STATUS_CHANGE, trigger_status='APPROVED', due_days_offset=5, assigned_role='COORDINATOR', task_category='PROCUREMENT', operational_category=OperationalCategory.LOGISTICS, sequence=35)
        ProjectTaskTemplate.objects.create(template_set=oc_set, name='workshop_readiness', task_title_template='Confirm workshop readiness - {reference_number}', task_description_template='Verify workshop equipment and materials', trigger_type=TriggerType.DATE_RELATIVE, date_reference=DateReferencePoint.PLANNED_START, offset_days=-7, assigned_role='FACILITATOR', task_category='PREPARATION', operational_category=OperationalCategory.LOGISTICS, sequence=25)
        ProjectTaskTemplate.objects.create(template_set=oc_set, name='eisa_prep', task_title_template='Prepare for EISA - {reference_number}', task_description_template='Submit EISA application and prepare candidates', trigger_type=TriggerType.DATE_RELATIVE, date_reference=DateReferencePoint.PLANNED_END, offset_days=-60, assigned_role='ASSESSOR', task_category='ASSESSMENT', task_priority='HIGH', operational_category=OperationalCategory.QUALITY, sequence=200)
        ProjectTaskTemplate.objects.create(template_set=oc_set, name='trade_test_booking', task_title_template='Book trade tests - {reference_number}', task_description_template='Book trade test dates for candidates', trigger_type=TriggerType.DATE_RELATIVE, date_reference=DateReferencePoint.PLANNED_END, offset_days=-30, assigned_role='COORDINATOR', task_category='ADMIN', task_priority='HIGH', operational_category=OperationalCategory.ADMIN, sequence=210)
    else:
        print(f"  - Exists: {oc_set.name}")

    # Skills Programme set
    sp_set, created = ProjectTemplateSet.objects.get_or_create(
        name='Skills Programme Projects',
        defaults={'description': 'Tasks for short skills programmes', 'parent_set': base_set, 'qualification_types': ['SP'], 'max_duration_months': 6, 'auto_apply': True, 'is_active': True, 'created_by': admin_user}
    )
    if created:
        print(f"  ✓ Created: {sp_set.name}")
        ProjectTaskTemplate.objects.create(template_set=sp_set, name='materials_prep', task_title_template='Prepare learner materials - {reference_number}', task_description_template='Print/prepare materials for learners', trigger_type=TriggerType.DATE_RELATIVE, date_reference=DateReferencePoint.PLANNED_START, offset_days=-5, assigned_role='COORDINATOR', task_category='PREPARATION', operational_category=OperationalCategory.LOGISTICS, sequence=20)
        ProjectTaskTemplate.objects.create(template_set=sp_set, name='certificates', task_title_template='Issue certificates - {reference_number}', task_description_template='Generate and issue certificates for competent learners', trigger_type=TriggerType.DATE_RELATIVE, date_reference=DateReferencePoint.PLANNED_END, offset_days=7, assigned_role='QUALITY_MANAGER', task_category='CERTIFICATION', operational_category=OperationalCategory.ADMIN, sequence=300)
    else:
        print(f"  - Exists: {sp_set.name}")

    # SETA Funded set
    seta_set, created = ProjectTemplateSet.objects.get_or_create(
        name='SETA Funded Projects',
        defaults={'description': 'Tasks for SETA discretionary grants', 'parent_set': base_set, 'funder_types': ['SETA_DG', 'SETA_MG'], 'auto_apply': True, 'is_active': True, 'created_by': admin_user}
    )
    if created:
        print(f"  ✓ Created: {seta_set.name}")
        ProjectTaskTemplate.objects.create(template_set=seta_set, name='sla_compliance', task_title_template='SLA compliance check - {reference_number}', task_description_template='Review SETA SLA requirements and compliance status', trigger_type=TriggerType.STATUS_CHANGE, trigger_status='IN_PROGRESS', due_days_offset=7, assigned_role='PROJECT_MANAGER', task_category='COMPLIANCE', task_priority='HIGH', operational_category=OperationalCategory.COMPLIANCE, sequence=50)
        ProjectTaskTemplate.objects.create(template_set=seta_set, name='quarterly_report', task_title_template='Quarterly SETA report - {reference_number}', task_description_template='Prepare and submit quarterly progress report to SETA', trigger_type=TriggerType.RECURRING, recurring_interval=RecurringInterval.QUARTERLY, recurring_start_status='IN_PROGRESS', recurring_end_status='COMPLETED', assigned_role='PROJECT_MANAGER', task_category='REPORTING', task_priority='HIGH', operational_category=OperationalCategory.REPORTING, sequence=120)
        ProjectTaskTemplate.objects.create(template_set=seta_set, name='tranche_claim', task_title_template='Prepare tranche claim - {reference_number}', task_description_template='Compile documentation for next tranche claim submission', trigger_type=TriggerType.RECURRING, recurring_interval=RecurringInterval.QUARTERLY, recurring_start_status='IN_PROGRESS', recurring_end_status='COMPLETED', assigned_role='FINANCE_ADMIN', task_category='FINANCE', task_priority='HIGH', operational_category=OperationalCategory.FINANCE, sequence=130)
        ProjectTaskTemplate.objects.create(template_set=seta_set, name='closeout_report', task_title_template='SETA closeout report - {reference_number}', task_description_template='Prepare final project closeout report for SETA', trigger_type=TriggerType.DATE_RELATIVE, date_reference=DateReferencePoint.PLANNED_END, offset_days=14, assigned_role='PROJECT_MANAGER', task_category='REPORTING', task_priority='HIGH', operational_category=OperationalCategory.REPORTING, sequence=400)
    else:
        print(f"  - Exists: {seta_set.name}")

print("\n" + "=" * 60)
print("✅ Complete!")
print(f"SETAs: {SETA.objects.count()} | Qualifications: {Qualification.objects.count()} | Template Sets: {ProjectTemplateSet.objects.count()} | Task Templates: {ProjectTaskTemplate.objects.count()}")
print("=" * 60)
