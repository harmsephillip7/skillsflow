"""
Create CRM Test Data - Leads, Opportunities, Quotes, etc.
Run: python create_crm_test_data.py
"""
import os
import random
from datetime import date, timedelta
from decimal import Decimal

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from core.models import User
from crm.models import Lead, LeadSource, LeadActivity, Opportunity
from finance.models import Quote, QuoteLineItem, QuoteTemplate, PaymentOption
from academics.models import Qualification, QualificationPricing, SETA
from tenants.models import Campus
from intakes.models import Intake


# South African names for realistic data
FIRST_NAMES = [
    'Sipho', 'Thandi', 'Bongani', 'Nomvula', 'Mpho', 'Lerato', 'Kagiso', 'Zanele',
    'Themba', 'Palesa', 'Siyabonga', 'Nokuthula', 'Thabiso', 'Lindiwe', 'Mandla',
    'Nompumelelo', 'Sibusiso', 'Ayanda', 'Vusi', 'Nonhlanhla', 'Musa', 'Precious',
    'Nkosinathi', 'Thandiwe', 'Dumisani', 'Ntombi', 'Buhle', 'Lwazi', 'Zinhle',
    'Johannes', 'Maria', 'Pieter', 'Annika', 'Willem', 'Chantelle', 'Johann', 'Liezel',
]

LAST_NAMES = [
    'Nkosi', 'Dlamini', 'Ndlovu', 'Mthembu', 'Khumalo', 'Zulu', 'Ngcobo', 'Sithole',
    'Cele', 'Mkhize', 'Zungu', 'Molefe', 'Mokoena', 'Maseko', 'Tshabalala', 'Mahlangu',
    'Mabena', 'Shabangu', 'Motaung', 'Radebe', 'Langa', 'Buthelezi', 'Gumede', 'Ntuli',
    'van der Merwe', 'Botha', 'Pretorius', 'Joubert', 'Venter', 'du Plessis', 'Steyn',
]

PHONE_PREFIXES = ['072', '073', '074', '076', '078', '079', '082', '083', '084']

LEAD_STATUSES = ['NEW', 'CONTACTED', 'QUALIFIED', 'PROPOSAL', 'NEGOTIATION', 'REGISTERED', 'ENROLLED', 'LOST']

# Opportunity stages from Opportunity.STAGE_CHOICES
OPPORTUNITY_STAGES = ['DISCOVERY', 'QUALIFICATION', 'PROPOSAL', 'NEGOTIATION', 'COMMITTED', 'WON', 'LOST']

ACTIVITY_TYPES = ['CALL', 'EMAIL', 'SMS', 'WHATSAPP', 'MEETING', 'NOTE']

ACTIVITY_NOTES = [
    "Initial contact made. Interested in the programme.",
    "Sent programme brochure via email.",
    "Follow-up call scheduled for next week.",
    "Discussed payment options. Learner prefers monthly plan.",
    "Requested more information about course content.",
    "Confirmed interest. Ready to enroll.",
    "Left voicemail. Will try again tomorrow.",
    "WhatsApp chat - answered questions about schedule.",
    "Meeting scheduled at campus for consultation.",
    "Sent quote via email. Awaiting response.",
    "Called back - very interested, needs to discuss with employer.",
    "Submitted application form online.",
    "Requested call back after work hours.",
    "Confirmed attendance for open day.",
]


def generate_phone():
    prefix = random.choice(PHONE_PREFIXES)
    number = ''.join([str(random.randint(0, 9)) for _ in range(7)])
    return f"{prefix} {number[:3]} {number[3:]}"


def generate_email(first_name, last_name):
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'icloud.com', 'hotmail.com', 'webmail.co.za']
    return f"{first_name.lower()}.{last_name.lower().replace(' ', '')}@{random.choice(domains)}"


def create_lead_sources():
    """Create lead sources if they don't exist"""
    sources = [
        {'name': 'Website', 'code': 'WEB'},
        {'name': 'Facebook', 'code': 'FB'},
        {'name': 'Instagram', 'code': 'IG'},
        {'name': 'Google Ads', 'code': 'GADS'},
        {'name': 'Walk-in', 'code': 'WALKIN'},
        {'name': 'Referral', 'code': 'REF'},
        {'name': 'Career Fair', 'code': 'FAIR'},
        {'name': 'LinkedIn', 'code': 'LI'},
        {'name': 'SMS Campaign', 'code': 'SMS'},
        {'name': 'Email Campaign', 'code': 'EMAIL'},
    ]
    
    created = 0
    for src in sources:
        obj, was_created = LeadSource.objects.get_or_create(
            code=src['code'],
            defaults={'name': src['name'], 'is_active': True}
        )
        if was_created:
            created += 1
    
    print(f"Lead sources: {created} created, {len(sources) - created} existing")
    return LeadSource.objects.filter(is_active=True)


def create_qualifications():
    """Create test qualifications if none exist"""
    if Qualification.objects.exists():
        print(f"Qualifications: {Qualification.objects.filter(is_active=True).count()} existing")
        return
    
    # First create SETAs
    setas = [
        {'code': 'SERVICES', 'name': 'Services SETA'},
        {'code': 'MERSETA', 'name': 'Manufacturing, Engineering and Related Services SETA'},
        {'code': 'EWSETA', 'name': 'Energy and Water SETA'},
        {'code': 'BANKSETA', 'name': 'Banking Sector Education and Training Authority'},
        {'code': 'MICT', 'name': 'Media, Information and Communication Technologies SETA'},
    ]
    
    for seta_data in setas:
        SETA.objects.get_or_create(
            code=seta_data['code'],
            defaults={'name': seta_data['name'], 'is_active': True}
        )
    print(f"SETAs: {SETA.objects.count()} available")
    
    services_seta = SETA.objects.get(code='SERVICES')
    merseta = SETA.objects.get(code='MERSETA')
    mict_seta = SETA.objects.get(code='MICT')
    
    qualifications = [
        {'short_title': 'Business Administration N3', 'saqa_id': '23833', 'nqf_level': 3, 'credits': 120, 'seta': services_seta, 'qual_type': 'NC'},
        {'short_title': 'End User Computing N3', 'saqa_id': '61591', 'nqf_level': 3, 'credits': 130, 'seta': mict_seta, 'qual_type': 'NC'},
        {'short_title': 'Project Management N4', 'saqa_id': '50080', 'nqf_level': 4, 'credits': 140, 'seta': services_seta, 'qual_type': 'NC'},
        {'short_title': 'Electrical Engineering N4', 'saqa_id': '57778', 'nqf_level': 4, 'credits': 140, 'seta': merseta, 'qual_type': 'NC'},
        {'short_title': 'Mechanical Engineering N4', 'saqa_id': '49035', 'nqf_level': 4, 'credits': 140, 'seta': merseta, 'qual_type': 'NC'},
        {'short_title': 'HR Management N5', 'saqa_id': '49692', 'nqf_level': 5, 'credits': 158, 'seta': services_seta, 'qual_type': 'NC'},
        {'short_title': 'Bookkeeping N4', 'saqa_id': '58376', 'nqf_level': 4, 'credits': 140, 'seta': services_seta, 'qual_type': 'NC'},
        {'short_title': 'Information Technology N5', 'saqa_id': '48573', 'nqf_level': 5, 'credits': 131, 'seta': mict_seta, 'qual_type': 'NC'},
        {'short_title': 'Marketing N5', 'saqa_id': '59985', 'nqf_level': 5, 'credits': 140, 'seta': services_seta, 'qual_type': 'NC'},
        {'short_title': 'Safety Management N6', 'saqa_id': '36121', 'nqf_level': 6, 'credits': 240, 'seta': merseta, 'qual_type': 'ND'},
    ]
    
    created = 0
    for qual_data in qualifications:
        Qualification.objects.create(
            short_title=qual_data['short_title'],
            title=f"National Certificate: {qual_data['short_title']}",
            saqa_id=qual_data['saqa_id'],
            nqf_level=qual_data['nqf_level'],
            credits=qual_data['credits'],
            seta=qual_data['seta'],
            qualification_type=qual_data['qual_type'],
            minimum_duration_months=12,
            maximum_duration_months=24,
            registration_start=date(2020, 1, 1),
            registration_end=date(2030, 12, 31),
            last_enrollment_date=date(2028, 12, 31),
            is_active=True,
        )
        created += 1
    
    print(f"Qualifications: {created} created")


def create_qualification_pricing():
    """Add pricing to qualifications that don't have it"""
    qualifications = Qualification.objects.filter(is_active=True)
    current_year = timezone.now().year
    
    created = 0
    for qual in qualifications:
        # Check if pricing exists for current year
        if not qual.pricing_history.filter(academic_year=current_year).exists():
            # Generate a realistic price based on NQF level
            base_price = 15000 + (qual.nqf_level * 5000) + random.randint(-2000, 5000)
            
            QualificationPricing.objects.create(
                qualification=qual,
                academic_year=current_year,
                effective_from=date(current_year, 1, 1),
                total_price=Decimal(str(base_price)),
                registration_fee=Decimal('1500'),
                tuition_fee=Decimal(str(base_price - 3000)),
                materials_fee=Decimal('1500'),
                is_active=True,
            )
            created += 1
    
    print(f"Qualification pricing: {created} created for {current_year}")


def create_leads(count=50):
    """Create test leads"""
    sources = list(LeadSource.objects.filter(is_active=True))
    qualifications = list(Qualification.objects.filter(is_active=True)[:10])
    campuses = list(Campus.objects.all())
    users = list(User.objects.filter(is_active=True, is_staff=True)[:5])
    
    if not sources:
        print("No lead sources found. Creating...")
        sources = list(create_lead_sources())
    
    if not campuses:
        print("No campuses found. Skipping campus assignment.")
    
    created = 0
    for i in range(count):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        
        # Weighted status distribution
        status_weights = {
            'NEW': 20,
            'CONTACTED': 20,
            'QUALIFIED': 25,
            'PROPOSAL': 10,
            'NEGOTIATION': 5,
            'REGISTERED': 5,
            'ENROLLED': 10,
            'LOST': 5,
        }
        status = random.choices(
            list(status_weights.keys()),
            weights=list(status_weights.values())
        )[0]
        
        # Random date in last 90 days
        days_ago = random.randint(0, 90)
        created_date = timezone.now() - timedelta(days=days_ago)
        
        lead = Lead.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=generate_email(first_name, last_name),
            phone=generate_phone(),
            whatsapp_number=generate_phone(),
            source=random.choice(sources) if sources else None,
            status=status,
            qualification_interest=random.choice(qualifications) if qualifications and random.random() > 0.2 else None,
            campus=random.choice(campuses) if campuses else None,
            assigned_to=random.choice(users) if users and random.random() > 0.3 else None,
            notes=f"Test lead {i+1}. Interested in skills training." if random.random() > 0.5 else "",
        )
        
        # Override created_at
        Lead.objects.filter(pk=lead.pk).update(created_at=created_date)
        
        created += 1
    
    print(f"Leads: {created} created")
    return Lead.objects.all()


def create_lead_activities(leads):
    """Create activities for leads"""
    created = 0
    for lead in leads:
        # Random number of activities (0-5)
        num_activities = random.randint(0, 5)
        
        lead_created = lead.created_at
        for j in range(num_activities):
            # Activity date between lead creation and now
            days_since_created = (timezone.now() - lead_created).days
            if days_since_created > 0:
                activity_days_ago = random.randint(0, days_since_created)
                activity_date = timezone.now() - timedelta(days=activity_days_ago)
            else:
                activity_date = timezone.now()
            
            activity = LeadActivity.objects.create(
                lead=lead,
                activity_type=random.choice(ACTIVITY_TYPES),
                description=random.choice(ACTIVITY_NOTES),
            )
            # Update created_at after creation
            LeadActivity.objects.filter(pk=activity.pk).update(created_at=activity_date)
            created += 1
    
    print(f"Lead activities: {created} created")


def create_opportunities(leads):
    """Create opportunities from qualified leads"""
    users = list(User.objects.filter(is_active=True, is_staff=True)[:5])
    qualifications = list(Qualification.objects.filter(is_active=True)[:10])
    
    # Get leads that should have opportunities
    leads_for_opps = leads.filter(status__in=['QUALIFIED', 'PROPOSAL', 'NEGOTIATION', 'REGISTERED', 'ENROLLED'])
    
    created = 0
    for lead in leads_for_opps[:30]:  # Create opportunities for up to 30 leads
        qual = lead.qualification_interest or (random.choice(qualifications) if qualifications else None)
        
        if not qual:
            continue
        
        # Map lead status to opportunity stage
        stage_map = {
            'QUALIFIED': 'QUALIFICATION',
            'PROPOSAL': 'PROPOSAL',
            'NEGOTIATION': 'NEGOTIATION',
            'REGISTERED': 'COMMITTED',
            'ENROLLED': 'WON',
        }
        stage = stage_map.get(lead.status, 'DISCOVERY')
        
        # Probability based on stage
        probability_map = {
            'DISCOVERY': 10,
            'QUALIFICATION': 25,
            'PROPOSAL': 50,
            'NEGOTIATION': 75,
            'COMMITTED': 90,
            'WON': 100,
            'LOST': 0,
        }
        
        # Estimated value based on qualification
        pricing = qual.get_current_pricing()
        value = pricing.total_price if pricing else Decimal('25000')
        
        Opportunity.objects.create(
            lead=lead,
            name=f"{lead.first_name} {lead.last_name} - {qual.short_title}",
            qualification=qual,
            stage=stage,
            value=value,
            probability=probability_map.get(stage, 25),
            notes="Created from qualified lead.",
            campus=lead.campus,
        )
        created += 1
    
    print(f"Opportunities: {created} created")


def create_quotes(leads):
    """Create quotes for leads"""
    templates = list(QuoteTemplate.objects.filter(is_active=True))
    payment_options = list(PaymentOption.objects.filter(is_active=True))
    qualifications = list(Qualification.objects.filter(is_active=True)[:10])
    campuses = list(Campus.objects.all())
    users = list(User.objects.filter(is_active=True, is_staff=True)[:5])
    
    if not templates:
        print("No quote templates found. Quotes will be created without templates.")
    
    if not payment_options:
        print("No payment options found. Run create_quote_template_data.py first.")
        return
    
    # Get leads with qualification interest
    leads_for_quotes = leads.filter(status__in=['QUALIFIED', 'CONTACTED']).exclude(qualification_interest__isnull=True)[:25]
    
    current_year = timezone.now().year
    created = 0
    
    for lead in leads_for_quotes:
        qual = lead.qualification_interest
        pricing = qual.get_current_pricing() if qual else None
        
        if not pricing:
            continue
        
        template = random.choice(templates) if templates else None
        payment_option = random.choice(payment_options)
        campus = lead.campus or (random.choice(campuses) if campuses else None)
        
        # Random status distribution
        status_weights = {
            'DRAFT': 10,
            'SENT': 30,
            'VIEWED': 25,
            'ACCEPTED': 15,
            'REJECTED': 10,
            'EXPIRED': 10,
        }
        status = random.choices(
            list(status_weights.keys()),
            weights=list(status_weights.values())
        )[0]
        
        # Quote date in past
        days_ago = random.randint(1, 30)
        quote_date = date.today() - timedelta(days=days_ago)
        
        quote = Quote(
            campus=campus,
            lead=lead,
            template=template,
            payment_option=payment_option,
            enrollment_year='CURRENT',
            academic_year=current_year,
            payment_plan='MONTHLY',
            quote_date=quote_date,
            valid_until=quote_date + timedelta(days=2),
            status=status,
            vat_rate=Decimal('0.00'),
            terms=template.get_effective_terms() if template else "Quote valid for 48 hours.",
            created_by=random.choice(users) if users else None,
        )
        quote.save()
        
        # Create line item
        QuoteLineItem.objects.create(
            quote=quote,
            item_type='TUITION',
            description=f"{qual.short_title} - {current_year} Academic Year",
            quantity=1,
            original_unit_price=pricing.total_price,
            unit_price=pricing.total_price,
            academic_year=current_year,
            qualification=qual,
        )
        
        # Calculate totals
        quote.calculate_totals()
        
        # Set status timestamps
        if status in ['SENT', 'VIEWED', 'ACCEPTED', 'REJECTED', 'EXPIRED']:
            quote.sent_at = timezone.now() - timedelta(days=days_ago - 1)
        if status in ['VIEWED', 'ACCEPTED', 'REJECTED']:
            quote.viewed_at = timezone.now() - timedelta(days=days_ago - 1, hours=random.randint(1, 12))
        if status == 'ACCEPTED':
            quote.accepted_at = timezone.now() - timedelta(days=random.randint(0, days_ago - 1))
        if status == 'REJECTED':
            quote.rejected_at = timezone.now() - timedelta(days=random.randint(0, days_ago - 1))
        
        quote.save()
        created += 1
    
    print(f"Quotes: {created} created")


def main():
    print("\n" + "=" * 50)
    print("Creating CRM Test Data")
    print("=" * 50 + "\n")
    
    # Create supporting data
    create_lead_sources()
    create_qualifications()
    create_qualification_pricing()
    
    # Create main CRM data
    print("\n--- Creating Leads ---")
    leads = create_leads(50)
    
    print("\n--- Creating Lead Activities ---")
    create_lead_activities(leads)
    
    print("\n--- Creating Opportunities ---")
    create_opportunities(leads)
    
    print("\n--- Creating Quotes ---")
    create_quotes(leads)
    
    # Summary
    print("\n" + "=" * 50)
    print("CRM Test Data Summary")
    print("=" * 50)
    print(f"Total Leads: {Lead.objects.count()}")
    print(f"  - NEW: {Lead.objects.filter(status='NEW').count()}")
    print(f"  - CONTACTED: {Lead.objects.filter(status='CONTACTED').count()}")
    print(f"  - QUALIFIED: {Lead.objects.filter(status='QUALIFIED').count()}")
    print(f"  - PROPOSAL: {Lead.objects.filter(status='PROPOSAL').count()}")
    print(f"  - REGISTERED: {Lead.objects.filter(status='REGISTERED').count()}")
    print(f"  - ENROLLED: {Lead.objects.filter(status='ENROLLED').count()}")
    print(f"  - LOST: {Lead.objects.filter(status='LOST').count()}")
    print(f"Total Lead Activities: {LeadActivity.objects.count()}")
    print(f"Total Opportunities: {Opportunity.objects.count()}")
    print(f"Total Quotes: {Quote.objects.count()}")
    print(f"  - DRAFT: {Quote.objects.filter(status='DRAFT').count()}")
    print(f"  - SENT: {Quote.objects.filter(status='SENT').count()}")
    print(f"  - VIEWED: {Quote.objects.filter(status='VIEWED').count()}")
    print(f"  - ACCEPTED: {Quote.objects.filter(status='ACCEPTED').count()}")
    print(f"  - REJECTED: {Quote.objects.filter(status='REJECTED').count()}")
    print("=" * 50)
    print("\n✅ CRM test data created successfully!")


if __name__ == '__main__':
    main()
