"""
Pipeline Settings Views
Provides CRUD for pipelines, stages, blueprints, and communication templates.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.db import transaction, models
from django.db.models import Count, Prefetch, Max
import json

from .models import Pipeline, PipelineStage, StageBlueprint
from .communication_models import MessageTemplate
from .views import CRMAccessMixin


class PipelineSettingsListView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """List all pipelines with management options."""
    template_name = 'crm/settings/pipeline_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get pipelines for user's campus(es)
        if user.is_superuser or user.groups.filter(name__in=['CRM Admin', 'System Admin']).exists():
            pipelines = Pipeline.objects.all()
        else:
            pipelines = Pipeline.objects.filter(campus=user.campus)
        
        # Use different names for annotations to avoid conflict with model properties
        pipelines = pipelines.annotate(
            stages_total=Count('stages'),
            leads_total=Count('leads')
        ).prefetch_related('stages').order_by('campus__name', 'learner_type', 'name')
        
        context['pipelines'] = pipelines
        context['learner_types'] = Pipeline.LEARNER_TYPE_CHOICES
        context['frequency_choices'] = Pipeline.FREQUENCY_CHOICES
        
        # Get available campuses for create form
        from tenants.models import Campus
        if user.is_superuser:
            context['campuses'] = Campus.objects.filter(is_active=True)
        else:
            context['campuses'] = Campus.objects.filter(pk=user.campus_id)
        
        return context


class PipelineCreateView(LoginRequiredMixin, CRMAccessMixin, View):
    """Create a new pipeline."""
    
    def post(self, request):
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            
            name = data.get('name', '').strip()
            learner_type = data.get('learner_type', '')
            campus_id = data.get('campus_id')
            description = data.get('description', '')
            color = data.get('color', '#3B82F6')
            frequency = int(data.get('default_communication_frequency_days', 14))
            
            if not name or not learner_type or not campus_id:
                return JsonResponse({'success': False, 'error': 'Name, learner type, and campus are required.'}, status=400)
            
            from tenants.models import Campus
            campus = get_object_or_404(Campus, pk=campus_id)
            
            # Check permissions
            if not request.user.is_superuser and request.user.campus_id != campus.pk:
                return JsonResponse({'success': False, 'error': 'You can only create pipelines for your campus.'}, status=403)
            
            with transaction.atomic():
                pipeline = Pipeline.objects.create(
                    name=name,
                    learner_type=learner_type,
                    campus=campus,
                    description=description,
                    color=color,
                    default_communication_frequency_days=frequency,
                    is_active=True,
                )
                
                # Create default stages
                default_stages = [
                    {'name': 'New Lead', 'code': 'NEW', 'order': 1, 'is_entry_stage': True, 'color': '#6B7280', 'win_probability': 10},
                    {'name': 'Contacted', 'code': 'CONTACTED', 'order': 2, 'color': '#3B82F6', 'win_probability': 20},
                    {'name': 'Interested', 'code': 'INTERESTED', 'order': 3, 'color': '#8B5CF6', 'win_probability': 40},
                    {'name': 'Pre-Approved', 'code': 'PREAPPROVED', 'order': 4, 'color': '#F59E0B', 'win_probability': 60},
                    {'name': 'Application', 'code': 'APPLICATION', 'order': 5, 'color': '#10B981', 'win_probability': 80},
                    {'name': 'Enrolled', 'code': 'ENROLLED', 'order': 6, 'is_won_stage': True, 'color': '#059669', 'win_probability': 100},
                    {'name': 'Lost', 'code': 'LOST', 'order': 99, 'is_lost_stage': True, 'color': '#EF4444', 'win_probability': 0},
                ]
                
                for stage_data in default_stages:
                    stage = PipelineStage.objects.create(
                        pipeline=pipeline,
                        **stage_data
                    )
                    # Create empty blueprint for each stage
                    StageBlueprint.objects.create(stage=stage)
            
            return JsonResponse({
                'success': True,
                'pipeline_id': pipeline.pk,
                'message': f'Pipeline "{name}" created successfully with default stages.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class PipelineDetailView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """Edit pipeline settings, stages, blueprints."""
    template_name = 'crm/settings/pipeline_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pipeline_id = self.kwargs.get('pk')
        
        pipeline = get_object_or_404(
            Pipeline.objects.prefetch_related(
                Prefetch('stages', queryset=PipelineStage.objects.order_by('order').prefetch_related('blueprint'))
            ),
            pk=pipeline_id
        )
        
        context['pipeline'] = pipeline
        context['stages'] = pipeline.stages.all()
        context['learner_types'] = Pipeline.LEARNER_TYPE_CHOICES
        context['frequency_choices'] = Pipeline.FREQUENCY_CHOICES
        
        # Get message templates for assignment
        templates = MessageTemplate.objects.filter(
            campus=pipeline.campus,
            status='APPROVED'
        ).order_by('channel_type', 'name')
        context['message_templates'] = templates
        
        return context


class PipelineUpdateView(LoginRequiredMixin, CRMAccessMixin, View):
    """Update pipeline settings."""
    
    def post(self, request, pk):
        try:
            pipeline = get_object_or_404(Pipeline, pk=pk)
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            
            # Update basic fields
            if 'name' in data:
                pipeline.name = data['name'].strip()
            if 'description' in data:
                pipeline.description = data['description']
            if 'learner_type' in data:
                pipeline.learner_type = data['learner_type']
            if 'color' in data:
                pipeline.color = data['color']
            if 'default_communication_frequency_days' in data:
                pipeline.default_communication_frequency_days = int(data['default_communication_frequency_days'])
            if 'is_active' in data:
                pipeline.is_active = data['is_active'] in [True, 'true', '1', 1]
            if 'is_default' in data:
                pipeline.is_default = data['is_default'] in [True, 'true', '1', 1]
            
            pipeline.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Pipeline updated successfully.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class PipelineDeleteView(LoginRequiredMixin, CRMAccessMixin, View):
    """Delete a pipeline."""
    
    def post(self, request, pk):
        try:
            pipeline = get_object_or_404(Pipeline, pk=pk)
            
            # Check if pipeline has leads
            leads_count = pipeline.leads.count()
            if leads_count > 0:
                return JsonResponse({
                    'success': False,
                    'error': f'Cannot delete pipeline with {leads_count} leads. Move or delete leads first.'
                }, status=400)
            
            name = pipeline.name
            pipeline.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Pipeline "{name}" deleted successfully.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class StageCreateView(LoginRequiredMixin, CRMAccessMixin, View):
    """Create a new stage in a pipeline."""
    
    def post(self, request, pipeline_pk):
        try:
            pipeline = get_object_or_404(Pipeline, pk=pipeline_pk)
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            
            name = data.get('name', '').strip()
            code = data.get('code', '').strip().upper().replace(' ', '_')
            
            if not name or not code:
                return JsonResponse({'success': False, 'error': 'Name and code are required.'}, status=400)
            
            # Check if code already exists
            if pipeline.stages.filter(code=code).exists():
                return JsonResponse({'success': False, 'error': f'Stage with code "{code}" already exists.'}, status=400)
            
            # Get max order
            max_order = pipeline.stages.exclude(is_lost_stage=True).aggregate(
                max_order=Max('order')
            )['max_order'] or 0
            
            with transaction.atomic():
                stage = PipelineStage.objects.create(
                    pipeline=pipeline,
                    name=name,
                    code=code,
                    description=data.get('description', ''),
                    order=max_order + 1,
                    expected_duration_days=int(data.get('expected_duration_days', 7)),
                    communication_frequency_days=int(data.get('communication_frequency_days', 0)) or None,
                    color=data.get('color', '#6B7280'),
                    win_probability=int(data.get('win_probability', 0)),
                    is_entry_stage=data.get('is_entry_stage', False) in [True, 'true', '1'],
                    is_won_stage=data.get('is_won_stage', False) in [True, 'true', '1'],
                    is_lost_stage=data.get('is_lost_stage', False) in [True, 'true', '1'],
                    is_nurture_stage=data.get('is_nurture_stage', False) in [True, 'true', '1'],
                )
                
                # Create blueprint
                StageBlueprint.objects.create(stage=stage)
            
            return JsonResponse({
                'success': True,
                'stage_id': stage.pk,
                'message': f'Stage "{name}" created successfully.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class StageUpdateView(LoginRequiredMixin, CRMAccessMixin, View):
    """Update a stage."""
    
    def post(self, request, pk):
        try:
            stage = get_object_or_404(PipelineStage, pk=pk)
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            
            # Update fields
            if 'name' in data:
                stage.name = data['name'].strip()
            if 'description' in data:
                stage.description = data['description']
            if 'expected_duration_days' in data:
                stage.expected_duration_days = int(data['expected_duration_days'])
            if 'communication_frequency_days' in data:
                val = data['communication_frequency_days']
                stage.communication_frequency_days = int(val) if val else None
            if 'color' in data:
                stage.color = data['color']
            if 'win_probability' in data:
                stage.win_probability = int(data['win_probability'])
            if 'is_entry_stage' in data:
                stage.is_entry_stage = data['is_entry_stage'] in [True, 'true', '1', 1]
            if 'is_won_stage' in data:
                stage.is_won_stage = data['is_won_stage'] in [True, 'true', '1', 1]
            if 'is_lost_stage' in data:
                stage.is_lost_stage = data['is_lost_stage'] in [True, 'true', '1', 1]
            if 'is_nurture_stage' in data:
                stage.is_nurture_stage = data['is_nurture_stage'] in [True, 'true', '1', 1]
            
            stage.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Stage "{stage.name}" updated successfully.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class StageDeleteView(LoginRequiredMixin, CRMAccessMixin, View):
    """Delete a stage."""
    
    def post(self, request, pk):
        try:
            stage = get_object_or_404(PipelineStage, pk=pk)
            
            # Check if stage has leads
            from .models import Lead
            leads_count = Lead.objects.filter(current_stage=stage).count()
            if leads_count > 0:
                return JsonResponse({
                    'success': False,
                    'error': f'Cannot delete stage with {leads_count} leads. Move leads to another stage first.'
                }, status=400)
            
            name = stage.name
            stage.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Stage "{name}" deleted successfully.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class StageReorderView(LoginRequiredMixin, CRMAccessMixin, View):
    """Reorder stages via drag-drop."""
    
    def post(self, request, pipeline_pk):
        try:
            pipeline = get_object_or_404(Pipeline, pk=pipeline_pk)
            data = json.loads(request.body)
            
            stage_order = data.get('stage_order', [])  # List of stage IDs in order
            
            with transaction.atomic():
                for index, stage_id in enumerate(stage_order, start=1):
                    PipelineStage.objects.filter(
                        pk=stage_id,
                        pipeline=pipeline
                    ).update(order=index)
            
            return JsonResponse({
                'success': True,
                'message': 'Stage order updated successfully.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class BlueprintUpdateView(LoginRequiredMixin, CRMAccessMixin, View):
    """Update stage blueprint configuration."""
    
    def post(self, request, stage_pk):
        try:
            stage = get_object_or_404(PipelineStage, pk=stage_pk)
            blueprint, created = StageBlueprint.objects.get_or_create(stage=stage)
            
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            
            # Update blueprint fields
            if 'recommended_actions' in data:
                blueprint.recommended_actions = data['recommended_actions']
            if 'auto_tasks' in data:
                blueprint.auto_tasks = data['auto_tasks']
            if 'notify_agent_on_entry' in data:
                blueprint.notify_agent_on_entry = data['notify_agent_on_entry'] in [True, 'true', '1', 1]
            if 'notify_agent_on_overdue' in data:
                blueprint.notify_agent_on_overdue = data['notify_agent_on_overdue'] in [True, 'true', '1', 1]
            if 'overdue_notification_days' in data:
                blueprint.overdue_notification_days = int(data['overdue_notification_days'])
            if 'auto_send_initial_communication' in data:
                blueprint.auto_send_initial_communication = data['auto_send_initial_communication'] in [True, 'true', '1', 1]
            if 'auto_schedule_follow_up' in data:
                blueprint.auto_schedule_follow_up = data['auto_schedule_follow_up'] in [True, 'true', '1', 1]
            if 'default_template_id' in data:
                template_id = data['default_template_id']
                if template_id:
                    blueprint.default_template_id = template_id
                else:
                    blueprint.default_template = None
            
            blueprint.save()
            
            # Update communication templates (M2M)
            if 'template_ids' in data:
                template_ids = data['template_ids']
                if isinstance(template_ids, str):
                    template_ids = [t.strip() for t in template_ids.split(',') if t.strip()]
                blueprint.communication_templates.set(template_ids)
            
            return JsonResponse({
                'success': True,
                'message': f'Blueprint for "{stage.name}" updated successfully.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class StageTransitionRulesView(LoginRequiredMixin, CRMAccessMixin, View):
    """Manage stage transition rules (what's required to move between stages)."""
    
    def get(self, request, stage_pk):
        """Get current transition rules for a stage."""
        stage = get_object_or_404(PipelineStage, pk=stage_pk)
        blueprint = getattr(stage, 'blueprint', None)
        
        # Get transition rules from blueprint's recommended_actions
        rules = []
        if blueprint and blueprint.recommended_actions:
            rules = [a for a in blueprint.recommended_actions if a.get('type') == 'requirement']
        
        return JsonResponse({
            'success': True,
            'stage_id': stage.pk,
            'stage_name': stage.name,
            'rules': rules
        })
    
    def post(self, request, stage_pk):
        """Update transition rules for a stage."""
        try:
            stage = get_object_or_404(PipelineStage, pk=stage_pk)
            blueprint, created = StageBlueprint.objects.get_or_create(stage=stage)
            
            data = json.loads(request.body)
            requirements = data.get('requirements', [])
            
            # Store requirements in recommended_actions with type='requirement'
            existing_actions = [a for a in (blueprint.recommended_actions or []) if a.get('type') != 'requirement']
            requirement_actions = [{'type': 'requirement', **req} for req in requirements]
            blueprint.recommended_actions = existing_actions + requirement_actions
            blueprint.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Transition rules updated successfully.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
