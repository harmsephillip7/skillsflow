"""
Pipeline Views

Opportunity and Application pipeline management:
- Kanban board for opportunities
- Stage transitions
- Conversion to applications
"""
import json
from decimal import Decimal
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.urls import reverse, reverse_lazy
from django import forms

from tenants.models import Brand, Campus
from crm.models import Lead, Opportunity, OpportunityActivity, Application, ApplicationDocument
from core.context_processors import get_selected_campus


class OpportunityForm(forms.ModelForm):
    """Form for creating/editing opportunities."""
    
    class Meta:
        model = Opportunity
        fields = [
            'lead', 'name', 'stage', 'value', 'probability',
            'qualification', 'intake', 'funding_type', 'expected_close_date', 
            'assigned_agent', 'campus', 'notes'
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
            'expected_close_date': forms.DateInput(attrs={'type': 'date'}),
            'value': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.brand = kwargs.pop('brand', None)
        super().__init__(*args, **kwargs)
        
        # Filter leads by brand/campus
        if self.brand:
            from tenants.models import Campus
            campuses = Campus.objects.filter(brand=self.brand)
            self.fields['lead'].queryset = Lead.objects.filter(campus__in=campuses)
        
        # Make some fields optional in the form
        self.fields['intake'].required = False
        self.fields['notes'].required = False


class OpportunityBoardView(LoginRequiredMixin, ListView):
    """
    Kanban-style opportunity board.
    
    Shows opportunities grouped by stage with drag-and-drop.
    """
    model = Opportunity
    template_name = 'crm/pipeline/opportunity_board.html'
    context_object_name = 'opportunities'
    
    STAGES = [
        ('discovery', 'Discovery', 'bg-gray-100', 'text-gray-700'),
        ('qualification', 'Qualification', 'bg-blue-100', 'text-blue-700'),
        ('proposal', 'Proposal', 'bg-yellow-100', 'text-yellow-700'),
        ('negotiation', 'Negotiation', 'bg-purple-100', 'text-purple-700'),
        ('committed', 'Committed', 'bg-green-100', 'text-green-700'),
    ]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Opportunity.objects.select_related(
            'lead', 'assigned_agent', 'qualification', 'campus', 'intake'
        ).exclude(stage__in=['WON', 'LOST'])
        
        # Apply global campus filter
        selected_campus = get_selected_campus(self.request)
        if selected_campus:
            queryset = queryset.filter(campus=selected_campus)
        
        # Filter by assigned user
        assigned = self.request.GET.get('assigned')
        if assigned == 'me':
            queryset = queryset.filter(assigned_agent=user)
        elif assigned and assigned.isdigit():
            queryset = queryset.filter(assigned_agent_id=int(assigned))
        
        # Search
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(lead__first_name__icontains=search) |
                Q(lead__last_name__icontains=search)
            )
        
        return queryset.order_by('-updated_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group opportunities by stage
        opportunities = self.get_queryset()
        
        stages_data = []
        for stage_key, stage_label, bg_class, text_class in self.STAGES:
            stage_opps = [o for o in opportunities if o.stage == stage_key]
            stages_data.append({
                'key': stage_key,
                'label': stage_label,
                'bg_class': bg_class,
                'text_class': text_class,
                'opportunities': stage_opps,
                'count': len(stage_opps),
                'value': sum(o.value or 0 for o in stage_opps),
            })
        
        context['stages'] = stages_data
        
        # Summary stats
        all_opps = list(opportunities)
        context['stats'] = {
            'total_count': len(all_opps),
            'total_value': sum(o.value or 0 for o in all_opps),
            'weighted_value': sum((o.value or 0) * (o.probability or 0) / 100 for o in all_opps),
            'avg_probability': sum(o.probability or 0 for o in all_opps) / len(all_opps) if all_opps else 0,
        }
        
        # Closed stats (won/lost)
        won = Opportunity.objects.filter(stage='won')
        lost = Opportunity.objects.filter(stage='lost')
        if not self.request.user.is_superuser and hasattr(self.request.user, 'profile'):
            if self.request.user.profile.brand:
                won = won.filter(brand=self.request.user.profile.brand)
                lost = lost.filter(brand=self.request.user.profile.brand)
        
        context['closed_stats'] = {
            'won_count': won.count(),
            'won_value': won.aggregate(total=Sum('value'))['total'] or 0,
            'lost_count': lost.count(),
        }
        
        context['current_filters'] = {
            'assigned': self.request.GET.get('assigned', ''),
            'q': self.request.GET.get('q', ''),
        }
        
        return context


class OpportunityListView(LoginRequiredMixin, ListView):
    """Table view of opportunities."""
    model = Opportunity
    template_name = 'crm/pipeline/opportunity_list.html'
    context_object_name = 'opportunities'
    paginate_by = 25
    
    def get_queryset(self):
        user = self.request.user
        queryset = Opportunity.objects.select_related(
            'lead', 'assigned_agent', 'qualification', 'campus', 'intake'
        )
        
        if not user.is_superuser:
            if hasattr(user, 'profile') and user.profile.brand:
                queryset = queryset.filter(campus__brand=user.profile.brand)
        
        # Filters
        stage = self.request.GET.get('stage')
        if stage:
            queryset = queryset.filter(stage=stage)
        
        funding = self.request.GET.get('funding')
        if funding:
            queryset = queryset.filter(funding_type=funding)
        
        return queryset.order_by('-created_at')


class OpportunityDetailView(LoginRequiredMixin, DetailView):
    """Opportunity detail with activity timeline."""
    model = Opportunity
    template_name = 'crm/pipeline/opportunity_detail.html'
    context_object_name = 'opportunity'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Activities
        context['activities'] = self.object.activities.select_related(
            'created_by'
        ).order_by('-created_at')[:20]
        
        # Related application if any
        context['application'] = Application.objects.filter(
            opportunity=self.object
        ).first()
        
        # Available stages for transition
        context['stages'] = Opportunity.STAGE_CHOICES
        
        return context


class OpportunityCreateView(LoginRequiredMixin, CreateView):
    """Create a new opportunity."""
    model = Opportunity
    form_class = OpportunityForm
    template_name = 'crm/pipeline/opportunity_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if hasattr(self.request.user, 'profile') and self.request.user.profile.brand:
            kwargs['brand'] = self.request.user.profile.brand
        return kwargs
    
    def form_valid(self, form):
        opportunity = form.save(commit=False)
        
        # Set brand from user profile
        if hasattr(self.request.user, 'profile') and self.request.user.profile.brand:
            opportunity.brand = self.request.user.profile.brand
        
        # Set from lead if provided
        lead_id = self.request.GET.get('lead')
        if lead_id:
            lead = get_object_or_404(Lead, pk=lead_id)
            opportunity.lead = lead
            opportunity.brand = lead.brand
            opportunity.campus = lead.campus
        
        opportunity.save()
        
        # Log creation
        OpportunityActivity.objects.create(
            opportunity=opportunity,
            activity_type='created',
            description='Opportunity created',
            created_by=self.request.user
        )
        
        return redirect('crm:opportunity_detail', pk=opportunity.pk)


class OpportunityUpdateView(LoginRequiredMixin, UpdateView):
    """Update an opportunity."""
    model = Opportunity
    form_class = OpportunityForm
    template_name = 'crm/pipeline/opportunity_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['brand'] = self.object.brand
        return kwargs
    
    def form_valid(self, form):
        old_stage = self.object.stage
        opportunity = form.save()
        
        # Log stage change
        if old_stage != opportunity.stage:
            OpportunityActivity.objects.create(
                opportunity=opportunity,
                activity_type='stage_change',
                previous_stage=old_stage,
                new_stage=opportunity.stage,
                description=f'Stage changed from {old_stage} to {opportunity.stage}',
                created_by=self.request.user
            )
        
        return redirect('crm:opportunity_detail', pk=opportunity.pk)


class OpportunityStageUpdateView(LoginRequiredMixin, View):
    """
    AJAX endpoint to update opportunity stage.
    
    POST /crm/opportunities/<id>/stage/
    {
        "stage": "qualification",
        "note": "Qualified after initial call"
    }
    """
    
    def post(self, request, pk):
        opportunity = get_object_or_404(Opportunity, pk=pk)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        new_stage = data.get('stage')
        note = data.get('note', '')
        
        valid_stages = [s[0] for s in Opportunity.STAGE_CHOICES]
        if new_stage not in valid_stages:
            return JsonResponse({'error': 'Invalid stage'}, status=400)
        
        old_stage = opportunity.stage
        opportunity.stage = new_stage
        
        # Handle won/lost
        if new_stage == 'won':
            opportunity.closed_at = timezone.now()
            opportunity.probability = 100
        elif new_stage == 'lost':
            opportunity.closed_at = timezone.now()
            opportunity.probability = 0
            opportunity.lost_reason = data.get('lost_reason', '')
        
        opportunity.save()
        
        # Log activity
        OpportunityActivity.objects.create(
            opportunity=opportunity,
            activity_type='stage_change',
            previous_stage=old_stage,
            new_stage=new_stage,
            description=note or f'Stage changed from {old_stage} to {new_stage}',
            created_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'stage': opportunity.stage,
            'stage_display': opportunity.get_stage_display()
        })


class ConvertToApplicationView(LoginRequiredMixin, View):
    """
    Convert an opportunity to an application.
    
    POST /crm/opportunities/<id>/convert/
    """
    
    def post(self, request, pk):
        opportunity = get_object_or_404(Opportunity, pk=pk)
        
        # Check if already converted
        if Application.objects.filter(opportunity=opportunity).exists():
            return JsonResponse({'error': 'Already converted to application'}, status=400)
        
        # Create application
        application = Application.objects.create(
            brand=opportunity.brand,
            campus=opportunity.campus or opportunity.lead.campus if opportunity.lead else None,
            lead=opportunity.lead,
            opportunity=opportunity,
            programme=opportunity.programme,
            status='draft'
        )
        
        # Update opportunity stage
        opportunity.stage = 'won'
        opportunity.closed_at = timezone.now()
        opportunity.probability = 100
        opportunity.save()
        
        # Log activity
        OpportunityActivity.objects.create(
            opportunity=opportunity,
            activity_type='converted',
            description=f'Converted to application #{application.id}',
            created_by=request.user
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'application_id': application.id,
                'redirect_url': reverse('crm:application_detail', kwargs={'pk': application.id})
            })
        
        return redirect('crm:application_detail', pk=application.id)


class ApplicationListView(LoginRequiredMixin, ListView):
    """List all applications."""
    model = Application
    template_name = 'crm/pipeline/application_list.html'
    context_object_name = 'applications'
    paginate_by = 25
    
    def get_queryset(self):
        user = self.request.user
        queryset = Application.objects.select_related(
            'campus', 'opportunity', 'learner', 'enrollment', 'submitted_by', 'reviewed_by'
        )
        
        # Apply global campus filter
        selected_campus = get_selected_campus(self.request)
        if selected_campus:
            queryset = queryset.filter(campus=selected_campus)
        elif not user.is_superuser:
            if hasattr(user, 'profile') and user.profile.brand:
                queryset = queryset.filter(campus__brand=user.profile.brand)
        
        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = Application.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        return context


class ApplicationDetailView(LoginRequiredMixin, DetailView):
    """Application detail with documents."""
    model = Application
    template_name = 'crm/pipeline/application_detail.html'
    context_object_name = 'application'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Documents
        context['documents'] = self.object.documents.all()
        
        # Status choices for updates
        context['statuses'] = Application.STATUS_CHOICES
        
        return context


class ApplicationStatusUpdateView(LoginRequiredMixin, View):
    """
    Update application status.
    
    POST /crm/applications/<id>/status/
    {
        "status": "submitted",
        "note": "Application submitted by learner"
    }
    """
    
    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        new_status = data.get('status')
        
        valid_statuses = [s[0] for s in Application.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({'error': 'Invalid status'}, status=400)
        
        application.status = new_status
        
        # Handle special statuses
        if new_status == 'submitted':
            application.submitted_at = timezone.now()
        elif new_status == 'accepted':
            application.accepted_at = timezone.now()
        elif new_status == 'rejected':
            application.rejected_at = timezone.now()
            application.rejection_reason = data.get('reason', '')
        
        application.save()
        
        return JsonResponse({
            'success': True,
            'status': application.status,
            'status_display': application.get_status_display()
        })


# URL patterns
def get_pipeline_urls():
    """Return URL patterns for pipeline views."""
    from django.urls import path
    
    return [
        # Opportunities
        path('opportunities/', OpportunityBoardView.as_view(), name='opportunity_board'),
        path('opportunities/list/', OpportunityListView.as_view(), name='opportunity_list'),
        path('opportunities/add/', OpportunityCreateView.as_view(), name='opportunity_create'),
        path('opportunities/<int:pk>/', OpportunityDetailView.as_view(), name='opportunity_detail'),
        path('opportunities/<int:pk>/edit/', OpportunityUpdateView.as_view(), name='opportunity_update'),
        path('opportunities/<int:pk>/stage/', OpportunityStageUpdateView.as_view(), name='opportunity_stage'),
        path('opportunities/<int:pk>/convert/', ConvertToApplicationView.as_view(), name='opportunity_convert'),
        
        # Applications
        path('applications/', ApplicationListView.as_view(), name='application_list'),
        path('applications/<int:pk>/', ApplicationDetailView.as_view(), name='application_detail'),
        path('applications/<int:pk>/status/', ApplicationStatusUpdateView.as_view(), name='application_status'),
    ]
