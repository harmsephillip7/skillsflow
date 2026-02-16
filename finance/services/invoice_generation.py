"""
Invoice Generation Service
Auto-generates invoices based on billing schedules and NOT configuration.
Supports pro forma with auto-conversion to tax invoice on payment.
"""
from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Avg, Count, Q, F
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from finance.models import (
    Invoice, InvoiceLineItem, ProjectBillingSchedule, 
    ScheduledInvoice, BillingScheduleTemplate, FunderCollectionMetrics
)


class InvoiceGenerationService:
    """
    Service for generating invoices from billing schedules.
    Handles pro forma creation and auto-conversion on payment.
    """
    
    @staticmethod
    def create_billing_schedule_for_not(training_notification):
        """
        Create or update billing schedule when NOT is created/approved.
        Uses BillingScheduleTemplate based on funder type.
        """
        from core.models import TrainingNotification
        
        # Get template for this funder type
        template = BillingScheduleTemplate.objects.filter(
            funder_type=training_notification.funder,
            is_active=True
        ).first()
        
        # Use NOT's billing_schedule field or fall back to template default
        schedule_type = training_notification.billing_schedule
        if schedule_type == 'MONTHLY' and template:
            # Use template's default if NOT hasn't been specifically configured
            schedule_type = template.default_schedule
        
        # Create or update billing schedule
        schedule, created = ProjectBillingSchedule.objects.update_or_create(
            training_notification=training_notification,
            defaults={
                'schedule_type': schedule_type,
                'invoice_type': template.invoice_type if template else 'PROFORMA',
                'auto_convert_on_payment': template.auto_convert_on_payment if template else True,
                'total_contract_value': training_notification.contract_value or Decimal('0.00'),
                'billing_start_date': training_notification.planned_start_date,
                'billing_end_date': training_notification.planned_end_date,
                'billing_day_of_month': template.billing_day_of_month if template else 1,
                'payment_terms_days': template.payment_terms_days if template else 30,
                'auto_generate': training_notification.auto_generate_invoices,
                'campus': training_notification.delivery_campus,
            }
        )
        
        # Calculate amount per period
        if schedule.total_contract_value and schedule.schedule_type != 'MANUAL':
            periods = schedule.calculate_periods()
            if periods > 0:
                schedule.amount_per_period = schedule.total_contract_value / periods
                schedule.save()
        
        # Generate scheduled invoices
        if created or not schedule.scheduled_invoices.exists():
            InvoiceGenerationService.generate_scheduled_invoices(schedule)
        
        return schedule
    
    @staticmethod
    def generate_scheduled_invoices(billing_schedule: ProjectBillingSchedule):
        """Generate all scheduled invoice records for a billing schedule."""
        if not billing_schedule.billing_start_date:
            return []
        
        # Clear existing scheduled (not generated) invoices
        billing_schedule.scheduled_invoices.filter(status='SCHEDULED').delete()
        
        scheduled = []
        current_date = billing_schedule.billing_start_date
        
        # Adjust to billing day of month
        try:
            current_date = current_date.replace(day=billing_schedule.billing_day_of_month)
        except ValueError:
            # Handle months with fewer days
            current_date = current_date.replace(day=28)
        
        period = 1
        end_date = billing_schedule.billing_end_date or (billing_schedule.billing_start_date + relativedelta(years=1))
        
        # For deliverable-based, create from deliverables
        if billing_schedule.schedule_type == 'DELIVERABLE':
            deliverables = billing_schedule.training_notification.deliverables.filter(
                status__in=['PENDING', 'IN_PROGRESS', 'COMPLETED']
            ).order_by('due_date')
            
            # Calculate amount per deliverable if not set
            deliverable_count = deliverables.count()
            amount_per_deliverable = billing_schedule.amount_per_period
            if not amount_per_deliverable and deliverable_count > 0:
                amount_per_deliverable = billing_schedule.total_contract_value / deliverable_count
            
            for deliverable in deliverables:
                scheduled_invoice = ScheduledInvoice.objects.create(
                    billing_schedule=billing_schedule,
                    period_number=period,
                    scheduled_date=deliverable.due_date,
                    due_date=deliverable.due_date + timedelta(days=billing_schedule.payment_terms_days),
                    amount=amount_per_deliverable or Decimal('0.00'),
                    deliverable=deliverable,
                    campus=billing_schedule.campus,
                )
                scheduled.append(scheduled_invoice)
                period += 1
        else:
            # Time-based schedules
            if billing_schedule.schedule_type == 'MONTHLY':
                delta = relativedelta(months=1)
            elif billing_schedule.schedule_type == 'QUARTERLY':
                delta = relativedelta(months=3)
            elif billing_schedule.schedule_type == 'ANNUALLY':
                delta = relativedelta(years=1)
            elif billing_schedule.schedule_type == 'UPFRONT':
                # Single invoice
                scheduled_invoice = ScheduledInvoice.objects.create(
                    billing_schedule=billing_schedule,
                    period_number=1,
                    scheduled_date=current_date,
                    due_date=current_date + timedelta(days=billing_schedule.payment_terms_days),
                    amount=billing_schedule.total_contract_value,
                    campus=billing_schedule.campus,
                )
                return [scheduled_invoice]
            else:
                return scheduled
            
            while current_date <= end_date:
                scheduled_invoice = ScheduledInvoice.objects.create(
                    billing_schedule=billing_schedule,
                    period_number=period,
                    scheduled_date=current_date,
                    due_date=current_date + timedelta(days=billing_schedule.payment_terms_days),
                    amount=billing_schedule.amount_per_period or Decimal('0.00'),
                    campus=billing_schedule.campus,
                )
                scheduled.append(scheduled_invoice)
                current_date += delta
                period += 1
        
        # Set next invoice date
        if scheduled:
            billing_schedule.next_invoice_date = scheduled[0].scheduled_date
            billing_schedule.save()
        
        return scheduled
    
    @staticmethod
    @transaction.atomic
    def generate_invoice_for_scheduled(scheduled_invoice: ScheduledInvoice) -> Invoice:
        """Generate actual invoice from scheduled invoice."""
        if scheduled_invoice.invoice:
            return scheduled_invoice.invoice
        
        bs = scheduled_invoice.billing_schedule
        tn = bs.training_notification
        
        # Determine invoice type prefix
        is_proforma = bs.invoice_type == 'PROFORMA'
        prefix = 'PF' if is_proforma else 'INV'
        
        # Generate invoice number
        from datetime import datetime
        date_part = datetime.now().strftime('%Y%m')
        last_invoice = Invoice.objects.filter(
            invoice_number__startswith=f"{prefix}-{date_part}-"
        ).order_by('-invoice_number').first()
        
        if last_invoice:
            try:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                invoice_number = f"{prefix}-{date_part}-{last_num + 1:04d}"
            except (ValueError, IndexError):
                invoice_number = f"{prefix}-{date_part}-0001"
        else:
            invoice_number = f"{prefix}-{date_part}-0001"
        
        # Determine invoice type and billing info
        if tn.funder == 'PRIVATE' and tn.cohort:
            # Get learner for private billing
            from academics.models import Enrollment
            enrollment = Enrollment.objects.filter(cohort=tn.cohort).first()
            invoice_type = 'LEARNER'
            learner = enrollment.learner if enrollment else None
            billing_name = learner.full_name if learner else tn.client_name
            billing_email = learner.email if learner else ''
            corporate_client = None
        elif tn.corporate_client:
            invoice_type = 'CORPORATE'
            learner = None
            corporate_client = tn.corporate_client
            billing_name = tn.corporate_client.name
            billing_email = getattr(tn.corporate_client, 'billing_email', '') or ''
        elif tn.funder == 'SETA':
            invoice_type = 'SETA'
            learner = None
            corporate_client = None
            billing_name = tn.client_name
            billing_email = ''
        else:
            invoice_type = 'CORPORATE'
            learner = None
            corporate_client = tn.corporate_client
            billing_name = tn.client_name or 'Unknown'
            billing_email = ''
        
        # Create invoice
        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            invoice_type=invoice_type,
            learner=learner,
            corporate_client=corporate_client,
            invoice_date=scheduled_invoice.scheduled_date,
            due_date=scheduled_invoice.due_date,
            status='DRAFT',
            billing_name=billing_name,
            billing_email=billing_email,
            subtotal=scheduled_invoice.amount,
            vat_amount=scheduled_invoice.amount * Decimal('0.15'),
            total=scheduled_invoice.amount * Decimal('1.15'),
            campus=bs.campus,
            notes=f"Auto-generated for {tn.reference_number} - Period {scheduled_invoice.period_number}",
        )
        
        # Build description
        description = f"{tn.title}"
        if scheduled_invoice.deliverable:
            description += f" - {scheduled_invoice.deliverable.title}"
        else:
            description += f" - Period {scheduled_invoice.period_number}"
        
        # Add line item
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=description,
            quantity=1,
            unit_price=scheduled_invoice.amount,
            qualification=tn.qualification,
        )
        
        # Update scheduled invoice
        scheduled_invoice.invoice = invoice
        scheduled_invoice.status = 'GENERATED'
        scheduled_invoice.generated_at = timezone.now()
        scheduled_invoice.save()
        
        # Update billing schedule
        bs.last_invoice_generated = scheduled_invoice.scheduled_date
        next_scheduled = bs.scheduled_invoices.filter(
            status='SCHEDULED',
            scheduled_date__gt=scheduled_invoice.scheduled_date
        ).first()
        bs.next_invoice_date = next_scheduled.scheduled_date if next_scheduled else None
        bs.save()
        
        return invoice
    
    @staticmethod
    def generate_due_invoices():
        """Generate all invoices that are due today or overdue."""
        today = date.today()
        due_invoices = ScheduledInvoice.objects.filter(
            status='SCHEDULED',
            scheduled_date__lte=today,
            billing_schedule__auto_generate=True
        )
        
        generated = []
        for scheduled in due_invoices:
            try:
                invoice = InvoiceGenerationService.generate_invoice_for_scheduled(scheduled)
                generated.append(invoice)
            except Exception as e:
                # Log error but continue with others
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error generating invoice for {scheduled}: {e}")
        
        return generated
    
    @staticmethod
    @transaction.atomic
    def convert_proforma_to_tax_invoice(invoice: Invoice) -> Invoice:
        """Convert a pro forma invoice to a tax invoice when payment is received."""
        if not invoice.invoice_number.startswith('PF-'):
            return invoice
        
        # Generate new tax invoice number
        from datetime import datetime
        date_part = datetime.now().strftime('%Y%m')
        last_invoice = Invoice.objects.filter(
            invoice_number__startswith=f"INV-{date_part}-"
        ).order_by('-invoice_number').first()
        
        if last_invoice:
            try:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                new_number = f"INV-{date_part}-{last_num + 1:04d}"
            except (ValueError, IndexError):
                new_number = f"INV-{date_part}-0001"
        else:
            new_number = f"INV-{date_part}-0001"
        
        # Store old number in notes
        old_number = invoice.invoice_number
        invoice.invoice_number = new_number
        invoice.notes = f"Converted from pro forma {old_number}\n{invoice.notes}"
        invoice.save()
        
        return invoice
    
    @staticmethod
    def check_and_convert_on_payment(payment):
        """
        Called when a payment is received.
        Checks if the linked invoice should be converted from pro forma.
        """
        invoice = payment.invoice
        
        # Check if linked billing schedule has auto-convert enabled
        try:
            scheduled = invoice.scheduled_invoice_link.first()
            if scheduled and scheduled.billing_schedule.auto_convert_on_payment:
                if invoice.invoice_number.startswith('PF-'):
                    InvoiceGenerationService.convert_proforma_to_tax_invoice(invoice)
                
                # Update scheduled invoice status
                if invoice.amount_paid >= invoice.total:
                    scheduled.status = 'PAID'
                    scheduled.save()
        except Exception:
            pass  # Invoice may not be linked to a scheduled invoice
        
        return invoice


class CollectionMetricsService:
    """
    Service for calculating collection rates and persistency metrics.
    Supports rolling quarterly and project lifetime calculations.
    """
    
    @staticmethod
    def calculate_project_metrics(training_notification, period_type='LIFETIME'):
        """Calculate collection metrics for a specific project."""
        from finance.models import Invoice, Payment
        
        # Determine period
        if period_type == 'QUARTERLY':
            period_end = date.today()
            period_start = period_end - relativedelta(months=3)
        else:  # LIFETIME
            period_start = training_notification.planned_start_date or training_notification.created_at.date()
            period_end = date.today()
        
        # Get invoices for this project
        invoices = Invoice.objects.filter(
            Q(scheduled_invoice_link__billing_schedule__training_notification=training_notification) |
            Q(tranche__training_notification=training_notification),
            invoice_date__gte=period_start,
            invoice_date__lte=period_end
        )
        
        # Calculate metrics
        total_invoiced = invoices.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        total_collected = invoices.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        total_outstanding = total_invoiced - total_collected
        
        # Count invoices by status
        invoices_issued = invoices.count()
        invoices_paid = invoices.filter(status='PAID').count()
        invoices_outstanding = invoices.filter(status__in=['SENT', 'PARTIAL', 'OVERDUE']).count()
        
        # Calculate on-time vs late
        invoices_paid_on_time = 0
        invoices_paid_late = 0
        for inv in invoices.filter(status='PAID'):
            payments = inv.payments.filter(status='COMPLETED')
            if payments.exists():
                first_payment = payments.order_by('payment_date').first()
                if first_payment.payment_date <= inv.due_date:
                    invoices_paid_on_time += 1
                else:
                    invoices_paid_late += 1
        
        # Calculate average days to payment
        avg_days = None
        paid_invoices = invoices.filter(status='PAID')
        if paid_invoices.exists():
            total_days = 0
            count = 0
            for inv in paid_invoices:
                first_payment = inv.payments.filter(status='COMPLETED').order_by('payment_date').first()
                if first_payment:
                    days = (first_payment.payment_date - inv.invoice_date).days
                    total_days += days
                    count += 1
            if count > 0:
                avg_days = Decimal(total_days) / count
        
        # Calculate aging
        today = date.today()
        aging_current = Decimal('0.00')
        aging_30 = Decimal('0.00')
        aging_60 = Decimal('0.00')
        aging_90 = Decimal('0.00')
        aging_over_90 = Decimal('0.00')
        
        for inv in invoices.filter(status__in=['SENT', 'PARTIAL', 'OVERDUE']):
            days_overdue = (today - inv.due_date).days
            balance = inv.balance_due
            
            if days_overdue <= 0:
                aging_current += balance
            elif days_overdue <= 30:
                aging_30 += balance
            elif days_overdue <= 60:
                aging_60 += balance
            elif days_overdue <= 90:
                aging_90 += balance
            else:
                aging_over_90 += balance
        
        # Create or update metrics record
        metrics, _ = FunderCollectionMetrics.objects.update_or_create(
            entity_type='PROJECT',
            period_type=period_type,
            training_notification=training_notification,
            defaults={
                'period_start': period_start,
                'period_end': period_end,
                'total_invoiced': total_invoiced,
                'total_collected': total_collected,
                'total_outstanding': total_outstanding,
                'invoices_issued': invoices_issued,
                'invoices_paid_on_time': invoices_paid_on_time,
                'invoices_paid_late': invoices_paid_late,
                'invoices_outstanding': invoices_outstanding,
                'average_days_to_payment': avg_days,
                'aging_current': aging_current,
                'aging_30_days': aging_30,
                'aging_60_days': aging_60,
                'aging_90_days': aging_90,
                'aging_over_90': aging_over_90,
                'campus': training_notification.delivery_campus,
            }
        )
        
        # Calculate rates and assess risk
        metrics.calculate_rates()
        
        return metrics
    
    @staticmethod
    def calculate_funder_type_metrics(funder_type, period_type='QUARTERLY'):
        """Calculate collection metrics for a funder type."""
        from core.models import TrainingNotification
        from finance.models import Invoice
        
        # Determine period
        if period_type == 'QUARTERLY':
            period_end = date.today()
            period_start = period_end - relativedelta(months=3)
        else:  # ANNUAL
            period_end = date.today()
            period_start = period_end - relativedelta(years=1)
        
        # Get all projects with this funder type
        projects = TrainingNotification.objects.filter(funder=funder_type)
        
        # Get all invoices linked to these projects
        invoices = Invoice.objects.filter(
            Q(scheduled_invoice_link__billing_schedule__training_notification__in=projects) |
            Q(tranche__training_notification__in=projects),
            invoice_date__gte=period_start,
            invoice_date__lte=period_end
        ).distinct()
        
        # Calculate metrics
        total_invoiced = invoices.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        total_collected = invoices.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        # Count by status
        invoices_issued = invoices.count()
        
        # Get campus from first project
        first_project = projects.first()
        campus = first_project.delivery_campus if first_project else None
        
        # Create or update metrics
        metrics, _ = FunderCollectionMetrics.objects.update_or_create(
            entity_type='FUNDER_TYPE',
            period_type=period_type,
            funder_type=funder_type,
            defaults={
                'period_start': period_start,
                'period_end': period_end,
                'total_invoiced': total_invoiced,
                'total_collected': total_collected,
                'total_outstanding': total_invoiced - total_collected,
                'invoices_issued': invoices_issued,
                'campus': campus,
            }
        )
        
        metrics.calculate_rates()
        return metrics
    
    @staticmethod
    def calculate_corporate_metrics(corporate_client, period_type='QUARTERLY'):
        """Calculate collection metrics for a corporate client."""
        from finance.models import Invoice
        
        # Determine period
        if period_type == 'QUARTERLY':
            period_end = date.today()
            period_start = period_end - relativedelta(months=3)
        else:
            period_end = date.today()
            period_start = period_end - relativedelta(years=1)
        
        # Get invoices for this corporate
        invoices = Invoice.objects.filter(
            corporate_client=corporate_client,
            invoice_date__gte=period_start,
            invoice_date__lte=period_end
        )
        
        total_invoiced = invoices.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        total_collected = invoices.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        
        metrics, _ = FunderCollectionMetrics.objects.update_or_create(
            entity_type='CORPORATE',
            period_type=period_type,
            corporate_client=corporate_client,
            defaults={
                'period_start': period_start,
                'period_end': period_end,
                'total_invoiced': total_invoiced,
                'total_collected': total_collected,
                'total_outstanding': total_invoiced - total_collected,
                'invoices_issued': invoices.count(),
                'campus': corporate_client.campus if hasattr(corporate_client, 'campus') else None,
            }
        )
        
        metrics.calculate_rates()
        return metrics
    
    @staticmethod
    def recalculate_all_metrics():
        """Recalculate all collection metrics - can be run as scheduled task."""
        from core.models import TrainingNotification
        from corporate.models import CorporateClient
        
        # Calculate for all active projects
        for project in TrainingNotification.objects.filter(is_deleted=False):
            try:
                CollectionMetricsService.calculate_project_metrics(project, 'QUARTERLY')
                CollectionMetricsService.calculate_project_metrics(project, 'LIFETIME')
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error calculating metrics for {project}: {e}")
        
        # Calculate for all funder types
        funder_types = ['PRIVATE', 'SETA', 'CORPORATE', 'CORPORATE_DG', 'MUNICIPALITY', 'GOVERNMENT']
        for funder_type in funder_types:
            try:
                CollectionMetricsService.calculate_funder_type_metrics(funder_type, 'QUARTERLY')
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error calculating metrics for {funder_type}: {e}")
        
        # Calculate for all corporate clients
        for corporate in CorporateClient.objects.filter(is_active=True):
            try:
                CollectionMetricsService.calculate_corporate_metrics(corporate, 'QUARTERLY')
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error calculating metrics for {corporate}: {e}")
