"""
Daily compliance check management command.
Runs via cron to check enrollments for document compliance issues.
Creates ComplianceAlert records for dashboard display.

Usage: python manage.py check_enrollment_compliance
Recommended: Run daily via cron at 6:00 AM
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from crm.models import SalesEnrollmentRecord, ComplianceAlert
from core.models import RequiredDocumentConfig
from learners.models import Document as LearnerDocument
from intakes.models import IntakeEnrollment


class Command(BaseCommand):
    help = 'Check enrollment compliance and create alerts for missing/rejected documents'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Check enrollments from the last N days (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without creating alerts'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        self.stdout.write(f"Checking enrollment compliance for last {days} days...")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No alerts will be created"))
        
        # Get required document types
        required_docs = RequiredDocumentConfig.get_required_types()
        if not required_docs:
            # Default required docs if none configured
            required_docs = ['ID_COPY', 'MATRIC', 'PROOF_ADDRESS']
            self.stdout.write(self.style.WARNING(
                f"No RequiredDocumentConfig found, using defaults: {required_docs}"
            ))
        else:
            self.stdout.write(f"Required documents: {required_docs}")
        
        # Get recent enrollments
        cutoff_date = timezone.now().date() - timedelta(days=days)
        enrollments = IntakeEnrollment.objects.filter(
            enrollment_date__gte=cutoff_date,
            status__in=['ENROLLED', 'ACTIVE', 'DOC_CHECK', 'PAYMENT_PENDING']
        ).select_related('learner', 'intake', 'intake__campus')
        
        self.stdout.write(f"Found {enrollments.count()} enrollments to check")
        
        alerts_created = 0
        alerts_updated = 0
        records_updated = 0
        
        for enrollment in enrollments:
            learner = enrollment.learner
            campus = enrollment.intake.campus
            
            # Check or create SalesEnrollmentRecord
            sales_record = SalesEnrollmentRecord.objects.filter(
                enrollment=enrollment
            ).first()
            
            if not sales_record:
                # Skip if no sales record exists
                continue
            
            # Get learner's documents
            learner_docs = LearnerDocument.objects.filter(
                learner=learner,
                is_deleted=False
            )
            
            # Check document upload completeness
            uploaded_types = set(learner_docs.values_list('document_type', flat=True))
            missing_docs = [doc for doc in required_docs if doc not in uploaded_types]
            
            # Check document quality (verified status)
            rejected_docs = list(learner_docs.filter(
                verified=False
            ).exclude(
                verification_notes=''
            ).values_list('document_type', flat=True))
            
            pending_docs = list(learner_docs.filter(
                verified=False,
                verification_notes=''
            ).values_list('document_type', flat=True))
            
            # Check proof of payment
            has_pop = learner_docs.filter(
                document_type='PROOF_OF_PAYMENT'
            ).exists()
            
            # Update sales record
            docs_complete = len(missing_docs) == 0
            docs_quality_ok = len(rejected_docs) == 0 and len(pending_docs) == 0
            
            compliance_issues = []
            if missing_docs:
                for doc in missing_docs:
                    compliance_issues.append({
                        'type': 'MISSING_DOC',
                        'doc_type': doc
                    })
            if rejected_docs:
                for doc in rejected_docs:
                    compliance_issues.append({
                        'type': 'QUALITY_REJECTED',
                        'doc_type': doc
                    })
            
            # Update sales record
            updated = False
            if sales_record.documents_uploaded_complete != docs_complete:
                sales_record.documents_uploaded_complete = docs_complete
                updated = True
            if sales_record.documents_quality_approved != docs_quality_ok:
                sales_record.documents_quality_approved = docs_quality_ok
                updated = True
            if sales_record.proof_of_payment_received != has_pop:
                sales_record.proof_of_payment_received = has_pop
                updated = True
            if sales_record.compliance_issues != compliance_issues:
                sales_record.compliance_issues = compliance_issues
                updated = True
            
            if updated:
                sales_record.last_compliance_check = timezone.now()
                if not dry_run:
                    sales_record.save()
                records_updated += 1
            
            # Create/update compliance alerts for issues
            if missing_docs and not dry_run:
                alert, created = ComplianceAlert.objects.update_or_create(
                    enrollment_record=sales_record,
                    alert_type='MISSING_DOCUMENTS',
                    resolved=False,
                    defaults={
                        'campus': campus,
                        'details': [{'doc_type': doc, 'issue': 'Missing'} for doc in missing_docs]
                    }
                )
                if created:
                    alerts_created += 1
                else:
                    alerts_updated += 1
            
            if rejected_docs and not dry_run:
                alert, created = ComplianceAlert.objects.update_or_create(
                    enrollment_record=sales_record,
                    alert_type='QUALITY_REJECTED',
                    resolved=False,
                    defaults={
                        'campus': campus,
                        'details': [{'doc_type': doc, 'issue': 'Quality rejected'} for doc in rejected_docs]
                    }
                )
                if created:
                    alerts_created += 1
                else:
                    alerts_updated += 1
            
            # Auto-resolve alerts if issues are fixed
            if not missing_docs and not dry_run:
                ComplianceAlert.objects.filter(
                    enrollment_record=sales_record,
                    alert_type='MISSING_DOCUMENTS',
                    resolved=False
                ).update(
                    resolved=True,
                    resolved_date=timezone.now(),
                    resolution_notes='Auto-resolved: All documents uploaded'
                )
            
            if not rejected_docs and not dry_run:
                ComplianceAlert.objects.filter(
                    enrollment_record=sales_record,
                    alert_type='QUALITY_REJECTED',
                    resolved=False
                ).update(
                    resolved=True,
                    resolved_date=timezone.now(),
                    resolution_notes='Auto-resolved: All documents approved'
                )
        
        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"\nCompliance check complete:\n"
            f"  - Records updated: {records_updated}\n"
            f"  - Alerts created: {alerts_created}\n"
            f"  - Alerts updated: {alerts_updated}"
        ))
