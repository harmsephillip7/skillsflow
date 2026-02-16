"""
Reports Views
Comprehensive organizational reports with campus filtering
"""
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Sum, Q, Avg, F, Value, CharField
from django.db.models.functions import TruncMonth, Coalesce
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


class CampusFilterMixin:
    """
    Mixin to apply campus filtering from session.
    Use get_campus_filter() to get the campus for filtering queries.
    """
    def get_campus_filter(self):
        """Returns the selected campus or None for 'all'"""
        campus_id = self.request.session.get('selected_campus_id', 'all')
        if campus_id == 'all':
            return None
        try:
            from tenants.models import Campus
            return Campus.objects.get(pk=campus_id, is_active=True)
        except:
            return None
    
    def filter_by_campus(self, queryset, campus_field='campus'):
        """
        Filter a queryset by the selected campus.
        campus_field: The field name that references the campus.
        """
        campus = self.get_campus_filter()
        if campus:
            return queryset.filter(**{campus_field: campus})
        return queryset


class ReportsView(LoginRequiredMixin, UserPassesTestMixin, CampusFilterMixin, TemplateView):
    """
    Comprehensive Reports Dashboard
    Shows summary of projects, campuses, enrollments, capacity
    """
    template_name = 'dashboard/reports.html'
    login_url = '/login/'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.now().date()
        current_year = today.year
        
        # Campus filter
        selected_campus = self.get_campus_filter()
        context['campus_filter_active'] = selected_campus is not None
        
        # Get all report sections
        context['campus_overview'] = self._get_campus_overview()
        context['project_summary'] = self._get_project_summary()
        context['enrollment_by_intake'] = self._get_enrollment_by_intake(current_year)
        context['capacity_utilization'] = self._get_capacity_utilization()
        context['qualification_breakdown'] = self._get_qualification_breakdown()
        context['cohort_overview'] = self._get_cohort_overview()
        context['monthly_trends'] = self._get_monthly_trends(current_year)
        
        return context
    
    def _get_campus_overview(self):
        """Get campus statistics and list"""
        from tenants.models import Campus
        from logistics.models import Venue
        from academics.models import Enrollment
        from learners.models import Learner
        
        campuses = Campus.objects.filter(is_active=True)
        selected_campus = self.get_campus_filter()
        
        if selected_campus:
            campuses = campuses.filter(pk=selected_campus.pk)
        
        campus_data = []
        for campus in campuses:
            # Get venue count and total capacity
            venues = Venue.objects.filter(campus=campus, is_active=True)
            venue_count = venues.count()
            total_capacity = venues.aggregate(total=Sum('capacity'))['total'] or 0
            
            # Get active enrollments for this campus
            # Enrollments linked via cohort.campus
            active_enrollments = Enrollment.objects.filter(
                status='ACTIVE',
                cohort__campus=campus
            ).count()
            
            campus_data.append({
                'campus': campus,
                'venue_count': venue_count,
                'total_capacity': total_capacity,
                'active_learners': active_enrollments,
                'utilization': round((active_enrollments / total_capacity * 100) if total_capacity > 0 else 0, 1),
            })
        
        # Summary stats
        summary = {
            'total_campuses': len(campus_data),
            'total_venues': sum(c['venue_count'] for c in campus_data),
            'total_capacity': sum(c['total_capacity'] for c in campus_data),
            'total_active_learners': sum(c['active_learners'] for c in campus_data),
        }
        
        return {
            'campuses': campus_data,
            'summary': summary,
        }
    
    def _get_project_summary(self):
        """Get grant project statistics"""
        from corporate.models import GrantProject
        
        projects = GrantProject.objects.all()
        selected_campus = self.get_campus_filter()
        
        if selected_campus:
            projects = projects.filter(campus=selected_campus)
        
        # Group by status
        by_status = projects.values('status').annotate(
            count=Count('id'),
            total_value=Sum('approved_amount'),
            total_learners=Sum('target_learners')
        ).order_by('status')
        
        # Recent projects
        recent_projects = projects.order_by('-created_at')[:10]
        
        # Summary
        summary = {
            'total_projects': projects.count(),
            'total_value': projects.aggregate(total=Sum('approved_amount'))['total'] or Decimal('0'),
            'total_learner_target': projects.aggregate(total=Sum('target_learners'))['total'] or 0,
            'active_projects': projects.filter(status='ACTIVE').count(),
        }
        
        return {
            'by_status': list(by_status),
            'recent_projects': recent_projects,
            'summary': summary,
        }
    
    def _get_enrollment_by_intake(self, year):
        """Get enrollments grouped by intake/cohort for the year"""
        from academics.models import Enrollment
        from logistics.models import Cohort
        
        enrollments = Enrollment.objects.filter(
            enrollment_date__year=year
        )
        
        selected_campus = self.get_campus_filter()
        if selected_campus:
            enrollments = enrollments.filter(cohort__campus=selected_campus)
        
        # Group by cohort
        by_cohort = enrollments.values(
            'cohort__id',
            'cohort__name',
            'cohort__start_date',
            'cohort__end_date',
            'qualification__short_title'
        ).annotate(
            total=Count('id'),
            active=Count('id', filter=Q(status='ACTIVE')),
            completed=Count('id', filter=Q(status='COMPLETED')),
            withdrawn=Count('id', filter=Q(status='WITHDRAWN')),
        ).order_by('-cohort__start_date')
        
        # Group by month
        by_month = enrollments.annotate(
            month=TruncMonth('enrollment_date')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        # Summary
        summary = {
            'total_enrollments': enrollments.count(),
            'active': enrollments.filter(status='ACTIVE').count(),
            'completed': enrollments.filter(status='COMPLETED').count(),
            'completion_rate': round(
                (enrollments.filter(status='COMPLETED').count() / enrollments.count() * 100)
                if enrollments.count() > 0 else 0, 1
            ),
        }
        
        return {
            'by_cohort': list(by_cohort),
            'by_month': list(by_month),
            'summary': summary,
            'year': year,
        }
    
    def _get_capacity_utilization(self):
        """Get venue capacity utilization by campus and type"""
        from logistics.models import Venue, Cohort
        from academics.models import Enrollment
        
        venues = Venue.objects.filter(is_active=True)
        selected_campus = self.get_campus_filter()
        
        if selected_campus:
            venues = venues.filter(campus=selected_campus)
        
        # Group by venue type
        by_type = venues.values('venue_type').annotate(
            count=Count('id'),
            total_capacity=Sum('capacity')
        ).order_by('venue_type')
        
        # Individual venue utilization (based on current active sessions)
        today = timezone.now().date()
        venue_utilization = []
        
        for venue in venues.select_related('campus')[:20]:  # Limit for performance
            # Count active enrollments in cohorts that have sessions at this venue
            # Go through sessions to find cohorts using this venue
            from logistics.models import ScheduleSession
            
            current_cohort_ids = ScheduleSession.objects.filter(
                venue=venue,
                date__gte=today - timedelta(days=30),  # Active in last 30 days
                date__lte=today + timedelta(days=30),  # Or upcoming 30 days
                is_cancelled=False
            ).values_list('cohort_id', flat=True).distinct()
            
            current_learners = Enrollment.objects.filter(
                cohort_id__in=current_cohort_ids,
                status='ACTIVE'
            ).count()
            
            utilization = round((current_learners / venue.capacity * 100) if venue.capacity > 0 else 0, 1)
            
            venue_utilization.append({
                'venue': venue,
                'current_learners': current_learners,
                'capacity': venue.capacity,
                'utilization': utilization,
                'status': 'high' if utilization > 80 else ('medium' if utilization > 50 else 'low'),
            })
        
        # Sort by utilization
        venue_utilization.sort(key=lambda x: x['utilization'], reverse=True)
        
        # Summary
        total_capacity = venues.aggregate(total=Sum('capacity'))['total'] or 0
        
        return {
            'by_type': list(by_type),
            'venues': venue_utilization,
            'total_capacity': total_capacity,
            'venue_types': dict(Venue.VENUE_TYPES) if hasattr(Venue, 'VENUE_TYPES') else {},
        }
    
    def _get_qualification_breakdown(self):
        """Get enrollment breakdown by qualification"""
        from academics.models import Enrollment, Qualification
        
        enrollments = Enrollment.objects.all()
        selected_campus = self.get_campus_filter()
        
        if selected_campus:
            enrollments = enrollments.filter(cohort__campus=selected_campus)
        
        by_qualification = enrollments.values(
            'qualification__id',
            'qualification__short_title',
            'qualification__nqf_level',
            'qualification__qualification_type'
        ).annotate(
            total=Count('id'),
            active=Count('id', filter=Q(status='ACTIVE')),
            completed=Count('id', filter=Q(status='COMPLETED'))
        ).order_by('-total')
        
        return list(by_qualification)
    
    def _get_cohort_overview(self):
        """Get cohort statistics"""
        from logistics.models import Cohort
        from academics.models import Enrollment
        
        today = timezone.now().date()
        cohorts = Cohort.objects.all()
        
        selected_campus = self.get_campus_filter()
        if selected_campus:
            cohorts = cohorts.filter(campus=selected_campus)
        
        # Active cohorts (currently running)
        active_cohorts = cohorts.filter(
            start_date__lte=today,
            end_date__gte=today
        ).select_related('qualification', 'campus').annotate(
            learner_count=Count('enrollments', filter=Q(enrollments__status='ACTIVE'))
        ).order_by('end_date')[:10]
        
        # Upcoming cohorts
        upcoming_cohorts = cohorts.filter(
            start_date__gt=today
        ).select_related('qualification', 'campus').annotate(
            learner_count=Count('enrollments')
        ).order_by('start_date')[:10]
        
        # Recently completed
        completed_cohorts = cohorts.filter(
            end_date__lt=today
        ).select_related('qualification', 'campus').annotate(
            learner_count=Count('enrollments'),
            completed_count=Count('enrollments', filter=Q(enrollments__status='COMPLETED'))
        ).order_by('-end_date')[:5]
        
        return {
            'active': active_cohorts,
            'upcoming': upcoming_cohorts,
            'completed': completed_cohorts,
            'total_active': active_cohorts.count() if hasattr(active_cohorts, 'count') else len(active_cohorts),
            'total_upcoming': cohorts.filter(start_date__gt=today).count(),
        }
    
    def _get_monthly_trends(self, year):
        """Get monthly enrollment trends for charts"""
        from academics.models import Enrollment
        from learners.models import Learner
        
        enrollments = Enrollment.objects.filter(enrollment_date__year=year)
        selected_campus = self.get_campus_filter()
        
        if selected_campus:
            enrollments = enrollments.filter(cohort__campus=selected_campus)
        
        # Build monthly data
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        enrollment_data = []
        completion_data = []
        
        for i in range(1, 13):
            month_enrollments = enrollments.filter(enrollment_date__month=i)
            enrollment_data.append(month_enrollments.count())
            completion_data.append(month_enrollments.filter(status='COMPLETED').count())
        
        return {
            'labels': months,
            'enrollment_data': enrollment_data,
            'completion_data': completion_data,
            'year': year,
        }
