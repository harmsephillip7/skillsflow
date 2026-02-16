"""
Custom Admin Views with Unified Tailwind Theme
Replaces Django's default admin interface
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Count, Q
from django.http import JsonResponse
from django.forms import modelform_factory
from django import forms
from django.utils import timezone

# Import all models
from core.models import User
from core.project_templates import ProjectTemplateSet, ProjectTaskTemplate
from learners.models import Learner, Document, SETA, Employer, LearnerEmployment, Address
from academics.models import Qualification, Module, UnitStandard, Enrollment, EnrollmentStatusHistory, QualificationPricing
from corporate.models import CorporateClient, CorporateContact, CorporateEmployee, GrantProject
from logistics.models import Cohort, Venue, ScheduleSession, Attendance
from assessments.models import AssessmentActivity, AssessmentResult, PoESubmission
from finance.models import Invoice, Payment, Quote
from tenants.models import Campus, Brand
from intakes.models import Contract, LearnerContractEnrollment


class StaffRequiredMixin(UserPassesTestMixin):
    """Require staff or superuser status"""
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


# =====================================================
# ADMIN DASHBOARD
# =====================================================

class AdminDashboardView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    """Main admin dashboard with all model sections"""
    template_name = 'admin/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Model sections for navigation
        context['sections'] = [
            {
                'title': 'People',
                'icon': 'users',
                'color': 'blue',
                'models': [
                    {'name': 'Users', 'url': 'admin:user_list', 'count': User.objects.count(), 'icon': 'user'},
                    {'name': 'Learners', 'url': 'admin:learner_list', 'count': Learner.objects.count(), 'icon': 'graduation-cap'},
                    {'name': 'Employers', 'url': 'admin:employer_list', 'count': Employer.objects.count(), 'icon': 'industry'},
                ]
            },
            {
                'title': 'Academics',
                'icon': 'book',
                'color': 'green',
                'models': [
                    {'name': 'Qualifications', 'url': 'admin:qualification_list', 'count': Qualification.objects.count(), 'icon': 'certificate'},
                    {'name': 'Modules', 'url': 'admin:module_list', 'count': Module.objects.count(), 'icon': 'puzzle-piece'},
                    {'name': 'Enrollments', 'url': 'admin:enrollment_list', 'count': Enrollment.objects.count(), 'icon': 'clipboard-list'},
                    {'name': 'Unit Standards', 'url': 'admin:unitstandard_list', 'count': UnitStandard.objects.count(), 'icon': 'list-check'},
                ]
            },
            {
                'title': 'Assessments',
                'icon': 'tasks',
                'color': 'purple',
                'models': [
                    {'name': 'Activities', 'url': 'admin:assessmentactivity_list', 'count': AssessmentActivity.objects.count(), 'icon': 'tasks'},
                    {'name': 'Results', 'url': 'admin:assessmentresult_list', 'count': AssessmentResult.objects.count(), 'icon': 'check-circle'},
                    {'name': 'PoE Submissions', 'url': 'admin:poesubmission_list', 'count': PoESubmission.objects.count(), 'icon': 'folder-open'},
                ]
            },
            {
                'title': 'Corporate',
                'icon': 'building',
                'color': 'indigo',
                'models': [
                    {'name': 'Contracts', 'url': 'admin:contract_list', 'count': Contract.objects.count(), 'icon': 'file-contract'},
                    {'name': 'Clients', 'url': 'admin:corporateclient_list', 'count': CorporateClient.objects.count(), 'icon': 'building'},
                    {'name': 'Contacts', 'url': 'admin:corporatecontact_list', 'count': CorporateContact.objects.count(), 'icon': 'address-book'},
                    {'name': 'Grant Projects', 'url': 'admin:grantproject_list', 'count': GrantProject.objects.count(), 'icon': 'hand-holding-usd'},
                ]
            },
            {
                'title': 'Logistics',
                'icon': 'truck',
                'color': 'yellow',
                'models': [
                    {'name': 'Cohorts', 'url': 'admin:cohort_list', 'count': Cohort.objects.count(), 'icon': 'layer-group'},
                    {'name': 'Venues', 'url': 'admin:venue_list', 'count': Venue.objects.count(), 'icon': 'map-marker-alt'},
                    {'name': 'Sessions', 'url': 'admin:schedulesession_list', 'count': ScheduleSession.objects.count(), 'icon': 'calendar'},
                ]
            },
            {
                'title': 'Finance',
                'icon': 'dollar-sign',
                'color': 'emerald',
                'models': [
                    {'name': 'Invoices', 'url': 'admin:invoice_list', 'count': Invoice.objects.count(), 'icon': 'file-invoice-dollar'},
                    {'name': 'Payments', 'url': 'admin:payment_list', 'count': Payment.objects.count(), 'icon': 'money-bill'},
                    {'name': 'Quotes', 'url': 'admin:quote_list', 'count': Quote.objects.count(), 'icon': 'file-invoice'},
                ]
            },
            {
                'title': 'Reference Data',
                'icon': 'database',
                'color': 'gray',
                'models': [
                    {'name': 'SETAs', 'url': 'admin:seta_list', 'count': SETA.objects.count(), 'icon': 'landmark'},
                    {'name': 'Employers', 'url': 'admin:employer_list', 'count': Employer.objects.count(), 'icon': 'industry'},
                ]
            },
            {
                'title': 'Human Resources',
                'icon': 'users-cog',
                'color': 'rose',
                'models': [
                    {'name': 'Departments', 'url': 'hr_admin:department_list', 'count': self._get_hr_count('Department'), 'icon': 'sitemap'},
                    {'name': 'Positions', 'url': 'hr_admin:position_list', 'count': self._get_hr_count('Position'), 'icon': 'id-badge'},
                    {'name': 'Staff', 'url': 'hr_admin:staff_list', 'count': self._get_hr_count('StaffProfile'), 'icon': 'user-tie'},
                ]
            },
            {
                'title': 'Configuration',
                'icon': 'cogs',
                'color': 'orange',
                'models': [
                    {'name': 'Brands', 'url': 'admin:brand_list', 'count': Brand.objects.count(), 'icon': 'building-columns'},
                    {'name': 'Campuses', 'url': 'admin:campus_list', 'count': Campus.objects.count(), 'icon': 'map-pin'},
                    {'name': 'Template Sets', 'url': 'admin:templateset_list', 'count': ProjectTemplateSet.objects.filter(is_active=True).count(), 'icon': 'template'},
                    {'name': 'Task Templates', 'url': 'admin:templateset_list', 'count': ProjectTaskTemplate.objects.filter(is_active=True).count(), 'icon': 'tasks'},
                ]
            },
            {
                'title': 'System',
                'icon': 'cog',
                'color': 'slate',
                'models': [
                    {'name': 'Process Flows', 'url': 'workflows:processflow_list', 'count': '-', 'icon': 'workflow'},
                    {'name': 'Transition Log', 'url': 'workflows:transition_log', 'count': '-', 'icon': 'history'},
                ]
            },
        ]
        
        # Quick stats
        context['stats'] = {
            'active_learners': Learner.objects.count(),
            'active_enrollments': Enrollment.objects.filter(status='ACTIVE').count(),
            'pending_assessments': AssessmentResult.objects.filter(status='PENDING_MOD').count(),
            'upcoming_sessions': ScheduleSession.objects.filter(is_cancelled=False, date__gte=timezone.now().date()).count(),
        }
        
        return context
    
    def _get_hr_count(self, model_name):
        """Get count for HR models safely"""
        try:
            from hr.models import Department, Position, StaffProfile
            models_map = {
                'Department': Department,
                'Position': Position,
                'StaffProfile': StaffProfile,
            }
            model = models_map.get(model_name)
            if model:
                return model.objects.filter(is_deleted=False).count()
            return 0
        except Exception:
            return 0


# =====================================================
# GENERIC MODEL VIEWS
# =====================================================

class GenericModelListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    """Generic list view for any model"""
    template_name = 'admin/model_list.html'
    context_object_name = 'objects'
    paginate_by = 25
    
    # Override these in subclasses
    model = None
    model_name = ''
    model_name_plural = ''
    list_display = []
    search_fields = []
    filter_fields = []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Search
        search = self.request.GET.get('search', '')
        if search and self.search_fields:
            q_objects = Q()
            for field in self.search_fields:
                q_objects |= Q(**{f'{field}__icontains': search})
            queryset = queryset.filter(q_objects)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = self.model_name or self.model._meta.verbose_name
        context['model_name_plural'] = self.model_name_plural or self.model._meta.verbose_name_plural
        context['list_display'] = self.list_display
        context['search'] = self.request.GET.get('search', '')
        context['add_url'] = f'admin:{self.model._meta.model_name}_create'
        context['detail_url_name'] = f'admin:{self.model._meta.model_name}_detail'
        return context


class GenericModelDetailView(LoginRequiredMixin, StaffRequiredMixin, DetailView):
    """Generic detail view for any model"""
    template_name = 'admin/model_detail.html'
    context_object_name = 'object'
    
    model = None
    model_name = ''
    detail_fields = []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = self.model_name or self.model._meta.verbose_name
        context['detail_fields'] = self.detail_fields
        context['edit_url'] = f'admin:{self.model._meta.model_name}_edit'
        context['delete_url'] = f'admin:{self.model._meta.model_name}_delete'
        context['list_url'] = f'admin:{self.model._meta.model_name}_list'
        return context


class GenericModelCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Generic create view for any model"""
    template_name = 'admin/model_form.html'
    
    model = None
    model_name = ''
    form_class = None
    fields = None
    
    def get_form_class(self):
        if self.form_class:
            return self.form_class
        return modelform_factory(self.model, fields=self.fields or '__all__')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = self.model_name or self.model._meta.verbose_name
        context['action'] = 'Create'
        context['list_url'] = f'admin:{self.model._meta.model_name}_list'
        return context
    
    def get_success_url(self):
        messages.success(self.request, f'{self.model_name or self.model._meta.verbose_name} created successfully.')
        return reverse(f'admin:{self.model._meta.model_name}_list')


class GenericModelUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Generic update view for any model"""
    template_name = 'admin/model_form.html'
    
    model = None
    model_name = ''
    form_class = None
    fields = None
    
    def get_form_class(self):
        if self.form_class:
            return self.form_class
        return modelform_factory(self.model, fields=self.fields or '__all__')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = self.model_name or self.model._meta.verbose_name
        context['action'] = 'Edit'
        context['list_url'] = f'admin:{self.model._meta.model_name}_list'
        return context
    
    def get_success_url(self):
        messages.success(self.request, f'{self.model_name or self.model._meta.verbose_name} updated successfully.')
        return reverse(f'admin:{self.model._meta.model_name}_detail', kwargs={'pk': self.object.pk})


class GenericModelDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    """Generic delete view for any model"""
    template_name = 'admin/model_delete.html'
    
    model = None
    model_name = ''
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = self.model_name or self.model._meta.verbose_name
        context['list_url'] = f'admin:{self.model._meta.model_name}_list'
        return context
    
    def get_success_url(self):
        messages.success(self.request, f'{self.model_name or self.model._meta.verbose_name} deleted successfully.')
        return reverse(f'admin:{self.model._meta.model_name}_list')


# =====================================================
# USER VIEWS
# =====================================================

class UserListView(GenericModelListView):
    model = User
    model_name = 'User'
    model_name_plural = 'Users'
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name']


class UserDetailView(GenericModelDetailView):
    model = User
    model_name = 'User'
    detail_fields = ['email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_login']


class UserCreateView(GenericModelCreateView):
    model = User
    model_name = 'User'
    fields = ['email', 'first_name', 'last_name', 'is_active', 'is_staff']


class UserUpdateView(GenericModelUpdateView):
    model = User
    model_name = 'User'
    fields = ['email', 'first_name', 'last_name', 'is_active', 'is_staff']


class UserDeleteView(GenericModelDeleteView):
    model = User
    model_name = 'User'


# =====================================================
# LEARNER VIEWS
# =====================================================

class LearnerListView(GenericModelListView):
    model = Learner
    model_name = 'Learner'
    model_name_plural = 'Learners'
    list_display = ['learner_number', 'first_name', 'last_name', 'email', 'phone_mobile', 'gender']
    search_fields = ['learner_number', 'first_name', 'last_name', 'email', 'sa_id_number']


class LearnerDetailView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    """Enhanced learner detail view with comprehensive profile information"""
    template_name = 'admin/learner_profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        learner = get_object_or_404(Learner, pk=kwargs.get('pk'))
        context['learner'] = learner
        context['model_name'] = 'Learner'
        
        # Get related data
        context['documents'] = Document.objects.filter(learner=learner).order_by('-created_at')
        context['enrollments'] = Enrollment.objects.filter(learner=learner).select_related('qualification')
        
        # Get user associated with the learner
        context['learner_user'] = learner.user if learner.user else None
        
        # Signature status
        context['has_signature'] = bool(learner.signature)
        context['signature_locked'] = learner.signature_locked
        
        # URLs for navigation
        context['edit_url'] = 'admin:learner_edit'
        context['delete_url'] = 'admin:learner_delete'
        context['list_url'] = 'admin:learner_list'
        
        return context


class LearnerProfileEditView(LoginRequiredMixin, StaffRequiredMixin, View):
    """Admin view to edit learner profile with all fields"""
    
    def get(self, request, pk):
        learner = get_object_or_404(Learner, pk=pk)
        context = {
            'learner': learner,
            'model_name': 'Learner',
            'action': 'Edit',
            'list_url': 'admin:learner_list',
            'gender_choices': Learner.GENDER_CHOICES if hasattr(Learner, 'GENDER_CHOICES') else [
                ('M', 'Male'), ('F', 'Female'), ('O', 'Other'), ('N', 'Prefer not to say')
            ],
            'population_choices': Learner.POPULATION_GROUP_CHOICES if hasattr(Learner, 'POPULATION_GROUP_CHOICES') else [],
            'citizenship_choices': Learner.CITIZENSHIP_CHOICES if hasattr(Learner, 'CITIZENSHIP_CHOICES') else [],
            'disability_choices': Learner.DISABILITY_STATUS_CHOICES if hasattr(Learner, 'DISABILITY_STATUS_CHOICES') else [],
        }
        return render(request, 'admin/learner_edit.html', context)
    
    def post(self, request, pk):
        learner = get_object_or_404(Learner, pk=pk)
        
        # Update learner fields
        learner.first_name = request.POST.get('first_name', '').strip()
        learner.last_name = request.POST.get('last_name', '').strip()
        learner.email = request.POST.get('email', '').strip()
        learner.sa_id_number = request.POST.get('sa_id_number', '').strip()
        learner.phone_mobile = request.POST.get('phone_mobile', '').strip()
        
        # Parse date
        dob = request.POST.get('date_of_birth')
        if dob:
            try:
                from datetime import datetime
                learner.date_of_birth = datetime.strptime(dob, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        learner.gender = request.POST.get('gender', '')
        learner.population_group = request.POST.get('population_group', '')
        learner.citizenship = request.POST.get('citizenship', '')
        learner.disability_status = request.POST.get('disability_status', '')
        learner.highest_qualification = request.POST.get('highest_qualification', '')
        
        # Address fields
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
        
        # Update associated user if exists
        if learner.user:
            learner.user.first_name = learner.first_name
            learner.user.last_name = learner.last_name
            learner.user.email = learner.email
            learner.user.save()
        
        messages.success(request, f'Learner profile for {learner.get_full_name()} updated successfully.')
        return redirect('admin:learner_detail', pk=pk)


class LearnerSignatureUnlockView(LoginRequiredMixin, StaffRequiredMixin, View):
    """Admin view to unlock a learner's signature"""
    
    def post(self, request, pk):
        learner = get_object_or_404(Learner, pk=pk)
        
        if not learner.signature_locked:
            messages.warning(request, 'Signature is not locked.')
            return redirect('admin:learner_detail', pk=pk)
        
        unlock_reason = request.POST.get('unlock_reason', '').strip()
        if not unlock_reason:
            messages.error(request, 'Please provide a reason for unlocking the signature.')
            return redirect('admin:learner_detail', pk=pk)
        
        # Unlock the signature
        learner.signature_locked = False
        learner.save(update_fields=['signature_locked'])
        
        # Log the unlock action
        from core.models import SignatureCapture
        if learner.user:
            try:
                sig_capture = SignatureCapture.objects.get(user=learner.user)
                sig_capture.unlock(request.user, unlock_reason)
            except SignatureCapture.DoesNotExist:
                pass
        
        messages.success(request, f'Signature for {learner.get_full_name()} has been unlocked. Reason: {unlock_reason}')
        return redirect('admin:learner_detail', pk=pk)


class LearnerCreateView(GenericModelCreateView):
    model = Learner
    model_name = 'Learner'
    fields = ['learner_number', 'first_name', 'last_name', 'sa_id_number', 'email', 'phone_mobile', 'date_of_birth', 'gender', 'population_group', 'citizenship', 'disability_status', 'socio_economic_status', 'highest_qualification']


class LearnerUpdateView(GenericModelUpdateView):
    model = Learner
    model_name = 'Learner'
    fields = ['learner_number', 'first_name', 'last_name', 'sa_id_number', 'email', 'phone_mobile', 'date_of_birth', 'gender', 'population_group', 'citizenship', 'disability_status', 'socio_economic_status', 'highest_qualification']


class LearnerDeleteView(GenericModelDeleteView):
    model = Learner
    model_name = 'Learner'


# =====================================================
# QUALIFICATION VIEWS
# =====================================================

class QualificationListView(GenericModelListView):
    model = Qualification
    model_name = 'Qualification'
    model_name_plural = 'Qualifications'
    list_display = ['saqa_id', 'short_title', 'nqf_level', 'credits', 'qualification_type', 'is_active']
    search_fields = ['saqa_id', 'title', 'short_title']


class QualificationDetailView(GenericModelDetailView):
    model = Qualification
    model_name = 'Qualification'
    detail_fields = ['saqa_id', 'title', 'short_title', 'nqf_level', 'credits', 'qualification_type', 'seta', 'minimum_duration_months', 'maximum_duration_months', 'registration_start', 'registration_end', 'is_active']


class QualificationCreateView(GenericModelCreateView):
    model = Qualification
    model_name = 'Qualification'
    fields = ['saqa_id', 'title', 'short_title', 'nqf_level', 'credits', 'qualification_type', 'seta', 'minimum_duration_months', 'maximum_duration_months', 'registration_start', 'registration_end', 'last_enrollment_date', 'is_active']


class QualificationUpdateView(GenericModelUpdateView):
    model = Qualification
    model_name = 'Qualification'
    fields = ['saqa_id', 'title', 'short_title', 'nqf_level', 'credits', 'qualification_type', 'seta', 'minimum_duration_months', 'maximum_duration_months', 'registration_start', 'registration_end', 'last_enrollment_date', 'is_active']


class QualificationDeleteView(GenericModelDeleteView):
    model = Qualification
    model_name = 'Qualification'


# =====================================================
# QUALIFICATION PRICING VIEWS
# =====================================================

class QualificationPricingListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    """List all pricing records for a qualification"""
    model = QualificationPricing
    template_name = 'admin/qualificationpricing_list.html'
    context_object_name = 'pricing_list'
    
    def get_queryset(self):
        qualification_id = self.kwargs.get('qualification_id')
        if qualification_id:
            return QualificationPricing.objects.filter(qualification_id=qualification_id).order_by('-academic_year', '-effective_from')
        return QualificationPricing.objects.all().select_related('qualification').order_by('-academic_year', '-effective_from')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qualification_id = self.kwargs.get('qualification_id')
        if qualification_id:
            context['qualification'] = get_object_or_404(Qualification, pk=qualification_id)
        context['model_name'] = 'Qualification Pricing'
        context['model_name_plural'] = 'Qualification Pricing'
        return context


class QualificationPricingCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Create pricing for a qualification"""
    model = QualificationPricing
    template_name = 'admin/qualificationpricing_form.html'
    fields = ['academic_year', 'effective_from', 'effective_to', 'total_price', 'registration_fee', 'tuition_fee', 'materials_fee', 'is_active', 'notes']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qualification_id = self.kwargs.get('qualification_id')
        context['qualification'] = get_object_or_404(Qualification, pk=qualification_id)
        context['model_name'] = 'Qualification Pricing'
        context['action'] = 'Add'
        return context
    
    def form_valid(self, form):
        qualification_id = self.kwargs.get('qualification_id')
        form.instance.qualification = get_object_or_404(Qualification, pk=qualification_id)
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Pricing for {form.instance.academic_year} created successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('academics:qualification_detail', kwargs={'pk': self.kwargs.get('qualification_id')})


class QualificationPricingUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Update pricing for a qualification"""
    model = QualificationPricing
    template_name = 'admin/qualificationpricing_form.html'
    fields = ['academic_year', 'effective_from', 'effective_to', 'total_price', 'registration_fee', 'tuition_fee', 'materials_fee', 'is_active', 'notes']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['qualification'] = self.object.qualification
        context['model_name'] = 'Qualification Pricing'
        context['action'] = 'Edit'
        return context
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Pricing for {form.instance.academic_year} updated successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('academics:qualification_detail', kwargs={'pk': self.object.qualification_id})


class QualificationPricingDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    """Delete pricing for a qualification"""
    model = QualificationPricing
    template_name = 'admin/qualificationpricing_confirm_delete.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['qualification'] = self.object.qualification
        context['model_name'] = 'Qualification Pricing'
        return context
    
    def get_success_url(self):
        messages.success(self.request, 'Pricing deleted successfully.')
        return reverse('academics:qualification_detail', kwargs={'pk': self.object.qualification_id})


# =====================================================
# MODULE VIEWS
# =====================================================

class ModuleListView(GenericModelListView):
    model = Module
    model_name = 'Module'
    model_name_plural = 'Modules'
    list_display = ['code', 'title', 'module_type', 'credits', 'is_compulsory', 'is_active']
    search_fields = ['code', 'title']


class ModuleDetailView(GenericModelDetailView):
    model = Module
    model_name = 'Module'
    detail_fields = ['code', 'title', 'description', 'qualification', 'module_type', 'credits', 'notional_hours', 'sequence_order', 'is_compulsory', 'is_active']


class ModuleCreateView(GenericModelCreateView):
    model = Module
    model_name = 'Module'
    fields = ['code', 'title', 'description', 'qualification', 'module_type', 'credits', 'notional_hours', 'sequence_order', 'is_compulsory', 'is_active']


class ModuleUpdateView(GenericModelUpdateView):
    model = Module
    model_name = 'Module'
    fields = ['code', 'title', 'description', 'qualification', 'module_type', 'credits', 'notional_hours', 'sequence_order', 'is_compulsory', 'is_active']


class ModuleDeleteView(GenericModelDeleteView):
    model = Module
    model_name = 'Module'


# =====================================================
# UNIT STANDARD VIEWS
# =====================================================

class UnitStandardListView(GenericModelListView):
    model = UnitStandard
    model_name = 'Unit Standard'
    model_name_plural = 'Unit Standards'
    list_display = ['saqa_id', 'title', 'nqf_level', 'credits', 'is_active']
    search_fields = ['saqa_id', 'title']


class UnitStandardDetailView(GenericModelDetailView):
    model = UnitStandard
    model_name = 'Unit Standard'
    detail_fields = ['saqa_id', 'title', 'nqf_level', 'credits', 'is_active']


class UnitStandardCreateView(GenericModelCreateView):
    model = UnitStandard
    model_name = 'Unit Standard'
    fields = ['saqa_id', 'title', 'nqf_level', 'credits', 'is_active']


class UnitStandardUpdateView(GenericModelUpdateView):
    model = UnitStandard
    model_name = 'Unit Standard'
    fields = ['saqa_id', 'title', 'nqf_level', 'credits', 'is_active']


class UnitStandardDeleteView(GenericModelDeleteView):
    model = UnitStandard
    model_name = 'Unit Standard'


# =====================================================
# ENROLLMENT VIEWS
# =====================================================

class EnrollmentListView(GenericModelListView):
    model = Enrollment
    model_name = 'Enrollment'
    model_name_plural = 'Enrollments'
    list_display = ['enrollment_number', 'learner', 'qualification', 'status', 'funding_type', 'start_date']
    search_fields = ['enrollment_number', 'learner__first_name', 'learner__last_name', 'qualification__title']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Navigate directly to enhanced edit view instead of detail view
        context['detail_url_name'] = 'admin:enrollment_edit'
        return context


class EnrollmentDetailView(GenericModelDetailView):
    model = Enrollment
    model_name = 'Enrollment'
    detail_fields = ['enrollment_number', 'learner', 'qualification', 'cohort', 'status', 'funding_type', 'application_date', 'enrollment_date', 'start_date', 'expected_completion', 'actual_completion', 'agreement_signed', 'nlrd_submitted', 'certificate_number']


class EnrollmentCreateView(GenericModelCreateView):
    model = Enrollment
    model_name = 'Enrollment'
    fields = ['enrollment_number', 'learner', 'qualification', 'cohort', 'status', 'funding_type', 'funding_source', 'application_date', 'enrollment_date', 'start_date', 'expected_completion']


class EnrollmentUpdateView(GenericModelUpdateView):
    model = Enrollment
    model_name = 'Enrollment'
    fields = ['enrollment_number', 'learner', 'qualification', 'cohort', 'status', 'funding_type', 'funding_source', 'application_date', 'enrollment_date', 'start_date', 'expected_completion', 'actual_completion', 'agreement_signed', 'nlrd_submitted', 'certificate_number']


class EnhancedEnrollmentEditView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """
    Enhanced enrollment edit view with:
    - Tabbed interface for organized form sections
    - Status change validation using ProcessFlow
    - Visual status history timeline
    - Campus filtering
    """
    model = Enrollment
    template_name = 'admin/enrollment_edit.html'
    
    def get_form_class(self):
        # Create a form with all fields
        return modelform_factory(
            Enrollment,
            fields=[
                'enrollment_number', 'learner', 'qualification', 'cohort',
                'status', 'status_reason',
                'funding_type', 'funding_source', 'funding_reference',
                'application_date', 'enrollment_date', 'start_date', 
                'expected_completion', 'actual_completion',
                'agreement_signed', 'agreement_date',
                'nlrd_submitted', 'nlrd_submission_date', 'nlrd_reference',
                'certificate_number', 'certificate_date',
            ],
            widgets={
                'learner': forms.Select(attrs={'class': 'select2'}),
                'qualification': forms.Select(attrs={'class': 'select2'}),
                'cohort': forms.Select(attrs={'class': 'select2'}),
                'status': forms.Select(attrs={'id': 'id_status', 'class': 'status-select'}),
                'status_reason': forms.Textarea(attrs={'rows': 3}),
                'application_date': forms.DateInput(attrs={'type': 'date'}),
                'enrollment_date': forms.DateInput(attrs={'type': 'date'}),
                'start_date': forms.DateInput(attrs={'type': 'date'}),
                'expected_completion': forms.DateInput(attrs={'type': 'date'}),
                'actual_completion': forms.DateInput(attrs={'type': 'date'}),
                'agreement_date': forms.DateInput(attrs={'type': 'date'}),
                'nlrd_submission_date': forms.DateInput(attrs={'type': 'date'}),
                'certificate_date': forms.DateInput(attrs={'type': 'date'}),
            }
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enrollment = self.object
        
        context['page_title'] = f'Edit Enrollment: {enrollment.enrollment_number}'
        context['model_name'] = 'Enrollment'
        context['list_url'] = 'admin:enrollment_list'
        
        # Get allowed transitions from TransitionService
        from workflows.services import TransitionService
        allowed_transitions = TransitionService.get_allowed_transitions(
            'enrollment', 
            enrollment.status
        )
        context['allowed_transitions'] = allowed_transitions
        context['current_status'] = enrollment.status
        
        # Get stage info for display
        stage_info = TransitionService.get_stage_info('enrollment', enrollment.status)
        context['stage_info'] = stage_info
        
        # Get status history
        context['status_history'] = EnrollmentStatusHistory.objects.filter(
            enrollment=enrollment
        ).order_by('-changed_at')[:10]
        
        # All status choices for reference
        context['all_statuses'] = Enrollment.STATUS_CHOICES
        context['funding_types'] = Enrollment.FUNDING_TYPES
        
        return context
    
    def form_valid(self, form):
        enrollment = self.object
        old_status = Enrollment.objects.get(pk=enrollment.pk).status
        new_status = form.cleaned_data.get('status')
        
        # Check if status is changing
        if old_status != new_status:
            from workflows.services import TransitionService
            
            # Get client IP
            x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = self.request.META.get('REMOTE_ADDR')
            
            # Validate and log the transition
            is_valid, error_message, transition = TransitionService.validate_and_log_transition(
                entity_type='enrollment',
                entity_id=enrollment.pk,
                instance=form.instance,
                from_stage_code=old_status,
                to_stage_code=new_status,
                user=self.request.user,
                reason=form.cleaned_data.get('status_reason', ''),
                ip_address=ip
            )
            
            if not is_valid:
                messages.error(self.request, f'Status change blocked: {error_message}')
                return self.form_invalid(form)
            
            # If transition requires reason and none provided, redirect back
            if transition and (transition.requires_reason or 
                             (transition.to_stage and transition.to_stage.requires_reason_on_entry)):
                if not form.cleaned_data.get('status_reason', '').strip():
                    messages.warning(self.request, 'Please provide a reason for this status change.')
                    return self.form_invalid(form)
        
        response = super().form_valid(form)
        messages.success(self.request, f'Enrollment {enrollment.enrollment_number} updated successfully.')
        return response
    
    def get_success_url(self):
        return reverse('admin:enrollment_detail', kwargs={'pk': self.object.pk})


class EnrollmentDeleteView(GenericModelDeleteView):
    model = Enrollment
    model_name = 'Enrollment'


# =====================================================
# CORPORATE CLIENT VIEWS
# =====================================================

class CorporateClientListView(GenericModelListView):
    model = CorporateClient
    model_name = 'Corporate Client'
    model_name_plural = 'Corporate Clients'
    list_display = ['company_name', 'email', 'phone', 'status', 'industry']
    search_fields = ['company_name', 'trading_name', 'email']


class CorporateClientDetailView(GenericModelDetailView):
    model = CorporateClient
    model_name = 'Corporate Client'
    detail_fields = ['company_name', 'trading_name', 'registration_number', 'vat_number', 'phone', 'email', 'website', 'physical_address', 'industry', 'employee_count', 'status', 'account_manager']


class CorporateClientCreateView(GenericModelCreateView):
    model = CorporateClient
    model_name = 'Corporate Client'
    fields = ['company_name', 'trading_name', 'registration_number', 'vat_number', 'phone', 'email', 'website', 'physical_address', 'postal_address', 'industry', 'sic_code', 'employee_count', 'annual_revenue', 'status', 'account_manager']


class CorporateClientUpdateView(GenericModelUpdateView):
    model = CorporateClient
    model_name = 'Corporate Client'
    fields = ['company_name', 'trading_name', 'registration_number', 'vat_number', 'phone', 'email', 'website', 'physical_address', 'postal_address', 'industry', 'sic_code', 'employee_count', 'annual_revenue', 'status', 'account_manager']


class CorporateClientDeleteView(GenericModelDeleteView):
    model = CorporateClient
    model_name = 'Corporate Client'


# =====================================================
# CORPORATE CONTACT VIEWS
# =====================================================

class CorporateContactListView(GenericModelListView):
    model = CorporateContact
    model_name = 'Corporate Contact'
    model_name_plural = 'Corporate Contacts'
    list_display = ['first_name', 'last_name', 'client', 'role', 'email', 'phone', 'is_primary']
    search_fields = ['first_name', 'last_name', 'email', 'client__company_name']


class CorporateContactDetailView(GenericModelDetailView):
    model = CorporateContact
    model_name = 'Corporate Contact'
    detail_fields = ['first_name', 'last_name', 'client', 'job_title', 'role', 'email', 'phone', 'mobile', 'is_primary', 'is_active']


class CorporateContactCreateView(GenericModelCreateView):
    model = CorporateContact
    model_name = 'Corporate Contact'
    fields = ['client', 'first_name', 'last_name', 'job_title', 'role', 'email', 'phone', 'mobile', 'is_primary', 'is_active']


class CorporateContactUpdateView(GenericModelUpdateView):
    model = CorporateContact
    model_name = 'Corporate Contact'
    fields = ['client', 'first_name', 'last_name', 'job_title', 'role', 'email', 'phone', 'mobile', 'is_primary', 'is_active']


class CorporateContactDeleteView(GenericModelDeleteView):
    model = CorporateContact
    model_name = 'Corporate Contact'


# =====================================================
# GRANT PROJECT VIEWS
# =====================================================

class GrantProjectListView(GenericModelListView):
    model = GrantProject
    model_name = 'Grant Project'
    model_name_plural = 'Grant Projects'
    list_display = ['project_name', 'client', 'seta', 'status', 'approved_amount', 'start_date']
    search_fields = ['project_name', 'project_number', 'client__company_name']


class GrantProjectDetailView(GenericModelDetailView):
    model = GrantProject
    model_name = 'Grant Project'
    detail_fields = ['project_name', 'project_number', 'client', 'seta', 'status', 'application_date', 'approval_date', 'start_date', 'end_date', 'approved_amount', 'claimed_amount', 'received_amount', 'target_learners', 'enrolled_learners', 'completed_learners', 'project_manager']


class GrantProjectCreateView(GenericModelCreateView):
    model = GrantProject
    model_name = 'Grant Project'
    fields = ['project_name', 'project_number', 'client', 'seta', 'status', 'application_date', 'approval_date', 'start_date', 'end_date', 'approved_amount', 'target_learners', 'project_manager']


class GrantProjectUpdateView(GenericModelUpdateView):
    model = GrantProject
    model_name = 'Grant Project'
    fields = ['project_name', 'project_number', 'client', 'seta', 'status', 'application_date', 'approval_date', 'start_date', 'end_date', 'approved_amount', 'claimed_amount', 'received_amount', 'target_learners', 'enrolled_learners', 'completed_learners', 'project_manager']


class GrantProjectDeleteView(GenericModelDeleteView):
    model = GrantProject
    model_name = 'Grant Project'


# =====================================================
# COHORT VIEWS
# =====================================================

class CohortListView(GenericModelListView):
    model = Cohort
    model_name = 'Cohort'
    model_name_plural = 'Cohorts'
    list_display = ['code', 'name', 'qualification', 'start_date', 'end_date', 'status', 'max_capacity']
    search_fields = ['code', 'name', 'qualification__title']


class CohortDetailView(GenericModelDetailView):
    model = Cohort
    model_name = 'Cohort'
    detail_fields = ['code', 'name', 'qualification', 'start_date', 'end_date', 'status', 'max_capacity', 'current_count', 'facilitator', 'description']


class CohortCreateView(GenericModelCreateView):
    model = Cohort
    model_name = 'Cohort'
    fields = ['code', 'name', 'qualification', 'start_date', 'end_date', 'status', 'max_capacity', 'facilitator', 'description']


class CohortUpdateView(GenericModelUpdateView):
    model = Cohort
    model_name = 'Cohort'
    fields = ['code', 'name', 'qualification', 'start_date', 'end_date', 'status', 'max_capacity', 'facilitator', 'description']


class CohortDeleteView(GenericModelDeleteView):
    model = Cohort
    model_name = 'Cohort'


# =====================================================
# VENUE VIEWS
# =====================================================

class VenueListView(GenericModelListView):
    model = Venue
    model_name = 'Venue'
    model_name_plural = 'Venues'
    list_display = ['name', 'campus', 'venue_type', 'capacity', 'is_active']
    search_fields = ['name', 'code', 'campus__name']


class VenueDetailView(GenericModelDetailView):
    model = Venue
    model_name = 'Venue'
    detail_fields = ['name', 'code', 'campus', 'venue_type', 'capacity', 'equipment', 'meeting_url', 'is_active']


class VenueCreateView(GenericModelCreateView):
    model = Venue
    model_name = 'Venue'
    fields = ['campus', 'name', 'code', 'venue_type', 'capacity', 'equipment', 'meeting_url', 'is_active']


class VenueUpdateView(GenericModelUpdateView):
    model = Venue
    model_name = 'Venue'
    fields = ['campus', 'name', 'code', 'venue_type', 'capacity', 'equipment', 'meeting_url', 'is_active']


class VenueDeleteView(GenericModelDeleteView):
    model = Venue
    model_name = 'Venue'


# =====================================================
# SCHEDULE SESSION VIEWS (renamed from TrainingSession)
# =====================================================

class ScheduleSessionListView(GenericModelListView):
    model = ScheduleSession
    model_name = 'Schedule Session'
    model_name_plural = 'Schedule Sessions'
    list_display = ['cohort', 'module', 'venue', 'session_date', 'start_time', 'end_time', 'session_type']
    search_fields = ['cohort__name', 'venue__name', 'module__title']


class ScheduleSessionDetailView(GenericModelDetailView):
    model = ScheduleSession
    model_name = 'Schedule Session'
    detail_fields = ['cohort', 'module', 'venue', 'session_date', 'start_time', 'end_time', 'session_type', 'facilitator', 'notes']


class ScheduleSessionCreateView(GenericModelCreateView):
    model = ScheduleSession
    model_name = 'Schedule Session'
    fields = ['cohort', 'module', 'venue', 'session_date', 'start_time', 'end_time', 'session_type', 'facilitator', 'notes']


class ScheduleSessionUpdateView(GenericModelUpdateView):
    model = ScheduleSession
    model_name = 'Schedule Session'
    fields = ['cohort', 'module', 'venue', 'session_date', 'start_time', 'end_time', 'session_type', 'facilitator', 'notes']


class ScheduleSessionDeleteView(GenericModelDeleteView):
    model = ScheduleSession
    model_name = 'Schedule Session'


# =====================================================
# ASSESSMENT ACTIVITY VIEWS
# =====================================================

class AssessmentActivityListView(GenericModelListView):
    model = AssessmentActivity
    model_name = 'Assessment Activity'
    model_name_plural = 'Assessment Activities'
    list_display = ['code', 'title', 'module', 'activity_type', 'weight', 'is_active']
    search_fields = ['code', 'title', 'module__title', 'description']


class AssessmentActivityDetailView(GenericModelDetailView):
    model = AssessmentActivity
    model_name = 'Assessment Activity'
    detail_fields = ['code', 'title', 'module', 'activity_type', 'description', 'weight', 'max_attempts', 'is_external', 'sequence_order', 'is_active']


class AssessmentActivityCreateView(GenericModelCreateView):
    model = AssessmentActivity
    model_name = 'Assessment Activity'
    fields = ['code', 'title', 'module', 'activity_type', 'description', 'weight', 'max_attempts', 'is_external', 'aqp', 'sequence_order', 'is_active']


class AssessmentActivityUpdateView(GenericModelUpdateView):
    model = AssessmentActivity
    model_name = 'Assessment Activity'
    fields = ['code', 'title', 'module', 'activity_type', 'description', 'weight', 'max_attempts', 'is_external', 'aqp', 'sequence_order', 'is_active']


class AssessmentActivityDeleteView(GenericModelDeleteView):
    model = AssessmentActivity
    model_name = 'Assessment Activity'


# =====================================================
# ASSESSMENT RESULT VIEWS
# =====================================================

class AssessmentResultListView(GenericModelListView):
    model = AssessmentResult
    model_name = 'Assessment Result'
    model_name_plural = 'Assessment Results'
    list_display = ['enrollment', 'activity', 'result', 'percentage_score', 'status', 'assessment_date']
    search_fields = ['enrollment__enrollment_number', 'activity__title']


class AssessmentResultDetailView(GenericModelDetailView):
    model = AssessmentResult
    model_name = 'Assessment Result'
    detail_fields = ['enrollment', 'activity', 'attempt_number', 'assessor', 'result', 'percentage_score', 'assessment_date', 'feedback', 'status', 'is_flagged_moderation', 'locked']


class AssessmentResultCreateView(GenericModelCreateView):
    model = AssessmentResult
    model_name = 'Assessment Result'
    fields = ['enrollment', 'activity', 'attempt_number', 'assessor', 'result', 'percentage_score', 'assessment_date', 'feedback', 'status']


class AssessmentResultUpdateView(GenericModelUpdateView):
    model = AssessmentResult
    model_name = 'Assessment Result'
    fields = ['enrollment', 'activity', 'attempt_number', 'assessor', 'result', 'percentage_score', 'assessment_date', 'feedback', 'status', 'is_flagged_moderation']


class AssessmentResultDeleteView(GenericModelDeleteView):
    model = AssessmentResult
    model_name = 'Assessment Result'


# =====================================================
# POE SUBMISSION VIEWS
# =====================================================

class PoESubmissionListView(GenericModelListView):
    model = PoESubmission
    model_name = 'PoE Submission'
    model_name_plural = 'PoE Submissions'
    list_display = ['enrollment', 'module', 'status', 'submission_date']
    search_fields = ['enrollment__enrollment_number', 'module__title']


class PoESubmissionDetailView(GenericModelDetailView):
    model = PoESubmission
    model_name = 'PoE Submission'
    detail_fields = ['enrollment', 'module', 'submission_date', 'description', 'status', 'reviewed_by', 'reviewed_at', 'review_comments']


class PoESubmissionCreateView(GenericModelCreateView):
    model = PoESubmission
    model_name = 'PoE Submission'
    fields = ['enrollment', 'module', 'submission_date', 'description', 'status']


class PoESubmissionUpdateView(GenericModelUpdateView):
    model = PoESubmission
    model_name = 'PoE Submission'
    fields = ['enrollment', 'module', 'submission_date', 'description', 'status', 'reviewed_by', 'reviewed_at', 'review_comments']


class PoESubmissionDeleteView(GenericModelDeleteView):
    model = PoESubmission
    model_name = 'PoE Submission'


# =====================================================
# INVOICE VIEWS
# =====================================================

class InvoiceListView(GenericModelListView):
    model = Invoice
    model_name = 'Invoice'
    model_name_plural = 'Invoices'
    list_display = ['invoice_number', 'invoice_type', 'learner', 'corporate_client', 'total', 'status', 'invoice_date', 'due_date']
    search_fields = ['invoice_number', 'corporate_client__company_name', 'learner__first_name', 'learner__last_name']


class InvoiceDetailView(GenericModelDetailView):
    model = Invoice
    model_name = 'Invoice'
    detail_fields = ['invoice_number', 'invoice_type', 'learner', 'corporate_client', 'enrollment', 'billing_name', 'billing_email', 'invoice_date', 'due_date', 'status', 'subtotal', 'vat_amount', 'discount_amount', 'total', 'amount_paid', 'notes']


class InvoiceCreateView(GenericModelCreateView):
    model = Invoice
    model_name = 'Invoice'
    fields = ['invoice_number', 'invoice_type', 'learner', 'corporate_client', 'enrollment', 'billing_name', 'billing_address', 'billing_vat_number', 'billing_email', 'invoice_date', 'due_date', 'status', 'subtotal', 'vat_amount', 'discount_amount', 'total', 'notes']


class InvoiceUpdateView(GenericModelUpdateView):
    model = Invoice
    model_name = 'Invoice'
    fields = ['invoice_number', 'invoice_type', 'learner', 'corporate_client', 'enrollment', 'billing_name', 'billing_address', 'billing_vat_number', 'billing_email', 'invoice_date', 'due_date', 'status', 'subtotal', 'vat_amount', 'discount_amount', 'total', 'amount_paid', 'notes']


class InvoiceDeleteView(GenericModelDeleteView):
    model = Invoice
    model_name = 'Invoice'


# =====================================================
# PAYMENT VIEWS
# =====================================================

class PaymentListView(GenericModelListView):
    model = Payment
    model_name = 'Payment'
    model_name_plural = 'Payments'
    list_display = ['payment_reference', 'invoice', 'amount', 'payment_method', 'payment_date', 'status']
    search_fields = ['payment_reference', 'invoice__invoice_number', 'external_reference']


class PaymentDetailView(GenericModelDetailView):
    model = Payment
    model_name = 'Payment'
    detail_fields = ['payment_reference', 'invoice', 'payment_date', 'amount', 'payment_method', 'status', 'external_reference', 'notes']


class PaymentCreateView(GenericModelCreateView):
    model = Payment
    model_name = 'Payment'
    fields = ['payment_reference', 'invoice', 'payment_date', 'amount', 'payment_method', 'status', 'external_reference', 'notes']


class PaymentUpdateView(GenericModelUpdateView):
    model = Payment
    model_name = 'Payment'
    fields = ['payment_reference', 'invoice', 'payment_date', 'amount', 'payment_method', 'status', 'external_reference', 'notes']


class PaymentDeleteView(GenericModelDeleteView):
    model = Payment
    model_name = 'Payment'


# =====================================================
# QUOTE VIEWS (renamed from Quotation)
# =====================================================

class QuoteListView(GenericModelListView):
    model = Quote
    model_name = 'Quote'
    model_name_plural = 'Quotes'
    list_display = ['quote_number', 'learner', 'corporate_client', 'total', 'status', 'quote_date', 'valid_until']
    search_fields = ['quote_number', 'corporate_client__company_name', 'learner__first_name', 'learner__last_name']


class QuoteDetailView(GenericModelDetailView):
    model = Quote
    model_name = 'Quote'
    detail_fields = ['quote_number', 'learner', 'corporate_client', 'lead', 'quote_date', 'valid_until', 'status', 'subtotal', 'vat_amount', 'discount_amount', 'total', 'notes', 'terms']


class QuoteCreateView(GenericModelCreateView):
    model = Quote
    model_name = 'Quote'
    fields = ['quote_number', 'learner', 'corporate_client', 'lead', 'quote_date', 'valid_until', 'status', 'subtotal', 'vat_amount', 'discount_amount', 'total', 'notes', 'terms']


class QuoteUpdateView(GenericModelUpdateView):
    model = Quote
    model_name = 'Quote'
    fields = ['quote_number', 'learner', 'corporate_client', 'lead', 'quote_date', 'valid_until', 'status', 'subtotal', 'vat_amount', 'discount_amount', 'total', 'notes', 'terms']


class QuoteDeleteView(GenericModelDeleteView):
    model = Quote
    model_name = 'Quote'


# =====================================================
# SETA VIEWS
# =====================================================

class SETAListView(GenericModelListView):
    model = SETA
    model_name = 'SETA'
    model_name_plural = 'SETAs'
    list_display = ['code', 'name', 'email', 'phone', 'is_active']
    search_fields = ['code', 'name']


class SETADetailView(GenericModelDetailView):
    model = SETA
    model_name = 'SETA'
    detail_fields = ['code', 'name', 'description', 'website', 'email', 'phone', 'is_active']


class SETACreateView(GenericModelCreateView):
    model = SETA
    model_name = 'SETA'
    fields = ['code', 'name', 'description', 'website', 'email', 'phone', 'is_active']


class SETAUpdateView(GenericModelUpdateView):
    model = SETA
    model_name = 'SETA'
    fields = ['code', 'name', 'description', 'website', 'email', 'phone', 'is_active']


class SETADeleteView(GenericModelDeleteView):
    model = SETA
    model_name = 'SETA'


# =====================================================
# EMPLOYER VIEWS
# =====================================================

class EmployerListView(GenericModelListView):
    model = Employer
    model_name = 'Employer'
    model_name_plural = 'Employers'
    list_display = ['name', 'trading_name', 'contact_email', 'contact_phone', 'workplace_approved', 'is_active']
    search_fields = ['name', 'trading_name', 'contact_email']


class EmployerDetailView(GenericModelDetailView):
    model = Employer
    model_name = 'Employer'
    detail_fields = ['name', 'trading_name', 'registration_number', 'vat_number', 'sdl_number', 'seta', 'contact_person', 'contact_email', 'contact_phone', 'workplace_approved', 'approval_date', 'approval_expiry', 'is_active']


class EmployerCreateView(GenericModelCreateView):
    model = Employer
    model_name = 'Employer'
    fields = ['name', 'trading_name', 'registration_number', 'vat_number', 'sdl_number', 'sic_code', 'seta', 'contact_person', 'contact_email', 'contact_phone', 'address', 'workplace_approved', 'approval_date', 'approval_expiry', 'approval_reference', 'is_active']


class EmployerUpdateView(GenericModelUpdateView):
    model = Employer
    model_name = 'Employer'
    fields = ['name', 'trading_name', 'registration_number', 'vat_number', 'sdl_number', 'sic_code', 'seta', 'contact_person', 'contact_email', 'contact_phone', 'address', 'workplace_approved', 'approval_date', 'approval_expiry', 'approval_reference', 'is_active']


class EmployerDeleteView(GenericModelDeleteView):
    model = Employer
    model_name = 'Employer'


# =====================================================
# ENROLLMENT WIZARD - Inline Learner Creation
# =====================================================

class EnrollmentWizardView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    """
    4-Step Enrollment Wizard with Inline Learner Creation
    
    Step 1: Learner - SA ID lookup or create new learner inline
    Step 2: Qualification & Cohort selection
    Step 3: Funding & Dates
    Step 4: Review & Confirm
    """
    template_name = 'admin/enrollment_wizard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        step = int(self.request.GET.get('step', 1))
        context['current_step'] = step
        
        # Steps for progress indicator
        context['steps'] = [
            (1, 'Learner'),
            (2, 'Qualification'),
            (3, 'Funding & Dates'),
            (4, 'Review'),
        ]
        
        # Get wizard data from session
        wizard_data = self.request.session.get('enrollment_wizard', {})
        context['wizard_data'] = wizard_data
        
        # Today's date for default application date
        context['today'] = timezone.now().date().isoformat()
        
        # Get choices for dropdowns
        context['qualifications'] = Qualification.objects.filter(is_active=True).order_by('title')
        context['cohorts'] = Cohort.objects.filter(status__in=['OPEN', 'IN_PROGRESS']).select_related('qualification').order_by('-start_date')
        context['campuses'] = Campus.objects.filter(is_active=True).order_by('name')
        
        # Funding type choices
        context['funding_types'] = Enrollment.FUNDING_TYPES
        
        # Gender choices
        context['gender_choices'] = Learner.GENDER_CHOICES
        
        # Population group choices
        context['population_group_choices'] = Learner.POPULATION_GROUP_CHOICES
        
        # Citizenship choices
        context['citizenship_choices'] = Learner.CITIZENSHIP_CHOICES
        
        # If learner was found in step 1, load details
        if wizard_data.get('learner_id'):
            try:
                context['selected_learner'] = Learner.objects.get(pk=wizard_data['learner_id'])
            except Learner.DoesNotExist:
                pass
        
        return context
    
    def post(self, request, *args, **kwargs):
        step = int(request.POST.get('step', 1))
        action = request.POST.get('action', 'next')
        
        # Initialize wizard data in session
        if 'enrollment_wizard' not in request.session:
            request.session['enrollment_wizard'] = {}
        
        wizard_data = request.session['enrollment_wizard']
        
        if action == 'cancel':
            # Clear wizard and redirect to list
            if 'enrollment_wizard' in request.session:
                del request.session['enrollment_wizard']
            return redirect('admin:enrollment_list')
        
        if action == 'back':
            return redirect(f"{reverse('admin:enrollment_wizard')}?step={step - 1}")
        
        # Process step data
        if step == 1:
            return self._process_step1(request, wizard_data)
        elif step == 2:
            return self._process_step2(request, wizard_data)
        elif step == 3:
            return self._process_step3(request, wizard_data)
        elif step == 4:
            return self._create_enrollment(request, wizard_data)
        
        return redirect(f"{reverse('admin:enrollment_wizard')}?step={step}")
    
    def _process_step1(self, request, wizard_data):
        """Process learner selection or creation"""
        learner_mode = request.POST.get('learner_mode', 'existing')
        
        if learner_mode == 'existing':
            learner_id = request.POST.get('learner_id')
            if not learner_id:
                messages.error(request, 'Please select an existing learner or create a new one.')
                return redirect(f"{reverse('admin:enrollment_wizard')}?step=1")
            wizard_data['learner_id'] = learner_id
            wizard_data['learner_mode'] = 'existing'
        else:
            # Store new learner data
            wizard_data['learner_mode'] = 'new'
            wizard_data['new_learner'] = {
                'sa_id_number': request.POST.get('sa_id_number', ''),
                'first_name': request.POST.get('first_name', ''),
                'last_name': request.POST.get('last_name', ''),
                'date_of_birth': request.POST.get('date_of_birth', ''),
                'gender': request.POST.get('gender', ''),
                'population_group': request.POST.get('population_group', ''),
                'citizenship': request.POST.get('citizenship', 'SA'),
                'email': request.POST.get('email', ''),
                'phone_mobile': request.POST.get('phone_mobile', ''),
            }
            
            # Validate required fields
            required = ['sa_id_number', 'first_name', 'last_name', 'date_of_birth', 'gender', 'email', 'phone_mobile']
            missing = [f for f in required if not wizard_data['new_learner'].get(f)]
            if missing:
                messages.error(request, f'Please fill in all required fields: {", ".join(missing)}')
                return redirect(f"{reverse('admin:enrollment_wizard')}?step=1")
        
        request.session['enrollment_wizard'] = wizard_data
        request.session.modified = True
        return redirect(f"{reverse('admin:enrollment_wizard')}?step=2")
    
    def _process_step2(self, request, wizard_data):
        """Process qualification and cohort selection"""
        qualification_id = request.POST.get('qualification')
        cohort_id = request.POST.get('cohort')
        campus_id = request.POST.get('campus')
        
        if not qualification_id:
            messages.error(request, 'Please select a qualification.')
            return redirect(f"{reverse('admin:enrollment_wizard')}?step=2")
        
        wizard_data['qualification_id'] = qualification_id
        wizard_data['cohort_id'] = cohort_id or None
        wizard_data['campus_id'] = campus_id or None
        
        request.session['enrollment_wizard'] = wizard_data
        request.session.modified = True
        return redirect(f"{reverse('admin:enrollment_wizard')}?step=3")
    
    def _process_step3(self, request, wizard_data):
        """Process funding and dates"""
        wizard_data['funding_type'] = request.POST.get('funding_type', 'SELF')
        wizard_data['funding_source'] = request.POST.get('funding_source', '')
        wizard_data['application_date'] = request.POST.get('application_date', '')
        wizard_data['start_date'] = request.POST.get('start_date', '')
        wizard_data['expected_completion'] = request.POST.get('expected_completion', '')
        
        if not wizard_data['application_date']:
            messages.error(request, 'Please enter an application date.')
            return redirect(f"{reverse('admin:enrollment_wizard')}?step=3")
        
        if not wizard_data['expected_completion']:
            messages.error(request, 'Please enter an expected completion date.')
            return redirect(f"{reverse('admin:enrollment_wizard')}?step=3")
        
        request.session['enrollment_wizard'] = wizard_data
        request.session.modified = True
        return redirect(f"{reverse('admin:enrollment_wizard')}?step=4")
    
    def _create_enrollment(self, request, wizard_data):
        """Create the learner (if new) and enrollment"""
        from django.db import transaction
        from datetime import datetime
        
        try:
            with transaction.atomic():
                # Create learner if new
                if wizard_data.get('learner_mode') == 'new':
                    new_learner_data = wizard_data['new_learner']
                    
                    # Generate learner number
                    last_learner = Learner.objects.order_by('-id').first()
                    next_num = (last_learner.id + 1) if last_learner else 1
                    learner_number = f"LRN{next_num:06d}"
                    
                    # Parse date of birth
                    dob = datetime.strptime(new_learner_data['date_of_birth'], '%Y-%m-%d').date()
                    
                    learner = Learner.objects.create(
                        learner_number=learner_number,
                        sa_id_number=new_learner_data['sa_id_number'],
                        first_name=new_learner_data['first_name'],
                        last_name=new_learner_data['last_name'],
                        date_of_birth=dob,
                        gender=new_learner_data['gender'],
                        population_group=new_learner_data.get('population_group', 'O'),
                        citizenship=new_learner_data.get('citizenship', 'SA'),
                        email=new_learner_data['email'],
                        phone_mobile=new_learner_data['phone_mobile'],
                    )
                else:
                    learner = Learner.objects.get(pk=wizard_data['learner_id'])
                
                # Generate enrollment number
                last_enrollment = Enrollment.objects.order_by('-id').first()
                next_num = (last_enrollment.id + 1) if last_enrollment else 1
                enrollment_number = f"ENR{next_num:06d}"
                
                # Parse dates
                application_date = datetime.strptime(wizard_data['application_date'], '%Y-%m-%d').date()
                expected_completion = datetime.strptime(wizard_data['expected_completion'], '%Y-%m-%d').date()
                start_date = None
                if wizard_data.get('start_date'):
                    start_date = datetime.strptime(wizard_data['start_date'], '%Y-%m-%d').date()
                
                # Create enrollment
                enrollment = Enrollment.objects.create(
                    enrollment_number=enrollment_number,
                    learner=learner,
                    qualification_id=wizard_data['qualification_id'],
                    cohort_id=wizard_data.get('cohort_id'),
                    campus_id=wizard_data.get('campus_id'),
                    funding_type=wizard_data.get('funding_type', 'SELF'),
                    funding_source=wizard_data.get('funding_source', ''),
                    application_date=application_date,
                    start_date=start_date,
                    expected_completion=expected_completion,
                    status='APPLIED',
                )
                
                # Clear wizard data
                del request.session['enrollment_wizard']
                
                messages.success(request, f'Enrollment {enrollment_number} created successfully for {learner.get_full_name()}!')
                return redirect('admin:enrollment_detail', pk=enrollment.pk)
                
        except Exception as e:
            messages.error(request, f'Error creating enrollment: {str(e)}')
            return redirect(f"{reverse('admin:enrollment_wizard')}?step=4")


class EnrollmentWizardStartView(LoginRequiredMixin, StaffRequiredMixin, View):
    """Start a fresh enrollment wizard"""
    def get(self, request):
        # Clear any existing wizard data
        if 'enrollment_wizard' in request.session:
            del request.session['enrollment_wizard']
        return redirect(f"{reverse('admin:enrollment_wizard')}?step=1")


def check_sa_id(request):
    """
    AJAX endpoint to check if SA ID exists and return learner data
    Returns JSON with learner details or not_found status
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    sa_id = request.GET.get('sa_id', '').strip()
    
    if not sa_id or len(sa_id) != 13:
        return JsonResponse({'status': 'invalid', 'message': 'SA ID must be 13 digits'})
    
    try:
        learner = Learner.objects.get(sa_id_number=sa_id)
        return JsonResponse({
            'status': 'found',
            'learner': {
                'id': learner.id,
                'learner_number': learner.learner_number,
                'first_name': learner.first_name,
                'last_name': learner.last_name,
                'full_name': learner.get_full_name(),
                'email': learner.email,
                'phone_mobile': learner.phone_mobile,
                'date_of_birth': learner.date_of_birth.isoformat() if learner.date_of_birth else None,
                'gender': learner.gender,
                'enrollments_count': learner.enrollments.count(),
            }
        })
    except Learner.DoesNotExist:
        # Try to extract DOB from SA ID
        dob_info = None
        try:
            year = int(sa_id[0:2])
            month = int(sa_id[2:4])
            day = int(sa_id[4:6])
            # Assume 2000s for years < 30, 1900s otherwise
            full_year = 2000 + year if year < 30 else 1900 + year
            dob_info = f"{full_year}-{month:02d}-{day:02d}"
        except:
            pass
        
        return JsonResponse({
            'status': 'not_found',
            'message': 'No learner found with this SA ID',
            'extracted_dob': dob_info
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


# =====================================================
# BRAND VIEWS
# =====================================================

class BrandListView(GenericModelListView):
    model = Brand
    model_name = 'Brand'
    model_name_plural = 'Brands'
    list_display = ['code', 'name', 'accreditation_number', 'is_active']
    search_fields = ['code', 'name', 'legal_name', 'accreditation_number']


class BrandDetailView(GenericModelDetailView):
    model = Brand
    model_name = 'Brand'
    detail_fields = ['code', 'name', 'legal_name', 'accreditation_number', 'seta_registration', 'email', 'phone', 'website', 'is_active']


class BrandCreateView(GenericModelCreateView):
    model = Brand
    model_name = 'Brand'
    fields = ['code', 'name', 'legal_name', 'accreditation_number', 'seta_registration', 'email', 'phone', 'website', 'primary_color', 'secondary_color', 'is_active']


class BrandUpdateView(GenericModelUpdateView):
    model = Brand
    model_name = 'Brand'
    fields = ['code', 'name', 'legal_name', 'accreditation_number', 'seta_registration', 'email', 'phone', 'website', 'primary_color', 'secondary_color', 'is_active']


class BrandDeleteView(GenericModelDeleteView):
    model = Brand
    model_name = 'Brand'


# =====================================================
# CAMPUS VIEWS
# =====================================================

class CampusListView(GenericModelListView):
    model = Campus
    model_name = 'Campus'
    model_name_plural = 'Campuses'
    list_display = ['code', 'name', 'brand', 'campus_type', 'city', 'province', 'is_active']
    search_fields = ['code', 'name', 'city', 'province', 'region']
    
    def get_queryset(self):
        return Campus.objects.select_related('brand').order_by('brand__name', 'name')


class CampusDetailView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    """Enhanced campus detail view with comprehensive information"""
    template_name = 'admin/campus_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campus = get_object_or_404(Campus.objects.select_related('brand'), pk=kwargs.get('pk'))
        context['campus'] = campus
        context['model_name'] = 'Campus'
        
        # Get qualification accreditations for this campus
        from academics.models import QualificationCampusAccreditation
        context['accreditations'] = QualificationCampusAccreditation.objects.filter(
            campus=campus
        ).select_related('qualification').order_by('-accredited_until')
        
        # Get cohorts at this campus
        context['cohorts'] = Cohort.objects.filter(campus=campus).select_related('qualification')[:10]
        
        # Get venues at this campus
        context['venues'] = Venue.objects.filter(campus=campus)
        
        # URLs for navigation
        context['edit_url'] = 'admin:campus_edit'
        context['delete_url'] = 'admin:campus_delete'
        context['list_url'] = 'admin:campus_list'
        
        return context


class CampusCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Create view for Campus with comprehensive form"""
    model = Campus
    template_name = 'admin/campus_form.html'
    fields = [
        'brand', 'code', 'name', 'campus_type', 'region',
        'address_line1', 'address_line2', 'suburb', 'city', 'province', 'postal_code', 'country',
        'email', 'phone', 'latitude', 'longitude', 'is_active'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'Campus'
        context['action'] = 'Create'
        context['list_url'] = 'admin:campus_list'
        context['brands'] = Brand.objects.filter(is_active=True).order_by('name')
        context['campus_types'] = Campus.CAMPUS_TYPES
        # Provide empty object for template compatibility
        context['object'] = Campus()
        return context
    
    def get_success_url(self):
        messages.success(self.request, f'Campus "{self.object.name}" created successfully.')
        return reverse('admin:campus_detail', kwargs={'pk': self.object.pk})


class CampusUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Update view for Campus with comprehensive form"""
    model = Campus
    template_name = 'admin/campus_form.html'
    fields = [
        'brand', 'code', 'name', 'campus_type', 'region',
        'address_line1', 'address_line2', 'suburb', 'city', 'province', 'postal_code', 'country',
        'email', 'phone', 'latitude', 'longitude', 'is_active'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'Campus'
        context['action'] = 'Edit'
        context['list_url'] = 'admin:campus_list'
        context['brands'] = Brand.objects.filter(is_active=True).order_by('name')
        context['campus_types'] = Campus.CAMPUS_TYPES
        return context
    
    def get_success_url(self):
        messages.success(self.request, f'Campus "{self.object.name}" updated successfully.')
        return reverse('admin:campus_detail', kwargs={'pk': self.object.pk})


class CampusDeleteView(GenericModelDeleteView):
    model = Campus
    model_name = 'Campus'


# =====================================================
# CONTRACT MANAGEMENT VIEWS
# =====================================================

class ContractListView(GenericModelListView):
    """List all contracts with key metrics"""
    model = Contract
    model_name = 'Contract'
    model_name_plural = 'Contracts'
    list_display = ['contract_number', 'name', 'client', 'funder_type', 'status', 'original_learner_count', 'dropout_percentage']
    search_fields = ['contract_number', 'name', 'client__name']
    
    def get_queryset(self):
        return Contract.objects.select_related('client', 'seta').order_by('-created_at')


class ContractDetailView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    """Contract detail view with KPI dashboard for dropout tracking"""
    template_name = 'admin/contract_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = get_object_or_404(
            Contract.objects.select_related('client', 'seta'),
            pk=kwargs.get('pk')
        )
        context['contract'] = contract
        context['model_name'] = 'Contract'
        
        # Get Training Notifications linked to this contract
        from core.models import TrainingNotification
        context['training_notifications'] = TrainingNotification.objects.filter(
            contract=contract
        ).select_related('qualification', 'delivery_campus').order_by('-created_at')
        
        # Get learner enrollments grouped by status
        context['active_enrollments'] = contract.learner_enrollments.filter(
            termination_date__isnull=True
        ).select_related('learner', 'training_notification').order_by('learner__surname')
        
        context['terminated_enrollments'] = contract.learner_enrollments.filter(
            termination_date__isnull=False
        ).select_related('learner', 'training_notification', 'terminated_by').order_by('-termination_date')
        
        context['replacement_enrollments'] = contract.learner_enrollments.filter(
            is_replacement=True
        ).select_related('learner', 'replaces_learner__learner').order_by('-enrollment_date')
        
        # Termination reasons for form
        context['termination_reasons'] = LearnerContractEnrollment.TERMINATION_REASON_CHOICES
        
        # URLs for navigation
        context['edit_url'] = 'admin:contract_edit'
        context['delete_url'] = 'admin:contract_delete'
        context['list_url'] = 'admin:contract_list'
        
        return context


class ContractCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Create view for Contract"""
    model = Contract
    template_name = 'admin/contract_form.html'
    fields = [
        'name', 'description', 'client', 'seta', 'funder_type', 
        'contract_value', 'start_date', 'end_date', 'signature_date',
        'status', 'original_learner_count', 'max_dropout_percentage', 
        'dropout_alert_threshold', 'contract_document', 'notes'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'Contract'
        context['action'] = 'Create'
        context['list_url'] = 'admin:contract_list'
        context['clients'] = CorporateClient.objects.filter(is_active=True).order_by('name')
        context['setas'] = SETA.objects.all().order_by('name')
        context['funder_types'] = Contract.FUNDER_TYPE_CHOICES
        context['status_choices'] = Contract.STATUS_CHOICES
        return context
    
    def get_success_url(self):
        messages.success(self.request, f'Contract "{self.object.name}" created successfully.')
        return reverse('admin:contract_detail', kwargs={'pk': self.object.pk})


class ContractUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Update view for Contract"""
    model = Contract
    template_name = 'admin/contract_form.html'
    fields = [
        'name', 'description', 'client', 'seta', 'funder_type', 
        'contract_value', 'start_date', 'end_date', 'signature_date',
        'status', 'original_learner_count', 'max_dropout_percentage', 
        'dropout_alert_threshold', 'contract_document', 'notes'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'Contract'
        context['action'] = 'Edit'
        context['list_url'] = 'admin:contract_list'
        context['clients'] = CorporateClient.objects.filter(is_active=True).order_by('name')
        context['setas'] = SETA.objects.all().order_by('name')
        context['funder_types'] = Contract.FUNDER_TYPE_CHOICES
        context['status_choices'] = Contract.STATUS_CHOICES
        return context
    
    def get_success_url(self):
        messages.success(self.request, f'Contract "{self.object.name}" updated successfully.')
        return reverse('admin:contract_detail', kwargs={'pk': self.object.pk})


class ContractDeleteView(GenericModelDeleteView):
    model = Contract
    model_name = 'Contract'


class TerminateLearnerView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    """View to terminate a learner from a contract"""
    template_name = 'admin/terminate_learner.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = get_object_or_404(Contract, pk=kwargs.get('contract_pk'))
        enrollment = get_object_or_404(
            LearnerContractEnrollment.objects.select_related('learner', 'contract'),
            pk=kwargs.get('enrollment_pk')
        )
        context['contract'] = contract
        context['enrollment'] = enrollment
        context['learner'] = enrollment.learner
        context['termination_reasons'] = LearnerContractEnrollment.TERMINATION_REASON_CHOICES
        
        # Calculate what dropout would be after this termination
        current_dropouts = contract.dropout_count
        new_dropouts = current_dropouts + (1 if enrollment.is_original else 0)
        base = contract.original_learner_count or contract.original_learners
        if base > 0:
            context['projected_dropout_percentage'] = round((new_dropouts / base) * 100, 1)
        else:
            context['projected_dropout_percentage'] = 0
        context['will_exceed_limit'] = context['projected_dropout_percentage'] >= float(contract.max_dropout_percentage)
        
        return context
    
    def post(self, request, *args, **kwargs):
        contract = get_object_or_404(Contract, pk=kwargs.get('contract_pk'))
        enrollment = get_object_or_404(LearnerContractEnrollment, pk=kwargs.get('enrollment_pk'))
        
        reason = request.POST.get('termination_reason')
        details = request.POST.get('termination_details', '')
        termination_date = request.POST.get('termination_date')
        
        from datetime import datetime
        if termination_date:
            termination_date = datetime.strptime(termination_date, '%Y-%m-%d').date()
        
        enrollment.terminate(
            reason=reason,
            details=details,
            terminated_by=request.user,
            termination_date=termination_date
        )
        
        messages.success(
            request, 
            f'Learner {enrollment.learner} has been terminated from contract {contract.contract_number}.'
        )
        return redirect('admin:contract_detail', pk=contract.pk)


class AddReplacementLearnerView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    """View to add a replacement learner to a contract"""
    template_name = 'admin/add_replacement_learner.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = get_object_or_404(Contract, pk=kwargs.get('contract_pk'))
        context['contract'] = contract
        
        # Get terminated learners that can be replaced
        context['terminated_enrollments'] = contract.learner_enrollments.filter(
            termination_date__isnull=False
        ).exclude(
            replaced_by__isnull=False  # Exclude already replaced
        ).select_related('learner')
        
        # Get available learners (not already enrolled in this contract)
        enrolled_learner_ids = contract.learner_enrollments.values_list('learner_id', flat=True)
        context['available_learners'] = Learner.objects.exclude(
            id__in=enrolled_learner_ids
        ).order_by('surname', 'first_name')[:100]  # Limit for performance
        
        # Get NOTs linked to this contract
        from core.models import TrainingNotification
        context['training_notifications'] = TrainingNotification.objects.filter(contract=contract)
        
        return context
    
    def post(self, request, *args, **kwargs):
        contract = get_object_or_404(Contract, pk=kwargs.get('contract_pk'))
        
        learner_id = request.POST.get('learner_id')
        replaces_id = request.POST.get('replaces_enrollment_id')
        not_id = request.POST.get('training_notification_id')
        enrollment_date = request.POST.get('enrollment_date')
        
        from datetime import datetime
        if enrollment_date:
            enrollment_date = datetime.strptime(enrollment_date, '%Y-%m-%d').date()
        else:
            from datetime import date
            enrollment_date = date.today()
        
        learner = get_object_or_404(Learner, pk=learner_id)
        replaces = None
        if replaces_id:
            replaces = get_object_or_404(LearnerContractEnrollment, pk=replaces_id)
        
        training_notification = None
        if not_id:
            from core.models import TrainingNotification
            training_notification = get_object_or_404(TrainingNotification, pk=not_id)
        
        # Create the replacement enrollment
        LearnerContractEnrollment.objects.create(
            contract=contract,
            learner=learner,
            training_notification=training_notification,
            is_original=False,
            is_replacement=True,
            replaces_learner=replaces,
            enrollment_date=enrollment_date,
            created_by=request.user
        )
        
        messages.success(
            request, 
            f'Replacement learner {learner} has been added to contract {contract.contract_number}.'
        )
        return redirect('admin:contract_detail', pk=contract.pk)


class AddLearnerToContractView(LoginRequiredMixin, StaffRequiredMixin, TemplateView):
    """View to add an original learner to a contract"""
    template_name = 'admin/add_learner_to_contract.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = get_object_or_404(Contract, pk=kwargs.get('contract_pk'))
        context['contract'] = contract
        
        # Get available learners (not already enrolled in this contract)
        enrolled_learner_ids = contract.learner_enrollments.values_list('learner_id', flat=True)
        context['available_learners'] = Learner.objects.exclude(
            id__in=enrolled_learner_ids
        ).order_by('surname', 'first_name')[:100]
        
        # Get NOTs linked to this contract
        from core.models import TrainingNotification
        context['training_notifications'] = TrainingNotification.objects.filter(contract=contract)
        
        return context
    
    def post(self, request, *args, **kwargs):
        contract = get_object_or_404(Contract, pk=kwargs.get('contract_pk'))
        
        learner_id = request.POST.get('learner_id')
        not_id = request.POST.get('training_notification_id')
        enrollment_date = request.POST.get('enrollment_date')
        
        from datetime import datetime, date
        if enrollment_date:
            enrollment_date = datetime.strptime(enrollment_date, '%Y-%m-%d').date()
        else:
            enrollment_date = date.today()
        
        learner = get_object_or_404(Learner, pk=learner_id)
        
        training_notification = None
        if not_id:
            from core.models import TrainingNotification
            training_notification = get_object_or_404(TrainingNotification, pk=not_id)
        
        # Create the enrollment
        LearnerContractEnrollment.objects.create(
            contract=contract,
            learner=learner,
            training_notification=training_notification,
            is_original=True,
            is_replacement=False,
            enrollment_date=enrollment_date,
            created_by=request.user
        )
        
        messages.success(
            request, 
            f'Learner {learner} has been added to contract {contract.contract_number}.'
        )
        return redirect('admin:contract_detail', pk=contract.pk)
