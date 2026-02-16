# Generated manually - Data migration to set existing accreditations to ACTIVE

from django.db import migrations


def set_existing_to_active(apps, schema_editor):
    """Set all existing QualificationCampusAccreditation records to status='ACTIVE'"""
    QualificationCampusAccreditation = apps.get_model('academics', 'QualificationCampusAccreditation')
    QualificationCampusAccreditation.objects.filter(status='').update(status='ACTIVE')
    # Also update any that might have None or empty default
    QualificationCampusAccreditation.objects.exclude(status__in=['ACTIVE', 'SUPERSEDED', 'EXPIRED']).update(status='ACTIVE')


def reverse_migration(apps, schema_editor):
    """No reverse needed - status field will remain"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0012_add_multiple_accreditation_letters_per_campus'),
    ]

    operations = [
        migrations.RunPython(set_existing_to_active, reverse_migration),
    ]
