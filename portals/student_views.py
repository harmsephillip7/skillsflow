"""
Student/Learner Portal Views - Easy Access to Learning

Simple, intuitive views for learners to:
- See their enrolled courses
- Access learning materials
- View upcoming and completed assessments
- Check their marks and progress
- View schedules (today, tomorrow, this week, 3-year outlook)
- Manage workplace-based learning (WBL) placements
- Submit attendance and logbooks
- Communicate with mentors and workplace officers
"""
import json
from calendar import monthrange
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView, ListView
from django.db import transaction
from django.db.models import Count, Q, Avg, Sum, Case, When, Value, IntegerField
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from datetime import date, timedelta, datetime

from learners.models import (
    Learner,
    WorkplaceAttendance,
    WorkplaceLogbookEntry,
    WorkplaceModuleCompletion,
    StipendCalculation,
    DisciplinaryRecord,
    LearnerSupportNote,
    DailyLogbookEntry,
    DailyTaskCompletion,
)
from academics.models import Enrollment, Module, Qualification, WorkplaceModuleOutcome
from assessments.models import AssessmentActivity, AssessmentResult, PoESubmission
from logistics.models import Cohort, ScheduleSession, Attendance
from corporate.models import WorkplacePlacement, HostMentor
from core.models import MessageThread, Message, ThreadParticipant, Notification


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main student dashboard - simple overview of everything including outstanding work and today's schedule
    """
    template_name = 'portals/student/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # Get learner profile
        learner = Learner.objects.filter(user=user).first()
        context['learner'] = learner
        
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        # Get active enrollments
        enrollments = Enrollment.objects.filter(
            learner=learner,
            status__in=['ACTIVE', 'ENROLLED', 'REGISTERED']
        ).select_related('qualification', 'campus', 'cohort')
        
        # Calculate progress for each enrollment
        enrollment_data = []
        all_pending_activities = []
        cohort_ids = []
        
        for enrollment in enrollments:
            if enrollment.cohort:
                cohort_ids.append(enrollment.cohort.id)
                
            # Get modules for this qualification
            modules = Module.objects.filter(qualification=enrollment.qualification, is_active=True)
            total_modules = modules.count()
            
            # Get assessment activities for these modules
            activities = AssessmentActivity.objects.filter(module__in=modules, is_active=True)
            total_activities = activities.count()
            
            # Get completed assessments (Competent results)
            completed = AssessmentResult.objects.filter(
                enrollment=enrollment,
                result='C',
                status='FINALIZED'
            ).values('activity').distinct().count()
            
            # Calculate progress percentage
            progress = (completed / total_activities * 100) if total_activities > 0 else 0
            
            enrollment_data.append({
                'enrollment': enrollment,
                'total_modules': total_modules,
                'total_activities': total_activities,
                'completed_activities': completed,
                'progress': round(progress, 1),
                'modules': modules[:5]  # First 5 modules
            })
            
            # Get pending activities for this enrollment
            for activity in activities:
                has_competent = AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    activity=activity,
                    result='C'
                ).exists()
                
                if not has_competent:
                    attempts = AssessmentResult.objects.filter(
                        enrollment=enrollment,
                        activity=activity
                    ).count()
                    
                    if attempts < activity.max_attempts:
                        all_pending_activities.append({
                            'activity': activity,
                            'enrollment': enrollment,
                            'module': activity.module,
                            'attempts_used': attempts,
                            'attempts_remaining': activity.max_attempts - attempts
                        })
        
        context['enrollments'] = enrollment_data
        context['upcoming_assessments'] = all_pending_activities[:8]
        context['outstanding_count'] = len(all_pending_activities)
        
        # Get today's and tomorrow's sessions
        if cohort_ids:
            today_sessions = ScheduleSession.objects.filter(
                cohort_id__in=cohort_ids,
                date=today,
                is_cancelled=False
            ).select_related('module', 'venue', 'facilitator').order_by('start_time')
            
            tomorrow_sessions = ScheduleSession.objects.filter(
                cohort_id__in=cohort_ids,
                date=tomorrow,
                is_cancelled=False
            ).select_related('module', 'venue', 'facilitator').order_by('start_time')
        else:
            today_sessions = []
            tomorrow_sessions = []
        
        context['today_sessions'] = today_sessions
        context['tomorrow_sessions'] = tomorrow_sessions
        context['today'] = today
        context['tomorrow'] = tomorrow
        
        # Recent results
        recent_results = AssessmentResult.objects.filter(
            enrollment__learner=learner
        ).select_related(
            'activity', 'activity__module', 'enrollment__qualification'
        ).order_by('-assessment_date')[:5]
        
        context['recent_results'] = recent_results
        
        # Stats
        total_results = AssessmentResult.objects.filter(
            enrollment__learner=learner,
            status='FINALIZED'
        )
        competent_count = total_results.filter(result='C').count()
        total_count = total_results.count()
        
        context['stats'] = {
            'total_assessments': total_count,
            'competent': competent_count,
            'nyc': total_results.filter(result='NYC').count(),
            'competency_rate': round(competent_count / total_count * 100, 1) if total_count > 0 else 0,
            'outstanding': len(all_pending_activities)
        }
        
        return context


class StudentScheduleView(LoginRequiredMixin, TemplateView):
    """
    Comprehensive schedule view with multiple time ranges:
    - Today's sessions
    - Tomorrow's sessions
    - This week
    - Next week
    - 3-year outlook (calendar view)
    """
    template_name = 'portals/student/schedule.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get view type from URL params
        view_type = self.request.GET.get('view', 'today')
        context['view_type'] = view_type
        
        # Get learner profile
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        # Get active enrollments and their cohorts
        enrollments = Enrollment.objects.filter(
            learner=learner,
            status__in=['ACTIVE', 'ENROLLED', 'REGISTERED']
        ).select_related('cohort', 'qualification')
        
        cohort_ids = [e.cohort.id for e in enrollments if e.cohort]
        context['enrollments'] = enrollments
        
        today = date.today()
        context['today'] = today
        
        # Import relativedelta for 3-year calculations
        try:
            from dateutil.relativedelta import relativedelta
        except ImportError:
            relativedelta = None
        
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
            # Current week (Monday to Sunday)
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            context['title'] = "This Week"
            context['subtitle'] = f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}"
            
        elif view_type == 'next_week':
            # Next week
            start_date = today - timedelta(days=today.weekday()) + timedelta(days=7)
            end_date = start_date + timedelta(days=6)
            context['title'] = "Next Week"
            context['subtitle'] = f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}"
            
        elif view_type == 'month':
            # Current month
            start_date = today.replace(day=1)
            # Last day of month
            if today.month == 12:
                end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            context['title'] = today.strftime("%B %Y")
            context['subtitle'] = "Full Month View"
            
        elif view_type == '3year':
            # 3-year outlook
            start_date = today
            if relativedelta:
                end_date = today + relativedelta(years=3)
            else:
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
        if cohort_ids:
            sessions = ScheduleSession.objects.filter(
                cohort_id__in=cohort_ids,
                date__gte=start_date,
                date__lte=end_date,
                is_cancelled=False
            ).select_related(
                'module', 'venue', 'facilitator', 'cohort'
            ).order_by('date', 'start_time')
        else:
            sessions = ScheduleSession.objects.none()
        
        context['sessions'] = sessions
        
        # Group sessions by date for easier template rendering
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
        
        # For 3-year view, group by month/year
        if view_type == '3year':
            # Get cohort timelines
            cohort_timeline = []
            for enrollment in enrollments:
                if enrollment.cohort:
                    cohort_timeline.append({
                        'cohort': enrollment.cohort,
                        'qualification': enrollment.qualification,
                        'start_date': enrollment.cohort.start_date,
                        'end_date': enrollment.cohort.end_date
                    })
            context['cohort_timeline'] = cohort_timeline
            
            # Group sessions by month for calendar view
            sessions_by_month = {}
            for session in sessions:
                month_key = session.date.strftime('%Y-%m')
                if month_key not in sessions_by_month:
                    sessions_by_month[month_key] = {
                        'month': session.date.strftime('%B %Y'),
                        'sessions': [],
                        'count': 0
                    }
                sessions_by_month[month_key]['sessions'].append(session)
                sessions_by_month[month_key]['count'] += 1
            
            context['sessions_by_month'] = dict(sorted(sessions_by_month.items()))
        
        # Get upcoming assessments
        upcoming_assessments = []
        for enrollment in enrollments:
            modules = Module.objects.filter(qualification=enrollment.qualification)
            activities = AssessmentActivity.objects.filter(
                module__in=modules,
                is_active=True
            )
            
            for activity in activities:
                has_competent = AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    activity=activity,
                    result='C'
                ).exists()
                
                if not has_competent:
                    upcoming_assessments.append({
                        'activity': activity,
                        'enrollment': enrollment,
                        'module': activity.module
                    })
        
        context['upcoming_assessments'] = upcoming_assessments[:10]
        
        return context


class StudentEnrollmentsView(LoginRequiredMixin, TemplateView):
    """
    View all enrolled courses/qualifications with modules
    """
    template_name = 'portals/student/enrollments.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return context
        
        context['learner'] = learner
        
        # Get all enrollments
        enrollments = Enrollment.objects.filter(
            learner=learner
        ).select_related('qualification', 'campus', 'cohort').order_by('-enrollment_date')
        
        enrollment_data = []
        for enrollment in enrollments:
            modules = Module.objects.filter(
                qualification=enrollment.qualification,
                is_active=True
            ).order_by('sequence_order')
            
            module_data = []
            for module in modules:
                activities = AssessmentActivity.objects.filter(module=module, is_active=True)
                completed = AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    activity__module=module,
                    result='C',
                    status='FINALIZED'
                ).count()
                
                module_data.append({
                    'module': module,
                    'total_activities': activities.count(),
                    'completed': completed,
                    'progress': round(completed / activities.count() * 100) if activities.count() > 0 else 0
                })
            
            enrollment_data.append({
                'enrollment': enrollment,
                'modules': module_data,
                'total_modules': len(module_data),
                'completed_modules': len([m for m in module_data if m['progress'] == 100])
            })
        
        context['enrollments'] = enrollment_data
        return context


class StudentCourseDetailView(LoginRequiredMixin, TemplateView):
    """
    Detailed view of a single enrollment with all modules and assessments
    """
    template_name = 'portals/student/course_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enrollment_id = self.kwargs.get('pk')
        
        user = self.request.user
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return context
        
        context['learner'] = learner
        
        enrollment = get_object_or_404(Enrollment, pk=enrollment_id, learner=learner)
        context['enrollment'] = enrollment
        
        # Get all modules with their assessment activities
        modules = Module.objects.filter(
            qualification=enrollment.qualification,
            is_active=True
        ).order_by('sequence_order')
        
        module_data = []
        total_activities = 0
        total_completed = 0
        
        for module in modules:
            activities = AssessmentActivity.objects.filter(
                module=module,
                is_active=True
            ).order_by('sequence_order')
            
            activity_data = []
            for activity in activities:
                results = AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    activity=activity
                ).order_by('-attempt_number')
                
                latest_result = results.first()
                is_competent = latest_result and latest_result.result == 'C'
                
                activity_data.append({
                    'activity': activity,
                    'results': results,
                    'latest_result': latest_result,
                    'is_competent': is_competent,
                    'status': 'completed' if is_competent else 
                             'in_progress' if latest_result else 'not_started',
                    'attempts_remaining': activity.max_attempts - results.count()
                })
                
                total_activities += 1
                if is_competent:
                    total_completed += 1
            
            module_completed = len([a for a in activity_data if a['is_competent']])
            
            module_data.append({
                'module': module,
                'activities': activity_data,
                'total_activities': len(activity_data),
                'completed_activities': module_completed,
                'progress': round(module_completed / len(activity_data) * 100) if activity_data else 0
            })
        
        context['modules'] = module_data
        context['total_activities'] = total_activities
        context['total_completed'] = total_completed
        context['overall_progress'] = round(total_completed / total_activities * 100) if total_activities > 0 else 0
        
        return context


class StudentMarksView(LoginRequiredMixin, TemplateView):
    """
    View all marks/results - simple report card style
    """
    template_name = 'portals/student/marks.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return context
        
        context['learner'] = learner
        
        # Get selected enrollment or default to first active
        enrollment_id = self.request.GET.get('enrollment')
        if enrollment_id:
            enrollment = get_object_or_404(Enrollment, pk=enrollment_id, learner=learner)
        else:
            enrollment = Enrollment.objects.filter(
                learner=learner,
                status__in=['ACTIVE', 'ENROLLED']
            ).first()
        
        context['selected_enrollment'] = enrollment
        context['all_enrollments'] = Enrollment.objects.filter(learner=learner)
        
        if not enrollment:
            return context
        
        # Get all modules and their results
        modules = Module.objects.filter(
            qualification=enrollment.qualification,
            is_active=True
        ).order_by('sequence_order')
        
        module_results = []
        total_competent = 0
        total_activities = 0
        
        for module in modules:
            activities = AssessmentActivity.objects.filter(module=module, is_active=True)
            
            activity_results = []
            for activity in activities:
                result = AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    activity=activity
                ).order_by('-attempt_number').first()
                
                activity_results.append({
                    'activity': activity,
                    'result': result,
                })
                
                total_activities += 1
                if result and result.result == 'C':
                    total_competent += 1
            
            module_competent = len([a for a in activity_results if a['result'] and a['result'].result == 'C'])
            
            module_results.append({
                'module': module,
                'activities': activity_results,
                'competent_count': module_competent,
                'total_count': len(activity_results),
                'progress': round(module_competent / len(activity_results) * 100) if activity_results else 0
            })
        
        context['module_results'] = module_results
        context['overall_progress'] = round(total_competent / total_activities * 100) if total_activities > 0 else 0
        context['total_competent'] = total_competent
        context['total_activities'] = total_activities
        
        return context


class StudentAssessmentView(LoginRequiredMixin, TemplateView):
    """
    View upcoming and past assessments with outstanding work highlighted
    """
    template_name = 'portals/student/assessment.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return context
        
        context['learner'] = learner
        
        # Get all active enrollments
        enrollments = Enrollment.objects.filter(
            learner=learner,
            status__in=['ACTIVE', 'ENROLLED']
        ).select_related('qualification', 'cohort')
        
        # Pending/Outstanding assessments (not yet completed)
        pending = []
        for enrollment in enrollments:
            modules = Module.objects.filter(qualification=enrollment.qualification)
            activities = AssessmentActivity.objects.filter(
                module__in=modules,
                is_active=True
            ).select_related('module')
            
            for activity in activities:
                # Check if already completed
                has_competent = AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    activity=activity,
                    result='C'
                ).exists()
                
                if not has_competent:
                    attempts = AssessmentResult.objects.filter(
                        enrollment=enrollment,
                        activity=activity
                    ).count()
                    
                    nyc_count = AssessmentResult.objects.filter(
                        enrollment=enrollment,
                        activity=activity,
                        result='NYC'
                    ).count()
                    
                    if attempts < activity.max_attempts:
                        pending.append({
                            'activity': activity,
                            'enrollment': enrollment,
                            'module': activity.module,
                            'attempts_used': attempts,
                            'attempts_remaining': activity.max_attempts - attempts,
                            'nyc_count': nyc_count,
                            'is_urgent': nyc_count >= 2 or activity.max_attempts - attempts == 1
                        })
        
        # Sort urgent items first
        pending.sort(key=lambda x: (not x['is_urgent'], -x['nyc_count']))
        context['pending_assessments'] = pending
        context['outstanding_count'] = len(pending)
        context['urgent_count'] = len([p for p in pending if p['is_urgent']])
        
        # Completed assessments
        completed_results = AssessmentResult.objects.filter(
            enrollment__in=enrollments
        ).select_related(
            'activity', 'activity__module', 'enrollment__qualification', 'assessor'
        ).order_by('-assessment_date')
        
        context['completed_assessments'] = completed_results
        
        return context


class StudentMaterialsView(LoginRequiredMixin, TemplateView):
    """
    View for accessing learning materials organized by module
    """
    template_name = 'portals/student/materials.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['enrollments'] = []
            return context
        
        context['learner'] = learner
        
        # Get all active enrollments
        enrollments = Enrollment.objects.filter(
            learner=learner,
            status__in=['ACTIVE', 'ENROLLED']
        ).select_related('qualification', 'cohort')
        
        enrollment_data = []
        for enrollment in enrollments:
            modules = Module.objects.filter(
                qualification=enrollment.qualification,
                is_active=True
            ).order_by('sequence_order')
            
            enrollment_data.append({
                'enrollment': enrollment,
                'modules': modules
            })
        
        context['enrollments'] = enrollment_data
        return context


class StudentTimetableView(LoginRequiredMixin, TemplateView):
    """
    Weekly timetable view - grid style
    """
    template_name = 'portals/student/timetable.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['enrollments'] = []
            return context
        
        context['learner'] = learner
        
        # Get enrollments
        enrollments = Enrollment.objects.filter(
            learner=learner,
            status__in=['ACTIVE', 'ENROLLED']
        ).select_related('cohort', 'qualification')
        
        cohort_ids = [e.cohort.id for e in enrollments if e.cohort]
        
        # Calculate current week
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=4)  # Monday to Friday
        
        context['enrollments'] = enrollments
        context['current_week_start'] = week_start
        context['current_week_end'] = week_end
        context['week_number'] = today.isocalendar()[1]
        context['days'] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        context['today'] = today
        
        # Get sessions for this week
        if cohort_ids:
            sessions = ScheduleSession.objects.filter(
                cohort_id__in=cohort_ids,
                date__gte=week_start,
                date__lte=week_end,
                is_cancelled=False
            ).select_related('module', 'venue', 'facilitator').order_by('date', 'start_time')
            
            # Build schedule grid
            time_slots = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00']
            schedule = {}
            
            for slot in time_slots:
                schedule[slot] = {}
                for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                    schedule[slot][day] = None
            
            for session in sessions:
                slot_key = session.start_time.strftime('%H:00')
                day_name = session.date.strftime('%A')
                if slot_key in schedule and day_name in schedule[slot_key]:
                    schedule[slot_key][day_name] = session
            
            context['time_slots'] = time_slots
            context['schedule'] = schedule
            context['sessions'] = sessions
            
            # Today's sessions
            today_sessions = [s for s in sessions if s.date == today]
            context['today_sessions'] = today_sessions
        else:
            context['time_slots'] = []
            context['schedule'] = {}
            context['sessions'] = []
            context['today_sessions'] = []
        
        return context


# =============================================================================
# Workplace-Based Learning (WBL) Views
# =============================================================================

class StudentAttendanceHomeView(LoginRequiredMixin, TemplateView):
    """
    Mobile-first clock-in home screen for WBL learners.
    This is the PRIMARY landing page for learners - attendance is the hero action.
    """
    template_name = 'portals/student/wbl/attendance_home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = date.today()
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        # Get active workplace placement
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).select_related(
            'host', 'host__employer',
            'workplace_officer'
        ).first()
        
        context['placement'] = placement
        
        if not placement:
            context['no_placement'] = True
            return context
        
        # Today's attendance
        today_attendance = WorkplaceAttendance.objects.filter(
            placement=placement,
            date=today
        ).first()
        context['today_attendance'] = today_attendance
        
        # This month stats
        month_start = today.replace(day=1)
        days_present = WorkplaceAttendance.objects.filter(
            placement=placement,
            date__gte=month_start,
            attendance_type='PRESENT'
        ).count()
        context['days_present_this_month'] = days_present
        
        # Module completions
        context['total_modules_completed'] = WorkplaceModuleCompletion.objects.filter(
            placement=placement
        ).count()
        
        # Unread messages
        user_id_str = str(user.id)
        unread_messages = Message.objects.filter(
            thread__participants__user=user
        ).exclude(sender=user).exclude(
            read_by__has_key=user_id_str
        ).count()
        context['unread_messages'] = unread_messages
        
        context['today'] = today
        
        return context


class StudentWBLDashboardView(LoginRequiredMixin, TemplateView):
    """
    WBL Dashboard - Overview of workplace placement, attendance, and tasks.
    """
    template_name = 'portals/student/wbl/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = date.today()
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        # Get active workplace placement
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).select_related(
            'host', 'host__employer',
            'workplace_officer', 'lead_employer', 'leave_policy'
        ).first()
        
        context['placement'] = placement
        
        if not placement:
            context['no_placement'] = True
            return context
        
        # Current month attendance
        month_start = today.replace(day=1)
        current_attendance = WorkplaceAttendance.objects.filter(
            placement=placement,
            date__gte=month_start
        ).order_by('-date')
        
        # Attendance summary
        attendance_summary = {}
        for record in current_attendance:
            att_type = record.get_attendance_type_display()
            attendance_summary[att_type] = attendance_summary.get(att_type, 0) + 1
        
        context['attendance_summary'] = attendance_summary
        context['recent_attendance'] = current_attendance[:10]
        
        # Calculate days present this month
        days_present = current_attendance.filter(attendance_type='PRESENT').count()
        context['days_present_this_month'] = days_present
        
        # Pending logbook entries (not yet signed by learner or returned for revision)
        pending_logbooks = WorkplaceLogbookEntry.objects.filter(
            placement=placement,
            learner_signed=False
        ).order_by('-year', '-month')
        
        context['pending_logbooks'] = pending_logbooks
        
        # Module completions
        recent_modules = WorkplaceModuleCompletion.objects.filter(
            placement=placement
        ).order_by('-completed_date')[:5]
        
        context['recent_modules'] = recent_modules
        context['total_modules_completed'] = WorkplaceModuleCompletion.objects.filter(
            placement=placement
        ).count()
        
        # Stipend history
        stipends = StipendCalculation.objects.filter(
            placement=placement,
            status__in=['APPROVED', 'PAID']
        ).order_by('-year', '-month')[:3]
        
        context['recent_stipends'] = stipends
        
        # Unread messages (messages where user hasn't marked as read)
        user_id_str = str(user.id)
        unread_messages = Message.objects.filter(
            thread__participants__user=user
        ).exclude(sender=user).exclude(
            read_by__has_key=user_id_str
        ).count()
        
        context['unread_messages'] = unread_messages
        
        # Notifications
        notifications = Notification.objects.filter(
            user=user,
            is_read=False
        ).order_by('-created_at')[:5]
        
        context['notifications'] = notifications
        
        # Disciplinary status
        active_disciplinary = DisciplinaryRecord.objects.filter(
            learner=learner,
            placement=placement,
            status__in=['OPEN', 'INVESTIGATION', 'HEARING_SCHEDULED']
        ).exists()
        
        context['has_active_disciplinary'] = active_disciplinary
        
        # Pending disputes
        from learners.models import StipendDispute
        pending_disputes = StipendDispute.objects.filter(
            learner=learner,
            status__in=['PENDING', 'UNDER_REVIEW', 'ESCALATED']
        ).count()
        
        context['pending_disputes'] = pending_disputes
        context['today'] = today
        
        # Today's attendance for one-tap clock in/out
        today_attendance = WorkplaceAttendance.objects.filter(
            placement=placement,
            date=today
        ).first()
        context['today_attendance'] = today_attendance
        
        # Clock-out reminder: Show if clocked in but not out and it's after 4 PM
        from datetime import time as dt_time
        from datetime import datetime
        current_time = datetime.now().time()
        show_clockout_reminder = (
            today_attendance and 
            today_attendance.clock_in and 
            not today_attendance.clock_out and 
            current_time >= dt_time(16, 0)
        )
        context['show_clockout_reminder'] = show_clockout_reminder
        
        return context


class StudentAttendanceSubmitView(LoginRequiredMixin, TemplateView):
    """
    Enhanced attendance submission page with GPS, camera, and offline support.
    """
    template_name = 'portals/student/wbl/attendance_submit.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Always provide attendance types for the form
        context['attendance_types'] = WorkplaceAttendance.ATTENDANCE_TYPE_CHOICES
        context['today'] = date.today()
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).first()
        
        if not placement:
            context['no_active_placement'] = True
            return context
        
        context['placement'] = placement
        
        return context


class StudentAttendanceView(LoginRequiredMixin, TemplateView):
    """
    View and submit daily attendance records.
    Unified calendar view with monthly stats and quick submission.
    Integrates with DailyLogbookEntry for task tracking.
    """
    template_name = 'portals/student/wbl/attendance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = date.today()
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).first()
        
        if not placement:
            context['no_placement'] = True
            return context
        
        context['placement'] = placement
        
        # Get month from params or default to current
        year = int(self.request.GET.get('year', today.year))
        month = int(self.request.GET.get('month', today.month))
        
        # Build calendar
        _, days_in_month = monthrange(year, month)
        first_day = date(year, month, 1)
        
        # Get attendance for this month (from WorkplaceAttendance)
        attendance_records = WorkplaceAttendance.objects.filter(
            placement=placement,
            date__year=year,
            date__month=month
        ).order_by('-date')
        
        # Also get DailyLogbookEntry for cross-reference
        daily_entries = DailyLogbookEntry.objects.filter(
            placement=placement,
            entry_date__year=year,
            entry_date__month=month
        ).prefetch_related('task_completions')
        
        attendance_dict = {a.date: a for a in attendance_records}
        daily_entry_dict = {e.entry_date: e for e in daily_entries}
        
        # Build calendar days (Sunday = 0 start)
        calendar_days = []
        # Get first weekday (Python: Monday=0, we need Sunday=0)
        first_weekday = first_day.weekday()  # Monday = 0
        first_weekday_sunday = (first_weekday + 1) % 7  # Convert to Sunday = 0
        
        # Add empty slots for days before the 1st
        for _ in range(first_weekday_sunday):
            calendar_days.append({'date': None})
        
        for day in range(1, days_in_month + 1):
            d = date(year, month, day)
            att = attendance_dict.get(d)
            daily_entry = daily_entry_dict.get(d)
            
            # Determine status from attendance record
            status = None
            if att:
                att_type = att.attendance_type.upper()
                if att_type == 'PRESENT':
                    status = 'present'
                elif att_type == 'LATE':
                    status = 'late'
                elif att_type == 'ABSENT':
                    status = 'absent'
                elif att_type in ['ANNUAL', 'SICK', 'FAMILY', 'UNPAID']:
                    status = 'leave'
                elif att_type == 'PUBLIC_HOLIDAY':
                    status = 'holiday'
                else:
                    status = 'other'
            elif daily_entry:
                # Fallback to daily entry status if no attendance
                entry_status = daily_entry.attendance_status.upper()
                if entry_status == 'PRESENT':
                    status = 'present'
                elif entry_status in ['SICK_LEAVE', 'ANNUAL_LEAVE', 'STUDY_LEAVE']:
                    status = 'leave'
                elif entry_status == 'ABSENT':
                    status = 'absent'
                elif entry_status in ['LATE', 'EARLY_OUT']:
                    status = 'late'
            
            calendar_days.append({
                'date': d,
                'day': day,
                'is_weekend': d.weekday() >= 5,
                'is_today': d == today,
                'is_future': d > today,
                'status': status,
                'attendance': att,
                'daily_entry': daily_entry,
                'task_count': daily_entry.tasks_count if daily_entry else 0,
                'has_tasks': daily_entry and daily_entry.task_completions.exists() if daily_entry else False,
            })
        
        # Fill remaining slots to complete the week
        while len(calendar_days) % 7 != 0:
            calendar_days.append({'date': None})
        
        context['calendar_days'] = calendar_days
        context['year'] = year
        context['month'] = month
        context['month_name'] = first_day.strftime('%B')
        context['today'] = today
        
        # Navigation
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        
        context['prev_month'] = prev_month
        context['prev_year'] = prev_year
        context['next_month'] = next_month
        context['next_year'] = next_year
        context['can_go_next'] = date(next_year, next_month, 1) <= today
        
        # Available months for dropdown
        available_months = []
        start_month = placement.start_date.replace(day=1) if placement.start_date else date(today.year, 1, 1)
        current = start_month
        while current <= today:
            available_months.append({
                'value': f"{current.year}-{current.month:02d}",
                'label': current.strftime('%B %Y'),
                'year': current.year,
                'month': current.month,
            })
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        context['available_months'] = list(reversed(available_months))
        context['selected_month'] = f"{year}-{month:02d}"
        context['selected_month_label'] = first_day.strftime('%B %Y')
        
        # Stats calculation
        stats = {
            'present_days': 0,
            'late_days': 0,
            'absent_days': 0,
            'leave_days': 0,
            'total_hours': Decimal('0'),
            'tasks_completed': 0,
            'working_days': 0,
        }
        
        for record in attendance_records:
            att_type = record.attendance_type.upper()
            if att_type == 'PRESENT':
                stats['present_days'] += 1
            elif att_type == 'LATE':
                stats['late_days'] += 1
            elif att_type == 'ABSENT':
                stats['absent_days'] += 1
            elif att_type in ['ANNUAL', 'SICK', 'FAMILY', 'UNPAID']:
                stats['leave_days'] += 1
            
            if record.hours_worked:
                stats['total_hours'] += record.hours_worked
        
        for entry in daily_entries:
            stats['tasks_completed'] += entry.tasks_count
        
        # Calculate working days (exclude weekends, only count up to today)
        for day in range(1, days_in_month + 1):
            d = date(year, month, day)
            if d <= today and d.weekday() < 5:
                stats['working_days'] += 1
        
        # Attendance rate
        if stats['working_days'] > 0:
            attended = stats['present_days'] + stats['late_days'] + stats['leave_days']
            stats['attendance_rate'] = round((attended / stats['working_days']) * 100, 1)
        else:
            stats['attendance_rate'] = 0
        
        context['stats'] = stats
        context['attendance_records'] = attendance_records
        
        # Attendance types for form
        context['attendance_types'] = WorkplaceAttendance.ATTENDANCE_TYPE_CHOICES
        
        # Check if today's records exist
        context['today_attendance'] = attendance_dict.get(today)
        context['today_daily_entry'] = daily_entry_dict.get(today)
        
        return context


@login_required
@require_POST
def student_attendance_submit(request):
    """Submit attendance record with GPS and photo support (AJAX/Multipart endpoint)."""
    user = request.user
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    placement = WorkplacePlacement.objects.filter(
        learner=learner,
        status='ACTIVE'
    ).first()
    
    if not placement:
        return JsonResponse({'error': 'No active placement'}, status=403)
    
    # Handle both JSON and multipart form data
    if request.content_type and 'application/json' in request.content_type:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        data = request.POST
    
    entry_date = data.get('date')
    attendance_type = data.get('type')
    clock_in = data.get('clock_in')
    clock_out = data.get('clock_out')
    notes = data.get('notes', '')
    
    # Offline sync support
    client_uuid = data.get('client_uuid')
    offline_created = data.get('offline_created', 'false').lower() == 'true'
    
    # GPS coordinates
    gps_latitude = data.get('gps_latitude')
    gps_longitude = data.get('gps_longitude')
    gps_accuracy = data.get('gps_accuracy')
    gps_timestamp = data.get('gps_timestamp')
    
    try:
        entry_date = date.fromisoformat(entry_date)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid date'}, status=400)
    
    # Don't allow future dates (unless offline created)
    if not offline_created and entry_date > date.today():
        return JsonResponse({'error': 'Cannot submit attendance for future dates'}, status=400)
    
    # Calculate hours if times provided
    hours_worked = None
    if clock_in and clock_out:
        try:
            t_in = datetime.strptime(clock_in, '%H:%M')
            t_out = datetime.strptime(clock_out, '%H:%M')
            delta = t_out - t_in
            hours_worked = Decimal(str(delta.seconds / 3600))
        except ValueError:
            pass
    
    # Check for duplicate using client_uuid (offline deduplication)
    if client_uuid:
        existing = WorkplaceAttendance.objects.filter(
            client_uuid=client_uuid
        ).first()
        if existing:
            return JsonResponse({
                'success': True,
                'id': existing.id,
                'created': False,
                'duplicate': True,
                'message': 'Record already exists (offline sync deduplication)'
            })
    
    defaults = {
        'attendance_type': attendance_type,
        'clock_in': clock_in or None,
        'clock_out': clock_out or None,
        'hours_worked': hours_worked,
        'notes': notes,
        'offline_created': offline_created,
        'sync_status': 'SYNCED',
    }
    
    # Add GPS data if provided
    if gps_latitude and gps_longitude:
        defaults['gps_latitude'] = Decimal(gps_latitude)
        defaults['gps_longitude'] = Decimal(gps_longitude)
        if gps_accuracy:
            defaults['gps_accuracy'] = Decimal(gps_accuracy)
        if gps_timestamp:
            try:
                defaults['gps_timestamp'] = datetime.fromisoformat(gps_timestamp.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
    
    # Add client UUID if provided
    if client_uuid:
        import uuid
        try:
            defaults['client_uuid'] = uuid.UUID(client_uuid)
        except ValueError:
            pass
    
    obj, created = WorkplaceAttendance.objects.update_or_create(
        placement=placement,
        date=entry_date,
        defaults=defaults
    )
    
    # Handle photo upload if provided
    if 'photo' in request.FILES:
        obj.photo = request.FILES['photo']
        obj.save(update_fields=['photo'])
    
    # Auto-create or link DailyLogbookEntry on clock-in
    daily_entry = None
    daily_entry_created = False
    if clock_in:
        # Map attendance type to DailyLogbookEntry status
        status_mapping = {
            'PRESENT': 'PRESENT',
            'LATE': 'LATE',
            'ABSENT': 'ABSENT',
            'ANNUAL': 'ANNUAL_LEAVE',
            'SICK': 'SICK_LEAVE',
            'FAMILY': 'ANNUAL_LEAVE',
            'UNPAID': 'ANNUAL_LEAVE',
            'PUBLIC_HOLIDAY': 'PUBLIC_HOLIDAY',
        }
        entry_status = status_mapping.get(attendance_type, 'PRESENT')
        
        # Create or update DailyLogbookEntry linked to this attendance
        daily_entry, daily_entry_created = DailyLogbookEntry.objects.update_or_create(
            placement=placement,
            entry_date=entry_date,
            defaults={
                'attendance_record': obj,
                'attendance_status': entry_status,
                'clock_in': clock_in or None,
            }
        )
        
        # If entry already existed but wasn't linked, link it now
        if not daily_entry_created and not daily_entry.attendance_record:
            daily_entry.attendance_record = obj
            daily_entry.save(update_fields=['attendance_record'])
    
    # Also update clock_out on daily entry if provided
    if clock_out:
        daily_entry = DailyLogbookEntry.objects.filter(
            placement=placement,
            entry_date=entry_date
        ).first()
        if daily_entry:
            daily_entry.clock_out = clock_out
            daily_entry.save(update_fields=['clock_out'])
    
    return JsonResponse({
        'success': True,
        'id': obj.id,
        'created': created,
        'has_gps': bool(gps_latitude and gps_longitude),
        'has_photo': bool(obj.photo),
        'daily_entry_id': daily_entry.id if daily_entry else None,
        'daily_entry_created': daily_entry_created,
    })


class StudentLogbookView(LoginRequiredMixin, TemplateView):
    """
    View and manage monthly logbook entries.
    """
    template_name = 'portals/student/wbl/logbook_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return context
        
        context['learner'] = learner
        
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).first()
        
        if not placement:
            context['no_placement'] = True
            return context
        
        context['placement'] = placement
        
        # Get all logbook entries
        logbooks = WorkplaceLogbookEntry.objects.filter(
            placement=placement
        ).order_by('-year', '-month')
        
        context['logbooks'] = logbooks
        
        # Check if current month entry exists
        today = date.today()
        _, days_in_month = monthrange(today.year, today.month)
        current_month_end = date(today.year, today.month, days_in_month)
        
        current_exists = logbooks.filter(year=today.year, month=today.month).exists()
        context['can_create_current'] = not current_exists
        context['current_month_end'] = current_month_end
        
        return context


class StudentLogbookDetailView(LoginRequiredMixin, TemplateView):
    """
    View/edit a specific logbook entry.
    """
    template_name = 'portals/student/wbl/logbook_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logbook_id = self.kwargs.get('pk')
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return context
        
        context['learner'] = learner
        
        logbook = get_object_or_404(
            WorkplaceLogbookEntry.objects.select_related('placement'),
            id=logbook_id,
            placement__learner=learner
        )
        
        context['logbook'] = logbook
        context['placement'] = logbook.placement
        
        # Get attendance for this period
        month_start = logbook.month_end_date.replace(day=1)
        attendance = WorkplaceAttendance.objects.filter(
            placement=logbook.placement,
            date__gte=month_start,
            date__lte=logbook.month_end_date
        ).order_by('date')
        
        context['attendance'] = attendance
        
        # Attendance summary
        summary = {}
        for record in attendance:
            att_type = record.get_attendance_type_display()
            summary[att_type] = summary.get(att_type, 0) + 1
        
        context['attendance_summary'] = summary
        
        # Module completions for this period
        modules = WorkplaceModuleCompletion.objects.filter(
            placement=logbook.placement,
            completed_date__gte=month_start,
            completed_date__lte=logbook.month_end_date
        )
        
        context['modules'] = modules
        
        # Can edit if draft or returned
        context['can_edit'] = logbook.status in ['DRAFT', 'RETURNED']
        
        return context


@login_required
@require_POST
def student_logbook_create(request):
    """Create a new logbook entry."""
    user = request.user
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    placement = WorkplacePlacement.objects.filter(
        learner=learner,
        status='ACTIVE'
    ).first()
    
    if not placement:
        return JsonResponse({'error': 'No active placement'}, status=403)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    month_end = data.get('month_end_date')
    
    try:
        month_end = date.fromisoformat(month_end)
    except (ValueError, TypeError):
        # Default to end of current month
        today = date.today()
        _, days_in_month = monthrange(today.year, today.month)
        month_end = date(today.year, today.month, days_in_month)
    
    # Check if already exists
    if WorkplaceLogbookEntry.objects.filter(
        placement=placement,
        year=month_end.year,
        month=month_end.month
    ).exists():
        return JsonResponse({'error': 'Logbook for this month already exists'}, status=400)
    
    logbook = WorkplaceLogbookEntry.objects.create(
        placement=placement,
        month=month_end.month,
        year=month_end.year,
        learning_outcomes=data.get('learning_summary', ''),
        tasks_completed=data.get('tasks_performed', []),
        challenges_faced=data.get('challenges_faced', ''),
        skills_developed=data.get('skills_developed', ''),
        learner_signed=False,
    )
    
    return JsonResponse({
        'success': True,
        'id': logbook.id,
    })


@login_required
@require_POST
def student_logbook_update(request, logbook_id):
    """Update a logbook entry."""
    user = request.user
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    logbook = get_object_or_404(
        WorkplaceLogbookEntry,
        id=logbook_id,
        placement__learner=learner
    )
    
    if logbook.status not in ['DRAFT', 'RETURNED']:
        return JsonResponse({'error': 'Cannot edit submitted logbook'}, status=403)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    logbook.learning_summary = data.get('learning_summary', logbook.learning_summary)
    logbook.tasks_performed = data.get('tasks_performed', logbook.tasks_performed)
    logbook.challenges_faced = data.get('challenges_faced', logbook.challenges_faced)
    logbook.skills_developed = data.get('skills_developed', logbook.skills_developed)
    
    # Submit for approval
    if data.get('submit'):
        logbook.status = 'SUBMITTED'
        logbook.submitted_at = timezone.now()
        
        # Notify mentor
        if logbook.placement.host and logbook.placement.host.user:
            from core.services.notifications import NotificationService
            NotificationService.send_notification(
                user=logbook.placement.host.user,
                title="Logbook Submitted for Review",
                message=f"{learner.get_full_name()} has submitted their logbook for {logbook.month_end_date.strftime('%B %Y')}.",
                notification_type='LOGBOOK',
                related_object=logbook,
                campus=logbook.placement.campus
            )
    
    logbook.save()
    
    return JsonResponse({
        'success': True,
        'status': logbook.status,
    })


class StudentMessagesView(LoginRequiredMixin, TemplateView):
    """
    View message threads with mentor and workplace officer.
    """
    template_name = 'portals/student/wbl/messages.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return context
        
        context['learner'] = learner
        
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).select_related('host', 'workplace_officer').first()
        
        context['placement'] = placement
        
        # Get message threads
        threads = MessageThread.objects.filter(
            participants__user=user
        ).order_by('-updated_at')
        
        user_id_str = str(user.id)
        for thread in threads:
            thread.unread_count = Message.objects.filter(
                thread=thread
            ).exclude(sender=user).exclude(
                read_by__has_key=user_id_str
            ).count()
        
        context['threads'] = threads
        
        return context


class StudentMessageThreadView(LoginRequiredMixin, TemplateView):
    """
    View a specific message thread.
    """
    template_name = 'portals/student/wbl/message_thread.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thread_id = self.kwargs.get('pk')
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return context
        
        context['learner'] = learner
        
        thread = get_object_or_404(
            MessageThread,
            id=thread_id,
            participants__user=user
        )
        
        # Mark as read using the model's method
        user_id_str = str(user.id)
        unread_msgs = Message.objects.filter(
            thread=thread
        ).exclude(sender=user).exclude(
            read_by__has_key=user_id_str
        )
        for msg in unread_msgs:
            msg.mark_read_by(user)
        
        context['thread'] = thread
        context['messages'] = Message.objects.filter(thread=thread).order_by('created_at')
        context['participants'] = thread.participants.select_related('user')
        
        return context


@login_required
@require_POST
def student_message_send(request, thread_id):
    """Send a message in a thread."""
    user = request.user
    
    thread = get_object_or_404(
        MessageThread,
        id=thread_id,
        participants__user=user
    )
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    content = data.get('content', '').strip()
    
    if not content:
        return JsonResponse({'error': 'Content required'}, status=400)
    
    message = Message.objects.create(
        thread=thread,
        sender=user,
        content=content,
    )
    
    thread.updated_at = timezone.now()
    thread.save()
    
    # Notify other participants
    from core.services.notifications import NotificationService
    for participant in thread.participants.exclude(user=user):
        NotificationService.trigger_message_received(
            message=message,
            recipient=participant.user
        )
    
    return JsonResponse({
        'success': True,
        'message_id': message.id,
    })


@login_required
def student_new_message(request):
    """Start a new message thread."""
    user = request.user
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    placement = WorkplacePlacement.objects.filter(
        learner=learner,
        status='ACTIVE'
    ).first()
    
    if not placement:
        return JsonResponse({'error': 'No active placement'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        recipient_type = data.get('recipient_type')  # 'mentor' or 'officer'
        subject = data.get('subject', '')
        content = data.get('content', '').strip()
        
        if not content:
            return JsonResponse({'error': 'Content required'}, status=400)
        
        # Determine recipient
        recipient = None
        if recipient_type == 'mentor' and placement.host and placement.host.user:
            recipient = placement.host.user
        elif recipient_type == 'officer' and placement.workplace_officer:
            recipient = placement.workplace_officer
        
        if not recipient:
            return JsonResponse({'error': 'Recipient not available'}, status=400)
        
        with transaction.atomic():
            thread = MessageThread.objects.create(
                subject=subject or f"Message from {learner.get_full_name()}",
                thread_type='LEARNER_SUPPORT',
                related_placement=placement,
            )
            
            ThreadParticipant.objects.create(
                thread=thread,
                user=user,
                role='LEARNER'
            )
            
            ThreadParticipant.objects.create(
                thread=thread,
                user=recipient,
                role='MENTOR' if recipient_type == 'mentor' else 'OFFICER'
            )
            
            message = Message.objects.create(
                thread=thread,
                sender=user,
                content=content,
            )
        
        # Notify recipient
        from core.services.notifications import NotificationService
        NotificationService.trigger_message_received(message, recipient)
        
        return JsonResponse({
            'success': True,
            'thread_id': thread.id,
        })
    
    # GET - return potential recipients
    recipients = []
    
    if placement.host and placement.host.user:
        recipients.append({
            'type': 'mentor',
            'name': placement.host.contact.get_full_name() if placement.host.contact else 'Your Mentor',
            'available': True,
        })
    
    if placement.workplace_officer:
        recipients.append({
            'type': 'officer',
            'name': placement.workplace_officer.get_full_name(),
            'available': True,
        })
    
    return JsonResponse({'recipients': recipients})


class StudentStipendHistoryView(LoginRequiredMixin, TemplateView):
    """
    View stipend payment history.
    """
    template_name = 'portals/student/wbl/stipend_history.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return context
        
        context['learner'] = learner
        
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).first()
        
        if not placement:
            context['no_placement'] = True
            return context
        
        context['placement'] = placement
        
        # Get all stipend calculations
        stipends = StipendCalculation.objects.filter(
            placement=placement
        ).order_by('-year', '-month')
        
        context['stipends'] = stipends
        
        # Total earned
        total = stipends.filter(status__in=['APPROVED', 'PAID']).aggregate(
            total=Sum('net_amount')
        )
        
        context['total_earned'] = total['total'] or Decimal('0')
        
        return context


class StudentStipendDetailView(LoginRequiredMixin, TemplateView):
    """
    View detailed stipend breakdown.
    """
    template_name = 'portals/student/wbl/stipend_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stipend_id = self.kwargs.get('pk')
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return context
        
        context['learner'] = learner
        
        stipend = get_object_or_404(
            StipendCalculation.objects.select_related('placement'),
            id=stipend_id,
            placement__learner=learner
        )
        
        context['stipend'] = stipend
        
        # Check for active dispute
        from learners.models import StipendDispute
        active_dispute = StipendDispute.objects.filter(
            stipend_calculation=stipend,
            learner=learner,
            status__in=['PENDING', 'UNDER_REVIEW', 'ESCALATED']
        ).first()
        context['active_dispute'] = active_dispute
        
        # Get attendance for this period
        month_start = date(stipend.year, stipend.month, 1)
        _, days_in_month = monthrange(stipend.year, stipend.month)
        month_end = date(stipend.year, stipend.month, days_in_month)
        
        attendance = WorkplaceAttendance.objects.filter(
            placement=stipend.placement,
            date__gte=month_start,
            date__lte=month_end
        ).order_by('date')
        
        context['attendance'] = attendance
        
        return context


# API endpoints for offline sync

@login_required
def student_wbl_sync(request):
    """
    Sync endpoint for offline WBL data.
    Returns current placement, recent attendance, etc.
    """
    user = request.user
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    placement = WorkplacePlacement.objects.filter(
        learner=learner,
        status='ACTIVE'
    ).select_related('host', 'host__employer').first()
    
    if not placement:
        return JsonResponse({'error': 'No active placement'}, status=404)
    
    today = date.today()
    month_start = today.replace(day=1)
    
    # Get current month attendance
    attendance = WorkplaceAttendance.objects.filter(
        placement=placement,
        date__gte=month_start
    ).order_by('date')
    
    attendance_data = [
        {
            'id': a.id,
            'date': a.date.isoformat(),
            'type': a.attendance_type,
            'time_in': str(a.time_in) if a.time_in else None,
            'time_out': str(a.time_out) if a.time_out else None,
            'hours': str(a.hours_worked) if a.hours_worked else None,
            'notes': a.notes,
        }
        for a in attendance
    ]
    
    return JsonResponse({
        'placement': {
            'id': placement.id,
            'host_employer': placement.host.employer.company_name if placement.host else None,
            'mentor_name': placement.host.contact.get_full_name() if placement.host and placement.host.contact else None,
            'start_date': placement.start_date.isoformat() if placement.start_date else None,
            'end_date': placement.end_date.isoformat() if placement.end_date else None,
        },
        'attendance': attendance_data,
        'attendance_types': [
            {'value': code, 'label': label}
            for code, label in WorkplaceAttendance.ATTENDANCE_TYPES
        ],
        'synced_at': timezone.now().isoformat(),
    })


# ==================== Calendar Views ====================

class StudentCalendarView(LoginRequiredMixin, TemplateView):
    """
    Unified calendar view showing attendance, stipend payments, logbooks, and assessments
    """
    template_name = 'portals/student/calendar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        # Get active placement for WBL
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).select_related('host', 'mentor', 'leave_policy').first()
        
        context['placement'] = placement
        
        # Get active enrollments for assessments
        enrollments = Enrollment.objects.filter(
            learner=learner,
            status__in=['ACTIVE', 'ENROLLED']
        ).select_related('qualification', 'cohort')
        
        context['enrollments'] = enrollments
        
        return context


@login_required
def calendar_events_api(request):
    """
    API endpoint for calendar events (FullCalendar.js compatible)
    Returns attendance, stipends, logbooks, and assessment due dates
    """
    user = request.user
    learner = Learner.objects.filter(user=user).first()
    
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    # Get date range from query params
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    if start_date and end_date:
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00')).date()
        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
    else:
        # Default to current month +/- 1 month
        today = date.today()
        start_date = (today.replace(day=1) - timedelta(days=30))
        end_date = (today.replace(day=1) + timedelta(days=60))
    
    events = []
    
    # Get workplace attendance
    placement = WorkplacePlacement.objects.filter(
        learner=learner,
        status='ACTIVE'
    ).first()
    
    if placement:
        attendance_records = WorkplaceAttendance.objects.filter(
            placement=placement,
            date__gte=start_date,
            date__lte=end_date
        ).select_related('verified_by')
        
        for att in attendance_records:
            # Color code by attendance type
            color_map = {
                'PRESENT': '#10b981',  # Green
                'ABSENT': '#ef4444',   # Red
                'SICK': '#f59e0b',     # Amber
                'ANNUAL': '#3b82f6',   # Blue
                'FAMILY': '#8b5cf6',   # Purple
                'UNPAID': '#6b7280',   # Gray
                'PUBLIC_HOLIDAY': '#06b6d4',  # Cyan
                'SUSPENDED': '#dc2626', # Dark red
            }
            
            events.append({
                'id': f'att-{att.id}',
                'title': att.get_attendance_type_display(),
                'start': att.date.isoformat(),
                'allDay': True,
                'backgroundColor': color_map.get(att.attendance_type, '#6b7280'),
                'borderColor': color_map.get(att.attendance_type, '#6b7280'),
                'extendedProps': {
                    'type': 'attendance',
                    'attendance_type': att.attendance_type,
                    'verified': att.verified_by is not None,
                    'time_in': str(att.time_in) if att.time_in else None,
                    'time_out': str(att.time_out) if att.time_out else None,
                }
            })
        
        # Get stipend payment dates
        stipends = StipendCalculation.objects.filter(
            placement=placement,
            payment_date__gte=start_date,
            payment_date__lte=end_date
        )
        
        for stipend in stipends:
            status_colors = {
                'DRAFT': '#9ca3af',
                'CALCULATED': '#f59e0b',
                'VERIFIED': '#3b82f6',
                'APPROVED': '#10b981',
                'PAID': '#22c55e',
                'DISPUTED': '#ef4444',
            }
            
            events.append({
                'id': f'stipend-{stipend.id}',
                'title': f'Stipend Payment: R{stipend.net_amount}',
                'start': stipend.payment_date.isoformat(),
                'allDay': True,
                'backgroundColor': status_colors.get(stipend.status, '#6b7280'),
                'borderColor': status_colors.get(stipend.status, '#6b7280'),
                'extendedProps': {
                    'type': 'stipend',
                    'amount': str(stipend.net_amount),
                    'status': stipend.status,
                    'month': stipend.month,
                    'year': stipend.year,
                }
            })
        
        # Get logbook due dates
        logbooks = WorkplaceLogbookEntry.objects.filter(
            placement=placement,
            month__gte=start_date.month,
            year__gte=start_date.year,
            month__lte=end_date.month,
            year__lte=end_date.year
        )
        
        for logbook in logbooks:
            # Logbook is due end of the month
            due_date = date(logbook.year, logbook.month, monthrange(logbook.year, logbook.month)[1])
            
            is_signed = (logbook.learner_signed_at and 
                        logbook.mentor_signed_at and 
                        logbook.facilitator_signed_at)
            
            events.append({
                'id': f'logbook-{logbook.id}',
                'title': f'Logbook Due: {logbook.get_month_name()}',
                'start': due_date.isoformat(),
                'allDay': True,
                'backgroundColor': '#22c55e' if is_signed else '#f59e0b',
                'borderColor': '#22c55e' if is_signed else '#f59e0b',
                'extendedProps': {
                    'type': 'logbook',
                    'month': logbook.month,
                    'year': logbook.year,
                    'signed': is_signed,
                }
            })
    
    # Get assessment due dates
    enrollments = Enrollment.objects.filter(
        learner=learner,
        status__in=['ACTIVE', 'ENROLLED']
    )
    
    for enrollment in enrollments:
        assessments = AssessmentActivity.objects.filter(
            module__qualification=enrollment.qualification,
            due_date__gte=start_date,
            due_date__lte=end_date,
            is_active=True
        ).select_related('module')
        
        for assessment in assessments:
            # Check if already completed
            result = AssessmentResult.objects.filter(
                enrollment=enrollment,
                activity=assessment,
                result='C'
            ).first()
            
            events.append({
                'id': f'assessment-{assessment.id}',
                'title': f'{assessment.module.code}: {assessment.title}',
                'start': assessment.due_date.isoformat(),
                'allDay': True,
                'backgroundColor': '#10b981' if result else '#8b5cf6',
                'borderColor': '#10b981' if result else '#8b5cf6',
                'extendedProps': {
                    'type': 'assessment',
                    'module': assessment.module.code,
                    'assessment_type': assessment.activity_type,
                    'completed': result is not None,
                }
            })
    
    return JsonResponse(events, safe=False)


# ==================== Stipend Dashboard Views ====================

class StudentStipendDashboardView(LoginRequiredMixin, TemplateView):
    """
    Enhanced stipend dashboard with transparent calculations and predictions
    """
    template_name = 'portals/student/wbl/stipend_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        # Get active placement
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).select_related('host', 'mentor', 'leave_policy').first()
        
        if not placement:
            context['no_active_placement'] = True
            return context
        
        context['placement'] = placement
        
        # Get current month calculation
        today = date.today()
        current_calculation = StipendCalculation.objects.filter(
            placement=placement,
            month=today.month,
            year=today.year
        ).first()
        
        context['current_calculation'] = current_calculation
        
        # Get last 6 months for historical comparison
        historical_stipends = StipendCalculation.objects.filter(
            placement=placement,
            status='PAID'
        ).order_by('-year', '-month')[:6]
        
        context['historical_stipends'] = historical_stipends
        
        # Calculate current month attendance summary
        month_start = today.replace(day=1)
        month_attendance = WorkplaceAttendance.objects.filter(
            placement=placement,
            date__gte=month_start,
            date__lte=today
        )
        
        attendance_summary = {
            'present': month_attendance.filter(attendance_type='PRESENT').count(),
            'sick': month_attendance.filter(attendance_type='SICK').count(),
            'annual': month_attendance.filter(attendance_type='ANNUAL').count(),
            'family': month_attendance.filter(attendance_type='FAMILY').count(),
            'absent': month_attendance.filter(attendance_type='ABSENT').count(),
            'unpaid': month_attendance.filter(attendance_type='UNPAID').count(),
        }
        
        context['attendance_summary'] = attendance_summary
        
        # Calculate working days in current month (excluding public holidays)
        total_days_in_month = monthrange(today.year, today.month)[1]
        public_holidays = month_attendance.filter(attendance_type='PUBLIC_HOLIDAY').count()
        total_working_days = total_days_in_month - public_holidays
        
        context['total_working_days'] = total_working_days
        context['days_elapsed'] = today.day
        context['days_remaining'] = total_days_in_month - today.day
        
        # Calculate daily rate if stipend amount is set
        if placement.stipend_amount and total_working_days > 0:
            daily_rate = placement.stipend_amount / total_working_days
            context['daily_rate'] = daily_rate
        else:
            context['daily_rate'] = 0
        
        # Get leave policy details
        if placement.leave_policy:
            context['leave_policy'] = {
                'annual_days': placement.leave_policy.annual_leave_days,
                'sick_days': placement.leave_policy.sick_leave_days,
                'family_days': placement.leave_policy.family_leave_days,
            }
        
        # Check for disputes
        from learners.models import StipendDispute
        active_disputes = StipendDispute.objects.filter(
            learner=learner,
            status__in=['PENDING', 'UNDER_REVIEW', 'ESCALATED']
        ).select_related('stipend_calculation')
        
        context['active_disputes'] = active_disputes
        
        return context


@login_required
def stipend_calculate_preview(request):
    """
    Calculate preview of stipend based on current attendance
    Returns real-time calculation for current month
    """
    user = request.user
    learner = Learner.objects.filter(user=user).first()
    
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    placement = WorkplacePlacement.objects.filter(
        learner=learner,
        status='ACTIVE'
    ).first()
    
    if not placement:
        return JsonResponse({'error': 'No active placement'}, status=404)
    
    # Use the StipendCalculator service
    from learners.services.stipend_calculator import StipendCalculator
    
    today = date.today()
    calculator = StipendCalculator()
    
    try:
        result = calculator.calculate_for_placement(
            placement=placement,
            month=today.month,
            year=today.year,
            preview=True  # Don't save, just calculate
        )
        
        return JsonResponse({
            'success': True,
            'calculation': {
                'base_amount': str(result['base_amount']),
                'daily_rate': str(result['daily_rate']),
                'total_billable_days': result['total_billable_days'],
                'present_days': result['present_days'],
                'sick_days_paid': result['sick_days_paid'],
                'annual_days_paid': result['annual_days_paid'],
                'family_days': result['family_days'],
                'absent_days': result['absent_days'],
                'deductions': str(result['deductions']),
                'net_amount': str(result['net_amount']),
                'breakdown': result.get('breakdown', []),
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def stipend_what_if_calculator(request):
    """
    What-if calculator for predicting stipend with future absences
    """
    user = request.user
    learner = Learner.objects.filter(user=user).first()
    
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    placement = WorkplacePlacement.objects.filter(
        learner=learner,
        status='ACTIVE'
    ).first()
    
    if not placement:
        return JsonResponse({'error': 'No active placement'}, status=404)
    
    # Get what-if parameters
    future_absent = int(request.GET.get('absent', 0))
    future_sick = int(request.GET.get('sick', 0))
    future_family = int(request.GET.get('family', 0))
    
    # Get current month attendance
    today = date.today()
    month_start = today.replace(day=1)
    
    current_attendance = WorkplaceAttendance.objects.filter(
        placement=placement,
        date__gte=month_start,
        date__lte=today
    )
    
    # Calculate current totals
    current_absent = current_attendance.filter(attendance_type='ABSENT').count()
    current_sick = current_attendance.filter(attendance_type='SICK').count()
    current_family = current_attendance.filter(attendance_type='FAMILY').count()
    
    # Calculate working days
    total_days_in_month = monthrange(today.year, today.month)[1]
    public_holidays = current_attendance.filter(attendance_type='PUBLIC_HOLIDAY').count()
    total_working_days = total_days_in_month - public_holidays
    
    # Calculate projected totals
    projected_absent = current_absent + future_absent
    projected_sick = current_sick + future_sick
    projected_family = current_family + future_family
    
    # Calculate deductions
    if placement.stipend_amount and total_working_days > 0:
        daily_rate = placement.stipend_amount / total_working_days
        
        # Check leave policy for paid days
        sick_paid = 0
        family_paid = 0
        
        if placement.leave_policy:
            # Pro-rate annual allowances
            months_worked = (today - placement.start_date).days / 30 if placement.start_date else 1
            sick_allowance = (placement.leave_policy.sick_leave_days / 12) * months_worked
            
            sick_paid = min(projected_sick, int(sick_allowance))
            # Family leave typically unpaid
        
        # Calculate deductions
        absent_deduction = projected_absent * daily_rate
        sick_deduction = max(0, (projected_sick - sick_paid)) * daily_rate
        family_deduction = projected_family * daily_rate
        
        total_deduction = absent_deduction + sick_deduction + family_deduction
        projected_net = placement.stipend_amount - total_deduction
        
        # Calculate percentage of base
        percentage = (projected_net / placement.stipend_amount * 100) if placement.stipend_amount > 0 else 0
        
        return JsonResponse({
            'success': True,
            'projection': {
                'base_amount': str(placement.stipend_amount),
                'daily_rate': str(daily_rate),
                'total_working_days': total_working_days,
                'current': {
                    'absent': current_absent,
                    'sick': current_sick,
                    'family': current_family,
                },
                'projected': {
                    'absent': projected_absent,
                    'sick': projected_sick,
                    'family': projected_family,
                    'sick_paid': sick_paid,
                },
                'deductions': {
                    'absent': str(absent_deduction),
                    'sick_unpaid': str(sick_deduction),
                    'family': str(family_deduction),
                    'total': str(total_deduction),
                },
                'projected_net': str(projected_net),
                'percentage_of_base': round(percentage, 1),
                'warning_level': 'red' if percentage < 70 else ('amber' if percentage < 90 else 'green'),
            }
        })
    else:
        return JsonResponse({'error': 'Stipend amount not configured'}, status=400)


# =============================================================================
# DAILY ENTRY & TASK COMPLETION VIEWS (Enhanced WBL Evidence Capture)
# =============================================================================

class StudentDailyEntryListView(LoginRequiredMixin, TemplateView):
    """
    Calendar/list view of daily logbook entries.
    Shows all daily entries with task counts and sign-off status.
    """
    template_name = 'portals/student/wbl/daily_entry_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).first()
        
        if not placement:
            context['no_placement'] = True
            return context
        
        context['placement'] = placement
        
        # Get filter parameters
        month = self.request.GET.get('month')
        year = self.request.GET.get('year')
        
        today = date.today()
        if not year:
            year = today.year
        else:
            year = int(year)
        if not month:
            month = today.month
        else:
            month = int(month)
        
        context['selected_month'] = month
        context['selected_year'] = year
        
        # Get entries for the selected month
        entries = DailyLogbookEntry.objects.filter(
            placement=placement,
            entry_date__year=year,
            entry_date__month=month
        ).prefetch_related('task_completions').order_by('-entry_date')
        
        context['entries'] = entries
        
        # Monthly summary
        from learners.models import DailyLogbookEntry as DLE
        context['monthly_summary'] = DLE.get_monthly_summary(placement, year, month)
        
        # Calendar data for navigation
        context['months'] = [
            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
        ]
        context['years'] = range(today.year - 2, today.year + 1)
        
        # Can create today's entry?
        today_entry = DailyLogbookEntry.objects.filter(
            placement=placement,
            entry_date=today
        ).first()
        context['today_entry'] = today_entry
        context['can_create_today'] = today_entry is None
        
        return context


class StudentDailyEntryCreateView(LoginRequiredMixin, TemplateView):
    """
    Create a new daily entry with multiple tasks and evidence.
    Mobile-friendly form with photo capture capability.
    """
    template_name = 'portals/student/wbl/daily_entry_create.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).first()
        
        if not placement:
            context['no_placement'] = True
            return context
        
        context['placement'] = placement
        context['today'] = date.today()
        
        # Check if today's entry already exists
        today_entry = DailyLogbookEntry.objects.filter(
            placement=placement,
            entry_date=date.today()
        ).first()
        
        if today_entry:
            context['existing_entry'] = today_entry
            context['entry_exists'] = True
        
        # Get available workplace modules for the learner's qualification
        enrollment = Enrollment.objects.filter(
            learner=learner,
            status__in=['ACTIVE', 'ENROLLED', 'REGISTERED']
        ).select_related('qualification').first()
        
        if enrollment:
            # Get workplace module outcomes for dropdown
            workplace_outcomes = WorkplaceModuleOutcome.objects.filter(
                module__qualification=enrollment.qualification,
                module__module_type='W',
                is_active=True
            ).select_related('module').order_by('module__code', 'outcome_number')
            
            context['workplace_outcomes'] = workplace_outcomes
            
            # Group outcomes by module for easier selection
            grouped_outcomes = {}
            for outcome in workplace_outcomes:
                module_code = outcome.module.code
                if module_code not in grouped_outcomes:
                    grouped_outcomes[module_code] = {
                        'module': outcome.module,
                        'outcomes': []
                    }
                grouped_outcomes[module_code]['outcomes'].append(outcome)
            
            context['grouped_outcomes'] = grouped_outcomes
        
        # Attendance status choices
        context['attendance_choices'] = DailyLogbookEntry.ATTENDANCE_STATUS_CHOICES
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle creation of a new daily entry"""
        user = request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            return JsonResponse({'error': 'No learner profile'}, status=403)
        
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).first()
        
        if not placement:
            return JsonResponse({'error': 'No active placement'}, status=403)
        
        # Parse form data
        entry_date = request.POST.get('entry_date', date.today().isoformat())
        try:
            entry_date = date.fromisoformat(entry_date)
        except (ValueError, TypeError):
            entry_date = date.today()
        
        # Don't allow future dates
        if entry_date > date.today():
            return JsonResponse({'error': 'Cannot create entry for future dates'}, status=400)
        
        # Check if entry already exists
        existing = DailyLogbookEntry.objects.filter(
            placement=placement,
            entry_date=entry_date
        ).first()
        
        if existing:
            return JsonResponse({
                'error': 'Entry already exists for this date',
                'entry_id': existing.id
            }, status=400)
        
        # Get form data
        attendance_status = request.POST.get('attendance_status', 'PRESENT')
        clock_in = request.POST.get('clock_in')
        clock_out = request.POST.get('clock_out')
        daily_summary = request.POST.get('daily_summary', '')
        
        # Create the entry
        with transaction.atomic():
            entry = DailyLogbookEntry.objects.create(
                placement=placement,
                entry_date=entry_date,
                attendance_status=attendance_status,
                clock_in=clock_in if clock_in else None,
                clock_out=clock_out if clock_out else None,
                daily_summary=daily_summary,
                learner_signed=False,
                mentor_signed=False
            )
        
        # Redirect to the detail page to add tasks
        return redirect('portals:student_daily_entry_detail', pk=entry.id)


class StudentDailyEntryDetailView(LoginRequiredMixin, TemplateView):
    """
    View and add tasks to a daily entry.
    Shows all completed tasks with their evidence photos.
    """
    template_name = 'portals/student/wbl/daily_entry_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entry_id = self.kwargs.get('pk')
        user = self.request.user
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        entry = get_object_or_404(
            DailyLogbookEntry.objects.select_related('placement'),
            id=entry_id,
            placement__learner=learner
        )
        
        context['entry'] = entry
        context['placement'] = entry.placement
        
        # Get all tasks for this entry
        tasks = entry.task_completions.select_related('workplace_outcome', 'workplace_outcome__module').order_by('created_at')
        context['tasks'] = tasks
        context['task_count'] = tasks.count()
        
        # Calculate total hours from tasks
        total_task_hours = sum(t.hours_spent for t in tasks)
        context['total_task_hours'] = total_task_hours
        
        # Can edit if not signed off
        context['can_edit'] = not entry.learner_signed
        context['can_add_tasks'] = not entry.learner_signed
        
        # Get workplace outcomes for dropdown (same logic as create view)
        enrollment = Enrollment.objects.filter(
            learner=learner,
            status__in=['ACTIVE', 'ENROLLED', 'REGISTERED']
        ).select_related('qualification').first()
        
        if enrollment:
            workplace_outcomes = WorkplaceModuleOutcome.objects.filter(
                module__qualification=enrollment.qualification,
                module__module_type='W',
                is_active=True
            ).select_related('module').order_by('module__code', 'outcome_number')
            
            context['workplace_outcomes'] = workplace_outcomes
            
            # Group outcomes by module
            grouped_outcomes = {}
            for outcome in workplace_outcomes:
                module_code = outcome.module.code
                if module_code not in grouped_outcomes:
                    grouped_outcomes[module_code] = {
                        'module': outcome.module,
                        'outcomes': []
                    }
                grouped_outcomes[module_code]['outcomes'].append(outcome)
            
            context['grouped_outcomes'] = grouped_outcomes
        
        return context


@login_required
@require_POST
def student_add_task(request, entry_id):
    """
    Add a task completion with evidence to a daily entry.
    Supports photo upload for evidence.
    """
    user = request.user
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    entry = get_object_or_404(
        DailyLogbookEntry,
        id=entry_id,
        placement__learner=learner
    )
    
    # Can't add tasks to signed entries
    if entry.learner_signed:
        return JsonResponse({'error': 'Cannot modify signed entry'}, status=403)
    
    # Get task data
    outcome_id = request.POST.get('outcome_id')
    task_description = request.POST.get('task_description', '')
    hours_spent = request.POST.get('hours_spent', '1.0')
    evidence_notes = request.POST.get('evidence_notes', '')
    
    if not task_description:
        return JsonResponse({'error': 'Task description is required'}, status=400)
    
    try:
        hours_spent = Decimal(hours_spent)
    except (ValueError, TypeError):
        hours_spent = Decimal('1.0')
    
    # Get workplace outcome if provided
    workplace_outcome = None
    if outcome_id:
        try:
            workplace_outcome = WorkplaceModuleOutcome.objects.get(id=outcome_id)
        except WorkplaceModuleOutcome.DoesNotExist:
            pass
    
    # Create the task
    task = DailyTaskCompletion.objects.create(
        daily_entry=entry,
        workplace_outcome=workplace_outcome,
        task_description=task_description,
        hours_spent=hours_spent,
        evidence_notes=evidence_notes
    )
    
    # Handle evidence file upload
    if 'evidence_file' in request.FILES:
        task.evidence_file = request.FILES['evidence_file']
        task.save(update_fields=['evidence_file'])
    
    # Return task data
    response_data = {
        'success': True,
        'task_id': task.id,
        'task': {
            'id': task.id,
            'description': task.task_description,
            'hours_spent': str(task.hours_spent),
            'outcome_code': task.outcome_code,
            'has_evidence': bool(task.evidence_file),
            'evidence_url': task.evidence_file.url if task.evidence_file else None,
        }
    }
    
    return JsonResponse(response_data)


@login_required
@require_POST
def student_delete_task(request, entry_id, task_id):
    """Delete a task from a daily entry."""
    user = request.user
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    entry = get_object_or_404(
        DailyLogbookEntry,
        id=entry_id,
        placement__learner=learner
    )
    
    if entry.learner_signed:
        return JsonResponse({'error': 'Cannot modify signed entry'}, status=403)
    
    task = get_object_or_404(DailyTaskCompletion, id=task_id, daily_entry=entry)
    task.delete()
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def student_sign_daily_entry(request, entry_id):
    """
    Sign off on a daily entry (learner signature).
    Marks the entry as complete from the learner's side.
    """
    user = request.user
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    entry = get_object_or_404(
        DailyLogbookEntry,
        id=entry_id,
        placement__learner=learner
    )
    
    if entry.learner_signed:
        return JsonResponse({'error': 'Already signed'}, status=400)
    
    # Require at least one task for sign-off
    if not entry.task_completions.exists():
        return JsonResponse({'error': 'Add at least one task before signing'}, status=400)
    
    entry.learner_signed = True
    entry.learner_signed_at = timezone.now()
    entry.save(update_fields=['learner_signed', 'learner_signed_at'])
    
    # Notify mentor if exists
    if entry.placement.host and entry.placement.host.user:
        from core.services.notifications import NotificationService
        NotificationService.send_notification(
            user=entry.placement.host.user,
            title="Daily Entry Signed",
            message=f"{learner.get_full_name()} has signed their daily entry for {entry.entry_date.strftime('%d %B %Y')}.",
            notification_type='LOGBOOK',
        )
    
    return JsonResponse({
        'success': True,
        'signed_at': entry.learner_signed_at.isoformat() if entry.learner_signed_at else None
    })


@login_required
@require_POST
def student_update_daily_entry(request, entry_id):
    """Update daily entry details (summary, times, attendance status)."""
    user = request.user
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    entry = get_object_or_404(
        DailyLogbookEntry,
        id=entry_id,
        placement__learner=learner
    )
    
    if entry.learner_signed:
        return JsonResponse({'error': 'Cannot modify signed entry'}, status=403)
    
    # Get update data
    data = request.POST
    
    if 'attendance_status' in data:
        entry.attendance_status = data['attendance_status']
    if 'clock_in' in data:
        entry.clock_in = data['clock_in'] if data['clock_in'] else None
    if 'clock_out' in data:
        entry.clock_out = data['clock_out'] if data['clock_out'] else None
    if 'daily_summary' in data:
        entry.daily_summary = data['daily_summary']
    
    entry.save()
    
    return JsonResponse({'success': True})


@login_required
def get_workplace_outcomes(request):
    """
    API endpoint to get workplace outcomes for a module.
    Used for dynamic dropdown population.
    """
    user = request.user
    module_id = request.GET.get('module_id')
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    outcomes = WorkplaceModuleOutcome.objects.filter(is_active=True)
    
    if module_id:
        outcomes = outcomes.filter(module_id=module_id)
    else:
        # Get outcomes for learner's qualification
        enrollment = Enrollment.objects.filter(
            learner=learner,
            status__in=['ACTIVE', 'ENROLLED', 'REGISTERED']
        ).first()
        
        if enrollment:
            outcomes = outcomes.filter(
                module__qualification=enrollment.qualification,
                module__module_type='W'
            )
    
    outcomes = outcomes.select_related('module').order_by('module__code', 'outcome_number')
    
    data = [{
        'id': o.id,
        'code': o.outcome_code,
        'title': o.title,
        'module_code': o.module.code,
        'module_name': o.module.name,
        'estimated_hours': str(o.estimated_hours) if o.estimated_hours else None
    } for o in outcomes]
    
    return JsonResponse({'outcomes': data})


# =============================================================================
# Task Quick Add Views (Separate from Attendance)
# =============================================================================

class StudentTaskQuickAddView(LoginRequiredMixin, TemplateView):
    """
    Mobile-first quick add task page.
    Shows WM outcomes grouped by module for selection.
    Designed for learners to add multiple tasks throughout the day AFTER clocking in.
    """
    template_name = 'portals/student/wbl/task_quick_add.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = date.today()
        
        learner = Learner.objects.filter(user=user).first()
        if not learner:
            context['no_learner_profile'] = True
            return context
        
        context['learner'] = learner
        
        # Get active placement
        placement = WorkplacePlacement.objects.filter(
            learner=learner,
            status='ACTIVE'
        ).select_related('host', 'host__employer').first()
        
        context['placement'] = placement
        
        if not placement:
            context['no_placement'] = True
            return context
        
        # Get today's attendance - must be clocked in
        today_attendance = WorkplaceAttendance.objects.filter(
            placement=placement,
            date=today
        ).first()
        context['today_attendance'] = today_attendance
        
        # Get or create today's daily entry
        daily_entry = DailyLogbookEntry.objects.filter(
            placement=placement,
            entry_date=today
        ).first()
        context['daily_entry'] = daily_entry
        context['can_add_tasks'] = daily_entry and not daily_entry.learner_signed
        
        # Get today's tasks if entry exists
        if daily_entry:
            today_tasks = daily_entry.task_completions.select_related(
                'workplace_outcome', 'workplace_outcome__module'
            ).order_by('-created_at')
            context['today_tasks'] = today_tasks
            context['task_count'] = today_tasks.count()
            context['total_hours'] = sum(t.hours_spent for t in today_tasks)
        else:
            context['today_tasks'] = []
            context['task_count'] = 0
            context['total_hours'] = Decimal('0')
        
        # Get active enrollment
        enrollment = Enrollment.objects.filter(
            learner=learner,
            status__in=['ACTIVE', 'ENROLLED', 'REGISTERED']
        ).select_related('qualification').first()
        
        context['enrollment'] = enrollment
        
        if enrollment:
            # Get all W modules for this qualification
            w_modules = Module.objects.filter(
                qualification=enrollment.qualification,
                module_type='W',
                is_active=True
            ).order_by('sequence_order', 'code')
            
            # Get all workplace outcomes grouped by module
            outcomes = WorkplaceModuleOutcome.objects.filter(
                module__in=w_modules,
                is_active=True
            ).select_related('module').order_by('module__sequence_order', 'outcome_number')
            
            # Group outcomes by module
            grouped_outcomes = {}
            for module in w_modules:
                grouped_outcomes[module.code] = {
                    'module': module,
                    'outcomes': []
                }
            
            for outcome in outcomes:
                if outcome.module.code in grouped_outcomes:
                    grouped_outcomes[outcome.module.code]['outcomes'].append(outcome)
            
            # Filter out modules with no outcomes
            grouped_outcomes = {k: v for k, v in grouped_outcomes.items() if v['outcomes']}
            
            context['grouped_outcomes'] = grouped_outcomes
            context['total_outcomes'] = outcomes.count()
        
        context['today'] = today
        context['competency_choices'] = DailyTaskCompletion.COMPETENCY_CHOICES
        
        return context


@login_required
@require_POST
def student_quick_add_task(request):
    """
    Quick add task API endpoint with offline support.
    Creates a task for today's daily entry (creates entry if needed).
    Returns JSON for AJAX/offline sync.
    """
    user = request.user
    
    learner = Learner.objects.filter(user=user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    placement = WorkplacePlacement.objects.filter(
        learner=learner,
        status='ACTIVE'
    ).first()
    
    if not placement:
        return JsonResponse({'error': 'No active placement'}, status=403)
    
    # Handle both JSON and form data
    if request.content_type and 'application/json' in request.content_type:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        data = request.POST
    
    # Get task data
    outcome_id = data.get('outcome_id')
    task_description = data.get('task_description', '')
    hours_spent = data.get('hours_spent', '1.0')
    evidence_notes = data.get('evidence_notes', '')
    entry_date_str = data.get('entry_date')  # Optional for offline sync
    
    # Offline sync support
    client_uuid = data.get('client_uuid')
    offline_created = data.get('offline_created', 'false')
    if isinstance(offline_created, str):
        offline_created = offline_created.lower() == 'true'
    
    # Parse entry date (defaults to today)
    if entry_date_str:
        try:
            entry_date = date.fromisoformat(entry_date_str)
        except (ValueError, TypeError):
            entry_date = date.today()
    else:
        entry_date = date.today()
    
    if not task_description:
        return JsonResponse({'error': 'Task description is required'}, status=400)
    
    try:
        hours_spent = Decimal(str(hours_spent))
    except (ValueError, TypeError, InvalidOperation):
        hours_spent = Decimal('1.0')
    
    # Get or create daily entry for this date
    daily_entry, entry_created = DailyLogbookEntry.objects.get_or_create(
        placement=placement,
        entry_date=entry_date,
        defaults={
            'attendance_status': 'PRESENT',
        }
    )
    
    # Check if entry is signed (can't add tasks to signed entries)
    if daily_entry.learner_signed:
        return JsonResponse({'error': 'Cannot add tasks to signed entry'}, status=403)
    
    # Get workplace outcome if provided
    workplace_outcome = None
    if outcome_id:
        try:
            workplace_outcome = WorkplaceModuleOutcome.objects.get(id=outcome_id)
        except (WorkplaceModuleOutcome.DoesNotExist, ValueError):
            pass
    
    # Check for duplicate via client_uuid (offline deduplication)
    if client_uuid:
        # Check if we already have a task with this client_uuid in evidence_notes
        existing = DailyTaskCompletion.objects.filter(
            daily_entry=daily_entry,
            evidence_notes__contains=f'client_uuid:{client_uuid}'
        ).first()
        if existing:
            return JsonResponse({
                'success': True,
                'task_id': existing.id,
                'created': False,
                'duplicate': True,
                'message': 'Task already exists (offline sync deduplication)'
            })
        # Store client_uuid in evidence_notes for deduplication
        if evidence_notes:
            evidence_notes = f"{evidence_notes}\nclient_uuid:{client_uuid}"
        else:
            evidence_notes = f"client_uuid:{client_uuid}"
    
    # Create the task
    task = DailyTaskCompletion.objects.create(
        daily_entry=daily_entry,
        workplace_outcome=workplace_outcome,
        task_description=task_description,
        hours_spent=hours_spent,
        evidence_notes=evidence_notes
    )
    
    # Handle evidence file upload (multipart only)
    if hasattr(request, 'FILES') and 'evidence_file' in request.FILES:
        task.evidence_file = request.FILES['evidence_file']
        task.save(update_fields=['evidence_file'])
    
    # Calculate new totals for today
    today_tasks = daily_entry.task_completions.all()
    total_tasks = today_tasks.count()
    total_hours = sum(t.hours_spent for t in today_tasks)
    
    return JsonResponse({
        'success': True,
        'task_id': task.id,
        'created': True,
        'daily_entry_id': daily_entry.id,
        'daily_entry_created': entry_created,
        'task': {
            'id': task.id,
            'description': task.task_description,
            'hours_spent': str(task.hours_spent),
            'outcome_code': task.outcome_code,
            'outcome_title': workplace_outcome.title if workplace_outcome else None,
            'module_code': workplace_outcome.module.code if workplace_outcome else None,
            'has_evidence': bool(task.evidence_file),
            'created_at': task.created_at.isoformat() if task.created_at else None,
        },
        'totals': {
            'task_count': total_tasks,
            'total_hours': str(total_hours),
        }
    })
