"""
Omnichannel Inbox Views

Unified inbox for managing conversations across all channels:
- WhatsApp
- Facebook Messenger
- Instagram DM
- SMS
- Email
"""
import json
from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q, Count, Max, F
from django.utils import timezone
from django.urls import reverse

from tenants.models import Brand, Campus
from crm.communication_models import (
    Conversation, Message, ConversationTag, MessageTemplate,
    SocialChannel, SMSConfig, EmailAccount
)
from crm.services.messaging import MessagingService
from core.context_processors import get_selected_campus


class InboxListView(LoginRequiredMixin, ListView):
    """
    Main inbox view showing all conversations.
    
    Features:
    - Filter by channel (whatsapp, facebook, instagram, sms, email)
    - Filter by status (open, pending, closed)
    - Filter by assigned agent
    - Search by contact name/phone/email
    - Sort by last message time
    """
    model = Conversation
    template_name = 'crm/inbox/conversation_list.html'
    context_object_name = 'conversations'
    paginate_by = 25
    
    def get_queryset(self):
        user = self.request.user
        queryset = Conversation.objects.select_related(
            'campus', 'campus__brand', 'lead', 'assigned_agent',
            'social_channel', 'sms_config', 'email_account'
        ).prefetch_related('tags')
        
        # Apply global campus filter
        selected_campus = get_selected_campus(self.request)
        if selected_campus:
            queryset = queryset.filter(
                Q(campus=selected_campus) | Q(campus__isnull=True)
            )
        
        # Filter by channel
        channel = self.request.GET.get('channel')
        if channel:
            queryset = queryset.filter(channel_type=channel)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        else:
            # Default to open conversations
            queryset = queryset.exclude(status='closed')
        
        # Filter by assignment
        assignment = self.request.GET.get('assigned')
        if assignment == 'me':
            queryset = queryset.filter(assigned_agent=user)
        elif assignment == 'unassigned':
            queryset = queryset.filter(assigned_agent__isnull=True)
        elif assignment and assignment.isdigit():
            queryset = queryset.filter(assigned_agent_id=int(assignment))
        
        # Filter by tag
        tag = self.request.GET.get('tag')
        if tag:
            queryset = queryset.filter(tags__name=tag)
        
        # Search
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(contact_name__icontains=search) |
                Q(contact_phone__icontains=search) |
                Q(contact_email__icontains=search) |
                Q(subject__icontains=search)
            )
        
        # Order by last message
        return queryset.order_by('-last_message_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        
        # Get counts for filter badges
        base_qs = Conversation.objects.all()
        if not user.is_superuser:
            if hasattr(user, 'profile') and user.profile.brand:
                base_qs = base_qs.filter(campus__brand=user.profile.brand)
        
        context['counts'] = {
            'all': base_qs.exclude(status='closed').count(),
            'open': base_qs.filter(status='open').count(),
            'pending': base_qs.filter(status='pending').count(),
            'mine': base_qs.filter(assigned_agent=user, status='open').count(),
            'unassigned': base_qs.filter(assigned_agent__isnull=True, status='open').count(),
        }
        
        # Channel counts
        context['channel_counts'] = dict(
            base_qs.exclude(status='closed')
            .values('channel_type')
            .annotate(count=Count('id'))
            .values_list('channel_type', 'count')
        )
        
        # Available tags
        if hasattr(user, 'profile') and user.profile.brand:
            context['tags'] = ConversationTag.objects.filter(campus__brand=user.profile.brand)
        else:
            context['tags'] = ConversationTag.objects.all()
        
        # Current filters
        context['current_filters'] = {
            'channel': self.request.GET.get('channel', ''),
            'status': self.request.GET.get('status', ''),
            'assigned': self.request.GET.get('assigned', ''),
            'tag': self.request.GET.get('tag', ''),
            'q': self.request.GET.get('q', ''),
        }
        
        return context


class ConversationDetailView(LoginRequiredMixin, DetailView):
    """
    Conversation thread view.
    
    Shows full message history with:
    - Message timeline
    - Contact info sidebar
    - Quick reply composer
    - Assignment controls
    """
    model = Conversation
    template_name = 'crm/inbox/conversation_detail.html'
    context_object_name = 'conversation'
    
    def get_object(self, queryset=None):
        conversation = get_object_or_404(
            Conversation.objects.select_related(
                'campus', 'campus__brand', 'lead', 'assigned_agent',
                'social_channel', 'sms_config', 'email_account'
            ).prefetch_related('tags'),
            pk=self.kwargs['pk']
        )
        
        # Mark as read
        conversation.unread_count = 0
        conversation.save(update_fields=['unread_count'])
        
        return conversation
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = self.object
        
        # Get messages
        context['messages'] = conversation.messages.select_related(
            'template'
        ).order_by('created_at')
        
        # Check if we can send messages
        service = MessagingService(conversation)
        can_send, reason = service.can_send_message()
        context['can_send'] = can_send
        context['send_reason'] = reason
        
        can_template, template_reason = service.can_send_template()
        context['can_template'] = can_template
        
        # Get available templates for this channel
        if conversation.channel == 'whatsapp' and conversation.brand:
            context['templates'] = MessageTemplate.objects.filter(
                brand=conversation.brand,
                channel='whatsapp',
                is_approved=True
            )
        else:
            context['templates'] = MessageTemplate.objects.none()
        
        # Get lead info if linked
        if conversation.lead:
            context['lead'] = conversation.lead
        
        # Quick actions based on channel
        context['quick_replies'] = self._get_quick_replies(conversation)
        
        # Agents for assignment
        from django.contrib.auth import get_user_model
        User = get_user_model()
        context['agents'] = User.objects.filter(
            is_active=True,
            is_staff=True
        ).order_by('first_name', 'last_name')
        
        # Available tags
        if conversation.brand:
            context['available_tags'] = ConversationTag.objects.filter(
                brand=conversation.brand
            )
        else:
            context['available_tags'] = ConversationTag.objects.all()
        
        return context
    
    def _get_quick_replies(self, conversation):
        """Get suggested quick replies based on channel and context."""
        replies = []
        
        if conversation.channel == 'whatsapp':
            replies = [
                {'text': 'Hi! How can I help you today?', 'label': 'Greeting'},
                {'text': 'Thank you for your message. Let me check on that for you.', 'label': 'Acknowledge'},
                {'text': 'Is there anything else I can help you with?', 'label': 'Follow-up'},
            ]
        elif conversation.channel == 'email':
            replies = [
                {'text': 'Thank you for reaching out.', 'label': 'Thanks'},
                {'text': 'I will look into this and get back to you shortly.', 'label': 'Acknowledge'},
            ]
        
        return replies


class SendMessageView(LoginRequiredMixin, View):
    """
    AJAX endpoint for sending messages.
    
    POST /crm/inbox/<id>/send/
    {
        "type": "text|media|template|email",
        "text": "...",
        "media_url": "...",
        "media_type": "image|video|document",
        "template_id": 123,
        "variables": {...},
        "subject": "...",  // for email
    }
    """
    
    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        msg_type = data.get('type', 'text')
        
        try:
            service = MessagingService(conversation)
            
            if msg_type == 'text':
                text = data.get('text', '').strip()
                if not text:
                    return JsonResponse({'error': 'Text is required'}, status=400)
                
                message = service.send_text(text, sender=request.user)
                
            elif msg_type == 'media':
                media_url = data.get('media_url')
                media_type = data.get('media_type', 'image')
                caption = data.get('caption')
                
                if not media_url:
                    return JsonResponse({'error': 'Media URL is required'}, status=400)
                
                message = service.send_media(
                    media_type, media_url,
                    caption=caption,
                    sender=request.user
                )
                
            elif msg_type == 'template':
                template_id = data.get('template_id')
                variables = data.get('variables', {})
                
                if not template_id:
                    return JsonResponse({'error': 'Template ID is required'}, status=400)
                
                template = get_object_or_404(MessageTemplate, pk=template_id)
                message = service.send_template(template, variables, sender=request.user)
                
            elif msg_type == 'email':
                subject = data.get('subject', 'No Subject')
                body = data.get('text', '')
                html_body = data.get('html_body')
                cc = data.get('cc', [])
                bcc = data.get('bcc', [])
                
                message = service.send_email(
                    subject, body,
                    html_body=html_body,
                    sender=request.user,
                    cc=cc,
                    bcc=bcc
                )
            else:
                return JsonResponse({'error': f'Unknown message type: {msg_type}'}, status=400)
            
            return JsonResponse({
                'success': True,
                'message_id': message.id,
                'status': message.status,
                'text': message.text,
                'sent_at': message.sent_at.isoformat() if message.sent_at else None
            })
            
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class AssignConversationView(LoginRequiredMixin, View):
    """
    Assign or reassign a conversation to an agent.
    
    POST /crm/inbox/<id>/assign/
    {
        "agent_id": 123  // or null to unassign
    }
    """
    
    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        agent_id = data.get('agent_id')
        
        if agent_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            agent = get_object_or_404(User, pk=agent_id)
            conversation.assigned_agent = agent
        else:
            conversation.assigned_agent = None
        
        conversation.save()
        
        return JsonResponse({
            'success': True,
            'assigned_agent': {
                'id': conversation.assigned_agent.id,
                'name': conversation.assigned_agent.get_full_name()
            } if conversation.assigned_agent else None
        })


class UpdateConversationStatusView(LoginRequiredMixin, View):
    """
    Update conversation status.
    
    POST /crm/inbox/<id>/status/
    {
        "status": "open|pending|closed"
    }
    """
    
    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        status = data.get('status')
        if status not in ('open', 'pending', 'closed'):
            return JsonResponse({'error': 'Invalid status'}, status=400)
        
        conversation.status = status
        
        if status == 'closed':
            conversation.closed_at = timezone.now()
            conversation.closed_by = request.user
        
        conversation.save()
        
        return JsonResponse({
            'success': True,
            'status': conversation.status
        })


class AddTagView(LoginRequiredMixin, View):
    """
    Add a tag to a conversation.
    
    POST /crm/inbox/<id>/tags/
    {
        "tag": "tag_name"  // or tag_id
    }
    """
    
    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        tag_value = data.get('tag')
        if not tag_value:
            return JsonResponse({'error': 'Tag is required'}, status=400)
        
        # Find or create tag
        if isinstance(tag_value, int) or (isinstance(tag_value, str) and tag_value.isdigit()):
            tag = get_object_or_404(ConversationTag, pk=int(tag_value))
        else:
            tag, _ = ConversationTag.objects.get_or_create(
                brand=conversation.brand,
                name=tag_value,
                defaults={'color': '#6B7280'}
            )
        
        conversation.tags.add(tag)
        
        return JsonResponse({
            'success': True,
            'tag': {'id': tag.id, 'name': tag.name, 'color': tag.color}
        })
    
    def delete(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        tag_id = data.get('tag_id')
        if tag_id:
            tag = get_object_or_404(ConversationTag, pk=tag_id)
            conversation.tags.remove(tag)
        
        return JsonResponse({'success': True})


class LinkLeadView(LoginRequiredMixin, View):
    """
    Link a conversation to a lead.
    
    POST /crm/inbox/<id>/link-lead/
    {
        "lead_id": 123
    }
    
    Or create a new lead:
    {
        "create": true,
        "first_name": "...",
        "last_name": "...",
        ...
    }
    """
    
    def post(self, request, pk):
        from crm.models import Lead
        
        conversation = get_object_or_404(Conversation, pk=pk)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        if data.get('create'):
            # Create new lead
            lead = Lead.objects.create(
                brand=conversation.brand,
                campus=conversation.campus,
                first_name=data.get('first_name', conversation.contact_name or 'Unknown'),
                last_name=data.get('last_name', ''),
                phone=conversation.contact_phone,
                email=conversation.contact_email,
                source=f'{conversation.channel}_inbound',
                status='new'
            )
        else:
            lead_id = data.get('lead_id')
            if not lead_id:
                return JsonResponse({'error': 'lead_id is required'}, status=400)
            
            lead = get_object_or_404(Lead, pk=lead_id)
        
        conversation.lead = lead
        conversation.save()
        
        return JsonResponse({
            'success': True,
            'lead': {
                'id': lead.id,
                'name': lead.full_name,
                'status': lead.status
            }
        })


class InboxStatsView(LoginRequiredMixin, View):
    """
    Get inbox statistics for the current user.
    
    Used for real-time updates and dashboard widgets.
    """
    
    def get(self, request):
        user = request.user
        
        base_qs = Conversation.objects.all()
        if not user.is_superuser:
            if hasattr(user, 'profile') and user.profile.brand:
                base_qs = base_qs.filter(campus__brand=user.profile.brand)
        
        stats = {
            'total_open': base_qs.filter(status='open').count(),
            'unassigned': base_qs.filter(status='open', assigned_agent__isnull=True).count(),
            'my_conversations': base_qs.filter(assigned_agent=user, status='open').count(),
            'my_unread': base_qs.filter(
                assigned_agent=user, 
                unread_count__gt=0
            ).aggregate(total=Count('id'))['total'],
            'by_channel': dict(
                base_qs.filter(status='open')
                .values('channel_type')
                .annotate(count=Count('id'))
                .values_list('channel_type', 'count')
            ),
            'recent': list(
                base_qs.filter(status='open')
                .order_by('-last_message_at')[:5]
                .values('id', 'contact_name', 'channel', 'last_message_at')
            )
        }
        
        return JsonResponse(stats)


class SearchLeadsView(LoginRequiredMixin, View):
    """
    Search leads for linking to conversations.
    
    GET /crm/inbox/search-leads/?q=...
    """
    
    def get(self, request):
        from crm.models import Lead
        
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return JsonResponse({'leads': []})
        
        leads = Lead.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        )[:20]
        
        return JsonResponse({
            'leads': [
                {
                    'id': lead.id,
                    'name': lead.full_name,
                    'email': lead.email,
                    'phone': lead.phone,
                    'status': lead.status
                }
                for lead in leads
            ]
        })


# URL configuration
def get_inbox_urls():
    """
    Return URL patterns for inbox views.
    
    Add to your urls.py:
        path('inbox/', include(get_inbox_urls()))
    """
    from django.urls import path
    
    return [
        path('', InboxListView.as_view(), name='inbox_list'),
        path('stats/', InboxStatsView.as_view(), name='inbox_stats'),
        path('search-leads/', SearchLeadsView.as_view(), name='inbox_search_leads'),
        path('<int:pk>/', ConversationDetailView.as_view(), name='conversation_detail'),
        path('<int:pk>/send/', SendMessageView.as_view(), name='send_message'),
        path('<int:pk>/assign/', AssignConversationView.as_view(), name='assign_conversation'),
        path('<int:pk>/status/', UpdateConversationStatusView.as_view(), name='update_status'),
        path('<int:pk>/tags/', AddTagView.as_view(), name='conversation_tags'),
        path('<int:pk>/link-lead/', LinkLeadView.as_view(), name='link_lead'),
    ]
