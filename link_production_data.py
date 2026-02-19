#!/usr/bin/env python
"""
Production Data Linking Script
===============================
Links existing learners to cohorts, creates enrollments, 
assigns facilitators, and generates schedules.
"""

import os
import sys
import django
import random
from datetime import date, timedelta, time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count

from learners.models import Learner
from academics.models import (
    Qualification, Module, ImplementationPlan, Enrollment,
    ImplementationPhase, ImplementationModuleSlot
)
from logistics.models import Cohort, ScheduleSession, CohortImplementationPlan, Venue
from corporate.models import HostEmployer, HostMentor, WorkplacePlacement
from core.models import FacilitatorProfile
from tenants.models import Campus, Brand

User = get_user_model()


def create_facilitator_profiles():
    """Create facilitator profiles for staff users."""
    print("\n--- CREATING FACILITATOR PROFILES ---")
    
    # Get or create the Facilitator group
    facilitator_group, _ = Group.objects.get_or_create(name='Facilitator')
    
    # Get all campuses
    campuses = list(Campus.objects.all())
    if not campuses:
        print("  ✗ No campuses found!")
        return []
    
    # Create some facilitator users if needed
    facilitator_emails = [
        ('facilitator1@skillsflow.co.za', 'John', 'Smith'),
        ('facilitator2@skillsflow.co.za', 'Sarah', 'Johnson'),
        ('facilitator3@skillsflow.co.za', 'Michael', 'Williams'),
        ('facilitator4@skillsflow.co.za', 'Emily', 'Brown'),
        ('facilitator5@skillsflow.co.za', 'David', 'Davis'),
    ]
    
    created_profiles = []
    
    for email, first_name, last_name in facilitator_emails:
        user, user_created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'first_name': first_name,
                'last_name': last_name,
                'is_active': True,
                'is_staff': True,
            }
        )
        if user_created:
            user.set_password('test1234')
            user.save()
            print(f"  ✓ Created user: {email}")
        
        # Add to facilitator group
        user.groups.add(facilitator_group)
        
        # Create facilitator profile
        campus = random.choice(campuses)
        profile, prof_created = FacilitatorProfile.objects.get_or_create(
            user=user,
            defaults={
                'primary_campus': campus,
                'employee_number': f'FAC-{user.id:03d}',
                'specializations': 'General Training, Assessment',
            }
        )
        if prof_created:
            # Assign 2-3 campuses
            profile.campuses.add(campus)
            for _ in range(random.randint(1, 2)):
                profile.campuses.add(random.choice(campuses))
            print(f"  ✓ Created profile for {email} at {campus.name}")
        
        created_profiles.append(profile)
    
    print(f"  Total facilitator profiles: {FacilitatorProfile.objects.count()}")
    return created_profiles


def assign_facilitators_to_cohorts():
    """Assign facilitators to cohorts that don't have one."""
    print("\n--- ASSIGNING FACILITATORS TO COHORTS ---")
    
    profiles = list(FacilitatorProfile.objects.all())
    if not profiles:
        print("  ✗ No facilitator profiles found!")
        return
    
    cohorts_without_fac = Cohort.objects.filter(facilitator__isnull=True)
    print(f"  Cohorts without facilitator: {cohorts_without_fac.count()}")
    
    for cohort in cohorts_without_fac:
        # Try to match by campus if possible
        matching_profiles = [p for p in profiles if cohort.campus in p.campuses.all()]
        if matching_profiles:
            profile = random.choice(matching_profiles)
        else:
            profile = random.choice(profiles)
        
        cohort.facilitator = profile.user
        cohort.save()
        print(f"  ✓ Assigned {profile.user.email} to {cohort.name}")


def create_implementation_plans_for_qualifications():
    """Create implementation plans for qualifications that don't have one."""
    print("\n--- CREATING IMPLEMENTATION PLANS ---")
    
    quals_without_plan = Qualification.objects.exclude(
        id__in=ImplementationPlan.objects.values_list('qualification_id', flat=True)
    )
    print(f"  Qualifications without implementation plan: {quals_without_plan.count()}")
    
    for qual in quals_without_plan:
        # Create a standard implementation plan
        plan = ImplementationPlan.objects.create(
            qualification=qual,
            name=f"Standard Programme - {qual.title[:30]}",
            description=f"Standard implementation plan for {qual.title}",
            total_weeks=52,
            contact_days_per_week=5,
            hours_per_day=6,
            status='ACTIVE',
            is_default=True,
        )
        
        # Get modules for this qualification
        modules = list(Module.objects.filter(qualification=qual))
        
        # Create phases
        # Phase 1: Induction (1 week)
        induction = ImplementationPhase.objects.create(
            implementation_plan=plan,
            name="Programme Induction",
            phase_type="INDUCTION",
            duration_weeks=1,
            sequence=1,
            description="Introduction to the programme"
        )
        
        # Phase 2: Institutional Block 1 (12 weeks)
        block1 = ImplementationPhase.objects.create(
            implementation_plan=plan,
            name="Institutional Block 1",
            phase_type="INSTITUTIONAL",
            duration_weeks=12,
            sequence=2,
            description="First institutional learning block"
        )
        
        # Add modules to block 1
        for i, module in enumerate(modules[:len(modules)//2]):
            ImplementationModuleSlot.objects.create(
                phase=block1,
                module=module,
                sequence=i+1,
                classroom_sessions=2,
                practical_sessions=3,
                total_days=5
            )
        
        # Phase 3: Workplace 1 (12 weeks)
        workplace1 = ImplementationPhase.objects.create(
            implementation_plan=plan,
            name="Workplace Stint 1",
            phase_type="WORKPLACE",
            duration_weeks=12,
            sequence=3,
            description="First workplace experience"
        )
        
        # Phase 4: Institutional Block 2 (12 weeks)
        block2 = ImplementationPhase.objects.create(
            implementation_plan=plan,
            name="Institutional Block 2",
            phase_type="INSTITUTIONAL",
            duration_weeks=12,
            sequence=4,
            description="Second institutional learning block"
        )
        
        # Add remaining modules to block 2
        for i, module in enumerate(modules[len(modules)//2:]):
            ImplementationModuleSlot.objects.create(
                phase=block2,
                module=module,
                sequence=i+1,
                classroom_sessions=2,
                practical_sessions=3,
                total_days=5
            )
        
        # Phase 5: Workplace 2 (12 weeks)
        workplace2 = ImplementationPhase.objects.create(
            implementation_plan=plan,
            name="Workplace Stint 2",
            phase_type="WORKPLACE",
            duration_weeks=12,
            sequence=5,
            description="Second workplace experience"
        )
        
        print(f"  ✓ Created plan for: {qual.title[:40]}... ({len(modules)} modules)")
    
    print(f"  Total implementation plans: {ImplementationPlan.objects.count()}")


def enroll_learners_in_cohorts():
    """Enroll unenrolled learners in available cohorts."""
    print("\n--- ENROLLING LEARNERS IN COHORTS ---")
    
    # Get unenrolled learners
    enrolled_learner_ids = Enrollment.objects.values_list('learner_id', flat=True)
    unenrolled = Learner.objects.exclude(id__in=enrolled_learner_ids)
    print(f"  Unenrolled learners: {unenrolled.count()}")
    
    if not unenrolled.exists():
        print("  All learners are already enrolled!")
        return
    
    # Get cohorts with space (limit enrollments per cohort)
    cohorts = list(Cohort.objects.filter(status__in=['ACTIVE', 'ENROLLED', 'PLANNING']))
    if not cohorts:
        # Use any cohort
        cohorts = list(Cohort.objects.all()[:20])
    
    if not cohorts:
        print("  ✗ No cohorts available!")
        return
    
    enrolled_count = 0
    for learner in unenrolled:
        # Pick a cohort (distribute evenly)
        cohort = cohorts[enrolled_count % len(cohorts)]
        
        # Create enrollment
        enroll_date = date.today() - timedelta(days=random.randint(1, 90))
        enrollment_number = f"ENR-{learner.learner_number}-{cohort.id}"
        enrollment, created = Enrollment.objects.get_or_create(
            learner=learner,
            cohort=cohort,
            defaults={
                'qualification': cohort.qualification,
                'campus': cohort.campus or learner.campus,
                'enrollment_date': enroll_date,
                'application_date': enroll_date - timedelta(days=random.randint(7, 30)),
                'expected_completion': enroll_date + timedelta(days=365),
                'enrollment_number': enrollment_number,
                'status': random.choice(['ACTIVE', 'ENROLLED']),
            }
        )
        
        if created:
            enrolled_count += 1
            if enrolled_count <= 10 or enrolled_count % 20 == 0:
                print(f"  ✓ Enrolled {learner} in {cohort.name}")
    
    print(f"  Total new enrollments: {enrolled_count}")
    print(f"  Total enrollments now: {Enrollment.objects.count()}")


def create_workplace_data():
    """Create host employers, mentors, and placements for enrolled learners."""
    print("\n--- CREATING WORKPLACE DATA ---")
    
    # Get a campus for host employers
    default_campus = Campus.objects.first()
    if not default_campus:
        print("  ✗ No campuses available!")
        return
    
    # Create some host employers
    employer_data = [
        ('Eskom Holdings', 'Electricity generation and distribution'),
        ('Sasol Limited', 'Energy and chemical company'),
        ('MTN Group', 'Telecommunications'),
        ('Standard Bank', 'Banking and financial services'),
        ('Shoprite Holdings', 'Retail'),
        ('Vodacom', 'Telecommunications'),
        ('Anglo American', 'Mining'),
        ('Nedbank', 'Banking'),
        ('Discovery Limited', 'Insurance and financial services'),
        ('Telkom SA', 'Telecommunications'),
    ]
    
    employers = []
    for name, industry in employer_data:
        employer, created = HostEmployer.objects.get_or_create(
            company_name=name,
            defaults={
                'contact_person': f'{name} HR',
                'contact_email': f'hr@{name.lower().replace(" ", "")}.co.za',
                'contact_phone': f'+27 11 {random.randint(100, 999)} {random.randint(1000, 9999)}',
                'physical_address': f'{random.randint(1, 100)} Main Road, Johannesburg',
                'status': 'APPROVED',
                'campus': default_campus,
            }
        )
        employers.append(employer)
        if created:
            print(f"  ✓ Created employer: {name}")
    
    # Create mentors
    mentor_names = [
        ('Patricia', 'Nkosi'), ('Thabo', 'Molefe'), ('Nomsa', 'Dlamini'),
        ('Sipho', 'Mthembu'), ('Zanele', 'Khumalo'), ('Bongani', 'Ndlovu'),
        ('Lindiwe', 'Zulu'), ('Mandla', 'Sithole'), ('Precious', 'Mokoena'),
        ('Kagiso', 'Mahlangu'),
    ]
    
    mentors = []
    for i, (first, last) in enumerate(mentor_names):
        employer = employers[i % len(employers)]
        mentor, created = HostMentor.objects.get_or_create(
            email=f'{first.lower()}.{last.lower()}@{employer.company_name.lower().replace(" ", "")}.co.za',
            defaults={
                'first_name': first,
                'last_name': last,
                'phone': f'+27 82 {random.randint(100, 999)} {random.randint(1000, 9999)}',
                'host': employer,
                'job_title': random.choice(['Senior Manager', 'Team Lead', 'Department Head', 'Supervisor']),
                'status': 'APPROVED',
            }
        )
        mentors.append(mentor)
        if created:
            print(f"  ✓ Created mentor: {first} {last}")
    
    # Create placements for enrolled learners without placements
    enrollments = Enrollment.objects.filter(
        status__in=['ACTIVE', 'ENROLLED']
    ).exclude(
        learner__in=WorkplacePlacement.objects.values_list('learner_id', flat=True)
    )
    
    placement_count = 0
    for enrollment in enrollments[:50]:  # Limit to 50 new placements
        employer = random.choice(employers)
        mentor = random.choice([m for m in mentors if m.host == employer] or mentors)
        
        # Check if placement already exists
        if WorkplacePlacement.objects.filter(learner=enrollment.learner, enrollment=enrollment).exists():
            continue
        
        try:
            placement = WorkplacePlacement.objects.create(
                learner=enrollment.learner,
                enrollment=enrollment,
                host=employer,
                mentor=mentor,
                start_date=enrollment.enrollment_date + timedelta(days=30),
                expected_end_date=enrollment.enrollment_date + timedelta(days=180),
                status='ACTIVE',
                campus=enrollment.campus or default_campus,
            )
            placement_count += 1
        except Exception as e:
            # Skip duplicates or other issues
            pass
    
    print(f"  Created {placement_count} workplace placements")
    print(f"  Total host employers: {HostEmployer.objects.count()}")
    print(f"  Total mentors: {HostMentor.objects.count()}")
    print(f"  Total placements: {WorkplacePlacement.objects.count()}")


def generate_schedules_for_cohorts():
    """Generate schedule sessions for cohorts that don't have any."""
    print("\n--- GENERATING SCHEDULE SESSIONS ---")
    
    from academics.models import Module
    from logistics.models import Venue
    
    # Get cohorts without schedule sessions (related_name is 'sessions')
    cohorts_without_sessions = Cohort.objects.annotate(
        session_count=Count('sessions')
    ).filter(session_count=0)
    
    print(f"  Cohorts without schedules: {cohorts_without_sessions.count()}")
    
    # Get all venues and facilitators
    venues = list(Venue.objects.all())
    if not venues:
        print("  No venues found - cannot create schedules")
        return
    
    facilitators = list(User.objects.filter(facilitator_profile__isnull=False))
    if not facilitators:
        print("  No facilitators found - cannot create schedules")
        return
    
    # Get all modules
    modules = list(Module.objects.all())
    if not modules:
        print("  No modules found - cannot create schedules")
        return
    
    print(f"  Available venues: {len(venues)}, facilitators: {len(facilitators)}, modules: {len(modules)}")
    
    generated = 0
    cohort_offset = 0  # Offset to vary dates per cohort
    
    for cohort in cohorts_without_sessions[:10]:  # Limit to 10 cohorts
        cohort_offset += 1  # Increment to stagger cohort schedules
        cohort_session_count = 0
        
        if not cohort.qualification:
            continue
        
        # Get modules for this qualification (or random if none)
        qual_modules = list(cohort.qualification.modules.all())
        if not qual_modules:
            qual_modules = modules[:5]  # Use first 5 modules
        
        # Get campus venue if available
        campus_venues = [v for v in venues if v.campus_id == cohort.campus_id] if cohort.campus_id else venues
        if not campus_venues:
            campus_venues = venues
        
        # Get cohort facilitator
        cohort_facilitator = cohort.facilitator or random.choice(facilitators)
        
        # Generate 10 sessions for each cohort - stagger by cohort_offset * 100 days
        start_date = (cohort.start_date or date.today()) + timedelta(days=cohort_offset * 100)
        
        for i in range(10):
            session_date = start_date + timedelta(days=i * 2)  # Every other day
            if session_date.weekday() >= 5:  # Skip weekends
                session_date += timedelta(days=2)
            
            module = random.choice(qual_modules or modules)
            venue = random.choice(campus_venues)
            
            try:
                session = ScheduleSession.objects.create(
                    cohort=cohort,
                    module=module,
                    venue=venue,
                    facilitator=cohort_facilitator,
                    date=session_date,
                    start_time=time(9, 0),
                    end_time=time(12, 0) if i % 2 == 0 else time(15, 0),
                    session_type=random.choice(['LECTURE', 'PRACTICAL', 'WORKSHOP']),
                    topic=f"Session {i+1}: {module.title[:50]}",
                )
                cohort_session_count += 1
            except Exception as e:
                # Likely unique constraint violation - try different time
                try:
                    session = ScheduleSession.objects.create(
                        cohort=cohort,
                        module=module,
                        venue=venue,
                        facilitator=cohort_facilitator,
                        date=session_date + timedelta(days=1),
                        start_time=time(13, 0),
                        end_time=time(16, 0),
                        session_type=random.choice(['LECTURE', 'PRACTICAL', 'WORKSHOP']),
                        topic=f"Session {i+1}: {module.title[:50]}",
                    )
                    cohort_session_count += 1
                except Exception:
                    pass  # Skip if still fails
        
        if cohort_session_count > 0:
            print(f"  ✓ Generated {cohort_session_count} sessions for {cohort.name}")
            generated += 1
    
    print(f"  Cohorts with new schedules: {generated}")
    print(f"  Total schedule sessions: {ScheduleSession.objects.count()}")


def main():
    print("=" * 60)
    print("PRODUCTION DATA LINKING SCRIPT")
    print("=" * 60)
    
    # 1. Create facilitator profiles
    create_facilitator_profiles()
    
    # 2. Assign facilitators to cohorts
    assign_facilitators_to_cohorts()
    
    # 3. Create implementation plans for qualifications without one
    create_implementation_plans_for_qualifications()
    
    # 4. Enroll unenrolled learners
    enroll_learners_in_cohorts()
    
    # 5. Create workplace data
    create_workplace_data()
    
    # 6. Generate schedules
    generate_schedules_for_cohorts()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Learners: {Learner.objects.count()}")
    print(f"  Enrollments: {Enrollment.objects.count()}")
    print(f"  Cohorts: {Cohort.objects.count()}")
    print(f"  Cohorts with facilitator: {Cohort.objects.filter(facilitator__isnull=False).count()}")
    print(f"  Implementation Plans: {ImplementationPlan.objects.count()}")
    print(f"  Schedule Sessions: {ScheduleSession.objects.count()}")
    print(f"  Facilitator Profiles: {FacilitatorProfile.objects.count()}")
    print(f"  Host Employers: {HostEmployer.objects.count()}")
    print(f"  Workplace Placements: {WorkplacePlacement.objects.count()}")
    print("=" * 60)
    
    print("\n" + "=" * 60)
    print("TEST CREDENTIALS (password: test1234)")
    print("=" * 60)
    for profile in FacilitatorProfile.objects.all()[:7]:
        print(f"  Facilitator: {profile.user.email}")
    print("=" * 60)


if __name__ == '__main__':
    main()
