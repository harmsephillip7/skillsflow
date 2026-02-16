"""
Campaign Management Views

Marketing campaign CRUD, approval workflow, template management, and bulk sending.
"""
import json
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Q, F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django import forms
from django.contrib import messages

from .models import Lead
from .communication_models import (
    Campaign, CampaignRecipient, MessageTemplate,
)
from tenants.models import Brand, Campus
from core.context_processors import get_selected_campus


class CampaignForm(forms.ModelForm):
    """Form for creating/editing campaigns."""
    
    class Meta:
        model = Campaign
        fields = [
            'name', 'description', 'campaign_type', 'channel_type',
            'template', 'social_channel', 'sms_config', 'campus',
            'scheduled_at',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500',
                'rows': 3,
            }),
            'campaign_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500'
            }),
            'channel_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500'
            }),
            'template': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500'
            }),
            'social_channel': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500'
            }),
            'sms_config': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500'
            }),
            'campus': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500'
            }),
            'scheduled_at': forms.DateTimeInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-primary-500 focus:border-primary-500',
                'type': 'datetime-local'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter templates by approved status
        self.fields['template'].queryset = MessageTemplate.objects.filter(status='APPROVED')
        
        # Make optional fields not required
        self.fields['social_channel'].required = False
        self.fields['sms_config'].required = False
        self.fields['scheduled_at'].required = False
        self.fields['description'].required = False


class CampaignListView(LoginRequiredMixin, ListView):
    """List all campaigns with filtering."""
    
    model = Campaign
    template_name = 'crm/campaigns/campaign_list.html'
    context_object_name = 'campaigns'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Campaign.objects.select_related('campus', 'created_by', 'template')
        
        # Apply global campus filter
        selected_campus = get_selected_campus(self.request)
        if selected_campus:
            queryset = queryset.filter(campus=selected_campus)
        
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        channel = self.request.GET.get('channel')
        if channel:
            queryset = queryset.filter(channel=channel)
        
        campaign_type = self.request.GET.get('type')
        if campaign_type:
            queryset = queryset.filter(campaign_type=campaign_type)
        
        # Search
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(content__icontains=q)
            )
        
        return queryset.annotate(
            recipient_count=Count('recipients'),
            recipients_sent=Count('recipients', filter=Q(recipients__status='sent')),
            recipients_delivered=Count('recipients', filter=Q(recipients__status='delivered')),
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Stats
        base_qs = Campaign.objects.all()
        if not self.request.user.is_superuser:
            user_brands = self.request.user.accessible_brands.all()
            base_qs = base_qs.filter(campus__brand__in=user_brands)
        
        context['stats'] = {
            'total': base_qs.count(),
            'draft': base_qs.filter(status='draft').count(),
            'pending': base_qs.filter(status='pending_approval').count(),
            'scheduled': base_qs.filter(status='scheduled').count(),
            'sent': base_qs.filter(status='sent').count(),
        }
        
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'channel': self.request.GET.get('channel', ''),
            'type': self.request.GET.get('type', ''),
            'q': self.request.GET.get('q', ''),
        }
        
        return context


class CampaignDetailView(LoginRequiredMixin, DetailView):
    """Campaign detail with recipient stats and preview."""
    
    model = Campaign
    template_name = 'crm/campaigns/campaign_detail.html'
    context_object_name = 'campaign'
    
    def get_queryset(self):
        queryset = Campaign.objects.select_related('campus', 'created_by', 'template')
        
        if not self.request.user.is_superuser:
            user_brands = self.request.user.accessible_brands.all()
            queryset = queryset.filter(campus__brand__in=user_brands)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Recipient stats
        recipients = self.object.recipients.all()
        context['recipient_stats'] = {
            'total': recipients.count(),
            'pending': recipients.filter(status='pending').count(),
            'sent': recipients.filter(status='sent').count(),
            'delivered': recipients.filter(status='delivered').count(),
            'failed': recipients.filter(status='failed').count(),
            'opened': recipients.filter(opened_at__isnull=False).count(),
            'clicked': recipients.filter(clicked_at__isnull=False).count(),
        }
        
        # Calculate rates
        total = context['recipient_stats']['total'] or 1
        context['delivery_rate'] = round(context['recipient_stats']['delivered'] / total * 100, 1)
        context['open_rate'] = round(context['recipient_stats']['opened'] / total * 100, 1)
        context['click_rate'] = round(context['recipient_stats']['clicked'] / total * 100, 1)
        
        # Sample recipients
        context['sample_recipients'] = recipients.select_related('lead')[:10]
        
        # Failed recipients for review
        context['failed_recipients'] = recipients.filter(status='failed').select_related('lead')[:10]
        
        # Can approve check
        context['can_approve'] = (
            self.object.status == 'pending_approval' and
            self.request.user.has_perm('crm.approve_campaign')
        )
        
        # Can send check
        context['can_send'] = (
            self.object.status in ('approved', 'scheduled') and
            self.object.recipients.filter(status='pending').exists()
        )
        
        return context


class CampaignCreateView(LoginRequiredMixin, CreateView):
    """Create a new campaign."""
    
    model = Campaign
    form_class = CampaignForm
    template_name = 'crm/campaigns/campaign_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.status = 'draft'
        return super().form_valid(form)
    
    def get_success_url(self):
        messages.success(self.request, 'Campaign created successfully. Add recipients to continue.')
        return reverse('crm:campaign_detail', kwargs={'pk': self.object.pk})


class CampaignUpdateView(LoginRequiredMixin, UpdateView):
    """Update a campaign (only if draft)."""
    
    model = Campaign
    form_class = CampaignForm
    template_name = 'crm/campaigns/campaign_form.html'
    
    def get_queryset(self):
        # Only allow editing draft campaigns
        queryset = Campaign.objects.filter(status='draft')
        
        if not self.request.user.is_superuser:
            user_brands = self.request.user.accessible_brands.all()
            queryset = queryset.filter(campus__brand__in=user_brands)
        
        return queryset
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        messages.success(self.request, 'Campaign updated successfully.')
        return reverse('crm:campaign_detail', kwargs={'pk': self.object.pk})


class CampaignAddRecipientsView(LoginRequiredMixin, View):
    """Add recipients to a campaign based on audience criteria."""
    
    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, status='draft')
        
        # Check access
        if not request.user.is_superuser:
            user_brands = request.user.accessible_brands.all()
            if campaign.campus and campaign.campus.brand not in user_brands:
                return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        try:
            data = json.loads(request.body) if request.body else {}
            audience = data.get('audience', campaign.target_audience)
            
            # Build recipient queryset
            leads = Lead.objects.filter(campus=campaign.campus)
            
            if audience == 'all':
                pass  # All leads
            elif audience == 'new':
                leads = leads.filter(status='new')
            elif audience == 'contacted':
                leads = leads.filter(status='contacted')
            elif audience == 'qualified':
                leads = leads.filter(status='qualified')
            elif audience == 'enrolled':
                leads = leads.filter(status='enrolled')
            elif audience == 'hot':
                leads = leads.filter(is_hot=True)
            
            # Filter by channel availability
            if campaign.channel == 'whatsapp':
                leads = leads.exclude(Q(whatsapp_number__isnull=True) | Q(whatsapp_number=''))
            elif campaign.channel == 'sms':
                leads = leads.exclude(Q(phone__isnull=True) | Q(phone=''))
            elif campaign.channel == 'email':
                leads = leads.exclude(Q(email__isnull=True) | Q(email=''))
            
            # Create recipients
            created = 0
            for lead in leads:
                recipient, is_new = CampaignRecipient.objects.get_or_create(
                    campaign=campaign,
                    lead=lead,
                    defaults={'status': 'pending'}
                )
                if is_new:
                    created += 1
            
            return JsonResponse({
                'success': True,
                'created': created,
                'total': campaign.recipients.count()
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class CampaignSubmitForApprovalView(LoginRequiredMixin, View):
    """Submit campaign for manager approval."""
    
    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, status='draft')
        
        # Validate campaign has recipients
        if not campaign.recipients.exists():
            return JsonResponse({
                'success': False,
                'error': 'Add recipients before submitting for approval'
            }, status=400)
        
        # Validate content
        if not campaign.content:
            return JsonResponse({
                'success': False,
                'error': 'Campaign content is required'
            }, status=400)
        
        campaign.status = 'pending_approval'
        campaign.save()
        
        # TODO: Send notification to approvers
        
        return JsonResponse({
            'success': True,
            'message': 'Campaign submitted for approval'
        })


class CampaignApprovalView(LoginRequiredMixin, View):
    """Approve or reject a campaign."""
    
    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, status='pending_approval')
        
        # Check permission
        if not request.user.has_perm('crm.approve_campaign'):
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to approve campaigns'
            }, status=403)
        
        try:
            data = json.loads(request.body)
            action = data.get('action')  # 'approve' or 'reject'
            
            if action == 'approve':
                campaign.status = 'approved'
                campaign.approved_by = request.user
                campaign.approved_at = timezone.now()
                campaign.save()
                
                messages.success(request, 'Campaign approved successfully.')
                return JsonResponse({
                    'success': True,
                    'message': 'Campaign approved'
                })
                
            elif action == 'reject':
                rejection_reason = data.get('reason', '')
                campaign.status = 'draft'
                campaign.rejection_reason = rejection_reason
                campaign.save()
                
                # TODO: Notify creator of rejection
                
                return JsonResponse({
                    'success': True,
                    'message': 'Campaign rejected and returned to draft'
                })
                
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid action'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class CampaignScheduleView(LoginRequiredMixin, View):
    """Schedule a campaign for later sending."""
    
    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, status='approved')
        
        try:
            data = json.loads(request.body)
            scheduled_at = data.get('scheduled_at')
            
            if scheduled_at:
                campaign.scheduled_at = timezone.datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                campaign.status = 'scheduled'
                campaign.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Campaign scheduled for {campaign.scheduled_at}'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Scheduled time is required'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class CampaignSendView(LoginRequiredMixin, View):
    """Send campaign immediately."""
    
    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk, status__in=['approved', 'scheduled'])
        
        try:
            # Import messaging service
            from .services.messaging import BulkMessagingService
            
            # Update status
            campaign.status = 'sending'
            campaign.started_at = timezone.now()
            campaign.save()
            
            # Get pending recipients
            pending_recipients = campaign.recipients.filter(status='pending')
            
            # Send via appropriate channel
            service = BulkMessagingService(campaign.brand)
            
            sent_count = 0
            failed_count = 0
            
            for recipient in pending_recipients:
                try:
                    # Personalize content
                    content = campaign.content
                    if recipient.lead:
                        content = content.replace('{{first_name}}', recipient.lead.first_name or '')
                        content = content.replace('{{last_name}}', recipient.lead.last_name or '')
                        content = content.replace('{{full_name}}', recipient.lead.full_name or '')
                    
                    # Send based on channel
                    if campaign.channel == 'whatsapp':
                        phone = recipient.lead.whatsapp_number if recipient.lead else None
                        if phone:
                            service.send_whatsapp_text(phone, content)
                            recipient.status = 'sent'
                            recipient.sent_at = timezone.now()
                            sent_count += 1
                        else:
                            recipient.status = 'failed'
                            recipient.error_message = 'No WhatsApp number'
                            failed_count += 1
                            
                    elif campaign.channel == 'sms':
                        phone = recipient.lead.phone if recipient.lead else None
                        if phone:
                            service.send_sms(phone, content)
                            recipient.status = 'sent'
                            recipient.sent_at = timezone.now()
                            sent_count += 1
                        else:
                            recipient.status = 'failed'
                            recipient.error_message = 'No phone number'
                            failed_count += 1
                            
                    elif campaign.channel == 'email':
                        email = recipient.lead.email if recipient.lead else None
                        if email:
                            # Email sending would be handled differently
                            recipient.status = 'sent'
                            recipient.sent_at = timezone.now()
                            sent_count += 1
                        else:
                            recipient.status = 'failed'
                            recipient.error_message = 'No email address'
                            failed_count += 1
                    
                    recipient.save()
                    
                except Exception as e:
                    recipient.status = 'failed'
                    recipient.error_message = str(e)[:500]
                    recipient.save()
                    failed_count += 1
            
            # Update campaign status
            campaign.status = 'sent'
            campaign.completed_at = timezone.now()
            campaign.save()
            
            return JsonResponse({
                'success': True,
                'sent': sent_count,
                'failed': failed_count,
                'message': f'Campaign sent: {sent_count} successful, {failed_count} failed'
            })
            
        except Exception as e:
            campaign.status = 'approved'  # Reset to approved on error
            campaign.save()
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


# Message Template Views

class TemplateListView(LoginRequiredMixin, ListView):
    """List message templates."""
    
    model = MessageTemplate
    template_name = 'crm/campaigns/template_list.html'
    context_object_name = 'templates'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = MessageTemplate.objects.all()
        
        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status.upper())
        
        channel = self.request.GET.get('channel')
        if channel:
            queryset = queryset.filter(channel_type=channel.upper())
        
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(body__icontains=q)
            )
        
        return queryset.order_by('channel_type', 'name')


class TemplateForm(forms.ModelForm):
    """Form for message templates."""
    
    class Meta:
        model = MessageTemplate
        fields = [
            'name', 'slug', 'description', 'channel_type', 'category',
            'header_type', 'header_content', 'body', 'footer',
            'email_subject', 'variables', 'campus'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg',
                'rows': 2
            }),
            'channel_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'
            }),
            'header_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'
            }),
            'header_content': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg',
                'rows': 2
            }),
            'body': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg',
                'rows': 6
            }),
            'footer': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'
            }),
            'email_subject': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'
            }),
            'variables': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg font-mono text-sm',
                'rows': 3,
                'placeholder': '["first_name", "programme_name"]'
            }),
            'campus': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make optional fields not required
        self.fields['description'].required = False
        self.fields['header_content'].required = False
        self.fields['footer'].required = False
        self.fields['email_subject'].required = False


class TemplateCreateView(LoginRequiredMixin, CreateView):
    """Create a new message template."""
    
    model = MessageTemplate
    form_class = TemplateForm
    template_name = 'crm/campaigns/template_form.html'
    success_url = reverse_lazy('crm:template_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Template created successfully.')
        return super().form_valid(form)


class TemplateUpdateView(LoginRequiredMixin, UpdateView):
    """Update a message template."""
    
    model = MessageTemplate
    form_class = TemplateForm
    template_name = 'crm/campaigns/template_form.html'
    success_url = reverse_lazy('crm:template_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Template updated successfully.')
        return super().form_valid(form)


class TemplatePreviewView(LoginRequiredMixin, View):
    """Preview a template with sample data."""
    
    def get(self, request, pk):
        template = get_object_or_404(MessageTemplate, pk=pk)
        
        # Sample data for preview
        sample_data = {
            '{{first_name}}': 'John',
            '{{last_name}}': 'Doe',
            '{{full_name}}': 'John Doe',
            '{{programme_name}}': 'Business Management',
            '{{campus_name}}': 'Johannesburg',
            '{{intake_date}}': 'January 2025',
        }
        
        content = template.content
        for placeholder, value in sample_data.items():
            content = content.replace(placeholder, value)
        
        return JsonResponse({
            'name': template.name,
            'channel': template.channel,
            'subject': template.subject,
            'content': content,
            'original_content': template.content,
        })
