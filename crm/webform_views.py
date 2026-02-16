"""
Web Form Webhook Views
Handles incoming webhooks from Gravity Forms and other web form providers
"""
import json
import logging
from django.views import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from .models import (
    Lead, LeadSource, LeadActivity, 
    WebFormSource, WebFormMapping, WebFormSubmission,
    Pipeline, PipelineStage
)

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def normalize_phone(phone):
    """Normalize phone number for comparison."""
    if not phone:
        return ''
    # Remove all non-digit characters
    digits = ''.join(c for c in str(phone) if c.isdigit())
    # Handle South African numbers
    if digits.startswith('27') and len(digits) > 9:
        digits = '0' + digits[2:]
    elif digits.startswith('0') and len(digits) == 10:
        pass  # Already normalized
    return digits


def find_duplicate_lead(email, phone, whatsapp, campus):
    """
    Find existing lead by email or phone within the same campus.
    Returns the lead if found, None otherwise.
    """
    if not email and not phone and not whatsapp:
        return None
    
    # Normalize phones for comparison
    phone_normalized = normalize_phone(phone)
    whatsapp_normalized = normalize_phone(whatsapp)
    
    # Build query conditions
    conditions = Q()
    
    if email:
        conditions |= Q(email__iexact=email)
    
    if phone_normalized:
        # Check phone and whatsapp fields
        conditions |= Q(phone__icontains=phone_normalized[-9:])  # Last 9 digits
        conditions |= Q(whatsapp_number__icontains=phone_normalized[-9:])
    
    if whatsapp_normalized and whatsapp_normalized != phone_normalized:
        conditions |= Q(phone__icontains=whatsapp_normalized[-9:])
        conditions |= Q(whatsapp_number__icontains=whatsapp_normalized[-9:])
    
    if not conditions:
        return None
    
    # Search within campus
    return Lead.objects.filter(conditions, campus=campus).first()


@method_decorator(csrf_exempt, name='dispatch')
class WebFormWebhookView(View):
    """
    Webhook endpoint for receiving web form submissions.
    
    URL: /crm/webhooks/web-forms/<uuid:source_id>/
    
    Security:
    - Each source has a unique URL with embedded UUID
    - Optional X-Webhook-Secret header verification
    
    Expected payload (Gravity Forms format):
    {
        "form_id": "1",
        "entry": {
            "1.3": "John",      // First name (compound field)
            "1.6": "Doe",       // Last name
            "2": "john@example.com",
            "3": "0821234567"
        }
    }
    
    Or simplified format:
    {
        "form_id": "1",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone": "0821234567"
    }
    """
    
    def post(self, request, source_id):
        """Handle incoming form submission."""
        submission = None
        
        try:
            # Get the source
            try:
                source = WebFormSource.objects.get(id=source_id, is_active=True)
            except WebFormSource.DoesNotExist:
                logger.warning(f"Web form webhook: Invalid source ID {source_id}")
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid webhook source'
                }, status=404)
            
            # Verify webhook secret if configured
            if source.webhook_secret:
                provided_secret = request.headers.get('X-Webhook-Secret', '')
                if provided_secret != source.webhook_secret:
                    logger.warning(f"Web form webhook: Invalid secret for source {source.name}")
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid webhook secret'
                    }, status=401)
            
            # Parse payload
            try:
                payload = json.loads(request.body)
            except json.JSONDecodeError as e:
                logger.error(f"Web form webhook: Invalid JSON - {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JSON payload'
                }, status=400)
            
            # Extract form ID
            form_id = str(payload.get('form_id', payload.get('formId', '')))
            if not form_id:
                # Try to use default mapping
                form_id = 'default'
            
            # Find form mapping
            form_mapping = WebFormMapping.objects.filter(
                source=source,
                form_id=form_id,
                is_active=True
            ).first()
            
            # If no specific mapping, try default
            if not form_mapping:
                form_mapping = WebFormMapping.objects.filter(
                    source=source,
                    form_id='default',
                    is_active=True
                ).first()
            
            # Get campus
            campus = form_mapping.get_campus() if form_mapping else source.default_campus
            if not campus:
                logger.error(f"Web form webhook: No campus configured for source {source.name}")
                return JsonResponse({
                    'success': False,
                    'error': 'No campus configured for this form'
                }, status=400)
            
            # Extract form data
            # Handle Gravity Forms "entry" format or flat format
            form_data = payload.get('entry', payload)
            
            # Map form data to lead fields
            if form_mapping:
                mapped_data = form_mapping.map_form_data(form_data)
            else:
                # Use direct field names if no mapping
                mapped_data = {
                    'first_name': form_data.get('first_name', ''),
                    'last_name': form_data.get('last_name', ''),
                    'email': form_data.get('email', ''),
                    'phone': form_data.get('phone', ''),
                    'whatsapp_number': form_data.get('whatsapp_number', form_data.get('whatsapp', '')),
                }
            
            # Create submission log
            submission = WebFormSubmission.objects.create(
                source=source,
                form_mapping=form_mapping,
                raw_payload=payload,
                mapped_data=mapped_data,
                status='FAILED',  # Will update on success
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            
            # Validate required fields
            first_name = mapped_data.get('first_name', '').strip()
            last_name = mapped_data.get('last_name', '').strip()
            email = mapped_data.get('email', '').strip()
            phone = mapped_data.get('phone', '').strip()
            whatsapp = mapped_data.get('whatsapp_number', '').strip()
            
            if not first_name or not last_name:
                submission.status = 'FAILED'
                submission.error_message = 'First name and last name are required'
                submission.save()
                return JsonResponse({
                    'success': False,
                    'error': 'First name and last name are required'
                }, status=400)
            
            if not email and not phone and not whatsapp:
                submission.status = 'FAILED'
                submission.error_message = 'At least one contact method (email, phone, or WhatsApp) is required'
                submission.save()
                return JsonResponse({
                    'success': False,
                    'error': 'At least one contact method required'
                }, status=400)
            
            # Get or create lead source
            lead_source = source.default_lead_source
            if not lead_source:
                lead_source, _ = LeadSource.objects.get_or_create(
                    code='WEB_FORM',
                    defaults={
                        'name': 'Web Form',
                        'description': 'Lead captured via website form'
                    }
                )
            
            # Check for duplicate
            existing_lead = find_duplicate_lead(email, phone, whatsapp, campus)
            
            with transaction.atomic():
                if existing_lead:
                    # Update existing lead with new information
                    lead = existing_lead
                    updated_fields = []
                    
                    # Update fields if they're empty or if new data is better
                    field_updates = {
                        'phone': phone,
                        'email': email,
                        'whatsapp_number': whatsapp,
                        'school_name': mapped_data.get('school_name', ''),
                        'grade': mapped_data.get('grade', ''),
                        'parent_name': mapped_data.get('parent_name', ''),
                        'parent_phone': mapped_data.get('parent_phone', ''),
                        'parent_email': mapped_data.get('parent_email', ''),
                        'employer_name': mapped_data.get('employer_name', ''),
                    }
                    
                    for field, value in field_updates.items():
                        if value and not getattr(lead, field, None):
                            setattr(lead, field, value)
                            updated_fields.append(field)
                    
                    if updated_fields:
                        lead.save()
                    
                    # Add activity note
                    activity_details = f"Form: {form_mapping.form_name if form_mapping else 'Unknown'}\n"
                    activity_details += f"Source: {source.name}\n"
                    activity_details += f"Updated fields: {', '.join(updated_fields) if updated_fields else 'None'}\n"
                    activity_details += f"Submitted data: {json.dumps(mapped_data, indent=2)}"
                    
                    LeadActivity.objects.create(
                        lead=lead,
                        activity_type='NOTE',
                        description=f"Duplicate web form submission received.\n{activity_details}",
                        created_by=None  # System
                    )
                    
                    # Update stats
                    submission.status = 'DUPLICATE'
                    submission.lead = lead
                    submission.save()
                    
                    source.total_duplicates_updated += 1
                    source.last_submission_at = timezone.now()
                    source.save(update_fields=['total_duplicates_updated', 'last_submission_at'])
                    
                    if form_mapping:
                        form_mapping.duplicates_updated += 1
                        form_mapping.last_submission_at = timezone.now()
                        form_mapping.save(update_fields=['duplicates_updated', 'last_submission_at'])
                    
                    logger.info(f"Web form webhook: Updated duplicate lead {lead.id} from {source.name}")
                    
                    return JsonResponse({
                        'success': True,
                        'lead_id': lead.id,
                        'action': 'updated',
                        'message': 'Existing lead updated with new submission'
                    })
                
                else:
                    # Create new lead
                    lead_data = {
                        'campus': campus,
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': email,
                        'phone': phone,
                        'whatsapp_number': whatsapp,
                        'source': lead_source,
                        'status': 'NEW',
                        'priority': 'MEDIUM',
                    }
                    
                    # Add optional fields
                    optional_fields = [
                        'phone_secondary', 'date_of_birth', 'school_name', 'grade',
                        'expected_matric_year', 'parent_name', 'parent_phone',
                        'parent_email', 'parent_relationship', 'employer_name',
                        'highest_qualification', 'employment_status', 'notes'
                    ]
                    
                    for field in optional_fields:
                        value = mapped_data.get(field)
                        if value:
                            # Handle special cases
                            if field == 'date_of_birth':
                                try:
                                    from datetime import datetime
                                    # Try common date formats
                                    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                                        try:
                                            lead_data[field] = datetime.strptime(value, fmt).date()
                                            break
                                        except ValueError:
                                            continue
                                except Exception:
                                    pass  # Skip invalid dates
                            elif field == 'expected_matric_year':
                                try:
                                    lead_data[field] = int(value)
                                except (ValueError, TypeError):
                                    pass
                            else:
                                lead_data[field] = value
                    
                    # Set lead type from mapping
                    if form_mapping and form_mapping.lead_type:
                        lead_data['lead_type'] = form_mapping.lead_type
                    
                    # Set qualification interest
                    if form_mapping and form_mapping.qualification:
                        lead_data['qualification_interest'] = form_mapping.qualification
                    
                    # Set auto-assign
                    if form_mapping and form_mapping.auto_assign_to:
                        lead_data['assigned_to'] = form_mapping.auto_assign_to
                    
                    # Set pipeline
                    if form_mapping and form_mapping.pipeline:
                        lead_data['pipeline'] = form_mapping.pipeline
                        # Get first stage
                        first_stage = form_mapping.pipeline.stages.order_by('order').first()
                        if first_stage:
                            lead_data['current_stage'] = first_stage
                            lead_data['stage_entered_at'] = timezone.now()
                    
                    # Create the lead
                    lead = Lead.objects.create(**lead_data)
                    
                    # Add activity
                    activity_details = f"Form: {form_mapping.form_name if form_mapping else 'Direct submission'}\n"
                    activity_details += f"Source: {source.name}\n"
                    activity_details += f"Domain: {source.domain}"
                    
                    LeadActivity.objects.create(
                        lead=lead,
                        activity_type='NOTE',
                        description=f"Lead created from web form submission.\n{activity_details}",
                        created_by=None
                    )
                    
                    # Update stats
                    submission.status = 'SUCCESS'
                    submission.lead = lead
                    submission.save()
                    
                    source.total_leads_created += 1
                    source.last_submission_at = timezone.now()
                    source.save(update_fields=['total_leads_created', 'last_submission_at'])
                    
                    if form_mapping:
                        form_mapping.leads_created += 1
                        form_mapping.last_submission_at = timezone.now()
                        form_mapping.save(update_fields=['leads_created', 'last_submission_at'])
                    
                    logger.info(f"Web form webhook: Created lead {lead.id} from {source.name}")
                    
                    return JsonResponse({
                        'success': True,
                        'lead_id': lead.id,
                        'action': 'created',
                        'message': 'Lead created successfully'
                    })
        
        except Exception as e:
            logger.exception(f"Web form webhook error: {e}")
            
            if submission:
                submission.status = 'FAILED'
                submission.error_message = str(e)
                submission.save()
            
            return JsonResponse({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    def get(self, request, source_id):
        """Handle GET request (for webhook verification)."""
        try:
            source = WebFormSource.objects.get(id=source_id, is_active=True)
            return JsonResponse({
                'success': True,
                'message': f'Webhook endpoint active for {source.name}',
                'source_id': str(source_id)
            })
        except WebFormSource.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid webhook source'
            }, status=404)


@method_decorator(csrf_exempt, name='dispatch')
class WebFormTestView(View):
    """
    Test endpoint for verifying webhook configuration.
    Returns the mapped field data without creating a lead.
    """
    
    def post(self, request, source_id):
        """Test form data mapping without creating lead."""
        try:
            source = WebFormSource.objects.get(id=source_id, is_active=True)
        except WebFormSource.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid webhook source'
            }, status=404)
        
        # Verify secret
        if source.webhook_secret:
            provided_secret = request.headers.get('X-Webhook-Secret', '')
            if provided_secret != source.webhook_secret:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid webhook secret'
                }, status=401)
        
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON payload'
            }, status=400)
        
        form_id = str(payload.get('form_id', 'default'))
        form_data = payload.get('entry', payload)
        
        form_mapping = WebFormMapping.objects.filter(
            source=source,
            form_id=form_id,
            is_active=True
        ).first()
        
        if form_mapping:
            mapped_data = form_mapping.map_form_data(form_data)
        else:
            mapped_data = form_data
        
        return JsonResponse({
            'success': True,
            'test_mode': True,
            'source': source.name,
            'form_id': form_id,
            'form_mapping_found': form_mapping is not None,
            'form_mapping_name': form_mapping.form_name if form_mapping else None,
            'raw_data': form_data,
            'mapped_data': mapped_data,
            'campus': str(form_mapping.get_campus()) if form_mapping and form_mapping.get_campus() else str(source.default_campus)
        })
