"""
Organizational Dashboard Views
Comprehensive KPIs and analytics for managing the entire organization
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.db.models import Count, Sum, Q, Avg, F
from django.db.models.functions import TruncMonth, TruncWeek, ExtractMonth
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


class CampusFilterMixin:
    """
    Mixin to apply campus filtering from session.
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


class OrganizationalDashboardView(LoginRequiredMixin, UserPassesTestMixin, CampusFilterMixin, TemplateView):
    """
    Main Organizational Dashboard
    Shows comprehensive KPIs for management overview with view switching
    """
    template_name = 'dashboard/organizational.html'
    login_url = '/login/'
    
    def test_func(self):
        """Only allow staff or superusers"""
        user = self.request.user
        return user.is_staff or user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get view mode from query param (default to capacity)
        view_mode = self.request.GET.get('view', 'capacity')
        context['current_view'] = view_mode
        
        # Get campus filter
        selected_campus = self.get_campus_filter()
        context['campus_filter_active'] = selected_campus is not None
        context['selected_campus'] = selected_campus
        
        # Get date ranges
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        start_of_year = today.replace(month=1, day=1)
        
        # Quick stats for header
        context['quick_stats'] = self._get_quick_stats(today)
        context['today'] = today
        
        # Always include summary stats
        context['summary_stats'] = self._get_summary_stats(selected_campus)
        
        if view_mode == 'capacity':
            # CAPACITY VIEW - Classroom, Facilitator, Equipment capacity
            context['capacity'] = self._get_capacity_overview(selected_campus)
        elif view_mode == 'projects':
            # PROJECTS VIEW - All projects running, students on campus/workplace
            project_status = self.request.GET.get('project_status')
            funder = self.request.GET.get('funder')
            project_search = self.request.GET.get('project_search')
            context['projects_data'] = self._get_projects_overview(
                selected_campus,
                project_status=project_status,
                funder=funder,
                project_search=project_search
            )
        elif view_mode == 'implementation':
            # IMPLEMENTATION VIEW - Kanban for implementation plan phases
            context['implementation_data'] = self._get_implementation_overview(selected_campus)
        else:
            # DEFAULT OVERVIEW VIEW - Standard dashboard
            context.update(self._get_overview_data(selected_campus, today, start_of_month, start_of_year))
        
        return context
    
    def _get_overview_data(self, campus, today, start_of_month, start_of_year):
        """Get data for the default overview dashboard"""
        from learners.models import Learner
        from academics.models import Enrollment, Qualification
        from corporate.models import GrantProject, CorporateClient
        from logistics.models import Cohort
        from finance.models import Invoice, Payment
        from assessments.models import AssessmentResult
        
        data = {}
        
        # Base querysets
        enrollments = Enrollment.objects.all()
        if campus:
            enrollments = enrollments.filter(cohort__campus=campus)
        
        # KPIs
        total_learners = Learner.objects.count()
        new_learners_month = Learner.objects.filter(created_at__gte=start_of_month).count()
        active_learners = enrollments.filter(status='ACTIVE').values('learner').distinct().count()
        total_enrollments = enrollments.count()
        active_enrollments = enrollments.filter(status='ACTIVE').count()
        completed_enrollments = enrollments.filter(status='COMPLETED').count()
        completion_rate = round((completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0, 1)
        
        data['kpis'] = {
            'total_learners': total_learners,
            'new_learners_month': new_learners_month,
            'active_learners': active_learners,
            'total_enrollments': total_enrollments,
            'active_enrollments': active_enrollments,
            'completed_enrollments': completed_enrollments,
            'completion_rate': completion_rate,
        }
        
        # Corporate Stats
        try:
            clients = CorporateClient.objects.all()
            data['corporate_stats'] = {
                'total_clients': clients.count(),
                'active_clients': clients.filter(status='ACTIVE').count(),
                'prospects': clients.filter(status='PROSPECT').count(),
            }
        except:
            data['corporate_stats'] = {'total_clients': 0, 'active_clients': 0, 'prospects': 0}
        
        # Financial Overview
        try:
            invoices = Invoice.objects.all()
            payments = Payment.objects.all()
            
            invoiced_ytd = invoices.filter(invoice_date__year=today.year).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            payments_ytd = payments.filter(payment_date__year=today.year).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            invoiced_mtd = invoices.filter(invoice_date__gte=start_of_month).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            payments_mtd = payments.filter(payment_date__gte=start_of_month).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            outstanding = invoices.filter(status__in=['SENT', 'OVERDUE']).aggregate(total=Sum('balance_due'))['total'] or Decimal('0')
            overdue = invoices.filter(status='OVERDUE').aggregate(total=Sum('balance_due'))['total'] or Decimal('0')
            collection_rate = round((float(payments_ytd) / float(invoiced_ytd) * 100) if invoiced_ytd > 0 else 0, 1)
            
            data['financial'] = {
                'invoiced_ytd': invoiced_ytd,
                'payments_ytd': payments_ytd,
                'invoiced_mtd': invoiced_mtd,
                'payments_mtd': payments_mtd,
                'outstanding': outstanding,
                'overdue': overdue,
                'collection_rate': collection_rate,
            }
        except:
            data['financial'] = {
                'invoiced_ytd': Decimal('0'), 'payments_ytd': Decimal('0'),
                'invoiced_mtd': Decimal('0'), 'payments_mtd': Decimal('0'),
                'outstanding': Decimal('0'), 'overdue': Decimal('0'), 'collection_rate': 0
            }
        
        # Training Progress
        try:
            active = enrollments.filter(status='ACTIVE')
            progress_ranges = {
                '0-25%': active.filter(progress_percentage__lt=25).count(),
                '25-50%': active.filter(progress_percentage__gte=25, progress_percentage__lt=50).count(),
                '50-75%': active.filter(progress_percentage__gte=50, progress_percentage__lt=75).count(),
                '75-100%': active.filter(progress_percentage__gte=75).count(),
            }
            pending_assessments = AssessmentResult.objects.filter(result__isnull=True).count()
            due_this_month = active.filter(
                expected_completion__month=today.month,
                expected_completion__year=today.year
            ).count()
            
            data['training_progress'] = {
                'total_active': active.count(),
                'progress_ranges': progress_ranges,
                'pending_assessments': pending_assessments,
                'due_this_month': due_this_month,
            }
        except:
            data['training_progress'] = {
                'total_active': 0,
                'progress_ranges': {'0-25%': 0, '25-50%': 0, '50-75%': 0, '75-100%': 0},
                'pending_assessments': 0,
                'due_this_month': 0,
            }
        
        # Trends (last 6 months)
        months = []
        enrollment_trend = []
        learner_trend = []
        for i in range(5, -1, -1):
            month_date = today - timedelta(days=i*30)
            months.append(month_date.strftime('%b'))
            enrollment_trend.append(
                enrollments.filter(enrollment_date__month=month_date.month, enrollment_date__year=month_date.year).count()
            )
            learner_trend.append(
                Learner.objects.filter(created_at__month=month_date.month, created_at__year=month_date.year).count()
            )
        
        data['trends'] = {
            'months': months,
            'enrollment_trend': enrollment_trend,
            'learner_trend': learner_trend,
        }
        
        # Enrollments by Qualification
        try:
            by_qual = enrollments.values(
                'qualification__short_title', 'qualification__nqf_level'
            ).annotate(
                active=Count('id', filter=Q(status='ACTIVE')),
                completed=Count('id', filter=Q(status='COMPLETED'))
            ).order_by('-active')[:10]
            data['enrollment_stats'] = {'by_qualification': list(by_qual)}
        except:
            data['enrollment_stats'] = {'by_qualification': []}
        
        # Upcoming Events
        try:
            upcoming = []
            # Upcoming cohort starts
            upcoming_cohorts = Cohort.objects.filter(
                start_date__gte=today,
                start_date__lte=today + timedelta(days=30)
            ).order_by('start_date')[:5]
            for cohort in upcoming_cohorts:
                upcoming.append({
                    'type': 'cohort',
                    'title': f"{cohort.qualification.short_title if cohort.qualification else 'Cohort'} starts",
                    'date': cohort.start_date,
                    'color': 'blue',
                })
            data['upcoming'] = upcoming
        except:
            data['upcoming'] = []
        
        # Resources
        try:
            upcoming_cohorts = Cohort.objects.filter(
                start_date__gte=today
            ).select_related('qualification', 'campus').annotate(
                learner_count=Count('enrollments')
            ).order_by('start_date')[:5]
            
            material_forecast = []
            for cohort in upcoming_cohorts:
                material_forecast.append({
                    'cohort': cohort.name,
                    'qualification': cohort.qualification.short_title if cohort.qualification else 'N/A',
                    'learner_count': cohort.learner_count,
                    'start_date': cohort.start_date,
                })
            data['resources'] = {'material_forecast': material_forecast, 'pending_orders': 0}
        except:
            data['resources'] = {'material_forecast': [], 'pending_orders': 0}
        
        # Alerts
        data['alerts'] = []
        
        return data
    
    def _get_capacity_overview(self, campus=None):
        """Get capacity data split by type"""
        from tenants.models import Campus
        from logistics.models import Venue, Cohort
        from academics.models import Enrollment
        from core.models import User
        
        # Get venues filtered by campus
        venues = Venue.objects.filter(is_active=True)
        if campus:
            venues = venues.filter(campus=campus)
        
        # Calculate totals
        total_capacity = venues.aggregate(total=Sum('capacity'))['total'] or 0
        
        # Get active learners
        cohorts = Cohort.objects.filter(
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        )
        if campus:
            cohorts = cohorts.filter(campus=campus)
        
        active_learners = Enrollment.objects.filter(
            status='ACTIVE',
            cohort__in=cohorts
        ).count()
        
        # Calculate utilization
        utilization = round((active_learners / total_capacity * 100) if total_capacity > 0 else 0, 1)
        
        # Classroom capacity by campus
        classroom_capacity = []
        facilitator_capacity = []
        equipment_capacity = []
        
        campuses = Campus.objects.filter(is_active=True)
        if campus:
            campuses = campuses.filter(pk=campus.pk)
        
        for c in campuses:
            c_venues = Venue.objects.filter(campus=c, is_active=True)
            
            # Classrooms (CLASSROOM and LAB types)
            classrooms = c_venues.filter(venue_type__in=['CLASSROOM', 'classroom', 'LAB', 'lab'])
            c_capacity = classrooms.aggregate(total=Sum('capacity'))['total'] or 0
            c_learners = Enrollment.objects.filter(
                status='ACTIVE',
                cohort__campus=c
            ).count()
            c_utilization = round((c_learners / c_capacity * 100) if c_capacity > 0 else 0, 1)
            
            classroom_capacity.append({
                'campus_name': c.name,
                'venue_count': classrooms.count(),
                'total_capacity': c_capacity,
                'occupied': c_learners,
                'available': max(0, c_capacity - c_learners),
                'utilization': c_utilization,
            })
            
            # Facilitators - count staff users (simplified)
            facilitator_count = User.objects.filter(is_staff=True, is_active=True).count()
            # Assign proportionally based on campus count
            campus_count = Campus.objects.filter(is_active=True).count()
            campus_facilitators = max(1, facilitator_count // campus_count) if campus_count > 0 else 0
            cohort_count = Cohort.objects.filter(
                campus=c,
                start_date__lte=timezone.now().date(),
                end_date__gte=timezone.now().date()
            ).count()
            workload = round((cohort_count / campus_facilitators * 100) if campus_facilitators > 0 else 0, 1)
            workload = min(100, workload)  # Cap at 100%
            
            facilitator_capacity.append({
                'campus_name': c.name,
                'total_facilitators': campus_facilitators,
                'assigned_cohorts': cohort_count,
                'available_facilitators': max(0, campus_facilitators - cohort_count),
                'workload': workload,
            })
            
            # Equipment (WORKSHOP type venues)
            workshops = c_venues.filter(venue_type__in=['WORKSHOP', 'workshop'])
            w_capacity = workshops.aggregate(total=Sum('capacity'))['total'] or 0
            # Simplified equipment utilization
            w_utilization = round((c_learners / (w_capacity or 1) * 100) if w_capacity > 0 else 0, 1)
            w_utilization = min(100, w_utilization)
            
            equipment_capacity.append({
                'campus_name': c.name,
                'total_equipment': workshops.count() * 10,  # Estimated equipment per workshop
                'in_use': round(workshops.count() * 10 * (w_utilization / 100)),
                'available': round(workshops.count() * 10 * (1 - w_utilization / 100)),
                'utilization': w_utilization,
            })
        
        return {
            'total_seats': total_capacity,
            'occupied_seats': active_learners,
            'available_seats': max(0, total_capacity - active_learners),
            'utilization': utilization,
            'classroom_capacity': classroom_capacity,
            'facilitator_capacity': facilitator_capacity,
            'equipment_capacity': equipment_capacity,
        }
    
    def _get_projects_overview(self, campus=None, project_status=None, funder=None, project_search=None):
        """Get projects running, students on campus vs workplace"""
        from corporate.models import GrantProject, CorporateClient
        from academics.models import Enrollment
        from logistics.models import Cohort
        from assessments.models import AssessmentResult
        
        # Get grant projects
        projects = GrantProject.objects.filter(status='ACTIVE')
        if campus:
            projects = projects.filter(campus=campus)
        
        # Get enrollments
        enrollments = Enrollment.objects.filter(status='ACTIVE')
        if campus:
            enrollments = enrollments.filter(cohort__campus=campus)
        
        total_students = enrollments.count()
        
        # Students by location (on campus vs workplace)
        # Try to determine by cohort training mode
        try:
            on_campus = enrollments.filter(
                cohort__training_mode__in=['CLASSROOM', 'classroom', 'BLENDED', 'blended', 'LAB', 'lab']
            ).count()
            workplace = enrollments.filter(
                cohort__training_mode__in=['WORKPLACE', 'workplace', 'LEARNERSHIPS', 'learnerships', 'WIL', 'wil']
            ).count()
            
            # If no training_mode matches, assume 70% campus, 30% workplace
            if on_campus == 0 and workplace == 0:
                on_campus = int(total_students * 0.7)
                workplace = total_students - on_campus
        except:
            on_campus = int(total_students * 0.7)
            workplace = total_students - on_campus
        
        # Progress distribution - calculate based on study year
        # Determine which year of study each active student is in based on their enrollment start date
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        today = date.today()
        
        # Get active enrollments with start dates
        active_enrollments = enrollments.filter(start_date__isnull=False)
        
        year_1_count = 0
        year_2_count = 0
        year_3_plus_count = 0
        
        for enrollment in active_enrollments:
            if enrollment.start_date:
                # Calculate years since enrollment started
                years_enrolled = relativedelta(today, enrollment.start_date).years
                if years_enrolled < 1:
                    year_1_count += 1
                elif years_enrolled < 2:
                    year_2_count += 1
                else:
                    year_3_plus_count += 1
        
        by_progress = {
            'Year 1': year_1_count,
            'Year 2': year_2_count,
            'Year 3+': year_3_plus_count,
        }
        
        # Competency rates
        try:
            results = AssessmentResult.objects.all()
            if campus:
                results = results.filter(enrollment__cohort__campus=campus)
            
            competent = results.filter(result__in=['COMPETENT', 'C', 'PASS', 'competent', 'pass']).count()
            not_competent = results.filter(result__in=['NYC', 'NOT_YET_COMPETENT', 'FAIL', 'nyc', 'fail']).count()
            in_progress = results.filter(result__isnull=True).count()
            total_results = competent + not_competent
            avg_rate = round((competent / total_results * 100) if total_results > 0 else 0, 1)
            
            # Not assessed = total students minus those with results
            assessed_enrollments = results.values('enrollment').distinct().count()
            not_assessed = max(0, total_students - assessed_enrollments)
        except:
            competent = 0
            not_competent = 0
            in_progress = 0
            avg_rate = 0
            not_assessed = total_students
        
        competency_rates = {
            'competent': competent,
            'not_competent': not_competent,
            'in_progress': in_progress,
            'not_assessed': not_assessed,
            'average': avg_rate,
        }
        
        # Build projects list with details
        # Use TrainingNotification as projects since Cohort doesn't have grant_project
        from core.models import TrainingNotification
        
        # Get all funders for filter dropdown
        funders_list = list(CorporateClient.objects.filter(
            training_notifications__isnull=False
        ).distinct().values('id', 'company_name').order_by('company_name'))
        # Rename company_name to name for template compatibility
        funders_list = [{'id': f['id'], 'name': f['company_name']} for f in funders_list]
        
        # Active projects include draft, planning, in progress, approved, or with notifications sent
        # Map filter values to statuses
        if project_status == 'ACTIVE':
            active_statuses = ['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL', 'IN_PROGRESS', 'APPROVED', 'NOTIFICATIONS_SENT']
        elif project_status == 'PLANNING':
            active_statuses = ['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL']
        elif project_status == 'IN_PROGRESS':
            active_statuses = ['IN_PROGRESS', 'APPROVED', 'NOTIFICATIONS_SENT']
        elif project_status == 'COMPLETED':
            active_statuses = ['COMPLETED', 'SIGNED_OFF']
        else:
            # Default - show all active statuses
            active_statuses = ['DRAFT', 'PLANNING', 'IN_MEETING', 'PENDING_APPROVAL', 'IN_PROGRESS', 'APPROVED', 'NOTIFICATIONS_SENT']
        
        nots = TrainingNotification.objects.filter(status__in=active_statuses)
        if campus:
            nots = nots.filter(delivery_campus=campus)
        if funder:
            nots = nots.filter(corporate_client_id=funder)
        if project_search:
            nots = nots.filter(
                Q(title__icontains=project_search) |
                Q(reference_number__icontains=project_search) |
                Q(corporate_client__name__icontains=project_search)
            )
        
        project_list = []
        for not_project in nots.select_related('corporate_client', 'delivery_campus').prefetch_related('intakes__cohort'):
            # Get cohorts linked to this NOT through intakes
            project_cohorts = [intake.cohort for intake in not_project.intakes.all() if intake.cohort]
            if not project_cohorts:
                # No cohorts linked, still show the project with zero learners
                project_list.append({
                    'name': not_project.title or not_project.reference_number,
                    'funder': not_project.corporate_client.name if not_project.corporate_client else 'N/A',
                    'total_learners': 0,
                    'on_campus': 0,
                    'in_workplace': 0,
                    'avg_progress': 0,
                    'competency_rate': 0,
                })
                continue
            
            project_enrollments = Enrollment.objects.filter(
                status='ACTIVE',
                cohort__in=project_cohorts
            )
            p_total = project_enrollments.count()
            p_on_campus = int(p_total * 0.7)  # Simplified
            p_workplace = p_total - p_on_campus
            
            # Calculate progress from enrollment status (no progress_percentage field)
            p_completed = Enrollment.objects.filter(
                status='COMPLETED',
                cohort__in=project_cohorts
            ).count()
            p_total_all = Enrollment.objects.filter(cohort__in=project_cohorts).count()
            p_avg_progress = round((p_completed / p_total_all * 100) if p_total_all > 0 else 0, 1)
            
            # Project competency
            p_results = AssessmentResult.objects.filter(enrollment__cohort__in=project_cohorts)
            p_competent = p_results.filter(result__in=['COMPETENT', 'C', 'PASS', 'competent', 'pass']).count()
            p_total_results = p_results.count()
            p_competency = round((p_competent / p_total_results * 100) if p_total_results > 0 else 0, 1)
            
            project_list.append({
                'name': not_project.title or not_project.reference_number,
                'funder': not_project.corporate_client.name if not_project.corporate_client else 'N/A',
                'total_learners': p_total,
                'on_campus': p_on_campus,
                'in_workplace': p_workplace,
                'avg_progress': p_avg_progress,
                'competency_rate': p_competency,
            })
        
        return {
            'projects': project_list,
            'students_on_campus': on_campus,
            'students_in_workplace': workplace,
            'total_students': total_students,
            'by_progress': by_progress,
            'competency_rates': competency_rates,
            'filters': {
                'funders': funders_list,
            },
        }
    
    def _get_implementation_overview(self, campus=None):
        """
        Get implementation plan phases for Kanban view.
        Groups phases by status with filter options for campus, qualification, project, year.
        """
        from logistics.models import CohortImplementationPhase, CohortImplementationPlan, Cohort, PHASE_TYPE_COLORS
        from academics.models import Qualification, ImplementationPlan
        from core.models import TrainingNotification, NOTIntake
        
        # Get filter parameters
        qualification_id = self.request.GET.get('qualification')
        project_id = self.request.GET.get('project')
        year = self.request.GET.get('year')
        
        # Base queryset for phases
        phases = CohortImplementationPhase.objects.select_related(
            'cohort_implementation_plan__cohort__qualification',
            'cohort_implementation_plan__cohort__campus',
        ).prefetch_related('module_slots')
        
        # Apply filters
        if campus:
            phases = phases.filter(cohort_implementation_plan__cohort__campus=campus)
        
        if qualification_id:
            phases = phases.filter(cohort_implementation_plan__cohort__qualification_id=qualification_id)
        
        if project_id:
            # Filter by NOT project through NOTIntake
            phases = phases.filter(
                cohort_implementation_plan__cohort__not_intakes__training_notification_id=project_id
            )
        
        if year:
            phases = phases.filter(year_level=int(year))
        
        # Group phases by status for Kanban columns
        kanban_columns = [
            {'status': 'PENDING', 'label': 'Pending', 'color': 'slate', 'phases': []},
            {'status': 'IN_PROGRESS', 'label': 'In Progress', 'color': 'blue', 'phases': []},
            {'status': 'COMPLETED', 'label': 'Completed', 'color': 'green', 'phases': []},
        ]
        
        status_to_column = {col['status']: col for col in kanban_columns}
        
        for phase in phases.order_by('cohort_implementation_plan__cohort__code', 'sequence'):
            cohort = phase.cohort_implementation_plan.cohort
            
            # Get associated project (NOT) via NOTIntake
            not_intake = cohort.not_intakes.select_related('training_notification').first()
            project_name = None
            project_ref = None
            if not_intake:
                project_name = not_intake.training_notification.title
                project_ref = not_intake.training_notification.reference_number
            
            phase_data = {
                'id': phase.id,
                'name': phase.name,
                'phase_type': phase.phase_type,
                'phase_type_display': phase.get_phase_type_display(),
                'color': phase.color,
                'status': phase.status,
                'cohort_code': cohort.code,
                'cohort_name': cohort.name,
                'qualification': cohort.qualification.short_title if cohort.qualification else 'N/A',
                'project_name': project_name or project_ref or 'No Project',
                'project_ref': project_ref,
                'planned_start': phase.planned_start,
                'planned_end': phase.planned_end,
                'actual_start': phase.actual_start,
                'actual_end': phase.actual_end,
                'duration_weeks': phase.duration_weeks,
                'progress': phase.get_module_progress(),
                'days_variance': phase.days_variance,
                'days_until_end': phase.days_until_planned_end,
                'is_at_risk': phase.is_at_risk,
                'is_overdue': phase.is_overdue,
                'module_count': phase.module_slots.count(),
            }
            
            # Add to appropriate column (DELAYED goes to IN_PROGRESS for visibility)
            column_status = phase.status if phase.status in status_to_column else 'IN_PROGRESS'
            if column_status in status_to_column:
                status_to_column[column_status]['phases'].append(phase_data)
        
        # Update counts
        for col in kanban_columns:
            col['count'] = len(col['phases'])
        
        # Get cohorts without implementation plans (for empty state)
        cohorts_without_plans = Cohort.objects.filter(
            implementation_plan__isnull=True,
            status__in=['ACTIVE', 'OPEN', 'PLANNED']
        ).select_related('qualification', 'campus')
        
        if campus:
            cohorts_without_plans = cohorts_without_plans.filter(campus=campus)
        
        missing_plans = []
        for cohort in cohorts_without_plans[:10]:
            # Check if qualification has an active template
            has_template = ImplementationPlan.objects.filter(
                qualification=cohort.qualification,
                is_default=True,
                status='ACTIVE'
            ).exists()
            
            not_intake = cohort.not_intakes.select_related('training_notification').first()
            project_name = None
            if not_intake:
                project_name = not_intake.training_notification.title or not_intake.training_notification.reference_number
            
            missing_plans.append({
                'cohort_code': cohort.code,
                'cohort_name': cohort.name,
                'qualification': cohort.qualification.short_title if cohort.qualification else 'N/A',
                'qualification_id': cohort.qualification_id,
                'project_name': project_name or 'No Project',
                'has_template': has_template,
            })
        
        # Build filter options
        # Qualifications with active cohorts
        qualifications = Qualification.objects.filter(
            cohorts__status__in=['ACTIVE', 'OPEN', 'PLANNED']
        ).distinct().values('id', 'short_title').order_by('short_title')
        
        # Projects (NOTs) with active status
        projects = TrainingNotification.objects.filter(
            status__in=['ACTIVE', 'IN_PROGRESS']
        ).values('id', 'reference_number', 'title').order_by('-created_at')[:50]
        
        # Years (1, 2, 3)
        years = [1, 2, 3]
        
        # Build Gantt data - group phases by cohort
        gantt_data = []
        cohort_plans = CohortImplementationPlan.objects.select_related(
            'cohort__qualification',
            'cohort__campus',
        ).prefetch_related(
            'phases__module_slots',
            'cohort__not_intakes__training_notification'
        )
        
        if campus:
            cohort_plans = cohort_plans.filter(cohort__campus=campus)
        
        if qualification_id:
            cohort_plans = cohort_plans.filter(cohort__qualification_id=qualification_id)
        
        if project_id:
            cohort_plans = cohort_plans.filter(
                cohort__not_intakes__training_notification_id=project_id
            )
        
        # Calculate timeline boundaries (for positioning)
        from datetime import date, timedelta
        all_phases_dates = CohortImplementationPhase.objects.filter(
            cohort_implementation_plan__in=cohort_plans
        ).exclude(planned_start__isnull=True, planned_end__isnull=True)
        
        if all_phases_dates.exists():
            timeline_start = all_phases_dates.order_by('planned_start').first().planned_start
            timeline_end = all_phases_dates.order_by('-planned_end').first().planned_end
            
            # Pad by 2 weeks on each side
            if timeline_start:
                timeline_start = timeline_start - timedelta(weeks=2)
            else:
                timeline_start = date.today() - timedelta(weeks=4)
            
            if timeline_end:
                timeline_end = timeline_end + timedelta(weeks=2)
            else:
                timeline_end = date.today() + timedelta(weeks=52)
        else:
            timeline_start = date.today() - timedelta(weeks=4)
            timeline_end = date.today() + timedelta(weeks=52)
        
        total_days = (timeline_end - timeline_start).days or 1
        
        # Generate month markers for timeline header
        month_markers = []
        current = timeline_start.replace(day=1)
        while current <= timeline_end:
            marker_offset = ((current - timeline_start).days / total_days) * 100
            month_markers.append({
                'month': current.strftime('%b'),
                'year': current.year,
                'offset': marker_offset,
            })
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        for plan in cohort_plans.order_by('cohort__code'):
            cohort = plan.cohort
            not_intake = cohort.not_intakes.select_related('training_notification').first()
            project_name = None
            if not_intake:
                project_name = not_intake.training_notification.title or not_intake.training_notification.reference_number
            
            cohort_phases = []
            for phase in plan.phases.order_by('sequence'):
                # Calculate position percentages for Gantt bar
                if phase.planned_start and phase.planned_end:
                    start_offset = ((phase.planned_start - timeline_start).days / total_days) * 100
                    end_offset = ((phase.planned_end - timeline_start).days / total_days) * 100
                    bar_width = end_offset - start_offset
                else:
                    start_offset = 0
                    bar_width = 0
                
                cohort_phases.append({
                    'id': phase.id,
                    'name': phase.name,
                    'phase_type': phase.phase_type,
                    'phase_type_display': phase.get_phase_type_display(),
                    'color': phase.color,
                    'status': phase.status,
                    'planned_start': phase.planned_start,
                    'planned_end': phase.planned_end,
                    'actual_start': phase.actual_start,
                    'actual_end': phase.actual_end,
                    'duration_weeks': phase.duration_weeks,
                    'progress': phase.get_module_progress(),
                    'days_variance': phase.days_variance,
                    'is_at_risk': phase.is_at_risk,
                    'is_overdue': phase.is_overdue,
                    'module_count': phase.module_slots.count(),
                    'start_offset': round(start_offset, 2),
                    'bar_width': round(max(bar_width, 0.5), 2),  # Min width for visibility
                })
            
            gantt_data.append({
                'cohort_id': cohort.id,
                'cohort_code': cohort.code,
                'cohort_name': cohort.name,
                'qualification': cohort.qualification.short_title if cohort.qualification else 'N/A',
                'campus': cohort.campus.name if cohort.campus else 'N/A',
                'project_name': project_name or 'No Project',
                'phases': cohort_phases,
                'total_phases': len(cohort_phases),
                'completed_phases': sum(1 for p in cohort_phases if p['status'] == 'COMPLETED'),
                'in_progress_phases': sum(1 for p in cohort_phases if p['status'] == 'IN_PROGRESS'),
            })
        
        return {
            'kanban_columns': kanban_columns,
            'gantt_data': gantt_data,
            'gantt_timeline': {
                'start': timeline_start,
                'end': timeline_end,
                'total_days': total_days,
                'month_markers': month_markers,
                'today_offset': round(((date.today() - timeline_start).days / total_days) * 100, 2),
            },
            'missing_plans': missing_plans,
            'missing_plans_count': cohorts_without_plans.count(),
            'phase_type_colors': PHASE_TYPE_COLORS,
            'filters': {
                'qualifications': list(qualifications),
                'projects': list(projects),
                'years': years,
                'selected_qualification': qualification_id,
                'selected_project': project_id,
                'selected_year': year,
            }
        }
    
    def _get_progress_overview(self, campus=None):
        """Get student progress and competency rates"""
        from academics.models import Enrollment
        from assessments.models import AssessmentResult
        from logistics.models import Cohort
        
        # Get enrollments
        enrollments = Enrollment.objects.all()
        if campus:
            enrollments = enrollments.filter(cohort__campus=campus)
        
        active_enrollments = enrollments.filter(status='ACTIVE')
        total_active = active_enrollments.count()
        
        # Progress distribution
        progress_ranges = {
            '0-25%': active_enrollments.filter(progress_percentage__lt=25).count(),
            '25-50%': active_enrollments.filter(progress_percentage__gte=25, progress_percentage__lt=50).count(),
            '50-75%': active_enrollments.filter(progress_percentage__gte=50, progress_percentage__lt=75).count(),
            '75-100%': active_enrollments.filter(progress_percentage__gte=75).count(),
        }
        
        # Average progress
        avg_progress = active_enrollments.aggregate(avg=Avg('progress_percentage'))['avg'] or 0
        
        # Progress by qualification
        by_qualification = active_enrollments.values(
            'qualification__short_title',
            'qualification__id'
        ).annotate(
            count=Count('id'),
            avg_progress=Avg('progress_percentage')
        ).order_by('-count')[:10]
        
        # Competency rates from assessment results
        try:
            # Get competent vs not yet competent
            results = AssessmentResult.objects.all()
            if campus:
                results = results.filter(enrollment__cohort__campus=campus)
            
            competent = results.filter(result__in=['COMPETENT', 'C', 'PASS']).count()
            not_yet_competent = results.filter(result__in=['NYC', 'NOT_YET_COMPETENT', 'FAIL']).count()
            total_results = competent + not_yet_competent
            
            competency_rate = round((competent / total_results * 100) if total_results > 0 else 0, 1)
        except:
            competent = 0
            not_yet_competent = 0
            competency_rate = 0
        
        # Students near completion (>75% progress)
        near_completion = active_enrollments.filter(progress_percentage__gte=75).count()
        
        # At risk (low progress, been enrolled long)
        at_risk = active_enrollments.filter(
            progress_percentage__lt=25,
            enrollment_date__lt=timezone.now().date() - timedelta(days=90)
        ).count()
        
        # Completion stats
        completed = enrollments.filter(status='COMPLETED').count()
        withdrawn = enrollments.filter(status='WITHDRAWN').count()
        total_all = enrollments.count()
        completion_rate = round((completed / total_all * 100) if total_all > 0 else 0, 1)
        
        # Due this month
        due_this_month = active_enrollments.filter(
            expected_completion__month=timezone.now().month,
            expected_completion__year=timezone.now().year
        ).count()
        
        return {
            'total_active': total_active,
            'progress_ranges': progress_ranges,
            'avg_progress': round(avg_progress, 1),
            'by_qualification': list(by_qualification),
            'competency_rate': competency_rate,
            'competent_count': competent,
            'nyc_count': not_yet_competent,
            'near_completion': near_completion,
            'at_risk': at_risk,
            'completed': completed,
            'withdrawn': withdrawn,
            'completion_rate': completion_rate,
            'due_this_month': due_this_month,
        }
    
    def _get_summary_stats(self, campus=None):
        """Get summary statistics shown on all views"""
        from learners.models import Learner
        from academics.models import Enrollment
        from corporate.models import GrantProject
        from logistics.models import Cohort
        
        enrollments = Enrollment.objects.all()
        if campus:
            enrollments = enrollments.filter(cohort__campus=campus)
        
        projects = GrantProject.objects.all()
        if campus:
            projects = projects.filter(campus=campus)
        
        cohorts = Cohort.objects.filter(
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        )
        if campus:
            cohorts = cohorts.filter(campus=campus)
        
        return {
            'total_learners': Learner.objects.count(),
            'active_enrollments': enrollments.filter(status='ACTIVE').count(),
            'active_projects': projects.filter(status='ACTIVE').count(),
            'active_cohorts': cohorts.count(),
        }
    
    def _get_quick_stats(self, today):
        """Quick stats for header"""
        from learners.models import Learner
        from logistics.models import Cohort
        
        try:
            active_cohorts = Cohort.objects.filter(
                start_date__lte=today,
                end_date__gte=today
            ).count()
        except:
            active_cohorts = 0
        
        return {
            'active_cohorts': active_cohorts,
            'today': today,
        }


class ResourcePlanningView(LoginRequiredMixin, UserPassesTestMixin, CampusFilterMixin, TemplateView):
    """
    Detailed Resource Planning View
    For forecasting learning materials and facilitator allocation
    """
    template_name = 'dashboard/resource_planning.html'
    login_url = '/login/'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from logistics.models import Cohort
        from academics.models import Qualification, Module
        
        today = timezone.now().date()
        
        try:
            # Get upcoming cohorts with learner counts
            upcoming_cohorts = Cohort.objects.filter(
                start_date__gte=today
            ).select_related('qualification').annotate(
                learner_count=Count('enrollments')
            ).order_by('start_date')
            
            context['upcoming_cohorts'] = upcoming_cohorts
        except:
            context['upcoming_cohorts'] = []
        
        try:
            # Material requirements by module
            modules_with_materials = Module.objects.all().select_related('qualification')
            context['modules'] = modules_with_materials
        except:
            context['modules'] = []
        
        # Forecasting periods
        context['forecast_periods'] = [
            {'label': 'Next Month', 'start': today, 'end': today + timedelta(days=30)},
            {'label': 'Next Quarter', 'start': today, 'end': today + timedelta(days=90)},
            {'label': 'Next 6 Months', 'start': today, 'end': today + timedelta(days=180)},
        ]
        
        return context


class TrainingProgressView(LoginRequiredMixin, UserPassesTestMixin, CampusFilterMixin, TemplateView):
    """
    Detailed Training Progress View
    Shows learner progress across all qualifications
    """
    template_name = 'dashboard/training_progress.html'
    login_url = '/login/'
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from academics.models import Enrollment
        
        try:
            # Get all active enrollments with progress
            enrollments = Enrollment.objects.filter(
                status='ACTIVE'
            ).select_related(
                'learner', 'qualification', 'cohort'
            ).order_by('-progress_percentage')
            
            context['enrollments'] = enrollments
        except:
            context['enrollments'] = []
        
        try:
            # Progress by qualification
            by_qualification = Enrollment.objects.filter(
                status='ACTIVE'
            ).values(
                'qualification__short_title'
            ).annotate(
                count=Count('id'),
                avg_progress=Avg('progress_percentage')
            ).order_by('qualification__short_title')
            
            context['by_qualification'] = list(by_qualification)
        except:
            context['by_qualification'] = []
        
        return context


# =====================================================
# IMPLEMENTATION PHASE AJAX ENDPOINTS
# =====================================================

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
import json


@login_required
@require_POST
@csrf_protect
def implementation_phase_update(request):
    """
    AJAX endpoint to update implementation phase status.
    Used by Kanban drag-drop and slide-over panel.
    """
    try:
        data = json.loads(request.body)
        phase_id = data.get('phase_id')
        new_status = data.get('status')
        
        if not phase_id or not new_status:
            return JsonResponse({'success': False, 'error': 'Missing phase_id or status'}, status=400)
        
        from logistics.models import CohortImplementationPhase
        
        phase = CohortImplementationPhase.objects.get(pk=phase_id)
        
        # Validate status
        valid_statuses = [choice[0] for choice in CohortImplementationPhase.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
        
        # Update status
        old_status = phase.status
        phase.status = new_status
        phase.save()
        
        # Log the change
        phase.cohort_implementation_plan.log_modification(
            request.user,
            f"Phase '{phase.name}' status changed: {old_status} → {new_status}",
            "Manual status update from dashboard"
        )
        
        return JsonResponse({
            'success': True,
            'phase_id': phase_id,
            'new_status': new_status,
            'old_status': old_status
        })
        
    except CohortImplementationPhase.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Phase not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def implementation_phase_detail(request, pk):
    """
    AJAX endpoint to get implementation phase details for slide-over panel.
    """
    try:
        from logistics.models import CohortImplementationPhase
        
        phase = CohortImplementationPhase.objects.select_related(
            'cohort_implementation_plan__cohort__qualification',
            'cohort_implementation_plan__cohort__campus',
        ).prefetch_related('module_slots__module').get(pk=pk)
        
        cohort = phase.cohort_implementation_plan.cohort
        
        # Get associated project (NOT) via NOTIntake
        not_intake = cohort.not_intakes.select_related('training_notification').first()
        project_name = None
        project_ref = None
        if not_intake:
            project_name = not_intake.training_notification.title
            project_ref = not_intake.training_notification.reference_number
        
        # Build module slots data
        module_slots = []
        for slot in phase.module_slots.order_by('sequence'):
            module_slots.append({
                'id': slot.id,
                'module_code': slot.module.code,
                'module_title': slot.module.title,
                'status': slot.status,
                'status_display': slot.get_status_display(),
                'total_days': slot.total_days,
                'actual_days_used': slot.actual_days_used,
            })
        
        data = {
            'id': phase.id,
            'name': phase.name,
            'phase_type': phase.phase_type,
            'phase_type_display': phase.get_phase_type_display(),
            'color': phase.color,
            'status': phase.status,
            'status_display': phase.get_status_display(),
            'cohort_code': cohort.code,
            'cohort_name': cohort.name,
            'qualification': cohort.qualification.short_title if cohort.qualification else 'N/A',
            'project_name': project_name or project_ref or 'No Project',
            'project_ref': project_ref,
            'planned_start': phase.planned_start.isoformat() if phase.planned_start else None,
            'planned_end': phase.planned_end.isoformat() if phase.planned_end else None,
            'actual_start': phase.actual_start.isoformat() if phase.actual_start else None,
            'actual_end': phase.actual_end.isoformat() if phase.actual_end else None,
            'duration_weeks': phase.duration_weeks,
            'year_level': phase.year_level,
            'description': phase.description,
            'progress': phase.get_module_progress(),
            'days_variance': phase.days_variance,
            'days_until_end': phase.days_until_planned_end,
            'is_at_risk': phase.is_at_risk,
            'is_overdue': phase.is_overdue,
            'module_slots': module_slots,
            'adjustment_reason': phase.adjustment_reason,
        }
        
        return JsonResponse({'success': True, 'phase': data})
        
    except CohortImplementationPhase.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Phase not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
# Utilization API Views
# =============================================================================

from django.views import View
from django.http import JsonResponse
from datetime import datetime


class CampusUtilizationAPIView(LoginRequiredMixin, View):
    """
    API endpoint for campus utilization metrics.
    Returns JSON with venue, facilitator, and resource utilization data.
    """
    
    def get(self, request, campus_id=None):
        from core.services.utilization import (
            calculate_campus_utilization,
            get_all_campuses_utilization,
            get_resource_availability_summary
        )
        
        # Parse date range from query params
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        try:
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD.'
            }, status=400)
        
        if campus_id:
            # Get utilization for specific campus
            data = calculate_campus_utilization(campus_id, start_date, end_date)
            
            # Include availability summary
            availability = get_resource_availability_summary(campus_id, start_date, end_date)
            if 'error' not in availability:
                data['availability'] = availability
        else:
            # Get utilization for all campuses
            data = {
                'campuses': get_all_campuses_utilization(start_date, end_date)
            }
        
        return JsonResponse({
            'success': True,
            'data': data
        })


class FacilitatorUtilizationAPIView(LoginRequiredMixin, View):
    """
    API endpoint for facilitator utilization metrics.
    """
    
    def get(self, request, user_id):
        from core.services.utilization import calculate_facilitator_utilization
        
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        try:
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD.'
            }, status=400)
        
        data = calculate_facilitator_utilization(user_id, start_date, end_date)
        
        if 'error' in data:
            return JsonResponse({
                'success': False,
                'error': data['error']
            }, status=404)
        
        return JsonResponse({
            'success': True,
            'data': data
        })


class VenueUtilizationAPIView(LoginRequiredMixin, View):
    """
    API endpoint for venue utilization metrics.
    """
    
    def get(self, request, venue_id):
        from core.services.utilization import calculate_venue_utilization
        
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        try:
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD.'
            }, status=400)
        
        data = calculate_venue_utilization(venue_id, start_date, end_date)
        
        if 'error' in data:
            return JsonResponse({
                'success': False,
                'error': data['error']
            }, status=404)
        
        return JsonResponse({
            'success': True,
            'data': data
        })
