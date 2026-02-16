"""
CRM Analytics Views

Enhanced dashboard with omnichannel metrics, pipeline analytics, and performance tracking.
"""
import json
from datetime import timedelta
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.http import JsonResponse
from django.utils import timezone

from .models import (
    Lead, Opportunity, Application,
)
from .communication_models import (
    Conversation, Message, Campaign, CampaignRecipient,
)
from core.context_processors import get_selected_campus


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """
    Comprehensive CRM analytics dashboard with charts and metrics.
    """
    template_name = 'crm/analytics/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        
        # Date ranges
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        last_90_days = today - timedelta(days=90)
        start_of_month = today.replace(day=1)
        
        # Apply global campus filter
        selected_campus = get_selected_campus(self.request)
        
        # Filter by user's brands
        user_brands = None
        if not user.is_superuser:
            user_brands = user.accessible_brands.all()
        
        # ====== Pipeline Metrics ======
        opportunities = Opportunity.objects.all()
        if selected_campus:
            opportunities = opportunities.filter(brand__campus=selected_campus)
        if user_brands:
            opportunities = opportunities.filter(brand__in=user_brands)
        
        # Active pipeline value
        active_stages = ['DISCOVERY', 'QUALIFICATION', 'PROPOSAL', 'NEGOTIATION', 'COMMITTED']
        active_opportunities = opportunities.filter(stage__in=active_stages)
        
        context['pipeline_metrics'] = {
            'total_count': active_opportunities.count(),
            'total_value': active_opportunities.aggregate(total=Sum('value'))['total'] or 0,
            'weighted_value': sum(
                (o.value or 0) * (o.probability or 0) / 100 
                for o in active_opportunities
            ),
            'avg_probability': active_opportunities.aggregate(avg=Avg('probability'))['avg'] or 0,
        }
        
        # Pipeline by stage
        context['pipeline_by_stage'] = []
        for stage, label in Opportunity.STAGE_CHOICES:
            if stage in active_stages:
                stage_opps = opportunities.filter(stage=stage)
                context['pipeline_by_stage'].append({
                    'stage': stage,
                    'label': label,
                    'count': stage_opps.count(),
                    'value': stage_opps.aggregate(total=Sum('value'))['total'] or 0,
                })
        
        # Won/Lost this month
        context['wins_this_month'] = opportunities.filter(
            stage='WON',
            updated_at__date__gte=start_of_month
        ).count()
        context['wins_value_this_month'] = opportunities.filter(
            stage='WON',
            updated_at__date__gte=start_of_month
        ).aggregate(total=Sum('value'))['total'] or 0
        
        context['losses_this_month'] = opportunities.filter(
            stage='LOST',
            updated_at__date__gte=start_of_month
        ).count()
        
        # Win rate
        closed = opportunities.filter(
            stage__in=['WON', 'LOST'],
            updated_at__date__gte=last_90_days
        )
        won = closed.filter(stage='WON').count()
        total_closed = closed.count()
        context['win_rate'] = round(won / total_closed * 100, 1) if total_closed > 0 else 0
        
        # ====== Channel Performance ======
        conversations = Conversation.objects.all()
        if user_brands:
            conversations = conversations.filter(brand__in=user_brands)
        
        messages = Message.objects.all()
        if user_brands:
            messages = messages.filter(conversation__brand__in=user_brands)
        
        # Messages by channel
        context['channel_metrics'] = []
        for channel, label in Conversation.CHANNEL_TYPES:
            channel_convs = conversations.filter(channel_type=channel)
            channel_msgs = messages.filter(conversation__channel_type=channel)
            
            context['channel_metrics'].append({
                'channel': channel,
                'label': label,
                'conversations': channel_convs.count(),
                'messages_sent': channel_msgs.filter(direction='outbound').count(),
                'messages_received': channel_msgs.filter(direction='inbound').count(),
                'unread': channel_convs.filter(unread_count__gt=0).count(),
            })
        
        # Total inbox stats
        context['inbox_stats'] = {
            'total_conversations': conversations.count(),
            'open': conversations.filter(status='open').count(),
            'pending': conversations.filter(status='pending').count(),
            'unread_total': conversations.aggregate(total=Sum('unread_count'))['total'] or 0,
            'avg_response_time': self._calculate_avg_response_time(messages),
        }
        
        # ====== Lead Metrics ======
        leads = Lead.objects.all()
        if user_brands:
            leads = leads.filter(brand__in=user_brands)
        
        context['lead_metrics'] = {
            'total': leads.count(),
            'new_this_month': leads.filter(created_at__date__gte=start_of_month).count(),
            'new_this_week': leads.filter(created_at__date__gte=last_7_days).count(),
            'hot_leads': leads.filter(priority='HIGH').count(),
        }
        
        # Leads by status
        context['leads_by_status'] = leads.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # ====== Application Metrics ======
        applications = Application.objects.all()
        if user_brands:
            applications = applications.filter(brand__in=user_brands)
        
        context['application_metrics'] = {
            'total': applications.count(),
            'pending': applications.filter(status='pending').count(),
            'under_review': applications.filter(status='under_review').count(),
            'approved': applications.filter(status='approved').count(),
            'enrolled': applications.filter(status='enrolled').count(),
            'this_month': applications.filter(submitted_at__date__gte=start_of_month).count(),
        }
        
        # ====== Campaign Metrics ======
        campaigns = Campaign.objects.all()
        if user_brands:
            campaigns = campaigns.filter(brand__in=user_brands)
        
        context['campaign_metrics'] = {
            'total': campaigns.count(),
            'sent': campaigns.filter(status='sent').count(),
            'scheduled': campaigns.filter(status='scheduled').count(),
            'pending_approval': campaigns.filter(status='pending_approval').count(),
        }
        
        # Campaign performance (last 30 days)
        recent_campaigns = campaigns.filter(status='sent', completed_at__date__gte=last_30_days)
        recipients = CampaignRecipient.objects.filter(campaign__in=recent_campaigns)
        
        total_recipients = recipients.count()
        if total_recipients > 0:
            context['campaign_performance'] = {
                'total_sent': total_recipients,
                'delivered': recipients.filter(status='delivered').count(),
                'delivery_rate': round(
                    recipients.filter(status='delivered').count() / total_recipients * 100, 1
                ),
                'opened': recipients.filter(opened_at__isnull=False).count(),
                'open_rate': round(
                    recipients.filter(opened_at__isnull=False).count() / total_recipients * 100, 1
                ),
            }
        else:
            context['campaign_performance'] = {
                'total_sent': 0, 'delivered': 0, 'delivery_rate': 0, 'opened': 0, 'open_rate': 0
            }
        
        # ====== Agent Performance ======
        if user.is_superuser or user.has_perm('crm.view_all_analytics'):
            context['agent_performance'] = self._get_agent_performance(
                user_brands, last_30_days
            )
        
        # ====== Trend Data for Charts ======
        context['lead_trend'] = self._get_lead_trend(leads, last_30_days)
        context['message_trend'] = self._get_message_trend(messages, last_7_days)
        
        return context
    
    def _calculate_avg_response_time(self, messages):
        """Calculate average response time in minutes."""
        # This is a simplified calculation - in production you'd want to
        # calculate the time between inbound and subsequent outbound messages
        return 15  # Placeholder - implement actual calculation
    
    def _get_agent_performance(self, user_brands, since_date):
        """Get agent performance metrics."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        agents = User.objects.filter(
            is_active=True,
            groups__name__in=['CRM Sales', 'CRM Admin']
        ).distinct()
        
        performance = []
        for agent in agents[:10]:  # Top 10 agents
            # Conversations handled
            convs = Conversation.objects.filter(
                assigned_to=agent,
                updated_at__date__gte=since_date
            )
            if user_brands:
                convs = convs.filter(brand__in=user_brands)
            
            # Messages sent
            msgs = Message.objects.filter(
                sent_by=agent,
                created_at__date__gte=since_date,
                direction='outbound'
            )
            if user_brands:
                msgs = msgs.filter(conversation__brand__in=user_brands)
            
            # Opportunities won
            opps_won = Opportunity.objects.filter(
                assigned_to=agent,
                stage='WON',
                updated_at__date__gte=since_date
            )
            if user_brands:
                opps_won = opps_won.filter(brand__in=user_brands)
            
            performance.append({
                'agent': agent,
                'conversations': convs.count(),
                'messages_sent': msgs.count(),
                'opportunities_won': opps_won.count(),
                'revenue_won': opps_won.aggregate(total=Sum('value'))['total'] or 0,
            })
        
        # Sort by revenue
        performance.sort(key=lambda x: x['revenue_won'], reverse=True)
        return performance
    
    def _get_lead_trend(self, leads, since_date):
        """Get daily lead creation trend."""
        trend = leads.filter(
            created_at__date__gte=since_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        return list(trend)
    
    def _get_message_trend(self, messages, since_date):
        """Get daily message trend."""
        trend = messages.filter(
            created_at__date__gte=since_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            inbound=Count('id', filter=Q(direction='inbound')),
            outbound=Count('id', filter=Q(direction='outbound'))
        ).order_by('date')
        
        return list(trend)


class AnalyticsAPIView(LoginRequiredMixin, View):
    """API endpoints for analytics data (for AJAX chart updates)."""
    
    def get(self, request, metric_type):
        """Get specific metric data."""
        user = request.user
        
        # Filter by user's brands
        user_brands = None
        if not user.is_superuser:
            user_brands = user.accessible_brands.all()
        
        if metric_type == 'pipeline_funnel':
            data = self._get_pipeline_funnel(user_brands)
        elif metric_type == 'channel_distribution':
            data = self._get_channel_distribution(user_brands)
        elif metric_type == 'conversion_trend':
            data = self._get_conversion_trend(user_brands)
        elif metric_type == 'lead_sources':
            data = self._get_lead_sources(user_brands)
        else:
            return JsonResponse({'error': 'Unknown metric type'}, status=400)
        
        return JsonResponse(data)
    
    def _get_pipeline_funnel(self, user_brands):
        """Get pipeline funnel data for chart."""
        opportunities = Opportunity.objects.all()
        if user_brands:
            opportunities = opportunities.filter(brand__in=user_brands)
        
        stages = ['DISCOVERY', 'QUALIFICATION', 'PROPOSAL', 'NEGOTIATION', 'COMMITTED', 'WON']
        data = []
        
        for stage in stages:
            count = opportunities.filter(stage=stage).count()
            value = opportunities.filter(stage=stage).aggregate(
                total=Sum('value')
            )['total'] or 0
            data.append({
                'stage': stage,
                'count': count,
                'value': value
            })
        
        return {'funnel': data}
    
    def _get_channel_distribution(self, user_brands):
        """Get message distribution by channel."""
        messages = Message.objects.all()
        if user_brands:
            messages = messages.filter(conversation__brand__in=user_brands)
        
        distribution = messages.values(
            'conversation__channel_type'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {'distribution': list(distribution)}
    
    def _get_conversion_trend(self, user_brands):
        """Get conversion trend over time."""
        last_90_days = timezone.now().date() - timedelta(days=90)
        
        opportunities = Opportunity.objects.filter(
            stage__in=['WON', 'LOST'],
            updated_at__date__gte=last_90_days
        )
        if user_brands:
            opportunities = opportunities.filter(brand__in=user_brands)
        
        trend = opportunities.annotate(
            week=TruncWeek('updated_at')
        ).values('week').annotate(
            won=Count('id', filter=Q(stage='WON')),
            lost=Count('id', filter=Q(stage='LOST'))
        ).order_by('week')
        
        return {'trend': list(trend)}
    
    def _get_lead_sources(self, user_brands):
        """Get leads by source."""
        leads = Lead.objects.all()
        if user_brands:
            leads = leads.filter(brand__in=user_brands)
        
        sources = leads.values('source__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {'sources': list(sources)}
