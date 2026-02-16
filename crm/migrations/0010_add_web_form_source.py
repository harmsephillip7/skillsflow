"""
Data migration to add WEB_FORM lead source
"""
from django.db import migrations


def create_web_form_source(apps, schema_editor):
    """Create WEB_FORM lead source if it doesn't exist."""
    LeadSource = apps.get_model('crm', 'LeadSource')
    LeadSource.objects.get_or_create(
        code='WEB_FORM',
        defaults={
            'name': 'Web Form',
            'description': 'Lead captured via website form (Gravity Forms, etc.)',
            'is_active': True
        }
    )


def reverse_migration(apps, schema_editor):
    """Remove WEB_FORM lead source."""
    LeadSource = apps.get_model('crm', 'LeadSource')
    LeadSource.objects.filter(code='WEB_FORM').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0009_web_form_integration'),
    ]

    operations = [
        migrations.RunPython(create_web_form_source, reverse_migration),
    ]
