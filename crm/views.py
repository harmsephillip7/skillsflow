"""
CRM Views
Sales leads, pipeline management, WhatsApp integration
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Q, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.urls import reverse_lazy
from datetime import timedelta, date
from .models import Lead, LeadSource, LeadActivity
from core.context_processors import get_selected_campus
from core.mixins import CampusFilterMixin


class CRMAccessMixin(UserPassesTestMixin):
    """Check if user has CRM access"""
    def test_func(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return True
        # Check for CRM-related roles
        if hasattr(user, 'profile') and user.profile:
            role = user.profile.role
            return role in ['ADMIN', 'SALES_MANAGER', 'SALES_REP', 'MARKETING_MANAGER', 'CAMPUS_MANAGER']
        return False


class CRMDashboardView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    CRM Dashboard with pipeline overview and KPIs
    """
    template_name = 'crm/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        start_of_year = today.replace(month=1, day=1)
        
        # Base queryset - apply global campus filter
        leads = Lead.objects.all()
        selected_campus = get_selected_campus(self.request)
        if selected_campus:
            leads = leads.filter(campus=selected_campus)
        
        # Pipeline Stats
        context['pipeline_stats'] = {
            'new': leads.filter(status='NEW').count(),
            'contacted': leads.filter(status='CONTACTED').count(),
            'qualified': leads.filter(status='QUALIFIED').count(),
            'proposal': leads.filter(status='PROPOSAL').count(),
            'negotiation': leads.filter(status='NEGOTIATION').count(),
            'registered': leads.filter(status='REGISTERED').count(),
            'enrolled': leads.filter(status='ENROLLED').count(),
            'lost': leads.filter(status='LOST').count(),
        }
        
        # Total leads
        context['total_leads'] = leads.count()
        context['active_leads'] = leads.exclude(status__in=['ENROLLED', 'LOST', 'ALUMNI']).count()
        
        # This month stats
        context['new_this_month'] = leads.filter(created_at__date__gte=start_of_month).count()
        context['converted_this_month'] = leads.filter(
            status='ENROLLED',
            converted_at__date__gte=start_of_month
        ).count()
        
        # Conversion rate
        total_with_outcome = leads.filter(status__in=['ENROLLED', 'LOST']).count()
        enrolled = leads.filter(status='ENROLLED').count()
        context['conversion_rate'] = round((enrolled / total_with_outcome * 100) if total_with_outcome > 0 else 0, 1)
        
        # School Leaver Stats
        school_leavers = leads.filter(lead_type='SCHOOL_LEAVER')
        context['school_leaver_stats'] = {
            'total': school_leavers.count(),
            'under_18': sum(1 for l in school_leavers if l.is_minor),
            'ready_to_enroll': sum(1 for l in school_leavers if l.is_enrollment_ready),
            'with_consent': school_leavers.filter(consent_bulk_messaging=True).count(),
        }
        
        # Leads by Source
        context['leads_by_source'] = leads.values(
            'source__name'
        ).annotate(count=Count('id')).order_by('-count')[:10]
        
        # Leads by Type
        context['leads_by_type'] = leads.values(
            'lead_type'
        ).annotate(count=Count('id')).order_by('-count')
        
        # Follow-ups Due
        context['follow_ups_due_today'] = leads.filter(
            next_follow_up__date=today,
            status__in=['NEW', 'CONTACTED', 'QUALIFIED', 'PROPOSAL', 'NEGOTIATION']
        ).count()
        context['follow_ups_overdue'] = leads.filter(
            next_follow_up__date__lt=today,
            status__in=['NEW', 'CONTACTED', 'QUALIFIED', 'PROPOSAL', 'NEGOTIATION']
        ).count()
        
        # My Leads (for sales reps)
        if not user.is_superuser:
            my_leads = leads.filter(assigned_to=user)
            context['my_leads_count'] = my_leads.count()
            context['my_follow_ups_today'] = my_leads.filter(
                next_follow_up__date=today
            ).count()
            context['my_leads'] = my_leads.exclude(
                status__in=['ENROLLED', 'LOST', 'ALUMNI']
            ).order_by('next_follow_up')[:10]
        
        # Recent Activities
        context['recent_activities'] = LeadActivity.objects.select_related(
            'lead', 'created_by'
        ).order_by('-created_at')[:15]
        
        # Age progression - school leavers turning 18 soon
        three_months_from_now = today + timedelta(days=90)
        context['turning_18_soon'] = [
            l for l in school_leavers.filter(date_of_birth__isnull=False)
            if l.age == 17 and l.date_of_birth.replace(year=today.year) <= three_months_from_now
        ][:10]
        
        return context


class LeadListView(LoginRequiredMixin, CRMAccessMixin, CampusFilterMixin, ListView):
    """
    List all leads with filtering and search
    """
    model = Lead
    template_name = 'crm/lead_list.html'
    context_object_name = 'leads'
    paginate_by = 25
    campus_field = 'campus'
    
    def get_queryset(self):
        queryset = Lead.objects.select_related(
            'source', 'assigned_to', 'campus', 'campus__brand', 'qualification_interest'
        ).order_by('-created_at')
        
        # Apply global campus filter
        selected_campus = get_selected_campus(self.request)
        if selected_campus:
            queryset = queryset.filter(campus=selected_campus)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(school_name__icontains=search)
            )
        
        # Filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        lead_type = self.request.GET.get('lead_type')
        if lead_type:
            queryset = queryset.filter(lead_type=lead_type)
        
        source = self.request.GET.get('source')
        if source:
            queryset = queryset.filter(source_id=source)
        
        assigned = self.request.GET.get('assigned')
        if assigned == 'me':
            queryset = queryset.filter(assigned_to=user)
        elif assigned == 'unassigned':
            queryset = queryset.filter(assigned_to__isnull=True)
        elif assigned:
            queryset = queryset.filter(assigned_to_id=assigned)
        
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Special filters
        filter_type = self.request.GET.get('filter')
        if filter_type == 'follow_up_today':
            queryset = queryset.filter(next_follow_up__date=timezone.now().date())
        elif filter_type == 'follow_up_overdue':
            queryset = queryset.filter(next_follow_up__date__lt=timezone.now().date())
        elif filter_type == 'school_leavers':
            queryset = queryset.filter(lead_type='SCHOOL_LEAVER')
        elif filter_type == 'minors':
            # Filter school leavers with DOB indicating under 18
            eighteen_years_ago = timezone.now().date() - timedelta(days=18*365)
            queryset = queryset.filter(
                lead_type='SCHOOL_LEAVER',
                date_of_birth__gt=eighteen_years_ago
            )
        elif filter_type == 'consent':
            queryset = queryset.filter(consent_bulk_messaging=True, unsubscribed=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = Lead.STATUS_CHOICES
        context['lead_types'] = Lead.LEAD_TYPE_CHOICES
        context['priorities'] = Lead.PRIORITY_CHOICES
        context['sources'] = LeadSource.objects.filter(is_active=True)
        context['current_filters'] = {
            'search': self.request.GET.get('search', ''),
            'status': self.request.GET.get('status', ''),
            'lead_type': self.request.GET.get('lead_type', ''),
            'source': self.request.GET.get('source', ''),
            'assigned': self.request.GET.get('assigned', ''),
            'priority': self.request.GET.get('priority', ''),
            'filter': self.request.GET.get('filter', ''),
        }
        return context


class LeadDetailView(LoginRequiredMixin, CRMAccessMixin, DetailView):
    """
    Lead detail with activity timeline
    """
    model = Lead
    template_name = 'crm/lead_detail.html'
    context_object_name = 'lead'
    
    def get_queryset(self):
        return Lead.objects.select_related(
            'source', 'assigned_to', 'campus', 'campus__brand', 
            'qualification_interest', 'converted_learner'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead = self.object
        
        # Activities
        context['activities'] = lead.activities.select_related(
            'created_by'
        ).order_by('-created_at')[:50]
        
        # Age info for school leavers
        if lead.lead_type == 'SCHOOL_LEAVER' and lead.date_of_birth:
            context['age'] = lead.age
            context['is_minor'] = lead.is_minor
            context['is_enrollment_ready'] = lead.is_enrollment_ready
            
            # Calculate when they turn 18
            if lead.is_minor:
                eighteenth_birthday = lead.date_of_birth.replace(
                    year=lead.date_of_birth.year + 18
                )
                context['turns_18'] = eighteenth_birthday
                context['days_until_18'] = (eighteenth_birthday - date.today()).days
        
        # Available statuses for quick update
        context['statuses'] = Lead.STATUS_CHOICES
        context['priorities'] = Lead.PRIORITY_CHOICES
        
        # Document upload requests
        context['document_requests'] = lead.document_requests.order_by('-created_at')[:10]
        
        # Uploaded documents
        context['lead_documents'] = lead.documents.order_by('-created_at')
        
        # Document types for request modal
        from .models import LeadDocument
        context['document_types'] = LeadDocument.DOCUMENT_TYPES
        
        # Pipeline Memberships
        context['pipeline_memberships'] = lead.pipeline_memberships.select_related(
            'pipeline', 'current_stage'
        ).order_by('-joined_at')
        
        # Available pipelines (not already enrolled)
        enrolled_pipeline_ids = lead.pipeline_memberships.values_list('pipeline_id', flat=True)
        context['available_pipelines'] = Pipeline.objects.filter(
            is_active=True
        ).exclude(id__in=enrolled_pipeline_ids)
        
        # Active applications (non-archived)
        context['active_applications'] = Application.objects.filter(
            opportunity__lead=lead,
            is_archived=False
        ).exclude(
            status__in=['ENROLLED', 'REJECTED', 'WITHDRAWN']
        ).select_related('opportunity', 'intake').order_by('-created_at')
        
        # Qualifications and intakes for application creation
        from academics.models import Qualification
        from intakes.models import Intake
        context['qualifications'] = Qualification.objects.filter(is_active=True).order_by('name')
        context['intakes'] = Intake.objects.filter(
            is_open_for_applications=True,
            start_date__gte=date.today()
        ).order_by('start_date')[:20]
        
        return context


class LeadCreateView(LoginRequiredMixin, CRMAccessMixin, CreateView):
    """
    Create a new lead
    """
    model = Lead
    template_name = 'crm/lead_form.html'
    fields = [
        'first_name', 'last_name', 'email', 'phone', 'phone_secondary',
        'whatsapp_number', 'prefers_whatsapp',
        'date_of_birth', 'lead_type',
        'parent_name', 'parent_phone', 'parent_email', 'parent_relationship',
        'school_name', 'grade', 'expected_matric_year',
        'source', 'qualification_interest',
        'highest_qualification', 'employment_status', 'employer_name',
        'priority', 'notes',
        'consent_bulk_messaging',
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Lead'
        context['sources'] = LeadSource.objects.filter(is_active=True)
        return context
    
    def form_valid(self, form):
        lead = form.save(commit=False)
        user = self.request.user
        
        # Set brand/campus from user profile if available
        if hasattr(user, 'profile') and user.profile:
            if user.profile.brand:
                lead.brand = user.profile.brand
            if user.profile.campus:
                lead.campus = user.profile.campus
        
        # Auto-assign to creator if they're a sales rep
        if not lead.assigned_to:
            lead.assigned_to = user
        
        # Set consent date if consent given
        if lead.consent_bulk_messaging:
            lead.consent_date = timezone.now()
        
        lead.save()
        
        # Log activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type='STATUS_CHANGE',
            description=f'Lead created with status: {lead.get_status_display()}',
            created_by=user,
            brand=lead.brand,
            campus=lead.campus
        )
        
        messages.success(self.request, f'Lead "{lead.get_full_name()}" created successfully.')
        return redirect('crm:lead_detail', pk=lead.pk)


class LeadUpdateView(LoginRequiredMixin, CRMAccessMixin, UpdateView):
    """
    Update an existing lead
    """
    model = Lead
    template_name = 'crm/lead_form.html'
    fields = [
        'first_name', 'last_name', 'email', 'phone', 'phone_secondary',
        'whatsapp_number', 'prefers_whatsapp',
        'date_of_birth', 'lead_type',
        'parent_name', 'parent_phone', 'parent_email', 'parent_relationship',
        'school_name', 'grade', 'expected_matric_year',
        'source', 'qualification_interest',
        'highest_qualification', 'employment_status', 'employer_name',
        'status', 'priority', 'notes',
        'assigned_to', 'next_follow_up', 'follow_up_notes',
        'consent_bulk_messaging',
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Lead: {self.object.get_full_name()}'
        context['sources'] = LeadSource.objects.filter(is_active=True)
        return context
    
    def form_valid(self, form):
        lead = form.save(commit=False)
        user = self.request.user
        
        # Track consent changes
        if 'consent_bulk_messaging' in form.changed_data:
            if lead.consent_bulk_messaging:
                lead.consent_date = timezone.now()
            else:
                lead.unsubscribed = True
                lead.unsubscribed_date = timezone.now()
        
        lead.save()
        
        # Log changes
        changed_fields = form.changed_data
        if changed_fields:
            if 'status' in changed_fields:
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type='STATUS_CHANGE',
                    description=f'Status changed to: {lead.get_status_display()}',
                    created_by=user,
                    brand=lead.brand,
                    campus=lead.campus
                )
            else:
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type='NOTE',
                    description=f'Lead updated. Changed: {", ".join(changed_fields)}',
                    created_by=user,
                    brand=lead.brand,
                    campus=lead.campus
                )
        
        messages.success(self.request, f'Lead "{lead.get_full_name()}" updated successfully.')
        return redirect('crm:lead_detail', pk=lead.pk)


@login_required
def lead_quick_status(request, pk):
    """AJAX endpoint to quickly update lead status"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    lead = get_object_or_404(Lead, pk=pk)
    new_status = request.POST.get('status')
    
    if new_status not in dict(Lead.STATUS_CHOICES):
        return JsonResponse({'error': 'Invalid status'}, status=400)
    
    old_status = lead.status
    lead.status = new_status
    lead.save()
    
    # Log activity
    LeadActivity.objects.create(
        lead=lead,
        activity_type='STATUS_CHANGE',
        description=f'Status changed from {old_status} to {new_status}',
        created_by=request.user,
        brand=lead.brand,
        campus=lead.campus
    )
    
    return JsonResponse({
        'success': True,
        'new_status': new_status,
        'status_display': lead.get_status_display()
    })


@login_required
def lead_add_activity(request, pk):
    """Add an activity/note to a lead"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    lead = get_object_or_404(Lead, pk=pk)
    activity_type = request.POST.get('activity_type', 'NOTE')
    description = request.POST.get('description', '')
    
    if not description:
        return JsonResponse({'error': 'Description required'}, status=400)
    
    activity = LeadActivity.objects.create(
        lead=lead,
        activity_type=activity_type,
        description=description,
        created_by=request.user,
        brand=lead.brand,
        campus=lead.campus
    )
    
    return JsonResponse({
        'success': True,
        'activity_id': activity.pk,
        'activity_type': activity.get_activity_type_display(),
        'description': activity.description,
        'created_at': activity.created_at.strftime('%Y-%m-%d %H:%M'),
        'performed_by': request.user.get_full_name() or request.user.username
    })


@login_required
def lead_save_profile(request, pk):
    """Save learner profile section data for a lead"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    lead = get_object_or_404(Lead, pk=pk)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    section = data.get('section')
    
    if not section:
        return JsonResponse({'error': 'Section required'}, status=400)
    
    # Import Address model for address sections
    from learners.models import Address
    
    try:
        if section == 'personal':
            # Personal information fields
            if data.get('title'):
                lead.title = data['title']
            if data.get('id_number'):
                lead.id_number = data['id_number']
                # Validate and extract date of birth & gender from ID
                validation = lead.validate_and_extract_id_number()
                if validation['valid']:
                    lead.date_of_birth = validation['date_of_birth']
                    lead.gender = validation['gender']
            if data.get('gender'):
                lead.gender = data['gender']
            if data.get('date_of_birth'):
                from datetime import datetime
                lead.date_of_birth = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
            if data.get('race'):
                lead.race = data['race']
            if data.get('marital_status'):
                lead.marital_status = data['marital_status']
            if data.get('number_of_dependents'):
                lead.number_of_dependents = int(data['number_of_dependents'])
            
        elif section == 'languages':
            # Language fields
            if data.get('first_language'):
                lead.first_language = data['first_language']
            if data.get('second_language'):
                lead.second_language = data['second_language']
            if data.get('english_speaking'):
                lead.english_speaking = data['english_speaking']
            if data.get('english_reading'):
                lead.english_reading = data['english_reading']
            if data.get('english_writing'):
                lead.english_writing = data['english_writing']
            
        elif section == 'education':
            # Education fields
            if data.get('highest_grade_passed'):
                lead.highest_grade_passed = data['highest_grade_passed']
            lead.last_school_attended = data.get('last_school_attended', '')
            lead.tertiary_qualification = data.get('tertiary_qualification', '')
            lead.subjects_completed = data.get('subjects_completed', '')
            
        elif section == 'work':
            # Work experience fields
            if data.get('work_status'):
                lead.work_status = data['work_status']
            if data.get('years_experience'):
                lead.years_experience = int(data['years_experience'])
            
        elif section == 'health':
            # Health fields
            lead.has_disability = data.get('has_disability', False)
            if lead.has_disability:
                lead.disability_description = data.get('disability_description', '')
            else:
                lead.disability_description = ''
            lead.has_medical_conditions = data.get('has_medical_conditions', False)
            if lead.has_medical_conditions:
                lead.medical_conditions = data.get('medical_conditions', '')
            else:
                lead.medical_conditions = ''
            
        elif section == 'payment':
            # Payment responsibility
            if data.get('payment_responsibility'):
                lead.payment_responsibility = data['payment_responsibility']
            
        elif section == 'physical_address':
            # Physical address - create or update
            address_data = {
                'line_1': data.get('physical_line_1', ''),
                'line_2': data.get('physical_line_2', ''),
                'suburb': data.get('physical_suburb', ''),
                'city': data.get('physical_city', ''),
                'province': data.get('physical_province', ''),
                'postal_code': data.get('physical_postal_code', ''),
                'country': 'South Africa'
            }
            
            if lead.physical_address:
                # Update existing address
                for key, value in address_data.items():
                    setattr(lead.physical_address, key, value)
                lead.physical_address.save()
            else:
                # Create new address
                address = Address.objects.create(**address_data)
                lead.physical_address = address
            
        elif section == 'postal_address':
            # Postal address
            lead.postal_same_as_physical = data.get('postal_same_as_physical', False)
            
            if not lead.postal_same_as_physical:
                address_data = {
                    'line_1': data.get('postal_line_1', ''),
                    'line_2': data.get('postal_line_2', ''),
                    'suburb': data.get('postal_suburb', ''),
                    'city': data.get('postal_city', ''),
                    'province': data.get('postal_province', ''),
                    'postal_code': data.get('postal_postal_code', ''),
                    'country': 'South Africa'
                }
                
                if lead.postal_address:
                    # Update existing address
                    for key, value in address_data.items():
                        setattr(lead.postal_address, key, value)
                    lead.postal_address.save()
                else:
                    # Create new address
                    address = Address.objects.create(**address_data)
                    lead.postal_address = address
        
        lead.save()
        
        # Log activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type='NOTE',
            description=f'Updated learner profile: {section.replace("_", " ").title()} section',
            created_by=request.user,
            brand=lead.brand,
            campus=lead.campus
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{section.replace("_", " ").title()} saved successfully',
            'profile_completion': lead.profile_completion_status
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def validate_id_number_api(request):
    """API endpoint to validate SA ID number and extract DOB/gender"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    id_number = data.get('id_number', '')
    
    if len(id_number) != 13 or not id_number.isdigit():
        return JsonResponse({
            'valid': False,
            'error': 'ID number must be exactly 13 digits'
        })
    
    # Import validation function from learners
    from learners.models import validate_sa_id_number
    
    if not validate_sa_id_number(id_number):
        return JsonResponse({
            'valid': False,
            'error': 'Invalid ID number (checksum failed)'
        })
    
    # Extract date of birth
    year_part = int(id_number[0:2])
    month = int(id_number[2:4])
    day = int(id_number[4:6])
    
    # Determine century (assume 1900s for year > 25, else 2000s)
    current_year = timezone.now().year % 100
    if year_part > current_year:
        year = 1900 + year_part
    else:
        year = 2000 + year_part
    
    # Validate date
    try:
        from datetime import date as date_type
        dob = date_type(year, month, day)
    except ValueError:
        return JsonResponse({
            'valid': False,
            'error': 'Invalid date in ID number'
        })
    
    # Extract gender (digit 7: 0-4 = female, 5-9 = male)
    gender_digit = int(id_number[6])
    gender = 'MALE' if gender_digit >= 5 else 'FEMALE'
    
    return JsonResponse({
        'valid': True,
        'date_of_birth': dob.strftime('%Y-%m-%d'),
        'gender': gender
    })


@login_required
def lead_upload_document(request, pk):
    """Staff endpoint to upload documents for a lead"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    lead = get_object_or_404(Lead, pk=pk)
    
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    file = request.FILES['file']
    document_type = request.POST.get('document_type', 'OTHER')
    title = request.POST.get('title', '')
    description = request.POST.get('description', '')
    
    from .models import LeadDocument, LeadActivity
    
    # Create the document
    doc = LeadDocument.objects.create(
        lead=lead,
        document_type=document_type,
        title=title or file.name,
        description=description,
        file=file,
        original_filename=file.name,
        file_size=file.size,
        content_type=file.content_type or 'application/octet-stream',
        status='VERIFIED',  # Staff uploads are auto-verified
        verified_by=request.user,
        verified_at=timezone.now(),
        created_by=request.user,
        brand=lead.brand,
        campus=lead.campus
    )
    
    # Log activity
    LeadActivity.objects.create(
        lead=lead,
        activity_type='NOTE',
        description=f'Document uploaded: {doc.get_document_type_display()} - {doc.title}',
        created_by=request.user,
        brand=lead.brand,
        campus=lead.campus
    )
    
    return JsonResponse({
        'success': True,
        'document_id': str(doc.id),
        'document_type': doc.get_document_type_display(),
        'title': doc.title,
        'file_size': doc.file_size,
        'file_url': doc.file.url
    })


@login_required
def lead_delete_document(request, pk, doc_id):
    """Delete a document from a lead"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    lead = get_object_or_404(Lead, pk=pk)
    
    from .models import LeadDocument, LeadActivity
    import uuid
    
    try:
        doc_uuid = uuid.UUID(doc_id)
        doc = get_object_or_404(LeadDocument, id=doc_uuid, lead=lead)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid document ID'}, status=400)
    
    doc_title = doc.title
    doc_type = doc.get_document_type_display()
    doc.delete()
    
    # Log activity
    LeadActivity.objects.create(
        lead=lead,
        activity_type='NOTE',
        description=f'Document deleted: {doc_type} - {doc_title}',
        created_by=request.user,
        brand=lead.brand,
        campus=lead.campus
    )
    
    return JsonResponse({
        'success': True,
        'message': f'Document "{doc_title}" deleted'
    })


@login_required
def lead_add_to_pipeline(request, pk):
    """Add lead to a pipeline"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    lead = get_object_or_404(Lead, pk=pk)
    
    import json
    try:
        data = json.loads(request.body)
        pipeline_id = data.get('pipeline_id')
    except json.JSONDecodeError:
        pipeline_id = request.POST.get('pipeline_id')
    
    if not pipeline_id:
        return JsonResponse({'error': 'Pipeline ID required'}, status=400)
    
    pipeline = get_object_or_404(Pipeline, pk=pipeline_id)
    
    membership = lead.add_to_pipeline(pipeline, user=request.user)
    
    return JsonResponse({
        'success': True,
        'membership_id': membership.id,
        'pipeline_name': pipeline.name,
        'message': f'Lead added to pipeline "{pipeline.name}"'
    })


@login_required
def lead_pipeline_membership_action(request, pk, membership_id, action):
    """Pause, resume, or remove a pipeline membership"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    lead = get_object_or_404(Lead, pk=pk)
    
    from .models import LeadPipelineMembership
    membership = get_object_or_404(LeadPipelineMembership, pk=membership_id, lead=lead)
    
    if action == 'pause':
        membership.pause()
        return JsonResponse({'success': True, 'message': 'Pipeline membership paused'})
    elif action == 'resume':
        membership.resume()
        return JsonResponse({'success': True, 'message': 'Pipeline membership resumed'})
    elif action == 'remove':
        pipeline_name = membership.pipeline.name
        membership.exit(request.user)
        return JsonResponse({'success': True, 'message': f'Removed from pipeline "{pipeline_name}"'})
    else:
        return JsonResponse({'error': 'Invalid action'}, status=400)


@login_required
def lead_create_application(request, pk):
    """Create an application for a lead"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    lead = get_object_or_404(Lead, pk=pk)
    
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = request.POST
    
    qualification_id = data.get('qualification_id')
    intake_id = data.get('intake_id')
    bypass_eligibility = data.get('bypass_eligibility', False)
    
    if not qualification_id:
        return JsonResponse({'error': 'Qualification required'}, status=400)
    
    from academics.models import Qualification
    from intakes.models import Intake
    
    qualification = get_object_or_404(Qualification, pk=qualification_id)
    intake = None
    if intake_id:
        intake = get_object_or_404(Intake, pk=intake_id)
    
    # Check eligibility if not bypassing
    if not bypass_eligibility and lead.pipeline:
        is_eligible, reason = lead.application_eligible_for_pipeline(lead.pipeline, bypass_check=False)
        if not is_eligible:
            return JsonResponse({'error': reason, 'eligibility_failed': True}, status=400)
    
    # Create opportunity first
    from .models import Opportunity
    opportunity, created = Opportunity.objects.get_or_create(
        lead=lead,
        qualification=qualification,
        defaults={
            'name': f"{lead.get_full_name()} - {qualification.name}",
            'value': 0,
            'stage': 'PROPOSAL',
            'brand': lead.brand,
            'campus': lead.campus,
        }
    )
    
    # Create application
    from .models import Application
    application = Application.objects.create(
        opportunity=opportunity,
        intake=intake,
        status='DRAFT',
        brand=lead.brand,
        campus=lead.campus,
        created_by=request.user,
    )
    
    # Log activity
    from .models import LeadActivity
    LeadActivity.objects.create(
        lead=lead,
        activity_type='STATUS_CHANGE',
        description=f'Application created for {qualification.name}' + (f' ({intake.name})' if intake else ''),
        created_by=request.user,
        brand=lead.brand,
        campus=lead.campus
    )
    
    return JsonResponse({
        'success': True,
        'application_id': str(application.id),
        'message': f'Application created for {qualification.name}'
    })


@login_required
def lead_assign(request, pk):
    """Assign lead to a user"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    lead = get_object_or_404(Lead, pk=pk)
    user_id = request.POST.get('user_id')
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    if user_id:
        new_assignee = get_object_or_404(User, pk=user_id)
    else:
        new_assignee = None
    
    old_assignee = lead.assigned_to
    lead.assigned_to = new_assignee
    lead.save()
    
    # Log activity
    if new_assignee:
        msg = f'Lead assigned to {new_assignee.get_full_name() or new_assignee.username}'
    else:
        msg = 'Lead unassigned'
    
    LeadActivity.objects.create(
        lead=lead,
        activity_type='ASSIGNMENT',
        description=msg,
        created_by=request.user,
        brand=lead.brand,
        campus=lead.campus
    )
    
    return JsonResponse({
        'success': True,
        'assigned_to': new_assignee.get_full_name() if new_assignee else None
    })


@login_required
def lead_set_follow_up(request, pk):
    """Set follow-up date for a lead"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    lead = get_object_or_404(Lead, pk=pk)
    follow_up_date = request.POST.get('follow_up_date')
    follow_up_notes = request.POST.get('follow_up_notes', '')
    
    if follow_up_date:
        from datetime import datetime
        try:
            lead.next_follow_up = datetime.fromisoformat(follow_up_date)
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)
    else:
        lead.next_follow_up = None
    
    lead.follow_up_notes = follow_up_notes
    lead.save()
    
    # Log activity
    LeadActivity.objects.create(
        lead=lead,
        activity_type='FOLLOW_UP',
        description=f'Follow-up scheduled: {follow_up_date}. {follow_up_notes}',
        created_by=request.user,
        brand=lead.brand,
        campus=lead.campus
    )
    
    return JsonResponse({
        'success': True,
        'next_follow_up': lead.next_follow_up.strftime('%Y-%m-%d %H:%M') if lead.next_follow_up else None
    })


class BulkMessagingListView(LoginRequiredMixin, CRMAccessMixin, ListView):
    """
    List leads eligible for bulk messaging
    """
    model = Lead
    template_name = 'crm/bulk_messaging.html'
    context_object_name = 'leads'
    paginate_by = 50
    
    def get_queryset(self):
        # Only leads with consent who haven't unsubscribed
        queryset = Lead.objects.filter(
            consent_bulk_messaging=True,
            unsubscribed=False
        ).exclude(
            status__in=['ENROLLED', 'LOST']
        ).select_related('source', 'campus', 'campus__brand')
        
        # Filter by lead type
        lead_type = self.request.GET.get('lead_type')
        if lead_type:
            queryset = queryset.filter(lead_type=lead_type)
        
        # Filter by age for school leavers
        age_filter = self.request.GET.get('age')
        if age_filter == 'minor':
            eighteen_years_ago = timezone.now().date() - timedelta(days=18*365)
            queryset = queryset.filter(date_of_birth__gt=eighteen_years_ago)
        elif age_filter == 'adult':
            eighteen_years_ago = timezone.now().date() - timedelta(days=18*365)
            queryset = queryset.filter(date_of_birth__lte=eighteen_years_ago)
        
        return queryset.order_by('lead_type', 'last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lead_types'] = Lead.LEAD_TYPE_CHOICES
        context['total_with_consent'] = Lead.objects.filter(
            consent_bulk_messaging=True, unsubscribed=False
        ).count()
        return context


# Lead Sources Management
class LeadSourceListView(LoginRequiredMixin, CRMAccessMixin, ListView):
    """List all lead sources"""
    model = LeadSource
    template_name = 'crm/source_list.html'
    context_object_name = 'sources'
    
    def get_queryset(self):
        return LeadSource.objects.annotate(
            lead_count=Count('leads')
        ).order_by('name')


class LeadSourceCreateView(LoginRequiredMixin, CRMAccessMixin, CreateView):
    """Create a lead source"""
    model = LeadSource
    template_name = 'crm/source_form.html'
    fields = ['name', 'description', 'is_active']
    success_url = reverse_lazy('crm:source_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Lead Source'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Lead source created successfully.')
        return super().form_valid(form)


# =====================================================
# Sales Agent Pipeline Dashboard
# =====================================================

class SalesPipelineView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    Sales agent pipeline board - kanban-style view.
    Shows leads organized by pipeline stages.
    Supports cross-campus viewing and actions.
    """
    template_name = 'crm/pipeline/sales_pipeline.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        from .models import Pipeline, PipelineStage, AgentNotification
        from .services.pipeline import PipelineService
        from tenants.models import Campus
        
        # Get user's default campus
        user_campus = None
        if hasattr(user, 'profile') and user.profile:
            user_campus = getattr(user.profile, 'campus', None)
        
        # Campus filter from URL (allows cross-campus viewing)
        campus_id = self.request.GET.get('campus')
        if campus_id:
            selected_campus = Campus.objects.filter(pk=campus_id, is_active=True).first()
        else:
            selected_campus = user_campus
        
        context['selected_campus'] = selected_campus
        context['user_campus'] = user_campus
        context['all_campuses'] = Campus.objects.filter(is_active=True)
        context['show_campus_selector'] = Campus.objects.filter(is_active=True).count() > 1
        
        # Get selected pipeline (from URL or user's default)
        pipeline_id = self.request.GET.get('pipeline')
        if pipeline_id:
            pipeline = Pipeline.objects.filter(pk=pipeline_id, is_active=True).first()
        elif selected_campus:
            # Get default pipeline for selected campus
            pipeline = Pipeline.objects.filter(
                is_active=True,
                campus=selected_campus,
                is_default=True
            ).first() or Pipeline.objects.filter(
                is_active=True,
                campus=selected_campus
            ).first()
        else:
            # Fallback to any active pipeline
            pipeline = Pipeline.objects.filter(is_active=True).first()
        
        context['current_pipeline'] = pipeline
        
        # All pipelines - optionally filter by selected campus
        all_pipelines = Pipeline.objects.filter(is_active=True)
        if selected_campus:
            context['all_pipelines'] = all_pipelines.filter(campus=selected_campus)
        else:
            context['all_pipelines'] = all_pipelines
        
        if not pipeline:
            context['stages'] = []
            return context
        
        # Get stages with leads
        stages_data = []
        stages = pipeline.stages.all().order_by('order')
        
        # Import for annotations
        from django.db.models import Exists, OuterRef, Subquery
        from .models import PreApprovalLetter
        
        # Annotate leads with pre-approval status
        latest_letter_status = PreApprovalLetter.objects.filter(
            lead=OuterRef('pk')
        ).order_by('-issued_date').values('status')[:1]
        
        latest_letter_number = PreApprovalLetter.objects.filter(
            lead=OuterRef('pk')
        ).order_by('-issued_date').values('letter_number')[:1]
        
        # Base lead filter - filter by pipeline and exclude final statuses
        leads_qs = Lead.objects.filter(
            pipeline=pipeline
        ).exclude(
            status__in=['ENROLLED', 'LOST']  # Exclude completed/lost leads from main view
        ).select_related(
            'source', 'qualification_interest', 'assigned_to', 'campus'
        ).annotate(
            has_pre_approval=Exists(
                PreApprovalLetter.objects.filter(lead=OuterRef('pk'))
            ),
            pre_approval_status=Subquery(latest_letter_status),
            pre_approval_number=Subquery(latest_letter_number),
        )
        
        # Filter by assignment if not superuser - default to showing all for better UX
        show_all = self.request.GET.get('show_all', '1') == '1' or user.is_superuser
        if not show_all and not user.is_superuser:
            leads_qs = leads_qs.filter(assigned_to=user)
        
        context['show_all'] = show_all
        
        for stage in stages:
            stage_leads = leads_qs.filter(current_stage=stage).order_by('-engagement_score', 'stage_entered_at')
            
            stages_data.append({
                'stage': stage,
                'leads': stage_leads[:20],  # Limit for performance
                'total_count': stage_leads.count(),
                'win_probability': stage.win_probability,
            })
        
        context['stages'] = stages_data
        
        # Dashboard data for the agent (pass campus, not pipeline)
        context['dashboard'] = PipelineService.get_agent_dashboard_data(user, selected_campus)
        
        # Unread notifications count
        context['unread_notifications'] = AgentNotification.objects.filter(
            agent=user,
            is_read=False
        ).count()
        
        return context


class PipelineHubView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    Unified Pipeline Hub - single entry point for all pipeline activities.
    
    Features:
    - Pipeline overview with stats cards
    - Tabs: Leads | Opportunities | Applications
    - Requirements tracking (documents, payments, forms)
    - Responsive kanban with collapsible stages
    """
    template_name = 'crm/pipeline/pipeline_hub.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        from .models import Pipeline, PipelineStage, AgentNotification, Opportunity, Application
        from .services.pipeline import PipelineService
        from tenants.models import Campus
        
        # Get user's default campus
        user_campus = None
        if hasattr(user, 'profile') and user.profile:
            user_campus = getattr(user.profile, 'campus', None)
        
        # Campus filter from URL
        campus_id = self.request.GET.get('campus')
        if campus_id:
            selected_campus = Campus.objects.filter(pk=campus_id, is_active=True).first()
        else:
            selected_campus = user_campus
        
        context['selected_campus'] = selected_campus
        context['user_campus'] = user_campus
        context['all_campuses'] = Campus.objects.filter(is_active=True)
        context['show_campus_selector'] = Campus.objects.filter(is_active=True).count() > 1
        
        # Active tab (leads, opportunities, applications)
        active_tab = self.request.GET.get('tab', 'leads')
        context['active_tab'] = active_tab
        
        # Show all or just user's leads
        show_all = self.request.GET.get('show_all', '1') == '1' or user.is_superuser
        context['show_all'] = show_all
        
        # ==========================================
        # PIPELINE OVERVIEW CARDS
        # ==========================================
        all_pipelines = Pipeline.objects.filter(is_active=True)
        if selected_campus:
            all_pipelines = all_pipelines.filter(campus=selected_campus)
        
        pipeline_cards = []
        for pipeline in all_pipelines:
            leads_count = Lead.objects.filter(
                pipeline=pipeline
            ).exclude(status__in=['ENROLLED', 'LOST']).count()
            
            # Get stage breakdown
            stage_counts = []
            for stage in pipeline.stages.all().order_by('order')[:4]:
                stage_leads = Lead.objects.filter(
                    pipeline=pipeline,
                    current_stage=stage
                ).exclude(status__in=['ENROLLED', 'LOST']).count()
                stage_counts.append({'name': stage.name, 'count': stage_leads, 'color': stage.color})
            
            pipeline_cards.append({
                'pipeline': pipeline,
                'leads_count': leads_count,
                'stage_counts': stage_counts,
            })
        
        context['pipeline_cards'] = pipeline_cards
        
        # Selected pipeline (from URL or default)
        pipeline_id = self.request.GET.get('pipeline')
        if pipeline_id:
            selected_pipeline = Pipeline.objects.filter(pk=pipeline_id, is_active=True).first()
        elif selected_campus:
            selected_pipeline = Pipeline.objects.filter(
                is_active=True,
                campus=selected_campus,
                is_default=True
            ).first() or Pipeline.objects.filter(
                is_active=True,
                campus=selected_campus
            ).first()
        else:
            selected_pipeline = Pipeline.objects.filter(is_active=True).first()
        
        context['current_pipeline'] = selected_pipeline
        context['all_pipelines'] = all_pipelines
        
        # ==========================================
        # LEADS TAB DATA
        # ==========================================
        if selected_pipeline and active_tab == 'leads':
            from django.db.models import Exists, OuterRef, Max, Subquery
            from .models import PreApprovalLetter
            
            stages_data = []
            stages = selected_pipeline.stages.all().order_by('order')
            
            # Annotate leads with pre-approval status
            latest_letter_status = PreApprovalLetter.objects.filter(
                lead=OuterRef('pk')
            ).order_by('-issued_date').values('status')[:1]
            
            latest_letter_number = PreApprovalLetter.objects.filter(
                lead=OuterRef('pk')
            ).order_by('-issued_date').values('letter_number')[:1]
            
            leads_qs = Lead.objects.filter(
                pipeline=selected_pipeline
            ).exclude(
                status__in=['ENROLLED', 'LOST']
            ).select_related(
                'source', 'qualification_interest', 'assigned_to', 'campus'
            ).annotate(
                has_pre_approval=Exists(
                    PreApprovalLetter.objects.filter(lead=OuterRef('pk'))
                ),
                pre_approval_status=Subquery(latest_letter_status),
                pre_approval_number=Subquery(latest_letter_number),
            )
            
            if not show_all and not user.is_superuser:
                leads_qs = leads_qs.filter(assigned_to=user)
            
            for stage in stages:
                stage_leads = leads_qs.filter(current_stage=stage).order_by('-engagement_score', 'stage_entered_at')
                
                # Requirements tracking for each lead
                leads_with_requirements = []
                for lead in stage_leads[:20]:
                    req_stats = self._get_lead_requirements(lead)
                    leads_with_requirements.append({
                        'lead': lead,
                        'requirements': req_stats
                    })
                
                stages_data.append({
                    'stage': stage,
                    'leads': leads_with_requirements,
                    'total_count': stage_leads.count(),
                    'win_probability': stage.win_probability,
                })
            
            context['stages'] = stages_data
            
            # Dashboard data
            context['dashboard'] = PipelineService.get_agent_dashboard_data(user, selected_campus)
        else:
            context['stages'] = []
            context['dashboard'] = {}
        
        # ==========================================
        # OPPORTUNITIES TAB DATA
        # ==========================================
        if active_tab == 'opportunities':
            OPPORTUNITY_STAGES = [
                ('DISCOVERY', 'Discovery', 'bg-gray-100', 'text-gray-700'),
                ('QUALIFICATION', 'Qualification', 'bg-blue-100', 'text-blue-700'),
                ('PROPOSAL', 'Proposal', 'bg-yellow-100', 'text-yellow-700'),
                ('NEGOTIATION', 'Negotiation', 'bg-purple-100', 'text-purple-700'),
                ('COMMITTED', 'Committed', 'bg-green-100', 'text-green-700'),
            ]
            
            opps_qs = Opportunity.objects.select_related(
                'lead', 'assigned_agent', 'qualification', 'campus', 'intake'
            ).exclude(stage__in=['WON', 'LOST'])
            
            if not user.is_superuser:
                if hasattr(user, 'profile') and user.profile.brand:
                    opps_qs = opps_qs.filter(campus__brand=user.profile.brand)
            
            if not show_all and not user.is_superuser:
                opps_qs = opps_qs.filter(assigned_agent=user)
            
            opp_stages_data = []
            for stage_key, stage_label, bg_class, text_class in OPPORTUNITY_STAGES:
                stage_opps = list(opps_qs.filter(stage=stage_key).order_by('-updated_at')[:20])
                opp_stages_data.append({
                    'key': stage_key,
                    'label': stage_label,
                    'bg_class': bg_class,
                    'text_class': text_class,
                    'opportunities': stage_opps,
                    'count': opps_qs.filter(stage=stage_key).count(),
                    'value': sum(o.value or 0 for o in stage_opps),
                })
            
            context['opportunity_stages'] = opp_stages_data
            
            # Opportunity summary stats
            all_opps = list(opps_qs)
            context['opportunity_stats'] = {
                'total_count': len(all_opps),
                'total_value': sum(o.value or 0 for o in all_opps),
                'weighted_value': sum((o.value or 0) * (o.probability or 0) / 100 for o in all_opps),
            }
        else:
            context['opportunity_stages'] = []
            context['opportunity_stats'] = {}
        
        # ==========================================
        # APPLICATIONS TAB DATA
        # ==========================================
        if active_tab == 'applications':
            APPLICATION_STATUSES = [
                ('DRAFT', 'Draft', 'bg-gray-100', 'text-gray-700'),
                ('SUBMITTED', 'Submitted', 'bg-blue-100', 'text-blue-700'),
                ('DOCUMENTS_PENDING', 'Documents Pending', 'bg-yellow-100', 'text-yellow-700'),
                ('UNDER_REVIEW', 'Under Review', 'bg-purple-100', 'text-purple-700'),
                ('ACCEPTED', 'Accepted', 'bg-green-100', 'text-green-700'),
            ]
            
            apps_qs = Application.objects.select_related(
                'opportunity', 'opportunity__lead', 'opportunity__qualification'
            ).exclude(status__in=['ENROLLED', 'REJECTED', 'WITHDRAWN'])
            
            if not user.is_superuser:
                if hasattr(user, 'profile') and user.profile.brand:
                    apps_qs = apps_qs.filter(opportunity__brand=user.profile.brand)
            
            app_stages_data = []
            for status_key, status_label, bg_class, text_class in APPLICATION_STATUSES:
                status_apps = list(apps_qs.filter(status=status_key).order_by('-created_at')[:20])
                app_stages_data.append({
                    'key': status_key,
                    'label': status_label,
                    'bg_class': bg_class,
                    'text_class': text_class,
                    'applications': status_apps,
                    'count': apps_qs.filter(status=status_key).count(),
                })
            
            context['application_stages'] = app_stages_data
            
            # Application summary stats
            context['application_stats'] = {
                'total_count': apps_qs.count(),
                'pending_docs': apps_qs.filter(status='DOCUMENTS_PENDING').count(),
                'accepted': apps_qs.filter(status='ACCEPTED').count(),
            }
        else:
            context['application_stages'] = []
            context['application_stats'] = {}
        
        # Unread notifications count
        context['unread_notifications'] = AgentNotification.objects.filter(
            agent=user,
            is_read=False
        ).count()
        
        return context
    
    def _get_lead_requirements(self, lead):
        """Get requirements tracking stats for a lead."""
        # Default empty stats
        stats = {
            'documents': {'required': 0, 'received': 0, 'pending': 0},
            'payments': {'required': 0, 'received': 0, 'pending': 0},
            'forms': {'required': 0, 'completed': 0, 'pending': 0},
            'has_pending': False
        }
        
        try:
            # Check for associated opportunity/application
            opportunity = lead.opportunities.filter(
                stage__in=['COMMITTED', 'NEGOTIATION', 'PROPOSAL']
            ).first()
            
            if opportunity and hasattr(opportunity, 'application'):
                app = opportunity.application
                
                # Document requirements
                required_docs = app.required_documents or []
                missing_docs = app.missing_documents or []
                stats['documents']['required'] = len(required_docs)
                stats['documents']['pending'] = len(missing_docs)
                stats['documents']['received'] = len(required_docs) - len(missing_docs)
            
            # Check for pending payments
            # Note: This would need adjustment based on actual payment model
            
            stats['has_pending'] = (
                stats['documents']['pending'] > 0 or 
                stats['payments']['pending'] > 0 or
                stats['forms']['pending'] > 0
            )
        except Exception:
            pass
        
        return stats


class AgentNotificationsView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    View agent notifications with ability to mark as read.
    """
    template_name = 'crm/pipeline/notifications.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        from .models import AgentNotification
        
        notifications = AgentNotification.objects.filter(
            agent=user
        ).select_related('lead').order_by('-created_at')
        
        context['unread_notifications'] = notifications.filter(is_read=False)[:50]
        context['read_notifications'] = notifications.filter(is_read=True)[:50]
        context['total_unread'] = notifications.filter(is_read=False).count()
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle marking notifications as read."""
        from .models import AgentNotification
        
        action = request.POST.get('action')
        notification_id = request.POST.get('notification_id')
        
        if action == 'mark_read' and notification_id:
            AgentNotification.objects.filter(
                pk=notification_id,
                agent=request.user
            ).update(is_read=True, read_at=timezone.now())
        
        elif action == 'mark_all_read':
            AgentNotification.objects.filter(
                agent=request.user,
                is_read=False
            ).update(is_read=True, read_at=timezone.now())
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok'})
        
        return redirect('crm:notifications')


class PipelineStageUpdateView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    AJAX endpoint to move a lead to a different pipeline stage.
    """
    
    def post(self, request, *args, **kwargs):
        from .models import PipelineStage
        from .services.pipeline import PipelineService
        import json
        
        try:
            data = json.loads(request.body)
            lead_id = data.get('lead_id')
            stage_id = data.get('stage_id')
            notes = data.get('notes', '')
            
            lead = Lead.objects.filter(pk=lead_id).first()
            stage = PipelineStage.objects.filter(pk=stage_id).first()
            
            if not lead or not stage:
                return JsonResponse({'error': 'Invalid lead or stage'}, status=400)
            
            # Move the lead
            success, message = PipelineService.move_to_stage(
                lead=lead,
                new_stage=stage,
                moved_by=request.user,
                notes=notes
            )
            
            if success:
                return JsonResponse({
                    'status': 'ok',
                    'message': message,
                    'lead': {
                        'id': lead.pk,
                        'name': lead.get_full_name(),
                        'stage': stage.name,
                        'stage_id': stage.pk,
                    }
                })
            else:
                return JsonResponse({'error': message}, status=400)
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class LeadQuickActionsView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    AJAX endpoint for quick lead actions (log call, send quote, etc.)
    """
    
    def post(self, request, *args, **kwargs):
        import json
        
        try:
            data = json.loads(request.body)
            lead_id = data.get('lead_id')
            action = data.get('action')
            
            lead = Lead.objects.filter(pk=lead_id).first()
            if not lead:
                return JsonResponse({'error': 'Lead not found'}, status=404)
            
            if action == 'log_call':
                notes = data.get('notes', 'Phone call')
                outcome = data.get('outcome', 'ANSWERED')
                
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type='CALL',
                    description=notes,
                    outcome=outcome,
                    created_by=request.user
                )
                
                # Update last contacted
                lead.last_contacted = timezone.now()
                if lead.status == 'NEW':
                    lead.status = 'CONTACTED'
                lead.save(update_fields=['last_contacted', 'status'])
                
                return JsonResponse({
                    'status': 'ok',
                    'message': 'Call logged successfully'
                })
            
            elif action == 'schedule_follow_up':
                follow_up_date = data.get('date')
                if follow_up_date:
                    from datetime import datetime
                    lead.next_follow_up = datetime.fromisoformat(follow_up_date)
                    lead.save(update_fields=['next_follow_up'])
                    
                    return JsonResponse({
                        'status': 'ok',
                        'message': f'Follow-up scheduled for {lead.next_follow_up.strftime("%d %b %Y")}'
                    })
            
            elif action == 'mark_lost':
                reason = data.get('reason', 'Unknown')
                lead.status = 'LOST'
                lead.lost_reason = reason
                lead.save(update_fields=['status', 'lost_reason'])
                
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type='NOTE',
                    description=f'Marked as lost: {reason}',
                    created_by=request.user
                )
                
                return JsonResponse({
                    'status': 'ok',
                    'message': 'Lead marked as lost'
                })
            
            return JsonResponse({'error': 'Unknown action'}, status=400)
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class NotificationAPIView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    API endpoint for notification bell - returns recent notifications.
    """
    
    def get(self, request, *args, **kwargs):
        from .models import AgentNotification
        
        notifications = AgentNotification.objects.filter(
            agent=request.user,
            is_read=False
        ).select_related('lead').order_by('-created_at')[:10]
        
        data = {
            'unread_count': notifications.count(),
            'notifications': [
                {
                    'id': str(n.pk),
                    'type': n.notification_type,
                    'title': n.title,
                    'message': n.message,
                    'priority': n.priority,
                    'lead_id': n.lead_id,
                    'lead_name': n.lead.get_full_name() if n.lead else None,
                    'created_at': n.created_at.isoformat(),
                    'action_url': n.action_url,
                }
                for n in notifications
            ]
        }
        
        return JsonResponse(data)


class PipelineMoveStageByCodeView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    AJAX endpoint to move a lead to a stage by stage code (e.g., CONTACTED, PRE_APPROVED).
    Simpler than move by ID for one-click stage transitions.
    """
    
    def post(self, request, *args, **kwargs):
        from .models import PipelineStage, Lead
        from .services.pipeline import PipelineService
        import json
        
        try:
            data = json.loads(request.body)
            lead_id = data.get('lead_id')
            stage_code = data.get('stage_code')
            notes = data.get('notes', '')
            lost_reason = data.get('lost_reason', '')
            
            lead = Lead.objects.filter(pk=lead_id).first()
            if not lead:
                return JsonResponse({'error': 'Lead not found'}, status=404)
            
            if not lead.current_pipeline:
                return JsonResponse({'error': 'Lead has no pipeline assigned'}, status=400)
            
            # Find the stage by code within the lead's pipeline
            stage = PipelineStage.objects.filter(
                pipeline=lead.current_pipeline,
                code=stage_code
            ).first()
            
            if not stage:
                return JsonResponse({'error': f'Stage {stage_code} not found in pipeline'}, status=400)
            
            # If marking as lost, save the reason
            if stage_code == 'LOST' and lost_reason:
                lead.lost_reason = lost_reason
                lead.save(update_fields=['lost_reason'])
                notes = f'Lost reason: {lost_reason}. {notes}'
            
            # Move the lead
            result = PipelineService.move_to_stage(
                lead=lead,
                new_stage=stage,
                moved_by=request.user,
                notes=notes
            )
            
            if result.get('success'):
                message = f'Lead moved to {stage.name}'
                
                # Add context for special stages
                if stage_code == 'PRE_APPROVED' and result.get('pre_approval_letter'):
                    letter = result['pre_approval_letter']
                    message = f'Pre-approval letter {letter.letter_number} sent!'
                elif stage_code == 'APPLICATION' and result.get('application'):
                    message = 'Application created successfully!'
                
                return JsonResponse({
                    'status': 'ok',
                    'message': message,
                    'lead': {
                        'id': lead.pk,
                        'name': lead.get_full_name(),
                        'stage': stage.name,
                        'stage_code': stage.code,
                    },
                    'actions_triggered': result.get('actions_triggered', [])
                })
            else:
                return JsonResponse({'error': result.get('error', 'Failed to move lead')}, status=400)
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# PUBLIC PRE-APPROVAL PORTAL VIEWS
# =============================================================================

class PreApprovalPortalView(TemplateView):
    """
    Public portal view for pre-approval letters.
    No login required - uses token-based access.
    
    Features:
    - View pre-approval letter details
    - Download PDF
    - Accept terms and start application (for adults)
    - Request parent consent (for minors)
    """
    template_name = 'crm/portal/pre_approval_portal.html'
    
    def get_letter(self):
        """Get the pre-approval letter from the token."""
        from crm.models import PreApprovalLetter
        token = self.kwargs.get('token')
        return get_object_or_404(PreApprovalLetter, id=token)
    
    def get(self, request, *args, **kwargs):
        letter = self.get_letter()
        
        # Track view
        letter.mark_viewed()
        
        # Record engagement event
        from crm.models import LeadEngagement
        LeadEngagement.objects.create(
            lead=letter.lead,
            event_type='DOCUMENT_VIEWED',
            event_data={'letter_number': letter.letter_number, 'type': 'pre_approval'},
            ip_address=self.get_client_ip(request),
        )
        
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        letter = self.get_letter()
        lead = letter.lead
        
        context['letter'] = letter
        context['lead'] = lead
        context['qualification'] = letter.qualification
        context['campus'] = letter.campus
        context['is_valid'] = letter.is_portal_valid
        context['is_minor'] = letter.requires_parent_consent
        context['can_start_application'] = letter.can_start_application
        context['has_parent_consent'] = letter.parent_consent_given
        context['learner_accepted'] = letter.learner_accepted
        
        # Get brand for styling
        if letter.campus and letter.campus.brand:
            context['brand'] = letter.campus.brand
        
        return context
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class PreApprovalAcceptView(TemplateView):
    """
    Handle acceptance of pre-approval terms by the learner.
    POST: Accept terms and optionally start application.
    """
    template_name = 'crm/portal/pre_approval_accept.html'
    
    def get_letter(self):
        from crm.models import PreApprovalLetter
        token = self.kwargs.get('token')
        return get_object_or_404(PreApprovalLetter, id=token)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        letter = self.get_letter()
        context['letter'] = letter
        context['lead'] = letter.lead
        context['qualification'] = letter.qualification
        context['is_minor'] = letter.requires_parent_consent
        return context
    
    def post(self, request, *args, **kwargs):
        import json
        letter = self.get_letter()
        
        # Validate letter is still valid
        if not letter.is_portal_valid:
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'error': 'This pre-approval has expired or been revoked.'
                }, status=400)
            messages.error(request, 'This pre-approval has expired or been revoked.')
            return redirect('crm:pre_approval_portal', token=str(letter.id))
        
        # Get IP address
        ip_address = self.get_client_ip(request)
        
        # Handle JSON or form data
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
        else:
            data = request.POST
        
        terms_accepted = data.get('terms_accepted') in [True, 'true', 'on', '1']
        start_application = data.get('start_application') in [True, 'true', 'on', '1']
        
        if not terms_accepted:
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'error': 'You must accept the terms to continue.'
                }, status=400)
            messages.error(request, 'You must accept the terms to continue.')
            return redirect('crm:pre_approval_portal', token=str(letter.id))
        
        # Record learner acceptance
        letter.record_learner_acceptance(ip_address=ip_address, terms_accepted=True)
        
        # Log activity
        from crm.models import LeadActivity
        LeadActivity.objects.create(
            lead=letter.lead,
            activity_type='STATUS_CHANGE',
            description=f'Learner accepted pre-approval terms via portal',
            is_automated=True,
            automation_source='pre_approval_portal',
        )
        
        # If minor and no parent consent, redirect to parent consent page
        if letter.requires_parent_consent and not letter.parent_consent_given:
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': 'Terms accepted. Parent/guardian consent is required.',
                    'redirect': reverse_lazy('crm:pre_approval_parent_consent', kwargs={'token': str(letter.id)}),
                    'needs_parent_consent': True
                })
            messages.info(request, 'Thank you! Parent/guardian consent is required to proceed.')
            return redirect('crm:pre_approval_parent_consent', token=str(letter.id))
        
        # If start_application is requested and allowed
        if start_application and letter.can_start_application:
            application = letter.start_application()
            
            LeadActivity.objects.create(
                lead=letter.lead,
                activity_type='APPLICATION_STARTED',
                description=f'Application started via pre-approval portal',
                is_automated=True,
                automation_source='pre_approval_portal',
            )
            
            # Notify agent
            if letter.lead.assigned_to:
                from crm.models import AgentNotification
                AgentNotification.objects.create(
                    agent=letter.lead.assigned_to,
                    notification_type='APPLICATION_STARTED',
                    title=f'Application started from portal!',
                    message=f'{letter.lead.get_full_name()} accepted pre-approval and started application via the self-service portal.',
                    lead=letter.lead,
                    action_url=f'/crm/applications/{application.pk}/',
                    action_label='View Application'
                )
            
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': 'Application started successfully!',
                    'application_id': str(application.pk),
                    'redirect': reverse_lazy('crm:pre_approval_success', kwargs={'token': str(letter.id)})
                })
            messages.success(request, 'Your application has been started! Our team will be in touch.')
            return redirect('crm:pre_approval_success', token=str(letter.id))
        
        # Just accepted terms without starting application
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': True,
                'message': 'Terms accepted successfully!',
                'redirect': reverse_lazy('crm:pre_approval_portal', kwargs={'token': str(letter.id)})
            })
        messages.success(request, 'Thank you for accepting the terms!')
        return redirect('crm:pre_approval_portal', token=str(letter.id))
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class PreApprovalParentConsentView(TemplateView):
    """
    Parent/guardian consent page for minor learners.
    """
    template_name = 'crm/portal/parent_consent.html'
    
    def get_letter(self):
        from crm.models import PreApprovalLetter
        token = self.kwargs.get('token')
        return get_object_or_404(PreApprovalLetter, id=token)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        letter = self.get_letter()
        context['letter'] = letter
        context['lead'] = letter.lead
        context['qualification'] = letter.qualification
        context['campus'] = letter.campus
        context['parent_name'] = letter.lead.parent_name or "Parent/Guardian"
        context['consent_given'] = letter.parent_consent_given
        return context
    
    def post(self, request, *args, **kwargs):
        import json
        letter = self.get_letter()
        
        if not letter.is_portal_valid:
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'error': 'This pre-approval has expired.'
                }, status=400)
            messages.error(request, 'This pre-approval has expired.')
            return redirect('crm:pre_approval_portal', token=str(letter.id))
        
        # Get data
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
        else:
            data = request.POST
        
        consent_given = data.get('consent_given') in [True, 'true', 'on', '1']
        parent_name_confirmed = data.get('parent_name', '').strip()
        
        if not consent_given:
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'error': 'Consent is required to proceed.'
                }, status=400)
            messages.error(request, 'Consent is required to proceed.')
            return redirect('crm:pre_approval_parent_consent', token=str(letter.id))
        
        # Get IP
        ip_address = self.get_client_ip(request)
        
        # Record consent
        letter.record_parent_consent(ip_address=ip_address)
        
        # Log activity
        from crm.models import LeadActivity
        LeadActivity.objects.create(
            lead=letter.lead,
            activity_type='CONSENT_GIVEN',
            description=f'Parent consent given via portal by {parent_name_confirmed or "parent/guardian"}',
            is_automated=True,
            automation_source='pre_approval_portal',
        )
        
        # Notify agent
        if letter.lead.assigned_to:
            from crm.models import AgentNotification
            AgentNotification.objects.create(
                agent=letter.lead.assigned_to,
                notification_type='ACTION_REQUIRED',
                title=f'Parent consent received!',
                message=f'Parent/guardian consent received for {letter.lead.get_full_name()}. Learner can now proceed with application.',
                lead=letter.lead,
                action_url=f'/crm/leads/{letter.lead.pk}/',
                action_label='View Lead'
            )
        
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': True,
                'message': 'Consent recorded successfully!',
                'redirect': reverse_lazy('crm:pre_approval_portal', kwargs={'token': str(letter.id)})
            })
        messages.success(request, 'Thank you for providing consent!')
        return redirect('crm:pre_approval_portal', token=str(letter.id))
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class PreApprovalSuccessView(TemplateView):
    """
    Success page after application started.
    """
    template_name = 'crm/portal/pre_approval_success.html'
    
    def get_letter(self):
        from crm.models import PreApprovalLetter
        token = self.kwargs.get('token')
        return get_object_or_404(PreApprovalLetter, id=token)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        letter = self.get_letter()
        context['letter'] = letter
        context['lead'] = letter.lead
        context['qualification'] = letter.qualification
        context['application'] = letter.application
        return context


class PreApprovalPDFDownloadView(TemplateView):
    """
    Download pre-approval letter PDF.
    """
    def get(self, request, *args, **kwargs):
        from django.http import FileResponse, Http404
        from crm.models import PreApprovalLetter
        
        token = self.kwargs.get('token')
        letter = get_object_or_404(PreApprovalLetter, id=token)
        
        # Track download
        from crm.models import LeadEngagement
        LeadEngagement.objects.create(
            lead=letter.lead,
            event_type='DOCUMENT_DOWNLOADED',
            event_data={'letter_number': letter.letter_number, 'type': 'pre_approval_pdf'},
            ip_address=self.get_client_ip(request),
        )
        
        if not letter.pdf_file:
            # Generate PDF on the fly
            from crm.services.pre_approval import PreApprovalService
            PreApprovalService.save_pdf_to_letter(letter)
            letter.refresh_from_db()
        
        if letter.pdf_file:
            response = FileResponse(
                letter.pdf_file.open('rb'),
                as_attachment=True,
                filename=f'Pre-Approval-{letter.letter_number}.pdf'
            )
            return response
        
        raise Http404("PDF not available")
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# =============================================================================
# DOCUMENT UPLOAD PORTAL VIEWS (PUBLIC - NO LOGIN REQUIRED)
# =============================================================================

class DocumentUploadPortalView(TemplateView):
    """
    Public portal view for document uploads.
    No login required - uses token-based access via DocumentUploadRequest.
    
    Features:
    - View required documents
    - Upload files
    - Track progress
    """
    template_name = 'crm/portal/document_upload_portal.html'
    
    def get_request_obj(self):
        """Get the document upload request from the token."""
        from crm.models import DocumentUploadRequest
        token = self.kwargs.get('token')
        return get_object_or_404(DocumentUploadRequest, id=token)
    
    def get(self, request, *args, **kwargs):
        upload_request = self.get_request_obj()
        
        # Track view
        upload_request.mark_viewed()
        
        # Record engagement event
        from crm.models import LeadEngagement
        LeadEngagement.objects.create(
            lead=upload_request.lead,
            event_type='DOCUMENT_VIEWED',
            event_data={'request_id': str(upload_request.id), 'type': 'document_upload_portal'},
            ip_address=self.get_client_ip(request),
        )
        
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        upload_request = self.get_request_obj()
        lead = upload_request.lead
        
        context['upload_request'] = upload_request
        context['lead'] = lead
        context['is_valid'] = upload_request.is_valid
        context['is_expired'] = upload_request.is_expired
        context['upload_progress'] = upload_request.upload_progress
        context['all_uploaded'] = upload_request.all_documents_uploaded
        
        # Build document type info with upload status
        from crm.models import LeadDocument
        document_types = []
        type_display = dict(LeadDocument.DOCUMENT_TYPES)
        
        uploaded_docs = {
            doc.document_type: doc
            for doc in upload_request.uploaded_documents.all()
        }
        
        for doc_type in upload_request.requested_document_types:
            document_types.append({
                'code': doc_type,
                'name': type_display.get(doc_type, doc_type),
                'uploaded': doc_type in uploaded_docs,
                'document': uploaded_docs.get(doc_type),
            })
        
        context['document_types'] = document_types
        context['all_document_types'] = LeadDocument.DOCUMENT_TYPES
        
        # Get brand for styling
        if lead.qualification_interest and lead.qualification_interest.campus and lead.qualification_interest.campus.brand:
            context['brand'] = lead.qualification_interest.campus.brand
        
        return context
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


@method_decorator(csrf_exempt, name='dispatch')
class DocumentUploadSubmitView(TemplateView):
    """
    Handle document upload submissions.
    POST: Upload a document file.
    CSRF exempt as this is a public portal.
    """
    
    def get_request_obj(self):
        from crm.models import DocumentUploadRequest
        token = self.kwargs.get('token')
        return get_object_or_404(DocumentUploadRequest, id=token)
    
    def post(self, request, *args, **kwargs):
        import json
        from crm.models import DocumentUploadRequest, LeadDocument, LeadActivity, AgentNotification
        
        upload_request = self.get_request_obj()
        
        # Validate request is still valid
        if not upload_request.is_valid:
            return JsonResponse({
                'success': False,
                'error': 'This document upload link has expired.'
            }, status=400)
        
        # Get file
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No file uploaded.'
            }, status=400)
        
        uploaded_file = request.FILES['file']
        document_type = request.POST.get('document_type', '')
        description = request.POST.get('description', '').strip()
        
        if not document_type:
            return JsonResponse({
                'success': False,
                'error': 'Document type is required.'
            }, status=400)
        
        # Validate file type
        allowed_types = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
        if uploaded_file.content_type not in allowed_types:
            return JsonResponse({
                'success': False,
                'error': 'Only PDF, JPEG, and PNG files are allowed.'
            }, status=400)
        
        # Validate file size (max 10MB)
        if uploaded_file.size > 10 * 1024 * 1024:
            return JsonResponse({
                'success': False,
                'error': 'File size must be under 10MB.'
            }, status=400)
        
        # Get IP address
        ip_address = self.get_client_ip(request)
        
        # Create lead document
        lead_doc = LeadDocument.objects.create(
            lead=upload_request.lead,
            upload_request=upload_request,
            document_type=document_type,
            description=description,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            content_type=uploaded_file.content_type,
            uploaded_via_portal=True,
            upload_ip_address=ip_address,
        )
        
        # Log activity
        from crm.models import LeadDocument as LD
        type_display = dict(LD.DOCUMENT_TYPES).get(document_type, document_type)
        LeadActivity.objects.create(
            lead=upload_request.lead,
            activity_type='DOCUMENT_UPLOADED',
            description=f'Document uploaded via portal: {type_display}',
            is_automated=True,
            automation_source='document_upload_portal',
        )
        
        # Check if all documents are uploaded
        all_uploaded = upload_request.all_documents_uploaded
        if all_uploaded:
            upload_request.mark_completed()
            
            # Notify assigned agent
            if upload_request.lead.assigned_to:
                AgentNotification.objects.create(
                    agent=upload_request.lead.assigned_to,
                    notification_type='DOCUMENTS_RECEIVED',
                    title=f'All documents received!',
                    message=f'{upload_request.lead.get_full_name()} has uploaded all requested documents via the portal.',
                    lead=upload_request.lead,
                    action_url=f'/crm/leads/{upload_request.lead.pk}/',
                    action_label='View Lead'
                )
        else:
            # Notify about individual upload
            if upload_request.lead.assigned_to:
                AgentNotification.objects.create(
                    agent=upload_request.lead.assigned_to,
                    notification_type='DOCUMENT_RECEIVED',
                    title=f'Document received',
                    message=f'{upload_request.lead.get_full_name()} uploaded {type_display} via the portal.',
                    lead=upload_request.lead,
                    action_url=f'/crm/leads/{upload_request.lead.pk}/',
                    action_label='View Lead'
                )
        
        # Record engagement
        from crm.models import LeadEngagement
        LeadEngagement.objects.create(
            lead=upload_request.lead,
            event_type='DOCUMENT_UPLOADED',
            event_data={
                'document_id': str(lead_doc.id),
                'document_type': document_type,
                'filename': uploaded_file.name,
            },
            ip_address=ip_address,
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{type_display} uploaded successfully!',
            'document': {
                'id': str(lead_doc.id),
                'type': document_type,
                'filename': lead_doc.original_filename,
            },
            'all_uploaded': all_uploaded,
            'upload_progress': upload_request.upload_progress,
            'missing_documents': upload_request.get_missing_document_types(),
        })
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class DocumentUploadSuccessView(TemplateView):
    """
    Success page after all documents are uploaded.
    """
    template_name = 'crm/portal/document_upload_success.html'
    
    def get_request_obj(self):
        from crm.models import DocumentUploadRequest
        token = self.kwargs.get('token')
        return get_object_or_404(DocumentUploadRequest, id=token)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        upload_request = self.get_request_obj()
        
        context['upload_request'] = upload_request
        context['lead'] = upload_request.lead
        context['uploaded_documents'] = upload_request.uploaded_documents.all()
        
        return context


class SendDocumentUploadLinkView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    AJAX endpoint to send document upload link to a lead.
    Creates DocumentUploadRequest and sends via WhatsApp/Email.
    Supports both URL-based lead_id (pk) and body-based lead_id.
    """
    
    def post(self, request, *args, **kwargs):
        from .models import Lead, DocumentUploadRequest, LeadActivity
        from .services.document_upload import DocumentUploadService
        import json
        from datetime import timedelta
        
        try:
            data = json.loads(request.body)
            
            # Support lead_id from URL kwargs or from request body
            lead_id = kwargs.get('pk') or data.get('lead_id')
            
            document_types = data.get('document_types', [])
            send_via = data.get('send_via', 'whatsapp')  # 'whatsapp', 'email', or 'both'
            custom_message = data.get('message', '')
            validity_days = data.get('validity_days', 14)
            recipient = data.get('recipient', 'learner')  # 'learner' or 'parent'
            resend_request_id = data.get('resend_request_id')  # UUID of existing request to resend
            
            lead = Lead.objects.filter(pk=lead_id).first()
            if not lead:
                return JsonResponse({'error': 'Lead not found'}, status=404)
            
            # If resending an existing request
            if resend_request_id:
                try:
                    existing_request = DocumentUploadRequest.objects.get(pk=resend_request_id, lead=lead)
                    if not existing_request.is_valid:
                        return JsonResponse({'error': 'This request has expired. Please create a new one.'}, status=400)
                    
                    # Resend using the existing request
                    service = DocumentUploadService()
                    result = service.send_upload_link(
                        upload_request=existing_request,
                        send_via=send_via,
                        recipient=recipient,
                    )
                    
                    if result.get('success'):
                        # Update sent info
                        existing_request.sent_at = timezone.now()
                        existing_request.sent_by = request.user
                        existing_request.sent_via = send_via.upper() if send_via != 'both' else 'WHATSAPP'
                        existing_request.save(update_fields=['sent_at', 'sent_by', 'sent_via'])
                        
                        # Log activity
                        LeadActivity.objects.create(
                            lead=lead,
                            activity_type='DOCUMENT_REQUEST_SENT',
                            description=f'Document upload link resent via {send_via} to {recipient}',
                            created_by=request.user,
                        )
                        
                        return JsonResponse({
                            'success': True,
                            'message': 'Document upload link resent!',
                            'request_id': str(existing_request.id),
                            'portal_url': existing_request.get_full_portal_url(),
                            'sent_via': send_via,
                        })
                    else:
                        return JsonResponse({
                            'success': False,
                            'error': result.get('error', 'Failed to resend link')
                        }, status=400)
                        
                except DocumentUploadRequest.DoesNotExist:
                    return JsonResponse({'error': 'Document request not found'}, status=404)
            
            # Creating a new request
            if not document_types:
                return JsonResponse({'error': 'Please select at least one document type'}, status=400)
            
            # Create upload request
            upload_request = DocumentUploadRequest.objects.create(
                lead=lead,
                requested_document_types=document_types,
                message=custom_message,
                valid_until=timezone.now() + timedelta(days=validity_days),
                sent_via=send_via.upper() if send_via != 'both' else 'WHATSAPP',
                sent_at=timezone.now(),
                sent_by=request.user,
            )
            
            # Send link via selected channel(s)
            service = DocumentUploadService()
            result = service.send_upload_link(
                upload_request=upload_request,
                send_via=send_via,
                recipient=recipient,
            )
            
            if result.get('success'):
                # Log activity
                LeadActivity.objects.create(
                    lead=lead,
                    activity_type='DOCUMENT_REQUEST_SENT',
                    description=f'Document upload link sent via {send_via} to {recipient}. Requested: {", ".join(document_types)}',
                    created_by=request.user,
                )
                
                return JsonResponse({
                    'success': True,
                    'message': result.get('message', 'Document upload link sent!'),
                    'request_id': str(upload_request.id),
                    'portal_url': upload_request.get_full_portal_url(),
                    'sent_via': send_via,
                })
            else:
                # Delete request if send failed
                upload_request.delete()
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Failed to send document upload link')
                }, status=400)
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)


class LeadPreApproveView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    AJAX endpoint to pre-approve a lead. 
    Confirms entry requirements, generates and sends pre-approval letter.
    """
    
    def post(self, request, *args, **kwargs):
        from .models import PipelineStage, Lead, PreApprovalLetter
        from .services.pipeline import PipelineService
        import json
        
        try:
            data = json.loads(request.body)
            lead_id = data.get('lead_id')
            entry_requirements_confirmed = data.get('entry_requirements_confirmed', False)
            verbal_commitment = data.get('verbal_commitment', False)
            notes = data.get('notes', '')
            
            lead = Lead.objects.filter(pk=lead_id).first()
            if not lead:
                return JsonResponse({'error': 'Lead not found'}, status=404)
            
            if not lead.qualification_interest:
                return JsonResponse({
                    'error': 'Please set the qualification interest before pre-approving'
                }, status=400)
            
            if not entry_requirements_confirmed or not verbal_commitment:
                return JsonResponse({
                    'error': 'Please confirm entry requirements and verbal commitment'
                }, status=400)
            
            if not lead.current_pipeline:
                return JsonResponse({'error': 'Lead has no pipeline assigned'}, status=400)
            
            # Find the PRE_APPROVED stage
            pre_approved_stage = PipelineStage.objects.filter(
                pipeline=lead.current_pipeline,
                code='PRE_APPROVED'
            ).first()
            
            if not pre_approved_stage:
                return JsonResponse({
                    'error': 'Pre-Approved stage not configured in this pipeline'
                }, status=400)
            
            # Move lead to PRE_APPROVED stage (this triggers the automation)
            notes_with_context = f'Entry requirements confirmed. Verbal commitment received. {notes}'
            
            result = PipelineService.move_to_stage(
                lead=lead,
                new_stage=pre_approved_stage,
                moved_by=request.user,
                notes=notes_with_context
            )
            
            if result.get('success'):
                letter = result.get('pre_approval_letter')
                message = 'Lead pre-approved!'
                if letter:
                    message = f'Pre-approval letter {letter.letter_number} sent to {lead.get_full_name()}!'
                
                # Get portal URL if letter exists
                portal_url = letter.get_portal_url() if letter else None
                
                return JsonResponse({
                    'status': 'ok',
                    'message': message,
                    'lead': {
                        'id': lead.pk,
                        'name': lead.get_full_name(),
                        'stage': pre_approved_stage.name,
                    },
                    'letter_number': letter.letter_number if letter else None,
                    'letter_id': str(letter.id) if letter else None,
                    'portal_url': portal_url,
                    'sent_via': result.get('sent_via', 'email'),
                    'is_minor': result.get('is_minor', False),
                    'next_step_required': result.get('next_step_required', True),
                    'actions_triggered': result.get('actions_triggered', [])
                })
            else:
                return JsonResponse({
                    'error': result.get('error', 'Failed to pre-approve lead')
                }, status=400)
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# COMPLIANCE ALERTS DASHBOARD
# =============================================================================

class ComplianceAlertsDashboardView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    Dashboard showing compliance alerts for enrollments.
    Campus-scoped with ability to resolve alerts.
    """
    template_name = 'crm/compliance_alerts_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import ComplianceAlert, SalesEnrollmentRecord
        from tenants.models import Campus
        
        # Get filter parameters
        campus_id = self.request.GET.get('campus')
        alert_type = self.request.GET.get('alert_type')
        show_resolved = self.request.GET.get('show_resolved') == 'true'
        
        # Base queryset
        alerts = ComplianceAlert.objects.select_related(
            'enrollment_record',
            'enrollment_record__enrollment',
            'enrollment_record__enrollment__learner',
            'enrollment_record__sales_person',
            'campus'
        ).order_by('-created_at')
        
        # Campus scoping
        user = self.request.user
        selected_campus = get_selected_campus(self.request)
        
        if selected_campus:
            alerts = alerts.filter(campus=selected_campus)
        elif not user.is_superuser:
            # Non-superusers see only their campus
            if hasattr(user, 'profile') and user.profile and user.profile.campus:
                alerts = alerts.filter(campus=user.profile.campus)
        
        # Additional filters
        if campus_id:
            alerts = alerts.filter(campus_id=campus_id)
        if alert_type:
            alerts = alerts.filter(alert_type=alert_type)
        if not show_resolved:
            alerts = alerts.filter(resolved=False)
        
        # Stats
        context['stats'] = {
            'total_open': alerts.filter(resolved=False).count(),
            'missing_docs': alerts.filter(resolved=False, alert_type='MISSING_DOCUMENTS').count(),
            'quality_rejected': alerts.filter(resolved=False, alert_type='QUALITY_REJECTED').count(),
        }
        
        context['alerts'] = alerts[:100]  # Limit to 100 most recent
        context['campuses'] = Campus.objects.filter(is_active=True)
        context['selected_campus'] = campus_id
        context['selected_alert_type'] = alert_type
        context['show_resolved'] = show_resolved
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle alert resolution"""
        from .models import ComplianceAlert
        import json
        
        try:
            data = json.loads(request.body)
            alert_id = data.get('alert_id')
            action = data.get('action')
            notes = data.get('notes', '')
            
            if action == 'resolve':
                alert = get_object_or_404(ComplianceAlert, pk=alert_id)
                alert.resolve(user=request.user, notes=notes)
                return JsonResponse({
                    'status': 'ok',
                    'message': 'Alert resolved successfully'
                })
            
            return JsonResponse({'error': 'Invalid action'}, status=400)
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# SALES COMMISSION DASHBOARD
# =============================================================================

class SalesCommissionDashboardView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    Dashboard showing sales enrollment records for commission calculation.
    Campus-scoped with Excel export functionality.
    """
    template_name = 'crm/sales_commission_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import SalesEnrollmentRecord
        from tenants.models import Campus
        from django.db.models import Count, Sum, Case, When, IntegerField
        from core.models import User
        
        # Get filter parameters
        month = self.request.GET.get('month', timezone.now().strftime('%Y-%m'))
        campus_id = self.request.GET.get('campus')
        sales_person_id = self.request.GET.get('sales_person')
        
        # Base queryset
        records = SalesEnrollmentRecord.objects.select_related(
            'enrollment',
            'enrollment__learner',
            'sales_person',
            'campus'
        )
        
        # Campus scoping
        user = self.request.user
        selected_campus = get_selected_campus(self.request)
        
        if selected_campus:
            records = records.filter(campus=selected_campus)
        elif not user.is_superuser:
            if hasattr(user, 'profile') and user.profile and user.profile.campus:
                records = records.filter(campus=user.profile.campus)
        
        # Additional filters
        if month:
            records = records.filter(month_period=month)
        if campus_id:
            records = records.filter(campus_id=campus_id)
        if sales_person_id:
            records = records.filter(sales_person_id=sales_person_id)
        
        # Aggregate by sales person
        sales_stats = records.values(
            'sales_person__id',
            'sales_person__first_name',
            'sales_person__last_name',
            'sales_person__email'
        ).annotate(
            total_enrollments=Count('id'),
            docs_complete=Count('id', filter=Q(documents_uploaded_complete=True)),
            quality_approved=Count('id', filter=Q(documents_quality_approved=True)),
            pop_received=Count('id', filter=Q(proof_of_payment_received=True)),
            private_count=Count('id', filter=Q(funding_type__in=['PRIVATE_UPFRONT', 'PRIVATE_PMT_AGREEMENT'])),
            bursary_count=Count('id', filter=Q(funding_type__in=['GOVERNMENT_BURSARY', 'CORPORATE_BURSARY', 'DG_BURSARY'])),
            commission_eligible=Count('id', filter=Q(
                documents_uploaded_complete=True,
                documents_quality_approved=True,
                proof_of_payment_received=True,
                funding_type__in=['PRIVATE_UPFRONT', 'PRIVATE_PMT_AGREEMENT']
            ))
        ).order_by('-total_enrollments')
        
        # Overall stats
        overall_stats = {
            'total_enrollments': records.count(),
            'total_eligible': records.filter(
                documents_uploaded_complete=True,
                documents_quality_approved=True,
                proof_of_payment_received=True,
                funding_type__in=['PRIVATE_UPFRONT', 'PRIVATE_PMT_AGREEMENT']
            ).count(),
            'total_bursary': records.filter(
                funding_type__in=['GOVERNMENT_BURSARY', 'CORPORATE_BURSARY', 'DG_BURSARY']
            ).count(),
        }
        
        # Get available months (last 12 months)
        months = []
        current = timezone.now().date()
        for i in range(12):
            m = current.replace(day=1) - timedelta(days=i*30)
            months.append(m.strftime('%Y-%m'))
        
        context['sales_stats'] = list(sales_stats)
        context['overall_stats'] = overall_stats
        context['records'] = records[:200]  # For detailed view
        context['campuses'] = Campus.objects.filter(is_active=True)
        context['months'] = sorted(set(months), reverse=True)
        context['selected_month'] = month
        context['selected_campus'] = campus_id
        context['selected_sales_person'] = sales_person_id
        
        # Get sales people for filter
        context['sales_people'] = User.objects.filter(
            is_active=True,
            sales_enrollment_records__isnull=False
        ).distinct()
        
        return context


class SalesCommissionExportView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """Export sales commission data to Excel"""
    
    def get(self, request, *args, **kwargs):
        from .models import SalesEnrollmentRecord
        import csv
        from django.http import HttpResponse
        
        month = request.GET.get('month', timezone.now().strftime('%Y-%m'))
        campus_id = request.GET.get('campus')
        
        # Build queryset
        records = SalesEnrollmentRecord.objects.select_related(
            'enrollment',
            'enrollment__learner',
            'sales_person',
            'campus'
        ).filter(month_period=month)
        
        # Campus scoping
        user = request.user
        selected_campus = get_selected_campus(request)
        
        if selected_campus:
            records = records.filter(campus=selected_campus)
        elif campus_id:
            records = records.filter(campus_id=campus_id)
        elif not user.is_superuser:
            if hasattr(user, 'profile') and user.profile and user.profile.campus:
                records = records.filter(campus=user.profile.campus)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="sales_commission_{month}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Enrollment Number',
            'Learner Name',
            'Sales Person',
            'Campus',
            'Enrollment Date',
            'Funding Type',
            'Docs Complete',
            'Quality Approved',
            'POP Received',
            'Commission Eligible'
        ])
        
        for record in records:
            learner_name = record.enrollment.learner.get_full_name() if record.enrollment and record.enrollment.learner else 'N/A'
            enrollment_number = record.enrollment.enrollment_number if record.enrollment else 'N/A'
            
            writer.writerow([
                enrollment_number,
                learner_name,
                record.sales_person.get_full_name() if record.sales_person else 'N/A',
                record.campus.name if record.campus else 'N/A',
                record.enrollment_date,
                record.get_funding_type_display(),
                'Yes' if record.documents_uploaded_complete else 'No',
                'Yes' if record.documents_quality_approved else 'No',
                'Yes' if record.proof_of_payment_received else 'No',
                'Yes' if record.commission_eligible else 'No'
            ])
        
        return response


# =============================================================================
# LEAD SALES ASSIGNMENT API
# =============================================================================

class LeadSalesAssignmentView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """API for managing lead sales assignments"""
    
    def get(self, request, lead_id):
        """Get current sales assignments for a lead"""
        from .models import Lead, LeadSalesAssignment
        
        lead = get_object_or_404(Lead, pk=lead_id)
        assignments = LeadSalesAssignment.objects.filter(
            lead=lead,
            is_active=True
        ).select_related('sales_person')
        
        return JsonResponse({
            'assignments': [{
                'id': a.pk,
                'sales_person_id': a.sales_person.pk,
                'sales_person_name': a.sales_person.get_full_name(),
                'is_primary': a.is_primary,
                'assigned_date': a.assigned_date.isoformat()
            } for a in assignments]
        })
    
    def post(self, request, lead_id):
        """Add or update sales assignment"""
        from .models import Lead, LeadSalesAssignment
        from core.models import User
        import json
        
        try:
            data = json.loads(request.body)
            lead = get_object_or_404(Lead, pk=lead_id)
            sales_person_id = data.get('sales_person_id')
            is_primary = data.get('is_primary', False)
            
            sales_person = get_object_or_404(User, pk=sales_person_id)
            
            assignment, created = LeadSalesAssignment.objects.update_or_create(
                lead=lead,
                sales_person=sales_person,
                defaults={
                    'is_primary': is_primary,
                    'assigned_by': request.user,
                    'is_active': True
                }
            )
            
            action = 'assigned' if created else 'updated'
            
            return JsonResponse({
                'status': 'ok',
                'message': f'Sales person {action} successfully',
                'assignment_id': assignment.pk
            })
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def delete(self, request, lead_id):
        """Remove sales assignment"""
        from .models import Lead, LeadSalesAssignment
        import json
        
        try:
            data = json.loads(request.body)
            assignment_id = data.get('assignment_id')
            
            assignment = get_object_or_404(LeadSalesAssignment, pk=assignment_id, lead_id=lead_id)
            assignment.is_active = False
            assignment.save()
            
            return JsonResponse({
                'status': 'ok',
                'message': 'Assignment removed'
            })
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# LEAD PIPELINE ASSIGNMENT API
# =============================================================================

class LeadPipelineAssignmentView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """API for assigning leads to pipelines"""
    
    def post(self, request, lead_id):
        """Assign lead to a pipeline"""
        from .models import Lead, Pipeline, PipelineStage
        import json
        
        try:
            data = json.loads(request.body)
            lead = get_object_or_404(Lead, pk=lead_id)
            pipeline_id = data.get('pipeline_id')
            
            pipeline = get_object_or_404(Pipeline, pk=pipeline_id)
            
            # Get entry stage for the pipeline
            entry_stage = pipeline.stages.filter(is_entry_stage=True).first()
            if not entry_stage:
                entry_stage = pipeline.stages.order_by('order').first()
            
            # Assign lead to pipeline
            lead.pipeline = pipeline
            if entry_stage:
                lead.current_stage = entry_stage
                lead.stage_entered_at = timezone.now()
            lead.save()
            
            # Log activity
            LeadActivity.objects.create(
                lead=lead,
                activity_type='STAGE_CHANGE',
                description=f'Assigned to pipeline: {pipeline.name}',
                created_by=request.user
            )
            
            return JsonResponse({
                'status': 'ok',
                'message': f'Lead assigned to {pipeline.name}',
                'pipeline': {
                    'id': pipeline.pk,
                    'name': pipeline.name
                },
                'stage': {
                    'id': entry_stage.pk if entry_stage else None,
                    'name': entry_stage.name if entry_stage else None
                }
            })
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

