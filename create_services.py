#!/usr/bin/env python
"""Create service categories and offerings for corporate clients."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from corporate.models import ServiceCategory, ServiceOffering

# Create Service Categories
categories_data = [
    {'name': 'Skills Development', 'code': 'SKILLS', 'description': 'Skills development services including WSP/ATR submissions', 'display_order': 1, 'icon': 'book-open', 'color': '#1a56db'},
    {'name': 'Employment Equity', 'code': 'EE', 'description': 'Employment Equity consulting and compliance', 'display_order': 2, 'icon': 'users', 'color': '#7e3af2'},
    {'name': 'B-BBEE', 'code': 'BBBEE', 'description': 'B-BBEE consulting and verification', 'display_order': 3, 'icon': 'check-circle', 'color': '#0e9f6e'},
    {'name': 'Training', 'code': 'TRAINING', 'description': 'Training and development programmes', 'display_order': 4, 'icon': 'academic-cap', 'color': '#f59e0b'},
    {'name': 'Grant Applications', 'code': 'GRANTS', 'description': 'Discretionary grant applications and management', 'display_order': 5, 'icon': 'currency-dollar', 'color': '#10b981'},
]

print("Creating service categories...")
for cat_data in categories_data:
    cat, created = ServiceCategory.objects.get_or_create(
        code=cat_data['code'],
        defaults=cat_data
    )
    if created:
        print(f'  Created category: {cat.name}')
    else:
        print(f'  Category exists: {cat.name}')

# Create Service Offerings
services_data = [
    # Skills Development
    {'category_code': 'SKILLS', 'name': 'WSP/ATR Full Package', 'code': 'WSP-FULL', 'service_type': 'WSP_ATR', 'billing_type': 'ANNUAL', 'description': 'Complete WSP/ATR preparation, submission and compliance management'},
    {'category_code': 'SKILLS', 'name': 'WSP/ATR Submission Only', 'code': 'WSP-SUB', 'service_type': 'WSP_ATR', 'billing_type': 'PER_SUBMISSION', 'description': 'WSP/ATR submission assistance'},
    {'category_code': 'SKILLS', 'name': 'Skills Development Planning', 'code': 'SKILLS-PLAN', 'service_type': 'WSP_ATR', 'billing_type': 'PROJECT', 'description': 'Skills development planning and strategy'},
    
    # Employment Equity
    {'category_code': 'EE', 'name': 'EE Full Compliance Package', 'code': 'EE-FULL', 'service_type': 'EE_CONSULTING', 'billing_type': 'ANNUAL', 'description': 'Complete Employment Equity compliance including plan, reports, and committee support'},
    {'category_code': 'EE', 'name': 'EE Plan Development', 'code': 'EE-PLAN', 'service_type': 'EE_CONSULTING', 'billing_type': 'PROJECT', 'description': 'Development of Employment Equity Plan'},
    {'category_code': 'EE', 'name': 'EE Committee Support', 'code': 'EE-COMMITTEE', 'service_type': 'EE_CONSULTING', 'billing_type': 'MONTHLY', 'description': 'Employment Equity committee meeting facilitation and support'},
    
    # B-BBEE
    {'category_code': 'BBBEE', 'name': 'B-BBEE Verification Preparation', 'code': 'BBBEE-VERIFY', 'service_type': 'BEE_CONSULTING', 'billing_type': 'ANNUAL', 'description': 'Preparation for B-BBEE verification including document collection and scorecard optimization'},
    {'category_code': 'BBBEE', 'name': 'B-BBEE Strategy Consulting', 'code': 'BBBEE-STRATEGY', 'service_type': 'BEE_CONSULTING', 'billing_type': 'PROJECT', 'description': 'Strategic B-BBEE improvement planning'},
    
    # Training
    {'category_code': 'TRAINING', 'name': 'Learnerships', 'code': 'TRAIN-LEARN', 'service_type': 'HOST_EMPLOYMENT', 'billing_type': 'PER_LEARNER', 'description': 'Learnership programme implementation and management'},
    {'category_code': 'TRAINING', 'name': 'Skills Programmes', 'code': 'TRAIN-SKILLS', 'service_type': 'HOST_EMPLOYMENT', 'billing_type': 'PER_LEARNER', 'description': 'Skills programme implementation'},
    {'category_code': 'TRAINING', 'name': 'Internships', 'code': 'TRAIN-INTERN', 'service_type': 'HOST_EMPLOYMENT', 'billing_type': 'PER_LEARNER', 'description': 'Internship programme management'},
    
    # Grant Applications
    {'category_code': 'GRANTS', 'name': 'Discretionary Grant Application', 'code': 'DG-APP', 'service_type': 'DG_APPLICATION', 'billing_type': 'PER_SUBMISSION', 'description': 'Discretionary grant application preparation and submission'},
    {'category_code': 'GRANTS', 'name': 'Grant Project Management', 'code': 'DG-MANAGE', 'service_type': 'DG_APPLICATION', 'billing_type': 'PROJECT', 'description': 'Full grant project implementation and reporting'},
]

print("\nCreating service offerings...")
for svc_data in services_data:
    category = ServiceCategory.objects.get(code=svc_data.pop('category_code'))
    service, created = ServiceOffering.objects.get_or_create(
        code=svc_data['code'],
        defaults={**svc_data, 'category': category, 'is_active': True}
    )
    if created:
        print(f'  Created service: {service.name}')
    else:
        print(f'  Service exists: {service.name}')

print("\nDone! Created service categories and offerings.")
