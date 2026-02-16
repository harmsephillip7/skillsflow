"""
Finance app models
Invoicing, payments, and Sage Intacct integration
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from core.models import AuditedModel
from tenants.models import TenantAwareModel


class PriceList(AuditedModel):
    """
    Price list for qualifications and services
    """
    name = models.CharField(max_length=100)
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='price_lists'
    )
    
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-effective_from']
        verbose_name = 'Price List'
        verbose_name_plural = 'Price Lists'
    
    def __str__(self):
        return f"{self.brand.code} - {self.name}"


class PriceListItem(models.Model):
    """
    Individual pricing items
    """
    ITEM_TYPES = [
        ('QUALIFICATION', 'Qualification'),
        ('MODULE', 'Module'),
        ('ASSESSMENT', 'Assessment'),
        ('MATERIAL', 'Material'),
        ('REGISTRATION', 'Registration Fee'),
        ('ADMIN', 'Admin Fee'),
        ('OTHER', 'Other'),
    ]
    
    price_list = models.ForeignKey(
        PriceList, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    
    # Link to qualification or module
    qualification = models.ForeignKey(
        'academics.Qualification', 
        null=True, blank=True,
        on_delete=models.CASCADE, 
        related_name='price_items'
    )
    module = models.ForeignKey(
        'academics.Module', 
        null=True, blank=True,
        on_delete=models.CASCADE, 
        related_name='price_items'
    )
    
    description = models.CharField(max_length=200)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Optional VAT override
    vat_inclusive = models.BooleanField(default=True)
    vat_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('15.00')
    )
    
    class Meta:
        ordering = ['item_type', 'description']
        verbose_name = 'Price List Item'
        verbose_name_plural = 'Price List Items'
    
    def __str__(self):
        return f"{self.description} - R{self.price}"


class Quote(TenantAwareModel):
    """
    Quotation for prospective learners or corporates
    Supports payment plans, year-specific pricing, and public sharing
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('VIEWED', 'Viewed'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
        ('CONVERTED', 'Converted to Invoice'),
    ]
    
    PAYMENT_PLAN_CHOICES = [
        ('UPFRONT', 'Full Payment Upfront'),
        ('TWO_INSTALLMENTS', 'Two Installments'),
        ('MONTHLY', 'Monthly Payments'),
    ]
    
    ENROLLMENT_YEAR_CHOICES = [
        ('CURRENT', 'Current Year'),
        ('NEXT', 'Next Year'),
        ('PLUS_TWO', 'Year After Next'),
    ]
    
    quote_number = models.CharField(max_length=50, unique=True, blank=True)
    
    # Public access token for shareable links (UUID-based)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Client - either learner or corporate
    learner = models.ForeignKey(
        'learners.Learner', 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='quotes'
    )
    corporate_client = models.ForeignKey(
        'corporate.CorporateClient', 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='quotes'
    )
    
    # Lead reference
    lead = models.ForeignKey(
        'crm.Lead', 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='quotes'
    )
    
    # Intake reference for intake-specific pricing
    intake = models.ForeignKey(
        'intakes.Intake',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='quotes',
        help_text="Intake this quote is for"
    )
    
    # Quote template used
    template = models.ForeignKey(
        'finance.QuoteTemplate',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='quotes',
        help_text="Template used to create this quote"
    )
    
    # Payment option selected
    payment_option = models.ForeignKey(
        'finance.PaymentOption',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='quotes',
        help_text="Payment option selected for this quote"
    )
    
    # Enrollment year
    enrollment_year = models.CharField(
        max_length=10, 
        choices=ENROLLMENT_YEAR_CHOICES, 
        default='CURRENT',
        help_text="Academic year for enrollment"
    )
    academic_year = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Specific academic year (e.g., 2026)"
    )
    
    # Payment plan
    payment_plan = models.CharField(
        max_length=20, 
        choices=PAYMENT_PLAN_CHOICES, 
        default='UPFRONT'
    )
    monthly_term = models.PositiveIntegerField(
        default=10,
        help_text="Number of monthly payments (for monthly plan)"
    )
    
    # Dates
    quote_date = models.DateField(default=timezone.now)
    valid_until = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Tracking timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    
    # VAT handling - default 0% for learners
    vat_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="VAT rate (0% for individual learners, 15% for corporates)"
    )
    
    # Totals (calculated from line items)
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    vat_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    discount_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    total = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Notes
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True, default="This quote is valid for 48 hours from the date of issue.")
    
    class Meta:
        ordering = ['-quote_date']
        verbose_name = 'Quote'
        verbose_name_plural = 'Quotes'
    
    def __str__(self):
        return self.quote_number
    
    def save(self, *args, **kwargs):
        # Generate quote number if not set
        if not self.quote_number:
            today = timezone.now()
            prefix = f"Q-{today.strftime('%Y%m')}-"
            last_quote = Quote.objects.filter(quote_number__startswith=prefix).order_by('-quote_number').first()
            if last_quote:
                last_num = int(last_quote.quote_number.split('-')[-1])
                self.quote_number = f"{prefix}{last_num + 1:04d}"
            else:
                self.quote_number = f"{prefix}0001"
        
        # Set valid_until to 48 hours from quote_date if not set
        if not self.valid_until:
            from datetime import timedelta
            if isinstance(self.quote_date, str):
                from datetime import datetime
                self.quote_date = datetime.strptime(self.quote_date, '%Y-%m-%d').date()
            self.valid_until = self.quote_date + timedelta(days=2)
        
        # Set academic year based on enrollment_year choice
        if not self.academic_year:
            current_year = timezone.now().year
            if self.enrollment_year == 'CURRENT':
                self.academic_year = current_year
            elif self.enrollment_year == 'NEXT':
                self.academic_year = current_year + 1
            else:  # PLUS_TWO
                self.academic_year = current_year + 2
        
        super().save(*args, **kwargs)
    
    def calculate_totals(self):
        """Recalculate totals from line items"""
        self.subtotal = sum(item.line_total for item in self.line_items.all())
        self.vat_amount = self.subtotal * (self.vat_rate / 100)
        self.total = self.subtotal + self.vat_amount
        self.save(update_fields=['subtotal', 'vat_amount', 'total'])
    
    def is_expired(self):
        """Check if quote has expired (48 hour window)"""
        return self.valid_until < timezone.now().date()
    
    def mark_as_sent(self):
        """Mark quote as sent"""
        self.status = 'SENT'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_as_viewed(self):
        """Mark quote as viewed (when public link accessed)"""
        if self.status == 'SENT':
            self.status = 'VIEWED'
        if not self.viewed_at:
            self.viewed_at = timezone.now()
            self.save(update_fields=['status', 'viewed_at'])
    
    def accept(self):
        """Accept the quote"""
        self.status = 'ACCEPTED'
        self.accepted_at = timezone.now()
        self.save(update_fields=['status', 'accepted_at'])
    
    def reject(self):
        """Reject the quote"""
        self.status = 'REJECTED'
        self.rejected_at = timezone.now()
        self.save(update_fields=['status', 'rejected_at'])
    
    def get_public_url(self):
        """Get public shareable URL"""
        from django.urls import reverse
        return reverse('finance:quote_public_view', kwargs={'token': self.public_token})
    
    def get_payment_schedule_display(self):
        """Get human-readable payment schedule"""
        if self.payment_plan == 'UPFRONT':
            return f"Full payment of R{self.total:,.2f} due on acceptance"
        elif self.payment_plan == 'TWO_INSTALLMENTS':
            half = self.total / 2
            return f"2 payments of R{half:,.2f} each"
        else:  # MONTHLY
            monthly = self.total / self.monthly_term
            return f"{self.monthly_term} monthly payments of R{monthly:,.2f}"


class QuoteLineItem(models.Model):
    """
    Quote line items with support for year-specific pricing
    """
    ITEM_TYPE_CHOICES = [
        ('TUITION', 'Tuition Fee'),
        ('REGISTRATION', 'Registration Fee'),
        ('MATERIALS', 'Materials Fee'),
        ('ASSESSMENT', 'Assessment Fee'),
        ('OTHER', 'Other'),
    ]
    
    quote = models.ForeignKey(
        Quote, 
        on_delete=models.CASCADE, 
        related_name='line_items'
    )
    
    item_type = models.CharField(
        max_length=20, 
        choices=ITEM_TYPE_CHOICES, 
        default='TUITION'
    )
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    
    # Pricing - original vs quoted (for audit trail)
    original_unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True, blank=True,
        help_text="Original price from price list/intake"
    )
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Final quoted price (may differ from original)"
    )
    
    # Discount
    discount_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    discount_reason = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Reason for discount if applicable"
    )
    
    # Academic year for this line item
    academic_year = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Academic year for this fee"
    )
    
    # Links
    qualification = models.ForeignKey(
        'academics.Qualification', 
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    module = models.ForeignKey(
        'academics.Module', 
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    
    class Meta:
        ordering = ['id']
        verbose_name = 'Quote Line Item'
        verbose_name_plural = 'Quote Line Items'
    
    def __str__(self):
        return f"{self.quote.quote_number} - {self.description}"
    
    @property
    def line_total(self):
        base = self.quantity * self.unit_price
        discount = base * (self.discount_percent / 100)
        return base - discount
    
    @property
    def discount_amount(self):
        base = self.quantity * self.unit_price
        return base * (self.discount_percent / 100)


class QualificationYearlyPricing(AuditedModel):
    """
    Year-specific pricing for qualifications
    Prices change year to year and enrollments can be for future years
    """
    qualification = models.ForeignKey(
        'academics.Qualification',
        on_delete=models.CASCADE,
        related_name='yearly_pricing'
    )
    
    academic_year = models.PositiveIntegerField(
        help_text="Academic year (e.g., 2026)"
    )
    
    # Fees
    registration_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    tuition_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    materials_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Total (computed property)
    @property
    def total_fee(self):
        return self.registration_fee + self.tuition_fee + self.materials_fee
    
    # Validity
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-academic_year', 'qualification__short_title']
        unique_together = ['qualification', 'academic_year']
        verbose_name = 'Qualification Yearly Pricing'
        verbose_name_plural = 'Qualification Yearly Pricing'
    
    def __str__(self):
        return f"{self.qualification.short_title} - {self.academic_year}"


class QuotePaymentSchedule(models.Model):
    """
    Payment schedule/installments for a quote
    Generated based on payment plan selection
    """
    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name='payment_schedule'
    )
    
    installment_number = models.PositiveIntegerField()
    description = models.CharField(max_length=100)
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Payment tracking
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['quote', 'installment_number']
        unique_together = ['quote', 'installment_number']
        verbose_name = 'Quote Payment Schedule'
        verbose_name_plural = 'Quote Payment Schedules'
    
    def __str__(self):
        return f"{self.quote.quote_number} - Installment {self.installment_number}"


class PaymentOption(AuditedModel):
    """
    Global payment options/plans that can be selected for quotes.
    Configurable installment plans with deposit and monthly terms.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    # Payment structure
    installments = models.PositiveIntegerField(
        default=1,
        help_text="Number of installments (1 = full payment)"
    )
    deposit_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Deposit percentage of total (e.g., 10.00 = 10%)"
    )
    monthly_term = models.PositiveIntegerField(
        default=10,
        help_text="Number of months for payment plan"
    )
    
    # Display order
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Payment Option'
        verbose_name_plural = 'Payment Options'
    
    def __str__(self):
        return self.name
    
    def calculate_schedule(self, total_amount, start_date=None):
        """
        Calculate payment schedule for a given total amount.
        Returns list of dicts with {installment_number, description, due_date, amount}
        """
        from django.utils import timezone
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta
        
        if start_date is None:
            start_date = timezone.now().date()
        
        schedule = []
        remaining = total_amount
        
        if self.installments == 1:
            # Full payment upfront
            schedule.append({
                'installment_number': 1,
                'description': 'Full Payment',
                'due_date': start_date,
                'amount': total_amount
            })
        elif self.deposit_percent > 0:
            # Deposit + installments
            deposit = total_amount * (self.deposit_percent / 100)
            remaining = total_amount - deposit
            
            schedule.append({
                'installment_number': 1,
                'description': f'Deposit ({self.deposit_percent}%)',
                'due_date': start_date,
                'amount': deposit.quantize(Decimal('0.01'))
            })
            
            # Remaining installments
            monthly_amount = remaining / (self.installments - 1)
            for i in range(2, self.installments + 1):
                due_date = start_date + relativedelta(months=(i - 1))
                schedule.append({
                    'installment_number': i,
                    'description': f'Installment {i - 1} of {self.installments - 1}',
                    'due_date': due_date,
                    'amount': monthly_amount.quantize(Decimal('0.01'))
                })
        else:
            # Equal installments
            monthly_amount = total_amount / self.installments
            for i in range(1, self.installments + 1):
                due_date = start_date + relativedelta(months=(i - 1))
                schedule.append({
                    'installment_number': i,
                    'description': f'Installment {i} of {self.installments}',
                    'due_date': due_date,
                    'amount': monthly_amount.quantize(Decimal('0.01'))
                })
        
        return schedule


class QuoteTemplate(TenantAwareModel):
    """
    Reusable quote templates that sales agents select when creating quotes.
    Supports global templates with optional campus-level overrides (inherit and extend).
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    # Template content
    default_terms = models.TextField(
        blank=True,
        help_text="Default terms and conditions"
    )
    header_text = models.TextField(
        blank=True,
        help_text="Header text appearing at top of quote"
    )
    footer_text = models.TextField(
        blank=True,
        help_text="Footer text appearing at bottom of quote"
    )
    
    # Inheritance - for campus-specific overrides
    parent_template = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='child_templates',
        help_text="Parent template to inherit from (for campus overrides)"
    )
    
    # Available payment options
    payment_options = models.ManyToManyField(
        PaymentOption,
        related_name='templates',
        blank=True,
        help_text="Payment options available with this template"
    )
    
    # Quote settings
    validity_hours = models.PositiveIntegerField(
        default=48,
        help_text="How long quotes remain valid (in hours)"
    )
    
    # Optional campus restriction
    campus = models.ForeignKey(
        'tenants.Campus',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='quote_templates',
        help_text="If set, template only available for this campus"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Quote Template'
        verbose_name_plural = 'Quote Templates'
    
    def __str__(self):
        if self.campus:
            return f"{self.name} ({self.campus.name})"
        return self.name
    
    def get_effective_terms(self):
        """Get terms, inheriting from parent if not set"""
        if self.default_terms:
            return self.default_terms
        if self.parent_template:
            return self.parent_template.get_effective_terms()
        return ""
    
    def get_effective_header(self):
        """Get header text, inheriting from parent if not set"""
        if self.header_text:
            return self.header_text
        if self.parent_template:
            return self.parent_template.get_effective_header()
        return ""
    
    def get_effective_footer(self):
        """Get footer text, inheriting from parent if not set"""
        if self.footer_text:
            return self.footer_text
        if self.parent_template:
            return self.parent_template.get_effective_footer()
        return ""
    
    def get_effective_payment_options(self):
        """Get payment options, inheriting from parent if none set"""
        own_options = self.payment_options.filter(is_active=True)
        if own_options.exists():
            return own_options
        if self.parent_template:
            return self.parent_template.get_effective_payment_options()
        return PaymentOption.objects.filter(is_active=True)
    
    def get_effective_validity_hours(self):
        """Get validity hours, using parent's if not explicitly set"""
        if self.validity_hours != 48:  # Non-default value
            return self.validity_hours
        if self.parent_template:
            return self.parent_template.get_effective_validity_hours()
        return self.validity_hours
    
    @classmethod
    def get_for_campus(cls, campus=None):
        """
        Get templates available for a campus.
        Returns campus-specific templates + global templates (no campus set).
        """
        qs = cls.objects.filter(is_active=True)
        if campus:
            return qs.filter(
                models.Q(campus=campus) | models.Q(campus__isnull=True)
            ).order_by('sort_order', 'name')
        return qs.filter(campus__isnull=True).order_by('sort_order', 'name')


class Invoice(TenantAwareModel):
    """
    Invoice for learners or corporates
    """
    INVOICE_TYPES = [
        ('LEARNER', 'Learner Invoice'),
        ('CORPORATE', 'Corporate Invoice'),
        ('SETA', 'SETA Invoice'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('PARTIAL', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPES)
    
    # Client - either learner, corporate, or SETA
    learner = models.ForeignKey(
        'learners.Learner', 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='invoices'
    )
    corporate_client = models.ForeignKey(
        'corporate.CorporateClient', 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='invoices'
    )
    
    # Link to enrollment
    enrollment = models.ForeignKey(
        'academics.Enrollment', 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='invoices'
    )
    
    # From quote
    quote = models.ForeignKey(
        Quote, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='invoices'
    )
    
    # Link to tranche (for SETA claims)
    tranche = models.ForeignKey(
        'core.TrancheSchedule',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='invoices',
        help_text='Link invoice to a tranche for SETA funding claims'
    )
    
    # Dates
    invoice_date = models.DateField()
    due_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Billing info
    billing_name = models.CharField(max_length=200)
    billing_address = models.TextField(blank=True)
    billing_vat_number = models.CharField(max_length=20, blank=True)
    billing_email = models.EmailField(blank=True)
    
    # Totals
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    vat_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    discount_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    total = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    amount_paid = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Sage Intacct sync
    sage_synced = models.BooleanField(default=False)
    sage_invoice_id = models.CharField(max_length=50, blank=True)
    sage_synced_at = models.DateTimeField(null=True, blank=True)
    sage_sync_error = models.TextField(blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-invoice_date']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['invoice_number']),
        ]
    
    def __str__(self):
        return self.invoice_number
    
    @property
    def balance_due(self):
        return self.total - self.amount_paid
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.status not in ['PAID', 'CANCELLED', 'REFUNDED'] and self.due_date < timezone.now().date()


class InvoiceLineItem(models.Model):
    """
    Invoice line items
    """
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='line_items'
    )
    
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    vat_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('15.00')
    )
    
    # Links
    qualification = models.ForeignKey(
        'academics.Qualification', 
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    module = models.ForeignKey(
        'academics.Module', 
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    
    # Sage Intacct
    sage_line_id = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['id']
        verbose_name = 'Invoice Line Item'
        verbose_name_plural = 'Invoice Line Items'
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description}"
    
    @property
    def line_subtotal(self):
        base = self.quantity * self.unit_price
        discount = base * (self.discount_percent / 100)
        return base - discount
    
    @property
    def line_vat(self):
        return self.line_subtotal * (self.vat_rate / 100)
    
    @property
    def line_total(self):
        return self.line_subtotal + self.line_vat


class Payment(TenantAwareModel):
    """
    Payment record
    """
    PAYMENT_METHODS = [
        ('EFT', 'EFT/Bank Transfer'),
        ('CARD', 'Credit/Debit Card'),
        ('CASH', 'Cash'),
        ('CHEQUE', 'Cheque'),
        ('BURSARY', 'Bursary'),
        ('SETA', 'SETA Payment'),
        ('CORPORATE', 'Corporate Payment'),
        ('PAYFAST', 'PayFast'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('REVERSED', 'Reversed'),
        ('REFUNDED', 'Refunded'),
    ]
    
    payment_reference = models.CharField(max_length=50, unique=True)
    
    # Link to invoice
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    
    # Payment details
    payment_date = models.DateField()
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # External references
    external_reference = models.CharField(max_length=100, blank=True)  # Bank ref, PayFast ref
    payfast_payment_id = models.CharField(max_length=100, blank=True)
    
    # Sage Intacct sync
    sage_synced = models.BooleanField(default=False)
    sage_payment_id = models.CharField(max_length=50, blank=True)
    sage_synced_at = models.DateTimeField(null=True, blank=True)
    sage_sync_error = models.TextField(blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['status', 'payment_date']),
            models.Index(fields=['payment_reference']),
        ]
    
    def __str__(self):
        return f"{self.payment_reference} - R{self.amount}"


class CreditNote(TenantAwareModel):
    """
    Credit note for refunds/adjustments
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('APPROVED', 'Approved'),
        ('APPLIED', 'Applied'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    credit_note_number = models.CharField(max_length=50, unique=True)
    
    # Link to original invoice
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='credit_notes'
    )
    
    # Dates
    credit_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Amount
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    
    # Sage sync
    sage_synced = models.BooleanField(default=False)
    sage_credit_note_id = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['-credit_date']
        verbose_name = 'Credit Note'
        verbose_name_plural = 'Credit Notes'
    
    def __str__(self):
        return self.credit_note_number


class PaymentPlan(TenantAwareModel):
    """
    Payment plan for learners
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('DEFAULTED', 'Defaulted'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    learner = models.ForeignKey(
        'learners.Learner', 
        on_delete=models.CASCADE, 
        related_name='payment_plans'
    )
    enrollment = models.ForeignKey(
        'academics.Enrollment', 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='payment_plans'
    )
    
    # Plan details
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    installment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    number_of_installments = models.PositiveIntegerField()
    
    # Schedule
    start_date = models.DateField()
    payment_day = models.PositiveIntegerField()  # Day of month
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    # Agreement
    signed_agreement = models.FileField(
        upload_to='payment_plans/',
        blank=True
    )
    signed_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Payment Plan'
        verbose_name_plural = 'Payment Plans'
    
    def __str__(self):
        return f"{self.learner} - {self.total_amount}"


class PaymentPlanInstallment(models.Model):
    """
    Individual installment in a payment plan
    """
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('INVOICED', 'Invoiced'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('SKIPPED', 'Skipped'),
    ]
    
    payment_plan = models.ForeignKey(
        PaymentPlan, 
        on_delete=models.CASCADE, 
        related_name='installments'
    )
    
    installment_number = models.PositiveIntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='SCHEDULED'
    )
    
    # Link to invoice/payment
    invoice = models.ForeignKey(
        Invoice, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='installments'
    )
    payment = models.ForeignKey(
        Payment, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='installments'
    )
    
    paid_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['payment_plan', 'installment_number']
        unique_together = ['payment_plan', 'installment_number']
        verbose_name = 'Payment Plan Installment'
        verbose_name_plural = 'Payment Plan Installments'
    
    def __str__(self):
        return f"{self.payment_plan} - Installment {self.installment_number}"


class SageIntacctConfig(models.Model):
    """
    Sage Intacct API configuration per brand
    """
    brand = models.OneToOneField(
        'tenants.Brand', 
        on_delete=models.CASCADE, 
        related_name='sage_config'
    )
    
    # API credentials
    sender_id = models.CharField(max_length=100)
    sender_password = models.TextField()  # Encrypted
    company_id = models.CharField(max_length=50)
    user_id = models.CharField(max_length=50)
    user_password = models.TextField()  # Encrypted
    
    # Endpoint
    endpoint_url = models.URLField(
        default='https://api.intacct.com/ia/xml/xmlgw.phtml'
    )
    
    # Mapping
    customer_dimension = models.CharField(max_length=50, default='CUSTOMER')
    location_id = models.CharField(max_length=50, blank=True)
    department_id = models.CharField(max_length=50, blank=True)
    
    # Revenue account mappings
    revenue_account_qualification = models.CharField(max_length=50, blank=True)
    revenue_account_assessment = models.CharField(max_length=50, blank=True)
    revenue_account_material = models.CharField(max_length=50, blank=True)
    
    # Status
    is_active = models.BooleanField(default=False)
    last_sync = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=50, blank=True)
    
    class Meta:
        verbose_name = 'Sage Intacct Config'
        verbose_name_plural = 'Sage Intacct Configs'
    
    def __str__(self):
        return f"Sage Intacct - {self.brand.name}"


class SageSyncLog(AuditedModel):
    """
    Log of Sage Intacct sync operations
    """
    SYNC_TYPES = [
        ('INVOICE', 'Invoice'),
        ('PAYMENT', 'Payment'),
        ('CREDIT_NOTE', 'Credit Note'),
        ('CUSTOMER', 'Customer'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('SKIPPED', 'Skipped'),
    ]
    
    config = models.ForeignKey(
        SageIntacctConfig, 
        on_delete=models.CASCADE, 
        related_name='sync_logs'
    )
    
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    direction = models.CharField(max_length=10)  # PUSH or PULL
    
    # Reference to synced record
    invoice = models.ForeignKey(
        Invoice, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='sage_sync_logs'
    )
    payment = models.ForeignKey(
        Payment, 
        null=True, blank=True,
        on_delete=models.SET_NULL, 
        related_name='sage_sync_logs'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Sage response
    sage_record_id = models.CharField(max_length=50, blank=True)
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sage Sync Log'
        verbose_name_plural = 'Sage Sync Logs'
    
    def __str__(self):
        return f"{self.sync_type} - {self.status} - {self.created_at}"


class BursaryProvider(AuditedModel):
    """
    External bursary, grant, or loan providers.
    e.g., NSFAS, private foundations, corporate bursary programs, banks
    """
    
    PROVIDER_TYPE_CHOICES = [
        ('NSFAS', 'NSFAS'),
        ('SETA', 'SETA Bursary'),
        ('CORPORATE', 'Corporate Bursary'),
        ('FOUNDATION', 'Private Foundation'),
        ('GOVERNMENT', 'Government Grant'),
        ('BANK', 'Bank Learner Loan'),
        ('INTERNAL', 'Internal Bursary'),
        ('OTHER', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    provider_type = models.CharField(max_length=20, choices=PROVIDER_TYPE_CHOICES)
    
    # Contact details
    contact_person = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Address
    address = models.TextField(blank=True)
    
    # Requirements and coverage
    requirements = models.TextField(
        blank=True,
        help_text="Eligibility requirements for this bursary"
    )
    covers_tuition = models.BooleanField(default=True)
    covers_registration = models.BooleanField(default=True)
    covers_materials = models.BooleanField(default=False)
    covers_accommodation = models.BooleanField(default=False)
    covers_stipend = models.BooleanField(default=False)
    
    # Limits
    max_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text="Maximum amount per learner"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Bursary Provider'
        verbose_name_plural = 'Bursary Providers'
    
    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"


class BursaryApplication(AuditedModel):
    """
    Individual learner bursary/loan application.
    Tracks the application process and approval status.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('DOCUMENTS_REQUIRED', 'Documents Required'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CONTRACT_PENDING', 'Contract Pending'),
        ('CONTRACT_SIGNED', 'Contract Signed'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Reference
    application_number = models.CharField(max_length=30, unique=True, blank=True)
    
    # Relationships
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.CASCADE,
        related_name='bursary_applications'
    )
    provider = models.ForeignKey(
        BursaryProvider,
        on_delete=models.PROTECT,
        related_name='applications'
    )
    
    # Application details
    application_date = models.DateField()
    external_reference = models.CharField(
        max_length=50, blank=True,
        help_text="Reference number from the provider"
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    status_changed_date = models.DateField(null=True, blank=True)
    
    # Financial details
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2)
    amount_approved = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True
    )
    
    # Coverage (what the bursary will cover)
    covers_tuition = models.BooleanField(default=True)
    covers_registration = models.BooleanField(default=False)
    covers_materials = models.BooleanField(default=False)
    covers_accommodation = models.BooleanField(default=False)
    covers_stipend = models.BooleanField(default=False)
    
    # Contract details (for approved bursaries)
    contract_signed = models.BooleanField(default=False)
    contract_signed_date = models.DateField(null=True, blank=True)
    contract_file = models.FileField(
        upload_to='bursary_contracts/',
        null=True, blank=True
    )
    contract_expiry = models.DateField(null=True, blank=True)
    
    # Terms and conditions
    repayment_required = models.BooleanField(
        default=False,
        help_text="Does this bursary need to be repaid (e.g., if learner fails)?"
    )
    service_obligation = models.BooleanField(
        default=False,
        help_text="Is there a work-back obligation?"
    )
    obligation_terms = models.TextField(
        blank=True,
        help_text="Terms of repayment or service obligation"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-application_date']
        verbose_name = 'Bursary Application'
        verbose_name_plural = 'Bursary Applications'
    
    def __str__(self):
        return f"{self.application_number} - {self.learner} - {self.provider.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate application number
        if not self.application_number:
            from datetime import date
            year = date.today().year
            prefix = f"BUR-{year}-"
            last = BursaryApplication.objects.filter(
                application_number__startswith=prefix
            ).order_by('-application_number').first()
            if last:
                try:
                    num = int(last.application_number.split('-')[-1]) + 1
                except ValueError:
                    num = 1
            else:
                num = 1
            self.application_number = f"{prefix}{num:05d}"
        super().save(*args, **kwargs)
    
    @property
    def is_approved_and_active(self):
        """Check if bursary is approved and contract is signed"""
        return self.status in ['CONTRACT_SIGNED', 'ACTIVE'] and self.contract_signed


class DebitOrderMandate(AuditedModel):
    """
    Debit order authorization for recurring payments.
    Stores mandate details for learner fee collection.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_SIGNATURE', 'Pending Signature'),
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    ]
    
    ACCOUNT_TYPE_CHOICES = [
        ('CHEQUE', 'Cheque Account'),
        ('SAVINGS', 'Savings Account'),
        ('TRANSMISSION', 'Transmission Account'),
    ]
    
    # Reference
    mandate_number = models.CharField(max_length=30, unique=True, blank=True)
    
    # Relationships
    learner = models.ForeignKey(
        'learners.Learner',
        on_delete=models.CASCADE,
        related_name='debit_order_mandates'
    )
    
    # Account holder (may be parent/guardian)
    account_holder_name = models.CharField(max_length=100)
    account_holder_id = models.CharField(
        max_length=13, blank=True,
        help_text="ID number of account holder"
    )
    relationship_to_learner = models.CharField(
        max_length=50, blank=True,
        help_text="Relationship of account holder to learner (e.g., Parent, Self)"
    )
    
    # Bank details (sensitive - consider encryption in production)
    bank_name = models.CharField(max_length=50)
    branch_code = models.CharField(max_length=10)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    account_number = models.CharField(max_length=20)  # Should be encrypted
    
    # Debit details
    debit_day = models.PositiveIntegerField(
        help_text="Day of month for debit (1-28)"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Monthly debit amount"
    )
    
    # Timeline
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Authorization
    signed_mandate_file = models.FileField(
        upload_to='debit_order_mandates/',
        null=True, blank=True,
        help_text="Signed mandate document"
    )
    signed_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Tracking
    last_debit_date = models.DateField(null=True, blank=True)
    last_debit_status = models.CharField(max_length=20, blank=True)
    failed_debit_count = models.PositiveIntegerField(default=0)
    
    # Notes
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Debit Order Mandate'
        verbose_name_plural = 'Debit Order Mandates'
    
    def __str__(self):
        return f"{self.mandate_number} - {self.learner} - R{self.amount}/month"
    
    def save(self, *args, **kwargs):
        # Auto-generate mandate number
        if not self.mandate_number:
            from datetime import date
            year = date.today().year
            prefix = f"DOM-{year}-"
            last = DebitOrderMandate.objects.filter(
                mandate_number__startswith=prefix
            ).order_by('-mandate_number').first()
            if last:
                try:
                    num = int(last.mandate_number.split('-')[-1]) + 1
                except ValueError:
                    num = 1
            else:
                num = 1
            self.mandate_number = f"{prefix}{num:05d}"
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        """Check if mandate is currently active"""
        from datetime import date
        if self.status != 'ACTIVE':
            return False
        if self.end_date and self.end_date < date.today():
            return False
        return True


# =====================================================
# COURSE PRICING MANAGEMENT SYSTEM
# =====================================================

class PricingStrategy(AuditedModel):
    """
    Named pricing strategies that define scope and priority for price resolution.
    Strategies can be brand-wide, regional, campus-specific, or corporate-specific.
    """
    STRATEGY_TYPES = [
        ('STANDARD', 'Standard (Brand Default)'),
        ('REGIONAL', 'Regional Variation'),
        ('CAMPUS', 'Campus-Specific'),
        ('CORPORATE', 'Corporate Client'),
        ('PROMOTIONAL', 'Promotional/Seasonal'),
    ]
    
    name = models.CharField(
        max_length=100,
        help_text='Strategy name (e.g., "Metro Pricing", "Rural Discount")'
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text='Unique code for the strategy'
    )
    description = models.TextField(blank=True)
    
    strategy_type = models.CharField(
        max_length=20,
        choices=STRATEGY_TYPES,
        default='STANDARD'
    )
    
    # Scope - determines what this strategy applies to
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='pricing_strategies',
        help_text='Brand this strategy belongs to'
    )
    
    # Optional scope narrowing
    region = models.ForeignKey(
        'core.Region',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='pricing_strategies',
        help_text='Region for REGIONAL type strategies'
    )
    campus = models.ForeignKey(
        'tenants.Campus',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='pricing_strategies',
        help_text='Campus for CAMPUS type strategies'
    )
    corporate_client = models.ForeignKey(
        'corporate.CorporateClient',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='pricing_strategies',
        help_text='Corporate client for CORPORATE type strategies'
    )
    
    # Priority for resolution (higher = checked first)
    priority = models.PositiveIntegerField(
        default=0,
        help_text='Higher priority strategies are applied first in price resolution'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text='Default strategy for this brand (only one per brand)'
    )
    
    class Meta:
        ordering = ['-priority', 'name']
        verbose_name = 'Pricing Strategy'
        verbose_name_plural = 'Pricing Strategies'
        indexes = [
            models.Index(fields=['brand', 'strategy_type', 'is_active']),
            models.Index(fields=['priority']),
        ]
    
    def __str__(self):
        return f"{self.brand.code} - {self.name} ({self.get_strategy_type_display()})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default per brand
        if self.is_default:
            PricingStrategy.objects.filter(
                brand=self.brand,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    def clean(self):
        from django.core.exceptions import ValidationError
        # Validate scope matches strategy type
        if self.strategy_type == 'REGIONAL' and not self.region:
            raise ValidationError({'region': 'Region is required for REGIONAL strategy type'})
        if self.strategy_type == 'CAMPUS' and not self.campus:
            raise ValidationError({'campus': 'Campus is required for CAMPUS strategy type'})
        if self.strategy_type == 'CORPORATE' and not self.corporate_client:
            raise ValidationError({'corporate_client': 'Corporate client is required for CORPORATE strategy type'})


class CoursePricing(AuditedModel):
    """
    All-inclusive product pricing for a qualification.
    Supports versioning, multi-year pricing, deposits, and approval workflow.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('ACTIVE', 'Active'),
        ('SUPERSEDED', 'Superseded'),
        ('ARCHIVED', 'Archived'),
    ]
    
    # Link to qualification/course
    qualification = models.ForeignKey(
        'academics.Qualification',
        on_delete=models.CASCADE,
        related_name='pricing_versions'
    )
    
    # Strategy determines scope (brand, region, campus, corporate)
    pricing_strategy = models.ForeignKey(
        PricingStrategy,
        on_delete=models.PROTECT,
        related_name='course_pricing',
        help_text='Pricing strategy that determines scope and priority'
    )
    
    # Version tracking
    version = models.PositiveIntegerField(default=1)
    version_notes = models.TextField(
        blank=True,
        help_text='Notes about this version (e.g., "2026 annual increase")'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Effective dates - supports future pricing up to 4+ years
    effective_from = models.DateField(
        help_text='Date this pricing becomes effective'
    )
    effective_to = models.DateField(
        null=True, blank=True,
        help_text='Date this pricing expires (null = no end date)'
    )
    
    # ===== ALL-INCLUSIVE TOTAL PRICING =====
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Total all-inclusive course price (excl. VAT)'
    )
    
    # ===== DEPOSIT CONFIGURATION =====
    deposit_required = models.BooleanField(default=True)
    deposit_type = models.CharField(
        max_length=10,
        choices=[('FIXED', 'Fixed Amount'), ('PERCENTAGE', 'Percentage of Total')],
        default='FIXED'
    )
    deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Fixed deposit amount (if deposit_type=FIXED)'
    )
    deposit_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        help_text='Deposit as percentage of total (if deposit_type=PERCENTAGE)'
    )
    
    # ===== FEE BREAKDOWN (included in total) =====
    registration_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='One-time registration fee (included in total)'
    )
    material_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Learning materials fee (included in total)'
    )
    assessment_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Assessment/examination fee (included in total)'
    )
    certification_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Certification/graduation fee (included in total)'
    )
    
    # ===== VAT HANDLING =====
    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('15.00'),
        help_text='VAT rate percentage'
    )
    prices_include_vat = models.BooleanField(
        default=False,
        help_text='Are the entered prices VAT inclusive?'
    )
    
    # ===== EARLY BIRD / PROMOTIONAL =====
    early_bird_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Early bird discount percentage'
    )
    early_bird_deadline_days = models.PositiveIntegerField(
        default=0,
        help_text='Days before course start for early bird eligibility'
    )
    
    # ===== APPROVAL WORKFLOW =====
    submitted_by = models.ForeignKey(
        'core.User',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='submitted_course_pricing'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'core.User',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_course_pricing'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Previous version link for superseded pricing
    previous_version = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='next_versions'
    )
    
    class Meta:
        ordering = ['-effective_from', '-version']
        verbose_name = 'Course Pricing'
        verbose_name_plural = 'Course Pricing'
        unique_together = [['qualification', 'pricing_strategy', 'version']]
        indexes = [
            models.Index(fields=['qualification', 'pricing_strategy', 'status']),
            models.Index(fields=['effective_from', 'effective_to']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.qualification.short_name} - {self.pricing_strategy.name} v{self.version}"
    
    # ===== CALCULATED PROPERTIES =====
    
    @property
    def total_price_vat_inclusive(self):
        """Calculate VAT-inclusive total price"""
        if self.prices_include_vat:
            return self.total_price
        vat_multiplier = 1 + (self.vat_rate / 100)
        return round(self.total_price * vat_multiplier, 2)
    
    @property
    def total_price_vat_exclusive(self):
        """Calculate VAT-exclusive total price"""
        if not self.prices_include_vat:
            return self.total_price
        vat_divisor = 1 + (self.vat_rate / 100)
        return round(self.total_price / vat_divisor, 2)
    
    @property
    def vat_amount(self):
        """Calculate the VAT amount"""
        return self.total_price_vat_inclusive - self.total_price_vat_exclusive
    
    @property
    def calculated_deposit(self):
        """Calculate the actual deposit amount"""
        if not self.deposit_required:
            return Decimal('0.00')
        if self.deposit_type == 'PERCENTAGE':
            return round((self.total_price_vat_inclusive * self.deposit_percentage) / 100, 2)
        return self.deposit_amount
    
    @property
    def balance_after_deposit(self):
        """Calculate balance remaining after deposit"""
        return self.total_price_vat_inclusive - self.calculated_deposit
    
    @property
    def tuition_fee(self):
        """Calculate tuition (total minus other fees)"""
        other_fees = self.registration_fee + self.material_fee + self.assessment_fee + self.certification_fee
        return max(self.total_price - other_fees, Decimal('0.00'))
    
    @property
    def is_current(self):
        """Check if this pricing is currently active"""
        from datetime import date
        today = date.today()
        if self.status != 'ACTIVE':
            return False
        if self.effective_from > today:
            return False
        if self.effective_to and self.effective_to < today:
            return False
        return True
    
    @property
    def is_future(self):
        """Check if this is future pricing (not yet effective)"""
        from datetime import date
        return self.effective_from > date.today()
    
    @property
    def brand(self):
        """Get brand through pricing strategy"""
        return self.pricing_strategy.brand
    
    # ===== WORKFLOW METHODS =====
    
    def submit_for_approval(self, user):
        """Submit pricing for approval"""
        if self.status != 'DRAFT':
            raise ValueError('Only DRAFT pricing can be submitted for approval')
        self.status = 'PENDING_APPROVAL'
        self.submitted_by = user
        self.submitted_at = timezone.now()
        self.save()
        self._create_history_entry('SUBMITTED', user, 'Submitted for approval')
    
    def approve(self, user, notes=''):
        """Approve the pricing"""
        if self.status != 'PENDING_APPROVAL':
            raise ValueError('Only PENDING_APPROVAL pricing can be approved')
        self.status = 'APPROVED'
        self.approved_by = user
        self.approved_at = timezone.now()
        if notes:
            self.version_notes = f"{self.version_notes}\nApproval notes: {notes}".strip()
        self.save()
        self._create_history_entry('APPROVED', user, f'Approved. {notes}'.strip())
    
    def reject(self, user, reason):
        """Reject the pricing"""
        if self.status != 'PENDING_APPROVAL':
            raise ValueError('Only PENDING_APPROVAL pricing can be rejected')
        self.status = 'DRAFT'
        self.rejection_reason = reason
        self.save()
        self._create_history_entry('REJECTED', user, f'Rejected: {reason}')
    
    def activate(self, user):
        """Activate the pricing (make it live)"""
        if self.status not in ('APPROVED', 'DRAFT'):
            raise ValueError('Only APPROVED or DRAFT pricing can be activated')
        
        from datetime import date
        # Supersede any currently active pricing for same qual/strategy
        CoursePricing.objects.filter(
            qualification=self.qualification,
            pricing_strategy=self.pricing_strategy,
            status='ACTIVE'
        ).exclude(pk=self.pk).update(status='SUPERSEDED')
        
        self.status = 'ACTIVE'
        if not self.approved_by:
            self.approved_by = user
            self.approved_at = timezone.now()
        self.save()
        self._create_history_entry('ACTIVATED', user, 'Activated')
    
    def _create_history_entry(self, change_type, user, reason=''):
        """Create a history entry for this pricing"""
        CoursePricingHistory.objects.create(
            pricing=self,
            change_type=change_type,
            changed_by=user,
            new_total_price=self.total_price,
            new_status=self.status,
            change_reason=reason,
            snapshot=self._get_snapshot()
        )
    
    def _get_snapshot(self):
        """Get a JSON snapshot of current pricing state"""
        return {
            'total_price': str(self.total_price),
            'deposit_amount': str(self.deposit_amount),
            'deposit_percentage': str(self.deposit_percentage),
            'registration_fee': str(self.registration_fee),
            'material_fee': str(self.material_fee),
            'assessment_fee': str(self.assessment_fee),
            'certification_fee': str(self.certification_fee),
            'vat_rate': str(self.vat_rate),
            'effective_from': str(self.effective_from),
            'effective_to': str(self.effective_to) if self.effective_to else None,
            'status': self.status,
            'version': self.version,
        }
    
    # ===== CLASS METHODS =====
    
    @classmethod
    def get_active_pricing(cls, qualification, pricing_strategy=None, brand=None, as_of_date=None):
        """
        Get the active pricing for a qualification.
        If pricing_strategy is provided, get pricing for that specific strategy.
        Otherwise, find the default strategy for the brand.
        """
        from datetime import date
        from django.db.models import Q
        
        target_date = as_of_date or date.today()
        
        queryset = cls.objects.filter(
            qualification=qualification,
            status='ACTIVE',
            effective_from__lte=target_date
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=target_date)
        )
        
        if pricing_strategy:
            queryset = queryset.filter(pricing_strategy=pricing_strategy)
        elif brand:
            queryset = queryset.filter(pricing_strategy__brand=brand)
        
        return queryset.order_by('-pricing_strategy__priority', '-effective_from').first()
    
    @classmethod
    def create_new_version(cls, existing_pricing, user):
        """Create a new version based on existing pricing"""
        new_pricing = cls.objects.get(pk=existing_pricing.pk)
        new_pricing.pk = None
        new_pricing.version = existing_pricing.version + 1
        new_pricing.status = 'DRAFT'
        new_pricing.previous_version = existing_pricing
        new_pricing.submitted_by = None
        new_pricing.submitted_at = None
        new_pricing.approved_by = None
        new_pricing.approved_at = None
        new_pricing.rejection_reason = ''
        new_pricing.created_by = user
        new_pricing.save()
        
        # Copy yearly pricing
        for yearly in existing_pricing.yearly_pricing.all():
            yearly.pk = None
            yearly.pricing = new_pricing
            yearly.save()
        
        # Copy payment terms
        for term in existing_pricing.available_payment_terms.all():
            term.pk = None
            term.pricing = new_pricing
            term.save()
        
        return new_pricing


class CoursePricingYear(models.Model):
    """
    Per-year pricing breakdown for multi-year qualifications.
    E.g., a 3-year qualification might have different fees per year of study.
    """
    pricing = models.ForeignKey(
        CoursePricing,
        on_delete=models.CASCADE,
        related_name='yearly_pricing'
    )
    
    year_number = models.PositiveIntegerField(
        help_text='Year of study (1, 2, 3, etc.)'
    )
    year_label = models.CharField(
        max_length=50,
        blank=True,
        help_text='Optional label (e.g., "Foundation Year", "Specialization Year")'
    )
    
    # Year-specific fee breakdown
    tuition_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Tuition fee for this year'
    )
    material_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Material fee for this year'
    )
    assessment_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Assessment/exam fee for this year'
    )
    other_fees = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Any other fees for this year'
    )
    
    # Credits/units to complete this year
    credits = models.PositiveIntegerField(
        default=0,
        help_text='Credits to be completed this year'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['pricing', 'year_number']
        verbose_name = 'Course Pricing Year'
        verbose_name_plural = 'Course Pricing Years'
        unique_together = [['pricing', 'year_number']]
    
    def __str__(self):
        label = self.year_label or f"Year {self.year_number}"
        return f"{self.pricing.qualification.short_name} - {label}"
    
    @property
    def total_year_fee(self):
        """Calculate total fee for this year"""
        return self.tuition_fee + self.material_fee + self.assessment_fee + self.other_fees


class CoursePricingOverride(models.Model):
    """
    Price overrides that allow adjustments from base pricing.
    Used to apply regional modifiers or campus-specific adjustments.
    """
    OVERRIDE_TYPES = [
        ('FIXED', 'Fixed Price Override'),
        ('MODIFIER', 'Percentage Modifier'),
        ('DISCOUNT', 'Fixed Discount'),
        ('DISCOUNT_PERCENT', 'Percentage Discount'),
    ]
    
    pricing = models.ForeignKey(
        CoursePricing,
        on_delete=models.CASCADE,
        related_name='overrides'
    )
    
    # Target scope for this override
    target_strategy = models.ForeignKey(
        PricingStrategy,
        on_delete=models.CASCADE,
        related_name='price_overrides',
        help_text='The strategy this override applies to'
    )
    
    override_type = models.CharField(max_length=20, choices=OVERRIDE_TYPES)
    
    # Override values (use one based on type)
    override_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True, blank=True,
        help_text='Fixed override price (for FIXED type)'
    )
    modifier_percent = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True, blank=True,
        help_text='Percentage modifier (for MODIFIER type, e.g., 110 = +10%)'
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True,
        help_text='Fixed discount amount (for DISCOUNT type)'
    )
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True, blank=True,
        help_text='Discount percentage (for DISCOUNT_PERCENT type)'
    )
    
    reason = models.TextField(blank=True, help_text='Reason for this override')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['pricing', 'target_strategy']
        verbose_name = 'Course Pricing Override'
        verbose_name_plural = 'Course Pricing Overrides'
        unique_together = [['pricing', 'target_strategy']]
    
    def __str__(self):
        return f"{self.pricing} → {self.target_strategy.name}"
    
    def calculate_price(self, base_price):
        """Apply this override to a base price"""
        if self.override_type == 'FIXED' and self.override_price:
            return self.override_price
        elif self.override_type == 'MODIFIER' and self.modifier_percent:
            return round(base_price * (self.modifier_percent / 100), 2)
        elif self.override_type == 'DISCOUNT' and self.discount_amount:
            return max(base_price - self.discount_amount, Decimal('0.00'))
        elif self.override_type == 'DISCOUNT_PERCENT' and self.discount_percent:
            discount = base_price * (self.discount_percent / 100)
            return round(base_price - discount, 2)
        return base_price


class PaymentTerm(AuditedModel):
    """
    Payment term templates that define how courses can be paid for.
    E.g., Full Payment, Monthly x12, Quarterly x4, etc.
    """
    PAYMENT_TYPES = [
        ('FULL', 'Full Payment'),
        ('DEPOSIT_BALANCE', 'Deposit + Balance'),
        ('MONTHLY', 'Monthly Instalments'),
        ('QUARTERLY', 'Quarterly Instalments'),
        ('PER_SEMESTER', 'Per Semester'),
        ('PER_YEAR', 'Per Year'),
        ('CUSTOM', 'Custom Schedule'),
    ]
    
    name = models.CharField(
        max_length=100,
        help_text='Term name (e.g., "Monthly x12", "Upfront Payment")'
    )
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    
    # Instalment configuration
    number_of_instalments = models.PositiveIntegerField(
        default=1,
        help_text='Total number of payments (including deposit if separate)'
    )
    instalment_frequency_days = models.PositiveIntegerField(
        default=30,
        help_text='Days between instalments (e.g., 30 for monthly)'
    )
    
    # Deposit handling
    deposit_with_application = models.BooleanField(
        default=True,
        help_text='Is deposit required with application?'
    )
    balance_due_before_start = models.BooleanField(
        default=False,
        help_text='Must full balance be paid before course starts?'
    )
    balance_due_days = models.PositiveIntegerField(
        default=0,
        help_text='Days before course start that balance is due (if applicable)'
    )
    
    # Discounts for this payment term
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Discount for choosing this term (e.g., 5% for upfront payment)'
    )
    
    # Admin/interest charges
    admin_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Admin fee for this payment term'
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Interest rate for instalment plans (annual %)'
    )
    
    # Availability restrictions
    is_active = models.BooleanField(default=True)
    available_for_self_funded = models.BooleanField(
        default=True,
        help_text='Available for self-paying learners'
    )
    available_for_sponsored = models.BooleanField(
        default=True,
        help_text='Available for sponsored/corporate learners'
    )
    min_course_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Minimum course value for this term to be available'
    )
    max_course_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True,
        help_text='Maximum course value for this term (null = no max)'
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Payment Term'
        verbose_name_plural = 'Payment Terms'
    
    def __str__(self):
        return f"{self.name} ({self.get_payment_type_display()})"
    
    def calculate_instalment_amount(self, total_amount, deposit_amount=Decimal('0.00')):
        """
        Calculate the instalment amount after deposit.
        Returns the per-instalment amount.
        """
        balance = total_amount - deposit_amount
        
        # Apply interest if any (simple interest for now)
        if self.interest_rate > 0:
            # Spread interest over payment period
            months = self.number_of_instalments
            annual_interest = balance * (self.interest_rate / 100)
            interest = (annual_interest / 12) * months
            balance += interest
        
        # Add admin fee
        balance += self.admin_fee
        
        # Apply discount
        if self.discount_percentage > 0:
            discount = balance * (self.discount_percentage / 100)
            balance -= discount
        
        if self.payment_type == 'FULL':
            return balance
        
        # Calculate number of instalments excluding deposit
        instalments = self.number_of_instalments
        if self.deposit_with_application and deposit_amount > 0:
            instalments = max(instalments - 1, 1)
        
        return round(balance / instalments, 2)
    
    def get_payment_schedule(self, total_amount, deposit_amount, start_date):
        """
        Generate a payment schedule based on this term.
        Returns list of (date, amount, description) tuples.
        """
        from datetime import timedelta
        schedule = []
        
        # Deposit payment
        if self.deposit_with_application and deposit_amount > 0:
            schedule.append({
                'date': start_date,
                'amount': deposit_amount,
                'description': 'Deposit',
                'is_deposit': True,
            })
        
        # Calculate instalment amount
        instalment = self.calculate_instalment_amount(total_amount, deposit_amount)
        
        # Generate instalment schedule
        instalments = self.number_of_instalments
        if self.deposit_with_application and deposit_amount > 0:
            instalments = max(instalments - 1, 1)
        
        current_date = start_date
        for i in range(instalments):
            if i > 0 or not self.deposit_with_application:
                current_date = start_date + timedelta(days=self.instalment_frequency_days * (i + 1))
            elif i == 0 and self.deposit_with_application:
                current_date = start_date + timedelta(days=self.instalment_frequency_days)
            
            schedule.append({
                'date': current_date,
                'amount': instalment,
                'description': f'Instalment {i + 1} of {instalments}',
                'is_deposit': False,
            })
        
        return schedule


class CoursePricingPaymentTerm(models.Model):
    """
    Links payment terms to specific course pricing.
    Allows different terms per course with optional overrides.
    """
    pricing = models.ForeignKey(
        CoursePricing,
        on_delete=models.CASCADE,
        related_name='available_payment_terms'
    )
    payment_term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.CASCADE,
        related_name='course_pricing'
    )
    
    # Override default values for this specific course
    override_discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True, blank=True,
        help_text='Override the default discount for this course'
    )
    override_instalments = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Override the number of instalments for this course'
    )
    override_admin_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True,
        help_text='Override the admin fee for this course'
    )
    
    is_default = models.BooleanField(
        default=False,
        help_text='Is this the default payment term for this course?'
    )
    is_available = models.BooleanField(
        default=True,
        help_text='Is this payment term available for this course?'
    )
    
    class Meta:
        ordering = ['pricing', '-is_default', 'payment_term__name']
        verbose_name = 'Course Payment Term'
        verbose_name_plural = 'Course Payment Terms'
        unique_together = [['pricing', 'payment_term']]
    
    def __str__(self):
        default = ' (Default)' if self.is_default else ''
        return f"{self.pricing.qualification.short_name} - {self.payment_term.name}{default}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default per pricing
        if self.is_default:
            CoursePricingPaymentTerm.objects.filter(
                pricing=self.pricing,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def effective_discount(self):
        """Get the effective discount (override or default)"""
        if self.override_discount is not None:
            return self.override_discount
        return self.payment_term.discount_percentage
    
    @property
    def effective_instalments(self):
        """Get the effective number of instalments"""
        if self.override_instalments is not None:
            return self.override_instalments
        return self.payment_term.number_of_instalments
    
    @property
    def effective_admin_fee(self):
        """Get the effective admin fee"""
        if self.override_admin_fee is not None:
            return self.override_admin_fee
        return self.payment_term.admin_fee


class CoursePricingHistory(models.Model):
    """
    Audit trail for all pricing changes.
    Records status changes, price updates, and approvals.
    """
    CHANGE_TYPES = [
        ('CREATED', 'Created'),
        ('UPDATED', 'Updated'),
        ('SUBMITTED', 'Submitted for Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('ACTIVATED', 'Activated'),
        ('SUPERSEDED', 'Superseded'),
        ('ARCHIVED', 'Archived'),
    ]
    
    pricing = models.ForeignKey(
        CoursePricing,
        on_delete=models.CASCADE,
        related_name='history'
    )
    
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        'core.User',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='pricing_changes'
    )
    
    # Snapshot of key values at time of change
    old_total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True, blank=True
    )
    new_total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True, blank=True
    )
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    
    # Full snapshot as JSON for complete audit
    snapshot = models.JSONField(
        null=True, blank=True,
        help_text='Complete snapshot of pricing at time of change'
    )
    
    change_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'Course Pricing History'
        verbose_name_plural = 'Course Pricing History'
        indexes = [
            models.Index(fields=['pricing', 'changed_at']),
            models.Index(fields=['change_type']),
        ]
    
    def __str__(self):
        return f"{self.pricing} - {self.get_change_type_display()} ({self.changed_at.strftime('%Y-%m-%d %H:%M')})"


class FuturePricingSchedule(AuditedModel):
    """
    Schedule for automatic future pricing with escalation rules.
    Allows setting prices up to 4+ years in advance with auto-calculation.
    """
    ESCALATION_TYPES = [
        ('FIXED_PERCENT', 'Fixed Percentage'),
        ('CPI_LINKED', 'CPI Linked'),
        ('CUSTOM', 'Custom per Year'),
    ]
    
    name = models.CharField(
        max_length=100,
        help_text='Schedule name (e.g., "2026-2029 Annual Increases")'
    )
    description = models.TextField(blank=True)
    
    brand = models.ForeignKey(
        'tenants.Brand',
        on_delete=models.CASCADE,
        related_name='future_pricing_schedules'
    )
    
    # Base pricing strategy to apply escalation to
    base_strategy = models.ForeignKey(
        PricingStrategy,
        on_delete=models.CASCADE,
        related_name='future_schedules',
        help_text='The pricing strategy to apply escalation to'
    )
    
    # Year configuration
    base_year = models.PositiveIntegerField(
        help_text='The starting year for this pricing schedule'
    )
    
    # Escalation rules
    escalation_type = models.CharField(
        max_length=20,
        choices=ESCALATION_TYPES,
        default='FIXED_PERCENT'
    )
    default_escalation_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('6.00'),
        help_text='Default annual escalation percentage (auto-filled, can be overridden per year)'
    )
    
    # When to apply new prices
    apply_from_month = models.PositiveIntegerField(
        default=1,
        help_text='Month when new prices take effect (1-12)'
    )
    apply_from_day = models.PositiveIntegerField(
        default=1,
        help_text='Day of month when new prices take effect'
    )
    
    # Approval workflow
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('PENDING_APPROVAL', 'Pending Approval'),
            ('APPROVED', 'Approved'),
            ('APPLIED', 'Applied'),
        ],
        default='DRAFT'
    )
    approved_by = models.ForeignKey(
        'core.User',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_pricing_schedules'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-base_year']
        verbose_name = 'Future Pricing Schedule'
        verbose_name_plural = 'Future Pricing Schedules'
        unique_together = [['brand', 'base_strategy', 'base_year']]
    
    def __str__(self):
        return f"{self.brand.code} - {self.name} ({self.base_year}+)"
    
    def generate_years(self, num_years=4):
        """
        Generate FuturePricingYear entries for the schedule.
        Auto-fills escalation from default, can be manually overridden.
        """
        for offset in range(num_years):
            year = self.base_year + offset
            FuturePricingYear.objects.get_or_create(
                schedule=self,
                year=year,
                defaults={
                    'year_offset': offset,
                    'escalation_percent': self.default_escalation_percent if offset > 0 else Decimal('0.00'),
                }
            )
    
    def calculate_future_price(self, base_price, target_year):
        """
        Calculate the price for a future year based on escalation rules.
        """
        if target_year < self.base_year:
            return base_price
        
        price = base_price
        for year_config in self.years.filter(year__gt=self.base_year, year__lte=target_year).order_by('year'):
            escalation = year_config.escalation_percent / 100
            price = price * (1 + escalation)
        
        return round(price, 2)
    
    def apply_to_pricing(self, user):
        """
        Apply this schedule to create future CoursePricing versions.
        Creates new pricing versions for each year in the schedule.
        """
        from datetime import date
        
        # Get all current active pricing for the base strategy
        current_pricing = CoursePricing.objects.filter(
            pricing_strategy=self.base_strategy,
            status='ACTIVE'
        )
        
        created_count = 0
        for pricing in current_pricing:
            base_price = pricing.total_price
            
            for year_config in self.years.filter(year__gt=self.base_year, is_applied=False).order_by('year'):
                new_price = self.calculate_future_price(base_price, year_config.year)
                effective_date = date(year_config.year, self.apply_from_month, self.apply_from_day)
                
                # Check if pricing already exists for this year
                existing = CoursePricing.objects.filter(
                    qualification=pricing.qualification,
                    pricing_strategy=self.base_strategy,
                    effective_from=effective_date
                ).exists()
                
                if not existing:
                    new_pricing = CoursePricing.objects.create(
                        qualification=pricing.qualification,
                        pricing_strategy=pricing.pricing_strategy,
                        version=1,
                        version_notes=f'Auto-generated from {self.name} ({year_config.escalation_percent}% escalation)',
                        status='APPROVED',
                        effective_from=effective_date,
                        total_price=new_price,
                        deposit_required=pricing.deposit_required,
                        deposit_type=pricing.deposit_type,
                        deposit_amount=pricing.deposit_amount if pricing.deposit_type == 'FIXED' else pricing.deposit_amount,
                        deposit_percentage=pricing.deposit_percentage,
                        registration_fee=round(pricing.registration_fee * (1 + year_config.escalation_percent / 100), 2),
                        material_fee=round(pricing.material_fee * (1 + year_config.escalation_percent / 100), 2),
                        assessment_fee=round(pricing.assessment_fee * (1 + year_config.escalation_percent / 100), 2),
                        certification_fee=round(pricing.certification_fee * (1 + year_config.escalation_percent / 100), 2),
                        vat_rate=pricing.vat_rate,
                        prices_include_vat=pricing.prices_include_vat,
                        approved_by=user,
                        approved_at=timezone.now(),
                        previous_version=pricing,
                        created_by=user,
                    )
                    created_count += 1
        
        # Mark years as applied
        self.years.filter(is_applied=False).update(is_applied=True, applied_at=timezone.now())
        self.status = 'APPLIED'
        self.save()
        
        return created_count


class FuturePricingYear(models.Model):
    """
    Per-year configuration within a future pricing schedule.
    Escalation is auto-filled from schedule default but can be manually overridden.
    """
    schedule = models.ForeignKey(
        FuturePricingSchedule,
        on_delete=models.CASCADE,
        related_name='years'
    )
    
    year = models.PositiveIntegerField(
        help_text='Calendar year this applies to'
    )
    year_offset = models.PositiveIntegerField(
        help_text='Years from base year (0-4+)'
    )
    
    # Escalation for this specific year (auto-filled, manually editable)
    escalation_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text='Escalation percentage for this year (0 for base year)'
    )
    
    # Manual override flag
    is_manually_set = models.BooleanField(
        default=False,
        help_text='Has this escalation been manually overridden?'
    )
    
    # Status tracking
    is_locked = models.BooleanField(
        default=False,
        help_text='Locked years cannot be modified'
    )
    is_applied = models.BooleanField(
        default=False,
        help_text='Has this year pricing been applied?'
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['schedule', 'year']
        verbose_name = 'Future Pricing Year'
        verbose_name_plural = 'Future Pricing Years'
        unique_together = [['schedule', 'year']]
    
    def __str__(self):
        status = '✓' if self.is_applied else '○'
        override = ' (manual)' if self.is_manually_set else ''
        return f"{self.year}: {self.escalation_percent}%{override} {status}"
    
    def save(self, *args, **kwargs):
        # Check if escalation was manually changed
        if self.pk:
            old = FuturePricingYear.objects.filter(pk=self.pk).first()
            if old and old.escalation_percent != self.escalation_percent:
                self.is_manually_set = True
        super().save(*args, **kwargs)


# =====================================================
# BILLING SCHEDULE TEMPLATES & COLLECTION ANALYTICS
# =====================================================

class BillingScheduleTemplate(TenantAwareModel):
    """
    Default billing schedule templates per funder type.
    Applied automatically when NOT is created based on funder.
    """
    FUNDER_CHOICES = [
        ('PRIVATE', 'Private'),
        ('SETA', 'SETA'),
        ('CORPORATE_DG', 'Corporate DG'),
        ('CORPORATE', 'Corporate'),
        ('MUNICIPALITY', 'Municipality'),
        ('GOVERNMENT', 'Government'),
    ]
    
    SCHEDULE_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('DELIVERABLE', 'Based on Deliverables'),
        ('ANNUALLY', 'Annually'),
        ('UPFRONT', 'Upfront (Full Payment)'),
    ]
    
    name = models.CharField(max_length=100)
    funder_type = models.CharField(max_length=30, choices=FUNDER_CHOICES, unique=True)
    default_schedule = models.CharField(max_length=20, choices=SCHEDULE_CHOICES)
    
    # Invoice settings
    invoice_type = models.CharField(
        max_length=20,
        choices=[('PROFORMA', 'Pro Forma'), ('TAX', 'Tax Invoice')],
        default='PROFORMA'
    )
    auto_convert_on_payment = models.BooleanField(
        default=True,
        help_text="Auto-convert pro forma to tax invoice when payment received"
    )
    
    # Payment terms
    payment_terms_days = models.PositiveIntegerField(default=30)
    
    # For monthly billing
    billing_day_of_month = models.PositiveIntegerField(
        default=1,
        help_text="Day of month to generate invoices (1-28)"
    )
    
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['funder_type']
        verbose_name = 'Billing Schedule Template'
        verbose_name_plural = 'Billing Schedule Templates'
    
    def __str__(self):
        return f"{self.get_funder_type_display()} - {self.get_default_schedule_display()}"


class ProjectBillingSchedule(TenantAwareModel):
    """
    Billing schedule for a specific NOT/Project.
    Generated from template or manually configured.
    """
    SCHEDULE_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('DELIVERABLE', 'Based on Deliverables'),
        ('ANNUALLY', 'Annually'),
        ('UPFRONT', 'Upfront (Full Payment)'),
        ('MANUAL', 'Manual Override'),
    ]
    
    training_notification = models.OneToOneField(
        'core.TrainingNotification',
        on_delete=models.CASCADE,
        related_name='project_billing_schedule'
    )
    
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_CHOICES)
    
    # Invoice settings
    invoice_type = models.CharField(
        max_length=20,
        choices=[('PROFORMA', 'Pro Forma'), ('TAX', 'Tax Invoice')],
        default='PROFORMA'
    )
    auto_convert_on_payment = models.BooleanField(default=True)
    
    # Amounts
    total_contract_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    amount_per_period = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Calculated or manually set amount per billing period"
    )
    
    # Schedule details
    billing_start_date = models.DateField(null=True, blank=True)
    billing_end_date = models.DateField(null=True, blank=True)
    billing_day_of_month = models.PositiveIntegerField(default=1)
    payment_terms_days = models.PositiveIntegerField(default=30)
    
    # Automation
    auto_generate = models.BooleanField(default=True)
    last_invoice_generated = models.DateField(null=True, blank=True)
    next_invoice_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Project Billing Schedule'
        verbose_name_plural = 'Project Billing Schedules'
    
    def __str__(self):
        return f"{self.training_notification.reference_number} - {self.get_schedule_type_display()}"
    
    def calculate_periods(self):
        """Calculate number of billing periods based on schedule type"""
        if not self.billing_start_date or not self.billing_end_date:
            return 0
        
        from dateutil.relativedelta import relativedelta
        delta = relativedelta(self.billing_end_date, self.billing_start_date)
        
        if self.schedule_type == 'MONTHLY':
            return delta.years * 12 + delta.months + 1
        elif self.schedule_type == 'QUARTERLY':
            return (delta.years * 12 + delta.months) // 3 + 1
        elif self.schedule_type == 'ANNUALLY':
            return delta.years + 1
        elif self.schedule_type == 'UPFRONT':
            return 1
        return 0


class ScheduledInvoice(TenantAwareModel):
    """
    Pre-scheduled invoices for a project.
    Generated based on billing schedule, tracks generation and payment status.
    """
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('GENERATED', 'Invoice Generated'),
        ('SENT', 'Sent'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    billing_schedule = models.ForeignKey(
        ProjectBillingSchedule,
        on_delete=models.CASCADE,
        related_name='scheduled_invoices'
    )
    
    # Schedule info
    period_number = models.PositiveIntegerField()
    scheduled_date = models.DateField()
    due_date = models.DateField()
    
    # Amounts
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # Link to actual invoice when generated
    invoice = models.ForeignKey(
        Invoice,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='scheduled_invoice_link'
    )
    
    # For deliverable-based billing
    deliverable = models.ForeignKey(
        'core.NOTDeliverable',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='scheduled_invoices'
    )
    
    # Tracking
    generated_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['billing_schedule', 'period_number']
        verbose_name = 'Scheduled Invoice'
        verbose_name_plural = 'Scheduled Invoices'
    
    def __str__(self):
        return f"{self.billing_schedule.training_notification.reference_number} - Period {self.period_number}"


class FunderCollectionMetrics(TenantAwareModel):
    """
    Collection rate and persistency metrics per funder type, corporate, or learner.
    Calculated rolling quarterly and project lifetime.
    """
    ENTITY_TYPE_CHOICES = [
        ('FUNDER_TYPE', 'Funder Type'),
        ('CORPORATE', 'Corporate Client'),
        ('LEARNER', 'Individual Learner'),
        ('PROJECT', 'Specific Project'),
    ]
    
    PERIOD_TYPE_CHOICES = [
        ('QUARTERLY', 'Rolling Quarterly'),
        ('LIFETIME', 'Project Lifetime'),
        ('ANNUAL', 'Annual'),
    ]
    
    # What we're tracking
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES)
    
    # Entity references (only one should be set based on entity_type)
    funder_type = models.CharField(max_length=30, blank=True)
    corporate_client = models.ForeignKey(
        'corporate.CorporateClient',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='collection_metrics'
    )
    learner = models.ForeignKey(
        'learners.Learner',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='collection_metrics'
    )
    training_notification = models.ForeignKey(
        'core.TrainingNotification',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='collection_metrics'
    )
    
    # Period covered
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Financial metrics
    total_invoiced = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    total_collected = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    total_outstanding = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    total_bad_debt = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text="Write-offs and uncollectable amounts"
    )
    
    # Calculated rates
    collection_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text="Percentage of invoiced amount collected"
    )
    persistency_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text="Percentage of expected payments actually received on time"
    )
    bad_debt_ratio = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text="Percentage of invoiced amount written off"
    )
    
    # Payment timing metrics
    average_days_to_payment = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text="Average days from invoice to payment"
    )
    
    # Invoice counts
    invoices_issued = models.PositiveIntegerField(default=0)
    invoices_paid_on_time = models.PositiveIntegerField(default=0)
    invoices_paid_late = models.PositiveIntegerField(default=0)
    invoices_outstanding = models.PositiveIntegerField(default=0)
    
    # Aging breakdown
    aging_current = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    aging_30_days = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    aging_60_days = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    aging_90_days = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    aging_over_90 = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Business assessment
    risk_rating = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low Risk'),
            ('MEDIUM', 'Medium Risk'),
            ('HIGH', 'High Risk'),
            ('CRITICAL', 'Critical Risk'),
        ],
        default='MEDIUM'
    )
    is_good_business = models.BooleanField(
        null=True,
        help_text="Calculated assessment: is this funder/client good business?"
    )
    
    # Metadata
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-period_end', 'entity_type']
        verbose_name = 'Collection Metrics'
        verbose_name_plural = 'Collection Metrics'
        indexes = [
            models.Index(fields=['entity_type', 'funder_type']),
            models.Index(fields=['period_type', 'period_end']),
        ]
    
    def __str__(self):
        entity = self.funder_type or self.corporate_client or self.learner or self.training_notification
        return f"{entity} - {self.get_period_type_display()} ({self.period_end})"
    
    def calculate_rates(self):
        """Recalculate all rates from totals"""
        if self.total_invoiced > 0:
            self.collection_rate = (self.total_collected / self.total_invoiced) * 100
            self.bad_debt_ratio = (self.total_bad_debt / self.total_invoiced) * 100
        
        total_expected = self.invoices_paid_on_time + self.invoices_paid_late + self.invoices_outstanding
        if total_expected > 0:
            self.persistency_rate = (self.invoices_paid_on_time / total_expected) * 100
        
        # Assess risk
        if self.collection_rate >= 95 and self.average_days_to_payment and self.average_days_to_payment <= 30:
            self.risk_rating = 'LOW'
            self.is_good_business = True
        elif self.collection_rate >= 80:
            self.risk_rating = 'MEDIUM'
            self.is_good_business = True
        elif self.collection_rate >= 60:
            self.risk_rating = 'HIGH'
            self.is_good_business = False
        else:
            self.risk_rating = 'CRITICAL'
            self.is_good_business = False
        
        self.save()
