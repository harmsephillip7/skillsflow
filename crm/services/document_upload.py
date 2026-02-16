"""
Document Upload Service

Handles:
- Sending document upload links via WhatsApp, Email
- Building portal URLs
- Message formatting
"""
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


class DocumentUploadService:
    """
    Service for sending document upload links to leads.
    """
    
    def send_upload_link(
        self,
        upload_request,
        send_via: str = 'whatsapp',
        recipient: str = 'learner',
    ) -> Dict[str, Any]:
        """
        Send document upload link via the specified channel(s).
        
        Args:
            upload_request: DocumentUploadRequest instance
            send_via: 'whatsapp', 'email', or 'both'
            recipient: 'learner' or 'parent'
            
        Returns:
            Dict with success status and details
        """
        result = {
            'success': False,
            'channel': send_via,
            'error': None,
            'sent_channels': [],
        }
        
        lead = upload_request.lead
        portal_url = upload_request.get_full_portal_url()
        
        # Determine contact details based on recipient
        if recipient == 'parent' and lead.parent_name:
            contact_name = lead.parent_name
            contact_phone = lead.parent_phone or lead.phone
            contact_email = lead.parent_email or lead.email
            is_parent = True
        else:
            contact_name = lead.first_name
            contact_phone = lead.whatsapp_number or lead.phone
            contact_email = lead.email
            is_parent = False
        
        # Build document type names for the message
        from crm.models import LeadDocument
        type_display = dict(LeadDocument.DOCUMENT_TYPES)
        doc_names = [type_display.get(dt, dt) for dt in upload_request.requested_document_types]
        
        # Send via requested channel(s)
        errors = []
        
        if send_via in ['whatsapp', 'both']:
            if contact_phone:
                try:
                    wa_result = self._send_via_whatsapp(
                        upload_request, 
                        contact_phone, 
                        portal_url,
                        doc_names,
                        contact_name=contact_name,
                        is_parent=is_parent,
                        learner_name=lead.first_name,
                    )
                    if wa_result.get('success'):
                        result['sent_channels'].append('whatsapp')
                    else:
                        errors.append(f"WhatsApp: {wa_result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"WhatsApp send failed: {e}")
                    errors.append(f"WhatsApp: {str(e)}")
            else:
                errors.append("WhatsApp: No phone number available")
        
        if send_via in ['email', 'both']:
            if contact_email:
                try:
                    email_result = self._send_via_email(
                        upload_request, 
                        contact_email, 
                        portal_url,
                        doc_names,
                        contact_name=contact_name,
                        is_parent=is_parent,
                        learner_name=lead.first_name,
                    )
                    if email_result.get('success'):
                        result['sent_channels'].append('email')
                    else:
                        errors.append(f"Email: {email_result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"Email send failed: {e}")
                    errors.append(f"Email: {str(e)}")
            else:
                errors.append("Email: No email address available")
        
        # Determine overall success
        if result['sent_channels']:
            result['success'] = True
            channels_str = ' and '.join(result['sent_channels'])
            result['message'] = f'Document upload link sent via {channels_str}!'
        else:
            result['error'] = '; '.join(errors) if errors else 'No channels available'
        
        return result
    
    def _send_via_whatsapp(
        self, 
        upload_request, 
        phone: str, 
        portal_url: str,
        doc_names: list,
        contact_name: str = None,
        is_parent: bool = False,
        learner_name: str = None,
    ) -> Dict[str, Any]:
        """
        Send document upload link via WhatsApp.
        """
        from integrations.whatsapp.connector import WhatsAppConnector
        
        lead = upload_request.lead
        
        # Build message
        message = self._build_whatsapp_message(
            lead, 
            portal_url, 
            doc_names, 
            upload_request.message,
            contact_name=contact_name,
            is_parent=is_parent,
            learner_name=learner_name,
        )
        
        # Attempt to send
        try:
            connector = WhatsAppConnector()
            response = connector.send_text_message(
                to=phone,
                message=message,
            )
            
            if response.get('success'):
                logger.info(f"WhatsApp document upload link sent to {phone} for lead {lead.pk}")
                return {'success': True, 'message_id': response.get('message_id')}
            else:
                return {'success': False, 'error': response.get('error', 'Send failed')}
        except Exception as e:
            logger.error(f"WhatsApp send error for lead {lead.pk}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _build_whatsapp_message(
        self, 
        lead, 
        portal_url: str, 
        doc_names: list,
        custom_message: str = '',
        contact_name: str = None,
        is_parent: bool = False,
        learner_name: str = None,
    ) -> str:
        """
        Build WhatsApp message for document upload request.
        """
        # Format document list
        doc_list = '\n'.join([f"• {name}" for name in doc_names])
        
        # Use provided contact name or default to lead's first name
        name = contact_name or lead.first_name
        
        # Build message - different for parent vs learner
        if is_parent and learner_name:
            message = f"""Hi {name}! 👋

We need a few documents for {learner_name}'s application.

*Required Documents:*
{doc_list}

"""
        else:
            message = f"""Hi {name}! 👋

We need a few documents to continue processing your application.

*Required Documents:*
{doc_list}

"""
        if custom_message:
            message += f"{custom_message}\n\n"
        
        message += f"""📄 *Click here to upload:*
{portal_url}

This link is valid for 14 days. If you have any questions, please reply to this message.

Thank you!"""
        
        return message
    
    def _send_via_email(
        self, 
        upload_request, 
        email: str, 
        portal_url: str,
        doc_names: list,
        contact_name: str = None,
        is_parent: bool = False,
        learner_name: str = None,
    ) -> Dict[str, Any]:
        """
        Send document upload link via email.
        """
        lead = upload_request.lead
        
        # Get brand for email
        brand_name = 'SkillsFlow'
        if lead.qualification_interest and hasattr(lead.qualification_interest, 'campus'):
            if lead.qualification_interest.campus and lead.qualification_interest.campus.brand:
                brand_name = lead.qualification_interest.campus.brand.name
        
        # Build email content
        subject = f"Document Upload Request - {brand_name}"
        
        # Render HTML template
        html_content = render_to_string('crm/emails/document_upload_email.html', {
            'lead': lead,
            'upload_request': upload_request,
            'portal_url': portal_url,
            'doc_names': doc_names,
            'brand_name': brand_name,
            'custom_message': upload_request.message,
            'contact_name': contact_name or lead.first_name,
            'is_parent': is_parent,
            'learner_name': learner_name,
        })
        
        # Plain text fallback
        text_content = self._build_email_text(
            lead, 
            portal_url, 
            doc_names, 
            upload_request.message,
            contact_name=contact_name,
            is_parent=is_parent,
            learner_name=learner_name,
        )
        
        try:
            # Send email
            email_message = EmailMessage(
                subject=subject,
                body=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )
            email_message.content_subtype = 'html'
            email_message.send(fail_silently=False)
            
            logger.info(f"Email document upload link sent to {email} for lead {lead.pk}")
            return {'success': True}
        except Exception as e:
            logger.error(f"Email send error for lead {lead.pk}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _build_email_text(
        self, 
        lead, 
        portal_url: str, 
        doc_names: list,
        custom_message: str = '',
        contact_name: str = None,
        is_parent: bool = False,
        learner_name: str = None,
    ) -> str:
        """
        Build plain text email content.
        """
        doc_list = '\n'.join([f"- {name}" for name in doc_names])
        name = contact_name or lead.first_name
        
        if is_parent and learner_name:
            text = f"""Hi {name},

We need a few documents for {learner_name}'s application.

Required Documents:
{doc_list}

"""
        else:
            text = f"""Hi {name},

We need a few documents to continue processing your application.

Required Documents:
{doc_list}

"""
        if custom_message:
            text += f"{custom_message}\n\n"
        
        text += f"""Click here to upload your documents:
{portal_url}

This link is valid for 14 days. If you have any questions, please reply to this email.

Thank you!"""
        
        return text
