"""
Project Template Management Views
Admin views for managing ProjectTemplateSet and ProjectTaskTemplate
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Count, Q
from django.http import JsonResponse
from django import forms
from django.utils import timezone

from .project_templates import (
    ProjectTemplateSet,
    ProjectTaskTemplate,
    TriggerType,
    DateReferencePoint,
    RecurringInterval,
    OperationalCategory,
)
from .models import TrainingNotification
from .tasks import TaskCategory, TaskPriority


class StaffRequiredMixin(UserPassesTestMixin):
    """Require staff or superuser status"""
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


# =====================================================
# FORMS
# =====================================================

QUALIFICATION_TYPE_CHOICES = [
    ('OC', 'Occupational Certificate'),
    ('NC', 'National Certificate'),
    ('ND', 'National Diploma'),
    ('PQ', 'Part Qualification'),
    ('SP', 'Skills Programme'),
    ('LP', 'Learnership'),
]


class TemplateSetForm(forms.ModelForm):
    """Form for ProjectTemplateSet with checkbox grids for JSON fields"""
    
    project_types_choices = forms.MultipleChoiceField(
        choices=TrainingNotification.PROJECT_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'space-y-2'}),
        required=False,
        label="Project Types",
        help_text="Leave empty to apply to all project types"
    )
    funder_types_choices = forms.MultipleChoiceField(
        choices=TrainingNotification.FUNDER_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'space-y-2'}),
        required=False,
        label="Funder Types",
        help_text="Leave empty to apply to all funder types"
    )
    qualification_types_choices = forms.MultipleChoiceField(
        choices=QUALIFICATION_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'space-y-2'}),
        required=False,
        label="Qualification Types",
        help_text="Leave empty to apply to all qualification types"
    )
    
    class Meta:
        model = ProjectTemplateSet
        fields = [
            'name', 'description', 'parent_set',
            'min_duration_months', 'max_duration_months',
            'auto_apply', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500'
            }),
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500'
            }),
            'min_duration_months': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500',
                'min': 1
            }),
            'max_duration_months': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500',
                'min': 1
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent_set'].queryset = ProjectTemplateSet.objects.filter(is_active=True)
        self.fields['parent_set'].required = False
        self.fields['parent_set'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500'
        })
        
        # Populate checkbox fields from instance JSON
        if self.instance.pk:
            self.fields['project_types_choices'].initial = self.instance.project_types or []
            self.fields['funder_types_choices'].initial = self.instance.funder_types or []
            self.fields['qualification_types_choices'].initial = self.instance.qualification_types or []
    
    def clean(self):
        cleaned_data = super().clean()
        min_dur = cleaned_data.get('min_duration_months')
        max_dur = cleaned_data.get('max_duration_months')
        
        if min_dur and max_dur and min_dur > max_dur:
            raise forms.ValidationError("Minimum duration cannot be greater than maximum duration.")
        
        # Check for circular parent reference
        parent = cleaned_data.get('parent_set')
        if parent and self.instance.pk:
            current = parent
            while current:
                if current.pk == self.instance.pk:
                    raise forms.ValidationError("Cannot set parent to create a circular reference.")
                current = current.parent_set
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.project_types = self.cleaned_data.get('project_types_choices', [])
        instance.funder_types = self.cleaned_data.get('funder_types_choices', [])
        instance.qualification_types = self.cleaned_data.get('qualification_types_choices', [])
        if commit:
            instance.save()
        return instance


class TaskTemplateForm(forms.ModelForm):
    """Form for ProjectTaskTemplate"""
    
    class Meta:
        model = ProjectTaskTemplate
        fields = [
            'name', 'trigger_type',
            'trigger_status',
            'date_reference', 'offset_days',
            'recurring_interval', 'recurring_start_status', 'recurring_end_status',
            'task_title_template', 'task_description_template',
            'task_category', 'task_priority', 'operational_category',
            'assigned_role', 'fallback_campus_role',
            'due_days_offset',
            'recalculate_on_date_change', 'sequence', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500',
                'placeholder': 'e.g., Send Registration Reminder'
            }),
            'task_title_template': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500',
                'placeholder': 'e.g., Register learners for {reference_number}'
            }),
            'task_description_template': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500',
                'placeholder': 'Use {reference_number}, {title}, {qualification}, {learner_count}, {client_name}, {due_date}'
            }),
            'fallback_campus_role': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500',
                'placeholder': 'e.g., REGISTRAR'
            }),
            'offset_days': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500'
            }),
            'due_days_offset': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500',
                'min': 1
            }),
            'sequence': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500',
                'min': 1
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add classes to all select fields
        select_class = 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500 bg-white'
        for field_name in ['trigger_type', 'trigger_status', 'date_reference', 
                           'recurring_interval', 'recurring_start_status', 'recurring_end_status',
                           'task_category', 'task_priority', 'operational_category', 'assigned_role']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({'class': select_class})


# =====================================================
# TEMPLATE SET VIEWS
# =====================================================

class TemplateSetListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    """List all project template sets"""
    model = ProjectTemplateSet
    template_name = 'admin/templates/templateset_list.html'
    context_object_name = 'template_sets'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = ProjectTemplateSet.objects.select_related('parent_set', 'created_by')
        queryset = queryset.annotate(
            template_count=Count('templates', filter=Q(templates__is_active=True))
        )
        
        # Search
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Filter by active status
        status = self.request.GET.get('status', '')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'archived':
            queryset = queryset.filter(is_active=False)
        
        # Filter by project type
        project_type = self.request.GET.get('project_type', '')
        if project_type:
            queryset = queryset.filter(project_types__contains=[project_type])
        
        # Filter by funder type
        funder_type = self.request.GET.get('funder_type', '')
        if funder_type:
            queryset = queryset.filter(funder_types__contains=[funder_type])
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['project_type_filter'] = self.request.GET.get('project_type', '')
        context['funder_type_filter'] = self.request.GET.get('funder_type', '')
        context['total_count'] = ProjectTemplateSet.objects.count()
        context['active_count'] = ProjectTemplateSet.objects.filter(is_active=True).count()
        
        # Choices for filters
        context['project_type_choices'] = TrainingNotification.PROJECT_TYPE_CHOICES
        context['funder_type_choices'] = TrainingNotification.FUNDER_CHOICES
        
        return context


class TemplateSetDetailView(LoginRequiredMixin, StaffRequiredMixin, DetailView):
    """View template set details with own and inherited templates"""
    model = ProjectTemplateSet
    template_name = 'admin/templates/templateset_detail.html'
    context_object_name = 'template_set'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Own templates
        own_templates = self.object.templates.all().order_by('trigger_type', 'sequence')
        context['own_templates'] = own_templates
        own_template_names = set(t.name for t in own_templates)
        
        # Inherited templates (from parent chain, excluding overridden)
        inherited_templates = []
        if self.object.parent_set:
            all_templates = self.object.parent_set.get_all_templates()
            inherited_templates = [
                t for name, t in all_templates.items()
                if name not in own_template_names
            ]
        context['inherited_templates'] = inherited_templates
        
        # Child sets
        context['child_sets'] = self.object.child_sets.all().order_by('name')
        
        # Stats
        context['stats'] = {
            'total_templates': own_templates.count(),
            'active_templates': own_templates.filter(is_active=True).count(),
            'status_triggers': own_templates.filter(trigger_type='status').count(),
            'date_triggers': own_templates.filter(trigger_type='date').count(),
            'recurring_triggers': own_templates.filter(trigger_type='recurring').count(),
        }
        
        # Choices for display
        context['project_type_choices'] = dict(TrainingNotification.PROJECT_TYPE_CHOICES)
        context['funder_type_choices'] = dict(TrainingNotification.FUNDER_CHOICES)
        context['qualification_type_choices'] = dict(QUALIFICATION_TYPE_CHOICES)
        context['trigger_type_choices'] = dict(TriggerType.choices)
        
        return context


class TemplateSetCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Create a new project template set"""
    model = ProjectTemplateSet
    form_class = TemplateSetForm
    template_name = 'admin/templates/templateset_form.html'
    
    def get_success_url(self):
        return reverse('admin:templateset_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_create'] = True
        context['project_type_choices'] = TrainingNotification.PROJECT_TYPE_CHOICES
        context['funder_type_choices'] = TrainingNotification.FUNDER_CHOICES
        context['qualification_type_choices'] = QUALIFICATION_TYPE_CHOICES
        return context
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Template set "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class TemplateSetUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Update a project template set"""
    model = ProjectTemplateSet
    form_class = TemplateSetForm
    template_name = 'admin/templates/templateset_form.html'
    
    def get_success_url(self):
        return reverse('admin:templateset_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_create'] = False
        context['project_type_choices'] = TrainingNotification.PROJECT_TYPE_CHOICES
        context['funder_type_choices'] = TrainingNotification.FUNDER_CHOICES
        context['qualification_type_choices'] = QUALIFICATION_TYPE_CHOICES
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Template set "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class TemplateSetArchiveView(LoginRequiredMixin, StaffRequiredMixin, View):
    """Archive (soft delete) a project template set"""
    
    def get(self, request, pk):
        template_set = get_object_or_404(ProjectTemplateSet, pk=pk)
        
        # Count affected items
        task_count = template_set.templates.count()
        child_count = template_set.child_sets.count()
        
        context = {
            'template_set': template_set,
            'task_count': task_count,
            'child_count': child_count,
        }
        return render(request, 'admin/templates/templateset_confirm_archive.html', context)
    
    def post(self, request, pk):
        template_set = get_object_or_404(ProjectTemplateSet, pk=pk)
        name = template_set.name
        
        # Soft delete by setting is_active to False
        template_set.is_active = False
        template_set.save()
        
        # Also archive all templates in the set
        template_set.templates.update(is_active=False)
        
        messages.success(request, f'Template set "{name}" has been archived.')
        return redirect('admin:templateset_list')


class TemplateSetRestoreView(LoginRequiredMixin, StaffRequiredMixin, View):
    """Restore an archived template set"""
    
    def post(self, request, pk):
        template_set = get_object_or_404(ProjectTemplateSet, pk=pk)
        template_set.is_active = True
        template_set.save()
        
        messages.success(request, f'Template set "{template_set.name}" has been restored.')
        return redirect('admin:templateset_detail', pk=pk)


# =====================================================
# TASK TEMPLATE VIEWS
# =====================================================

class TaskTemplateCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Create a new task template within a template set"""
    model = ProjectTaskTemplate
    form_class = TaskTemplateForm
    template_name = 'admin/templates/tasktemplate_form.html'
    
    def get_template_set(self):
        return get_object_or_404(ProjectTemplateSet, pk=self.kwargs['set_pk'])
    
    def get_success_url(self):
        return reverse('admin:templateset_detail', kwargs={'pk': self.kwargs['set_pk']})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['template_set'] = self.get_template_set()
        context['is_create'] = True
        context['trigger_types'] = TriggerType.choices
        context['date_references'] = DateReferencePoint.choices
        context['recurring_intervals'] = RecurringInterval.choices
        context['operational_categories'] = OperationalCategory.choices
        context['task_categories'] = TaskCategory.choices
        context['task_priorities'] = TaskPriority.choices
        context['role_choices'] = ProjectTaskTemplate.ROLE_CHOICES
        context['status_choices'] = ProjectTaskTemplate.TRIGGER_STATUS_CHOICES
        return context
    
    def form_valid(self, form):
        form.instance.template_set = self.get_template_set()
        messages.success(self.request, f'Task template "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class TaskTemplateUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Update a task template"""
    model = ProjectTaskTemplate
    form_class = TaskTemplateForm
    template_name = 'admin/templates/tasktemplate_form.html'
    
    def get_success_url(self):
        return reverse('admin:templateset_detail', kwargs={'pk': self.object.template_set_id})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['template_set'] = self.object.template_set
        context['is_create'] = False
        context['trigger_types'] = TriggerType.choices
        context['date_references'] = DateReferencePoint.choices
        context['recurring_intervals'] = RecurringInterval.choices
        context['operational_categories'] = OperationalCategory.choices
        context['task_categories'] = TaskCategory.choices
        context['task_priorities'] = TaskPriority.choices
        context['role_choices'] = ProjectTaskTemplate.ROLE_CHOICES
        context['status_choices'] = ProjectTaskTemplate.TRIGGER_STATUS_CHOICES
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Task template "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class TaskTemplateArchiveView(LoginRequiredMixin, StaffRequiredMixin, View):
    """Archive a task template"""
    
    def get(self, request, pk):
        task_template = get_object_or_404(ProjectTaskTemplate, pk=pk)
        context = {
            'task_template': task_template,
            'template_set': task_template.template_set,
        }
        return render(request, 'admin/templates/tasktemplate_confirm_archive.html', context)
    
    def post(self, request, pk):
        task_template = get_object_or_404(ProjectTaskTemplate, pk=pk)
        name = task_template.name
        template_set_id = task_template.template_set_id
        
        task_template.is_active = False
        task_template.save()
        
        messages.success(request, f'Task template "{name}" has been archived.')
        return redirect('admin:templateset_detail', pk=template_set_id)


class TaskTemplateRestoreView(LoginRequiredMixin, StaffRequiredMixin, View):
    """Restore an archived task template"""
    
    def post(self, request, pk):
        task_template = get_object_or_404(ProjectTaskTemplate, pk=pk)
        task_template.is_active = True
        task_template.save()
        
        messages.success(request, f'Task template "{task_template.name}" has been restored.')
        return redirect('admin:templateset_detail', pk=task_template.template_set_id)
