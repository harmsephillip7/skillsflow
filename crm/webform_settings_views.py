"""
Web Form Settings Views
UI for managing web form integrations (Gravity Forms, etc.)
"""
import json
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction

from .models import WebFormSource, WebFormMapping, WebFormSubmission, LeadSource, Pipeline
from tenants.models import Brand, Campus
from academics.models import Qualification
from core.models import User


class WebFormSourceListView(LoginRequiredMixin, ListView):
    """List all web form sources."""
    model = WebFormSource
    template_name = 'crm/webform/source_list.html'
    context_object_name = 'sources'
    
    def get_queryset(self):
        return WebFormSource.objects.select_related(
            'brand', 'default_campus', 'default_lead_source'
        ).prefetch_related('form_mappings').order_by('brand__name', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['brands'] = Brand.objects.filter(is_active=True)
        context['campuses'] = Campus.objects.filter(is_active=True).select_related('brand')
        context['lead_sources'] = LeadSource.objects.filter(is_active=True)
        return context


class WebFormSourceCreateView(LoginRequiredMixin, CreateView):
    """Create a new web form source."""
    model = WebFormSource
    template_name = 'crm/webform/source_form.html'
    fields = ['name', 'domain', 'description', 'brand', 'default_campus', 'default_lead_source', 'is_active']
    success_url = reverse_lazy('crm:webform_sources')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['brands'] = Brand.objects.filter(is_active=True)
        context['campuses'] = Campus.objects.filter(is_active=True).select_related('brand')
        context['lead_sources'] = LeadSource.objects.filter(is_active=True)
        context['is_create'] = True
        return context
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f"Web form source '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class WebFormSourceUpdateView(LoginRequiredMixin, UpdateView):
    """Update a web form source."""
    model = WebFormSource
    template_name = 'crm/webform/source_form.html'
    fields = ['name', 'domain', 'description', 'brand', 'default_campus', 'default_lead_source', 'is_active']
    success_url = reverse_lazy('crm:webform_sources')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['brands'] = Brand.objects.filter(is_active=True)
        context['campuses'] = Campus.objects.filter(is_active=True).select_related('brand')
        context['lead_sources'] = LeadSource.objects.filter(is_active=True)
        context['is_create'] = False
        return context
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f"Web form source '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


class WebFormSourceDetailView(LoginRequiredMixin, DetailView):
    """View web form source details and manage mappings."""
    model = WebFormSource
    template_name = 'crm/webform/source_detail.html'
    context_object_name = 'source'
    
    def get_queryset(self):
        return WebFormSource.objects.select_related(
            'brand', 'default_campus', 'default_lead_source'
        ).prefetch_related(
            'form_mappings__campus',
            'form_mappings__qualification',
            'form_mappings__pipeline',
            'form_mappings__auto_assign_to'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['campuses'] = Campus.objects.filter(is_active=True).select_related('brand')
        context['qualifications'] = Qualification.objects.filter(is_active=True).order_by('title')
        context['pipelines'] = Pipeline.objects.filter(is_active=True)
        context['users'] = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        context['lead_field_choices'] = WebFormMapping.LEAD_FIELD_CHOICES
        context['recent_submissions'] = WebFormSubmission.objects.filter(
            source=self.object
        ).select_related('form_mapping', 'lead').order_by('-created_at')[:20]
        return context


class WebFormSourceDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a web form source."""
    model = WebFormSource
    success_url = reverse_lazy('crm:webform_sources')
    
    def delete(self, request, *args, **kwargs):
        source = self.get_object()
        messages.success(request, f"Web form source '{source.name}' deleted.")
        return super().delete(request, *args, **kwargs)


class WebFormSourceRegenerateSecretView(LoginRequiredMixin, View):
    """Regenerate webhook secret for a source."""
    
    def post(self, request, pk):
        source = get_object_or_404(WebFormSource, pk=pk)
        new_secret = source.regenerate_secret()
        messages.success(request, f"Webhook secret regenerated for '{source.name}'.")
        return redirect('crm:webform_source_detail', pk=pk)


class WebFormMappingCreateView(LoginRequiredMixin, View):
    """Create a new form mapping (AJAX)."""
    
    def post(self, request, source_pk):
        source = get_object_or_404(WebFormSource, pk=source_pk)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST
        
        # Parse field mapping
        field_mapping = data.get('field_mapping', {})
        if isinstance(field_mapping, str):
            try:
                field_mapping = json.loads(field_mapping)
            except json.JSONDecodeError:
                field_mapping = {}
        
        # Create mapping
        mapping = WebFormMapping.objects.create(
            source=source,
            form_id=data.get('form_id', ''),
            form_name=data.get('form_name', ''),
            campus_id=data.get('campus') or None,
            qualification_id=data.get('qualification') or None,
            pipeline_id=data.get('pipeline') or None,
            lead_type=data.get('lead_type', 'ADULT'),
            auto_assign_to_id=data.get('auto_assign_to') or None,
            field_mapping=field_mapping,
            is_active=data.get('is_active', True),
            created_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'mapping_id': str(mapping.id),
            'message': f"Form mapping '{mapping.form_name}' created."
        })


class WebFormMappingUpdateView(LoginRequiredMixin, View):
    """Update a form mapping (AJAX)."""
    
    def post(self, request, pk):
        mapping = get_object_or_404(WebFormMapping, pk=pk)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = request.POST
        
        # Parse field mapping
        field_mapping = data.get('field_mapping', mapping.field_mapping)
        if isinstance(field_mapping, str):
            try:
                field_mapping = json.loads(field_mapping)
            except json.JSONDecodeError:
                field_mapping = mapping.field_mapping
        
        # Update fields
        mapping.form_id = data.get('form_id', mapping.form_id)
        mapping.form_name = data.get('form_name', mapping.form_name)
        mapping.campus_id = data.get('campus') or None
        mapping.qualification_id = data.get('qualification') or None
        mapping.pipeline_id = data.get('pipeline') or None
        mapping.lead_type = data.get('lead_type', mapping.lead_type)
        mapping.auto_assign_to_id = data.get('auto_assign_to') or None
        mapping.field_mapping = field_mapping
        mapping.is_active = data.get('is_active', mapping.is_active)
        mapping.updated_by = request.user
        mapping.save()
        
        return JsonResponse({
            'success': True,
            'message': f"Form mapping '{mapping.form_name}' updated."
        })


class WebFormMappingDeleteView(LoginRequiredMixin, View):
    """Delete a form mapping (AJAX)."""
    
    def post(self, request, pk):
        mapping = get_object_or_404(WebFormMapping, pk=pk)
        source_pk = mapping.source.pk
        name = mapping.form_name
        mapping.delete()
        
        return JsonResponse({
            'success': True,
            'message': f"Form mapping '{name}' deleted."
        })


class WebFormSubmissionListView(LoginRequiredMixin, ListView):
    """View recent form submissions."""
    model = WebFormSubmission
    template_name = 'crm/webform/submission_list.html'
    context_object_name = 'submissions'
    paginate_by = 50
    
    def get_queryset(self):
        qs = WebFormSubmission.objects.select_related(
            'source', 'form_mapping', 'lead'
        ).order_by('-created_at')
        
        # Filter by source if specified
        source_id = self.request.GET.get('source')
        if source_id:
            qs = qs.filter(source_id=source_id)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        
        # Filter by date range
        from_date = self.request.GET.get('from_date')
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        
        to_date = self.request.GET.get('to_date')
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sources'] = WebFormSource.objects.all()
        context['status_choices'] = WebFormSubmission.STATUS_CHOICES
        context['source_filter'] = self.request.GET.get('source', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['from_date'] = self.request.GET.get('from_date', '')
        context['to_date'] = self.request.GET.get('to_date', '')
        
        # Calculate stats for the filtered queryset
        qs = self.get_queryset()
        context['total_count'] = qs.count()
        context['success_count'] = qs.filter(status='SUCCESS').count()
        context['duplicate_count'] = qs.filter(status='DUPLICATE').count()
        context['failed_count'] = qs.filter(status='FAILED').count()
        
        return context
