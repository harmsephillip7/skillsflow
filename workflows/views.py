"""
SOP (Standard Operating Procedures) Views

Views for managing SOPs, tasks, and business process flows.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import models
from django.urls import reverse_lazy
from .models import (
    SOPCategory, SOP, SOPStep, Task,
    ProcessFlow, ProcessStage, ProcessStageTransition, TransitionAttemptLog
)


# =====================================================
# SOP VIEWS (User-facing)
# =====================================================

class SOPListView(LoginRequiredMixin, ListView):
    """Browse all published SOPs grouped by category."""
    template_name = 'sops/sop_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return SOPCategory.objects.filter(
            is_active=True
        ).prefetch_related(
            models.Prefetch(
                'sops',
                queryset=SOP.objects.filter(is_published=True)
            )
        ).order_by('sort_order', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Standard Operating Procedures'
        
        # Quick stats
        context['total_sops'] = SOP.objects.filter(is_published=True).count()
        context['total_categories'] = SOPCategory.objects.filter(is_active=True).count()
        
        return context


class SOPCategoryView(LoginRequiredMixin, DetailView):
    """View all SOPs in a specific category."""
    template_name = 'sops/sop_category.html'
    context_object_name = 'category'
    slug_field = 'code'
    slug_url_kwarg = 'category_code'
    
    def get_queryset(self):
        return SOPCategory.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'{self.object.name} Procedures'
        context['sops'] = self.object.sops.filter(
            is_published=True
        ).order_by('name')
        return context


class SOPDetailView(LoginRequiredMixin, DetailView):
    """View detailed SOP with all steps and clickable links."""
    template_name = 'sops/sop_detail.html'
    context_object_name = 'sop'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    
    def get_queryset(self):
        return SOP.objects.filter(is_published=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.object.name
        context['steps'] = self.object.get_steps()
        
        # Get other SOPs in same category for sidebar
        context['related_sops'] = SOP.objects.filter(
            category=self.object.category,
            is_published=True
        ).exclude(pk=self.object.pk)[:5]
        
        return context


# =====================================================
# TASK VIEWS
# =====================================================

class TaskListView(LoginRequiredMixin, ListView):
    """View all tasks assigned to the current user."""
    template_name = 'workflows/task_list.html'
    context_object_name = 'tasks'
    paginate_by = 20
    
    def get_queryset(self):
        return Task.objects.filter(
            assigned_to=self.request.user
        ).select_related('sop', 'sop_step').order_by('-priority', 'due_date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group tasks by status
        all_tasks = Task.objects.filter(assigned_to=self.request.user)
        context['pending_count'] = all_tasks.filter(status='pending').count()
        context['in_progress_count'] = all_tasks.filter(status='in_progress').count()
        context['completed_count'] = all_tasks.filter(status='completed').count()
        context['overdue_count'] = all_tasks.filter(status='overdue').count()
        context['page_title'] = 'My Tasks'
        
        return context


class TaskDetailView(LoginRequiredMixin, DetailView):
    """View details of a specific task."""
    template_name = 'workflows/task_detail.html'
    context_object_name = 'task'
    
    def get_queryset(self):
        return Task.objects.filter(assigned_to=self.request.user)


@login_required
@require_POST
def complete_task(request, pk):
    """Mark a task as completed."""
    from django.utils import timezone
    
    task = get_object_or_404(Task, pk=pk, assigned_to=request.user)
    notes = request.POST.get('notes', '')
    
    task.status = 'completed'
    task.completed_at = timezone.now()
    task.completed_by = request.user
    task.notes = notes
    task.save()
    
    messages.success(request, f'Task "{task.name}" marked as completed.')
    
    # Return JSON for HTMX, redirect otherwise
    if request.headers.get('HX-Request'):
        return JsonResponse({'status': 'success', 'message': 'Task completed'})
    
    return redirect('workflows:task_list')


# =====================================================
# SOP ADMIN VIEWS
# =====================================================

class SOPAdminListView(LoginRequiredMixin, ListView):
    """Admin: List all SOPs for management."""
    template_name = 'admin/sops/sop_admin_list.html'
    context_object_name = 'sops'
    paginate_by = 20
    
    def get_queryset(self):
        qs = SOP.objects.all().select_related(
            'category', 'owner'
        ).prefetch_related('steps').order_by('category', 'name')
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category__code=category)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status == 'published':
            qs = qs.filter(is_published=True)
        elif status == 'draft':
            qs = qs.filter(is_published=False)
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Manage SOPs'
        context['categories'] = SOPCategory.objects.all()
        
        # Stats
        context['total_sops'] = SOP.objects.count()
        context['published_count'] = SOP.objects.filter(is_published=True).count()
        context['draft_count'] = SOP.objects.filter(is_published=False).count()
        
        return context


class SOPCreateView(LoginRequiredMixin, CreateView):
    """Admin: Create a new SOP."""
    model = SOP
    template_name = 'admin/sops/sop_form.html'
    fields = ['category', 'name', 'code', 'description', 'purpose', 'owner',
              'version', 'effective_date', 'icon', 'estimated_duration', 'target_roles']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create SOP'
        context['categories'] = SOPCategory.objects.filter(is_active=True)
        return context
    
    def get_success_url(self):
        return reverse_lazy('workflows:sop_update', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f'SOP "{form.instance.name}" created. Now add steps.')
        return super().form_valid(form)


class SOPUpdateView(LoginRequiredMixin, UpdateView):
    """Admin: Edit an SOP and its steps."""
    model = SOP
    template_name = 'admin/sops/sop_edit.html'
    fields = ['category', 'name', 'code', 'description', 'purpose', 'owner',
              'version', 'effective_date', 'icon', 'estimated_duration', 'target_roles']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Edit: {self.object.name}'
        context['categories'] = SOPCategory.objects.filter(is_active=True)
        context['steps'] = self.object.steps.all().order_by('order')
        return context
    
    def get_success_url(self):
        return reverse_lazy('workflows:sop_update', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f'SOP "{form.instance.name}" updated.')
        return super().form_valid(form)


@login_required
@require_POST
def sop_delete(request, pk):
    """Admin: Delete an SOP."""
    sop = get_object_or_404(SOP, pk=pk)
    name = sop.name
    sop.delete()
    messages.success(request, f'SOP "{name}" deleted.')
    return redirect('workflows:sop_admin_list')


@login_required
@require_POST
def sop_toggle_publish(request, pk):
    """Admin: Toggle SOP published status."""
    sop = get_object_or_404(SOP, pk=pk)
    sop.is_published = not sop.is_published
    sop.save()
    
    status = 'published' if sop.is_published else 'unpublished'
    messages.success(request, f'SOP "{sop.name}" has been {status}.')
    
    if request.headers.get('HX-Request'):
        return JsonResponse({'status': 'success', 'is_published': sop.is_published})
    
    return redirect('workflows:sop_update', pk=pk)


# =====================================================
# SOP STEP MANAGEMENT
# =====================================================

@login_required
@require_POST
def sop_step_create(request, sop_pk):
    """Admin: Create a new step for an SOP."""
    sop = get_object_or_404(SOP, pk=sop_pk)
    
    # Get max order
    max_order = sop.steps.aggregate(max_order=models.Max('order'))['max_order'] or 0
    
    step = SOPStep.objects.create(
        sop=sop,
        order=max_order + 1,
        title=request.POST.get('title', 'New Step'),
        description=request.POST.get('description', ''),
        app_url_name=request.POST.get('app_url_name', ''),
        app_url_label=request.POST.get('app_url_label', ''),
        external_url=request.POST.get('external_url', ''),
        external_url_label=request.POST.get('external_url_label', ''),
        responsible_role=request.POST.get('responsible_role', ''),
        tips=request.POST.get('tips', ''),
        is_optional=request.POST.get('is_optional') == 'on',
    )
    
    if request.headers.get('HX-Request'):
        return render(request, 'admin/sops/partials/step_row.html', {'step': step, 'sop': sop})
    
    messages.success(request, f'Step "{step.title}" added.')
    return redirect('workflows:sop_update', pk=sop_pk)


@login_required
@require_POST
def sop_step_update(request, pk):
    """Admin: Update an SOP step."""
    step = get_object_or_404(SOPStep, pk=pk)
    
    step.order = int(request.POST.get('order', step.order))
    step.title = request.POST.get('title', step.title)
    step.description = request.POST.get('description', step.description)
    step.app_url_name = request.POST.get('app_url_name', step.app_url_name)
    step.app_url_label = request.POST.get('app_url_label', step.app_url_label)
    step.external_url = request.POST.get('external_url', step.external_url)
    step.external_url_label = request.POST.get('external_url_label', step.external_url_label)
    step.responsible_role = request.POST.get('responsible_role', step.responsible_role)
    step.tips = request.POST.get('tips', step.tips)
    step.is_optional = request.POST.get('is_optional') == 'on'
    step.save()
    
    if request.headers.get('HX-Request'):
        return render(request, 'admin/sops/partials/step_row.html', {'step': step, 'sop': step.sop})
    
    messages.success(request, f'Step "{step.title}" updated.')
    return redirect('workflows:sop_update', pk=step.sop.pk)


@login_required
@require_POST
def sop_step_delete(request, pk):
    """Admin: Delete an SOP step."""
    step = get_object_or_404(SOPStep, pk=pk)
    sop_pk = step.sop.pk
    title = step.title
    step.delete()
    
    if request.headers.get('HX-Request'):
        return JsonResponse({'status': 'deleted'})
    
    messages.success(request, f'Step "{title}" deleted.')
    return redirect('workflows:sop_update', pk=sop_pk)


# =====================================================
# SOP CATEGORY ADMIN
# =====================================================

class SOPCategoryAdminListView(LoginRequiredMixin, ListView):
    """Admin: List all SOP categories."""
    template_name = 'admin/sops/category_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return SOPCategory.objects.annotate(
            sop_count=models.Count('sops')
        ).order_by('sort_order', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'SOP Categories'
        return context


class SOPCategoryCreateView(LoginRequiredMixin, CreateView):
    """Admin: Create a new SOP category."""
    model = SOPCategory
    template_name = 'admin/sops/category_form.html'
    fields = ['name', 'code', 'description', 'icon', 'color', 'sort_order']
    success_url = reverse_lazy('workflows:category_admin_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create Category'
        return context


class SOPCategoryUpdateView(LoginRequiredMixin, UpdateView):
    """Admin: Edit an SOP category."""
    model = SOPCategory
    template_name = 'admin/sops/category_form.html'
    fields = ['name', 'code', 'description', 'icon', 'color', 'sort_order', 'is_active']
    success_url = reverse_lazy('workflows:category_admin_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Edit: {self.object.name}'
        return context


# =====================================================
# BUSINESS PROCESS FLOW ADMIN VIEWS
# =====================================================

class ProcessFlowListView(LoginRequiredMixin, ListView):
    """List all process flows."""
    template_name = 'admin/workflows/processflow_list.html'
    context_object_name = 'process_flows'
    paginate_by = 20
    
    def get_queryset(self):
        return ProcessFlow.objects.all().annotate(
            stage_count=models.Count('stages'),
            transition_count=models.Count('transitions')
        ).order_by('-is_active', 'entity_type', '-version')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Business Process Flows'
        context['entity_types'] = ProcessFlow.objects.values_list('entity_type', flat=True).distinct()
        return context


class ProcessFlowDetailView(LoginRequiredMixin, DetailView):
    """View details of a process flow with transition matrix."""
    template_name = 'admin/workflows/processflow_detail.html'
    context_object_name = 'process_flow'
    model = ProcessFlow
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all stages ordered by sequence
        stages = self.object.stages.all().order_by('sequence_order')
        context['stages'] = stages
        
        # Build transition matrix
        transitions = self.object.transitions.all().select_related('from_stage', 'to_stage')
        
        # Create a lookup dict
        transition_map = {}
        for t in transitions:
            key = f"{t.from_stage.code}:{t.to_stage.code}"
            transition_map[key] = t
        
        # Build matrix for template
        matrix = []
        for from_stage in stages:
            row = {'stage': from_stage, 'transitions': []}
            for to_stage in stages:
                key = f"{from_stage.code}:{to_stage.code}"
                transition = transition_map.get(key)
                row['transitions'].append({
                    'to_stage': to_stage,
                    'transition': transition,
                    'is_same': from_stage.code == to_stage.code,
                })
            matrix.append(row)
        
        context['transition_matrix'] = matrix
        context['page_title'] = f'Process Flow: {self.object.name}'
        
        # Recent transition attempts
        context['recent_attempts'] = TransitionAttemptLog.objects.filter(
            entity_type=self.object.entity_type
        ).order_by('-attempted_at')[:20]
        
        return context


class ProcessFlowCreateView(LoginRequiredMixin, CreateView):
    """Create a new process flow."""
    model = ProcessFlow
    template_name = 'admin/workflows/processflow_form.html'
    fields = ['entity_type', 'name', 'description']
    
    def get_success_url(self):
        return reverse_lazy('workflows:processflow_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        form.instance.version = 1
        form.instance.is_active = True
        messages.success(self.request, 'Process flow created successfully.')
        return super().form_valid(form)


class ProcessStageEditView(LoginRequiredMixin, TemplateView):
    """Edit stages for a process flow (HTMX-powered)."""
    template_name = 'admin/workflows/processstage_edit.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        process_flow = get_object_or_404(ProcessFlow, pk=self.kwargs['pk'])
        context['process_flow'] = process_flow
        context['stages'] = process_flow.stages.all().order_by('sequence_order')
        context['stage_types'] = ProcessStage.STAGE_TYPE_CHOICES
        context['colors'] = [
            ('primary', 'Primary'),
            ('secondary', 'Secondary'),
            ('success', 'Success'),
            ('danger', 'Danger'),
            ('warning', 'Warning'),
            ('info', 'Info'),
            ('dark', 'Dark'),
        ]
        context['page_title'] = f'Edit Stages: {process_flow.name}'
        return context


@login_required
@require_POST
def processflow_toggle_active(request, pk):
    """Toggle the active status of a process flow."""
    process_flow = get_object_or_404(ProcessFlow, pk=pk)
    
    if process_flow.is_active:
        process_flow.is_active = False
        messages.warning(request, f'Process flow "{process_flow.name}" has been deactivated.')
    else:
        # Deactivate other flows for the same entity type
        ProcessFlow.objects.filter(
            entity_type=process_flow.entity_type,
            is_active=True
        ).update(is_active=False)
        process_flow.is_active = True
        messages.success(request, f'Process flow "{process_flow.name}" has been activated.')
    
    process_flow.save()
    
    if request.headers.get('HX-Request'):
        return JsonResponse({'status': 'success'})
    
    return redirect('workflows:processflow_detail', pk=pk)


@login_required
@require_POST
def stage_create(request, pk):
    """Create a new stage for a process flow (HTMX)."""
    process_flow = get_object_or_404(ProcessFlow, pk=pk)
    
    code = request.POST.get('code', '').upper()
    name = request.POST.get('name', '')
    stage_type = request.POST.get('stage_type', 'intermediate')
    color = request.POST.get('color', 'primary')
    
    if not code or not name:
        return JsonResponse({'error': 'Code and name are required'}, status=400)
    
    # Get max sequence order
    max_order = process_flow.stages.aggregate(
        max_order=models.Max('sequence_order')
    )['max_order'] or 0
    
    stage = ProcessStage.objects.create(
        process_flow=process_flow,
        code=code,
        name=name,
        stage_type=stage_type,
        color=color,
        sequence_order=max_order + 10,
    )
    
    if request.headers.get('HX-Request'):
        # Return the new stage row HTML
        return render(request, 'admin/workflows/partials/stage_row.html', {'stage': stage})
    
    return JsonResponse({'status': 'success', 'stage_id': stage.id})


@login_required
@require_POST
def stage_update(request, pk):
    """Update a stage (HTMX)."""
    stage = get_object_or_404(ProcessStage, pk=pk)
    
    stage.code = request.POST.get('code', stage.code).upper()
    stage.name = request.POST.get('name', stage.name)
    stage.stage_type = request.POST.get('stage_type', stage.stage_type)
    stage.color = request.POST.get('color', stage.color)
    stage.icon = request.POST.get('icon', stage.icon)
    stage.requires_reason_on_entry = request.POST.get('requires_reason_on_entry') == 'on'
    stage.save()
    
    if request.headers.get('HX-Request'):
        return render(request, 'admin/workflows/partials/stage_row.html', {'stage': stage})
    
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def stage_delete(request, pk):
    """Delete a stage (HTMX)."""
    stage = get_object_or_404(ProcessStage, pk=pk)
    process_flow_pk = stage.process_flow.pk
    stage.delete()
    
    if request.headers.get('HX-Request'):
        return JsonResponse({'status': 'deleted'})
    
    return redirect('workflows:processstage_edit', pk=process_flow_pk)


@login_required
@require_POST
def transition_toggle(request, pk):
    """Toggle a transition's allowed status (HTMX)."""
    process_flow = get_object_or_404(ProcessFlow, pk=pk)
    
    from_stage_code = request.POST.get('from_stage')
    to_stage_code = request.POST.get('to_stage')
    
    from_stage = get_object_or_404(ProcessStage, process_flow=process_flow, code=from_stage_code)
    to_stage = get_object_or_404(ProcessStage, process_flow=process_flow, code=to_stage_code)
    
    transition, created = ProcessStageTransition.objects.get_or_create(
        process_flow=process_flow,
        from_stage=from_stage,
        to_stage=to_stage,
        defaults={'is_allowed': True}
    )
    
    if not created:
        transition.is_allowed = not transition.is_allowed
        transition.save()
    
    return JsonResponse({
        'status': 'success',
        'is_allowed': transition.is_allowed,
        'from_stage': from_stage_code,
        'to_stage': to_stage_code,
    })


class TransitionAttemptLogListView(LoginRequiredMixin, ListView):
    """View blocked transition attempts for analysis."""
    template_name = 'admin/workflows/transition_log.html'
    context_object_name = 'attempts'
    paginate_by = 50
    
    def get_queryset(self):
        qs = TransitionAttemptLog.objects.all().select_related(
            'process_flow', 'attempted_by'
        ).order_by('-attempted_at')
        
        # Filter by entity type
        entity_type = self.request.GET.get('entity_type')
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        
        # Filter blocked only
        if self.request.GET.get('blocked_only'):
            qs = qs.filter(was_blocked=True)
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Transition Attempt Log'
        context['entity_types'] = TransitionAttemptLog.objects.values_list(
            'entity_type', flat=True
        ).distinct()
        
        # Stats
        context['total_attempts'] = TransitionAttemptLog.objects.count()
        context['blocked_attempts'] = TransitionAttemptLog.objects.filter(was_blocked=True).count()
        
        return context


class ProcessFlowListView(LoginRequiredMixin, ListView):
    """List all process flows."""
    template_name = 'admin/workflows/processflow_list.html'
    context_object_name = 'process_flows'
    paginate_by = 20
    
    def get_queryset(self):
        return ProcessFlow.objects.all().annotate(
            stage_count=models.Count('stages'),
            transition_count=models.Count('transitions')
        ).order_by('-is_active', 'entity_type', '-version')
    
    def get_context_data(self, **kwargs):
        from django.db import models
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Business Process Flows'
        context['entity_types'] = ProcessFlow.objects.values_list('entity_type', flat=True).distinct()
        return context


class ProcessFlowDetailView(LoginRequiredMixin, DetailView):
    """View details of a process flow with transition matrix."""
    template_name = 'admin/workflows/processflow_detail.html'
    context_object_name = 'process_flow'
    model = ProcessFlow
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all stages ordered by sequence
        stages = self.object.stages.all().order_by('sequence_order')
        context['stages'] = stages
        
        # Build transition matrix
        transitions = self.object.transitions.all().select_related('from_stage', 'to_stage')
        
        # Create a lookup dict
        transition_map = {}
        for t in transitions:
            key = f"{t.from_stage.code}:{t.to_stage.code}"
            transition_map[key] = t
        
        # Build matrix for template
        matrix = []
        for from_stage in stages:
            row = {'stage': from_stage, 'transitions': []}
            for to_stage in stages:
                key = f"{from_stage.code}:{to_stage.code}"
                transition = transition_map.get(key)
                row['transitions'].append({
                    'to_stage': to_stage,
                    'transition': transition,
                    'is_same': from_stage.code == to_stage.code,
                })
            matrix.append(row)
        
        context['transition_matrix'] = matrix
        context['page_title'] = f'Process Flow: {self.object.name}'
        
        # Recent transition attempts
        context['recent_attempts'] = TransitionAttemptLog.objects.filter(
            entity_type=self.object.entity_type
        ).order_by('-attempted_at')[:20]
        
        return context


class ProcessFlowCreateView(LoginRequiredMixin, CreateView):
    """Create a new process flow."""
    model = ProcessFlow
    template_name = 'admin/workflows/processflow_form.html'
    fields = ['entity_type', 'name', 'description']
    
    def get_success_url(self):
        return reverse_lazy('workflows:processflow_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        form.instance.version = 1
        form.instance.is_active = True
        messages.success(self.request, 'Process flow created successfully.')
        return super().form_valid(form)


class ProcessStageEditView(LoginRequiredMixin, TemplateView):
    """Edit stages for a process flow (HTMX-powered)."""
    template_name = 'admin/workflows/processstage_edit.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        process_flow = get_object_or_404(ProcessFlow, pk=self.kwargs['pk'])
        context['process_flow'] = process_flow
        context['stages'] = process_flow.stages.all().order_by('sequence_order')
        context['stage_types'] = ProcessStage.STAGE_TYPES
        context['colors'] = [
            ('primary', 'Primary'),
            ('secondary', 'Secondary'),
            ('success', 'Success'),
            ('danger', 'Danger'),
            ('warning', 'Warning'),
            ('info', 'Info'),
            ('dark', 'Dark'),
        ]
        context['page_title'] = f'Edit Stages: {process_flow.name}'
        return context


@login_required
@require_POST
def processflow_toggle_active(request, pk):
    """Toggle the active status of a process flow."""
    process_flow = get_object_or_404(ProcessFlow, pk=pk)
    
    if process_flow.is_active:
        process_flow.is_active = False
        messages.warning(request, f'Process flow "{process_flow.name}" has been deactivated.')
    else:
        # Deactivate other flows for the same entity type
        ProcessFlow.objects.filter(
            entity_type=process_flow.entity_type,
            is_active=True
        ).update(is_active=False)
        process_flow.is_active = True
        messages.success(request, f'Process flow "{process_flow.name}" has been activated.')
    
    process_flow.save()
    
    if request.headers.get('HX-Request'):
        return JsonResponse({'status': 'success'})
    
    return redirect('workflows:processflow_detail', pk=pk)


@login_required
@require_POST
def stage_create(request, pk):
    """Create a new stage for a process flow (HTMX)."""
    process_flow = get_object_or_404(ProcessFlow, pk=pk)
    
    code = request.POST.get('code', '').upper()
    name = request.POST.get('name', '')
    stage_type = request.POST.get('stage_type', 'PROCESS')
    color = request.POST.get('color', 'primary')
    
    if not code or not name:
        return JsonResponse({'error': 'Code and name are required'}, status=400)
    
    # Get max sequence order
    max_order = process_flow.stages.aggregate(
        max_order=models.Max('sequence_order')
    )['max_order'] or 0
    
    stage = ProcessStage.objects.create(
        process_flow=process_flow,
        code=code,
        name=name,
        stage_type=stage_type,
        color=color,
        sequence_order=max_order + 10,
    )
    
    if request.headers.get('HX-Request'):
        # Return the new stage row HTML
        return render(request, 'admin/workflows/partials/stage_row.html', {'stage': stage})
    
    return JsonResponse({'status': 'success', 'stage_id': stage.id})


@login_required
@require_POST
def stage_update(request, pk):
    """Update a stage (HTMX)."""
    stage = get_object_or_404(ProcessStage, pk=pk)
    
    stage.code = request.POST.get('code', stage.code).upper()
    stage.name = request.POST.get('name', stage.name)
    stage.stage_type = request.POST.get('stage_type', stage.stage_type)
    stage.color = request.POST.get('color', stage.color)
    stage.icon = request.POST.get('icon', stage.icon)
    stage.requires_reason_on_entry = request.POST.get('requires_reason_on_entry') == 'on'
    stage.save()
    
    if request.headers.get('HX-Request'):
        return render(request, 'admin/workflows/partials/stage_row.html', {'stage': stage})
    
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def stage_delete(request, pk):
    """Delete a stage (HTMX)."""
    stage = get_object_or_404(ProcessStage, pk=pk)
    process_flow_pk = stage.process_flow.pk
    stage.delete()
    
    if request.headers.get('HX-Request'):
        return JsonResponse({'status': 'deleted'})
    
    return redirect('workflows:processstage_edit', pk=process_flow_pk)


@login_required
@require_POST
def transition_toggle(request, pk):
    """Toggle a transition's allowed status (HTMX)."""
    process_flow = get_object_or_404(ProcessFlow, pk=pk)
    
    from_stage_code = request.POST.get('from_stage')
    to_stage_code = request.POST.get('to_stage')
    
    from_stage = get_object_or_404(ProcessStage, process_flow=process_flow, code=from_stage_code)
    to_stage = get_object_or_404(ProcessStage, process_flow=process_flow, code=to_stage_code)
    
    transition, created = ProcessStageTransition.objects.get_or_create(
        process_flow=process_flow,
        from_stage=from_stage,
        to_stage=to_stage,
        defaults={'is_allowed': True}
    )
    
    if not created:
        transition.is_allowed = not transition.is_allowed
        transition.save()
    
    return JsonResponse({
        'status': 'success',
        'is_allowed': transition.is_allowed,
        'from_stage': from_stage_code,
        'to_stage': to_stage_code,
    })


class TransitionAttemptLogListView(LoginRequiredMixin, ListView):
    """View blocked transition attempts for analysis."""
    template_name = 'admin/workflows/transition_log.html'
    context_object_name = 'attempts'
    paginate_by = 50
    
    def get_queryset(self):
        qs = TransitionAttemptLog.objects.all().select_related(
            'process_flow', 'attempted_by'
        ).order_by('-attempted_at')
        
        # Filter by entity type
        entity_type = self.request.GET.get('entity_type')
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        
        # Filter blocked only
        if self.request.GET.get('blocked_only'):
            qs = qs.filter(was_blocked=True)
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Transition Attempt Log'
        context['entity_types'] = TransitionAttemptLog.objects.values_list(
            'entity_type', flat=True
        ).distinct()
        
        # Stats
        context['total_attempts'] = TransitionAttemptLog.objects.count()
        context['blocked_attempts'] = TransitionAttemptLog.objects.filter(was_blocked=True).count()
        
        return context


# Create your views here.
