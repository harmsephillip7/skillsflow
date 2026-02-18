#!/usr/bin/env python
"""
Schedule Test Data Creation Script
===================================
Creates comprehensive test data to verify schedule pre-population functionality.

This script creates:
1. A qualification with modules
2. An implementation plan template with phases and module slots
3. A cohort with start date
4. Links cohort to implementation plan
5. Generates schedule sessions
6. Creates test users (learner, facilitator, mentor, WIL officer)
7. Creates enrollments and placements

Run with:
    python create_schedule_test_data.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


def create_schedule_test_data():
    """Create all test data for schedule testing."""
    
    print("=" * 60)
    print("SCHEDULE TEST DATA CREATION")
    print("=" * 60)
    
    # Import models
    from tenants.models import Campus, Brand
    from academics.models import (
        Qualification, Module, ImplementationPlan, 
        ImplementationPhase, ImplementationModuleSlot,
        Enrollment
    )
    from logistics.models import (
        Cohort, Venue, CohortImplementationPlan, 
        CohortImplementationPhase, CohortImplementationModuleSlot,
        ScheduleSession
    )
    from learners.models import Learner, SETA
    from corporate.models import (
        HostEmployer, HostMentor, WorkplacePlacement
    )
    from core.models import FacilitatorProfile
    
    # Get or create brand and campus
    brand = Brand.objects.first()
    if not brand:
        brand = Brand.objects.create(
            name='Test Training Provider',
            code='TEST',
            is_active=True
        )
        print(f"✓ Created brand: {brand.name}")
    
    campus = Campus.objects.first()
    if not campus:
        campus = Campus.objects.create(
            brand=brand,
            name='Main Campus',
            code='MAIN',
            city='Johannesburg',
            province='GP',
            is_active=True
        )
        print(f"✓ Created campus: {campus.name}")
    
    # =========================================================================
    # 1. CREATE SUPERUSER IF NOT EXISTS
    # =========================================================================
    superuser = User.objects.filter(is_superuser=True).first()
    if not superuser:
        superuser = User.objects.create_superuser(
            email='admin@skillsflow.co.za',
            password='admin1234',
            first_name='System',
            last_name='Admin'
        )
        print(f"✓ Created superuser: {superuser.email}")
    else:
        print(f"• Using existing superuser: {superuser.email}")
    
    # =========================================================================
    # 2. CREATE FACILITATOR USER
    # =========================================================================
    facilitator_user, created = User.objects.get_or_create(
        email='schedule.facilitator@skillsflow.co.za',
        defaults={
            'first_name': 'James',
            'last_name': 'Facilitator',
            'is_staff': True,
            'is_active': True,
        }
    )
    if created:
        facilitator_user.set_password('test1234')
        facilitator_user.save()
        print(f"✓ Created facilitator user: {facilitator_user.email}")
    else:
        print(f"• Using existing facilitator: {facilitator_user.email}")
    
    # Create FacilitatorProfile for the facilitator user
    facilitator_profile, fp_created = FacilitatorProfile.objects.get_or_create(
        user=facilitator_user,
        defaults={
            'primary_campus': campus,
            'employee_number': 'FAC-001',
            'specializations': 'Electrical Engineering, Industrial Systems',
        }
    )
    if fp_created:
        facilitator_profile.campuses.add(campus)
        print(f"✓ Created facilitator profile with campus: {campus.name}")
    else:
        # Ensure campus is assigned
        if not facilitator_profile.campuses.filter(id=campus.id).exists():
            facilitator_profile.campuses.add(campus)
        if not facilitator_profile.primary_campus:
            facilitator_profile.primary_campus = campus
            facilitator_profile.save()
        print(f"• Using existing facilitator profile")
    
    # =========================================================================
    # 3. CREATE LEARNER USER
    # =========================================================================
    learner_user, created = User.objects.get_or_create(
        email='schedule.learner@skillsflow.co.za',
        defaults={
            'first_name': 'Thabo',
            'last_name': 'Learner',
            'is_staff': False,
            'is_active': True,
        }
    )
    if created:
        learner_user.set_password('test1234')
        learner_user.save()
        print(f"✓ Created learner user: {learner_user.email}")
    else:
        print(f"• Using existing learner user: {learner_user.email}")
    
    # =========================================================================
    # 4. CREATE MENTOR USER
    # =========================================================================
    mentor_user, created = User.objects.get_or_create(
        email='schedule.mentor@skillsflow.co.za',
        defaults={
            'first_name': 'Sarah',
            'last_name': 'Mentor',
            'is_staff': False,
            'is_active': True,
        }
    )
    if created:
        mentor_user.set_password('test1234')
        mentor_user.save()
        print(f"✓ Created mentor user: {mentor_user.email}")
    else:
        print(f"• Using existing mentor user: {mentor_user.email}")
    
    # =========================================================================
    # 5. CREATE WIL OFFICER USER
    # =========================================================================
    officer_user, created = User.objects.get_or_create(
        email='schedule.officer@skillsflow.co.za',
        defaults={
            'first_name': 'David',
            'last_name': 'Officer',
            'is_staff': True,
            'is_active': True,
        }
    )
    if created:
        officer_user.set_password('test1234')
        officer_user.save()
        print(f"✓ Created WIL officer user: {officer_user.email}")
    else:
        print(f"• Using existing WIL officer: {officer_user.email}")
    
    # =========================================================================
    # 6. CREATE SETA AND QUALIFICATION
    # =========================================================================
    seta, created = SETA.objects.get_or_create(
        code='MERSETA',
        defaults={
            'name': 'Manufacturing, Engineering and Related Services SETA',
            'is_active': True,
        }
    )
    if created:
        print(f"✓ Created SETA: {seta.code}")
    
    TODAY = date.today()
    
    qualification, created = Qualification.objects.get_or_create(
        saqa_id='67890',
        defaults={
            'title': 'Occupational Certificate: Electrician',
            'short_title': 'OC: Electrician (NQF 4)',
            'nqf_level': 4,
            'credits': 240,
            'qualification_type': 'OC',
            'seta': seta,
            'registration_start': TODAY - timedelta(days=365),
            'registration_end': TODAY + timedelta(days=365 * 5),
            'last_enrollment_date': TODAY + timedelta(days=365 * 4),
            'is_active': True,
        }
    )
    if created:
        print(f"✓ Created qualification: {qualification.short_title}")
    else:
        print(f"• Using existing qualification: {qualification.short_title}")
    
    # =========================================================================
    # 7. CREATE MODULES FOR QUALIFICATION
    # =========================================================================
    modules_data = [
        {'code': 'ELEC-101', 'title': 'Electrical Fundamentals', 'nqf_level': 4, 'credits': 20, 'notional_hours': 200, 'type': 'K'},
        {'code': 'ELEC-102', 'title': 'Circuit Theory', 'nqf_level': 4, 'credits': 25, 'notional_hours': 250, 'type': 'K'},
        {'code': 'ELEC-103', 'title': 'Wiring & Installation', 'nqf_level': 4, 'credits': 30, 'notional_hours': 300, 'type': 'P'},
        {'code': 'ELEC-104', 'title': 'Motor Control', 'nqf_level': 4, 'credits': 25, 'notional_hours': 250, 'type': 'P'},
        {'code': 'ELEC-105', 'title': 'Industrial Electrical Systems', 'nqf_level': 4, 'credits': 30, 'notional_hours': 300, 'type': 'P'},
    ]
    
    modules = []
    for mod_data in modules_data:
        module, created = Module.objects.get_or_create(
            code=mod_data['code'],
            qualification=qualification,
            defaults={
                'title': mod_data['title'],
                'year_level': 1,
                'credits': mod_data['credits'],
                'notional_hours': mod_data['notional_hours'],
                'module_type': mod_data['type'],
                'is_active': True,
            }
        )
        modules.append(module)
        if created:
            print(f"  ✓ Created module: {module.code} - {module.title}")
    
    print(f"✓ {len(modules)} modules ready")
    
    # =========================================================================
    # 8. CREATE VENUE
    # =========================================================================
    venue, created = Venue.objects.get_or_create(
        code='ELEC-LAB-01',
        defaults={
            'campus': campus,
            'name': 'Electrical Workshop Lab 1',
            'venue_type': 'WORKSHOP',
            'capacity': 20,
            'is_active': True,
        }
    )
    if created:
        print(f"✓ Created venue: {venue.name}")
    else:
        print(f"• Using existing venue: {venue.name}")
    
    # =========================================================================
    # 9. CREATE IMPLEMENTATION PLAN TEMPLATE
    # =========================================================================
    impl_plan, created = ImplementationPlan.objects.get_or_create(
        qualification=qualification,
        name='Electrician Standard Programme',
        defaults={
            'description': 'Standard 12-month programme for Electrician qualification',
            'delivery_mode': 'FULL_TIME',
            'total_weeks': 52,
            'contact_days_per_week': 5,
            'hours_per_day': 6,
            'classroom_hours_per_day': 2,
            'practical_hours_per_day': 4,
            'is_default': True,
            'status': 'ACTIVE',
            'created_by': superuser,
        }
    )
    if created:
        print(f"✓ Created implementation plan template: {impl_plan.name}")
        
        # Create phases
        # Phase 1: Induction (1 week)
        phase1 = ImplementationPhase.objects.create(
            implementation_plan=impl_plan,
            phase_type='INDUCTION',
            name='Programme Induction',
            sequence=1,
            duration_weeks=1,
            year_level=1,
            description='Introduction to programme and workplace orientation'
        )
        print(f"  ✓ Created phase: {phase1.name}")
        
        # Phase 2: Institutional Block 1 (8 weeks)
        phase2 = ImplementationPhase.objects.create(
            implementation_plan=impl_plan,
            phase_type='INSTITUTIONAL',
            name='Institutional Block 1',
            sequence=2,
            duration_weeks=8,
            year_level=1,
            description='First institutional training block'
        )
        print(f"  ✓ Created phase: {phase2.name}")
        
        # Add module slots to Phase 2
        slot1 = ImplementationModuleSlot.objects.create(
            phase=phase2,
            module=modules[0],  # Electrical Fundamentals
            sequence=1,
            classroom_sessions=10,
            practical_sessions=10,
            total_days=10
        )
        slot2 = ImplementationModuleSlot.objects.create(
            phase=phase2,
            module=modules[1],  # Circuit Theory
            sequence=2,
            classroom_sessions=15,
            practical_sessions=15,
            total_days=15
        )
        slot3 = ImplementationModuleSlot.objects.create(
            phase=phase2,
            module=modules[2],  # Wiring & Installation
            sequence=3,
            classroom_sessions=15,
            practical_sessions=15,
            total_days=15
        )
        print(f"  ✓ Created {3} module slots for Block 1")
        
        # Phase 3: Workplace Stint 1 (12 weeks)
        phase3 = ImplementationPhase.objects.create(
            implementation_plan=impl_plan,
            phase_type='WORKPLACE',
            name='Workplace Stint 1',
            sequence=3,
            duration_weeks=12,
            year_level=1,
            description='First workplace experience period'
        )
        print(f"  ✓ Created phase: {phase3.name}")
        
        # Phase 4: Institutional Block 2 (8 weeks)
        phase4 = ImplementationPhase.objects.create(
            implementation_plan=impl_plan,
            phase_type='INSTITUTIONAL',
            name='Institutional Block 2',
            sequence=4,
            duration_weeks=8,
            year_level=1,
            description='Second institutional training block'
        )
        print(f"  ✓ Created phase: {phase4.name}")
        
        # Add module slots to Phase 4
        slot4 = ImplementationModuleSlot.objects.create(
            phase=phase4,
            module=modules[3],  # Motor Control
            sequence=1,
            classroom_sessions=15,
            practical_sessions=15,
            total_days=15
        )
        slot5 = ImplementationModuleSlot.objects.create(
            phase=phase4,
            module=modules[4],  # Industrial Electrical Systems
            sequence=2,
            classroom_sessions=20,
            practical_sessions=20,
            total_days=20
        )
        print(f"  ✓ Created {2} module slots for Block 2")
        
    else:
        print(f"• Using existing implementation plan: {impl_plan.name}")
    
    # =========================================================================
    # 10. CREATE COHORT
    # =========================================================================
    TODAY = date.today()
    cohort_start = TODAY  # Start today
    
    cohort, created = Cohort.objects.get_or_create(
        code='SCHED-TEST-2026-C1',
        defaults={
            'name': 'Schedule Test Cohort 2026',
            'qualification': qualification,
            'campus': campus,
            'start_date': cohort_start,
            'end_date': cohort_start + timedelta(weeks=52),
            'max_capacity': 20,
            'status': 'ACTIVE',
            'facilitator': facilitator_user,
        }
    )
    if created:
        print(f"✓ Created cohort: {cohort.code}")
    else:
        # Update start date to today for testing
        cohort.start_date = cohort_start
        cohort.facilitator = facilitator_user
        cohort.save()
        print(f"• Using existing cohort: {cohort.code} (updated start date to {cohort_start})")
    
    # =========================================================================
    # 11. CREATE LEARNER PROFILE
    # =========================================================================
    learner, created = Learner.objects.get_or_create(
        user=learner_user,
        defaults={
            'campus': campus,
            'first_name': 'Thabo',
            'last_name': 'Learner',
            'sa_id_number': '9501015800086',
            'phone_mobile': '0821234567',
            'email': learner_user.email,
            'learner_number': 'LRN-SCHED-001',
            'date_of_birth': date(1995, 1, 1),
            'gender': 'M',
            'population_group': 'A',
            'citizenship': 'SA',
        }
    )
    if created:
        print(f"✓ Created learner profile: {learner.learner_number}")
    else:
        print(f"• Using existing learner: {learner.learner_number}")
    
    # =========================================================================
    # 12. CREATE ENROLLMENT
    # =========================================================================
    enrollment, created = Enrollment.objects.get_or_create(
        learner=learner,
        qualification=qualification,
        defaults={
            'enrollment_number': f'ENR-SCHED-{TODAY.strftime("%Y%m%d")}-001',
            'cohort': cohort,
            'campus': campus,
            'status': 'ACTIVE',
            'application_date': cohort_start - timedelta(days=30),
            'enrollment_date': cohort_start,
            'start_date': cohort_start,
            'expected_completion': cohort_start + timedelta(weeks=52),
            'created_by': superuser,
        }
    )
    if created:
        print(f"✓ Created enrollment for {learner.learner_number}")
    else:
        # Make sure enrollment is linked to cohort
        if enrollment.cohort != cohort:
            enrollment.cohort = cohort
            enrollment.save()
        print(f"• Using existing enrollment")
    
    # =========================================================================
    # 13. CREATE HOST EMPLOYER
    # =========================================================================
    employer, created = HostEmployer.objects.get_or_create(
        company_name='Eskom Holdings',
        defaults={
            'campus': campus,
            'trading_name': 'Eskom',
            'registration_number': '1923/000002/30',
            'contact_person': 'John Smith',
            'contact_email': 'john.smith@eskom.co.za',
            'contact_phone': '0114569000',
            'physical_address': '1 Megawatt Park, Sunninghill, Johannesburg',
            'status': 'APPROVED',
        }
    )
    if created:
        print(f"✓ Created host employer: {employer.company_name}")
    else:
        print(f"• Using existing employer: {employer.company_name}")
    
    # =========================================================================
    # 14. CREATE MENTOR
    # =========================================================================
    mentor, created = HostMentor.objects.get_or_create(
        email=mentor_user.email,
        host=employer,
        defaults={
            'user': mentor_user,
            'first_name': mentor_user.first_name,
            'last_name': mentor_user.last_name,
            'phone': '0829876543',
            'job_title': 'Senior Electrician',
            'status': 'APPROVED',
        }
    )
    if created:
        print(f"✓ Created mentor: {mentor.first_name} {mentor.last_name}")
    else:
        print(f"• Using existing mentor: {mentor.first_name} {mentor.last_name}")
    
    # =========================================================================
    # 15. CREATE WORKPLACE PLACEMENT
    # =========================================================================
    placement, created = WorkplacePlacement.objects.get_or_create(
        learner=learner,
        enrollment=enrollment,
        defaults={
            'campus': campus,
            'host': employer,
            'mentor': mentor,
            'workplace_officer': officer_user,
            'placement_reference': f'WPL-SCHED-{TODAY.strftime("%Y%m%d")}-001',
            'start_date': cohort_start + timedelta(weeks=9),  # After Block 1
            'expected_end_date': cohort_start + timedelta(weeks=21),
            'status': 'PENDING',
        }
    )
    if created:
        print(f"✓ Created workplace placement for {learner.learner_number}")
    else:
        print(f"• Using existing workplace placement")
    
    # =========================================================================
    # 16. CREATE COHORT IMPLEMENTATION PLAN AND GENERATE SESSIONS
    # =========================================================================
    print("\n" + "=" * 60)
    print("GENERATING SCHEDULE SESSIONS")
    print("=" * 60)
    
    # Delete existing sessions for this cohort to regenerate
    existing_sessions = ScheduleSession.objects.filter(cohort=cohort)
    if existing_sessions.exists():
        count = existing_sessions.count()
        existing_sessions.delete()
        print(f"✓ Deleted {count} existing sessions for fresh generation")
    
    # Check if cohort implementation plan exists
    cohort_impl_plan = None
    try:
        cohort_impl_plan = cohort.implementation_plan
        print(f"• Using existing cohort implementation plan")
    except:
        pass
    
    if not cohort_impl_plan:
        # Create cohort implementation plan from template
        cohort_impl_plan = impl_plan.copy_to_cohort(cohort, created_by=superuser)
        print(f"✓ Created cohort implementation plan from template")
    
    # Generate schedule sessions
    sessions = cohort_impl_plan.generate_schedule_sessions()
    print(f"✓ Generated {len(sessions)} schedule sessions")
    
    # =========================================================================
    # 17. SUMMARY
    # =========================================================================
    print("\n" + "=" * 60)
    print("SUMMARY - TEST CREDENTIALS")
    print("=" * 60)
    
    session_count = ScheduleSession.objects.filter(cohort=cohort).count()
    first_session = ScheduleSession.objects.filter(cohort=cohort).order_by('date', 'start_time').first()
    last_session = ScheduleSession.objects.filter(cohort=cohort).order_by('date', 'start_time').last()
    
    print(f"""
SCHEDULE DATA:
  • Total sessions: {session_count}
  • First session: {first_session.date if first_session else 'N/A'} at {first_session.start_time if first_session else 'N/A'}
  • Last session: {last_session.date if last_session else 'N/A'} at {last_session.start_time if last_session else 'N/A'}
  • Cohort: {cohort.code}
  • Qualification: {qualification.title}

TEST USER CREDENTIALS:
  
  Learner Portal:
    • Email: schedule.learner@skillsflow.co.za
    • Password: test1234
    • URL: http://127.0.0.1:8000/portal/student/schedule/
  
  Facilitator Portal:
    • Email: schedule.facilitator@skillsflow.co.za
    • Password: test1234
    • URL: http://127.0.0.1:8000/portal/facilitator/schedule/
  
  Mentor Portal:
    • Email: schedule.mentor@skillsflow.co.za
    • Password: test1234
    • URL: http://127.0.0.1:8000/portal/mentor/
  
  WIL Officer Portal:
    • Email: schedule.officer@skillsflow.co.za
    • Password: test1234
    • URL: http://127.0.0.1:8000/portal/officer/

  Admin:
    • Email: admin@skillsflow.co.za
    • URL: http://127.0.0.1:8000/admin/
""")
    
    print("=" * 60)
    print("✓ SCHEDULE TEST DATA CREATION COMPLETE")
    print("=" * 60)
    
    return {
        'cohort': cohort,
        'sessions': session_count,
        'learner': learner,
        'facilitator': facilitator_user,
        'mentor': mentor,
        'officer': officer_user,
    }


if __name__ == '__main__':
    with transaction.atomic():
        create_schedule_test_data()
