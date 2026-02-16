"""Quick check script"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from crm.models import Lead
from academics.models import Qualification, QualificationPricing
from finance.models import Quote, QuoteTemplate, PaymentOption

print("=== CRM Data Check ===")
leads_with_qual = Lead.objects.exclude(qualification_interest__isnull=True).count()
print(f"Leads with qual interest: {leads_with_qual}")

quals = Qualification.objects.filter(is_active=True).count()
print(f"Active qualifications: {quals}")

pricing = QualificationPricing.objects.count()
print(f"Qualification pricing records: {pricing}")

templates = QuoteTemplate.objects.count()
print(f"Quote templates: {templates}")

payment_opts = PaymentOption.objects.count()
print(f"Payment options: {payment_opts}")

# Check leads by status
print("\n=== Lead Statuses ===")
for status in ['QUALIFIED', 'PROPOSAL', 'CONTACTED']:
    count = Lead.objects.filter(status=status).count()
    print(f"  {status}: {count}")
