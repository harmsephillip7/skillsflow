"""
Create comprehensive project test data with:
- Qualification with modules
- Implementation Plan with phases
- TrainingNotification (Project)
- Cohort with CohortImplementationPlan
- NOTIntake linking
- Stakeholders (Facilitator, Assessor, etc.)
- Learners with Enrollments
- Full data flow through all portals

Run: ./venv/bin/python create_project_test_data.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from core.models import (
    User, FacilitatorProfile, WorkplaceOfficerProfile, 
    TrainingNotification, NOTIntake, NOTStakeholder
)
from learners.models import Learner, SETA
from corporate.models import (
    HostEmployer, HostMentor, WorkplacePlacement, CorporateClient
)
from academics.models import (
    Qualification, Enrollment, Module, 
    ImplementationPlan, ImplementationPhase, ImplementationModuleSlot
)
from logistics.models import Cohort, CohortImplementationPlan, CohortImplementationPhase
from tenants.models import Brand, Campus

print("=" * 70)
print("Creating Comprehensive Project Test Data")
print("=" * 70)


def get_or_create_campus():
    """Get or create a test campus."""
    campus = Campus.objects.filter(name__icontains='Johannesburg').first()
    if not campus:
        campus = Campus.objects.first()
    if not campus:
        brand, _ = Brand.objects.get_or_create(
            name='SkillsFlow Training Academy',
            defaults={
                'legal_name': 'SkillsFlow Training Academy (Pty) Ltd',
                'is_active': True,
            }
        )
        campus = Campus.objects.create(
            brand=brand,
            name='Johannesburg Main Campus',
            code='JHB-MAIN',
            phone='011 123 4567',
            email='jhb@skillsflow.co.za',
            physical_address='100 Skills Avenue, Johannesburg',
        )
        print(f"✓ Created campus: {campus.name}")
    else:
        print(f"✓ Using campus: {campus.name}")
    return campus


def get_or_create_superuser():
    """Ensure superuser exists."""
    superuser = User.objects.filter(is_superuser=True).first()
    if superuser:
        print(f"✓ Superuser exists: {superuser.email}")
        return superuser
    
    superuser = User.objects.create_superuser(
        email='admin@skillsflow.co.za',
        password='admin1234',
        first_name='Admin',
        last_name='User'
    )
    print(f"✓ Created superuser: admin@skillsflow.co.za (password: admin1234)")
    return superuser


def create_seta():
    """Create or get MERSETA."""
    seta, created = SETA.objects.get_or_create(
        code='MERSETA',
        defaults={
            'name': 'Manufacturing, Engineering and Related Services SETA',
            'is_active': True,
        }
    )
    if created:
        print(f"✓ Created SETA: {seta.name}")
    else:
        print(f"✓ SETA exists: {seta.code}")
    return seta


def create_qualification_with_modules(seta):
    """Create a qualification with full module structure."""
    # Check if qualification exists
    qual = Qualification.objects.filter(saqa_id='91761').first()
    if qual:
        print(f"✓ Qualification exists: {qual.title}")
        return qual
    
    today = date.today()
    qual = Qualification.objects.create(
        title='Occupational Certificate: Electrician',
        short_title='OC: Electrician',
        saqa_id='91761',
        nqf_level=4,
        credits=360,
        qualification_type='OC',
        seta=seta,
        is_active=True,
        minimum_duration_months=36,
        maximum_duration_months=48,
        registration_start=today - timedelta(days=365),
        registration_end=today + timedelta(days=365 * 5),
        last_enrollment_date=today + timedelta(days=365 * 4),
        qcto_code='OC-ELEC-91761',
    )
    print(f"✓ Created qualification: {qual.title}")
    
    # Create modules - Knowledge Modules (code, title, desc, year, credits, notional_hours)
    knowledge_modules = [
        ('KM-01', 'Electrical Fundamentals', 'Year 1 knowledge module', 1, 15, 150),
        ('KM-02', 'Circuit Analysis', 'Year 1 knowledge module', 1, 15, 150),
        ('KM-03', 'Electrical Safety', 'Year 1 knowledge module', 1, 10, 100),
        ('KM-04', 'Wiring Regulations', 'Year 2 knowledge module', 2, 15, 150),
        ('KM-05', 'Motor Control Systems', 'Year 2 knowledge module', 2, 20, 200),
        ('KM-06', 'PLC Fundamentals', 'Year 3 knowledge module', 3, 15, 150),
    ]
    
    for code, title, desc, year, credits, notional_hours in knowledge_modules:
        Module.objects.get_or_create(
            qualification=qual,
            code=code,
            defaults={
                'title': title,
                'description': desc,
                'year_level': year,
                'credits': credits,
                'notional_hours': notional_hours,
                'module_type': 'K',  # K for Knowledge
                'is_active': True,
            }
        )
    print(f"  ✓ Created {len(knowledge_modules)} knowledge modules")
    
    # Create modules - Practical Modules
    practical_modules = [
        ('PM-01', 'Basic Wiring Installation', 'Year 1 practical', 1, 20, 200),
        ('PM-02', 'Distribution Board Assembly', 'Year 1 practical', 1, 20, 200),
        ('PM-03', 'Motor Installation', 'Year 2 practical', 2, 25, 250),
        ('PM-04', 'Industrial Wiring', 'Year 2 practical', 2, 25, 250),
        ('PM-05', 'Fault Finding', 'Year 3 practical', 3, 30, 300),
    ]
    
    for code, title, desc, year, credits, notional_hours in practical_modules:
        Module.objects.get_or_create(
            qualification=qual,
            code=code,
            defaults={
                'title': title,
                'description': desc,
                'year_level': year,
                'credits': credits,
                'notional_hours': notional_hours,
                'module_type': 'P',  # P for Practical
                'is_active': True,
            }
        )
    print(f"  ✓ Created {len(practical_modules)} practical modules")
    
    # Create modules - Workplace Modules
    workplace_modules = [
        ('WM-01', 'Workplace Safety Orientation', 'Year 1 workplace', 1, 10, 100),
        ('WM-02', 'Supervised Installation Practice', 'Year 1 workplace', 1, 25, 250),
        ('WM-03', 'Independent Wiring Tasks', 'Year 2 workplace', 2, 35, 350),
        ('WM-04', 'Advanced Industrial Work', 'Year 3 workplace', 3, 40, 400),
    ]
    
    for code, title, desc, year, credits, notional_hours in workplace_modules:
        Module.objects.get_or_create(
            qualification=qual,
            code=code,
            defaults={
                'title': title,
                'description': desc,
                'year_level': year,
                'credits': credits,
                'notional_hours': notional_hours,
                'module_type': 'W',  # W for Workplace
                'is_active': True,
            }
        )
    print(f"  ✓ Created {len(workplace_modules)} workplace modules")
    
    return qual


def create_implementation_plan(qualification, user):
    """Create implementation plan with phases for the qualification."""
    # Check if plan exists
    plan = ImplementationPlan.objects.filter(
        qualification=qualification, 
        is_default=True
    ).first()
    
    if plan:
        print(f"✓ Implementation plan exists: {plan.name}")
        return plan
    
    plan = ImplementationPlan.objects.create(
        qualification=qualification,
        name='3-Year Full-Time Apprenticeship',
        description='Standard 3-year apprenticeship with alternating institutional and workplace phases',
        delivery_mode='FULL_TIME',
        total_weeks=156,  # 3 years
        contact_days_per_week=5,
        hours_per_day=6,
        classroom_hours_per_day=2,
        practical_hours_per_day=4,
        is_default=True,
        status='ACTIVE',
        version='1.0',
        effective_from=date.today(),
        created_by=user,
    )
    print(f"✓ Created implementation plan: {plan.name}")
    
    # Get modules by type
    knowledge_modules = list(Module.objects.filter(
        qualification=qualification, 
        module_type='KNOWLEDGE'
    ).order_by('year_level', 'code'))
    
    practical_modules = list(Module.objects.filter(
        qualification=qualification, 
        module_type='PRACTICAL'
    ).order_by('year_level', 'code'))
    
    # Create phases
    phases_data = [
        # Year 1
        ('INDUCTION', 'Orientation & Safety', 1, 2, 1, 'purple'),
        ('INSTITUTIONAL', 'Year 1 - Knowledge Block 1', 2, 6, 1, 'blue'),
        ('INSTITUTIONAL', 'Year 1 - Practical Block 1', 3, 4, 1, 'blue'),
        ('WORKPLACE', 'Year 1 - Workplace Stint 1', 4, 12, 1, 'orange'),
        ('INSTITUTIONAL', 'Year 1 - Knowledge Block 2', 5, 6, 1, 'blue'),
        ('INSTITUTIONAL', 'Year 1 - Practical Block 2', 6, 4, 1, 'blue'),
        ('WORKPLACE', 'Year 1 - Workplace Stint 2', 7, 18, 1, 'orange'),
        
        # Year 2
        ('INSTITUTIONAL', 'Year 2 - Knowledge Block 1', 8, 6, 2, 'blue'),
        ('INSTITUTIONAL', 'Year 2 - Practical Block 1', 9, 6, 2, 'blue'),
        ('WORKPLACE', 'Year 2 - Workplace Stint 1', 10, 16, 2, 'orange'),
        ('INSTITUTIONAL', 'Year 2 - Knowledge Block 2', 11, 4, 2, 'blue'),
        ('WORKPLACE', 'Year 2 - Workplace Stint 2', 12, 20, 2, 'orange'),
        
        # Year 3
        ('INSTITUTIONAL', 'Year 3 - Advanced Knowledge', 13, 6, 3, 'blue'),
        ('INSTITUTIONAL', 'Year 3 - Advanced Practical', 14, 6, 3, 'blue'),
        ('WORKPLACE', 'Year 3 - Workplace Stint', 15, 26, 3, 'orange'),
        ('ASSESSMENT', 'Integration & Trade Test Prep', 16, 4, 3, 'purple'),
        ('TRADE_TEST', 'Trade Test', 17, 2, 3, 'amber'),
    ]
    
    km_idx = 0
    pm_idx = 0
    
    for phase_type, name, seq, weeks, year, color in phases_data:
        phase = ImplementationPhase.objects.create(
            implementation_plan=plan,
            phase_type=phase_type,
            name=name,
            sequence=seq,
            duration_weeks=weeks,
            year_level=year,
            color=color,
            created_by=user,
        )
        
        # Add module slots for institutional phases
        if phase_type == 'INSTITUTIONAL':
            slot_seq = 1
            
            # Add knowledge modules
            if 'Knowledge' in name and km_idx < len(knowledge_modules):
                modules_to_add = min(2, len(knowledge_modules) - km_idx)
                for i in range(modules_to_add):
                    ImplementationModuleSlot.objects.create(
                        phase=phase,
                        module=knowledge_modules[km_idx],
                        sequence=slot_seq,
                        classroom_sessions=weeks * 5,  # One per day
                        practical_sessions=0,
                        total_days=weeks * 5,
                    )
                    km_idx += 1
                    slot_seq += 1
            
            # Add practical modules
            if 'Practical' in name and pm_idx < len(practical_modules):
                ImplementationModuleSlot.objects.create(
                    phase=phase,
                    module=practical_modules[pm_idx],
                    sequence=slot_seq,
                    classroom_sessions=0,
                    practical_sessions=weeks * 5,
                    total_days=weeks * 5,
                )
                pm_idx += 1
    
    print(f"  ✓ Created {len(phases_data)} implementation phases")
    return plan


def create_facilitator(campus, user):
    """Create facilitator user and profile."""
    facilitator, created = User.objects.get_or_create(
        email='facilitator@skillsflow.co.za',
        defaults={
            'first_name': 'John',
            'last_name': 'Smith',
            'is_active': True,
            'is_staff': True,
        }
    )
    if created:
        facilitator.set_password('facilitator1234')
        facilitator.save()
        print(f"✓ Created facilitator user: {facilitator.email}")
    else:
        print(f"✓ Facilitator user exists: {facilitator.email}")
    
    # Create facilitator profile
    profile, _ = FacilitatorProfile.objects.get_or_create(
        user=facilitator,
        defaults={'primary_campus': campus}
    )
    if not profile.campuses.exists():
        profile.campuses.add(campus)
    
    return facilitator


def create_assessor(campus):
    """Create assessor user."""
    assessor, created = User.objects.get_or_create(
        email='assessor@skillsflow.co.za',
        defaults={
            'first_name': 'Mary',
            'last_name': 'Jones',
            'is_active': True,
            'is_staff': True,
        }
    )
    if created:
        assessor.set_password('assessor1234')
        assessor.save()
        print(f"✓ Created assessor user: {assessor.email}")
    else:
        print(f"✓ Assessor user exists: {assessor.email}")
    return assessor


def create_corporate_client(campus):
    """Create corporate client for the project."""
    client, created = CorporateClient.objects.get_or_create(
        company_name="Eskom Holdings SOC",
        defaults={
            'trading_name': 'Eskom',
            'registration_number': '2002/015527/06',
            'vat_number': '4740101508',
            'phone': '011 800 8111',
            'email': 'training@eskom.co.za',
            'physical_address': 'Megawatt Park, Maxwell Drive, Sunninghill',
            'industry': 'Energy & Utilities',
            'employee_count': 40000,
            'status': 'ACTIVE',
            'client_tier': 'KEY',
            'campus': campus,
        }
    )
    if created:
        print(f"✓ Created corporate client: {client.company_name}")
    else:
        print(f"✓ Corporate client exists: {client.company_name}")
    return client


def create_host_employer(campus):
    """Create host employer for workplace placements."""
    host, created = HostEmployer.objects.get_or_create(
        company_name="Eskom Distribution - Gauteng",
        defaults={
            'trading_name': 'Eskom Gauteng',
            'registration_number': '2002/015527/06',
            'contact_person': 'Peter Nkosi',
            'contact_email': 'peter.nkosi@eskom.co.za',
            'contact_phone': '011 800 2000',
            'physical_address': 'Megawatt Park, Maxwell Drive, Sunninghill',
            'status': 'APPROVED',
            'campus': campus,
            'gps_latitude': Decimal('-26.0324'),
            'gps_longitude': Decimal('28.0610'),
            'geofence_radius_meters': 5000,
            'max_placement_capacity': 50,
            'has_workshop': True,
            'has_training_room': True,
            'safety_requirements_met': True,
        }
    )
    if created:
        print(f"✓ Created host employer: {host.company_name}")
    else:
        print(f"✓ Host employer exists: {host.company_name}")
    return host


def create_mentor(host):
    """Create mentor at the host employer."""
    mentor_user, created = User.objects.get_or_create(
        email='mentor@eskom.co.za',
        defaults={
            'first_name': 'Thabo',
            'last_name': 'Molefe',
            'is_active': True,
        }
    )
    if created:
        mentor_user.set_password('mentor1234')
        mentor_user.save()
        print(f"✓ Created mentor user: {mentor_user.email}")
    
    mentor, created = HostMentor.objects.get_or_create(
        email='mentor@eskom.co.za',
        host=host,
        defaults={
            'first_name': 'Thabo',
            'last_name': 'Molefe',
            'id_number': '7805155800087',
            'phone': '082 456 7890',
            'job_title': 'Senior Artisan - Electrical',
            'department': 'Technical Services',
            'years_experience': 20,
            'trade': 'Electrician',
            'trade_certificate_number': 'TC-2005-78901',
            'mentor_trained': True,
            'mentor_training_date': date(2022, 6, 15),
            'max_mentees': 8,
            'current_mentees': 0,
            'user': mentor_user,
            'is_active': True,
            'status': 'APPROVED',
        }
    )
    if created:
        print(f"✓ Created mentor: {mentor.full_name}")
    else:
        print(f"✓ Mentor exists: {mentor.full_name}")
    return mentor


def create_training_notification(qualification, client, campus, facilitator, assessor, user):
    """Create the training notification (project)."""
    # Check if project exists
    project = TrainingNotification.objects.filter(
        title__icontains='Eskom Electrician'
    ).first()
    
    if project:
        print(f"✓ Project exists: {project.title}")
        return project
    
    # Generate reference number
    from datetime import datetime
    ref_num = f"NOT-{datetime.now().strftime('%Y%m')}-0001"
    
    # Check for unique reference
    counter = 1
    while TrainingNotification.objects.filter(reference_number=ref_num).exists():
        counter += 1
        ref_num = f"NOT-{datetime.now().strftime('%Y%m')}-{counter:04d}"
    
    start_date = date.today() + timedelta(days=30)
    end_date = start_date + timedelta(days=365 * 3)  # 3 years
    
    project = TrainingNotification.objects.create(
        reference_number=ref_num,
        title='Eskom Electrician Apprenticeship Programme 2026',
        project_type='OC_APPRENTICESHIP',
        funder='CORPORATE_DG',
        billing_schedule='MONTHLY',
        auto_generate_invoices=True,
        description='3-year apprenticeship programme for Eskom electrical technicians. Includes institutional training at SkillsFlow Academy and workplace learning at Eskom facilities.',
        status='APPROVED',
        priority='HIGH',
        client_name='Eskom Holdings SOC',
        corporate_client=client,
        contract_value=Decimal('12500000.00'),  # R12.5M
        facilitator=facilitator,
        assessor=assessor,
        qualification=qualification,
        program_description='Full OC: Electrician qualification including all knowledge, practical, and workplace modules over 3 years.',
        expected_learner_count=25,
        learner_source='CLIENT_PROVIDED',
        recruitment_notes='Learners selected from Eskom internal development programme.',
        planned_start_date=start_date,
        planned_end_date=end_date,
        duration_months=36,
        delivery_campus=campus,
        delivery_mode='ON_CAMPUS',
        created_by=user,
    )
    print(f"✓ Created project: {project.title}")
    print(f"  Reference: {project.reference_number}")
    print(f"  Value: R{project.contract_value:,.2f}")
    
    return project


def create_cohort(qualification, campus, facilitator, project, user):
    """Create cohort for the project."""
    start_date = project.planned_start_date or (date.today() + timedelta(days=30))
    
    # Generate cohort code
    code = f"{qualification.saqa_id}-{start_date.year}{start_date.strftime('%m')}-01"
    
    cohort = Cohort.objects.filter(code=code).first()
    if cohort:
        print(f"✓ Cohort exists: {cohort.code}")
        return cohort
    
    cohort = Cohort.objects.create(
        code=code,
        name=f"{qualification.short_title} - Eskom 2026",
        qualification=qualification,
        campus=campus,
        start_date=start_date,
        end_date=project.planned_end_date or (start_date + timedelta(days=1095)),
        max_capacity=30,
        current_count=0,
        status='PLANNED',
        facilitator=facilitator,
        description=f'Cohort for {project.title}',
    )
    print(f"✓ Created cohort: {cohort.code}")
    return cohort


def create_not_intake(project, cohort, user):
    """Create NOT intake linking project to cohort."""
    intake = NOTIntake.objects.filter(
        training_notification=project, 
        intake_number=1
    ).first()
    
    if intake:
        print(f"✓ NOT Intake exists: {intake}")
        if not intake.cohort:
            intake.cohort = cohort
            intake.save()
        return intake
    
    intake = NOTIntake.objects.create(
        training_notification=project,
        intake_number=1,
        name='Main Intake - 2026',
        original_cohort_size=project.expected_learner_count,
        status='PLANNED',
        intake_date=project.planned_start_date,
        cohort=cohort,
        notes='Primary intake for Eskom apprenticeship programme.',
        created_by=user,
    )
    print(f"✓ Created NOT Intake: {intake}")
    return intake


def create_cohort_implementation_plan(cohort, implementation_plan, user):
    """Create cohort implementation plan from template."""
    if hasattr(cohort, 'implementation_plan') and cohort.implementation_plan:
        print(f"✓ Cohort implementation plan exists")
        return cohort.implementation_plan
    
    # Use the template's copy_to_cohort method
    cohort_plan = implementation_plan.copy_to_cohort(cohort, user)
    print(f"✓ Created cohort implementation plan: {cohort_plan.name}")
    print(f"  Phases: {cohort_plan.phases.count()}")
    return cohort_plan


def create_stakeholders(project, facilitator, assessor, user):
    """Create project stakeholders."""
    stakeholders_created = 0
    
    # Facilitator stakeholder
    _, created = NOTStakeholder.objects.get_or_create(
        training_notification=project,
        user=facilitator,
        role_in_project='FACILITATOR',
        defaults={
            'department': 'ACADEMIC',
            'responsibilities': 'Primary facilitator for institutional training',
            'created_by': user,
        }
    )
    if created:
        stakeholders_created += 1
    
    # Assessor stakeholder
    _, created = NOTStakeholder.objects.get_or_create(
        training_notification=project,
        user=assessor,
        role_in_project='ASSESSOR',
        defaults={
            'department': 'ACADEMIC',
            'responsibilities': 'Primary assessor for all assessments',
            'created_by': user,
        }
    )
    if created:
        stakeholders_created += 1
    
    # Admin stakeholder
    _, created = NOTStakeholder.objects.get_or_create(
        training_notification=project,
        user=user,
        role_in_project='PROJECT_MANAGER',
        defaults={
            'department': 'EXECUTIVE',
            'responsibilities': 'Overall project management',
            'created_by': user,
        }
    )
    if created:
        stakeholders_created += 1
    
    print(f"✓ Created {stakeholders_created} stakeholders")


def create_test_learners(qualification, cohort, campus, host, mentor, user, count=10):
    """Create test learners with enrollments."""
    from datetime import datetime
    
    learners_created = 0
    enrollments_created = 0
    placements_created = 0
    
    first_names = ['Sipho', 'Thandi', 'Bongani', 'Nomvula', 'Kagiso', 
                   'Lindiwe', 'Teboho', 'Naledi', 'Mpho', 'Lerato',
                   'Tshepo', 'Palesa', 'Kabelo', 'Dineo', 'Tumelo']
    last_names = ['Mokoena', 'Dlamini', 'Nkosi', 'Zulu', 'Mthembu',
                  'Ndlovu', 'Khumalo', 'Sithole', 'Mahlangu', 'Moloi']
    
    for i in range(count):
        email = f"learner{i+1}@eskom-training.co.za"
        
        # Check if learner already exists
        existing_learner = Learner.objects.filter(email=email).first()
        if existing_learner:
            continue
        
        # Create user
        learner_user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_names[i % len(first_names)],
                'last_name': last_names[i % len(last_names)],
                'is_active': True,
            }
        )
        learner_user.set_password('learner1234')
        learner_user.save()
        
        # Generate ID number (fake but valid format)
        birth_year = 1998 + (i % 5)
        birth_month = (i % 12) + 1
        id_number = f"{birth_year % 100:02d}{birth_month:02d}015{800 + i:04d}87"
        
        # Create learner
        learner_number = f"L{datetime.now().strftime('%Y%m%d')}{i+1:03d}"
        
        learner = Learner.objects.create(
            user=learner_user,
            learner_number=learner_number,
            sa_id_number=id_number,
            first_name=first_names[i % len(first_names)],
            last_name=last_names[i % len(last_names)],
            email=email,
            phone_mobile=f"08{i+1:01d} {400 + i:03d} {1000 + i:04d}",
            date_of_birth=date(birth_year, birth_month, 15),
            gender='M' if i % 2 == 0 else 'F',
            population_group='A',
            citizenship='SA',
            home_language='Sesotho' if i % 3 == 0 else ('isiZulu' if i % 3 == 1 else 'English'),
            campus=campus,
        )
        learners_created += 1
        
        # Create enrollment
        enrollment_number = f"ENR{datetime.now().strftime('%Y%m%d')}{i+1:03d}"
        start_date = cohort.start_date
        
        enrollment = Enrollment.objects.create(
            learner=learner,
            qualification=qualification,
            cohort=cohort,
            campus=campus,
            enrollment_number=enrollment_number,
            application_date=date.today() - timedelta(days=60),
            enrollment_date=date.today() - timedelta(days=30),
            start_date=start_date,
            expected_completion=cohort.end_date,
            status='ENROLLED',
            funding_type='LEARNERSHIP',
            funding_source='Eskom/MERSETA DG',
        )
        enrollments_created += 1
        
        # Create workplace placement
        placement_ref = f"WPL-{datetime.now().strftime('%Y%m%d')}-{i+1:03d}"
        
        placement = WorkplacePlacement.objects.create(
            learner=learner,
            enrollment=enrollment,
            host=host,
            mentor=mentor,
            placement_reference=placement_ref,
            start_date=start_date + timedelta(weeks=12),  # After first institutional phase
            expected_end_date=cohort.end_date - timedelta(weeks=6),
            status='PLANNED',
            department='Technical Services',
            position='Apprentice Electrician',
            campus=campus,
        )
        placements_created += 1
    
    # Update cohort count
    cohort.current_count = cohort.enrollments.filter(status__in=['ENROLLED', 'ACTIVE']).count()
    cohort.save()
    
    # Update mentor count
    mentor.current_mentees = placements_created
    mentor.save()
    
    # Update host count
    host.current_placements = placements_created
    host.save()
    
    print(f"✓ Created {learners_created} learners")
    print(f"✓ Created {enrollments_created} enrollments")
    print(f"✓ Created {placements_created} workplace placements")


def setup_superuser_profiles(superuser, campus, qualification, cohort, host, mentor):
    """Set up superuser with all profiles for portal testing."""
    # FacilitatorProfile
    fac_profile, created = FacilitatorProfile.objects.get_or_create(
        user=superuser,
        defaults={'primary_campus': campus}
    )
    if not fac_profile.campuses.exists():
        fac_profile.campuses.add(campus)
    if created:
        print(f"✓ Created FacilitatorProfile for superuser")
    
    # WorkplaceOfficerProfile
    wpo_profile, created = WorkplaceOfficerProfile.objects.get_or_create(
        user=superuser,
        defaults={}
    )
    if created:
        print(f"✓ Created WorkplaceOfficerProfile for superuser")
    
    # Learner profile for student portal
    learner = Learner.objects.filter(user=superuser).first()
    if not learner:
        from datetime import datetime
        learner = Learner.objects.create(
            user=superuser,
            learner_number=f"ADMIN{datetime.now().strftime('%Y%m%d%H%M%S')}",
            sa_id_number='8501015800087',
            first_name=superuser.first_name or 'Admin',
            last_name=superuser.last_name or 'User',
            email=superuser.email,
            phone_mobile='082 000 0000',
            date_of_birth=date(1985, 1, 1),
            gender='M',
            population_group='A',
            citizenship='SA',
            home_language='English',
            campus=campus,
        )
        print(f"✓ Created Learner profile for superuser")
        
        # Create enrollment
        from datetime import datetime as dt
        enrollment = Enrollment.objects.create(
            learner=learner,
            qualification=qualification,
            cohort=cohort,
            campus=campus,
            enrollment_number=f"ADM{dt.now().strftime('%Y%m%d%H%M%S')}",
            application_date=date.today() - timedelta(days=30),
            enrollment_date=date.today() - timedelta(days=15),
            start_date=cohort.start_date,
            expected_completion=cohort.end_date,
            status='ACTIVE',
            funding_type='SELF',
        )
        print(f"✓ Created enrollment for superuser")
        
        # Create placement
        placement = WorkplacePlacement.objects.create(
            learner=learner,
            enrollment=enrollment,
            host=host,
            mentor=mentor,
            placement_reference=f"ADM-WPL-{dt.now().strftime('%Y%m%d%H%M%S')}",
            start_date=date.today(),
            expected_end_date=cohort.end_date - timedelta(days=30),
            status='ACTIVE',
            department='Technical Services',
            position='Administrator Testing',
            campus=campus,
        )
        print(f"✓ Created placement for superuser")


@transaction.atomic
def main():
    """Main function to create all test data."""
    print("\n--- Phase 1: Base Setup ---")
    campus = get_or_create_campus()
    superuser = get_or_create_superuser()
    seta = create_seta()
    
    print("\n--- Phase 2: Academic Setup ---")
    qualification = create_qualification_with_modules(seta)
    implementation_plan = create_implementation_plan(qualification, superuser)
    
    print("\n--- Phase 3: Staff Setup ---")
    facilitator = create_facilitator(campus, superuser)
    assessor = create_assessor(campus)
    
    print("\n--- Phase 4: Corporate & Workplace Setup ---")
    client = create_corporate_client(campus)
    host = create_host_employer(campus)
    mentor = create_mentor(host)
    
    print("\n--- Phase 5: Project Setup ---")
    project = create_training_notification(
        qualification, client, campus, facilitator, assessor, superuser
    )
    create_stakeholders(project, facilitator, assessor, superuser)
    
    print("\n--- Phase 6: Cohort & Implementation ---")
    cohort = create_cohort(qualification, campus, facilitator, project, superuser)
    intake = create_not_intake(project, cohort, superuser)
    cohort_plan = create_cohort_implementation_plan(cohort, implementation_plan, superuser)
    
    print("\n--- Phase 7: Learner Setup ---")
    create_test_learners(qualification, cohort, campus, host, mentor, superuser, count=15)
    
    print("\n--- Phase 8: Superuser Portal Access ---")
    setup_superuser_profiles(superuser, campus, qualification, cohort, host, mentor)
    
    print("\n" + "=" * 70)
    print("PROJECT TEST DATA CREATION COMPLETE")
    print("=" * 70)
    
    print("\n📋 PROJECT SUMMARY")
    print("-" * 50)
    print(f"  Project: {project.title}")
    print(f"  Reference: {project.reference_number}")
    print(f"  Client: {client.company_name}")
    print(f"  Qualification: {qualification.title}")
    print(f"  Duration: {project.duration_months} months")
    print(f"  Value: R{project.contract_value:,.2f}")
    
    print("\n📚 COHORT SUMMARY")
    print("-" * 50)
    print(f"  Cohort: {cohort.code}")
    print(f"  Start: {cohort.start_date}")
    print(f"  End: {cohort.end_date}")
    print(f"  Learners: {cohort.current_count}")
    if hasattr(cohort, 'implementation_plan'):
        print(f"  Implementation Phases: {cohort.implementation_plan.phases.count()}")
    
    print("\n👥 TEST ACCOUNTS")
    print("-" * 50)
    print(f"  Superadmin: {superuser.email}")
    print(f"  Facilitator: facilitator@skillsflow.co.za / facilitator1234")
    print(f"  Assessor: assessor@skillsflow.co.za / assessor1234")
    print(f"  Mentor: mentor@eskom.co.za / mentor1234")
    print(f"  Learners: learner1@eskom-training.co.za - learner15@eskom-training.co.za / learner1234")
    
    print("\n🌐 PORTAL URLS")
    print("-" * 50)
    print("  /portal/student/       - Student Portal")
    print("  /portal/mentor/        - Mentor Portal")
    print("  /portal/facilitator/   - Facilitator Portal")
    print("  /portal/corporate/     - Corporate Portal")
    print("  /portal/wpo/           - Workplace Officer Portal")
    print("  /portal/staff/         - Staff Portal")
    
    print("\n📊 ADMIN URLS")
    print("-" * 50)
    print("  /dashboard/            - Main Dashboard")
    print("  /not/                  - Projects (Training Notifications)")
    print("  /cohorts/              - Cohorts")
    print("  /learners/             - Learners")
    print("  /academics/            - Qualifications & Implementation Plans")
    
    print("\n✅ Superadmin has access to ALL portals for testing.")
    print("=" * 70)


if __name__ == '__main__':
    main()
