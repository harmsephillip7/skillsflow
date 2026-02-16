# Generated migration for Card Scan lead source
from django.db import migrations


def create_card_scan_source(apps, schema_editor):
    """Create the CARD_SCAN lead source for AI card scanner feature"""
    LeadSource = apps.get_model('crm', 'LeadSource')
    LeadSource.objects.get_or_create(
        code='CARD_SCAN',
        defaults={
            'name': 'Card Scan',
            'description': 'Lead captured via AI-powered contact card scanner at events and exhibitions',
            'is_active': True,
        }
    )


def remove_card_scan_source(apps, schema_editor):
    """Remove the CARD_SCAN lead source"""
    LeadSource = apps.get_model('crm', 'LeadSource')
    LeadSource.objects.filter(code='CARD_SCAN').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0007_add_lead_document_upload_models'),
    ]

    operations = [
        migrations.RunPython(create_card_scan_source, remove_card_scan_source),
    ]
