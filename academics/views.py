"""Academics app views"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Prefetch, Max
from django.utils import timezone
from django.views.generic import TemplateView, CreateView, UpdateView, DeleteView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from datetime import timedelta, date

from .models import (
    Qualification, 
    Module,
    AccreditationChecklistItem,
    AccreditationChecklistProgress,
    ComplianceDocument,
    AccreditationAlert,
    PersonnelRegistration,
    QualificationCampusAccreditation,
    LearningMaterial,
    QCTOSyncLog,
    QCTOQualificationChange,
    LessonPlanTemplate
)
from .forms import (
    QualificationForm, ModuleForm, LearningMaterialForm, 
    PersonnelRegistrationForm, MaterialArchiveForm, ChecklistItemForm
)
from tenants.models import Campus
from assessments.models import AssessmentActivity


class AcademicsDashboardView(LoginRequiredMixin, TemplateView):
    """
    Academic management dashboard showing:
    - Current qualifications and accreditation status
    - Accreditations expiring soon or expired
    - Learning materials needing review
    - Assessments needing creation
    - Materials needing printing
    """
    template_name = 'academics/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        
        # Qualifications summary
        all_qualifications = Qualification.objects.select_related('seta').prefetch_related(
            'campus_accreditations__campus'
        )
        
        context['total_qualifications'] = all_qualifications.count()
        context['active_qualifications'] = all_qualifications.filter(
            accreditation_expiry__gte=today + timedelta(days=180)
        ).count()
        
        # Accreditations expiring soon (within 180 days)
        context['expiring_soon'] = all_qualifications.filter(
            accreditation_expiry__gte=today,
            accreditation_expiry__lt=today + timedelta(days=180)
        ).order_by('accreditation_expiry')
        
        # Expired accreditations
        context['expired_accreditations'] = all_qualifications.filter(
            accreditation_expiry__lt=today
        ).order_by('accreditation_expiry')
        
        # Applications needed (no accreditation date or very old)
        context['needs_application'] = all_qualifications.filter(
            Q(accreditation_expiry__isnull=True) | Q(accreditation_expiry__lt=today - timedelta(days=30))
        ).order_by('title')
        
        # Learning materials needing review (not approved or overdue for review)
        context['materials_need_review'] = LearningMaterial.objects.filter(
            Q(approved=False) | Q(next_review_date__lt=today)
        ).select_related('qualification').order_by('-updated_at')[:10]
        
        # Recently updated learning materials (for printing/distribution needs)
        context['materials_need_printing'] = LearningMaterial.objects.filter(
            is_current=True, approved=True
        ).select_related('qualification').order_by('-updated_at')[:10]
        
        # Assessments needing creation (modules without assessments)
        from academics.models import Module
        modules_with_assessments = AssessmentActivity.objects.values_list('module_id', flat=True).distinct()
        context['modules_need_assessments'] = Module.objects.exclude(
            id__in=modules_with_assessments
        ).select_related('qualification').order_by('qualification__title', 'code')[:10]
        
        # Compliance alerts
        context['compliance_alerts'] = AccreditationAlert.objects.filter(
            resolved=False
        ).select_related('qualification').order_by('-created_at')[:5]
        
        # Recent accreditation progress
        context['recent_progress'] = AccreditationChecklistProgress.objects.filter(
            completed=True
        ).select_related(
            'checklist_item__qualification', 'completed_by'
        ).order_by('-completed_at')[:10]
        
        # Calculate needs_action_count for template
        context['needs_action_count'] = (
            context['expired_accreditations'].count() + 
            context['needs_application'].count()
        )
        
        return context


@login_required
def qualification_list(request):
    """
    List all qualifications with accreditation status, delivery readiness, and checklist progress
    """
    qualifications = Qualification.objects.all().select_related('seta').prefetch_related(
        'checklist_items',
        'campus_accreditations__campus'
    )
    
    # Filters
    seta_filter = request.GET.get('seta')
    nqf_filter = request.GET.get('nqf')
    status_filter = request.GET.get('status')
    delivery_filter = request.GET.get('delivery')
    
    if seta_filter:
        qualifications = qualifications.filter(seta_id=seta_filter)
    if nqf_filter:
        qualifications = qualifications.filter(nqf_level=nqf_filter)
    if status_filter:
        # Filter by accreditation status
        today = timezone.now().date()
        if status_filter == 'ACTIVE':
            qualifications = qualifications.filter(
                accreditation_expiry__gte=today + timedelta(days=180)
            )
        elif status_filter == 'EXPIRING':
            qualifications = qualifications.filter(
                accreditation_expiry__lt=today + timedelta(days=180),
                accreditation_expiry__gte=today
            )
        elif status_filter == 'EXPIRED':
            qualifications = qualifications.filter(
                accreditation_expiry__lt=today
            )
    
    if delivery_filter == 'IN_PERSON':
        qualifications = qualifications.filter(ready_in_person=True)
    elif delivery_filter == 'ONLINE':
        qualifications = qualifications.filter(ready_online=True)
    elif delivery_filter == 'HYBRID':
        qualifications = qualifications.filter(ready_hybrid=True)
    
    # Calculate stats for each qualification
    qual_data = []
    for qual in qualifications:
        checklist_items = qual.checklist_items.all()
        total_items = checklist_items.count()
        completed_items = sum(
            1 for item in checklist_items 
            if hasattr(item, 'progress_records') and item.progress_records.filter(completed=True).exists()
        )
        
        qual_data.append({
            'qualification': qual,
            'checklist_total': total_items,
            'checklist_completed': completed_items,
            'checklist_percent': int((completed_items / total_items * 100)) if total_items > 0 else 0,
            'accreditation_status': qual.accreditation_status,
            'days_until_expiry': qual.days_until_expiry,
        })
    
    # Stats
    from learners.models import SETA
    setas = SETA.objects.all()
    nqf_levels = range(1, 11)
    
    # Alert counts
    unresolved_alerts = AccreditationAlert.objects.filter(
        resolved=False,
        qualification__isnull=False
    ).count()
    
    context = {
        'qual_data': qual_data,
        'setas': setas,
        'nqf_levels': nqf_levels,
        'unresolved_alerts': unresolved_alerts,
        'filters': {
            'seta': seta_filter,
            'nqf': nqf_filter,
            'status': status_filter,
            'delivery': delivery_filter,
        }
    }
    
    return render(request, 'academics/qualification_list.html', context)


@login_required
def qualification_detail(request, pk):
    """
    Detailed view of a qualification with tabs for checklist, resources, documents
    """
    # Update expired accreditation statuses before querying
    QualificationCampusAccreditation.objects.update_expired_statuses()
    
    qualification = get_object_or_404(
        Qualification.objects.select_related('seta').prefetch_related(
            'modules',
            'checklist_items__progress_records',
            'campus_accreditations__campus',
            'learning_materials',
            'registered_personnel__user',
            'accreditation_alerts'
        ),
        pk=pk
    )
    
    # Checklist data
    checklist_items = qualification.checklist_items.all().order_by('category', 'sequence_order')
    checklist_by_category = {}
    for item in checklist_items:
        category = item.get_category_display()
        if category not in checklist_by_category:
            checklist_by_category[category] = []
        
        # Get progress
        progress = item.progress_records.first() if hasattr(item, 'progress_records') else None
        checklist_by_category[category].append({
            'item': item,
            'progress': progress,
            'completed': progress.completed if progress else False,
        })
    
    # Calculate checklist completion
    total_items = len(checklist_items)
    completed_items = sum(
        1 for item in checklist_items 
        if hasattr(item, 'progress_records') and item.progress_records.filter(completed=True).exists()
    )
    checklist_percent = int((completed_items / total_items * 100)) if total_items > 0 else 0
    
    # Campus accreditations - group by campus to show multiple letters per campus
    all_campus_accreditations = qualification.campus_accreditations.select_related('campus').order_by('campus__name', '-accredited_until')
    
    # Group accreditations by campus
    campus_accreditations_grouped = {}
    for accred in all_campus_accreditations:
        campus_name = accred.campus.name
        if campus_name not in campus_accreditations_grouped:
            campus_accreditations_grouped[campus_name] = {
                'campus': accred.campus,
                'accreditations': [],
                'has_active': False,
                'has_expiring_soon': False,
            }
        campus_accreditations_grouped[campus_name]['accreditations'].append(accred)
        if accred.status == 'ACTIVE':
            campus_accreditations_grouped[campus_name]['has_active'] = True
        if accred.is_expiring_soon:
            campus_accreditations_grouped[campus_name]['has_expiring_soon'] = True
    
    # Also keep flat list for backwards compatibility
    campus_accreditations = all_campus_accreditations.filter(is_active=True)
    
    # Implementation Plans
    implementation_plans = ImplementationPlan.objects.filter(qualification=qualification).prefetch_related('phases')[:5]
    
    # Modules with lesson plan counts
    modules = qualification.modules.annotate(
        lesson_plan_count=Count('lesson_plans')
    ).order_by('module_type', 'sequence_order')
    
    # Personnel
    personnel = qualification.registered_personnel.filter(is_active=True)
    
    # Learning materials
    materials = qualification.learning_materials.filter(is_current=True)
    
    # Recent alerts
    recent_alerts = qualification.accreditation_alerts.filter(resolved=False)[:5]
    
    # Enrollments count
    active_enrollments = qualification.enrollments.filter(
        status__in=['ENROLLED', 'ACTIVE']
    ).count()
    
    # Qualification Pricing - current, history, and future
    from academics.models import QualificationPricing
    from datetime import date
    current_year = date.today().year
    
    current_pricing = qualification.get_current_pricing()
    pricing_history = QualificationPricing.objects.filter(
        qualification=qualification
    ).order_by('-academic_year', '-effective_from')
    
    context = {
        'qualification': qualification,
        'checklist_by_category': checklist_by_category,
        'checklist_percent': checklist_percent,
        'total_items': total_items,
        'completed_items': completed_items,
        'campus_accreditations': campus_accreditations,
        'campus_accreditations_grouped': campus_accreditations_grouped,
        'implementation_plans': implementation_plans,
        'modules': modules,
        'personnel': personnel,
        'materials': materials,
        'recent_alerts': recent_alerts,
        'active_enrollments': active_enrollments,
        'accreditation_status': qualification.accreditation_status,
        'days_until_expiry': qualification.days_until_expiry,
        'current_pricing': current_pricing,
        'pricing_history': pricing_history,
        'current_year': current_year,
    }
    
    return render(request, 'academics/qualification_detail.html', context)


@login_required
def toggle_checklist_item(request, pk):
    """
    Toggle completion status of a checklist item
    """
    if request.method == 'POST':
        item = get_object_or_404(AccreditationChecklistItem, pk=pk)
        
        # Get or create progress record
        progress, created = AccreditationChecklistProgress.objects.get_or_create(
            checklist_item=item,
            defaults={
                'completed': True,
                'completed_by': request.user,
                'completed_at': timezone.now(),
            }
        )
        
        if not created:
            # Toggle completion
            progress.completed = not progress.completed
            if progress.completed:
                progress.completed_by = request.user
                progress.completed_at = timezone.now()
            else:
                progress.completed_by = None
                progress.completed_at = None
            progress.save()
        
        # Add notes if provided
        notes = request.POST.get('notes')
        if notes:
            progress.notes = notes
            progress.save()
        
        messages.success(request, f"Checklist item {'completed' if progress.completed else 'reopened'}")
        return redirect('academics:qualification_detail', pk=item.qualification.pk)
    
    return redirect('academics:qualification_list')


@login_required
def compliance_dashboard(request):
    """
    Dashboard showing all compliance documents grouped by campus
    """
    # Get all compliance documents
    documents = ComplianceDocument.objects.select_related('campus').prefetch_related(
        'compliance_alerts'
    ).order_by('campus__name', 'document_type')
    
    # Filter by campus if specified
    campus_filter = request.GET.get('campus')
    if campus_filter:
        if campus_filter == 'org_wide':
            documents = documents.filter(campus__isnull=True)
        else:
            documents = documents.filter(campus_id=campus_filter)
    
    # Group by campus
    org_wide_docs = []
    campus_docs = {}
    
    for doc in documents:
        doc_data = {
            'document': doc,
            'compliance_status': doc.compliance_status,
            'days_until_expiry': doc.days_until_expiry,
            'unresolved_alerts': doc.compliance_alerts.filter(resolved=False).count()
        }
        
        if doc.campus:
            campus_name = doc.campus.name
            if campus_name not in campus_docs:
                campus_docs[campus_name] = []
            campus_docs[campus_name].append(doc_data)
        else:
            org_wide_docs.append(doc_data)
    
    # Stats
    total_docs = documents.count()
    expired_docs = sum(1 for doc in documents if doc.compliance_status == 'EXPIRED')
    expiring_docs = sum(1 for doc in documents if doc.compliance_status == 'EXPIRING')
    valid_docs = sum(1 for doc in documents if doc.compliance_status == 'VALID')
    
    # Unresolved alerts
    unresolved_alerts = AccreditationAlert.objects.filter(
        resolved=False,
        compliance_document__isnull=False
    ).count()
    
    # Campuses for filter
    campuses = Campus.objects.filter(is_active=True)
    
    context = {
        'org_wide_docs': org_wide_docs,
        'campus_docs': campus_docs,
        'total_docs': total_docs,
        'expired_docs': expired_docs,
        'expiring_docs': expiring_docs,
        'valid_docs': valid_docs,
        'unresolved_alerts': unresolved_alerts,
        'campuses': campuses,
        'campus_filter': campus_filter,
    }
    
    return render(request, 'academics/compliance_dashboard.html', context)


@login_required
def accreditation_alerts(request):
    """
    View all accreditation and compliance alerts
    """
    alerts = AccreditationAlert.objects.select_related(
        'qualification',
        'compliance_document',
        'acknowledged_by'
    ).order_by('-alert_date')
    
    # Filter
    status_filter = request.GET.get('status', 'unresolved')
    if status_filter == 'unresolved':
        alerts = alerts.filter(resolved=False)
    elif status_filter == 'resolved':
        alerts = alerts.filter(resolved=True)
    
    type_filter = request.GET.get('type')
    if type_filter == 'qualification':
        alerts = alerts.filter(qualification__isnull=False)
    elif type_filter == 'compliance':
        alerts = alerts.filter(compliance_document__isnull=False)
    
    context = {
        'alerts': alerts,
        'status_filter': status_filter,
        'type_filter': type_filter,
    }
    
    return render(request, 'academics/accreditation_alerts.html', context)


# =============================================================================
# CRUD Views for Qualifications
# =============================================================================

class QualificationCreateView(LoginRequiredMixin, CreateView):
    """Create a new qualification"""
    model = Qualification
    form_class = QualificationForm
    template_name = 'academics/qualification_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Qualification'
        context['submit_text'] = 'Create Qualification'
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Create default checklist items for new qualification
        self.object.create_default_checklist()
        messages.success(self.request, f'Qualification "{self.object.short_title}" created successfully with default checklist.')
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_success_url(self):
        return reverse('academics:qualification_detail', kwargs={'pk': self.object.pk})


class QualificationUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing qualification"""
    model = Qualification
    form_class = QualificationForm
    template_name = 'academics/qualification_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit: {self.object.short_title}'
        context['submit_text'] = 'Save Changes'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Qualification "{self.object.short_title}" updated successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('academics:qualification_detail', kwargs={'pk': self.object.pk})


class QualificationDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a qualification (soft delete via is_active=False)"""
    model = Qualification
    template_name = 'academics/qualification_confirm_delete.html'
    success_url = reverse_lazy('academics:qualification_list')
    
    def form_valid(self, form):
        # Soft delete instead of hard delete
        self.object.is_active = False
        self.object.save()
        messages.success(self.request, f'Qualification "{self.object.short_title}" has been deactivated.')
        return redirect(self.get_success_url())


# =============================================================================
# CRUD Views for Modules
# =============================================================================

class ModuleCreateView(LoginRequiredMixin, CreateView):
    """Create a new module for a qualification"""
    model = Module
    form_class = ModuleForm
    template_name = 'academics/module_form.html'
    
    def get_qualification(self):
        return get_object_or_404(Qualification, pk=self.kwargs['qualification_pk'])
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['qualification'] = self.get_qualification()
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['qualification'] = self.get_qualification()
        context['title'] = 'Add New Module'
        context['submit_text'] = 'Create Module'
        return context
    
    def form_valid(self, form):
        form.instance.qualification = self.get_qualification()
        messages.success(self.request, f'Module "{form.instance.title}" created successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('academics:qualification_detail', kwargs={'pk': self.kwargs['qualification_pk']})


class ModuleUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing module"""
    model = Module
    form_class = ModuleForm
    template_name = 'academics/module_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['qualification'] = self.object.qualification
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['qualification'] = self.object.qualification
        context['title'] = f'Edit: {self.object.title}'
        context['submit_text'] = 'Save Changes'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Module "{self.object.title}" updated successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('academics:qualification_detail', kwargs={'pk': self.object.qualification.pk})


class ModuleDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a module (soft delete)"""
    model = Module
    template_name = 'academics/module_confirm_delete.html'
    
    def form_valid(self, form):
        qualification_pk = self.object.qualification.pk
        self.object.is_active = False
        self.object.save()
        messages.success(self.request, f'Module "{self.object.title}" has been deactivated.')
        return redirect('academics:qualification_detail', pk=qualification_pk)
    
    def get_success_url(self):
        return reverse('academics:qualification_detail', kwargs={'pk': self.object.qualification.pk})


# =============================================================================
# CRUD Views for Learning Materials
# =============================================================================

class LearningMaterialCreateView(LoginRequiredMixin, CreateView):
    """Upload a new learning material"""
    model = LearningMaterial
    form_class = LearningMaterialForm
    template_name = 'academics/material_form.html'
    
    def get_qualification(self):
        return get_object_or_404(Qualification, pk=self.kwargs['qualification_pk'])
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['qualification'] = self.get_qualification()
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['qualification'] = self.get_qualification()
        context['title'] = 'Upload Learning Material'
        context['submit_text'] = 'Upload Material'
        return context
    
    def form_valid(self, form):
        form.instance.qualification = self.get_qualification()
        messages.success(self.request, f'Learning material "{form.instance.title}" uploaded successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('academics:qualification_detail', kwargs={'pk': self.kwargs['qualification_pk']})


class LearningMaterialUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing learning material with explicit archive option"""
    model = LearningMaterial
    form_class = LearningMaterialForm
    template_name = 'academics/material_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['qualification'] = self.object.qualification
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['qualification'] = self.object.qualification
        context['title'] = f'Edit: {self.object.title}'
        context['submit_text'] = 'Save Changes'
        context['show_archive_option'] = True
        return context
    
    def form_valid(self, form):
        # Handle explicit archive action
        if form.cleaned_data.get('archive_previous'):
            # Create archived copy before saving new version
            old_material = LearningMaterial.objects.get(pk=self.object.pk)
            old_material.pk = None  # Create new record
            old_material.is_current = False
            old_material.title = f"{old_material.title} (Archived v{old_material.version})"
            old_material.save()
            
            # Increment version
            try:
                current_version = float(form.instance.version or '1.0')
                form.instance.version = str(current_version + 0.1)
            except ValueError:
                form.instance.version = '1.1'
        
        messages.success(self.request, f'Learning material "{self.object.title}" updated successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('academics:qualification_detail', kwargs={'pk': self.object.qualification.pk})


@login_required
def archive_material(request, pk):
    """Explicitly archive a learning material"""
    material = get_object_or_404(LearningMaterial, pk=pk)
    
    if request.method == 'POST':
        form = MaterialArchiveForm(request.POST)
        if form.is_valid():
            material.is_current = False
            material.title = f"{material.title} (Archived)"
            material.save()
            messages.success(request, f'Material "{material.title}" has been archived.')
            return redirect('academics:qualification_detail', pk=material.qualification.pk)
    else:
        form = MaterialArchiveForm()
    
    return render(request, 'academics/material_archive.html', {
        'form': form,
        'material': material,
        'qualification': material.qualification,
    })


# =============================================================================
# CRUD Views for Personnel Registration
# =============================================================================

class PersonnelRegistrationCreateView(LoginRequiredMixin, CreateView):
    """Add a new personnel registration"""
    model = PersonnelRegistration
    form_class = PersonnelRegistrationForm
    template_name = 'academics/personnel_form.html'
    
    def get_qualification(self):
        return get_object_or_404(Qualification, pk=self.kwargs['qualification_pk'])
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['qualification'] = self.get_qualification()
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['qualification'] = self.get_qualification()
        context['title'] = 'Add Personnel Registration'
        context['submit_text'] = 'Add Registration'
        context['verification_note'] = 'Registration numbers are stored for manual verification only. We do not automatically validate against SETA systems.'
        return context
    
    def form_valid(self, form):
        # Link to qualification
        qualification = self.get_qualification()
        response = super().form_valid(form)
        # Add to qualification's personnel
        self.object.qualifications.add(qualification)
        messages.success(self.request, f'Personnel registration added successfully. Remember to manually verify the registration number with the SETA.')
        return response
    
    def get_success_url(self):
        return reverse('academics:qualification_detail', kwargs={'pk': self.kwargs['qualification_pk']})


class StandalonePersonnelCreateView(LoginRequiredMixin, CreateView):
    """Add a new personnel registration without pre-selected qualification"""
    model = PersonnelRegistration
    template_name = 'academics/personnel_form.html'
    
    def get_form_class(self):
        from .forms import StandalonePersonnelRegistrationForm
        return StandalonePersonnelRegistrationForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Personnel Registration'
        context['submit_text'] = 'Add Registration'
        context['verification_note'] = 'Registration numbers are stored for manual verification only. We do not automatically validate against SETA systems.'
        context['standalone'] = True
        return context
    
    def form_valid(self, form):
        # Save the personnel registration
        self.object = form.save()
        # Link to selected qualifications
        qualifications = form.cleaned_data.get('qualifications', [])
        for qual in qualifications:
            self.object.qualifications.add(qual)
        # Link to selected campuses
        campuses = form.cleaned_data.get('campuses', [])
        for campus in campuses:
            self.object.campuses.add(campus)
        messages.success(self.request, f'Personnel registration added successfully for {self.object.user.get_full_name()}. Remember to manually verify the registration number with the SETA.')
        return redirect(self.get_success_url())
    
    def get_success_url(self):
        return reverse('academics:personnel_list')


class PersonnelRegistrationUpdateView(LoginRequiredMixin, UpdateView):
    """Edit personnel registration"""
    model = PersonnelRegistration
    form_class = PersonnelRegistrationForm
    template_name = 'academics/personnel_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Registration: {self.object.user.get_full_name()}'
        context['submit_text'] = 'Save Changes'
        context['verification_note'] = 'Registration numbers are stored for manual verification only.'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Personnel registration updated successfully.')
        return super().form_valid(form)
    
    def get_success_url(self):
        # Redirect to first linked qualification or list
        qual = self.object.qualifications.first()
        if qual:
            return reverse('academics:qualification_detail', kwargs={'pk': qual.pk})
        return reverse('academics:qualification_list')


class PersonnelRegistrationListView(LoginRequiredMixin, ListView):
    """List all personnel registrations"""
    model = PersonnelRegistration
    template_name = 'academics/personnel_list.html'
    context_object_name = 'registrations'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = PersonnelRegistration.objects.select_related(
            'user', 'seta'
        ).prefetch_related('qualifications').order_by('-registration_date')
        
        # Filter by personnel type
        personnel_type = self.request.GET.get('type')
        if personnel_type:
            queryset = queryset.filter(personnel_type=personnel_type)
        
        # Filter by active status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(registration_number__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['personnel_types'] = PersonnelRegistration.PERSONNEL_TYPE_CHOICES
        context['selected_type'] = self.request.GET.get('type', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class LearningMaterialListView(LoginRequiredMixin, ListView):
    """List all learning materials"""
    model = LearningMaterial
    template_name = 'academics/material_list.html'
    context_object_name = 'materials'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = LearningMaterial.objects.select_related(
            'qualification'
        ).order_by('-updated_at')
        
        # Filter by material type
        material_type = self.request.GET.get('type')
        if material_type:
            queryset = queryset.filter(material_type=material_type)
        
        # Filter by approval status
        approved = self.request.GET.get('approved')
        if approved == 'yes':
            queryset = queryset.filter(approved=True)
        elif approved == 'no':
            queryset = queryset.filter(approved=False)
        
        # Filter by current/archived
        current = self.request.GET.get('current')
        if current == 'yes':
            queryset = queryset.filter(is_current=True)
        elif current == 'no':
            queryset = queryset.filter(is_current=False)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(qualification__title__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['material_types'] = LearningMaterial.MATERIAL_TYPE_CHOICES
        context['selected_type'] = self.request.GET.get('type', '')
        context['selected_approved'] = self.request.GET.get('approved', '')
        context['selected_current'] = self.request.GET.get('current', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


# =============================================================================
# QCTO Sync Views
# =============================================================================

class QCTOSyncDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard showing QCTO sync status and detected changes"""
    template_name = 'academics/qcto_sync_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Sync status
        context['last_sync'] = QCTOSyncLog.get_last_sync()
        context['next_scheduled_sync'] = QCTOSyncLog.get_next_scheduled_sync()
        context['can_trigger_manual'] = QCTOSyncLog.can_trigger_manual_sync()
        context['manual_syncs_used'] = QCTOSyncLog.get_manual_sync_count_this_month()
        context['manual_syncs_remaining'] = 2 - context['manual_syncs_used']
        
        # Recent sync logs
        context['recent_syncs'] = QCTOSyncLog.objects.all()[:10]
        
        # Pending changes requiring review
        context['pending_changes'] = QCTOQualificationChange.objects.filter(
            status='PENDING'
        ).select_related('qualification', 'sync_log')[:20]
        
        context['pending_count'] = QCTOQualificationChange.objects.filter(status='PENDING').count()
        
        return context


@login_required
def trigger_qcto_sync(request):
    """Manually trigger a QCTO sync (max 2 per month)"""
    if request.method == 'POST':
        if not QCTOSyncLog.can_trigger_manual_sync():
            messages.error(request, 'Maximum 2 manual syncs per month. Please wait for the scheduled sync on the 15th.')
            return redirect('academics:qcto_sync_dashboard')
        
        # Create sync log
        sync_log = QCTOSyncLog.objects.create(
            trigger_type='MANUAL',
            triggered_by=request.user,
            status='PENDING'
        )
        
        # Run sync (in production, this would be async)
        try:
            from .services.qcto_sync import QCTOSyncService
            service = QCTOSyncService(sync_log)
            service.run_sync()
            messages.success(request, f'QCTO sync completed. {sync_log.qualifications_checked} qualifications checked, {sync_log.qualifications_updated} updates detected.')
        except Exception as e:
            sync_log.status = 'FAILED'
            sync_log.error_message = str(e)
            sync_log.save()
            messages.error(request, f'QCTO sync failed: {str(e)}')
        
        return redirect('academics:qcto_sync_dashboard')
    
    return redirect('academics:qcto_sync_dashboard')


@login_required
def acknowledge_qcto_change(request, pk):
    """Acknowledge a detected QCTO change"""
    change = get_object_or_404(QCTOQualificationChange, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'acknowledge':
            change.status = 'ACKNOWLEDGED'
        elif action == 'dismiss':
            change.status = 'DISMISSED'
        elif action == 'apply':
            # Apply the change to the qualification
            qualification = change.qualification
            if hasattr(qualification, change.field_name):
                setattr(qualification, change.field_name, change.new_value)
                qualification.save()
            change.status = 'APPLIED'
        
        change.reviewed_by = request.user
        change.reviewed_at = timezone.now()
        change.review_notes = notes
        change.save()
        
        messages.success(request, f'Change {change.status.lower()}.')
        return redirect('academics:qcto_sync_dashboard')
    
    return render(request, 'academics/qcto_change_review.html', {
        'change': change,
    })


# ============================================================================
# Implementation Plan Views
# ============================================================================

from .models import ImplementationPlan, ImplementationPhase, ImplementationModuleSlot, LessonPlanTemplate


@login_required
def implementation_plan_list(request, qualification_pk):
    """List all implementation plans for a qualification"""
    qualification = get_object_or_404(Qualification, pk=qualification_pk)
    implementation_plans = qualification.implementation_plans.all().order_by('-is_default', 'name')
    
    return render(request, 'academics/implementation_plan/list.html', {
        'qualification': qualification,
        'implementation_plans': implementation_plans,
    })


@login_required
def implementation_plan_create(request, qualification_pk):
    """Create a new implementation plan"""
    qualification = get_object_or_404(Qualification, pk=qualification_pk)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        delivery_mode = request.POST.get('delivery_mode', 'FULL_TIME')
        total_weeks = int(request.POST.get('total_weeks', 52))
        is_default = request.POST.get('is_default') == 'on'
        description = request.POST.get('description', '')
        
        # Session configuration
        contact_days_per_week = int(request.POST.get('contact_days_per_week', 5))
        hours_per_day = int(request.POST.get('hours_per_day', 6))
        classroom_hours_per_day = int(request.POST.get('classroom_hours_per_day', 2))
        practical_hours_per_day = int(request.POST.get('practical_hours_per_day', 4))
        
        implementation_plan = ImplementationPlan.objects.create(
            qualification=qualification,
            name=name,
            delivery_mode=delivery_mode,
            total_weeks=total_weeks,
            is_default=is_default,
            description=description,
            contact_days_per_week=contact_days_per_week,
            hours_per_day=hours_per_day,
            classroom_hours_per_day=classroom_hours_per_day,
            practical_hours_per_day=practical_hours_per_day,
            status='DRAFT',
            created_by=request.user
        )
        
        messages.success(request, f'Implementation plan "{name}" created successfully.')
        return redirect('academics:implementation_plan_detail', pk=implementation_plan.pk)
    
    return render(request, 'academics/implementation_plan/form.html', {
        'qualification': qualification,
        'is_create': True,
    })


@login_required
def implementation_plan_detail(request, pk):
    """View implementation plan with visual timeline"""
    implementation_plan = get_object_or_404(
        ImplementationPlan.objects.select_related('qualification')
        .prefetch_related(
            Prefetch('phases', queryset=ImplementationPhase.objects.prefetch_related('module_slots__module'))
        ),
        pk=pk
    )
    
    # Build Gantt chart data
    gantt_data = []
    cumulative_weeks = 0
    
    for phase in implementation_plan.phases.all():
        phase_data = {
            'id': phase.id,
            'name': phase.name,
            'type': phase.phase_type,
            'start_week': cumulative_weeks,
            'duration_weeks': phase.duration_weeks,
            'end_week': cumulative_weeks + phase.duration_weeks,
            'year_level': phase.year_level,
            'color': 'orange' if phase.is_workplace else 'blue',
            'modules': []
        }
        
        if phase.is_institutional:
            for slot in phase.module_slots.all():
                phase_data['modules'].append({
                    'id': slot.id,
                    'code': slot.module.code,
                    'title': slot.module.title,
                    'type': slot.module.module_type,
                    'days': slot.total_days,
                    'classroom_sessions': slot.classroom_sessions,
                    'practical_sessions': slot.practical_sessions,
                })
        
        gantt_data.append(phase_data)
        cumulative_weeks += phase.duration_weeks
    
    # Get modules for adding to phases
    available_modules = implementation_plan.qualification.modules.filter(
        module_type__in=['K', 'P']  # Only K and P modules for institutional phases
    ).order_by('year_level', 'sequence_order')
    
    # Calculate phase percentages for Gantt chart display
    phases = implementation_plan.phases.all()
    total_weeks = implementation_plan.total_weeks or 52
    cumulative = 0
    for phase in phases:
        phase.start_week_percent = (cumulative / total_weeks) * 100 if total_weeks > 0 else 0
        phase.width_percent = (phase.duration_weeks / total_weeks) * 100 if total_weeks > 0 else 0
        cumulative += phase.duration_weeks
    
    # Generate week range for timeline header
    total_weeks_range = range(1, total_weeks + 1)
    
    return render(request, 'academics/implementation_plan/detail.html', {
        'implementation_plan': implementation_plan,
        'gantt_data': gantt_data,
        'available_modules': available_modules,
        'total_weeks': total_weeks,
        'phases': phases,
        'total_weeks_range': total_weeks_range,
    })


@login_required
def implementation_plan_edit(request, pk):
    """Edit implementation plan settings"""
    implementation_plan = get_object_or_404(ImplementationPlan, pk=pk)
    
    if request.method == 'POST':
        implementation_plan.name = request.POST.get('name')
        implementation_plan.delivery_mode = request.POST.get('delivery_mode')
        implementation_plan.total_weeks = int(request.POST.get('total_weeks', 52))
        implementation_plan.is_default = request.POST.get('is_default') == 'on'
        implementation_plan.description = request.POST.get('description', '')
        implementation_plan.contact_days_per_week = int(request.POST.get('contact_days_per_week', 5))
        implementation_plan.hours_per_day = int(request.POST.get('hours_per_day', 6))
        implementation_plan.classroom_hours_per_day = int(request.POST.get('classroom_hours_per_day', 2))
        implementation_plan.practical_hours_per_day = int(request.POST.get('practical_hours_per_day', 4))
        implementation_plan.status = request.POST.get('status', 'DRAFT')
        implementation_plan.updated_by = request.user
        implementation_plan.save()
        
        messages.success(request, 'Implementation plan updated successfully.')
        return redirect('academics:implementation_plan_detail', pk=pk)
    
    return render(request, 'academics/implementation_plan/form.html', {
        'qualification': implementation_plan.qualification,
        'implementation_plan': implementation_plan,
        'is_create': False,
    })


@login_required
def implementation_plan_set_default(request, pk):
    """Set an implementation plan as the default for its qualification"""
    implementation_plan = get_object_or_404(ImplementationPlan, pk=pk)
    
    if request.method == 'POST':
        implementation_plan.is_default = True
        implementation_plan.save()  # save() method handles unsetting other defaults
        messages.success(request, f'"{implementation_plan.name}" is now the default implementation plan.')
    
    return redirect('academics:implementation_plan_detail', pk=pk)


@login_required
def implementation_plan_activate(request, pk):
    """Activate an implementation plan"""
    implementation_plan = get_object_or_404(ImplementationPlan, pk=pk)
    
    if request.method == 'POST':
        implementation_plan.status = 'ACTIVE'
        implementation_plan.effective_from = timezone.now().date()
        implementation_plan.save()
        messages.success(request, f'Implementation plan "{implementation_plan.name}" is now active.')
    
    return redirect('academics:implementation_plan_detail', pk=pk)


@login_required
def implementation_phase_add(request, implementation_plan_pk):
    """Add a phase to an implementation plan"""
    implementation_plan = get_object_or_404(ImplementationPlan, pk=implementation_plan_pk)
    
    if request.method == 'POST':
        phase_type = request.POST.get('phase_type')
        name = request.POST.get('name')
        duration_weeks_str = request.POST.get('duration_weeks', '')
        duration_weeks = int(duration_weeks_str) if duration_weeks_str else 4
        year_level_str = request.POST.get('year_level', '')
        year_level = int(year_level_str) if year_level_str else 1
        description = request.POST.get('description', '')
        
        # Get next sequence number
        max_seq = implementation_plan.phases.aggregate(max_seq=Max('sequence'))['max_seq'] or 0
        
        # Assign color based on phase type
        phase_colors = {
            'INDUCTION': 'purple',
            'INSTITUTIONAL': 'blue',
            'WORKPLACE': 'orange',
            'WORKPLACE_STINT': 'orange',  # Legacy
            'TRADE_TEST': 'green',
            'ASSESSMENT': 'red',
        }
        color = phase_colors.get(phase_type, 'blue')
        
        phase = ImplementationPhase.objects.create(
            implementation_plan=implementation_plan,
            phase_type=phase_type,
            name=name,
            sequence=max_seq + 1,
            duration_weeks=duration_weeks,
            year_level=year_level,
            description=description,
            color=color,
            created_by=request.user
        )
        
        messages.success(request, f'Phase "{name}" added successfully.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'phase_id': phase.id})
    
    return redirect('academics:implementation_plan_detail', pk=implementation_plan_pk)


@login_required
def implementation_phase_edit(request, pk):
    """Edit a phase"""
    phase = get_object_or_404(ImplementationPhase, pk=pk)
    
    if request.method == 'POST':
        phase.name = request.POST.get('name')
        
        # Handle phase type
        phase_type = request.POST.get('phase_type')
        if phase_type:
            phase.phase_type = phase_type
            # Update color based on phase type
            phase_colors = {
                'INDUCTION': 'purple',
                'INSTITUTIONAL': 'blue',
                'WORKPLACE': 'orange',
                'WORKPLACE_STINT': 'orange',
                'TRADE_TEST': 'green',
                'ASSESSMENT': 'red',
            }
            phase.color = phase_colors.get(phase_type, 'blue')
        
        duration_weeks_str = request.POST.get('duration_weeks', '')
        phase.duration_weeks = int(duration_weeks_str) if duration_weeks_str else phase.duration_weeks
        year_level_str = request.POST.get('year_level', '')
        phase.year_level = int(year_level_str) if year_level_str else phase.year_level
        
        # Handle sequence
        sequence_str = request.POST.get('sequence', '')
        if sequence_str:
            phase.sequence = int(sequence_str)
        
        phase.description = request.POST.get('description', '')
        phase.updated_by = request.user
        phase.save()
        
        messages.success(request, f'Phase "{phase.name}" updated.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
        return redirect('academics:implementation_plan_detail', pk=phase.implementation_plan.pk)
    
    # GET request - render edit form
    context = {
        'phase': phase,
    }
    return render(request, 'academics/implementation_plan/phase_form.html', context)


@login_required
def implementation_phase_delete(request, pk):
    """Delete a phase"""
    phase = get_object_or_404(ImplementationPhase, pk=pk)
    implementation_plan_pk = phase.implementation_plan.pk
    phase_name = phase.name
    
    if request.method == 'POST':
        phase.delete()
        messages.success(request, f'Phase "{phase_name}" deleted.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
    
    return redirect('academics:implementation_plan_detail', pk=implementation_plan_pk)


@login_required
def implementation_phase_reorder(request, implementation_plan_pk):
    """Reorder phases via AJAX"""
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        phase_order = data.get('phase_order', [])
        
        for index, phase_id in enumerate(phase_order):
            ImplementationPhase.objects.filter(pk=phase_id).update(sequence=index + 1)
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})


@login_required
def implementation_module_slot_add(request, phase_pk):
    """Add a module slot to a phase"""
    phase = get_object_or_404(ImplementationPhase, pk=phase_pk)
    
    if request.method == 'POST':
        module_id = request.POST.get('module')
        classroom_sessions = int(request.POST.get('classroom_sessions', 1))
        practical_sessions = int(request.POST.get('practical_sessions', 1))
        total_days = int(request.POST.get('total_days', 1))
        notes = request.POST.get('notes', '')
        
        module = get_object_or_404(Module, pk=module_id)
        
        # Get next sequence
        max_seq = phase.module_slots.aggregate(max_seq=models.Max('sequence'))['max_seq'] or 0
        
        slot = ImplementationModuleSlot.objects.create(
            phase=phase,
            module=module,
            sequence=max_seq + 1,
            classroom_sessions=classroom_sessions,
            practical_sessions=practical_sessions,
            total_days=total_days,
            notes=notes,
            created_by=request.user
        )
        
        messages.success(request, f'Module "{module.code}" added to phase.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'slot_id': slot.id})
    
    return redirect('academics:implementation_plan_detail', pk=phase.implementation_plan.pk)


@login_required
def implementation_module_slot_edit(request, pk):
    """Edit a module slot"""
    slot = get_object_or_404(ImplementationModuleSlot, pk=pk)
    
    if request.method == 'POST':
        slot.classroom_sessions = int(request.POST.get('classroom_sessions', 1))
        slot.practical_sessions = int(request.POST.get('practical_sessions', 1))
        slot.total_days = int(request.POST.get('total_days', 1))
        slot.notes = request.POST.get('notes', '')
        slot.updated_by = request.user
        slot.save()
        
        messages.success(request, f'Module slot updated.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
    
    return redirect('academics:implementation_plan_detail', pk=slot.phase.implementation_plan.pk)


@login_required
def implementation_module_slot_delete(request, pk):
    """Delete a module slot"""
    slot = get_object_or_404(ImplementationModuleSlot, pk=pk)
    implementation_plan_pk = slot.phase.implementation_plan.pk
    
    if request.method == 'POST':
        slot.delete()
        messages.success(request, 'Module removed from phase.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
    
    return redirect('academics:implementation_plan_detail', pk=implementation_plan_pk)


@login_required
def implementation_module_slot_reorder(request, phase_pk):
    """Reorder module slots within a phase via AJAX"""
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        slot_order = data.get('slot_order', [])
        
        for index, slot_id in enumerate(slot_order):
            ImplementationModuleSlot.objects.filter(pk=slot_id).update(sequence=index + 1)
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})


# ============================================================================
# Lesson Plan Views
# ============================================================================

@login_required
def lesson_plan_list(request, module_pk):
    """List all lesson plans for a module"""
    module = get_object_or_404(Module.objects.select_related('qualification'), pk=module_pk)
    lesson_plans = module.lesson_plans.all().order_by('session_number')
    
    return render(request, 'academics/lesson_plan/list.html', {
        'module': module,
        'lesson_plans': lesson_plans,
    })


@login_required
def lesson_plan_create(request, module_pk):
    """Create a new lesson plan"""
    module = get_object_or_404(Module.objects.select_related('qualification'), pk=module_pk)
    
    # Get next session number
    max_session = module.lesson_plans.aggregate(max_num=models.Max('session_number'))['max_num'] or 0
    next_session = max_session + 1
    
    if request.method == 'POST':
        import json
        
        lesson_plan = LessonPlanTemplate.objects.create(
            module=module,
            session_number=int(request.POST.get('session_number', next_session)),
            topic=request.POST.get('topic'),
            
            # Learning outcomes
            learning_outcomes=json.loads(request.POST.get('learning_outcomes', '[]')),
            
            # Classroom segment
            classroom_duration_minutes=int(request.POST.get('classroom_duration_minutes', 120)),
            classroom_introduction=request.POST.get('classroom_introduction', ''),
            classroom_topics=json.loads(request.POST.get('classroom_topics', '[]')),
            discussion_questions=json.loads(request.POST.get('discussion_questions', '[]')),
            key_concepts=json.loads(request.POST.get('key_concepts', '[]')),
            classroom_summary=request.POST.get('classroom_summary', ''),
            
            # Practical segment
            practical_duration_minutes=int(request.POST.get('practical_duration_minutes', 240)),
            safety_briefing=request.POST.get('safety_briefing', ''),
            practical_activities=json.loads(request.POST.get('practical_activities', '[]')),
            demonstration_notes=request.POST.get('demonstration_notes', ''),
            practical_debrief=request.POST.get('practical_debrief', ''),
            
            # Resources
            resources_required=json.loads(request.POST.get('resources_required', '[]')),
            equipment_list=json.loads(request.POST.get('equipment_list', '[]')),
            consumables_list=json.loads(request.POST.get('consumables_list', '[]')),
            
            # Assessment
            has_assessment=request.POST.get('has_assessment') == 'on',
            assessment_type=request.POST.get('assessment_type', ''),
            assessment_criteria=json.loads(request.POST.get('assessment_criteria', '[]')),
            assessment_notes=request.POST.get('assessment_notes', ''),
            
            # Facilitator guidance
            facilitator_notes=request.POST.get('facilitator_notes', ''),
            preparation_checklist=json.loads(request.POST.get('preparation_checklist', '[]')),
            common_mistakes=json.loads(request.POST.get('common_mistakes', '[]')),
            differentiation_notes=request.POST.get('differentiation_notes', ''),
            
            created_by=request.user
        )
        
        messages.success(request, f'Lesson plan for Session {lesson_plan.session_number} created.')
        return redirect('academics:lesson_plan_detail', pk=lesson_plan.pk)
    
    return render(request, 'academics/lesson_plan/form.html', {
        'module': module,
        'is_create': True,
        'next_session': next_session,
    })


@login_required
def lesson_plan_detail(request, pk):
    """View lesson plan details - printable format"""
    lesson_plan = get_object_or_404(
        LessonPlanTemplate.objects.select_related('module__qualification'),
        pk=pk
    )
    
    return render(request, 'academics/lesson_plan/detail.html', {
        'lesson_plan': lesson_plan,
        'printable': request.GET.get('print') == '1',
    })


@login_required
def lesson_plan_edit(request, pk):
    """Edit a lesson plan"""
    lesson_plan = get_object_or_404(
        LessonPlanTemplate.objects.select_related('module__qualification'),
        pk=pk
    )
    
    if request.method == 'POST':
        import json
        
        lesson_plan.topic = request.POST.get('topic')
        lesson_plan.learning_outcomes = json.loads(request.POST.get('learning_outcomes', '[]'))
        
        # Classroom segment
        lesson_plan.classroom_duration_minutes = int(request.POST.get('classroom_duration_minutes', 120))
        lesson_plan.classroom_introduction = request.POST.get('classroom_introduction', '')
        lesson_plan.classroom_topics = json.loads(request.POST.get('classroom_topics', '[]'))
        lesson_plan.discussion_questions = json.loads(request.POST.get('discussion_questions', '[]'))
        lesson_plan.key_concepts = json.loads(request.POST.get('key_concepts', '[]'))
        lesson_plan.classroom_summary = request.POST.get('classroom_summary', '')
        
        # Practical segment
        lesson_plan.practical_duration_minutes = int(request.POST.get('practical_duration_minutes', 240))
        lesson_plan.safety_briefing = request.POST.get('safety_briefing', '')
        lesson_plan.practical_activities = json.loads(request.POST.get('practical_activities', '[]'))
        lesson_plan.demonstration_notes = request.POST.get('demonstration_notes', '')
        lesson_plan.practical_debrief = request.POST.get('practical_debrief', '')
        
        # Resources
        lesson_plan.resources_required = json.loads(request.POST.get('resources_required', '[]'))
        lesson_plan.equipment_list = json.loads(request.POST.get('equipment_list', '[]'))
        lesson_plan.consumables_list = json.loads(request.POST.get('consumables_list', '[]'))
        
        # Assessment
        lesson_plan.has_assessment = request.POST.get('has_assessment') == 'on'
        lesson_plan.assessment_type = request.POST.get('assessment_type', '')
        lesson_plan.assessment_criteria = json.loads(request.POST.get('assessment_criteria', '[]'))
        lesson_plan.assessment_notes = request.POST.get('assessment_notes', '')
        
        # Facilitator guidance
        lesson_plan.facilitator_notes = request.POST.get('facilitator_notes', '')
        lesson_plan.preparation_checklist = json.loads(request.POST.get('preparation_checklist', '[]'))
        lesson_plan.common_mistakes = json.loads(request.POST.get('common_mistakes', '[]'))
        lesson_plan.differentiation_notes = request.POST.get('differentiation_notes', '')
        
        lesson_plan.updated_by = request.user
        lesson_plan.save()
        
        messages.success(request, 'Lesson plan updated successfully.')
        return redirect('academics:lesson_plan_detail', pk=pk)
    
    return render(request, 'academics/lesson_plan/form.html', {
        'module': lesson_plan.module,
        'lesson_plan': lesson_plan,
        'is_create': False,
    })


@login_required
def lesson_plan_delete(request, pk):
    """Delete a lesson plan"""
    lesson_plan = get_object_or_404(LessonPlanTemplate, pk=pk)
    module_pk = lesson_plan.module.pk
    
    if request.method == 'POST':
        lesson_plan.delete()
        messages.success(request, 'Lesson plan deleted.')
    
    return redirect('academics:lesson_plan_list', module_pk=module_pk)


@login_required
def lesson_plan_duplicate(request, pk):
    """Duplicate a lesson plan"""
    original = get_object_or_404(LessonPlanTemplate, pk=pk)
    
    if request.method == 'POST':
        # Get next session number
        max_session = original.module.lesson_plans.aggregate(
            max_num=models.Max('session_number')
        )['max_num'] or 0
        
        # Create duplicate
        duplicate = LessonPlanTemplate.objects.create(
            module=original.module,
            session_number=max_session + 1,
            topic=f"{original.topic} (Copy)",
            learning_outcomes=original.learning_outcomes,
            classroom_duration_minutes=original.classroom_duration_minutes,
            classroom_introduction=original.classroom_introduction,
            classroom_topics=original.classroom_topics,
            discussion_questions=original.discussion_questions,
            key_concepts=original.key_concepts,
            classroom_summary=original.classroom_summary,
            practical_duration_minutes=original.practical_duration_minutes,
            safety_briefing=original.safety_briefing,
            practical_activities=original.practical_activities,
            demonstration_notes=original.demonstration_notes,
            practical_debrief=original.practical_debrief,
            resources_required=original.resources_required,
            equipment_list=original.equipment_list,
            consumables_list=original.consumables_list,
            has_assessment=original.has_assessment,
            assessment_type=original.assessment_type,
            assessment_criteria=original.assessment_criteria,
            assessment_notes=original.assessment_notes,
            facilitator_notes=original.facilitator_notes,
            preparation_checklist=original.preparation_checklist,
            common_mistakes=original.common_mistakes,
            differentiation_notes=original.differentiation_notes,
            created_by=request.user
        )
        
        messages.success(request, f'Lesson plan duplicated as Session {duplicate.session_number}.')
        return redirect('academics:lesson_plan_edit', pk=duplicate.pk)
    
    return redirect('academics:lesson_plan_detail', pk=pk)


# =============================================================================
# Campus Accreditation Views
# =============================================================================

from .forms import CampusAccreditationForm


@login_required
def campus_accreditation_add(request, qualification_pk):
    """Add a new campus accreditation to a qualification"""
    qualification = get_object_or_404(Qualification, pk=qualification_pk)
    
    if request.method == 'POST':
        form = CampusAccreditationForm(request.POST, request.FILES)
        if form.is_valid():
            accreditation = form.save(commit=False)
            accreditation.qualification = qualification
            accreditation.created_by = request.user
            accreditation.save()
            
            messages.success(
                request, 
                f'Campus accreditation added for {accreditation.campus.name}.'
            )
            return redirect('academics:qualification_detail', pk=qualification.pk)
    else:
        form = CampusAccreditationForm()
    
    context = {
        'qualification': qualification,
        'form': form,
        'title': 'Add Campus Accreditation',
    }
    return render(request, 'academics/campus_accreditation_form.html', context)


@login_required
def campus_accreditation_edit(request, pk):
    """Edit an existing campus accreditation"""
    accreditation = get_object_or_404(QualificationCampusAccreditation, pk=pk)
    qualification = accreditation.qualification
    
    if request.method == 'POST':
        form = CampusAccreditationForm(request.POST, request.FILES, instance=accreditation)
        if form.is_valid():
            accreditation = form.save(commit=False)
            accreditation.modified_by = request.user
            accreditation.save()
            
            messages.success(
                request, 
                f'Campus accreditation updated for {accreditation.campus.name}.'
            )
            return redirect('academics:qualification_detail', pk=qualification.pk)
    else:
        form = CampusAccreditationForm(instance=accreditation)
    
    context = {
        'qualification': qualification,
        'form': form,
        'accreditation': accreditation,
        'title': 'Edit Campus Accreditation',
    }
    return render(request, 'academics/campus_accreditation_form.html', context)


@login_required
def campus_accreditation_delete(request, pk):
    """Delete a campus accreditation"""
    accreditation = get_object_or_404(QualificationCampusAccreditation, pk=pk)
    qualification = accreditation.qualification
    
    if request.method == 'POST':
        campus_name = accreditation.campus.name
        accreditation.delete()
        messages.success(request, f'Campus accreditation for {campus_name} deleted.')
        return redirect('academics:qualification_detail', pk=qualification.pk)
    
    context = {
        'accreditation': accreditation,
        'qualification': qualification,
    }
    return render(request, 'academics/campus_accreditation_confirm_delete.html', context)


# =============================================================================
# Cron Endpoints for Automated Tasks
# =============================================================================

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET


@csrf_exempt
@require_GET
def expire_accreditations_cron(request):
    """
    Cron endpoint to expire accreditations past their end date.
    Called daily by Vercel cron to ensure statuses are always current.
    
    URL: /api/cron/expire-accreditations/
    
    Returns JSON with count of expired records.
    """
    # Optional: Verify cron secret for security
    # cron_secret = request.headers.get('Authorization')
    # if cron_secret != f"Bearer {settings.CRON_SECRET}":
    #     return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    # Update expired statuses
    count = QualificationCampusAccreditation.objects.update_expired_statuses()
    
    return JsonResponse({
        'success': True,
        'expired_count': count,
        'message': f'Updated {count} accreditation(s) to EXPIRED status'
    })
