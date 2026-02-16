"""
Management command to check for expiring accreditations and compliance documents
Run daily via cron or scheduler to generate alerts

Usage:
    python manage.py check_accreditation_expiry
    python manage.py check_accreditation_expiry --dry-run
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from academics.models import (
    Qualification,
    ComplianceDocument,
    AccreditationAlert,
    PersonnelRegistration
)


class Command(BaseCommand):
    help = 'Check for expiring accreditations and compliance documents and generate alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating alerts',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()
        alerts_created = 0

        self.stdout.write(self.style.NOTICE(f'Checking accreditation expiry as of {today}'))
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no alerts will be created'))

        # Define alert thresholds
        thresholds = [
            ('6_MONTHS', 180),
            ('3_MONTHS', 90),
            ('1_MONTH', 30),
            ('EXPIRED', 0),
        ]

        # Check Qualifications
        self.stdout.write('\nChecking Qualifications...')
        qualifications = Qualification.objects.filter(
            accreditation_expiry__isnull=False,
            is_active=True
        )

        for qual in qualifications:
            days_until_expiry = (qual.accreditation_expiry - today).days

            for alert_type, threshold_days in thresholds:
                # Check if this alert type applies
                if alert_type == 'EXPIRED':
                    should_alert = days_until_expiry < 0
                elif alert_type == '1_MONTH':
                    should_alert = 0 <= days_until_expiry <= 30
                elif alert_type == '3_MONTHS':
                    should_alert = 30 < days_until_expiry <= 90
                elif alert_type == '6_MONTHS':
                    should_alert = 90 < days_until_expiry <= 180

                if should_alert:
                    # Check if alert already exists for this type
                    existing = AccreditationAlert.objects.filter(
                        qualification=qual,
                        alert_type=alert_type,
                        resolved=False
                    ).exists()

                    if not existing:
                        if alert_type == 'EXPIRED':
                            message = f"Accreditation for {qual.short_title} has EXPIRED on {qual.accreditation_expiry}. Immediate action required!"
                        else:
                            message = f"Accreditation for {qual.short_title} expires on {qual.accreditation_expiry} ({days_until_expiry} days remaining)."

                        if dry_run:
                            self.stdout.write(f"  Would create: {alert_type} alert for {qual.saqa_id}")
                        else:
                            AccreditationAlert.objects.create(
                                qualification=qual,
                                alert_type=alert_type,
                                alert_date=today,
                                message=message
                            )
                            alerts_created += 1
                            self.stdout.write(f"  Created: {alert_type} alert for {qual.saqa_id}")
                    break  # Only one alert type per qualification

        # Check Compliance Documents
        self.stdout.write('\nChecking Compliance Documents...')
        documents = ComplianceDocument.objects.filter(
            expiry_date__isnull=False
        )

        for doc in documents:
            days_until_expiry = (doc.expiry_date - today).days
            reminder_days = doc.reminder_days or 180

            for alert_type, threshold_days in thresholds:
                if alert_type == 'EXPIRED':
                    should_alert = days_until_expiry < 0
                elif alert_type == '1_MONTH':
                    should_alert = 0 <= days_until_expiry <= 30
                elif alert_type == '3_MONTHS':
                    should_alert = 30 < days_until_expiry <= 90
                elif alert_type == '6_MONTHS':
                    should_alert = 90 < days_until_expiry <= reminder_days

                if should_alert:
                    existing = AccreditationAlert.objects.filter(
                        compliance_document=doc,
                        alert_type=alert_type,
                        resolved=False
                    ).exists()

                    if not existing:
                        scope = f"{doc.campus.name}" if doc.campus else "Organisation-wide"
                        if alert_type == 'EXPIRED':
                            message = f"{doc.get_document_type_display()} ({scope}) has EXPIRED on {doc.expiry_date}. Immediate action required!"
                        else:
                            message = f"{doc.get_document_type_display()} ({scope}) expires on {doc.expiry_date} ({days_until_expiry} days remaining)."

                        if dry_run:
                            self.stdout.write(f"  Would create: {alert_type} alert for {doc.title}")
                        else:
                            AccreditationAlert.objects.create(
                                compliance_document=doc,
                                alert_type=alert_type,
                                alert_date=today,
                                message=message
                            )
                            alerts_created += 1
                            self.stdout.write(f"  Created: {alert_type} alert for {doc.title}")
                    break

        # Check Personnel Registrations
        self.stdout.write('\nChecking Personnel Registrations...')
        personnel = PersonnelRegistration.objects.filter(
            expiry_date__isnull=False,
            is_active=True
        )

        for person in personnel:
            days_until_expiry = (person.expiry_date - today).days

            for alert_type, threshold_days in thresholds:
                if alert_type == 'EXPIRED':
                    should_alert = days_until_expiry < 0
                elif alert_type == '1_MONTH':
                    should_alert = 0 <= days_until_expiry <= 30
                elif alert_type == '3_MONTHS':
                    should_alert = 30 < days_until_expiry <= 90
                elif alert_type == '6_MONTHS':
                    should_alert = 90 < days_until_expiry <= 180

                if should_alert:
                    # Personnel alerts are logged but not stored in AccreditationAlert
                    # Could be extended to create Task items instead
                    if dry_run:
                        self.stdout.write(
                            f"  Would flag: {person.user.get_full_name()} "
                            f"{person.get_personnel_type_display()} registration "
                            f"{'EXPIRED' if alert_type == 'EXPIRED' else f'expires in {days_until_expiry} days'}"
                        )
                    else:
                        self.stdout.write(
                            f"  Flagged: {person.user.get_full_name()} - {alert_type}"
                        )
                    break

        # Summary
        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN complete - no changes made'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Created {alerts_created} new alerts'))
