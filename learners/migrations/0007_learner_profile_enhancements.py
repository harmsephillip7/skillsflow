# Generated migration for learner profile enhancements

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('learners', '0006_add_gps_photo_offline_fields'),
    ]

    operations = [
        # Add profile photo field
        migrations.AddField(
            model_name='learner',
            name='profile_photo',
            field=models.ImageField(upload_to='learner_profiles/', null=True, blank=True, help_text='Profile photo for student card'),
        ),
        
        # Add simplified contact fields for backward compatibility
        migrations.AddField(
            model_name='learner',
            name='id_number',
            field=models.CharField(max_length=13, blank=True, help_text='ID Number (for profile views)'),
        ),
        migrations.AddField(
            model_name='learner',
            name='phone_number',
            field=models.CharField(max_length=20, blank=True, help_text='Primary phone (for profile views)'),
        ),
        migrations.AddField(
            model_name='learner',
            name='alternative_phone',
            field=models.CharField(max_length=20, blank=True, help_text='Alternative phone number'),
        ),
        
        # Add simplified address fields
        migrations.AddField(
            model_name='learner',
            name='address_line1',
            field=models.CharField(max_length=200, blank=True),
        ),
        migrations.AddField(
            model_name='learner',
            name='address_line2',
            field=models.CharField(max_length=200, blank=True),
        ),
        migrations.AddField(
            model_name='learner',
            name='city',
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name='learner',
            name='province',
            field=models.CharField(max_length=50, blank=True),
        ),
        migrations.AddField(
            model_name='learner',
            name='postal_code',
            field=models.CharField(max_length=10, blank=True),
        ),
        
        # Add emergency contact fields
        migrations.AddField(
            model_name='learner',
            name='emergency_contact_name',
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name='learner',
            name='emergency_contact_phone',
            field=models.CharField(max_length=20, blank=True),
        ),
        migrations.AddField(
            model_name='learner',
            name='emergency_contact_relationship',
            field=models.CharField(max_length=50, blank=True),
        ),
    ]
