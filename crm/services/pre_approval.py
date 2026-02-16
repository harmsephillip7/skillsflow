"""
Pre-Approval Letter Service

Handles:
- PDF generation for pre-approval letters
- Sending via WhatsApp, Email, or SMS
- Letter tracking and status updates
"""
import logging
import os
from datetime import date, timedelta
from typing import Optional, Dict, Any, Tuple
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


class PreApprovalService:
    """
    Service for generating and sending pre-approval letters.
    """
    
    @classmethod
    def create_pre_approval_letter(
        cls,
        lead,
        qualification,
        campus=None,
        intake=None,
        entry_requirements_notes: str = '',
        confirmed_by=None,
        valid_days: int = 90
    ):
        """
        Create a pre-approval letter for a lead.
        
        Args:
            lead: Lead instance
            qualification: Qualification the lead is being pre-approved for
            campus: Campus (defaults to lead's campus)
            intake: Optional specific intake
            entry_requirements_notes: Notes about entry requirements
            confirmed_by: User who confirmed the pre-approval
            valid_days: Number of days the letter is valid
        
        Returns:
            PreApprovalLetter instance
        """
        from crm.models import PreApprovalLetter
        
        letter = PreApprovalLetter.objects.create(
            lead=lead,
            qualification=qualification,
            campus=campus or lead.campus,
            intake=intake,
            entry_requirements_confirmed=True,
            entry_requirements_notes=entry_requirements_notes,
            valid_until=date.today() + timedelta(days=valid_days),
            confirmed_by=confirmed_by,
        )
        
        return letter
    
    @classmethod
    def generate_pdf(cls, letter) -> bytes:
        """
        Generate PDF for the pre-approval letter.
        
        Args:
            letter: PreApprovalLetter instance
            
        Returns:
            PDF as bytes
        """
        try:
            from weasyprint import HTML, CSS
            has_weasyprint = True
        except ImportError:
            has_weasyprint = False
            logger.warning("WeasyPrint not installed - PDF generation will be basic HTML")
        
        # Render HTML template
        html_content = cls._render_letter_html(letter)
        
        if has_weasyprint:
            # Generate proper PDF
            html = HTML(string=html_content, base_url=str(settings.BASE_DIR))
            pdf_bytes = html.write_pdf()
        else:
            # Fallback to HTML bytes
            pdf_bytes = html_content.encode('utf-8')
        
        return pdf_bytes
    
    @classmethod
    def _render_letter_html(cls, letter) -> str:
        """
        Render the pre-approval letter to HTML.
        """
        from tenants.models import Brand
        
        # Get brand info
        brand = None
        if letter.campus:
            brand = letter.campus.brand
        if not brand:
            brand = Brand.objects.first()
        
        lead = letter.lead
        qualification = letter.qualification
        
        # Build context
        context = {
            'letter': letter,
            'lead': lead,
            'qualification': qualification,
            'campus': letter.campus,
            'brand': brand,
            'generated_date': timezone.now(),
            
            # Letter details
            'letter_number': letter.letter_number,
            'issued_date': letter.issued_date,
            'valid_until': letter.valid_until,
            
            # Lead details
            'lead_name': lead.get_full_name(),
            'lead_first_name': lead.first_name,
            
            # Qualification details
            'qualification_name': qualification.name,
            'qualification_code': qualification.code if hasattr(qualification, 'code') else '',
            'qualification_nqf_level': getattr(qualification, 'nqf_level', ''),
            'qualification_duration': getattr(qualification, 'duration_months', 12),
            
            # Campus details
            'campus_name': letter.campus.name if letter.campus else '',
            'campus_address': getattr(letter.campus, 'address', '') if letter.campus else '',
            'campus_phone': getattr(letter.campus, 'phone', '') if letter.campus else '',
            
            # Intake if specified
            'intake': letter.intake,
            'intake_start_date': letter.intake.start_date if letter.intake else None,
        }
        
        return render_to_string('crm/letters/pre_approval_letter.html', context)
    
    @classmethod
    def save_pdf_to_letter(cls, letter) -> str:
        """
        Generate PDF and save to the letter's pdf_file field.
        
        Returns:
            The file path
        """
        pdf_bytes = cls.generate_pdf(letter)
        
        # Save to model field
        filename = f"pre_approval_{letter.letter_number}.pdf"
        letter.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
        
        return letter.pdf_file.path
    
    @classmethod
    def send_letter(
        cls,
        letter,
        channel: str = None,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Send the pre-approval letter via the preferred channel.
        
        Args:
            letter: PreApprovalLetter instance
            channel: Channel to send via (whatsapp, email, sms). 
                    Defaults to lead's preferred contact method.
            force_regenerate: Regenerate PDF even if it exists
            
        Returns:
            Dict with success status and details
        """
        result = {
            'success': False,
            'channel': None,
            'error': None,
            'message_id': None,
        }
        
        lead = letter.lead
        
        # Determine channel
        if not channel:
            channel = lead.preferred_contact_method or 'email'
        channel = channel.lower()
        
        result['channel'] = channel
        
        # Generate/get PDF
        if force_regenerate or not letter.pdf_file:
            try:
                cls.save_pdf_to_letter(letter)
            except Exception as e:
                logger.error(f"Failed to generate PDF for {letter.letter_number}: {e}")
                result['error'] = f"PDF generation failed: {str(e)}"
                return result
        
        # Get contact info
        contact = lead.get_contact_for_channel(channel)
        if not contact:
            # Try fallback channels
            for fallback in ['email', 'whatsapp', 'phone']:
                if fallback != channel:
                    contact = lead.get_contact_for_channel(fallback)
                    if contact:
                        channel = fallback
                        result['channel'] = channel
                        break
        
        if not contact:
            result['error'] = "No contact information available"
            return result
        
        # Send via appropriate channel
        try:
            if channel == 'whatsapp':
                send_result = cls._send_via_whatsapp(letter, contact)
            elif channel == 'email':
                send_result = cls._send_via_email(letter, contact)
            elif channel in ['phone', 'sms']:
                send_result = cls._send_via_sms(letter, contact)
            else:
                # Default to email
                contact = lead.email
                if contact:
                    send_result = cls._send_via_email(letter, contact)
                else:
                    result['error'] = f"Unsupported channel: {channel}"
                    return result
            
            if send_result.get('success'):
                # Update letter status
                letter.status = 'SENT'
                letter.sent_at = timezone.now()
                letter.sent_via = channel.upper()
                letter.sent_to_contact = contact
                letter.save()
                
                result['success'] = True
                result['message_id'] = send_result.get('message_id')
            else:
                result['error'] = send_result.get('error', 'Send failed')
                
        except Exception as e:
            logger.exception(f"Error sending pre-approval letter: {e}")
            result['error'] = str(e)
        
        return result
    
    @classmethod
    def _send_via_whatsapp(cls, letter, phone_number: str) -> Dict[str, Any]:
        """
        Send pre-approval letter via WhatsApp.
        
        Uses WhatsApp template message with document attachment.
        """
        from integrations.models import IntegrationConnection
        from integrations.connectors import WhatsAppConnector
        
        result = {'success': False, 'error': None}
        
        # Get WhatsApp connection
        connection = IntegrationConnection.objects.filter(
            provider__slug='whatsapp',
            is_active=True
        ).first()
        
        if not connection:
            result['error'] = "WhatsApp not configured"
            return result
        
        lead = letter.lead
        qualification = letter.qualification
        
        try:
            connector = WhatsAppConnector(connection)
            
            # Format phone number
            formatted_phone = cls._format_phone_for_whatsapp(phone_number)
            
            # Build message text
            message_text = cls._build_whatsapp_message(letter)
            
            # Try to send as document with caption
            if letter.pdf_file:
                # Get public URL for the PDF
                pdf_url = cls._get_public_pdf_url(letter)
                
                if pdf_url:
                    # Send document
                    send_result = connector.send_document(
                        to=formatted_phone,
                        document_url=pdf_url,
                        filename=f"Pre-Approval-{letter.letter_number}.pdf",
                        caption=message_text[:1024]  # WhatsApp caption limit
                    )
                else:
                    # Send text message without attachment
                    send_result = connector.send_text(
                        to=formatted_phone,
                        text=message_text
                    )
            else:
                # Send text only
                send_result = connector.send_text(
                    to=formatted_phone,
                    text=message_text
                )
            
            if send_result.success:
                result['success'] = True
                result['message_id'] = send_result.external_id
            else:
                result['error'] = send_result.error_message or "WhatsApp send failed"
                
        except Exception as e:
            logger.exception(f"WhatsApp send error: {e}")
            result['error'] = str(e)
        
        return result
    
    @classmethod
    def _send_via_email(cls, letter, email_address: str) -> Dict[str, Any]:
        """
        Send pre-approval letter via Email.
        """
        from django.core.mail import EmailMessage
        from tenants.models import Brand
        
        result = {'success': False, 'error': None}
        
        lead = letter.lead
        qualification = letter.qualification
        campus = letter.campus
        
        # Get brand
        brand = campus.brand if campus else Brand.objects.first()
        brand_name = brand.name if brand else "SkillsFlow"
        
        try:
            # Build email
            subject = f"Pre-Approval Letter for {qualification.name} - {letter.letter_number}"
            
            # Render email body
            html_content = render_to_string('crm/emails/pre_approval_email.html', {
                'letter': letter,
                'lead': lead,
                'qualification': qualification,
                'campus': campus,
                'brand': brand,
                'brand_name': brand_name,
            })
            
            text_content = cls._build_email_text(letter)
            
            # Create email
            email = EmailMessage(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_address],
            )
            
            # Add HTML version
            email.content_subtype = 'html'
            email.body = html_content
            
            # Attach PDF if available
            if letter.pdf_file:
                email.attach(
                    f"Pre-Approval-{letter.letter_number}.pdf",
                    letter.pdf_file.read(),
                    'application/pdf'
                )
            
            # Send
            email.send(fail_silently=False)
            
            result['success'] = True
            
        except Exception as e:
            logger.exception(f"Email send error: {e}")
            result['error'] = str(e)
        
        return result
    
    @classmethod
    def _send_via_sms(cls, letter, phone_number: str) -> Dict[str, Any]:
        """
        Send pre-approval notification via SMS.
        Note: SMS cannot include PDF, so we send a notification with a link.
        """
        from integrations.models import IntegrationConnection
        from integrations.connectors import BulkSMSConnector, ClickatellConnector
        
        result = {'success': False, 'error': None}
        
        # Get SMS connection (try BulkSMS first, then Clickatell)
        connection = IntegrationConnection.objects.filter(
            provider__slug__in=['bulksms', 'clickatell'],
            is_active=True
        ).first()
        
        if not connection:
            result['error'] = "SMS not configured"
            return result
        
        try:
            # Build short SMS message
            message = cls._build_sms_message(letter)
            
            # Get connector
            if connection.provider.slug == 'bulksms':
                connector = BulkSMSConnector(connection)
            else:
                connector = ClickatellConnector(connection)
            
            # Send
            send_result = connector.send_sms(
                to=phone_number,
                message=message
            )
            
            if send_result.success:
                result['success'] = True
                result['message_id'] = send_result.external_id
            else:
                result['error'] = send_result.error_message or "SMS send failed"
                
        except Exception as e:
            logger.exception(f"SMS send error: {e}")
            result['error'] = str(e)
        
        return result
    
    @classmethod
    def _build_whatsapp_message(cls, letter) -> str:
        """Build WhatsApp message text."""
        lead = letter.lead
        qualification = letter.qualification
        campus = letter.campus
        
        brand_name = campus.brand.name if campus and campus.brand else "us"
        portal_url = letter.get_full_portal_url()
        
        message = f"""🎓 *Pre-Approval Letter*

Hi {lead.first_name}!

Great news! You have been *pre-approved* for:
📚 *{qualification.name}*
🏫 {campus.name if campus else ''}

Your pre-approval reference: *{letter.letter_number}*
Valid until: {letter.valid_until.strftime('%d %B %Y')}

📱 *View your letter & start your application:*
{portal_url}

*Next Steps:*
1. Click the link above to view your letter
2. Accept the pre-approval terms
3. Start your enrollment application

We're excited to have you join {brand_name}! 🌟

Reply to this message if you have any questions."""

        return message
    
    @classmethod
    def _build_email_text(cls, letter) -> str:
        """Build plain text email body."""
        lead = letter.lead
        qualification = letter.qualification
        campus = letter.campus
        portal_url = letter.get_full_portal_url()
        
        return f"""Dear {lead.first_name},

Congratulations! You have been pre-approved for enrollment in:

Qualification: {qualification.name}
Campus: {campus.name if campus else 'N/A'}

Your pre-approval reference number is: {letter.letter_number}
This pre-approval is valid until: {letter.valid_until.strftime('%d %B %Y')}

Please find your official Pre-Approval Letter attached to this email.

VIEW YOUR LETTER & START YOUR APPLICATION:
{portal_url}

Next Steps:
1. Click the link above or review the attached pre-approval letter
2. Accept the pre-approval terms
3. Start your enrollment application online

If you have any questions, please don't hesitate to contact us.

We look forward to welcoming you!

Best regards,
{campus.name if campus else 'Admissions Team'}
"""
    
    @classmethod
    def _build_sms_message(cls, letter) -> str:
        """Build short SMS message (160 char limit)."""
        lead = letter.lead
        qualification = letter.qualification
        
        # Keep it short
        qual_short = qualification.short_title if hasattr(qualification, 'short_title') else qualification.name[:30]
        
        return f"Hi {lead.first_name}! You're pre-approved for {qual_short}. Ref: {letter.letter_number}. Check your email for the full letter."
    
    @classmethod
    def _format_phone_for_whatsapp(cls, phone: str) -> str:
        """Format phone number for WhatsApp API (needs country code, no +)."""
        if not phone:
            return ''
        
        # Remove all non-digits
        digits = ''.join(c for c in phone if c.isdigit())
        
        # Handle South African numbers
        if digits.startswith('0') and len(digits) == 10:
            digits = '27' + digits[1:]
        elif not digits.startswith('27') and len(digits) == 9:
            digits = '27' + digits
        
        return digits
    
    @classmethod
    def _get_public_pdf_url(cls, letter) -> Optional[str]:
        """
        Get a publicly accessible URL for the PDF.
        For local dev, this returns the local media URL.
        For production, should return a CDN or signed URL.
        """
        if not letter.pdf_file:
            return None
        
        # Build URL
        if hasattr(settings, 'SITE_URL'):
            base_url = settings.SITE_URL.rstrip('/')
        else:
            base_url = 'http://localhost:8000'
        
        return f"{base_url}{letter.pdf_file.url}"
    
    @classmethod
    def track_view(cls, letter) -> None:
        """
        Track when a letter is viewed (e.g., from tracking pixel or link).
        """
        letter.view_count += 1
        
        if not letter.first_viewed_at:
            letter.first_viewed_at = timezone.now()
            letter.status = 'VIEWED'
        
        letter.save(update_fields=['view_count', 'first_viewed_at', 'status'])
        
        # Log activity
        from crm.models import LeadActivity
        LeadActivity.objects.create(
            lead=letter.lead,
            activity_type='DOCUMENT_VIEWED',
            description=f'Pre-approval letter {letter.letter_number} viewed',
            is_automated=True,
            automation_source='pre_approval_service'
        )
    
    @classmethod
    def accept_letter(cls, letter) -> Tuple[bool, Optional[str]]:
        """
        Mark letter as accepted and trigger application creation.
        
        Returns:
            Tuple of (success, error_message)
        """
        if letter.status in ['ACCEPTED', 'EXPIRED', 'REVOKED']:
            return False, f"Letter is already {letter.status}"
        
        # Check if still valid
        if letter.valid_until < date.today():
            letter.status = 'EXPIRED'
            letter.save()
            return False, "Letter has expired"
        
        # Mark as accepted
        letter.status = 'ACCEPTED'
        letter.save()
        
        # Create application
        try:
            application = letter.start_application()
            
            # Log activity
            from crm.models import LeadActivity
            LeadActivity.objects.create(
                lead=letter.lead,
                activity_type='APPLICATION_STARTED',
                description=f'Application started from pre-approval {letter.letter_number}',
                is_automated=True,
                automation_source='pre_approval_service'
            )
            
            return True, None
            
        except Exception as e:
            logger.exception(f"Failed to start application: {e}")
            return False, str(e)    
    # =========================================================================
    # PARENT NOTIFICATION METHODS
    # =========================================================================
    
    @classmethod
    def send_parent_notification(cls, letter, channel: str = None) -> Dict[str, Any]:
        """
        Send notification to parent/guardian about their child's pre-approval.
        
        Args:
            letter: PreApprovalLetter instance
            channel: Channel to send via. Defaults to email if available, else whatsapp.
        
        Returns:
            Dict with success status and details
        """
        result = {
            'success': False,
            'channel': None,
            'error': None,
        }
        
        lead = letter.lead
        
        # Get parent contact
        parent_email = lead.parent_email
        parent_phone = lead.parent_phone
        parent_name = lead.parent_name or "Parent/Guardian"
        
        if not parent_email and not parent_phone:
            result['error'] = "No parent contact information available"
            return result
        
        # Determine channel (prefer email for parents as it's more formal)
        if not channel:
            channel = 'email' if parent_email else 'whatsapp'
        channel = channel.lower()
        result['channel'] = channel
        
        try:
            if channel == 'email' and parent_email:
                send_result = cls._send_parent_email(letter, parent_email, parent_name)
            elif parent_phone:
                send_result = cls._send_parent_whatsapp(letter, parent_phone, parent_name)
            else:
                result['error'] = f"No contact for channel: {channel}"
                return result
            
            if send_result.get('success'):
                # Update letter with parent notification info
                letter.parent_notified_at = timezone.now()
                letter.parent_sent_to = parent_email or parent_phone
                letter.save(update_fields=['parent_notified_at', 'parent_sent_to'])
                
                result['success'] = True
                result['message_id'] = send_result.get('message_id')
                
                # Log activity
                from crm.models import LeadActivity
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type='COMMUNICATION',
                    description=f'Parent notification sent for pre-approval {letter.letter_number} to {parent_email or parent_phone}',
                    is_automated=True,
                    automation_source='pre_approval_service'
                )
            else:
                result['error'] = send_result.get('error', 'Send failed')
                
        except Exception as e:
            logger.exception(f"Error sending parent notification: {e}")
            result['error'] = str(e)
        
        return result
    
    @classmethod
    def _send_parent_email(cls, letter, email_address: str, parent_name: str) -> Dict[str, Any]:
        """Send notification email to parent/guardian."""
        from django.core.mail import EmailMessage
        from tenants.models import Brand
        
        result = {'success': False, 'error': None}
        
        lead = letter.lead
        qualification = letter.qualification
        campus = letter.campus
        
        # Get brand
        brand = campus.brand if campus else Brand.objects.first()
        brand_name = brand.name if brand else "SkillsFlow"
        
        try:
            subject = f"Your Child's Pre-Approval for {qualification.name} - Action Required"
            
            # Build email context
            context = {
                'letter': letter,
                'lead': lead,
                'qualification': qualification,
                'campus': campus,
                'brand': brand,
                'brand_name': brand_name,
                'parent_name': parent_name,
                'portal_url': letter.get_full_portal_url(),
            }
            
            # Render email
            html_content = render_to_string('crm/emails/parent_pre_approval_email.html', context)
            text_content = cls._build_parent_email_text(letter, parent_name)
            
            email = EmailMessage(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_address],
            )
            email.content_subtype = 'html'
            email.body = html_content
            
            # Attach PDF
            if letter.pdf_file:
                email.attach(
                    f"Pre-Approval-{letter.letter_number}.pdf",
                    letter.pdf_file.read(),
                    'application/pdf'
                )
            
            email.send(fail_silently=False)
            result['success'] = True
            
        except Exception as e:
            logger.exception(f"Parent email send error: {e}")
            result['error'] = str(e)
        
        return result
    
    @classmethod
    def _send_parent_whatsapp(cls, letter, phone_number: str, parent_name: str) -> Dict[str, Any]:
        """Send notification WhatsApp to parent/guardian."""
        from integrations.models import IntegrationConnection
        from integrations.connectors import WhatsAppConnector
        
        result = {'success': False, 'error': None}
        
        connection = IntegrationConnection.objects.filter(
            provider__slug='whatsapp',
            is_active=True
        ).first()
        
        if not connection:
            result['error'] = "WhatsApp not configured"
            return result
        
        try:
            connector = WhatsAppConnector(connection)
            formatted_phone = cls._format_phone_for_whatsapp(phone_number)
            message_text = cls._build_parent_whatsapp_message(letter, parent_name)
            
            send_result = connector.send_text(
                to=formatted_phone,
                text=message_text
            )
            
            if send_result.success:
                result['success'] = True
                result['message_id'] = send_result.external_id
            else:
                result['error'] = send_result.error_message or "WhatsApp send failed"
                
        except Exception as e:
            logger.exception(f"Parent WhatsApp send error: {e}")
            result['error'] = str(e)
        
        return result
    
    @classmethod
    def _build_parent_whatsapp_message(cls, letter, parent_name: str) -> str:
        """Build WhatsApp message for parent/guardian."""
        lead = letter.lead
        qualification = letter.qualification
        campus = letter.campus
        brand_name = campus.brand.name if campus and campus.brand else "us"
        
        message = f"""👨‍👩‍👧 *Parent/Guardian Notification*

Dear {parent_name},

We're pleased to inform you that *{lead.first_name} {lead.last_name}* has been *pre-approved* for:

📚 *{qualification.name}*
🏫 {campus.name if campus else ''}

Reference: *{letter.letter_number}*
Valid until: {letter.valid_until.strftime('%d %B %Y')}

As {lead.first_name} is under 18, your consent is required to proceed with the enrollment application.

*To provide consent:*
🔗 Visit the portal link provided in your email
✅ Review the pre-approval letter
📝 Provide your digital consent

If you have any questions, please contact us.

Thank you for considering {brand_name}! 🎓"""

        return message
    
    @classmethod
    def _build_parent_email_text(cls, letter, parent_name: str) -> str:
        """Build plain text email for parent/guardian."""
        lead = letter.lead
        qualification = letter.qualification
        campus = letter.campus
        
        return f"""Dear {parent_name},

We are pleased to inform you that {lead.first_name} {lead.last_name} has been pre-approved for enrollment in:

Qualification: {qualification.name}
Campus: {campus.name if campus else 'N/A'}

Pre-approval Reference: {letter.letter_number}
Valid Until: {letter.valid_until.strftime('%d %B %Y')}

As {lead.first_name} is under 18 years of age, your consent is required to proceed with the enrollment application.

To provide your consent:
1. Click the portal link in this email
2. Review the pre-approval letter
3. Provide your digital consent

Your consent confirms that you approve of {lead.first_name} enrolling in this qualification.

If you have any questions or concerns, please don't hesitate to contact us.

Best regards,
{campus.name if campus else 'Admissions Team'}
"""