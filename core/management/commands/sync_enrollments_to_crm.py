from django.core.management.base import BaseCommand
from academics.models import Enrollment
from crm.models import Lead, LeadSource
from django.utils import timezone


class Command(BaseCommand):
    help = 'Create Lead records for existing enrollments to sync with CRM dashboard'

    def handle(self, *args, **options):
        # Get or create "Direct Enrollment" source
        direct_source, created = LeadSource.objects.get_or_create(
            name='Direct Enrollment',
            defaults={'is_active': True}
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Created new LeadSource: {direct_source.name}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"✓ Using existing LeadSource: {direct_source.name}"))

        # Process all enrollments
        enrollments = Enrollment.objects.all()
        self.stdout.write(f"\nProcessing {enrollments.count()} enrollment(s)...")

        created_count = 0
        updated_count = 0

        for enrollment in enrollments:
            learner = enrollment.learner
            
            # Try to find existing lead
            lead = None
            if learner.email:
                lead = Lead.objects.filter(email=learner.email).first()
            
            if lead:
                # Update existing lead
                if lead.status != 'ENROLLED':
                    lead.status = 'ENROLLED'
                    lead.converted_at = enrollment.application_date
                    lead.save()
                    updated_count += 1
                    self.stdout.write(f"  ✓ Updated Lead: {lead.first_name} {lead.last_name} → ENROLLED")
            else:
                # Create new lead
                lead = Lead.objects.create(
                    campus=enrollment.campus,
                    first_name=learner.first_name,
                    last_name=learner.last_name,
                    email=learner.email if learner.email else '',
                    phone=learner.phone_mobile if learner.phone_mobile else 'N/A',
                    date_of_birth=learner.date_of_birth,
                    status='ENROLLED',
                    lead_type='DIRECT_ENROLLMENT',
                    source=direct_source,
                    converted_at=enrollment.application_date,
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Created Lead: {lead.first_name} {lead.last_name}"))

        self.stdout.write(self.style.SUCCESS(f"\n{'='*50}"))
        self.stdout.write(self.style.SUCCESS(f"Summary:"))
        self.stdout.write(self.style.SUCCESS(f"  • Created: {created_count} new lead(s)"))
        self.stdout.write(self.style.SUCCESS(f"  • Updated: {updated_count} existing lead(s)"))
        self.stdout.write(self.style.SUCCESS(f"  • Total: {created_count + updated_count} lead(s) processed"))
        self.stdout.write(self.style.SUCCESS(f"{'='*50}"))
