# Generated manually for renaming trade test models

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('corporate', '0008_year_based_progress'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='TradeTestBooking',
            new_name='LegacyTradeTestBooking',
        ),
        migrations.RenameModel(
            old_name='TradeTestResult',
            new_name='LegacyTradeTestResult',
        ),
        migrations.RenameModel(
            old_name='TradeTestAppeal',
            new_name='LegacyTradeTestAppeal',
        ),
        migrations.AlterModelOptions(
            name='legacytradetestbooking',
            options={'verbose_name': 'Legacy Trade Test Booking', 'verbose_name_plural': 'Legacy Trade Test Bookings'},
        ),
        migrations.AlterModelOptions(
            name='legacytradetestresult',
            options={'verbose_name': 'Legacy Trade Test Result', 'verbose_name_plural': 'Legacy Trade Test Results'},
        ),
        migrations.AlterModelOptions(
            name='legacytradetestappeal',
            options={'verbose_name': 'Legacy Trade Test Appeal', 'verbose_name_plural': 'Legacy Trade Test Appeals'},
        ),
    ]
