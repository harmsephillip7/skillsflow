"""
CRM Quote Views
Quote creation, management, and public access views
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DetailView, TemplateView
from django.views import View
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from decimal import Decimal

from .models import Lead, LeadActivity, LeadEngagement, AgentNotification
from .views import CRMAccessMixin
from finance.models import Quote, QuoteLineItem, QuotePaymentSchedule, QuoteTemplate, PaymentOption
from finance.services.quote_service import QuoteService
from academics.models import Qualification
from intakes.models import Intake
from core.context_processors import get_selected_campus


class QuickQuoteView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    Streamlined quote builder for private learners.
    Auto-populates from lead's qualification interest.
    Single-step: select payment plan, preview, and send.
    """
    template_name = 'crm/quick_quote.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead_pk = self.kwargs.get('lead_pk')
        lead = get_object_or_404(Lead, pk=lead_pk)
        context['lead'] = lead
        
        # Get qualification from lead's interest
        qualification = lead.qualification_interest
        context['qualification'] = qualification
        
        # Get pricing if qualification exists
        if qualification:
            current_year = timezone.now().year
            enrollment_year = self._get_enrollment_year(lead)
            academic_year = current_year if enrollment_year == 'CURRENT' else (
                current_year + 1 if enrollment_year == 'NEXT' else current_year + 2
            )
            
            context['pricing'] = QuoteService.get_pricing_for_qualification(qualification, academic_year)
            context['enrollment_year'] = enrollment_year
            context['academic_year'] = academic_year
        
        # Get default template for this campus
        templates = QuoteService.get_available_templates(lead.campus)
        context['default_template'] = templates.first() if templates.exists() else None
        context['templates'] = templates
        
        # Payment options
        context['payment_options'] = PaymentOption.objects.filter(is_active=True).order_by('sort_order')
        
        # Check if lead has WhatsApp
        context['has_whatsapp'] = bool(lead.whatsapp_number or lead.phone)
        context['has_email'] = bool(lead.email)
        
        # Recent quotes for this lead
        context['existing_quotes'] = Quote.objects.filter(
            lead=lead
        ).order_by('-created_at')[:5]
        
        return context
    
    def _get_enrollment_year(self, lead):
        """Determine enrollment year based on lead type and matric year."""
        current_year = timezone.now().year
        
        if lead.lead_type == 'SCHOOL_LEAVER' and lead.expected_matric_year:
            if lead.expected_matric_year == current_year:
                return 'CURRENT'
            elif lead.expected_matric_year == current_year + 1:
                return 'NEXT'
            elif lead.expected_matric_year > current_year + 1:
                return 'PLUS_TWO'
        
        return 'CURRENT'
    
    def post(self, request, *args, **kwargs):
        """Create and optionally send quote."""
        lead_pk = self.kwargs.get('lead_pk')
        lead = get_object_or_404(Lead, pk=lead_pk)
        
        qualification = lead.qualification_interest
        if not qualification:
            messages.error(request, 'Lead has no qualification interest set.')
            return redirect('crm:lead_detail', pk=lead.pk)
        
        # Get form data
        payment_option_id = request.POST.get('payment_option')
        template_id = request.POST.get('template')
        enrollment_year = request.POST.get('enrollment_year', 'CURRENT')
        notes = request.POST.get('notes', '')
        send_method = request.POST.get('send_method')  # 'email', 'whatsapp', or empty
        
        # Get objects
        payment_option = None
        template = None
        
        if payment_option_id:
            payment_option = get_object_or_404(PaymentOption, pk=payment_option_id)
        
        if template_id:
            template = get_object_or_404(QuoteTemplate, pk=template_id)
        
        try:
            # Create the quote
            quote = QuoteService.create_quote_from_lead(
                lead=lead,
                qualification=qualification,
                intake=None,
                enrollment_year=enrollment_year,
                payment_plan='UPFRONT',  # Legacy fallback
                created_by=request.user,
                campus=lead.campus,
                template=template,
                payment_option=payment_option
            )
            
            if notes:
                quote.notes = notes
                quote.save(update_fields=['notes'])
            
            # Log activity
            LeadActivity.objects.create(
                lead=lead,
                activity_type='QUOTE_SENT',
                description=f'Quote {quote.quote_number} created for {qualification.name}',
                created_by=request.user
            )
            
            # Send if requested
            if send_method == 'email' and lead.email:
                QuoteService.send_email(quote, lead.email, request)
                messages.success(request, f'Quote {quote.quote_number} created and sent via email.')
                
                # Move lead to Proposal stage if pipeline exists
                self._move_to_proposal_stage(lead, request.user)
                
            elif send_method == 'whatsapp':
                phone = lead.whatsapp_number or lead.phone
                if phone:
                    public_url = request.build_absolute_uri(
                        reverse('finance:quote_public_view', kwargs={'token': quote.public_token})
                    )
                    QuoteService.send_whatsapp_link(quote, phone, public_url)
                    messages.success(request, f'Quote {quote.quote_number} created and sent via WhatsApp.')
                    
                    # Move lead to Proposal stage if pipeline exists
                    self._move_to_proposal_stage(lead, request.user)
            else:
                messages.success(request, f'Quote {quote.quote_number} created successfully.')
            
            return redirect('crm:quote_detail', pk=quote.pk)
            
        except Exception as e:
            messages.error(request, f'Error creating quote: {str(e)}')
            return redirect('crm:quick_quote', lead_pk=lead.pk)
    
    def _move_to_proposal_stage(self, lead, user):
        """Move lead to Proposal stage in their pipeline."""
        if not lead.pipeline or not lead.current_stage:
            return
        
        # Find proposal stage
        proposal_stage = lead.pipeline.stages.filter(
            code__icontains='proposal'
        ).first()
        
        if proposal_stage and lead.current_stage != proposal_stage:
            from crm.services.pipeline import PipelineService
            PipelineService.move_to_stage(lead, proposal_stage, user, 'Quote sent')


class QuoteCreateView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    Create a quote for a lead - Template-first approach
    Step 1: Select a quote template
    Step 2: Select intake/qualification and payment option
    Step 3: Review and confirm
    """
    template_name = 'crm/quote_create.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead_pk = self.kwargs.get('lead_pk')
        
        if lead_pk:
            context['lead'] = get_object_or_404(Lead, pk=lead_pk)
            lead = context['lead']
            campus = getattr(lead, 'campus', None)
        else:
            lead = None
            campus = None
        
        # Available quote templates (for the campus or global)
        context['quote_templates'] = QuoteService.get_available_templates(campus)
        
        # Available payment options (global)
        context['payment_options'] = PaymentOption.objects.filter(is_active=True).order_by('sort_order')
        
        # Available qualifications
        context['qualifications'] = Qualification.objects.filter(
            is_active=True
        ).order_by('title')
        
        # Available intakes (upcoming ones)
        context['intakes'] = Intake.objects.filter(
            status__in=['PLANNED', 'RECRUITING', 'ENROLLMENT_OPEN'],
            start_date__gte=timezone.now().date()
        ).select_related('qualification', 'campus').order_by('start_date')[:50]
        
        # Enrollment years
        current_year = timezone.now().year
        context['enrollment_years'] = [
            {'value': 'CURRENT', 'label': f'Current Year ({current_year})'},
            {'value': 'NEXT', 'label': f'Next Year ({current_year + 1})'},
            {'value': 'PLUS_TWO', 'label': f'Year After Next ({current_year + 2})'},
        ]
        
        # Legacy payment plans (fallback if no payment options defined)
        context['payment_plans'] = [
            {'value': 'UPFRONT', 'label': 'Full Payment Upfront', 'icon': 'fas fa-money-bill'},
            {'value': 'TWO_INSTALLMENTS', 'label': 'Two Installments (50% each)', 'icon': 'fas fa-divide'},
            {'value': 'MONTHLY', 'label': 'Monthly Payments (10 months)', 'icon': 'fas fa-calendar-alt'},
        ]
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle quote creation"""
        lead_pk = self.kwargs.get('lead_pk')
        lead = get_object_or_404(Lead, pk=lead_pk)
        
        # Get form data
        template_id = request.POST.get('template')
        payment_option_id = request.POST.get('payment_option')
        intake_id = request.POST.get('intake')
        qualification_id = request.POST.get('qualification')
        enrollment_year = request.POST.get('enrollment_year', 'CURRENT')
        payment_plan = request.POST.get('payment_plan', 'UPFRONT')  # Legacy fallback
        notes = request.POST.get('notes', '')
        
        # Get objects
        template = None
        payment_option = None
        intake = None
        qualification = None
        
        if template_id:
            template = get_object_or_404(QuoteTemplate, pk=template_id)
        
        if payment_option_id:
            payment_option = get_object_or_404(PaymentOption, pk=payment_option_id)
        
        if intake_id:
            intake = get_object_or_404(Intake, pk=intake_id)
            qualification = intake.qualification
        elif qualification_id:
            qualification = get_object_or_404(Qualification, pk=qualification_id)
        
        if not qualification:
            messages.error(request, 'Please select an intake or qualification.')
            return redirect('crm:quote_create_for_lead', lead_pk=lead.pk)
        
        # Create the quote using service
        try:
            quote = QuoteService.create_quote_from_lead(
                lead=lead,
                qualification=qualification,
                intake=intake,
                enrollment_year=enrollment_year,
                payment_plan=payment_plan,
                created_by=request.user,
                campus=intake.campus if intake else (getattr(lead, 'campus', None)),
                template=template,
                payment_option=payment_option
            )
            
            # Add notes if provided
            if notes:
                quote.notes = notes
                quote.save(update_fields=['notes'])
            
            messages.success(request, f'Quote {quote.quote_number} created successfully.')
            return redirect('crm:quote_detail', pk=quote.pk)
            
        except Exception as e:
            messages.error(request, f'Error creating quote: {str(e)}')
            return redirect('crm:quote_create_for_lead', lead_pk=lead.pk)


class QuoteDetailView(LoginRequiredMixin, CRMAccessMixin, DetailView):
    """
    Internal quote detail view with actions
    """
    model = Quote
    template_name = 'crm/quote_detail.html'
    context_object_name = 'quote'
    
    def get_queryset(self):
        return Quote.objects.select_related(
            'lead', 'learner', 'intake', 'campus', 'campus__brand'
        ).prefetch_related('line_items', 'payment_schedule')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quote = self.object
        
        # Check if expired
        context['is_expired'] = quote.is_expired()
        
        # Payment schedule
        context['payment_schedule'] = quote.payment_schedule.order_by('installment_number')
        
        # Public URL for sharing
        context['public_url'] = self.request.build_absolute_uri(
            reverse('finance:quote_public_view', kwargs={'token': quote.public_token})
        )
        
        # WhatsApp URL
        if quote.lead and quote.lead.whatsapp_number:
            context['whatsapp_available'] = True
            context['whatsapp_number'] = quote.lead.whatsapp_number
        elif quote.lead and quote.lead.phone:
            context['whatsapp_available'] = True
            context['whatsapp_number'] = quote.lead.phone
        else:
            context['whatsapp_available'] = False
        
        return context


class QuoteListView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    List all quotes
    """
    template_name = 'crm/quote_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        quotes = Quote.objects.select_related(
            'lead', 'learner', 'intake', 'campus'
        ).order_by('-created_at')
        
        # Apply global campus filter
        selected_campus = get_selected_campus(self.request)
        if selected_campus:
            quotes = quotes.filter(campus=selected_campus)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            quotes = quotes.filter(status=status)
        
        # Filter by lead
        lead_pk = self.request.GET.get('lead')
        if lead_pk:
            quotes = quotes.filter(lead_id=lead_pk)
        
        context['quotes'] = quotes[:100]
        context['statuses'] = Quote.STATUS_CHOICES
        context['current_status'] = status
        
        return context


@login_required
def download_quote_pdf(request, pk):
    """
    Download quote as PDF
    """
    quote = get_object_or_404(Quote, pk=pk)
    
    try:
        pdf_bytes = QuoteService.generate_pdf(quote, request)
        
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{quote.quote_number}.pdf"'
        return response
        
    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('crm:quote_detail', pk=quote.pk)


@login_required
def send_quote_email(request, pk):
    """
    Send quote via email
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    quote = get_object_or_404(Quote, pk=pk)
    
    # Get recipient email
    email = None
    if quote.lead:
        email = quote.lead.email
    elif quote.learner:
        email = quote.learner.email
    
    if not email:
        return JsonResponse({'success': False, 'error': 'No email address available'})
    
    try:
        success = QuoteService.send_email(quote, email, request)
        
        if success:
            return JsonResponse({
                'success': True, 
                'message': f'Quote sent to {email}',
                'status': quote.status
            })
        else:
            return JsonResponse({'success': False, 'error': 'Failed to send email'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def send_quote_whatsapp(request, pk):
    """
    Send quote via WhatsApp (returns data for WhatsApp message)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    quote = get_object_or_404(Quote, pk=pk)
    
    # Get WhatsApp number
    phone = None
    if quote.lead:
        phone = quote.lead.whatsapp_number or quote.lead.phone
    
    if not phone:
        return JsonResponse({'success': False, 'error': 'No phone number available'})
    
    # Get send type from request
    data = json.loads(request.body) if request.body else {}
    send_type = data.get('type', 'link')  # 'link' or 'pdf'
    
    try:
        if send_type == 'pdf':
            # Save PDF to media and get path
            pdf_path = QuoteService.save_pdf_to_media(quote, request)
            pdf_url = request.build_absolute_uri(pdf_path)
            
            success = QuoteService.send_whatsapp_pdf(quote, phone, pdf_url)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': f'Quote PDF sent to WhatsApp',
                    'pdf_url': pdf_url
                })
        else:
            # Send link only
            public_url = request.build_absolute_uri(
                reverse('finance:quote_public_view', kwargs={'token': quote.public_token})
            )
            
            success = QuoteService.send_whatsapp_link(quote, phone, public_url)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': f'Quote link sent to WhatsApp',
                    'public_url': public_url
                })
        
        return JsonResponse({'success': False, 'error': 'Failed to send WhatsApp message'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


class QuotePublicView(View):
    """
    Public view for quote acceptance (accessed via UUID token)
    No login required
    """
    template_name = 'finance/quote_public.html'
    
    def get(self, request, token):
        # Get quote by public token
        quote = get_object_or_404(Quote, public_token=token)
        
        # Check if expired
        if quote.is_expired() and quote.status not in ['ACCEPTED', 'CONVERTED']:
            if quote.status not in ['EXPIRED']:
                quote.status = 'EXPIRED'
                quote.save(update_fields=['status'])
            
            return render(request, 'finance/quote_expired.html', {
                'quote': quote
            })
        
        # Mark as viewed
        quote.mark_as_viewed()
        
        # Get payment schedule
        payment_schedule = quote.payment_schedules.order_by('installment_number')
        
        # Get client info
        client_name = ""
        if quote.lead:
            client_name = f"{quote.lead.first_name} {quote.lead.last_name}"
        elif quote.learner:
            client_name = f"{quote.learner.first_name} {quote.learner.surname}"
        
        # Brand info for branding
        brand = None
        if quote.campus and quote.campus.brand:
            brand = quote.campus.brand
        
        context = {
            'quote': quote,
            'client_name': client_name,
            'payment_schedule': payment_schedule,
            'brand': brand,
            'can_accept': quote.status in ['SENT', 'VIEWED'],
            'is_accepted': quote.status == 'ACCEPTED',
            'is_rejected': quote.status == 'REJECTED',
        }
        
        return render(request, self.template_name, context)


@login_required
def accept_quote_public(request, token):
    """
    Accept a quote (public endpoint)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    quote = get_object_or_404(Quote, public_token=token)
    
    # Check if can still accept
    if quote.is_expired():
        return JsonResponse({'success': False, 'error': 'Quote has expired'})
    
    if quote.status not in ['SENT', 'VIEWED']:
        return JsonResponse({'success': False, 'error': f'Quote cannot be accepted (status: {quote.status})'})
    
    # Accept the quote
    quote.accept()
    
    return JsonResponse({
        'success': True,
        'message': 'Quote accepted successfully',
        'status': quote.status
    })


def reject_quote_public(request, token):
    """
    Reject a quote (public endpoint)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    quote = get_object_or_404(Quote, public_token=token)
    
    # Check if can still reject
    if quote.status not in ['SENT', 'VIEWED']:
        return JsonResponse({'success': False, 'error': f'Quote cannot be rejected (status: {quote.status})'})
    
    # Reject the quote
    quote.reject()
    
    return JsonResponse({
        'success': True,
        'message': 'Quote rejected',
        'status': quote.status
    })


@login_required
def get_intake_details(request):
    """
    AJAX endpoint to get intake details for quote creation
    """
    intake_id = request.GET.get('intake_id')
    if not intake_id:
        return JsonResponse({'success': False, 'error': 'intake_id required'})
    
    try:
        intake = Intake.objects.select_related('qualification', 'campus').get(pk=intake_id)
        
        pricing = QuoteService.get_pricing_from_intake(intake)
        
        return JsonResponse({
            'success': True,
            'intake': {
                'id': str(intake.pk),
                'code': intake.code,
                'name': intake.name,
                'qualification': intake.qualification.title if intake.qualification else '',
                'campus': intake.campus.name if intake.campus else '',
                'start_date': intake.start_date.isoformat() if intake.start_date else '',
            },
            'pricing': {
                'total_price': float(pricing['total_price']),
                'registration_fee': float(pricing['registration_fee']),
                'tuition_fee': float(pricing['tuition_fee']),
                'materials_fee': float(pricing['materials_fee']),
            }
        })
        
    except Intake.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Intake not found'})


@login_required
def get_template_payment_options(request):
    """
    AJAX endpoint to get payment options for a quote template
    """
    template_id = request.GET.get('template_id')
    
    try:
        if template_id:
            template = QuoteTemplate.objects.get(pk=template_id)
            payment_options = template.get_effective_payment_options()
            validity_hours = template.get_effective_validity_hours()
            terms = template.get_effective_terms()
            header = template.get_effective_header()
            footer = template.get_effective_footer()
        else:
            payment_options = PaymentOption.objects.filter(is_active=True).order_by('sort_order')
            validity_hours = 48
            terms = ""
            header = ""
            footer = ""
        
        options_list = [{
            'id': str(opt.pk),
            'name': opt.name,
            'code': opt.code,
            'description': opt.description,
            'installments': opt.installments,
            'deposit_percent': float(opt.deposit_percent),
            'monthly_term': opt.monthly_term,
        } for opt in payment_options]
        
        return JsonResponse({
            'success': True,
            'payment_options': options_list,
            'validity_hours': validity_hours,
            'terms': terms,
            'header': header,
            'footer': footer,
        })
        
    except QuoteTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Template not found'})


@login_required
def get_qualification_pricing(request):
    """
    AJAX endpoint to get qualification pricing for a specific year
    """
    qualification_id = request.GET.get('qualification_id')
    enrollment_year = request.GET.get('enrollment_year', 'CURRENT')
    
    if not qualification_id:
        return JsonResponse({'success': False, 'error': 'qualification_id required'})
    
    try:
        qualification = Qualification.objects.get(pk=qualification_id)
        
        # Calculate academic year
        current_year = timezone.now().year
        if enrollment_year == 'NEXT':
            academic_year = current_year + 1
        elif enrollment_year == 'PLUS_TWO':
            academic_year = current_year + 2
        else:
            academic_year = current_year
        
        pricing = QuoteService.get_pricing_for_qualification(qualification, academic_year)
        
        return JsonResponse({
            'success': True,
            'qualification': {
                'id': str(qualification.pk),
                'title': qualification.title,
                'code': qualification.saqa_id or '',
            },
            'academic_year': academic_year,
            'pricing': {
                'total_price': float(pricing['total_price']),
                'registration_fee': float(pricing['registration_fee']),
                'tuition_fee': float(pricing['tuition_fee']),
                'materials_fee': float(pricing['materials_fee']),
                'source': pricing['source']
            }
        })
        
    except Qualification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Qualification not found'})


@login_required
def quick_quote_data(request, lead_pk):
    """
    AJAX endpoint to get all data needed for the Quick Quote modal.
    Returns lead info, qualifications, pricing, and payment options.
    """
    from finance.models import PaymentOption
    
    lead = get_object_or_404(Lead, pk=lead_pk)
    current_year = timezone.now().year
    
    # Get qualification from lead's interest or None
    qualification = lead.qualification_interest
    pricing = None
    pricing_warning = None
    
    if qualification:
        pricing = QuoteService.get_pricing_for_qualification(qualification, current_year)
        if pricing['source'] == 'default' or pricing['total_price'] == 0:
            pricing_warning = "No pricing configured for this qualification. Quote will be created with R0.00."
    
    # Get all active qualifications for dropdown
    qualifications = Qualification.objects.filter(is_active=True).order_by('title')
    qualifications_list = [{
        'id': q.pk,
        'title': q.title,
        'short_title': q.short_title or q.title[:50],
        'saqa_id': q.saqa_id or ''
    } for q in qualifications]
    
    # Get payment options
    payment_options = PaymentOption.objects.filter(is_active=True).order_by('sort_order')
    payment_options_list = [{
        'id': po.pk,
        'name': po.name,
        'description': po.description or '',
        'installments': po.installments,
        'monthly_term': po.monthly_term,
        'deposit_percent': float(po.deposit_percent) if po.deposit_percent else 0,
    } for po in payment_options]
    
    # Determine best contact method
    has_whatsapp = bool(lead.whatsapp_number or lead.phone)
    has_email = bool(lead.email)
    
    response_data = {
        'success': True,
        'lead': {
            'id': lead.pk,
            'full_name': lead.get_full_name(),
            'first_name': lead.first_name,
            'last_name': lead.last_name,
            'email': lead.email or '',
            'phone': lead.phone or '',
            'whatsapp': lead.whatsapp_number or lead.phone or '',
            'has_whatsapp': has_whatsapp,
            'has_email': has_email,
        },
        'qualification': {
            'id': qualification.pk if qualification else None,
            'title': qualification.title if qualification else None,
            'short_title': qualification.short_title if qualification else None,
        } if qualification else None,
        'pricing': {
            'total_price': float(pricing['total_price']) if pricing else 0,
            'registration_fee': float(pricing['registration_fee']) if pricing else 0,
            'tuition_fee': float(pricing['tuition_fee']) if pricing else 0,
            'materials_fee': float(pricing['materials_fee']) if pricing else 0,
            'source': pricing['source'] if pricing else 'none',
        } if pricing else None,
        'pricing_warning': pricing_warning,
        'qualifications': qualifications_list,
        'payment_options': payment_options_list,
        'academic_year': current_year,
    }
    
    return JsonResponse(response_data)


@login_required
def quick_quote_create(request, lead_pk):
    """
    AJAX endpoint to create a quote and optionally send it.
    Supports multiple send channels (WhatsApp + Email).
    Returns the created quote details for preview.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    from finance.models import PaymentOption
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    lead = get_object_or_404(Lead, pk=lead_pk)
    
    # Get qualification - from lead or from request
    qualification_id = data.get('qualification_id')
    if qualification_id:
        qualification = get_object_or_404(Qualification, pk=qualification_id)
        # Update lead's qualification interest
        lead.qualification_interest = qualification
        lead.save(update_fields=['qualification_interest'])
    else:
        qualification = lead.qualification_interest
    
    if not qualification:
        return JsonResponse({
            'success': False, 
            'error': 'No qualification selected. Please select a qualification first.'
        }, status=400)
    
    # Get payment option
    payment_option_id = data.get('payment_option_id')
    payment_option = None
    if payment_option_id:
        payment_option = get_object_or_404(PaymentOption, pk=payment_option_id)
    
    enrollment_year = data.get('enrollment_year', 'CURRENT')
    notes = data.get('notes', '')
    send_whatsapp = data.get('send_whatsapp', False)
    send_email = data.get('send_email', False)
    
    try:
        # Create the quote
        quote = QuoteService.create_quote_from_lead(
            lead=lead,
            qualification=qualification,
            intake=None,
            enrollment_year=enrollment_year,
            payment_plan='UPFRONT',
            created_by=request.user,
            campus=lead.campus,
            template=None,
            payment_option=payment_option
        )
        
        if notes:
            quote.notes = notes
            quote.save(update_fields=['notes'])
        
        # Log activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type='QUOTE_SENT',
            description=f'Quote {quote.quote_number} created for {qualification.title}',
            created_by=request.user
        )
        
        # Generate public URL for the quote
        public_url = request.build_absolute_uri(
            reverse('finance:quote_public_view', kwargs={'token': quote.public_token})
        )
        
        # PDF download URL
        pdf_url = request.build_absolute_uri(
            reverse('crm:download_quote_pdf', kwargs={'pk': quote.pk})
        )
        
        send_results = []
        
        # Send via channels
        if send_whatsapp:
            phone = lead.whatsapp_number or lead.phone
            if phone:
                try:
                    QuoteService.send_whatsapp_link(quote, phone, public_url)
                    send_results.append('WhatsApp')
                except Exception as e:
                    send_results.append(f'WhatsApp failed: {str(e)}')
        
        if send_email and lead.email:
            try:
                QuoteService.send_email(quote, lead.email, request)
                send_results.append('Email')
            except Exception as e:
                send_results.append(f'Email failed: {str(e)}')
        
        # Move lead to Proposal stage if sent
        if send_whatsapp or send_email:
            if lead.pipeline and lead.current_stage:
                proposal_stage = lead.pipeline.stages.filter(
                    code__icontains='proposal'
                ).first()
                if proposal_stage and lead.current_stage != proposal_stage:
                    from crm.services.pipeline import PipelineService
                    PipelineService.move_to_stage(lead, proposal_stage, request.user, 'Quote sent')
        
        # Build response
        response_data = {
            'success': True,
            'quote': {
                'id': quote.pk,
                'quote_number': quote.quote_number,
                'total_amount': float(quote.total_amount),
                'valid_until': quote.valid_until.strftime('%d %B %Y') if quote.valid_until else None,
                'public_url': public_url,
                'pdf_url': pdf_url,
                'detail_url': reverse('crm:quote_detail', kwargs={'pk': quote.pk}),
            },
            'qualification': {
                'title': qualification.title,
                'short_title': qualification.short_title,
            },
            'send_results': send_results,
            'message': f'Quote {quote.quote_number} created successfully!' + (
                f' Sent via: {", ".join(send_results)}' if send_results else ''
            )
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error creating quote: {str(e)}'
        }, status=500)
