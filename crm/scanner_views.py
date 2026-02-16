"""
Views for Contact Card Scanner feature
"""
import json
import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.db import transaction

from .models import Lead, LeadSource, LeadActivity
from .services.card_scanner import get_card_scanner
from tenants.models import Campus
from academics.models import Qualification
from core.context_processors import get_selected_campus

logger = logging.getLogger(__name__)


@login_required
def card_scanner_view(request):
    """Main card scanner page with batch support"""
    scanner = get_card_scanner()
    
    # Get global campus selection
    selected_campus = get_selected_campus(request)
    
    context = {
        'scanner_available': scanner.is_available(),
        'campuses': Campus.objects.filter(is_active=True).order_by('name'),
        'qualifications': Qualification.objects.filter(is_active=True).order_by('title'),
        'lead_sources': LeadSource.objects.filter(is_active=True),
        'default_campus': selected_campus,  # Pre-select global campus
    }
    
    # Get or create CARD_SCAN source
    card_scan_source, _ = LeadSource.objects.get_or_create(
        code='CARD_SCAN',
        defaults={'name': 'Card Scan', 'description': 'Lead captured via AI card scanner'}
    )
    context['card_scan_source'] = card_scan_source
    
    return render(request, 'crm/card_scanner.html', context)


@login_required
@require_POST
def scan_card_api(request):
    """API endpoint to scan a single card image"""
    scanner = get_card_scanner()
    
    if not scanner.is_available():
        return JsonResponse({
            'success': False,
            'error': 'Card scanner not available. Please configure OpenAI API key.'
        }, status=503)
    
    # Get uploaded image
    if 'image' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'No image provided'
        }, status=400)
    
    image_file = request.FILES['image']
    
    # Validate file size (max 20MB)
    if image_file.size > 20 * 1024 * 1024:
        return JsonResponse({
            'success': False,
            'error': 'Image too large. Maximum size is 20MB.'
        }, status=400)
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
    if image_file.content_type not in allowed_types:
        return JsonResponse({
            'success': False,
            'error': f'Invalid file type. Allowed: {", ".join(allowed_types)}'
        }, status=400)
    
    try:
        image_data = image_file.read()
        result = scanner.scan_card(image_data)
        
        return JsonResponse({
            'success': True,
            'data': result.to_dict(),
            'has_minimum_data': result.has_minimum_data()
        })
        
    except Exception as e:
        logger.exception(f"Error in scan_card_api: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def create_lead_from_scan(request):
    """Create a lead from scanned card data"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    # Validate required fields
    if not data.get('first_name') and not data.get('last_name'):
        return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)
    
    if not (data.get('email') or data.get('phone') or data.get('whatsapp_number')):
        return JsonResponse({'success': False, 'error': 'At least one contact method required'}, status=400)
    
    # Get campus
    campus_id = data.get('campus_id')
    if not campus_id:
        # Default to user's campus if available
        if hasattr(request.user, 'profile') and request.user.profile.campus:
            campus = request.user.profile.campus
        else:
            # Get first active campus as fallback
            campus = Campus.objects.filter(is_active=True).first()
            if not campus:
                return JsonResponse({'success': False, 'error': 'Campus is required'}, status=400)
    else:
        try:
            campus = Campus.objects.get(id=campus_id, is_active=True)
        except Campus.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid campus'}, status=400)
    
    # Get or create CARD_SCAN source
    source, _ = LeadSource.objects.get_or_create(
        code='CARD_SCAN',
        defaults={'name': 'Card Scan', 'description': 'Lead captured via AI card scanner'}
    )
    
    # Get qualification if specified
    qualification = None
    qual_id = data.get('qualification_interest_id')
    if qual_id:
        try:
            qualification = Qualification.objects.get(id=qual_id)
        except Qualification.DoesNotExist:
            pass
    
    # Determine lead type
    lead_type = 'ADULT'
    if data.get('school_name') or data.get('grade'):
        lead_type = 'SCHOOL_LEAVER'
    elif data.get('employer_name'):
        lead_type = 'CORPORATE'
    
    try:
        with transaction.atomic():
            lead = Lead.objects.create(
                campus=campus,
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
                email=data.get('email', ''),
                phone=data.get('phone', '').replace(' ', ''),
                phone_secondary=data.get('phone_secondary', '').replace(' ', ''),
                whatsapp_number=data.get('whatsapp_number', '').replace(' ', ''),
                school_name=data.get('school_name', ''),
                grade=data.get('grade', ''),
                expected_matric_year=data.get('expected_matric_year'),
                parent_name=data.get('parent_name', ''),
                parent_phone=data.get('parent_phone', '').replace(' ', ''),
                parent_email=data.get('parent_email', ''),
                parent_relationship=data.get('parent_relationship', ''),
                employer_name=data.get('employer_name', ''),
                notes=data.get('notes', ''),
                source=source,
                qualification_interest=qualification,
                lead_type=lead_type,
                status='NEW',
                priority='MEDIUM',
                assigned_to=request.user,
                created_by=request.user,
            )
            
            # Log activity
            LeadActivity.objects.create(
                lead=lead,
                activity_type='NOTE',
                description=f'Lead created via card scanner by {request.user.get_full_name()}',
                created_by=request.user
            )
            
            return JsonResponse({
                'success': True,
                'lead_id': lead.id,
                'message': f'Lead created: {lead.first_name} {lead.last_name}'
            })
            
    except Exception as e:
        logger.exception(f"Error creating lead: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def create_leads_batch(request):
    """Create multiple leads from batch scan"""
    try:
        data = json.loads(request.body)
        leads_data = data.get('leads', [])
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    if not leads_data:
        return JsonResponse({'success': False, 'error': 'No leads provided'}, status=400)
    
    # Get default campus
    default_campus_id = data.get('default_campus_id')
    default_campus = None
    if default_campus_id:
        try:
            default_campus = Campus.objects.get(id=default_campus_id, is_active=True)
        except Campus.DoesNotExist:
            pass
    
    if not default_campus:
        if hasattr(request.user, 'profile') and request.user.profile.campus:
            default_campus = request.user.profile.campus
        else:
            # Get first active campus as fallback
            default_campus = Campus.objects.filter(is_active=True).first()
            if not default_campus:
                return JsonResponse({'success': False, 'error': 'Default campus is required'}, status=400)
    
    # Get or create CARD_SCAN source
    source, _ = LeadSource.objects.get_or_create(
        code='CARD_SCAN',
        defaults={'name': 'Card Scan', 'description': 'Lead captured via AI card scanner'}
    )
    
    results = []
    created_count = 0
    error_count = 0
    
    for lead_data in leads_data:
        try:
            # Skip if no minimum data
            if not (lead_data.get('first_name') or lead_data.get('last_name')):
                results.append({'success': False, 'error': 'No name', 'data': lead_data})
                error_count += 1
                continue
            
            if not (lead_data.get('email') or lead_data.get('phone') or lead_data.get('whatsapp_number')):
                results.append({'success': False, 'error': 'No contact info', 'data': lead_data})
                error_count += 1
                continue
            
            # Get campus for this lead or use default
            campus = default_campus
            if lead_data.get('campus_id'):
                try:
                    campus = Campus.objects.get(id=lead_data['campus_id'], is_active=True)
                except Campus.DoesNotExist:
                    pass
            
            # Get qualification
            qualification = None
            if lead_data.get('qualification_interest_id'):
                try:
                    qualification = Qualification.objects.get(id=lead_data['qualification_interest_id'])
                except Qualification.DoesNotExist:
                    pass
            
            # Determine lead type
            lead_type = 'ADULT'
            if lead_data.get('school_name') or lead_data.get('grade'):
                lead_type = 'SCHOOL_LEAVER'
            elif lead_data.get('employer_name'):
                lead_type = 'CORPORATE'
            
            with transaction.atomic():
                lead = Lead.objects.create(
                    campus=campus,
                    first_name=lead_data.get('first_name', ''),
                    last_name=lead_data.get('last_name', ''),
                    email=lead_data.get('email', ''),
                    phone=lead_data.get('phone', '').replace(' ', ''),
                    phone_secondary=lead_data.get('phone_secondary', '').replace(' ', ''),
                    whatsapp_number=lead_data.get('whatsapp_number', '').replace(' ', ''),
                    school_name=lead_data.get('school_name', ''),
                    grade=lead_data.get('grade', ''),
                    expected_matric_year=lead_data.get('expected_matric_year'),
                    parent_name=lead_data.get('parent_name', ''),
                    parent_phone=lead_data.get('parent_phone', '').replace(' ', ''),
                    parent_email=lead_data.get('parent_email', ''),
                    parent_relationship=lead_data.get('parent_relationship', ''),
                    employer_name=lead_data.get('employer_name', ''),
                    notes=lead_data.get('notes', ''),
                    source=source,
                    qualification_interest=qualification,
                    lead_type=lead_type,
                    status='NEW',
                    priority='MEDIUM',
                    assigned_to=request.user,
                    created_by=request.user,
                )
                
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type='NOTE',
                    description=f'Lead created via batch card scanner by {request.user.get_full_name()}',
                    created_by=request.user
                )
                
                results.append({
                    'success': True,
                    'lead_id': lead.id,
                    'name': f'{lead.first_name} {lead.last_name}'
                })
                created_count += 1
                
        except Exception as e:
            logger.exception(f"Error creating lead in batch: {e}")
            results.append({'success': False, 'error': str(e), 'data': lead_data})
            error_count += 1
    
    return JsonResponse({
        'success': True,
        'created': created_count,
        'errors': error_count,
        'results': results
    })
