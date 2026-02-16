"""
Learner Profile Management Views
Handles profile editing, document uploads, and digital student card generation
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings
from learners.models import Learner, Document
from django.contrib.auth import get_user_model
import os
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64
import json

User = get_user_model()


class StudentProfileView(LoginRequiredMixin, TemplateView):
    """
    Student profile overview with personal details and document status.
    """
    template_name = 'portals/student/profile/overview.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        # Get uploaded documents
        documents = Document.objects.filter(learner=learner).order_by('-created_at')
        context['documents'] = documents
        
        # Check document completeness
        required_doc_types = ['ID_COPY', 'PROOF_ADDRESS']
        uploaded_types = documents.filter(
            document_type__in=required_doc_types,
            verified=True
        ).values_list('document_type', flat=True)
        
        context['documents_complete'] = all(
            doc_type in uploaded_types for doc_type in required_doc_types
        )
        
        # Profile completeness check
        profile_fields = [
            learner.sa_id_number,
            learner.date_of_birth,
            learner.gender,
            learner.phone_mobile,
            learner.physical_address,
            learner.province_code,
        ]
        
        filled_fields = sum(1 for field in profile_fields if field)
        context['profile_completeness'] = int((filled_fields / len(profile_fields)) * 100)
        
        return context


class StudentProfileEditView(LoginRequiredMixin, TemplateView):
    """
    Edit learner profile details.
    """
    template_name = 'portals/student/profile/edit.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        # Gender choices
        context['gender_choices'] = [
            ('M', 'Male'),
            ('F', 'Female'),
            ('O', 'Other'),
            ('N', 'Prefer not to say'),
        ]
        
        return context
    
    def post(self, request, *args, **kwargs):
        user = request.user
        learner = get_object_or_404(Learner, user=user)
        
        with transaction.atomic():
            # Update user fields
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.email = request.POST.get('email', '').strip()
            user.save()
            
            # Update learner fields
            learner.id_number = request.POST.get('id_number', '').strip()
            learner.date_of_birth = request.POST.get('date_of_birth') or None
            learner.gender = request.POST.get('gender', '')
            learner.phone_number = request.POST.get('phone_number', '').strip()
            learner.alternative_phone = request.POST.get('alternative_phone', '').strip()
            learner.address_line1 = request.POST.get('address_line1', '').strip()
            learner.address_line2 = request.POST.get('address_line2', '').strip()
            learner.city = request.POST.get('city', '').strip()
            learner.province = request.POST.get('province', '').strip()
            learner.postal_code = request.POST.get('postal_code', '').strip()
            
            # Emergency contact
            learner.emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()
            learner.emergency_contact_phone = request.POST.get('emergency_contact_phone', '').strip()
            learner.emergency_contact_relationship = request.POST.get('emergency_contact_relationship', '').strip()
            
            learner.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('portals:student_profile')


@login_required
def student_profile_photo_upload(request):
    """
    Upload or update profile photo.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    user = request.user
    learner = get_object_or_404(Learner, user=user)
    
    if 'photo' not in request.FILES:
        return JsonResponse({'error': 'No photo uploaded'}, status=400)
    
    photo = request.FILES['photo']
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
    if photo.content_type not in allowed_types:
        return JsonResponse({'error': 'Only JPEG and PNG images allowed'}, status=400)
    
    # Validate file size (max 5MB)
    if photo.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'File size must be under 5MB'}, status=400)
    
    # Delete old photo if exists
    if learner.profile_photo:
        old_photo_path = learner.profile_photo.path
        if os.path.exists(old_photo_path):
            os.remove(old_photo_path)
    
    # Save new photo
    learner.profile_photo = photo
    learner.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Profile photo updated successfully',
        'photo_url': learner.profile_photo.url if learner.profile_photo else None
    })


class StudentDocumentsView(LoginRequiredMixin, TemplateView):
    """
    Manage learner documents (ID, proof of address, etc.).
    """
    template_name = 'portals/student/profile/documents.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        # Get documents organized by type
        documents = Document.objects.filter(learner=learner).order_by('-created_at')
        context['documents'] = documents
        
        # Document types
        context['document_types'] = [
            ('ID_COPY', 'ID Document / Passport'),
            ('PROOF_ADDRESS', 'Proof of Address'),
            ('MATRIC', 'Matric Certificate'),
            ('QUALIFICATION', 'Prior Qualification'),
            ('BANK_CONFIRM', 'Bank Confirmation'),
            ('OTHER', 'Other Document'),
        ]
        
        # Group documents by type
        docs_by_type = {}
        for doc in documents:
            if doc.document_type not in docs_by_type:
                docs_by_type[doc.document_type] = []
            docs_by_type[doc.document_type].append(doc)
        
        context['docs_by_type'] = docs_by_type
        
        return context


@login_required
def student_document_upload(request):
    """
    Upload a new document.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    user = request.user
    learner = get_object_or_404(Learner, user=user)
    
    if 'document' not in request.FILES:
        return JsonResponse({'error': 'No document uploaded'}, status=400)
    
    document_file = request.FILES['document']
    document_type = request.POST.get('document_type', '')
    description = request.POST.get('description', '').strip()
    
    if not document_type:
        return JsonResponse({'error': 'Document type is required'}, status=400)
    
    # Validate file type
    allowed_types = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
    if document_file.content_type not in allowed_types:
        return JsonResponse({'error': 'Only PDF, JPEG, and PNG files allowed'}, status=400)
    
    # Validate file size (max 10MB)
    if document_file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'File size must be under 10MB'}, status=400)
    
    # Create document record
    doc = Document.objects.create(
        learner=learner,
        document_type=document_type,
        file=document_file,
        original_filename=document_file.name,
        file_size=document_file.size,
        title=description,
        verified=False
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Document uploaded successfully. Awaiting verification.',
        'document_id': doc.id
    })


@login_required
def student_document_delete(request, document_id):
    """
    Delete a document.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    user = request.user
    learner = get_object_or_404(Learner, user=user)
    
    document = get_object_or_404(Document, id=document_id, learner=learner)
    
    # Delete file from storage
    if document.file:
        document.file.delete()
    
    document.delete()
    
    return JsonResponse({
        'success': True,
        'message': 'Document deleted successfully'
    })


class StudentCardView(LoginRequiredMixin, TemplateView):
    """
    Display digital student card.
    """
    template_name = 'portals/student/profile/student_card.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        # Get active enrollment for program name
        from academics.models import Enrollment
        enrollment = Enrollment.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).select_related('qualification', 'campus').first()
        
        context['enrollment'] = enrollment
        
        # Generate barcode data URL
        if learner.learner_number:
            context['barcode_data'] = generate_barcode_data(learner.learner_number)
        
        return context


def generate_barcode_data(learner_number):
    """
    Generate barcode as base64 data URL.
    """
    try:
        # Generate Code128 barcode
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(str(learner_number), writer=ImageWriter())
        
        # Render to BytesIO
        buffer = BytesIO()
        barcode_instance.write(buffer, options={
            'module_height': 10,
            'module_width': 0.3,
            'quiet_zone': 2,
            'font_size': 10,
            'text_distance': 3,
        })
        
        # Convert to base64
        buffer.seek(0)
        barcode_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        return f"data:image/png;base64,{barcode_base64}"
    except Exception as e:
        return None


@login_required
def download_student_card(request):
    """
    Generate and download student card as image.
    """
    user = request.user
    learner = get_object_or_404(Learner, user=user)
    
    # Get enrollment for program details
    from academics.models import Enrollment
    enrollment = Enrollment.objects.filter(
        learner=learner,
        status='ACTIVE'
    ).select_related('qualification', 'campus').first()
    
    # Create student card image
    card_image = generate_student_card_image(learner, enrollment)
    
    # Return as downloadable image
    response = HttpResponse(content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="student_card_{learner.learner_number}.png"'
    card_image.save(response, 'PNG')
    
    return response


def generate_student_card_image(learner, enrollment=None):
    """
    Generate student card as PIL Image.
    """
    # Card dimensions (standard credit card size at 300 DPI: 1050 x 675)
    width, height = 1050, 675
    
    # Create blank card with gradient background
    card = Image.new('RGB', (width, height), '#1e3a8a')
    draw = ImageDraw.Draw(card)
    
    # Add gradient effect (simple top-to-bottom)
    for y in range(height):
        # Interpolate from dark blue to lighter blue
        r = int(30 + (50 - 30) * (y / height))
        g = int(58 + (100 - 58) * (y / height))
        b = int(138 + (200 - 138) * (y / height))
        draw.rectangle([(0, y), (width, y + 1)], fill=(r, g, b))
    
    # Load or use default fonts
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
        name_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        info_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except:
        title_font = ImageFont.load_default()
        name_font = ImageFont.load_default()
        info_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
    
    # Add logo/title
    draw.text((50, 40), "SkillsFlow Training", font=title_font, fill='white')
    draw.text((50, 105), "STUDENT CARD", font=label_font, fill='#93c5fd')
    
    # Add photo
    photo_x, photo_y = 50, 180
    photo_size = 200
    
    if learner.profile_photo and os.path.exists(learner.profile_photo.path):
        try:
            photo = Image.open(learner.profile_photo.path)
            photo = photo.resize((photo_size, photo_size), Image.Resampling.LANCZOS)
            
            # Create circular mask
            mask = Image.new('L', (photo_size, photo_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([(0, 0), (photo_size, photo_size)], fill=255)
            
            # Apply mask
            card.paste(photo, (photo_x, photo_y), mask)
        except:
            # Draw placeholder circle
            draw.ellipse([(photo_x, photo_y), (photo_x + photo_size, photo_y + photo_size)], 
                        fill='#3b82f6', outline='white', width=3)
    else:
        # Draw placeholder circle with initials
        draw.ellipse([(photo_x, photo_y), (photo_x + photo_size, photo_y + photo_size)], 
                    fill='#3b82f6', outline='white', width=3)
        
        # Add initials
        initials = f"{learner.user.first_name[0]}{learner.user.last_name[0]}".upper() if learner.user.first_name and learner.user.last_name else "?"
        bbox = draw.textbbox((0, 0), initials, font=title_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(
            (photo_x + photo_size//2 - text_width//2, photo_y + photo_size//2 - text_height//2),
            initials, font=title_font, fill='white'
        )
    
    # Add white border around photo
    draw.ellipse([(photo_x - 3, photo_y - 3), (photo_x + photo_size + 3, photo_y + photo_size + 3)], 
                outline='white', width=4)
    
    # Add learner details
    details_x = 300
    y_pos = 180
    
    # Full name
    full_name = learner.user.get_full_name().upper()
    draw.text((details_x, y_pos), full_name, font=name_font, fill='white')
    y_pos += 70
    
    # Learner number
    draw.text((details_x, y_pos), "Learner No:", font=label_font, fill='#93c5fd')
    draw.text((details_x, y_pos + 30), learner.learner_number or "N/A", font=info_font, fill='white')
    y_pos += 90
    
    # ID Number
    draw.text((details_x, y_pos), "ID Number:", font=label_font, fill='#93c5fd')
    draw.text((details_x, y_pos + 30), learner.id_number or "N/A", font=info_font, fill='white')
    y_pos += 90
    
    # Program
    if enrollment and enrollment.qualification:
        draw.text((details_x, y_pos), "Programme:", font=label_font, fill='#93c5fd')
        program_name = enrollment.qualification.name[:35]  # Truncate if too long
        draw.text((details_x, y_pos + 30), program_name, font=label_font, fill='white')
    
    # Add barcode at bottom
    if learner.learner_number:
        try:
            code128 = barcode.get_barcode_class('code128')
            barcode_instance = code128(str(learner.learner_number), writer=ImageWriter())
            
            buffer = BytesIO()
            barcode_instance.write(buffer, options={
                'module_height': 12,
                'module_width': 0.4,
                'quiet_zone': 2,
                'font_size': 0,  # No text below barcode
                'text_distance': 0,
            })
            
            buffer.seek(0)
            barcode_img = Image.open(buffer)
            
            # Resize barcode to fit
            barcode_width = 600
            barcode_height = int(barcode_img.height * (barcode_width / barcode_img.width))
            barcode_img = barcode_img.resize((barcode_width, barcode_height), Image.Resampling.LANCZOS)
            
            # Paste barcode
            barcode_x = (width - barcode_width) // 2
            barcode_y = height - barcode_height - 40
            
            # Create white background for barcode
            draw.rectangle([(barcode_x - 10, barcode_y - 10), 
                          (barcode_x + barcode_width + 10, barcode_y + barcode_height + 10)],
                         fill='white')
            
            card.paste(barcode_img, (barcode_x, barcode_y))
        except:
            pass
    
    # Add rounded corners
    card = add_rounded_corners(card, radius=40)
    
    return card


def add_rounded_corners(image, radius):
    """
    Add rounded corners to image.
    """
    # Create mask for rounded corners
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), image.size], radius=radius, fill=255)
    
    # Apply mask
    output = Image.new('RGBA', image.size, (255, 255, 255, 0))
    output.paste(image, (0, 0))
    output.putalpha(mask)
    
    return output


# =====================================================
# DIGITAL SIGNATURE CAPTURE VIEWS
# =====================================================

class StudentSignatureView(LoginRequiredMixin, TemplateView):
    """
    Digital signature capture for learners.
    Signatures are locked after first capture and can only be modified by admin.
    """
    template_name = 'portals/student/profile/signature.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        context['signature_locked'] = learner.signature_locked
        context['has_signature'] = bool(learner.signature)
        
        if learner.signature:
            context['signature_url'] = learner.signature.url
            context['signature_captured_at'] = learner.signature_captured_at
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle signature submission."""
        from core.services.signature_service import SignatureService
        
        user = request.user
        learner = get_object_or_404(Learner, user=user)
        
        # Check if already locked
        if learner.signature_locked:
            messages.error(request, 'Your signature is locked and cannot be changed. Contact support for assistance.')
            return redirect('portals:student_signature')
        
        # Get signature data
        signature_data = request.POST.get('signature_data', '')
        consent_given = request.POST.get('popia_consent') == 'on'
        
        if not signature_data:
            messages.error(request, 'Please provide your signature.')
            return redirect('portals:student_signature')
        
        if not consent_given:
            messages.error(request, 'You must accept the POPIA consent to proceed.')
            return redirect('portals:student_signature')
        
        # Capture signature
        service = SignatureService()
        success, message = service.capture_signature_for_learner(
            learner=learner,
            base64_data=signature_data,
            request=request,
            consent_given=consent_given
        )
        
        if success:
            messages.success(request, 'Your digital signature has been captured and locked successfully.')
        else:
            messages.error(request, message)
        
        return redirect('portals:student_signature')


@login_required
def student_signature_capture_api(request):
    """
    API endpoint for signature capture (AJAX).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    from core.services.signature_service import SignatureService
    
    user = request.user
    learner = get_object_or_404(Learner, user=user)
    
    try:
        data = json.loads(request.body)
        signature_data = data.get('signature_data', '')
        consent_given = data.get('popia_consent', False)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    service = SignatureService()
    success, message = service.capture_signature_for_learner(
        learner=learner,
        base64_data=signature_data,
        request=request,
        consent_given=consent_given
    )
    
    if success:
        return JsonResponse({
            'success': True,
            'message': message,
            'signature_url': learner.signature.url if learner.signature else None,
            'locked': learner.signature_locked
        })
    else:
        return JsonResponse({'success': False, 'error': message}, status=400)

