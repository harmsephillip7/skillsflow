"""
Facilitator Portal Views - Class Management & Assessment

Easy views for facilitators to:
- See their assigned cohorts/classes
- View learner progress and performance
- Manage assessments (mark/grade)
- Moderate results
- View schedules (today, tomorrow, week, 3-year outlook)
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView, ListView
from django.views.decorators.http import require_POST
from django.db.models import Count, Q, Avg, Sum, Case, When, Value, IntegerField, F
from django.utils import timezone
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseForbidden
from django.urls import reverse
from django.contrib import messages
from datetime import date, timedelta
import json

from core.models import User, FacilitatorProfile
from learners.models import Learner
from academics.models import Enrollment, Module, Qualification, PersonnelRegistration
from assessments.models import AssessmentActivity, AssessmentResult, ModerationRecord
from logistics.models import Cohort, ScheduleSession, Attendance


def get_facilitator_context(user):
    """
    Get facilitator profile with campus validation.
    Returns facilitator profile or None if user is not a facilitator or has no campuses assigned.
    """
    try:
        facilitator = FacilitatorProfile.objects.select_related('primary_campus').prefetch_related('campuses').get(user=user)
        return facilitator
    except FacilitatorProfile.DoesNotExist:
        return None


def get_user_personnel_roles(user):
    """
    Get the user's personnel registrations (facilitator, assessor, moderator).
    Returns dict with is_assessor, is_moderator flags and related qualifications.
    """
    from django.utils import timezone
    today = timezone.now().date()
    
    registrations = PersonnelRegistration.objects.filter(
        user=user,
        is_active=True,
        expiry_date__gte=today
    ).prefetch_related('qualifications')
    
    roles = {
        'is_facilitator': False,
        'is_assessor': False,
        'is_moderator': False,
        'facilitator_qualifications': [],
        'assessor_qualifications': [],
        'moderator_qualifications': [],
    }
    
    for reg in registrations:
        quals = list(reg.qualifications.values_list('short_title', flat=True))
        
        if reg.personnel_type == 'FACILITATOR':
            roles['is_facilitator'] = True
            roles['facilitator_qualifications'].extend(quals)
        elif reg.personnel_type == 'ASSESSOR':
            roles['is_assessor'] = True
            roles['assessor_qualifications'].extend(quals)
        elif reg.personnel_type == 'MODERATOR':
            roles['is_moderator'] = True
            roles['moderator_qualifications'].extend(quals)
    
    # Deduplicate qualifications
    roles['facilitator_qualifications'] = list(set(roles['facilitator_qualifications']))
    roles['assessor_qualifications'] = list(set(roles['assessor_qualifications']))
    roles['moderator_qualifications'] = list(set(roles['moderator_qualifications']))
    
    return roles


class FacilitatorDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main facilitator dashboard - overview of classes, pending work, and today's schedule
    """
    template_name = 'portals/facilitator/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get facilitator profile and validate campus assignments
        facilitator = get_facilitator_context(user)
        if not facilitator:
            # No facilitator profile found
            return {'error': 'no_profile', 'message': 'Facilitator profile not found. Please contact your administrator.'}
        
        if not facilitator.campuses.exists():
            # No campuses assigned
            return {'error': 'no_campuses', 'message': 'You do not have any campuses assigned. Please contact your administrator to assign campuses before using this portal.'}
        
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # Get assigned campuses
        assigned_campuses = facilitator.campuses.all()
        context['facilitator'] = facilitator
        context['assigned_campuses'] = assigned_campuses
        context['primary_campus'] = facilitator.primary_campus
        
        # Get selected campus from session or use primary campus
        selected_campus_id = self.request.GET.get('campus') or self.request.session.get('facilitator_selected_campus')
        if selected_campus_id:
            try:
                selected_campus = assigned_campuses.get(id=selected_campus_id)
                self.request.session['facilitator_selected_campus'] = selected_campus_id
            except:
                selected_campus = facilitator.primary_campus
        else:
            selected_campus = facilitator.primary_campus
        
        context['selected_campus'] = selected_campus
        
        # Filter cohorts by selected campus (or all campuses if "All" is selected)
        cohort_filter = Q(facilitator=user, status__in=['ACTIVE', 'OPEN'])
        if selected_campus:
            cohort_filter &= Q(campus=selected_campus)
        else:
            cohort_filter &= Q(campus__in=assigned_campuses)
        
        # Get cohorts where user is facilitator
        cohorts = Cohort.objects.filter(cohort_filter).select_related('qualification', 'campus')
        
        context['cohorts'] = cohorts
        
        # Total learners across all cohorts
        total_learners = Enrollment.objects.filter(
            cohort__in=cohorts,
            status__in=['ACTIVE', 'ENROLLED']
        ).count()
        context['total_learners'] = total_learners
        
        # Pending assessments to mark
        pending_to_mark = AssessmentResult.objects.filter(
            assessor=user,
            status='DRAFT'
        ).count()
        
        # Results pending moderation from facilitator's cohorts
        cohort_enrollments = Enrollment.objects.filter(cohort__in=cohorts)
        
        pending_moderation = AssessmentResult.objects.filter(
            enrollment__in=cohort_enrollments,
            status='PENDING_MOD'
        ).count()
        
        context['pending_to_mark'] = pending_to_mark
        context['pending_moderation'] = pending_moderation
        
        # Today's and Tomorrow's Sessions
        today_sessions = ScheduleSession.objects.filter(
            facilitator=user,
            date=today,
            is_cancelled=False
        ).select_related('module', 'venue', 'cohort').order_by('start_time')
        
        tomorrow_sessions = ScheduleSession.objects.filter(
            facilitator=user,
            date=tomorrow,
            is_cancelled=False
        ).select_related('module', 'venue', 'cohort').order_by('start_time')
        
        context['today_sessions'] = today_sessions
        context['tomorrow_sessions'] = tomorrow_sessions
        context['today'] = today
        context['tomorrow'] = tomorrow
        
        # Recently graded
        recent_grades = AssessmentResult.objects.filter(
            assessor=user
        ).select_related(
            'enrollment__learner', 'activity'
        ).order_by('-updated_at')[:10]
        context['recent_grades'] = recent_grades
        
        # Cohort summary with stats
        cohort_data = []
        for cohort in cohorts:
            enrollments = Enrollment.objects.filter(
                cohort=cohort,
                status__in=['ACTIVE', 'ENROLLED']
            )
            member_count = enrollments.count()
            
            # Calculate average progress
            total_progress = 0
            for enrollment in enrollments:
                modules = Module.objects.filter(qualification=enrollment.qualification)
                activities = AssessmentActivity.objects.filter(module__in=modules, is_active=True)
                completed = AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    result='C',
                    status='FINALIZED'
                ).values('activity').distinct().count()
                if activities.count() > 0:
                    total_progress += (completed / activities.count() * 100)
            
            avg_progress = total_progress / enrollments.count() if enrollments.count() > 0 else 0
            
            # At-risk learners (those with multiple NYC results)
            at_risk = AssessmentResult.objects.filter(
                enrollment__in=enrollments,
                result='NYC'
            ).values('enrollment').annotate(
                nyc_count=Count('id')
            ).filter(nyc_count__gte=2).count()
            
            cohort_data.append({
                'cohort': cohort,
                'member_count': member_count,
                'avg_progress': round(avg_progress, 1),
                'at_risk_count': at_risk
            })
        
        context['cohort_data'] = cohort_data
        
        # Get personnel roles (assessor/moderator badges)
        personnel_roles = get_user_personnel_roles(user)
        context['personnel_roles'] = personnel_roles
        context['is_assessor'] = personnel_roles['is_assessor']
        context['is_moderator'] = personnel_roles['is_moderator']
        
        # Outstanding work summary
        outstanding_assessments = []
        for cohort in cohorts:
            enrollments = Enrollment.objects.filter(cohort=cohort, status__in=['ACTIVE', 'ENROLLED'])
            for enrollment in enrollments:
                modules = Module.objects.filter(qualification=enrollment.qualification)
                activities = AssessmentActivity.objects.filter(module__in=modules, is_active=True)
                
                for activity in activities:
                    has_result = AssessmentResult.objects.filter(
                        enrollment=enrollment,
                        activity=activity
                    ).exists()
                    
                    if not has_result:
                        outstanding_assessments.append({
                            'enrollment': enrollment,
                            'activity': activity,
                            'learner': enrollment.learner
                        })
        
        context['outstanding_assessments'] = outstanding_assessments[:20]
        context['outstanding_count'] = len(outstanding_assessments)
        
        # Add aliases for template compatibility
        context['my_cohorts'] = cohorts  # Template expects my_cohorts
        context['pending_assessments_count'] = pending_to_mark  # Template expects this name
        
        # Collect at-risk learners list (learners with 2+ NYC results)
        at_risk_learners = []
        for data in cohort_data:
            cohort = data['cohort']
            enrollments = Enrollment.objects.filter(cohort=cohort, status__in=['ACTIVE', 'ENROLLED'])
            at_risk_enrollments = AssessmentResult.objects.filter(
                enrollment__in=enrollments,
                result='NYC'
            ).values('enrollment').annotate(
                nyc_count=Count('id')
            ).filter(nyc_count__gte=2).values_list('enrollment', flat=True)
            
            for enrollment_id in at_risk_enrollments:
                enrollment = enrollments.filter(id=enrollment_id).select_related('learner', 'cohort').first()
                if enrollment:
                    at_risk_learners.append({
                        'learner': enrollment.learner,
                        'enrollment': enrollment,
                        'cohort': cohort
                    })
        context['at_risk_learners'] = at_risk_learners
        
        # Quick stats
        context['stats'] = {
            'total_cohorts': cohorts.count(),
            'total_learners': total_learners,
            'pending_to_mark': pending_to_mark,
            'pending_moderation': pending_moderation,
            'today_sessions_count': today_sessions.count(),
            'outstanding_count': len(outstanding_assessments)
        }
        
        return context


class FacilitatorScheduleView(LoginRequiredMixin, TemplateView):
    """
    Comprehensive schedule view for facilitators
    """
    template_name = 'portals/facilitator/schedule.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        view_type = self.request.GET.get('view', 'today')
        context['view_type'] = view_type
        
        today = date.today()
        context['today'] = today
        
        # Calculate date ranges based on view type
        if view_type == 'today':
            start_date = today
            end_date = today
            context['title'] = "Today's Schedule"
            context['subtitle'] = today.strftime("%A, %d %B %Y")
            
        elif view_type == 'tomorrow':
            start_date = today + timedelta(days=1)
            end_date = start_date
            context['title'] = "Tomorrow's Schedule"
            context['subtitle'] = start_date.strftime("%A, %d %B %Y")
            
        elif view_type == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            context['title'] = "This Week"
            context['subtitle'] = f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}"
            
        elif view_type == 'next_week':
            start_date = today - timedelta(days=today.weekday()) + timedelta(days=7)
            end_date = start_date + timedelta(days=6)
            context['title'] = "Next Week"
            context['subtitle'] = f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}"
            
        elif view_type == 'month':
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            context['title'] = today.strftime("%B %Y")
            context['subtitle'] = "Full Month View"
            
        elif view_type == '3year':
            start_date = today
            end_date = today + timedelta(days=365*3)
            context['title'] = "3-Year Outlook"
            context['subtitle'] = f"{today.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}"
            
        else:
            start_date = today
            end_date = today
            context['title'] = "Today's Schedule"
            context['subtitle'] = today.strftime("%A, %d %B %Y")
        
        context['start_date'] = start_date
        context['end_date'] = end_date
        
        # Get sessions for the date range
        sessions = ScheduleSession.objects.filter(
            facilitator=user,
            date__gte=start_date,
            date__lte=end_date,
            is_cancelled=False
        ).select_related(
            'module', 'venue', 'cohort'
        ).order_by('date', 'start_time')
        
        context['sessions'] = sessions
        
        # Group sessions by date
        sessions_by_date = {}
        for session in sessions:
            if session.date not in sessions_by_date:
                sessions_by_date[session.date] = []
            sessions_by_date[session.date].append(session)
        
        context['sessions_by_date'] = dict(sorted(sessions_by_date.items()))
        
        # For week views, create a list of days
        if view_type in ['week', 'next_week']:
            days = []
            current = start_date
            while current <= end_date:
                days.append({
                    'date': current,
                    'name': current.strftime('%A'),
                    'short_name': current.strftime('%a'),
                    'is_today': current == today,
                    'sessions': sessions_by_date.get(current, [])
                })
                current += timedelta(days=1)
            context['days'] = days
        
        # Get cohorts for 3-year view
        if view_type == '3year':
            cohorts = Cohort.objects.filter(
                facilitator=user,
                status__in=['PLANNED', 'OPEN', 'ACTIVE']
            ).order_by('start_date')
            
            cohort_timeline = []
            for cohort in cohorts:
                cohort_timeline.append({
                    'cohort': cohort,
                    'qualification': cohort.qualification,
                    'start_date': cohort.start_date,
                    'end_date': cohort.end_date
                })
            context['cohort_timeline'] = cohort_timeline
        
        return context


class FacilitatorClassListView(LoginRequiredMixin, TemplateView):
    """
    View all learners in a specific cohort/class with easy access to grading
    """
    template_name = 'portals/facilitator/class_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cohort_id = self.kwargs.get('cohort_id')
        user = self.request.user
        
        # If no cohort specified, show list of all cohorts
        if not cohort_id:
            cohorts = Cohort.objects.filter(
                facilitator=user,
                status__in=['ACTIVE', 'OPEN']
            ).select_related('qualification', 'campus')
            context['cohorts'] = cohorts
            context['show_cohort_list'] = True
            return context
        
        cohort = get_object_or_404(Cohort, pk=cohort_id)
        context['cohort'] = cohort
        context['show_cohort_list'] = False
        
        # Get all learner enrollments in this cohort
        enrollments = Enrollment.objects.filter(
            cohort=cohort,
            status__in=['ACTIVE', 'ENROLLED']
        ).select_related('learner', 'learner__user', 'qualification')
        
        learner_data = []
        for enrollment in enrollments:
            # Calculate progress
            modules = Module.objects.filter(qualification=enrollment.qualification)
            activities = AssessmentActivity.objects.filter(module__in=modules, is_active=True)
            total = activities.count()
            
            completed = AssessmentResult.objects.filter(
                enrollment=enrollment,
                result='C',
                status='FINALIZED'
            ).values('activity').distinct().count()
            
            # Get NYC count
            nyc_count = AssessmentResult.objects.filter(
                enrollment=enrollment,
                result='NYC'
            ).count()
            
            # Pending assessments (needs grading)
            graded_activities = AssessmentResult.objects.filter(
                enrollment=enrollment
            ).values_list('activity_id', flat=True)
            
            pending_count = activities.exclude(id__in=graded_activities).count()
            
            # Latest activity
            latest_result = AssessmentResult.objects.filter(
                enrollment=enrollment
            ).order_by('-assessment_date').first()
            
            learner_data.append({
                'enrollment': enrollment,
                'learner': enrollment.learner,
                'total_activities': total,
                'completed': completed,
                'progress': round(completed / total * 100) if total > 0 else 0,
                'nyc_count': nyc_count,
                'pending_count': pending_count,
                'latest_activity': latest_result,
                'status': 'at_risk' if nyc_count >= 2 else 'on_track'
            })
        
        # Sort by status (at-risk first) then by progress
        learner_data.sort(key=lambda x: (x['status'] != 'at_risk', -x['pending_count'], -x['progress']))
        
        context['learners'] = learner_data
        context['total_learners'] = len(learner_data)
        context['at_risk_count'] = len([l for l in learner_data if l['status'] == 'at_risk'])
        
        # Get activities for quick grading dropdown
        if enrollments.exists():
            first_enrollment = enrollments.first()
            modules = Module.objects.filter(qualification=first_enrollment.qualification)
            activities = AssessmentActivity.objects.filter(
                module__in=modules,
                is_active=True
            ).select_related('module').order_by('module__sequence_order', 'sequence_order')
            context['activities'] = activities
        
        return context


class FacilitatorCohortDetailView(LoginRequiredMixin, TemplateView):
    """
    Detailed view of a cohort or single learner's progress for grading
    """
    template_name = 'portals/facilitator/learner_detail.html'
    
    def get_template_names(self):
        cohort_id = self.kwargs.get('cohort_id')
        if cohort_id:
            return ['portals/facilitator/cohort_detail.html']
        return [self.template_name]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        learner_id = self.kwargs.get('learner_id')
        enrollment_id = self.kwargs.get('enrollment_id')
        cohort_id = self.kwargs.get('cohort_id')
        
        if enrollment_id:
            enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
            learner = enrollment.learner
        elif learner_id:
            learner = get_object_or_404(Learner, pk=learner_id)
            enrollment = Enrollment.objects.filter(learner=learner).first()
        elif cohort_id:
            # Show cohort overview instead
            cohort = get_object_or_404(Cohort, pk=cohort_id)
            context['cohort'] = cohort
            context['show_cohort_overview'] = True
            
            # Get all enrollments for this cohort
            enrollments = Enrollment.objects.filter(
                cohort=cohort,
                status__in=['ACTIVE', 'ENROLLED', 'COMPLETED', 'WITHDRAWN']
            ).select_related('learner__user', 'qualification')
            
            # Calculate stats for each enrollment
            enrollment_list = []
            total_progress = 0
            total_score = 0
            score_count = 0
            score_distribution = {
                '0_30': 0, '31_50': 0, '51_70': 0, '71_85': 0, '86_100': 0
            }
            
            for enrollment in enrollments:
                modules = Module.objects.filter(qualification=enrollment.qualification)
                activities = AssessmentActivity.objects.filter(module__in=modules, is_active=True)
                total_activities = activities.count()
                
                # Get results
                results = AssessmentResult.objects.filter(enrollment=enrollment)
                competent = results.filter(result='C').values('activity').distinct().count()
                pending = total_activities - results.values('activity').distinct().count()
                
                # Calculate progress
                progress = round((competent / total_activities * 100) if total_activities > 0 else 0)
                enrollment.progress = progress
                total_progress += progress
                
                # Calculate average score
                scores = results.filter(percentage_score__isnull=False)
                if scores.exists():
                    avg = scores.aggregate(avg=Avg('percentage_score'))['avg'] or 0
                    enrollment.avg_score = round(avg)
                    total_score += avg
                    score_count += 1
                    
                    # Update score distribution
                    if avg <= 30:
                        score_distribution['0_30'] += 1
                    elif avg <= 50:
                        score_distribution['31_50'] += 1
                    elif avg <= 70:
                        score_distribution['51_70'] += 1
                    elif avg <= 85:
                        score_distribution['71_85'] += 1
                    else:
                        score_distribution['86_100'] += 1
                else:
                    enrollment.avg_score = None
                
                enrollment.pending_count = pending
                enrollment_list.append(enrollment)
            
            context['enrollments'] = enrollment_list
            context['active_learners'] = enrollments.filter(status='ACTIVE').count()
            context['pending_assessments'] = sum(e.pending_count for e in enrollment_list)
            context['avg_progress'] = round(total_progress / len(enrollment_list)) if enrollment_list else 0
            context['pass_rate'] = round(total_score / score_count) if score_count > 0 else 0
            context['score_distribution'] = score_distribution
            
            return context
        else:
            return context
        
        context['learner'] = learner
        context['enrollment'] = enrollment
        
        # Get all modules with results
        modules = Module.objects.filter(
            qualification=enrollment.qualification,
            is_active=True
        ).order_by('sequence_order')
        
        module_data = []
        total_activities = 0
        total_completed = 0
        
        for module in modules:
            activities = AssessmentActivity.objects.filter(module=module, is_active=True)
            
            activity_data = []
            for activity in activities:
                results = AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    activity=activity
                ).order_by('-attempt_number')
                
                latest = results.first()
                is_competent = latest and latest.result == 'C'
                
                activity_data.append({
                    'activity': activity,
                    'results': results,
                    'latest_result': latest,
                    'status': 'competent' if is_competent else
                             'nyc' if latest and latest.result == 'NYC' else
                             'pending' if latest else 'not_started',
                    'can_grade': not is_competent and (not latest or results.count() < activity.max_attempts)
                })
                
                total_activities += 1
                if is_competent:
                    total_completed += 1
            
            competent_count = len([a for a in activity_data if a['status'] == 'competent'])
            
            module_data.append({
                'module': module,
                'activities': activity_data,
                'competent_count': competent_count,
                'total_count': len(activity_data),
                'progress': round(competent_count / len(activity_data) * 100) if activity_data else 0
            })
        
        context['modules'] = module_data
        
        # Overall stats
        context['overall_progress'] = round(total_completed / total_activities * 100) if total_activities > 0 else 0
        context['total_completed'] = total_completed
        context['total_activities'] = total_activities
        
        return context


class FacilitatorPendingAssessmentsView(LoginRequiredMixin, TemplateView):
    """
    List of assessments to grade/mark - organized for easy batch grading
    """
    template_name = 'portals/facilitator/pending_assessments.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get facilitator's cohorts
        cohorts = Cohort.objects.filter(
            facilitator=user,
            status__in=['ACTIVE', 'OPEN']
        )
        
        context['cohorts'] = cohorts
        
        # Filter by cohort if specified
        selected_cohort = self.request.GET.get('cohort')
        if selected_cohort:
            cohorts = cohorts.filter(pk=selected_cohort)
            context['selected_cohort'] = int(selected_cohort)
        
        # Get enrollments for these cohorts
        enrollments = Enrollment.objects.filter(
            cohort__in=cohorts,
            status__in=['ACTIVE', 'ENROLLED']
        )
        
        # Filter by status
        status_filter = self.request.GET.get('status', 'pending')
        context['status_filter'] = status_filter
        
        if status_filter == 'pending':
            # Get activities that need grading (no result yet)
            pending = []
            for enrollment in enrollments:
                modules = Module.objects.filter(qualification=enrollment.qualification)
                activities = AssessmentActivity.objects.filter(module__in=modules, is_active=True)
                
                for activity in activities:
                    has_result = AssessmentResult.objects.filter(
                        enrollment=enrollment,
                        activity=activity
                    ).exists()
                    
                    if not has_result:
                        pending.append({
                            'enrollment': enrollment,
                            'activity': activity,
                            'learner': enrollment.learner,
                            'module': activity.module
                        })
            
            # Sort by module order
            pending.sort(key=lambda x: (x['module'].sequence_order, x['activity'].sequence_order))
            context['assessments'] = pending[:100]
            context['total_pending'] = len(pending)
            
        elif status_filter == 'to_moderate':
            # Results pending moderation
            results = AssessmentResult.objects.filter(
                enrollment__in=enrollments,
                status='PENDING_MOD'
            ).select_related('enrollment__learner', 'activity', 'assessor')
            context['assessments'] = results
            context['total_to_moderate'] = results.count()
            
        elif status_filter == 'recent':
            # Recently graded
            results = AssessmentResult.objects.filter(
                enrollment__in=enrollments
            ).select_related(
                'enrollment__learner', 'activity', 'assessor'
            ).order_by('-updated_at')[:50]
            context['assessments'] = results
        
        return context


class AssessLearnerView(LoginRequiredMixin, TemplateView):
    """
    Grade/mark an assessment for a learner - simplified capture form
    """
    template_name = 'portals/facilitator/assess_learner.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enrollment_id = self.kwargs.get('enrollment_id')
        activity_id = self.kwargs.get('activity_id')
        
        enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
        activity = get_object_or_404(AssessmentActivity, pk=activity_id)
        
        context['enrollment'] = enrollment
        context['activity'] = activity
        context['learner'] = enrollment.learner
        context['module'] = activity.module
        
        # Get previous attempts
        previous_results = AssessmentResult.objects.filter(
            enrollment=enrollment,
            activity=activity
        ).order_by('attempt_number')
        
        context['previous_results'] = previous_results
        context['attempt_number'] = previous_results.count() + 1
        context['can_attempt'] = previous_results.count() < activity.max_attempts
        
        # Check if already competent
        context['is_competent'] = previous_results.filter(result='C').exists()
        
        return context
    
    def post(self, request, *args, **kwargs):
        enrollment_id = self.kwargs.get('enrollment_id')
        activity_id = self.kwargs.get('activity_id')
        
        enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
        activity = get_object_or_404(AssessmentActivity, pk=activity_id)
        
        # Get form data
        result = request.POST.get('result')
        percentage = request.POST.get('percentage_score')
        feedback = request.POST.get('feedback', '')
        
        # Get attempt number
        existing = AssessmentResult.objects.filter(
            enrollment=enrollment,
            activity=activity
        ).count()
        
        # Validate
        if existing >= activity.max_attempts:
            messages.error(request, 'Maximum attempts reached for this assessment.')
            return HttpResponseRedirect(request.path)
        
        # Create result
        assessment_result = AssessmentResult.objects.create(
            enrollment=enrollment,
            activity=activity,
            assessor=request.user,
            result=result,
            percentage_score=percentage if percentage else None,
            feedback=feedback,
            assessment_date=date.today(),
            attempt_number=existing + 1,
            status='PENDING_MOD' if result == 'NYC' else 'FINALIZED'
        )
        
        messages.success(request, f'Assessment result saved for {enrollment.learner}')
        
        # Check where to redirect
        next_url = request.POST.get('next')
        if next_url:
            return HttpResponseRedirect(next_url)
        
        return HttpResponseRedirect(reverse('portals:facilitator_assessments'))


class ModerateLearnerView(LoginRequiredMixin, TemplateView):
    """
    Moderate assessment results - easy approval/rejection
    """
    template_name = 'portals/facilitator/moderate_learner.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result_id = self.kwargs.get('result_id')
        
        result = get_object_or_404(AssessmentResult, pk=result_id)
        context['result'] = result
        context['learner'] = result.enrollment.learner
        context['activity'] = result.activity
        context['enrollment'] = result.enrollment
        
        # Get previous moderation records
        moderations = ModerationRecord.objects.filter(
            assessment_result=result
        ).order_by('-moderated_at')
        context['moderations'] = moderations
        
        return context
    
    def post(self, request, *args, **kwargs):
        result_id = self.kwargs.get('result_id')
        result = get_object_or_404(AssessmentResult, pk=result_id)
        
        # Get form data
        decision = request.POST.get('decision')  # 'approve' or 'reject'
        comments = request.POST.get('comments', '')
        new_result = request.POST.get('new_result', result.result)
        
        # Create moderation record
        ModerationRecord.objects.create(
            assessment_result=result,
            moderator=request.user,
            original_result=result.result,
            moderated_result=new_result if decision == 'change' else result.result,
            is_upheld=decision == 'approve',
            comments=comments,
            moderated_at=timezone.now()
        )
        
        # Update result status
        if decision == 'approve':
            result.status = 'FINALIZED'
            result.save()
            messages.success(request, 'Result approved and finalized')
        elif decision == 'change':
            result.result = new_result
            result.status = 'FINALIZED'
            result.save()
            messages.info(request, f'Result changed to {new_result} and finalized')
        
        return HttpResponseRedirect(reverse('portals:facilitator_assessments') + '?status=to_moderate')


class FacilitatorLearnerProgressView(LoginRequiredMixin, TemplateView):
    """
    Batch grade multiple learners for the same activity
    """
    template_name = 'portals/facilitator/batch_grade.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cohort_id = self.kwargs.get('cohort_id')
        activity_id = self.kwargs.get('activity_id')
        
        cohort = get_object_or_404(Cohort, pk=cohort_id)
        activity = get_object_or_404(AssessmentActivity, pk=activity_id)
        
        context['cohort'] = cohort
        context['activity'] = activity
        context['module'] = activity.module
        
        # Get all learners in cohort
        enrollments = Enrollment.objects.filter(
            cohort=cohort,
            status__in=['ACTIVE', 'ENROLLED']
        ).select_related('learner', 'learner__user')
        
        learner_data = []
        for enrollment in enrollments:
            existing_result = AssessmentResult.objects.filter(
                enrollment=enrollment,
                activity=activity
            ).order_by('-attempt_number').first()
            
            is_competent = existing_result and existing_result.result == 'C'
            attempts_used = AssessmentResult.objects.filter(
                enrollment=enrollment,
                activity=activity
            ).count()
            
            learner_data.append({
                'learner': enrollment.learner,
                'enrollment': enrollment,
                'existing_result': existing_result,
                'is_competent': is_competent,
                'attempts_used': attempts_used,
                'can_grade': not is_competent and attempts_used < activity.max_attempts
            })
        
        # Sort: those who can be graded first
        learner_data.sort(key=lambda x: (not x['can_grade'], x['learner'].surname))
        
        context['learners'] = learner_data
        context['gradeable_count'] = len([l for l in learner_data if l['can_grade']])
        
        return context
    
    def post(self, request, *args, **kwargs):
        cohort_id = self.kwargs.get('cohort_id')
        activity_id = self.kwargs.get('activity_id')
        
        cohort = get_object_or_404(Cohort, pk=cohort_id)
        activity = get_object_or_404(AssessmentActivity, pk=activity_id)
        
        # Process each learner's grade
        graded_count = 0
        for key, value in request.POST.items():
            if key.startswith('result_'):
                enrollment_id = key.replace('result_', '')
                result_value = value
                
                if result_value:  # Only if a result was selected
                    try:
                        enrollment = Enrollment.objects.get(pk=enrollment_id)
                        
                        # Check existing results
                        existing = AssessmentResult.objects.filter(
                            enrollment=enrollment,
                            activity=activity
                        )
                        
                        # Check if already competent or max attempts reached
                        if existing.filter(result='C').exists():
                            continue
                        if existing.count() >= activity.max_attempts:
                            continue
                        
                        # Get percentage if provided
                        percentage_key = f'percentage_{enrollment_id}'
                        percentage = request.POST.get(percentage_key)
                        
                        feedback_key = f'feedback_{enrollment_id}'
                        feedback = request.POST.get(feedback_key, '')
                        
                        # Create result
                        AssessmentResult.objects.create(
                            enrollment=enrollment,
                            activity=activity,
                            assessor=request.user,
                            result=result_value,
                            percentage_score=percentage if percentage else None,
                            feedback=feedback,
                            assessment_date=date.today(),
                            attempt_number=existing.count() + 1,
                            status='PENDING_MOD' if result_value == 'NYC' else 'FINALIZED'
                        )
                        graded_count += 1
                    except Enrollment.DoesNotExist:
                        continue
        
        messages.success(request, f'Saved {graded_count} assessment results')
        return HttpResponseRedirect(reverse('portals:facilitator_class', args=[cohort_id]))


class FacilitatorLearnerYearProgressView(LoginRequiredMixin, TemplateView):
    """
    Year-based learner progress view
    Shows progress organized by Year 1/2/3 with Institutional vs Workplace legs
    Includes formative/summative assessment breakdown and manual override capability
    """
    template_name = 'portals/facilitator/learner_year_progress.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enrollment_id = self.kwargs.get('enrollment_id')
        
        enrollment = get_object_or_404(
            Enrollment.objects.select_related(
                'learner', 'learner__user', 'qualification', 'cohort'
            ),
            pk=enrollment_id
        )
        
        context['enrollment'] = enrollment
        context['learner'] = enrollment.learner
        context['qualification'] = enrollment.qualification
        
        # Get comprehensive progress data
        progress_data = enrollment.get_progress_by_component()
        context['progress_data'] = progress_data
        context['current_year'] = progress_data['current_year']
        context['years'] = progress_data['years']
        context['institutional_total'] = progress_data['institutional_total']
        context['workplace_total'] = progress_data['workplace_total']
        context['overall_progress'] = progress_data['overall_progress']
        
        # Selected year tab (default to current year)
        selected_year = self.request.GET.get('year', str(progress_data['current_year']))
        try:
            context['selected_year'] = int(selected_year)
        except ValueError:
            context['selected_year'] = progress_data['current_year']
        
        # Get selected year's detailed data
        if context['selected_year'] in progress_data['years']:
            context['year_data'] = progress_data['years'][context['selected_year']]
        else:
            context['year_data'] = None
        
        # Overall stats
        from assessments.models import AssessmentResult
        results = AssessmentResult.objects.filter(enrollment=enrollment, status='FINALIZED')
        context['competent_count'] = results.filter(result='C').count()
        context['nyc_count'] = results.filter(result='NYC').count()
        context['avg_score'] = results.filter(
            percentage_score__isnull=False
        ).aggregate(avg=Avg('percentage_score'))['avg']
        
        # Get workplace stints progress
        from corporate.models import WorkplaceStint
        stints = WorkplaceStint.objects.filter(
            qualification=enrollment.qualification,
            is_active=True
        ).order_by('stint_number')
        
        stint_progress = []
        for stint in stints:
            placements = enrollment.workplace_placements.filter(workplace_stint=stint)
            total_days = sum(p.duration_days for p in placements if p.status in ['ACTIVE', 'COMPLETED'])
            stint_progress.append({
                'stint': stint,
                'placements': placements,
                'days_completed': total_days,
                'days_required': stint.duration_days_required,
                'progress_percent': min(100, int((total_days / stint.duration_days_required) * 100)) if stint.duration_days_required > 0 else 0,
                'is_complete': total_days >= stint.duration_days_required,
            })
        context['stint_progress'] = stint_progress
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle manual override requests"""
        from academics.models import LearnerModuleProgress
        
        enrollment_id = self.kwargs.get('enrollment_id')
        enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
        
        action = request.POST.get('action')
        module_progress_id = request.POST.get('module_progress_id')
        
        if action == 'override':
            progress = get_object_or_404(LearnerModuleProgress, pk=module_progress_id)
            
            formative_status = request.POST.get('formative_status')
            summative_status = request.POST.get('summative_status')
            overall_status = request.POST.get('overall_status')
            reason = request.POST.get('override_reason', '')
            
            progress.apply_manual_override(
                user=request.user,
                formative_status=formative_status if formative_status else None,
                summative_status=summative_status if summative_status else None,
                overall_status=overall_status if overall_status else None,
                reason=reason
            )
            messages.success(request, f'Manual override applied for {progress.module.title}')
        
        elif action == 'clear_override':
            progress = get_object_or_404(LearnerModuleProgress, pk=module_progress_id)
            progress.clear_manual_override()
            messages.success(request, f'Override cleared for {progress.module.title}, progress recalculated')
        
        return HttpResponseRedirect(
            reverse('portals:facilitator_learner_progress', args=[enrollment_id]) + 
            f'?year={request.POST.get("year", "1")}'
        )


# =====================================================
# ATTENDANCE VERIFICATION VIEWS
# =====================================================

class FacilitatorAttendanceView(LoginRequiredMixin, TemplateView):
    """
    Facilitator attendance verification portal.
    Shows all mentor-verified attendance records awaiting facilitator verification.
    """
    template_name = 'portals/facilitator/attendance_verify.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get facilitator profile and validate campus assignments
        facilitator = get_facilitator_context(user)
        if not facilitator:
            return {'error': 'no_profile', 'message': 'Facilitator profile not found. Please contact your administrator.'}
        
        if not facilitator.campuses.exists():
            return {'error': 'no_campuses', 'message': 'You do not have any campuses assigned. Please contact your administrator.'}
        
        # Get selected campus filter
        assigned_campuses = facilitator.campuses.all()
        selected_campus_id = self.request.GET.get('campus') or self.request.session.get('facilitator_selected_campus')
        selected_campus = None
        if selected_campus_id:
            try:
                selected_campus = assigned_campuses.get(id=selected_campus_id)
            except:
                pass
        
        # Get filter parameters
        learner_id = self.request.GET.get('learner')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        show_verified = self.request.GET.get('show_verified', '').lower() == 'true'
        
        # Import models
        from learners.models import WorkplaceAttendance
        from corporate.models import WorkplacePlacement
        
        # Base query: attendance records for placements at employers in facilitator's campuses
        placements = WorkplacePlacement.objects.filter(
            host_employer__campus__in=assigned_campuses if not selected_campus else [selected_campus],
            status__in=['ACTIVE', 'COMPLETED']
        )
        
        # Filter attendance records
        attendance_filter = Q(placement__in=placements, mentor_verified=True)
        
        if not show_verified:
            attendance_filter &= Q(facilitator_verified=False)
        
        if learner_id:
            attendance_filter &= Q(placement__learner_id=learner_id)
        
        if date_from:
            attendance_filter &= Q(date__gte=date_from)
        
        if date_to:
            attendance_filter &= Q(date__lte=date_to)
        
        attendance_records = WorkplaceAttendance.objects.filter(
            attendance_filter
        ).select_related(
            'placement__learner',
            'placement__host_employer',
            'mentor_verified_by',
            'facilitator_verified_by'
        ).prefetch_related(
            'audit_logs'
        ).order_by('-date', 'placement__learner__first_name')
        
        # Get summary stats
        total_pending = attendance_records.filter(facilitator_verified=False).count()
        total_verified = attendance_records.filter(facilitator_verified=True).count()
        
        # Get unique learners for filter dropdown
        learners_with_attendance = Learner.objects.filter(
            placements__in=placements
        ).distinct().order_by('first_name', 'last_name')
        
        context.update({
            'facilitator': facilitator,
            'assigned_campuses': assigned_campuses,
            'selected_campus': selected_campus,
            'attendance_records': attendance_records,
            'total_pending': total_pending,
            'total_verified': total_verified,
            'learners': learners_with_attendance,
            'show_verified': show_verified,
            'date_from': date_from,
            'date_to': date_to,
            'selected_learner_id': int(learner_id) if learner_id else None,
        })
        
        return context


@login_required
@require_POST
def facilitator_bulk_verify_attendance(request):
    """
    POST handler for bulk verification of attendance records.
    Creates audit log entries for each verification.
    """
    from learners.models import WorkplaceAttendance, AttendanceAuditLog
    
    # Get facilitator profile
    facilitator = get_facilitator_context(request.user)
    if not facilitator or not facilitator.campuses.exists():
        return JsonResponse({'success': False, 'error': 'No facilitator profile or campuses assigned'}, status=403)
    
    # Get selected attendance IDs from POST
    attendance_ids = request.POST.getlist('attendance_ids[]')
    
    if not attendance_ids:
        return JsonResponse({'success': False, 'error': 'No attendance records selected'}, status=400)
    
    # Verify facilitator has access to these attendance records
    from corporate.models import WorkplacePlacement
    assigned_campuses = facilitator.campuses.all()
    
    placements = WorkplacePlacement.objects.filter(
        host_employer__campus__in=assigned_campuses,
        status__in=['ACTIVE', 'COMPLETED']
    )
    
    attendance_records = WorkplaceAttendance.objects.filter(
        id__in=attendance_ids,
        placement__in=placements,
        mentor_verified=True,
        facilitator_verified=False
    )
    
    verified_count = 0
    
    for attendance in attendance_records:
        # Mark as facilitator verified
        attendance.facilitator_verified = True
        attendance.facilitator_verified_at = timezone.now()
        attendance.facilitator_verified_by = request.user
        attendance.save()
        
        # Create audit log entry
        AttendanceAuditLog.objects.create(
            attendance=attendance,
            changed_by=request.user,
            action='VERIFY',
            notes='Facilitator verification completed'
        )
        
        verified_count += 1
    
    messages.success(request, f'Successfully verified {verified_count} attendance record(s)')
    
    return JsonResponse({
        'success': True,
        'verified_count': verified_count
    })


# =====================================================
# DIGITAL SIGNATURE CAPTURE FOR FACILITATORS
# =====================================================

class FacilitatorSignatureView(LoginRequiredMixin, TemplateView):
    """
    Digital signature capture for facilitators.
    Signatures are locked after first capture and can only be modified by admin.
    """
    template_name = 'portals/facilitator/signature.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        facilitator = get_facilitator_context(user)
        if not facilitator:
            context['no_profile'] = True
            return context
        
        context['facilitator'] = facilitator
        context['signature_locked'] = facilitator.signature_locked
        context['has_signature'] = bool(facilitator.signature)
        
        if facilitator.signature:
            context['signature_url'] = facilitator.signature.url
            context['signature_captured_at'] = facilitator.signature_captured_at
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle signature submission."""
        from core.services.signature_service import SignatureService
        
        facilitator = get_facilitator_context(request.user)
        if not facilitator:
            messages.error(request, 'Facilitator profile not found.')
            return redirect('portals:facilitator_dashboard')
        
        # Check if already locked
        if facilitator.signature_locked:
            messages.error(request, 'Your signature is locked and cannot be changed. Contact admin for assistance.')
            return redirect('portals:facilitator_signature')
        
        # Get signature data
        signature_data = request.POST.get('signature_data', '')
        consent_given = request.POST.get('popia_consent') == 'on'
        
        if not signature_data:
            messages.error(request, 'Please provide your signature.')
            return redirect('portals:facilitator_signature')
        
        if not consent_given:
            messages.error(request, 'You must accept the POPIA consent to proceed.')
            return redirect('portals:facilitator_signature')
        
        # Capture signature
        service = SignatureService()
        success, message = service.capture_signature_for_facilitator(
            facilitator=facilitator,
            base64_data=signature_data,
            request=request,
            consent_given=consent_given
        )
        
        if success:
            messages.success(request, 'Your digital signature has been captured and locked successfully.')
        else:
            messages.error(request, message)
        
        return redirect('portals:facilitator_signature')


@login_required
def facilitator_signature_api(request):
    """
    API endpoint for facilitator signature capture (AJAX).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    from core.services.signature_service import SignatureService
    
    facilitator = get_facilitator_context(request.user)
    if not facilitator:
        return JsonResponse({'error': 'Facilitator profile not found'}, status=403)
    
    try:
        data = json.loads(request.body)
        signature_data = data.get('signature_data', '')
        consent_given = data.get('popia_consent', False)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    service = SignatureService()
    success, message = service.capture_signature_for_facilitator(
        facilitator=facilitator,
        base64_data=signature_data,
        request=request,
        consent_given=consent_given
    )
    
    if success:
        return JsonResponse({
            'success': True,
            'message': message,
            'signature_url': facilitator.signature.url if facilitator.signature else None,
            'locked': facilitator.signature_locked
        })
    else:
        return JsonResponse({'success': False, 'error': message}, status=400)

