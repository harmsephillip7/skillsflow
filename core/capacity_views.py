"""
Campus Capacity & Utilization Dashboard Views

Provides comprehensive capacity analytics:
- Total capacity vs current utilization
- On-campus vs off-site learner distribution
- Historical trends using IntakeCapacitySnapshot
- Per-campus breakdowns with drill-down support
"""
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.http import JsonResponse
from django.views import View

from tenants.models import Campus
from academics.models import Enrollment
from intakes.models import Intake, IntakeEnrollment, IntakeCapacitySnapshot
from core.context_processors import get_selected_campus


class CapacityDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Campus Capacity & Utilization Dashboard
    
    Shows:
    - Summary cards with total/on-campus capacity and utilization
    - Utilization gauges per campus
    - Historical trend charts
    - Learner distribution by delivery mode
    - Campus comparison table
    """
    template_name = 'dashboard/capacity.html'
    login_url = '/login/'
    
    def test_func(self):
        """Allow staff or superusers"""
        user = self.request.user
        return user.is_staff or user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get global campus filter
        selected_campus = get_selected_campus(self.request)
        context['selected_campus'] = selected_campus
        
        # Get all active campuses or just the selected one
        if selected_campus:
            campuses = Campus.objects.filter(pk=selected_campus.pk, is_active=True)
        else:
            campuses = Campus.objects.filter(is_active=True)
        
        context['campuses'] = campuses
        
        # Calculate summary metrics
        context['summary'] = self._get_summary_metrics(campuses)
        
        # Get per-campus breakdown
        context['campus_data'] = self._get_campus_breakdown(campuses)
        
        # Get learner distribution by delivery mode
        context['delivery_distribution'] = self._get_delivery_distribution(campuses)
        
        # Get historical trends (last 90 days)
        context['trend_data'] = self._get_capacity_trends(campuses)
        
        # Get alerts for campuses approaching capacity
        context['capacity_alerts'] = self._get_capacity_alerts(campuses)
        
        return context
    
    def _get_summary_metrics(self, campuses):
        """Calculate overall summary metrics across all selected campuses"""
        total_max_capacity = campuses.aggregate(
            total=Sum('max_learner_capacity')
        )['total'] or 0
        
        total_on_campus_capacity = campuses.aggregate(
            total=Sum('on_campus_capacity')
        )['total'] or 0
        
        # Get current learner counts
        total_learners = Enrollment.objects.filter(
            campus__in=campuses,
            status__in=['ENROLLED', 'ACTIVE']
        ).count()
        
        # Get on-campus learners (from intakes with ON_CAMPUS delivery mode)
        on_campus_intakes = Intake.objects.filter(
            campus__in=campuses,
            delivery_mode='ON_CAMPUS',
            status__in=['ACTIVE', 'ENROLLMENT_OPEN']
        )
        on_campus_learners = IntakeEnrollment.objects.filter(
            intake__in=on_campus_intakes,
            status__in=['ENROLLED', 'ACTIVE']
        ).count()
        
        # Get off-site learners
        off_site_intakes = Intake.objects.filter(
            campus__in=campuses,
            delivery_mode__in=['OFF_SITE', 'WORKPLACE'],
            status__in=['ACTIVE', 'ENROLLMENT_OPEN']
        )
        off_site_learners = IntakeEnrollment.objects.filter(
            intake__in=off_site_intakes,
            status__in=['ENROLLED', 'ACTIVE']
        ).count()
        
        # Calculate utilization percentages
        total_utilization = round((total_learners / total_max_capacity * 100), 1) if total_max_capacity > 0 else 0
        on_campus_utilization = round((on_campus_learners / total_on_campus_capacity * 100), 1) if total_on_campus_capacity > 0 else 0
        
        # Calculate average target
        avg_target = campuses.aggregate(avg=Avg('target_utilization'))['avg'] or 85
        
        # Available capacity
        available_total = total_max_capacity - total_learners
        available_on_campus = total_on_campus_capacity - on_campus_learners
        
        return {
            'total_max_capacity': total_max_capacity,
            'total_on_campus_capacity': total_on_campus_capacity,
            'total_learners': total_learners,
            'on_campus_learners': on_campus_learners,
            'off_site_learners': off_site_learners,
            'online_learners': total_learners - on_campus_learners - off_site_learners,
            'total_utilization': total_utilization,
            'on_campus_utilization': on_campus_utilization,
            'target_utilization': round(avg_target, 1),
            'available_total': available_total,
            'available_on_campus': available_on_campus,
            'utilization_status': self._get_utilization_status(total_utilization, avg_target),
            'on_campus_status': self._get_utilization_status(on_campus_utilization, avg_target),
        }
    
    def _get_utilization_status(self, current, target):
        """Get status color based on utilization vs target"""
        if current >= target:
            return 'success'  # At or above target
        elif current >= target * 0.8:
            return 'warning'  # Within 80% of target
        else:
            return 'danger'  # Below 80% of target
    
    def _get_campus_breakdown(self, campuses):
        """Get detailed breakdown per campus"""
        campus_data = []
        
        for campus in campuses:
            # Get enrollment counts
            total_learners = Enrollment.objects.filter(
                campus=campus,
                status__in=['ENROLLED', 'ACTIVE']
            ).count()
            
            # On-campus learners
            on_campus_intakes = Intake.objects.filter(
                campus=campus,
                delivery_mode='ON_CAMPUS',
                status__in=['ACTIVE', 'ENROLLMENT_OPEN']
            )
            on_campus_learners = IntakeEnrollment.objects.filter(
                intake__in=on_campus_intakes,
                status__in=['ENROLLED', 'ACTIVE']
            ).count()
            
            # Off-site learners
            off_site_intakes = Intake.objects.filter(
                campus=campus,
                delivery_mode__in=['OFF_SITE', 'WORKPLACE'],
                status__in=['ACTIVE', 'ENROLLMENT_OPEN']
            )
            off_site_learners = IntakeEnrollment.objects.filter(
                intake__in=off_site_intakes,
                status__in=['ENROLLED', 'ACTIVE']
            ).count()
            
            # Calculate utilizations
            total_util = round((total_learners / campus.max_learner_capacity * 100), 1) if campus.max_learner_capacity > 0 else 0
            on_campus_util = round((on_campus_learners / campus.on_campus_capacity * 100), 1) if campus.on_campus_capacity > 0 else 0
            
            # Active intakes count
            active_intakes = Intake.objects.filter(
                campus=campus,
                status__in=['ACTIVE', 'ENROLLMENT_OPEN']
            ).count()
            
            campus_data.append({
                'campus': campus,
                'total_learners': total_learners,
                'on_campus_learners': on_campus_learners,
                'off_site_learners': off_site_learners,
                'online_learners': total_learners - on_campus_learners - off_site_learners,
                'max_capacity': campus.max_learner_capacity,
                'on_campus_capacity': campus.on_campus_capacity,
                'total_utilization': total_util,
                'on_campus_utilization': on_campus_util,
                'target_utilization': campus.target_utilization,
                'available_total': campus.max_learner_capacity - total_learners,
                'available_on_campus': campus.on_campus_capacity - on_campus_learners,
                'active_intakes': active_intakes,
                'total_status': self._get_utilization_status(total_util, campus.target_utilization),
                'on_campus_status': self._get_utilization_status(on_campus_util, campus.target_utilization),
            })
        
        return campus_data
    
    def _get_delivery_distribution(self, campuses):
        """Get learner distribution by delivery mode"""
        distribution = []
        
        delivery_modes = [
            ('ON_CAMPUS', 'On Campus', '#10b981'),
            ('OFF_SITE', 'Off-Site', '#f59e0b'),
            ('WORKPLACE', 'Workplace', '#3b82f6'),
            ('ONLINE', 'Online', '#8b5cf6'),
            ('BLENDED', 'Blended', '#ec4899'),
        ]
        
        for mode, label, color in delivery_modes:
            intakes = Intake.objects.filter(
                campus__in=campuses,
                delivery_mode=mode,
                status__in=['ACTIVE', 'ENROLLMENT_OPEN']
            )
            count = IntakeEnrollment.objects.filter(
                intake__in=intakes,
                status__in=['ENROLLED', 'ACTIVE']
            ).count()
            
            if count > 0:
                distribution.append({
                    'mode': mode,
                    'label': label,
                    'count': count,
                    'color': color,
                })
        
        return distribution
    
    def _get_capacity_trends(self, campuses):
        """Get historical capacity trends from IntakeCapacitySnapshot"""
        today = date.today()
        start_date = today - timedelta(days=90)
        
        # Get snapshots for intakes in selected campuses
        snapshots = IntakeCapacitySnapshot.objects.filter(
            intake__campus__in=campuses,
            snapshot_date__gte=start_date
        ).values('snapshot_date').annotate(
            total_capacity=Sum('max_capacity'),
            total_enrolled=Sum('enrolled_count'),
            total_pending=Sum('pending_count'),
        ).order_by('snapshot_date')
        
        # Format for chart
        trend_data = {
            'labels': [],
            'capacity': [],
            'enrolled': [],
            'pending': [],
            'utilization': [],
        }
        
        for snapshot in snapshots:
            trend_data['labels'].append(snapshot['snapshot_date'].strftime('%Y-%m-%d'))
            trend_data['capacity'].append(snapshot['total_capacity'] or 0)
            trend_data['enrolled'].append(snapshot['total_enrolled'] or 0)
            trend_data['pending'].append(snapshot['total_pending'] or 0)
            
            # Calculate utilization
            if snapshot['total_capacity'] and snapshot['total_capacity'] > 0:
                util = round((snapshot['total_enrolled'] / snapshot['total_capacity']) * 100, 1)
            else:
                util = 0
            trend_data['utilization'].append(util)
        
        return trend_data
    
    def _get_capacity_alerts(self, campuses):
        """Get alerts for campuses with capacity issues"""
        alerts = []
        
        for campus in campuses:
            total_learners = Enrollment.objects.filter(
                campus=campus,
                status__in=['ENROLLED', 'ACTIVE']
            ).count()
            
            on_campus_intakes = Intake.objects.filter(
                campus=campus,
                delivery_mode='ON_CAMPUS',
                status__in=['ACTIVE', 'ENROLLMENT_OPEN']
            )
            on_campus_learners = IntakeEnrollment.objects.filter(
                intake__in=on_campus_intakes,
                status__in=['ENROLLED', 'ACTIVE']
            ).count()
            
            total_util = (total_learners / campus.max_learner_capacity * 100) if campus.max_learner_capacity > 0 else 0
            on_campus_util = (on_campus_learners / campus.on_campus_capacity * 100) if campus.on_campus_capacity > 0 else 0
            
            # Check for over-capacity
            if total_util > 100:
                alerts.append({
                    'campus': campus,
                    'type': 'danger',
                    'message': f'Over total capacity ({total_util:.1f}%)',
                    'icon': 'exclamation-triangle',
                })
            elif on_campus_util > 100:
                alerts.append({
                    'campus': campus,
                    'type': 'danger',
                    'message': f'Over on-campus capacity ({on_campus_util:.1f}%)',
                    'icon': 'exclamation-triangle',
                })
            # Check for approaching capacity (>90%)
            elif total_util > 90:
                alerts.append({
                    'campus': campus,
                    'type': 'warning',
                    'message': f'Approaching total capacity ({total_util:.1f}%)',
                    'icon': 'exclamation-circle',
                })
            elif on_campus_util > 90:
                alerts.append({
                    'campus': campus,
                    'type': 'warning',
                    'message': f'Approaching on-campus capacity ({on_campus_util:.1f}%)',
                    'icon': 'exclamation-circle',
                })
            # Check for under-utilization (<50%)
            elif total_util < 50:
                alerts.append({
                    'campus': campus,
                    'type': 'info',
                    'message': f'Under-utilized ({total_util:.1f}%) - sales opportunity',
                    'icon': 'arrow-trending-up',
                })
        
        return alerts


class CapacityTrendAPIView(LoginRequiredMixin, View):
    """API endpoint for capacity trend data (for AJAX chart updates)"""
    
    def get(self, request):
        campus_id = request.GET.get('campus')
        range_days = int(request.GET.get('range', 90))
        
        today = date.today()
        start_date = today - timedelta(days=range_days)
        
        # Get campus filter
        if campus_id and campus_id != 'all':
            campuses = Campus.objects.filter(pk=campus_id, is_active=True)
        else:
            selected_campus = get_selected_campus(request)
            if selected_campus:
                campuses = Campus.objects.filter(pk=selected_campus.pk, is_active=True)
            else:
                campuses = Campus.objects.filter(is_active=True)
        
        # Get snapshots
        snapshots = IntakeCapacitySnapshot.objects.filter(
            intake__campus__in=campuses,
            snapshot_date__gte=start_date
        ).values('snapshot_date').annotate(
            total_capacity=Sum('max_capacity'),
            total_enrolled=Sum('enrolled_count'),
        ).order_by('snapshot_date')
        
        data = {
            'labels': [s['snapshot_date'].strftime('%Y-%m-%d') for s in snapshots],
            'capacity': [s['total_capacity'] or 0 for s in snapshots],
            'enrolled': [s['total_enrolled'] or 0 for s in snapshots],
        }
        
        return JsonResponse(data)


class CampusCapacityDetailView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Detailed capacity view for a single campus"""
    template_name = 'dashboard/capacity_detail.html'
    login_url = '/login/'
    
    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        campus_id = self.kwargs.get('pk')
        campus = Campus.objects.get(pk=campus_id)
        context['campus'] = campus
        
        # Get detailed metrics
        context['metrics'] = self._get_detailed_metrics(campus)
        
        # Get intakes breakdown
        context['intakes'] = self._get_intakes_breakdown(campus)
        
        # Get historical data
        context['history'] = self._get_campus_history(campus)
        
        return context
    
    def _get_detailed_metrics(self, campus):
        """Get detailed metrics for a single campus"""
        total_learners = Enrollment.objects.filter(
            campus=campus,
            status__in=['ENROLLED', 'ACTIVE']
        ).count()
        
        # Breakdown by status
        status_breakdown = Enrollment.objects.filter(
            campus=campus
        ).values('status').annotate(count=Count('id'))
        
        return {
            'total_learners': total_learners,
            'max_capacity': campus.max_learner_capacity,
            'on_campus_capacity': campus.on_campus_capacity,
            'target_utilization': campus.target_utilization,
            'status_breakdown': {s['status']: s['count'] for s in status_breakdown},
        }
    
    def _get_intakes_breakdown(self, campus):
        """Get breakdown of active intakes"""
        intakes = Intake.objects.filter(
            campus=campus,
            status__in=['ACTIVE', 'ENROLLMENT_OPEN', 'RECRUITING']
        ).select_related('qualification')
        
        intake_data = []
        for intake in intakes:
            enrolled = IntakeEnrollment.objects.filter(
                intake=intake,
                status__in=['ENROLLED', 'ACTIVE']
            ).count()
            
            intake_data.append({
                'intake': intake,
                'enrolled': enrolled,
                'capacity': intake.max_capacity,
                'utilization': round((enrolled / intake.max_capacity * 100), 1) if intake.max_capacity > 0 else 0,
            })
        
        return intake_data
    
    def _get_campus_history(self, campus):
        """Get historical snapshot data for campus"""
        today = date.today()
        start_date = today - timedelta(days=180)
        
        snapshots = IntakeCapacitySnapshot.objects.filter(
            intake__campus=campus,
            snapshot_date__gte=start_date
        ).values('snapshot_date').annotate(
            capacity=Sum('max_capacity'),
            enrolled=Sum('enrolled_count'),
        ).order_by('snapshot_date')
        
        return list(snapshots)
