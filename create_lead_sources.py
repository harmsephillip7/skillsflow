"""
Create default lead sources for CRM
Run with: python manage.py shell < create_lead_sources.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from crm.models import LeadSource

# Default lead sources
LEAD_SOURCES = [
    {'name': 'School Visit', 'code': 'SCHOOL_VISIT', 'description': 'Career talks and visits to high schools'},
    {'name': 'Exhibition', 'code': 'EXHIBITION', 'description': 'Education expos and career exhibitions'},
    {'name': 'Social Media', 'code': 'SOCIAL_MEDIA', 'description': 'Facebook, Instagram, TikTok, LinkedIn campaigns'},
    {'name': 'Walk-in', 'code': 'WALKIN', 'description': 'Direct campus walk-in enquiries'},
    {'name': 'Website', 'code': 'WEBSITE', 'description': 'Online form submissions from website'},
    {'name': 'WhatsApp', 'code': 'WHATSAPP', 'description': 'WhatsApp enquiries and chatbot conversations'},
    {'name': 'Referral', 'code': 'REFERRAL', 'description': 'Referred by existing learner, alumni or partner'},
    {'name': 'Radio/TV', 'code': 'RADIO_TV', 'description': 'Radio and television advertising campaigns'},
    {'name': 'Print Media', 'code': 'PRINT', 'description': 'Newspaper and magazine advertisements'},
    {'name': 'Career Fair', 'code': 'CAREER_FAIR', 'description': 'Career fairs and job expos'},
    {'name': 'Corporate Partner', 'code': 'CORPORATE', 'description': 'Referrals from corporate partners and employers'},
    {'name': 'Call Center', 'code': 'CALL_CENTER', 'description': 'Inbound calls to the call center'},
    {'name': 'Email Campaign', 'code': 'EMAIL', 'description': 'Email marketing campaigns'},
    {'name': 'Google Ads', 'code': 'GOOGLE_ADS', 'description': 'Google search and display advertising'},
    {'name': 'Alumni Network', 'code': 'ALUMNI', 'description': 'Referrals through alumni network'},
]

created_count = 0
for source_data in LEAD_SOURCES:
    source, created = LeadSource.objects.get_or_create(
        code=source_data['code'],
        defaults={
            'name': source_data['name'],
            'description': source_data['description'],
            'is_active': True
        }
    )
    if created:
        created_count += 1
        print(f"Created: {source.name}")
    else:
        print(f"Already exists: {source.name}")

print(f"\nDone! Created {created_count} new lead sources.")
