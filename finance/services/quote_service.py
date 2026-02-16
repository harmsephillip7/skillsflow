"""
Quote Service
Handles quote creation, pricing, PDF generation, and messaging
"""
import io
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List, Tuple

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse


class QuoteService:
    """
    Service class for quote operations
    """
    
    @staticmethod
    def get_pricing_for_qualification(qualification, academic_year: int) -> dict:
        """
        Get pricing for a qualification for a specific academic year.
        Uses the new QualificationPricing model with effective dates.
        Falls back to legacy QualificationYearlyPricing or price list.
        """
        from academics.models import QualificationPricing
        from finance.models import QualificationYearlyPricing, PriceList, PriceListItem
        
        # Try new QualificationPricing first (from academics)
        pricing = qualification.get_pricing_for_year(academic_year)
        if pricing:
            return {
                'total_price': pricing.total_price,
                'registration_fee': pricing.registration_fee,
                'tuition_fee': pricing.tuition_fee,
                'materials_fee': pricing.materials_fee,
                'source': 'qualification_pricing'
            }
        
        # Try current pricing if no year-specific pricing
        pricing = qualification.get_current_pricing()
        if pricing:
            return {
                'total_price': pricing.total_price,
                'registration_fee': pricing.registration_fee,
                'tuition_fee': pricing.tuition_fee,
                'materials_fee': pricing.materials_fee,
                'source': 'qualification_pricing_current'
            }
        
        # Fall back to legacy QualificationYearlyPricing
        yearly_pricing = QualificationYearlyPricing.objects.filter(
            qualification=qualification,
            academic_year=academic_year,
            is_active=True
        ).first()
        
        if yearly_pricing:
            total = yearly_pricing.registration_fee + yearly_pricing.tuition_fee + yearly_pricing.materials_fee
            return {
                'total_price': total,
                'registration_fee': yearly_pricing.registration_fee,
                'tuition_fee': yearly_pricing.tuition_fee,
                'materials_fee': yearly_pricing.materials_fee,
                'source': 'yearly_pricing_legacy'
            }
        
        # Fall back to active price list
        price_item = PriceListItem.objects.filter(
            qualification=qualification,
            price_list__is_active=True,
            price_list__effective_from__lte=date.today()
        ).order_by('-price_list__effective_from').first()
        
        if price_item:
            return {
                'total_price': price_item.price,
                'registration_fee': Decimal('0.00'),
                'tuition_fee': price_item.price,
                'materials_fee': Decimal('0.00'),
                'source': 'price_list'
            }
        
        # Default pricing
        return {
            'total_price': Decimal('0.00'),
            'registration_fee': Decimal('0.00'),
            'tuition_fee': Decimal('0.00'),
            'materials_fee': Decimal('0.00'),
            'source': 'default'
        }
    
    @staticmethod
    def get_pricing_from_intake(intake) -> dict:
        """
        Get pricing from an intake's fee structure.
        """
        reg_fee = intake.registration_fee or Decimal('0.00')
        tuition_fee = intake.tuition_fee or Decimal('0.00')
        materials_fee = intake.materials_fee or Decimal('0.00')
        total = reg_fee + tuition_fee + materials_fee
        
        return {
            'total_price': total,
            'registration_fee': reg_fee,
            'tuition_fee': tuition_fee,
            'materials_fee': materials_fee,
            'source': 'intake'
        }
    
    @staticmethod
    def get_available_templates(campus=None):
        """
        Get quote templates available for a campus.
        """
        from finance.models import QuoteTemplate
        return QuoteTemplate.get_for_campus(campus)
    
    @staticmethod
    def get_available_payment_options(template=None):
        """
        Get payment options - from template if provided, otherwise all active.
        """
        from finance.models import PaymentOption
        
        if template:
            return template.get_effective_payment_options()
        return PaymentOption.objects.filter(is_active=True).order_by('sort_order')
    
    @staticmethod
    def create_quote_from_template(
        template,
        lead,
        qualification=None,
        intake=None,
        payment_option=None,
        enrollment_year: str = 'CURRENT',
        created_by=None,
        campus=None
    ):
        """
        Create a quote using a quote template.
        
        Args:
            template: QuoteTemplate instance
            lead: CRM Lead instance
            qualification: Optional Qualification to quote for
            intake: Optional Intake (overrides qualification)
            payment_option: PaymentOption instance
            enrollment_year: CURRENT, NEXT, or PLUS_TWO
            created_by: User creating the quote
            campus: Campus for the quote
        """
        from finance.models import Quote, QuoteLineItem, QuotePaymentSchedule
        from tenants.models import Campus
        
        # Determine academic year
        current_year = timezone.now().year
        if enrollment_year == 'CURRENT':
            academic_year = current_year
        elif enrollment_year == 'NEXT':
            academic_year = current_year + 1
        else:
            academic_year = current_year + 2
        
        # Get qualification from intake if not specified
        if intake and not qualification:
            qualification = intake.qualification
        
        # Get campus
        if not campus:
            if intake:
                campus = intake.campus
            elif template.campus:
                campus = template.campus
            else:
                campus = Campus.objects.first()
        
        # Calculate valid_until from template
        valid_hours = template.get_effective_validity_hours() if template else 48
        valid_until = date.today() + timedelta(hours=valid_hours)
        
        # Get terms from template
        terms = template.get_effective_terms() if template else ""
        
        # Determine payment plan from PaymentOption
        payment_plan = 'UPFRONT'
        monthly_term = 10
        if payment_option:
            if payment_option.installments == 1:
                payment_plan = 'UPFRONT'
            elif payment_option.installments == 2:
                payment_plan = 'TWO_INSTALLMENTS'
            else:
                payment_plan = 'MONTHLY'
                monthly_term = payment_option.monthly_term
        
        # Create the quote
        quote = Quote.objects.create(
            campus=campus,
            lead=lead,
            intake=intake,
            template=template,
            payment_option=payment_option,
            enrollment_year=enrollment_year,
            academic_year=academic_year,
            payment_plan=payment_plan,
            monthly_term=monthly_term,
            quote_date=date.today(),
            valid_until=valid_until,
            vat_rate=Decimal('0.00'),  # 0% VAT for learners
            terms=terms,
            created_by=created_by
        )
        
        # Get pricing
        if intake:
            pricing = QuoteService.get_pricing_from_intake(intake)
        elif qualification:
            pricing = QuoteService.get_pricing_for_qualification(qualification, academic_year)
        else:
            pricing = {
                'total_price': Decimal('0.00'),
                'registration_fee': Decimal('0.00'),
                'tuition_fee': Decimal('0.00'),
                'materials_fee': Decimal('0.00'),
                'source': 'manual'
            }
        
        # Create single line item with total all-inclusive price
        if pricing['total_price'] > 0:
            description = qualification.short_title if qualification else "Programme Fee"
            QuoteLineItem.objects.create(
                quote=quote,
                item_type='TUITION',
                description=f'{description} - {academic_year} Academic Year',
                quantity=1,
                original_unit_price=pricing['total_price'],
                unit_price=pricing['total_price'],
                academic_year=academic_year,
                qualification=qualification
            )
        
        # Calculate totals
        quote.calculate_totals()
        
        # Generate payment schedule using PaymentOption
        if payment_option:
            QuoteService.generate_payment_schedule_from_option(quote, payment_option)
        else:
            QuoteService.generate_payment_schedule(quote)
        
        return quote
    
    @staticmethod
    def generate_payment_schedule_from_option(quote, payment_option):
        """
        Generate payment schedule using a PaymentOption model.
        """
        from finance.models import QuotePaymentSchedule
        
        # Clear existing schedule
        quote.payment_schedule.all().delete()
        
        if quote.total <= 0:
            return
        
        base_date = quote.quote_date if isinstance(quote.quote_date, date) else date.today()
        
        # Use PaymentOption's calculate_schedule method
        schedule = payment_option.calculate_schedule(quote.total, base_date)
        
        for item in schedule:
            QuotePaymentSchedule.objects.create(
                quote=quote,
                installment_number=item['installment_number'],
                description=item['description'],
                due_date=item['due_date'],
                amount=item['amount']
            )
    
    @staticmethod
    def create_quote_from_lead(
        lead,
        qualification=None,
        intake=None,
        enrollment_year: str = 'CURRENT',
        payment_plan: str = 'UPFRONT',
        created_by=None,
        campus=None,
        template=None,
        payment_option=None
    ):
        """
        Create a quote for a lead with automatic pricing lookup.
        
        Args:
            lead: CRM Lead instance
            qualification: Optional Qualification to quote for
            intake: Optional Intake (overrides qualification)
            enrollment_year: CURRENT, NEXT, or PLUS_TWO
            payment_plan: UPFRONT, TWO_INSTALLMENTS, or MONTHLY
            created_by: User creating the quote
            campus: Campus for the quote
            template: Optional QuoteTemplate to use
            payment_option: Optional PaymentOption to use
        """
        # If template is provided, use template-based creation
        if template:
            return QuoteService.create_quote_from_template(
                template=template,
                lead=lead,
                qualification=qualification,
                intake=intake,
                payment_option=payment_option,
                enrollment_year=enrollment_year,
                created_by=created_by,
                campus=campus
            )
        
        from finance.models import Quote, QuoteLineItem
        from tenants.models import Campus
        
        # Determine academic year
        current_year = timezone.now().year
        if enrollment_year == 'CURRENT':
            academic_year = current_year
        elif enrollment_year == 'NEXT':
            academic_year = current_year + 1
        else:
            academic_year = current_year + 2
        
        # Get qualification from intake if not specified
        if intake and not qualification:
            qualification = intake.qualification
        
        # Get campus
        if not campus:
            if intake:
                campus = intake.campus
            else:
                campus = Campus.objects.first()
        
        # Create the quote
        quote = Quote.objects.create(
            campus=campus,
            lead=lead,
            intake=intake,
            template=template,
            payment_option=payment_option,
            enrollment_year=enrollment_year,
            academic_year=academic_year,
            payment_plan=payment_plan,
            quote_date=date.today(),
            vat_rate=Decimal('0.00'),  # 0% VAT for learners
            created_by=created_by
        )
        
        # Get pricing
        if intake:
            pricing = QuoteService.get_pricing_from_intake(intake)
        elif qualification:
            pricing = QuoteService.get_pricing_for_qualification(qualification, academic_year)
        else:
            pricing = {
                'total_price': Decimal('0.00'),
                'registration_fee': Decimal('0.00'),
                'tuition_fee': Decimal('0.00'),
                'materials_fee': Decimal('0.00'),
                'source': 'manual'
            }
        
        # Create single line item with total all-inclusive price
        if pricing['total_price'] > 0:
            description = qualification.short_title if qualification else "Programme Fee"
            QuoteLineItem.objects.create(
                quote=quote,
                item_type='TUITION',
                description=f'{description} - {academic_year} Academic Year',
                quantity=1,
                original_unit_price=pricing['total_price'],
                unit_price=pricing['total_price'],
                academic_year=academic_year,
                qualification=qualification
            )
        
        # Calculate totals
        quote.calculate_totals()
        
        # Generate payment schedule
        if payment_option:
            QuoteService.generate_payment_schedule_from_option(quote, payment_option)
        else:
            QuoteService.generate_payment_schedule(quote)
        
        return quote
    
    @staticmethod
    def generate_payment_schedule(quote):
        """
        Generate payment schedule based on quote's payment plan.
        """
        from finance.models import QuotePaymentSchedule
        
        # Clear existing schedule
        quote.payment_schedule.all().delete()
        
        if quote.total <= 0:
            return
        
        base_date = quote.quote_date if isinstance(quote.quote_date, date) else date.today()
        
        if quote.payment_plan == 'UPFRONT':
            # Single payment on acceptance
            QuotePaymentSchedule.objects.create(
                quote=quote,
                installment_number=1,
                description='Full Payment',
                due_date=base_date,
                amount=quote.total
            )
        
        elif quote.payment_plan == 'TWO_INSTALLMENTS':
            # 50% deposit, 50% 30 days later
            half_amount = quote.total / 2
            
            QuotePaymentSchedule.objects.create(
                quote=quote,
                installment_number=1,
                description='Deposit (50%)',
                due_date=base_date,
                amount=half_amount
            )
            
            QuotePaymentSchedule.objects.create(
                quote=quote,
                installment_number=2,
                description='Final Payment (50%)',
                due_date=base_date + timedelta(days=30),
                amount=half_amount
            )
        
        else:  # MONTHLY
            monthly_amount = quote.total / quote.monthly_term
            
            for i in range(quote.monthly_term):
                QuotePaymentSchedule.objects.create(
                    quote=quote,
                    installment_number=i + 1,
                    description=f'Monthly Payment {i + 1} of {quote.monthly_term}',
                    due_date=base_date + timedelta(days=30 * i),
                    amount=monthly_amount
                )
    
    @staticmethod
    def generate_pdf(quote) -> bytes:
        """
        Generate PDF for the quote using WeasyPrint.
        Returns PDF as bytes.
        """
        try:
            from weasyprint import HTML, CSS
        except ImportError:
            # Fallback to simple HTML if WeasyPrint not available
            html_content = QuoteService._render_quote_html(quote)
            return html_content.encode('utf-8')
        
        html_content = QuoteService._render_quote_html(quote)
        
        # Generate PDF
        html = HTML(string=html_content, base_url=settings.BASE_DIR)
        pdf = html.write_pdf()
        
        return pdf
    
    @staticmethod
    def _render_quote_html(quote) -> str:
        """
        Render quote to HTML for PDF generation.
        """
        from tenants.models import Brand
        
        # Get brand info
        brand = None
        if quote.campus:
            brand = quote.campus.brand
        if not brand:
            brand = Brand.objects.first()
        
        context = {
            'quote': quote,
            'line_items': quote.line_items.all(),
            'payment_schedule': quote.payment_schedule.all(),
            'brand': brand,
            'generated_date': timezone.now(),
        }
        
        return render_to_string('finance/quote_pdf.html', context)
    
    @staticmethod
    def save_pdf_to_media(quote) -> str:
        """
        Generate and save PDF to media folder.
        Returns the file path.
        """
        pdf_bytes = QuoteService.generate_pdf(quote)
        
        # Create directory if needed
        pdf_dir = os.path.join(settings.MEDIA_ROOT, 'quotes', 'pdf')
        os.makedirs(pdf_dir, exist_ok=True)
        
        # Save file
        filename = f"{quote.quote_number}.pdf"
        filepath = os.path.join(pdf_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(pdf_bytes)
        
        return filepath
    
    @staticmethod
    def send_email(quote, recipient_email: str = None, cc_emails: List[str] = None) -> bool:
        """
        Send quote via email with PDF attachment.
        
        Args:
            quote: Quote instance
            recipient_email: Email address (defaults to lead's email)
            cc_emails: List of CC email addresses
        
        Returns:
            True if sent successfully
        """
        # Determine recipient
        if not recipient_email:
            if quote.lead:
                recipient_email = quote.lead.email
            elif quote.learner:
                recipient_email = quote.learner.email
        
        if not recipient_email:
            return False
        
        # Get lead/learner name
        recipient_name = "Valued Client"
        if quote.lead:
            recipient_name = f"{quote.lead.first_name} {quote.lead.last_name}"
        elif quote.learner:
            recipient_name = quote.learner.get_full_name()
        
        # Build public URL
        public_url = quote.get_public_url()
        if hasattr(settings, 'SITE_URL'):
            public_url = f"{settings.SITE_URL}{public_url}"
        else:
            public_url = f"https://skillsflow.vercel.app{public_url}"
        
        # Render email
        context = {
            'quote': quote,
            'recipient_name': recipient_name,
            'public_url': public_url,
        }
        
        subject = f"Quote {quote.quote_number} - {quote.intake.qualification.short_title if quote.intake else 'Programme Fees'}"
        html_content = render_to_string('finance/email/quote_email.html', context)
        text_content = render_to_string('finance/email/quote_email.txt', context)
        
        # Generate PDF
        pdf_bytes = QuoteService.generate_pdf(quote)
        
        # Create email
        email = EmailMessage(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
            cc=cc_emails or [],
        )
        email.attach(f"{quote.quote_number}.pdf", pdf_bytes, 'application/pdf')
        
        try:
            email.send()
            quote.mark_as_sent()
            return True
        except Exception as e:
            print(f"Error sending quote email: {e}")
            return False
    
    @staticmethod
    def send_whatsapp_link(quote, phone_number: str = None) -> bool:
        """
        Send quote link via WhatsApp.
        
        Args:
            quote: Quote instance
            phone_number: Phone number (defaults to lead's phone)
        
        Returns:
            True if message queued successfully
        """
        from crm.models import WhatsAppMessage
        
        # Determine phone number
        if not phone_number:
            if quote.lead:
                phone_number = quote.lead.phone
            elif quote.learner:
                phone_number = quote.learner.phone
        
        if not phone_number:
            return False
        
        # Format phone number (ensure it has country code)
        phone_number = QuoteService._format_phone_number(phone_number)
        
        # Build message
        recipient_name = "there"
        if quote.lead:
            recipient_name = quote.lead.first_name
        elif quote.learner:
            recipient_name = quote.learner.first_name
        
        public_url = quote.get_public_url()
        if hasattr(settings, 'SITE_URL'):
            public_url = f"{settings.SITE_URL}{public_url}"
        else:
            public_url = f"https://skillsflow.vercel.app{public_url}"
        
        message_content = f"""Hi {recipient_name}! 👋

Your quote {quote.quote_number} is ready!

💰 Total: R{quote.total:,.2f}
📅 Valid until: {quote.valid_until.strftime('%d %B %Y')}
💳 Payment Plan: {quote.get_payment_plan_display()}

View and accept your quote here:
{public_url}

This quote expires in 48 hours. Please review and accept to secure your place.

If you have any questions, please reply to this message.

Kind regards,
SkillsFlow Team"""
        
        # Create WhatsApp message record
        wa_message = WhatsAppMessage.objects.create(
            direction='OUT',
            phone_number=phone_number,
            lead=quote.lead,
            learner=quote.learner,
            message_type='TEXT',
            content=message_content,
            status='PENDING'
        )
        
        # TODO: Integrate with WhatsApp Business API to actually send
        # For now, mark as sent (would be handled by async task in production)
        wa_message.status = 'SENT'
        wa_message.sent_at = timezone.now()
        wa_message.save()
        
        quote.mark_as_sent()
        return True
    
    @staticmethod
    def send_whatsapp_pdf(quote, phone_number: str = None) -> bool:
        """
        Send quote PDF via WhatsApp as a document.
        
        Args:
            quote: Quote instance
            phone_number: Phone number (defaults to lead's phone)
        
        Returns:
            True if message queued successfully
        """
        from crm.models import WhatsAppMessage
        
        # Determine phone number
        if not phone_number:
            if quote.lead:
                phone_number = quote.lead.phone
            elif quote.learner:
                phone_number = quote.learner.phone
        
        if not phone_number:
            return False
        
        phone_number = QuoteService._format_phone_number(phone_number)
        
        # Save PDF to media
        pdf_path = QuoteService.save_pdf_to_media(quote)
        pdf_url = f"{settings.MEDIA_URL}quotes/pdf/{quote.quote_number}.pdf"
        
        # Build caption
        recipient_name = "there"
        if quote.lead:
            recipient_name = quote.lead.first_name
        
        caption = f"""Hi {recipient_name}! 👋

Please find attached your quote {quote.quote_number}.

💰 Total: R{quote.total:,.2f}
📅 Valid until: {quote.valid_until.strftime('%d %B %Y')}

This quote is valid for 48 hours.

Kind regards,
SkillsFlow Team"""
        
        # Create WhatsApp message record
        wa_message = WhatsAppMessage.objects.create(
            direction='OUT',
            phone_number=phone_number,
            lead=quote.lead,
            learner=quote.learner,
            message_type='DOCUMENT',
            content=caption,
            media_url=pdf_url,
            status='PENDING'
        )
        
        # TODO: Integrate with WhatsApp Business API to actually send
        wa_message.status = 'SENT'
        wa_message.sent_at = timezone.now()
        wa_message.save()
        
        quote.mark_as_sent()
        return True
    
    @staticmethod
    def _format_phone_number(phone: str) -> str:
        """
        Format phone number to international format.
        Assumes South African numbers if no country code.
        """
        phone = ''.join(filter(str.isdigit, phone))
        
        if phone.startswith('0'):
            phone = '27' + phone[1:]
        elif not phone.startswith('27'):
            phone = '27' + phone
        
        return phone
    
    @staticmethod
    def check_and_expire_quotes():
        """
        Check for expired quotes and update their status.
        Can be run as a scheduled task.
        """
        from finance.models import Quote
        
        expired_quotes = Quote.objects.filter(
            status__in=['DRAFT', 'SENT', 'VIEWED'],
            valid_until__lt=date.today()
        )
        
        count = expired_quotes.update(status='EXPIRED')
        return count
