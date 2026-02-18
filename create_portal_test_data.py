"""
Create comprehensive test data for all portal testing.
This ensures the superadmin can access and test all portal pages.

Run: ./venv/bin/python create_portal_test_data.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from datetime import date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from core.models import User, FacilitatorProfile, WorkplaceOfficerProfile
from learners.models import Learner, SETA
from corporate.models import (
    HostEmployer, HostMentor, WorkplacePlacement, CorporateClient
)
from academics.models import Qualification, Enrollment, Module
from tenants.models import Brand, Campus

print("=" * 60)
print("Creating Portal Test Data")
print("=" * 60)


def get_or_create_campus():
    """Get or create a test campus."""
    campus = Campus.objects.filter(name__icontains='Johannesburg').first()
    if not campus:
        campus = Campus.objects.first()
    if not campus:
        # Create a brand and campus
        brand, _ = Brand.objects.get_or_create(
            name='Test Training Academy',
            defaults={
                'legal_name': 'Test Training Academy (Pty) Ltd',
                'is_active': True,
            }
        )
        campus = Campus.objects.create(
            brand=brand,
            name='Johannesburg Campus',
            code='JHB',
            phone='011 123 4567',
            email='jhb@test.co.za',
            physical_address='123 Test Street, Johannesburg',
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
        email='admin@skillsflow.test',
        password='admin1234',
        first_name='Admin',
        last_name='User'
    )
    print(f"✓ Created superuser: admin@skillsflow.test (password: admin1234)")
    return superuser


def create_host_employer(campus):
    """Create a test host employer."""
    host, created = HostEmployer.objects.get_or_create(
        company_name="Acme Engineering Works",
        defaults={
            'trading_name': 'Acme Engineering',
            'registration_number': '2020/123456/07',
            'contact_person': 'John Smith',
            'contact_email': 'john@acme-eng.co.za',
            'contact_phone': '011 234 5678',
            'physical_address': '45 Industrial Road, Johannesburg',
            'status': 'APPROVED',
            'campus': campus,
            'gps_latitude': Decimal('-26.2041'),
            'gps_longitude': Decimal('28.0473'),
            'geofence_radius_meters': 5000,
            'max_placement_capacity': 20,
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


def create_mentor(host, user=None):
    """Create a test mentor linked to the host employer."""
    mentor, created = HostMentor.objects.get_or_create(
        email='mentor@acme-eng.co.za',
        host=host,
        defaults={
            'first_name': 'Mike',
            'last_name': 'Johnson',
            'id_number': '8001015009087',
            'phone': '082 123 4567',
            'job_title': 'Senior Technician',
            'department': 'Engineering',
            'years_experience': 15,
            'trade': 'Electrical Engineering',
            'trade_certificate_number': 'TC-2010-12345',
            'mentor_trained': True,
            'mentor_training_date': date(2023, 1, 15),
            'max_mentees': 5,
            'current_mentees': 0,
            'user': user,
            'is_active': True,
            'status': 'APPROVED',
        }
    )
    if created:
        print(f"✓ Created mentor: {mentor.full_name}")
    else:
        print(f"✓ Mentor exists: {mentor.full_name}")
    return mentor


def create_mentor_user():
    """Create a user account for the mentor."""
    mentor_user, created = User.objects.get_or_create(
        email='mentor@acme-eng.co.za',
        defaults={
            'first_name': 'Mike',
            'last_name': 'Johnson',
            'is_active': True,
        }
    )
    if created:
        mentor_user.set_password('mentor1234')
        mentor_user.save()
        print(f"✓ Created mentor user: mentor@acme-eng.co.za (password: mentor1234)")
    else:
        print(f"✓ Mentor user exists: {mentor_user.email}")
    return mentor_user


def create_learner_user(campus):
    """Create a test learner user."""
    learner_user, created = User.objects.get_or_create(
        email='learner@skillsflow.test',
        defaults={
            'first_name': 'Sarah',
            'last_name': 'Williams',
            'is_active': True,
        }
    )
    if created:
        learner_user.set_password('learner1234')
        learner_user.save()
        print(f"✓ Created learner user: learner@skillsflow.test (password: learner1234)")
    else:
        print(f"✓ Learner user exists: {learner_user.email}")
    return learner_user


def create_learner(user, campus):
    """Create a test learner profile."""
    # Generate learner number
    from datetime import datetime
    learner_number = f"L{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Check if learner exists for this user
    existing = Learner.objects.filter(user=user).first()
    if existing:
        print(f"✓ Learner exists: {existing.first_name} {existing.last_name}")
        return existing
    
    learner = Learner.objects.create(
        user=user,
        learner_number=learner_number,
        sa_id_number='9901015800087',
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        phone_mobile='083 456 7890',
        date_of_birth=date(1999, 1, 1),
        gender='F',
        population_group='A',
        citizenship='SA',
        home_language='English',
        campus=campus,
    )
    print(f"✓ Created learner: {learner.first_name} {learner.last_name}")
    return learner


def create_qualification():
    """Create or get a test qualification."""
    qualification = Qualification.objects.first()
    if qualification:
        print(f"✓ Using qualification: {qualification.title}")
        return qualification
    
    # Create a SETA first if needed
    seta, _ = SETA.objects.get_or_create(
        code='MERSETA',
        defaults={
            'name': 'Manufacturing, Engineering and Related Services SETA',
            'is_active': True,
        }
    )
    
    qualification = Qualification.objects.create(
        title='National Certificate: Electrical Engineering',
        saqa_id='58215',
        nqf_level=4,
        credits=120,
        qualification_type='NC',
        seta=seta,
        status='ACTIVE',
    )
    print(f"✓ Created qualification: {qualification.title}")
    return qualification


def create_enrollment(learner, qualification, campus):
    """Create an enrollment for the learner."""
    from datetime import datetime
    
    # Check if enrollment exists
    existing = Enrollment.objects.filter(learner=learner, qualification=qualification).first()
    if existing:
        print(f"✓ Enrollment exists for {learner.first_name}")
        return existing
    
    enrollment_number = f"ENR{datetime.now().strftime('%Y%m%d%H%M%S')}"
    today = date.today()
    
    enrollment = Enrollment.objects.create(
        learner=learner,
        qualification=qualification,
        campus=campus,
        enrollment_number=enrollment_number,
        application_date=today - timedelta(days=100),
        enrollment_date=today - timedelta(days=90),
        start_date=today - timedelta(days=90),
        expected_completion=today + timedelta(days=275),
        status='ACTIVE',
        funding_type='LEARNERSHIP',
    )
    print(f"✓ Created enrollment for {learner.first_name}")
    return enrollment


def create_placement(learner, enrollment, host, mentor, campus):
    """Create a workplace placement."""
    # Check if placement exists
    existing = WorkplacePlacement.objects.filter(learner=learner, enrollment=enrollment, host=host).first()
    if existing:
        print(f"✓ Placement exists: {existing.placement_reference}")
        return existing
    
    # Generate unique placement reference
    from datetime import datetime as dt
    placement_ref = f"WPL-{dt.now().strftime('%Y%m%d%H%M%S')}-{learner.id}"
    
    placement = WorkplacePlacement.objects.create(
        learner=learner,
        enrollment=enrollment,
        host=host,
        mentor=mentor,
        placement_reference=placement_ref,
        start_date=date.today() - timedelta(days=30),
        expected_end_date=date.today() + timedelta(days=150),
        status='ACTIVE',
        department='Engineering',
        position='Apprentice Technician',
        campus=campus,
    )
    
    mentor.current_mentees += 1
    mentor.save()
    host.current_placements += 1
    host.save()
    print(f"✓ Created placement: {placement.placement_reference}")
    return placement


def create_corporate_client(campus):
    """Create a test corporate client."""
    client, created = CorporateClient.objects.get_or_create(
        company_name="Global Industries Ltd",
        defaults={
            'trading_name': 'Global Industries',
            'registration_number': '2019/987654/07',
            'vat_number': '4123456789',
            'phone': '011 987 6543',
            'email': 'info@globalindustries.co.za',
            'physical_address': '100 Corporate Park, Sandton',
            'industry': 'Manufacturing',
            'employee_count': 500,
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


def create_facilitator_user():
    """Create a test facilitator user."""
    facilitator, created = User.objects.get_or_create(
        email='facilitator@skillsflow.test',
        defaults={
            'first_name': 'David',
            'last_name': 'Brown',
            'is_active': True,
            'is_staff': True,
        }
    )
    if created:
        facilitator.set_password('facilitator1234')
        facilitator.save()
        print(f"✓ Created facilitator user: facilitator@skillsflow.test (password: facilitator1234)")
    else:
        print(f"✓ Facilitator user exists: {facilitator.email}")
    return facilitator


def create_workplace_officer_user():
    """Create a test workplace officer user."""
    officer, created = User.objects.get_or_create(
        email='wpo@skillsflow.test',
        defaults={
            'first_name': 'Emily',
            'last_name': 'Davis',
            'is_active': True,
            'is_staff': True,
        }
    )
    if created:
        officer.set_password('wpo1234')
        officer.save()
        print(f"✓ Created WPO user: wpo@skillsflow.test (password: wpo1234)")
    else:
        print(f"✓ WPO user exists: {officer.email}")
    return officer


@transaction.atomic
def main():
    """Main function to create all test data."""
    print("\n--- Setting up base entities ---")
    campus = get_or_create_campus()
    superuser = get_or_create_superuser()
    
    print("\n--- Creating host employer and mentor ---")
    host = create_host_employer(campus)
    mentor_user = create_mentor_user()
    mentor = create_mentor(host, mentor_user)
    
    # Link user to mentor if not already
    if not mentor.user:
        mentor.user = mentor_user
        mentor.save()
        print(f"✓ Linked mentor user to mentor profile")
    
    print("\n--- Creating learner and enrollment ---")
    learner_user = create_learner_user(campus)
    learner = create_learner(learner_user, campus)
    qualification = create_qualification()
    enrollment = create_enrollment(learner, qualification, campus)
    
    print("\n--- Creating workplace placement ---")
    placement = create_placement(learner, enrollment, host, mentor, campus)
    
    print("\n--- Creating corporate client ---")
    corporate = create_corporate_client(campus)
    
    print("\n--- Creating staff users ---")
    facilitator = create_facilitator_user()
    wpo = create_workplace_officer_user()
    
    # Assign WPO to placement
    if not placement.workplace_officer:
        placement.workplace_officer = wpo
        placement.save()
        print(f"✓ Assigned WPO to placement")
    
    print("\n--- Setting up superuser portal access ---")
    # Create FacilitatorProfile for superuser
    fac_profile, created = FacilitatorProfile.objects.get_or_create(
        user=superuser,
        defaults={'primary_campus': campus}
    )
    if created:
        fac_profile.campuses.add(campus)
        print(f"✓ Created FacilitatorProfile for superuser")
    else:
        if not fac_profile.campuses.exists():
            fac_profile.campuses.add(campus)
        print(f"✓ FacilitatorProfile exists for superuser")
    
    # Create WorkplaceOfficerProfile for superuser
    wpo_profile, created = WorkplaceOfficerProfile.objects.get_or_create(
        user=superuser,
        defaults={}
    )
    if created:
        print(f"✓ Created WorkplaceOfficerProfile for superuser")
    else:
        print(f"✓ WorkplaceOfficerProfile exists for superuser")
    
    # Create a test learner linked to superuser for student portal testing
    superuser_learner = Learner.objects.filter(user=superuser).first()
    if not superuser_learner:
        from datetime import datetime as dt
        superuser_learner = Learner.objects.create(
            user=superuser,
            learner_number=f"ADMIN{dt.now().strftime('%Y%m%d%H%M%S')}",
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
        print(f"✓ Created Learner profile for superuser (student portal)")
        
        # Create enrollment for superuser learner
        superuser_enrollment = create_enrollment(superuser_learner, qualification, campus)
        
        # Create placement for superuser
        create_placement(superuser_learner, superuser_enrollment, host, mentor, campus)
    else:
        print(f"✓ Learner profile exists for superuser")
    
    print("\n" + "=" * 60)
    print("TEST DATA CREATION COMPLETE")
    print("=" * 60)
    print("\nTest Accounts:")
    print("-" * 40)
    print(f"  Superadmin: {superuser.email}")
    print(f"  Mentor: mentor@acme-eng.co.za / mentor1234")
    print(f"  Learner: learner@skillsflow.test / learner1234")
    print(f"  Facilitator: facilitator@skillsflow.test / facilitator1234")
    print(f"  WPO: wpo@skillsflow.test / wpo1234")
    print("\nPortal URLs:")
    print("-" * 40)
    print("  /portal/student/       - Student/Learner Portal")
    print("  /portal/mentor/        - Mentor Portal")
    print("  /portal/facilitator/   - Facilitator Portal")
    print("  /portal/corporate/     - Corporate Portal")
    print("  /portal/wpo/           - Workplace Officer Portal")
    print("\nSuperadmin has access to all portals for testing.")
    print("=" * 60)


if __name__ == '__main__':
    main()
