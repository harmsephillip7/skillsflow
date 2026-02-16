"""
Create initial Quote Templates and Payment Options
Run: python create_quote_template_data.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from finance.models import PaymentOption, QuoteTemplate


def create_payment_options():
    """Create default payment options"""
    options = [
        {
            'name': 'Full Payment Upfront',
            'code': 'UPFRONT',
            'description': 'Pay the full amount upfront and save on administration fees.',
            'installments': 1,
            'deposit_percent': Decimal('0.00'),
            'monthly_term': 1,
            'sort_order': 1,
        },
        {
            'name': 'Two Installments',
            'code': 'TWO_PAYMENTS',
            'description': 'Pay 50% deposit and 50% after 30 days.',
            'installments': 2,
            'deposit_percent': Decimal('50.00'),
            'monthly_term': 2,
            'sort_order': 2,
        },
        {
            'name': '10 Month Payment Plan',
            'code': 'MONTHLY_10',
            'description': 'Spread your payments over 10 months with no interest.',
            'installments': 10,
            'deposit_percent': Decimal('10.00'),
            'monthly_term': 10,
            'sort_order': 3,
        },
        {
            'name': '12 Month Payment Plan',
            'code': 'MONTHLY_12',
            'description': 'Spread your payments over 12 months with no interest.',
            'installments': 12,
            'deposit_percent': Decimal('10.00'),
            'monthly_term': 12,
            'sort_order': 4,
        },
    ]
    
    created_count = 0
    for opt_data in options:
        opt, created = PaymentOption.objects.get_or_create(
            code=opt_data['code'],
            defaults=opt_data
        )
        if created:
            print(f"Created PaymentOption: {opt.name}")
            created_count += 1
        else:
            print(f"PaymentOption exists: {opt.name}")
    
    return created_count


def create_quote_templates():
    """Create default quote templates"""
    # Get all payment options for templates
    payment_options = PaymentOption.objects.filter(is_active=True)
    
    templates = [
        {
            'name': 'Standard Quote',
            'code': 'STANDARD',
            'description': 'Standard quote template for individual learners.',
            'default_terms': '''Terms and Conditions:
1. This quote is valid for 48 hours from the date of issue.
2. Payment must be made according to the selected payment plan.
3. Enrollment is subject to availability and entry requirements.
4. Cancellation policy applies as per the learner agreement.
5. All prices are in South African Rand (ZAR).''',
            'header_text': 'Thank you for your interest in our programmes. Please find your personalized quote below.',
            'footer_text': 'For any queries, please contact our admissions team.',
            'validity_hours': 48,
            'sort_order': 1,
        },
        {
            'name': 'Corporate Quote',
            'code': 'CORPORATE',
            'description': 'Quote template for corporate training enquiries.',
            'default_terms': '''Corporate Terms and Conditions:
1. This quote is valid for 14 days from the date of issue.
2. Volume discounts may apply for groups of 10 or more learners.
3. Corporate billing and purchase orders accepted.
4. Training can be customized to meet your organization\'s needs.
5. All prices are exclusive of VAT (15%).''',
            'header_text': 'Thank you for your training enquiry. Please find the quotation for your organization below.',
            'footer_text': 'Our corporate training team will be in touch to discuss your requirements further.',
            'validity_hours': 336,  # 14 days
            'sort_order': 2,
        },
        {
            'name': 'Promotional Quote',
            'code': 'PROMO',
            'description': 'Quote template for promotional campaigns with limited-time offers.',
            'default_terms': '''Promotional Terms:
1. This promotional quote is valid for 24 hours only.
2. Early bird pricing subject to availability.
3. Cannot be combined with other offers.
4. Standard terms and conditions apply.''',
            'header_text': '🎉 Limited Time Offer! Don\'t miss out on this special promotional pricing.',
            'footer_text': 'Act now - this offer expires soon!',
            'validity_hours': 24,
            'sort_order': 3,
        },
    ]
    
    created_count = 0
    for tmpl_data in templates:
        tmpl, created = QuoteTemplate.objects.get_or_create(
            code=tmpl_data['code'],
            defaults=tmpl_data
        )
        if created:
            # Add all payment options to the template
            tmpl.payment_options.set(payment_options)
            print(f"Created QuoteTemplate: {tmpl.name}")
            created_count += 1
        else:
            print(f"QuoteTemplate exists: {tmpl.name}")
    
    return created_count


if __name__ == '__main__':
    print("\n=== Creating Payment Options ===")
    opt_count = create_payment_options()
    
    print("\n=== Creating Quote Templates ===")
    tmpl_count = create_quote_templates()
    
    print(f"\n✅ Done! Created {opt_count} payment options and {tmpl_count} quote templates.")
    print("\nYou can now create quotes using these templates in the CRM.")
