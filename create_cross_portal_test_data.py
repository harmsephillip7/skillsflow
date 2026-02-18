"""
Create Cross-Portal Test Data

Creates a learner with partial progress that is visible across ALL portals:
- Learner Portal: Sees their own progress, modules, assessments
- Facilitator Portal: Sees learner in their assigned cohort
- WIL Officer Portal: Sees learner in workplace placement
- Mentor Portal: Sees learner assigned to them

The learner is:
- In the middle of a qualification (Year 2 of 3)
- Has completed Year 1 modules
- Currently working on Year 2 modules
- Linked to a project with implementation plan
- Has workplace placement with assigned mentor
- Has a facilitator for their cohort
- Has a WIL officer for their placement

Run: ./venv/bin/python create_cross_portal_test_data.py
"""
import os
import sys
import django
import random

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.hashers import make_password

from core.models import (
    User, FacilitatorProfile, WorkplaceOfficerProfile,
    TrainingNotification, NOTIntake, NOTStakeholder
)
from learners.models import Learner, SETA
from corporate.models import (
    HostEmployer, HostMentor, WorkplacePlacement, CorporateClient
)
from academics.models import (
    Qualification, Enrollment, Module, LearnerModuleProgress,
    ImplementationPlan, ImplementationPhase
)
from logistics.models import Cohort, CohortImplementationPlan, CohortImplementationPhase, Venue, ScheduleSession
from tenants.models import Brand, Campus

print("=" * 70)
print("Creating Cross-Portal Test Data")
print("=" * 70)

TODAY = date.today()


@transaction.atomic
def main():
    """Main function to create all test data."""
    
    # =====================================================
    # 1. BASIC INFRASTRUCTURE
    # =====================================================
    
    # Get or create brand and campus
    brand, _ = Brand.objects.get_or_create(
        name='SkillsFlow Training Academy',
        defaults={
            'legal_name': 'SkillsFlow Training Academy (Pty) Ltd',
            'is_active': True,
        }
    )
    print(f"✓ Brand: {brand.name}")
    
    campus, _ = Campus.objects.get_or_create(
        name='Johannesburg Central Campus',
        defaults={
            'brand': brand,
            'code': 'JHB-CTR',
            'phone': '011 555 1234',
            'email': 'jhb@skillsflow.co.za',
            'address_line1': '123 Skills Road',
            'suburb': 'Braamfontein',
            'city': 'Johannesburg',
            'province': 'Gauteng',
            'postal_code': '2000',
        }
    )
    print(f"✓ Campus: {campus.name}")
    
    # Get or create SETA
    seta, _ = SETA.objects.get_or_create(
        code='MERSETA',
        defaults={
            'name': 'Manufacturing, Engineering and Related Services SETA',
            'is_active': True,
        }
    )
    print(f"✓ SETA: {seta.code}")
    
    # Get superuser
    superuser = User.objects.filter(is_superuser=True).first()
    if not superuser:
        superuser = User.objects.create_superuser(
            email='admin@skillsflow.co.za',
            password='admin1234',
            first_name='Admin',
            last_name='User'
        )
        print(f"✓ Created superuser: admin@skillsflow.co.za")
    else:
        print(f"✓ Superuser: {superuser.email}")
    
    # =====================================================
    # 2. QUALIFICATION WITH MODULES
    # =====================================================
    
    qual, qual_created = Qualification.objects.get_or_create(
        saqa_id='98765',
        defaults={
            'title': 'Occupational Certificate: Fitter and Turner',
            'short_title': 'OC: Fitter & Turner',
            'nqf_level': 4,
            'credits': 360,
            'qualification_type': 'OC',
            'seta': seta,
            'is_active': True,
            'minimum_duration_months': 36,
            'maximum_duration_months': 48,
            'registration_start': TODAY - timedelta(days=365),
            'registration_end': TODAY + timedelta(days=365 * 3),
            'last_enrollment_date': TODAY + timedelta(days=365 * 2),
            'qcto_code': 'OC-FITTER-98765',
        }
    )
    if qual_created:
        print(f"✓ Created qualification: {qual.title}")
    else:
        print(f"✓ Using qualification: {qual.title}")
    
    # Create modules for 3 years
    modules_data = [
        # Year 1 - Knowledge Modules
        ('KM-101', 'Engineering Fundamentals', 'K', 1, 15, 150, 'Basic engineering principles and mathematics'),
        ('KM-102', 'Technical Drawing', 'K', 1, 15, 150, 'Reading and interpreting engineering drawings'),
        ('KM-103', 'Materials Science', 'K', 1, 10, 100, 'Properties of metals and materials'),
        # Year 1 - Practical Modules
        ('PM-101', 'Basic Machining Operations', 'P', 1, 20, 200, 'Lathe and milling basics'),
        ('PM-102', 'Hand Tools and Measuring', 'P', 1, 20, 200, 'Using precision measuring instruments'),
        # Year 1 - Workplace Modules
        ('WM-101', 'Workshop Safety', 'W', 1, 10, 100, 'Workplace safety orientation'),
        ('WM-102', 'Basic Machine Operation', 'W', 1, 25, 250, 'Supervised machine operation'),
        
        # Year 2 - Knowledge Modules
        ('KM-201', 'Advanced Machining Theory', 'K', 2, 20, 200, 'Complex machining calculations'),
        ('KM-202', 'Hydraulics & Pneumatics', 'K', 2, 15, 150, 'Fluid power systems'),
        # Year 2 - Practical Modules
        ('PM-201', 'Complex Turning Operations', 'P', 2, 25, 250, 'Advanced lathe work'),
        ('PM-202', 'Milling Operations', 'P', 2, 25, 250, 'Milling machine operations'),
        # Year 2 - Workplace Modules
        ('WM-201', 'Independent Machining', 'W', 2, 35, 350, 'Working with minimal supervision'),
        
        # Year 3 - Knowledge Modules
        ('KM-301', 'CNC Programming', 'K', 3, 20, 200, 'Programming CNC machines'),
        ('KM-302', 'Quality Control', 'K', 3, 10, 100, 'Quality assurance procedures'),
        # Year 3 - Practical Modules
        ('PM-301', 'CNC Operations', 'P', 3, 30, 300, 'Operating CNC machines'),
        ('PM-302', 'Tool Making', 'P', 3, 25, 250, 'Manufacturing precision tools'),
        # Year 3 - Workplace Modules
        ('WM-301', 'Advanced Production', 'W', 3, 40, 400, 'Full production responsibilities'),
    ]
    
    modules_created = 0
    for code, title, mtype, year, credits, hours, desc in modules_data:
        mod, created = Module.objects.get_or_create(
            qualification=qual,
            code=code,
            defaults={
                'title': title,
                'module_type': mtype,
                'year_level': year,
                'credits': credits,
                'notional_hours': hours,
                'description': desc,
                'is_active': True,
            }
        )
        if created:
            modules_created += 1
    print(f"✓ Modules: {modules_created} created, {len(modules_data)} total")
    
    # =====================================================
    # 3. IMPLEMENTATION PLAN TEMPLATE
    # =====================================================
    
    impl_plan, plan_created = ImplementationPlan.objects.get_or_create(
        qualification=qual,
        name='3-Year Full-Time Apprenticeship',
        defaults={
            'description': 'Standard 3-year apprenticeship with institutional and workplace phases',
            'delivery_mode': 'FULL_TIME',
            'total_weeks': 156,  # 3 years
            'contact_days_per_week': 5,
            'hours_per_day': 8,
            'classroom_hours_per_day': 4,
            'practical_hours_per_day': 4,
            'is_default': True,
            'status': 'ACTIVE',
            'version': '1.0',
            'effective_from': TODAY - timedelta(days=365),
            'created_by': superuser,
        }
    )
    if plan_created:
        print(f"✓ Created implementation plan: {impl_plan.name}")
        
        # Create phases for the implementation plan
        phases_data = [
            # Year 1
            (1, 'Year 1 Institutional Phase 1', 'INSTITUTIONAL', 10, 1),
            (2, 'Year 1 Workplace Stint 1', 'WORKPLACE_STINT', 12, 1),
            (3, 'Year 1 Institutional Phase 2', 'INSTITUTIONAL', 10, 1),
            (4, 'Year 1 Workplace Stint 2', 'WORKPLACE_STINT', 20, 1),
            # Year 2
            (5, 'Year 2 Institutional Phase 1', 'INSTITUTIONAL', 8, 2),
            (6, 'Year 2 Workplace Stint 1', 'WORKPLACE_STINT', 14, 2),
            (7, 'Year 2 Institutional Phase 2', 'INSTITUTIONAL', 8, 2),
            (8, 'Year 2 Workplace Stint 2', 'WORKPLACE_STINT', 22, 2),
            # Year 3
            (9, 'Year 3 Institutional Phase 1', 'INSTITUTIONAL', 6, 3),
            (10, 'Year 3 Workplace Stint 1', 'WORKPLACE_STINT', 16, 3),
            (11, 'Year 3 Institutional Phase 2', 'INSTITUTIONAL', 6, 3),
            (12, 'Year 3 Workplace Stint 2', 'WORKPLACE_STINT', 24, 3),
        ]
        
        for seq, name, ptype, weeks, year in phases_data:
            ImplementationPhase.objects.create(
                implementation_plan=impl_plan,
                sequence=seq,
                name=name,
                phase_type=ptype,
                year_level=year,
                duration_weeks=weeks,
                created_by=superuser,
            )
        print(f"  ✓ Created {len(phases_data)} implementation phases")
    else:
        print(f"✓ Using implementation plan: {impl_plan.name}")
    
    # =====================================================
    # 4. CORPORATE CLIENT (FUNDING COMPANY)
    # =====================================================
    
    client, _ = CorporateClient.objects.get_or_create(
        company_name='Sasol South Africa (Pty) Ltd',
        defaults={
            'campus': campus,
            'trading_name': 'Sasol SA',
            'registration_number': '1979/000000/07',
            'vat_number': '4000000000',
            'phone': '011 441 3111',
            'email': 'procurement@sasol.com',
            'physical_address': 'Sasol Place, 50 Katherine St, Sandton',
            'seta_number': 'L000000000',
            'industry': 'Mining & Energy',
            'status': 'ACTIVE',
            'created_by': superuser,
        }
    )
    print(f"✓ Corporate client: {client.company_name}")
    
    # =====================================================
    # 5. HOST EMPLOYER WITH GPS COORDINATES
    # =====================================================
    
    host, _ = HostEmployer.objects.get_or_create(
        company_name='Sasol Mining - Secunda',
        defaults={
            'campus': campus,
            'trading_name': 'Sasol Mining Secunda',
            'registration_number': '1980/000001/07',
            'physical_address': 'Sasol Mining Complex, R546, Secunda, 2302',
            'gps_latitude': Decimal('-26.5361'),
            'gps_longitude': Decimal('29.1707'),
            'contact_person': 'Pieter Botha',
            'contact_phone': '017 610 5000',
            'contact_email': 'pieter.botha@sasol.com',
            'max_placement_capacity': 50,
            'status': 'APPROVED',
            'created_by': superuser,
        }
    )
    print(f"✓ Host employer: {host.company_name}")
    
    # =====================================================
    # 6. CREATE USERS FOR ALL ROLES
    # =====================================================
    
    # Facilitator User
    facilitator_user, fac_created = User.objects.get_or_create(
        email='facilitator.test@skillsflow.co.za',
        defaults={
            'first_name': 'Sarah',
            'last_name': 'Molefe',
            'is_active': True,
            'phone': '082 555 1001',
            'password': make_password('test1234'),
        }
    )
    fac_profile, _ = FacilitatorProfile.objects.get_or_create(
        user=facilitator_user,
        defaults={
            'employee_number': 'FAC-001',
            'specializations': 'Fitting, Turning, Machining',
            'primary_campus': campus,
        }
    )
    fac_profile.campuses.add(campus)
    print(f"✓ Facilitator: {facilitator_user.get_full_name()} ({facilitator_user.email})")
    
    # WIL Officer User
    officer_user, off_created = User.objects.get_or_create(
        email='officer.test@skillsflow.co.za',
        defaults={
            'first_name': 'Thabo',
            'last_name': 'Nkosi',
            'is_active': True,
            'phone': '082 555 1002',
            'password': make_password('test1234'),
        }
    )
    WorkplaceOfficerProfile.objects.get_or_create(
        user=officer_user,
        defaults={
            'employee_number': 'WIL-001',
            'is_active': True,
            'assigned_region': 'Mpumalanga',
            'created_by': superuser,
        }
    )
    print(f"✓ WIL Officer: {officer_user.get_full_name()} ({officer_user.email})")
    
    # Mentor User
    mentor_user, ment_created = User.objects.get_or_create(
        email='mentor.test@skillsflow.co.za',
        defaults={
            'first_name': 'Willem',
            'last_name': 'Pretorius',
            'is_active': True,
            'phone': '082 555 1003',
            'password': make_password('test1234'),
        }
    )
    print(f"✓ Mentor user: {mentor_user.get_full_name()} ({mentor_user.email})")
    
    # Host Mentor (linked to host employer)
    host_mentor, _ = HostMentor.objects.get_or_create(
        email='mentor.test@skillsflow.co.za',
        host=host,
        defaults={
            'first_name': 'Willem',
            'last_name': 'Pretorius',
            'phone': '082 555 1003',
            'job_title': 'Senior Artisan',
            'trade': 'Fitter and Turner',
            'years_experience': 15,
            'mentor_trained': True,
            'status': 'APPROVED',
            'is_active': True,
            'user': mentor_user,
            'created_by': superuser,
        }
    )
    print(f"✓ Host mentor: {host_mentor.full_name}")
    
    # Learner User
    learner_user, lrn_created = User.objects.get_or_create(
        email='learner.test@skillsflow.co.za',
        defaults={
            'first_name': 'Sipho',
            'last_name': 'Dlamini',
            'is_active': True,
            'phone': '082 555 2001',
            'password': make_password('test1234'),
        }
    )
    print(f"✓ Learner user: {learner_user.get_full_name()} ({learner_user.email})")
    
    # =====================================================
    # 7. PROJECT (TRAINING NOTIFICATION)
    # =====================================================
    
    # Try to find existing or create new
    project = TrainingNotification.objects.filter(title='Sasol Fitter & Turner Apprenticeship Programme 2024').first()
    if not project:
        project = TrainingNotification.objects.create(
            title='Sasol Fitter & Turner Apprenticeship Programme 2024',
            description='Three-year apprenticeship programme for Fitter and Turner trade',
            corporate_client=client,
            qualification=qual,
            project_type='OC_APPRENTICESHIP',
            funder='CORPORATE',
            planned_start_date=TODAY - timedelta(days=365),  # Started 1 year ago
            planned_end_date=TODAY + timedelta(days=730),  # 2 more years
            expected_learner_count=30,
            contract_value=Decimal('4500000.00'),
            status='IN_PROGRESS',
            facilitator=facilitator_user,
            delivery_campus=campus,
            created_by=superuser,
        )
        print(f"✓ Created project: {project.title}")
    else:
        print(f"✓ Project: {project.title}")
    
    # =====================================================
    # 8. COHORT WITH IMPLEMENTATION PLAN
    # =====================================================
    
    cohort, coh_created = Cohort.objects.get_or_create(
        code='SASOL-FIT-2024-C1',
        defaults={
            'name': 'Sasol Fitter & Turner 2024 Cohort 1',
            'qualification': qual,
            'campus': campus,
            'facilitator': facilitator_user,
            'start_date': TODAY - timedelta(days=365),  # Started 1 year ago
            'end_date': TODAY + timedelta(days=730),
            'max_capacity': 15,
            'status': 'ACTIVE',
            'created_by': superuser,
        }
    )
    print(f"✓ Cohort: {cohort.name}")
    
    # Copy implementation plan to cohort
    if coh_created or not CohortImplementationPlan.objects.filter(cohort=cohort).exists():
        try:
            cohort_plan = impl_plan.copy_to_cohort(cohort, superuser)
            print(f"  ✓ Created cohort implementation plan with phases")
        except Exception as e:
            print(f"  ⚠ Could not copy implementation plan: {e}")
            cohort_plan = None
    else:
        cohort_plan = CohortImplementationPlan.objects.filter(cohort=cohort).first()
        print(f"  ✓ Using existing cohort implementation plan")
    
    # =====================================================
    # 9. LINK PROJECT TO COHORT (NOTIntake)
    # =====================================================
    
    intake, _ = NOTIntake.objects.get_or_create(
        training_notification=project,
        intake_number=1,
        defaults={
            'name': 'Main Intake',
            'cohort': cohort,
            'original_cohort_size': 15,
            'status': 'ACTIVE',
            'created_by': superuser,
        }
    )
    print(f"✓ Linked project to cohort via NOTIntake")
    
    # =====================================================
    # 10. LEARNER RECORD
    # =====================================================
    
    learner, lrn_rec_created = Learner.objects.get_or_create(
        sa_id_number='9501015800086',
        defaults={
            'campus': campus,
            'user': learner_user,
            'learner_number': 'LRN-2024-0001',
            'first_name': 'Sipho',
            'last_name': 'Dlamini',
            'email': 'learner.test@skillsflow.co.za',
            'phone_mobile': '082 555 2001',
            'date_of_birth': date(1995, 1, 1),
            'gender': 'M',
            'population_group': 'A',
            'citizenship': 'SA',
            'home_language': 'Zulu',
            'disability_status': 'N',
            'socio_economic_status': 'E',
            'highest_qualification': '4',
            'province_code': 'MP',
            'created_by': superuser,
        }
    )
    print(f"✓ Learner: {learner.get_full_name()} (ID: {learner.sa_id_number})")
    
    # =====================================================
    # 11. ENROLLMENT WITH PARTIAL PROGRESS
    # =====================================================
    
    enrollment, enr_created = Enrollment.objects.get_or_create(
        learner=learner,
        qualification=qual,
        defaults={
            'campus': campus,
            'enrollment_number': f'ENR-{learner.sa_id_number[:6]}-{qual.saqa_id}',
            'cohort': cohort,
            'application_date': TODAY - timedelta(days=400),
            'enrollment_date': TODAY - timedelta(days=365),
            'start_date': TODAY - timedelta(days=365),
            'expected_completion': TODAY + timedelta(days=730),
            'status': 'ACTIVE',
            'funding_type': 'LEARNERSHIP',
            'funding_source': 'Sasol SA',
            'funding_reference': project.reference_number,
            'agreement_signed': True,
            'agreement_date': TODAY - timedelta(days=365),
            'created_by': superuser,
        }
    )
    if enr_created:
        print(f"✓ Created enrollment: {enrollment.enrollment_number}")
    else:
        print(f"✓ Using enrollment: {enrollment.enrollment_number}")
    
    # =====================================================
    # 12. MODULE PROGRESS - YEAR 1 COMPLETE, YEAR 2 IN PROGRESS
    # =====================================================
    
    # Get all modules
    all_modules = Module.objects.filter(qualification=qual).order_by('year_level', 'code')
    
    progress_created = 0
    for module in all_modules:
        # Determine status based on year
        if module.year_level == 1:
            # Year 1 modules - all completed
            status = 'COMPETENT'
            formative_status = 'COMPETENT'
            summative_status = 'COMPETENT'
            completed_at = timezone.now() - timedelta(days=30)
        elif module.year_level == 2:
            # Year 2 modules - some in progress, some not started
            if 'KM-201' in module.code or 'PM-201' in module.code:
                # First Y2 modules completed
                status = 'COMPETENT'
                formative_status = 'COMPETENT'
                summative_status = 'COMPETENT'
                completed_at = timezone.now() - timedelta(days=15)
            elif 'KM-202' in module.code or 'PM-202' in module.code:
                # Second Y2 modules in progress
                status = 'IN_PROGRESS'
                formative_status = 'IN_PROGRESS'
                summative_status = 'NOT_STARTED'
                completed_at = None
            else:
                # Workplace modules in progress
                status = 'IN_PROGRESS'
                formative_status = 'NOT_STARTED'
                summative_status = 'NOT_STARTED'
                completed_at = None
        else:
            # Year 3 - not started
            status = 'NOT_STARTED'
            formative_status = 'NOT_STARTED'
            summative_status = 'NOT_STARTED'
            completed_at = None
        
        progress, created = LearnerModuleProgress.objects.update_or_create(
            enrollment=enrollment,
            module=module,
            defaults={
                'overall_status': status,
                'formative_status': formative_status,
                'summative_status': summative_status,
                'overall_completed_at': completed_at,
                'formative_completed_at': completed_at if formative_status == 'COMPETENT' else None,
                'summative_completed_at': completed_at if summative_status == 'COMPETENT' else None,
                'formative_competent_count': 3 if formative_status == 'COMPETENT' else (1 if formative_status == 'IN_PROGRESS' else 0),
                'formative_total_count': 3,
                'summative_competent_count': 1 if summative_status == 'COMPETENT' else 0,
                'summative_total_count': 1,
                'created_by': superuser,
            }
        )
        if created:
            progress_created += 1
    
    print(f"✓ Module progress: {progress_created} created, {all_modules.count()} total")
    
    # Calculate progress
    total_modules = all_modules.count()
    completed_modules = LearnerModuleProgress.objects.filter(
        enrollment=enrollment,
        overall_status='COMPETENT'
    ).count()
    progress_pct = int((completed_modules / total_modules) * 100)
    print(f"  → Progress: {completed_modules}/{total_modules} modules ({progress_pct}%)")
    
    # =====================================================
    # 13. WORKPLACE PLACEMENT
    # =====================================================
    
    placement, plc_created = WorkplacePlacement.objects.get_or_create(
        learner=learner,
        host=host,
        enrollment=enrollment,
        defaults={
            'campus': campus,
            'workplace_officer': officer_user,
            'mentor': host_mentor,
            'training_notification': project,
            'start_date': TODAY - timedelta(days=300),
            'expected_end_date': TODAY + timedelta(days=500),
            'status': 'ACTIVE',
            'stipend_daily_rate': Decimal('225.00'),
            'created_by': superuser,
        }
    )
    if plc_created:
        print(f"✓ Created workplace placement at {host.company_name}")
    else:
        print(f"✓ Using placement at {host.company_name}")
    
    # =====================================================
    # 14. PROJECT STAKEHOLDERS
    # =====================================================
    
    # Add facilitator as stakeholder
    NOTStakeholder.objects.get_or_create(
        training_notification=project,
        user=facilitator_user,
        role_in_project='FACILITATOR',
        defaults={
            'department': 'ACADEMIC',
            'created_by': superuser,
        }
    )
    
    # Add WIL officer as stakeholder
    NOTStakeholder.objects.get_or_create(
        training_notification=project,
        user=officer_user,
        role_in_project='LOGISTICS_LEAD',
        defaults={
            'department': 'LOGISTICS',
            'created_by': superuser,
        }
    )
    
    print(f"✓ Added stakeholders to project")
    
    # =====================================================
    # 15. VENUE FOR TRAINING SESSIONS
    # =====================================================
    
    venue, _ = Venue.objects.get_or_create(
        campus=campus,
        code='WS-101',
        defaults={
            'name': 'Workshop 101 - Fitting & Turning',
            'venue_type': 'WORKSHOP',
            'capacity': 20,
            'equipment': ['Lathe', 'Milling Machine', 'Drill Press', 'Bench Grinder'],
            'is_active': True,
            'created_by': superuser,
        }
    )
    print(f"✓ Venue: {venue.name}")
    
    # =====================================================
    # 16. SCHEDULE SESSIONS (CLASSES)
    # =====================================================
    
    from datetime import time
    
    # Get Year 2 modules for scheduling
    year2_modules = Module.objects.filter(qualification=qual, year_level=2).order_by('sequence_order')[:4]
    
    # Create schedule sessions for the next 2 weeks
    sessions_created = 0
    
    # Session schedule: Mon-Fri, 08:00-12:00 and 13:00-16:00
    session_times = [
        (time(8, 0), time(12, 0), 'LECTURE'),
        (time(13, 0), time(16, 0), 'PRACTICAL'),
    ]
    
    # Generate sessions for the next 14 days
    for day_offset in range(14):
        session_date = TODAY + timedelta(days=day_offset)
        
        # Skip weekends
        if session_date.weekday() >= 5:
            continue
        
        # Pick a module based on the day
        module = year2_modules[day_offset % len(year2_modules)] if year2_modules else None
        if not module:
            continue
        
        for start_time, end_time, session_type in session_times:
            session, created = ScheduleSession.objects.get_or_create(
                cohort=cohort,
                module=module,
                venue=venue,
                date=session_date,
                start_time=start_time,
                defaults={
                    'facilitator': facilitator_user,
                    'end_time': end_time,
                    'session_type': session_type,
                    'topic': f"{module.title} - {session_type.title()} Session",
                    'description': f"{'Theory and concepts' if session_type == 'LECTURE' else 'Hands-on practical work'} for {module.title}",
                    'is_cancelled': False,
                    'created_by': superuser,
                }
            )
            if created:
                sessions_created += 1
    
    print(f"✓ Created {sessions_created} schedule sessions for next 2 weeks")
    
    # =====================================================
    # SUMMARY
    # =====================================================
    
    print("\n" + "=" * 70)
    print("CROSS-PORTAL TEST DATA CREATED SUCCESSFULLY")
    print("=" * 70)
    print("\n📌 TEST ACCOUNTS (all passwords: test1234)")
    print("-" * 50)
    print(f"  🎓 Learner:     {learner_user.email}")
    print(f"  👨‍🏫 Facilitator: {facilitator_user.email}")
    print(f"  🏭 WIL Officer: {officer_user.email}")
    print(f"  👷 Mentor:      {mentor_user.email}")
    print(f"  🔑 Superuser:   {superuser.email}")
    
    print("\n📊 LEARNER PROGRESS")
    print("-" * 50)
    print(f"  Qualification: {qual.short_title}")
    print(f"  Enrollment:    {enrollment.enrollment_number}")
    print(f"  Status:        {enrollment.status}")
    print(f"  Progress:      {progress_pct}% ({completed_modules}/{total_modules} modules)")
    print(f"  Current Year:  Year 2 of 3")
    
    print("\n📅 CLASS SCHEDULE")
    print("-" * 50)
    print(f"  Sessions:      {sessions_created} sessions over 2 weeks")
    print(f"  Venue:         {venue.name}")
    print(f"  Times:         08:00-12:00 (Lecture), 13:00-16:00 (Practical)")
    
    print("\n🏢 PROJECT & WORKPLACE")
    print("-" * 50)
    print(f"  Project:       {project.title}")
    print(f"  Cohort:        {cohort.code}")
    print(f"  Host:          {host.company_name}")
    print(f"  Mentor:        {host_mentor.full_name}")
    
    print("\n🔗 PORTAL ACCESS")
    print("-" * 50)
    print("  http://127.0.0.1:8000/portal/student/    → Learner Portal")
    print("  http://127.0.0.1:8000/portal/facilitator/ → Facilitator Portal")
    print("  http://127.0.0.1:8000/portal/officer/    → WIL Officer Portal")
    print("  http://127.0.0.1:8000/portal/mentor/     → Mentor Portal")
    print("=" * 70)


if __name__ == '__main__':
    main()
