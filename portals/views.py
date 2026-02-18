"""
Portal Views

User-friendly views for different portal types (Learner, Corporate, Facilitator, etc.)
These provide role-based dashboards and workflow-guided experiences.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView, View
from django.db import models
from django.db.models import Count, Q
from django.utils import timezone


# =====================================================
# Dashboard Mixin
# =====================================================

class DashboardMixin:
    """Mixin providing common dashboard functionality."""
    
    def get_pending_tasks(self, user):
        """Get pending tasks for the user."""
        from workflows.models import Task
        return Task.objects.filter(
            assigned_to=user,
            status__in=['pending', 'in_progress']
        ).order_by('-priority', 'due_date')[:5]
    
    def get_notifications(self, user):
        """Get unread notifications for the user."""
        from portals.models import Notification
        return Notification.objects.filter(
            user=user,
            is_read=False
        ).order_by('-created_at')[:10]
    
    def get_announcements(self, portal_type, brand=None):
        """Get active announcements for a portal type."""
        from portals.models import Announcement
        
        # Map portal type to audience choices
        audience_map = {
            'learner': ['ALL', 'LEARNERS'],
            'staff': ['ALL', 'STAFF'],
            'facilitator': ['ALL', 'FACILITATORS', 'STAFF'],
            'corporate': ['ALL', 'STAFF'],
            'host_employer': ['ALL', 'STAFF'],
        }
        audiences = audience_map.get(portal_type, ['ALL'])
        
        qs = Announcement.objects.filter(
            audience__in=audiences,
            is_published=True,
            publish_at__lte=timezone.now()
        ).filter(
            Q(expire_at__isnull=True) | Q(expire_at__gte=timezone.now())
        )
        if brand:
            qs = qs.filter(brand=brand)
        return qs.order_by('-is_pinned', '-priority', '-publish_at')[:5]


# =====================================================
# Learner Portal
# =====================================================

class LearnerDashboardView(LoginRequiredMixin, DashboardMixin, TemplateView):
    """
    Learner Dashboard - The main hub for learners.
    
    Shows:
    - Current enrollments and progress
    - Upcoming assessments
    - Pending tasks (documents to upload, forms to complete)
    - Achievement badges
    - Quick actions
    """
    template_name = 'portals/learner/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get learner profile
        from learners.models import Learner
        learner = Learner.objects.filter(user=user).first()
        
        if learner:
            # Get active enrollments
            from academics.models import Enrollment
            enrollments = Enrollment.objects.filter(
                learner=learner,
                status__in=['active', 'in_progress']
            ).select_related('qualification', 'campus')
            
            # Calculate progress for each enrollment
            enrollment_data = []
            for enrollment in enrollments:
                progress = self._calculate_enrollment_progress(enrollment)
                enrollment_data.append({
                    'enrollment': enrollment,
                    'progress': progress
                })
            
            context['enrollments'] = enrollment_data
            context['learner'] = learner
            
            # Get upcoming assessments
            from assessments.models import AssessmentResult
            upcoming_assessments = AssessmentResult.objects.filter(
                enrollment__learner=learner,
                status='scheduled'
            ).select_related('activity', 'enrollment__qualification')[:5]
            context['upcoming_assessments'] = upcoming_assessments
            
            # Get document status
            from learners.models import Document
            documents = Document.objects.filter(learner=learner)
            context['document_stats'] = {
                'total': documents.count(),
                'verified': documents.filter(verified=True).count(),
                'pending': documents.filter(verified=False).count(),
            }
            
            # Journey progress placeholder (UserJourney model not implemented)
            context['journey'] = None
        
        # Common dashboard elements
        context['tasks'] = self.get_pending_tasks(user)
        context['notifications'] = self.get_notifications(user)
        context['announcements'] = self.get_announcements('learner')
        
        # Quick stats
        context['quick_stats'] = self._get_learner_stats(learner) if learner else {}
        
        return context
    
    def _calculate_enrollment_progress(self, enrollment):
        """Calculate progress percentage for an enrollment."""
        from assessments.models import AssessmentResult
        
        total = AssessmentResult.objects.filter(enrollment=enrollment).count()
        completed = AssessmentResult.objects.filter(
            enrollment=enrollment,
            status='competent'
        ).count()
        
        if total == 0:
            return 0
        return int((completed / total) * 100)
    
    def _get_learner_stats(self, learner):
        """Get quick statistics for the learner."""
        from academics.models import Enrollment
        from assessments.models import AssessmentResult
        
        return {
            'active_programs': Enrollment.objects.filter(
                learner=learner,
                status__in=['active', 'in_progress']
            ).count(),
            'assessments_passed': AssessmentResult.objects.filter(
                enrollment__learner=learner,
                result='competent'
            ).count(),
            'certificates_earned': Enrollment.objects.filter(
                learner=learner,
                status='completed'
            ).count()
        }


class LearnerEnrollmentsView(LoginRequiredMixin, ListView):
    """View all enrollments for a learner."""
    template_name = 'portals/learner/enrollments.html'
    context_object_name = 'enrollments'
    
    def get_queryset(self):
        from academics.models import Enrollment
        from learners.models import Learner
        
        learner = Learner.objects.filter(user=self.request.user).first()
        if not learner:
            return Enrollment.objects.none()
        
        return Enrollment.objects.filter(
            learner=learner
        ).select_related('qualification', 'campus').order_by('-created_at')


class LearnerDocumentsView(LoginRequiredMixin, ListView):
    """View and manage learner documents."""
    template_name = 'portals/learner/documents.html'
    context_object_name = 'documents'
    
    def get_queryset(self):
        from learners.models import Document, Learner
        
        learner = Learner.objects.filter(user=self.request.user).first()
        if not learner:
            return Document.objects.none()
        
        return Document.objects.filter(learner=learner).order_by('-uploaded_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Required document types
        context['required_documents'] = [
            {'type': 'id_document', 'name': 'ID Document / Passport', 'required': True},
            {'type': 'matric_certificate', 'name': 'Matric Certificate', 'required': True},
            {'type': 'proof_of_residence', 'name': 'Proof of Residence', 'required': True},
            {'type': 'cv', 'name': 'Curriculum Vitae (CV)', 'required': False},
            {'type': 'qualification_certificates', 'name': 'Other Qualifications', 'required': False},
        ]
        
        return context


# =====================================================
# Corporate Portal
# =====================================================

class CorporateDashboardView(LoginRequiredMixin, DashboardMixin, TemplateView):
    """
    Corporate Client Dashboard - Hub for SDFs and corporate contacts.
    
    Shows:
    - Company overview and employees
    - WSP/ATR status and deadlines
    - Training progress
    - Grant applications
    - Compliance status
    """
    template_name = 'portals/corporate/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get corporate client for this user
        from corporate.models import CorporateClient, CorporateContact
        contact = CorporateContact.objects.filter(user=user).first()
        
        if contact:
            client = contact.client
            context['client'] = client
            context['contact'] = contact
            
            # WSP/ATR Status
            from corporate.models import WSPSubmission, ATRSubmission, WSPYear
            current_year = WSPYear.objects.filter(is_current=True).first()
            
            if current_year:
                context['wsp_status'] = WSPSubmission.objects.filter(
                    client=client,
                    wsp_year=current_year
                ).first()
                context['atr_status'] = ATRSubmission.objects.filter(
                    client=client,
                    reporting_year=current_year
                ).first()
                context['current_year'] = current_year
            
            # Employee training stats
            from corporate.models import CorporateEmployee
            employees = CorporateEmployee.objects.filter(client=client, is_active=True)
            context['employee_stats'] = {
                'total': employees.count(),
                'in_training': employees.filter(linked_learner__isnull=False).count(),
            }
            
            # Grant projects
            from corporate.models import GrantProject
            context['active_grants'] = GrantProject.objects.filter(
                client=client,
                status__in=['approved', 'in_progress']
            )[:5]
            
            # Upcoming deadlines
            from corporate.models import DeadlineReminder
            context['upcoming_deadlines'] = DeadlineReminder.objects.filter(
                client=client,
                deadline_date__gte=timezone.now().date()
            ).order_by('deadline_date')[:5]
            
            # Compliance overview
            context['compliance'] = self._get_compliance_status(client)
        
        context['tasks'] = self.get_pending_tasks(user)
        context['notifications'] = self.get_notifications(user)
        context['announcements'] = self.get_announcements('corporate')
        
        return context
    
    def _get_compliance_status(self, client):
        """Get compliance status for the client."""
        from corporate.models import EEReport, BBBEEScorecard
        
        return {
            'ee_status': EEReport.objects.filter(client=client).order_by('-created_at').first(),
            'bbbee_status': BBBEEScorecard.objects.filter(client=client).order_by('-certificate_date').first(),
        }


class CorporateEmployeesView(LoginRequiredMixin, ListView):
    """View and manage corporate employees."""
    template_name = 'portals/corporate/employees.html'
    context_object_name = 'employees'
    paginate_by = 20
    
    def get_queryset(self):
        from corporate.models import CorporateEmployee, CorporateContact
        
        contact = CorporateContact.objects.filter(user=self.request.user).first()
        if not contact:
            return CorporateEmployee.objects.none()
        
        return CorporateEmployee.objects.filter(
            client=contact.client
        ).select_related('linked_learner').order_by('last_name', 'first_name')


# =====================================================
# Facilitator Portal
# =====================================================

class FacilitatorDashboardView(LoginRequiredMixin, DashboardMixin, TemplateView):
    """
    Facilitator Dashboard - Hub for trainers and assessors.
    
    Shows:
    - My cohorts and schedules
    - Attendance to capture
    - Assessments to conduct
    - Assessment results to capture
    - Moderation items
    """
    template_name = 'portals/facilitator/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get facilitator's cohorts
        from logistics.models import Cohort, ScheduleSession, Attendance
        
        my_cohorts = Cohort.objects.filter(
            Q(facilitator=user) | Q(co_facilitators=user),
            status='active'
        ).distinct()
        context['my_cohorts'] = my_cohorts
        
        # Today's sessions
        today = timezone.now().date()
        context['today_sessions'] = ScheduleSession.objects.filter(
            cohort__in=my_cohorts,
            session_date=today
        ).select_related('cohort', 'venue')
        
        # Pending attendance capture
        context['pending_attendance'] = ScheduleSession.objects.filter(
            cohort__in=my_cohorts,
            session_date__lt=today,
            attendance_captured=False
        ).count()
        
        # Assessments to conduct
        from assessments.models import AssessmentResult
        context['pending_assessments'] = AssessmentResult.objects.filter(
            assessor=user,
            status='scheduled'
        ).select_related('enrollment__learner', 'activity')[:10]
        
        # Results to capture
        context['results_to_capture'] = AssessmentResult.objects.filter(
            assessor=user,
            status='in_progress'
        ).count()
        
        # Moderation items
        from assessments.models import ModerationRecord
        context['moderation_items'] = ModerationRecord.objects.filter(
            moderator=user,
            status='pending'
        ).count()
        
        # Quick stats
        context['quick_stats'] = {
            'active_cohorts': my_cohorts.count(),
            'total_learners': sum(c.enrollments.filter(status='active').count() for c in my_cohorts),
            'sessions_this_week': ScheduleSession.objects.filter(
                cohort__in=my_cohorts,
                session_date__gte=today,
                session_date__lt=today + timezone.timedelta(days=7)
            ).count()
        }
        
        context['tasks'] = self.get_pending_tasks(user)
        context['notifications'] = self.get_notifications(user)
        context['announcements'] = self.get_announcements('facilitator')
        
        return context


class FacilitatorCohortView(LoginRequiredMixin, DetailView):
    """View details of a specific cohort."""
    template_name = 'portals/facilitator/cohort_detail.html'
    context_object_name = 'cohort'
    
    def get_queryset(self):
        from logistics.models import Cohort
        return Cohort.objects.filter(
            Q(facilitator=self.request.user) | Q(co_facilitators=self.request.user)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cohort = self.object
        
        # Get enrolled learners
        context['enrollments'] = cohort.enrollments.filter(
            status__in=['active', 'in_progress']
        ).select_related('learner')
        
        # Get upcoming sessions
        context['upcoming_sessions'] = cohort.sessions.filter(
            session_date__gte=timezone.now().date()
        ).order_by('session_date')[:10]
        
        return context


# =====================================================
# Host Employer Portal
# =====================================================

class HostEmployerDashboardView(LoginRequiredMixin, DashboardMixin, TemplateView):
    """
    Host Employer Dashboard - Hub for workplace supervisors.
    
    Shows:
    - Placed learners
    - Logbook hours to verify
    - Workplace assessments to sign off
    - Training schedules
    """
    template_name = 'portals/host_employer/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get host employer for this user
        # Check if user is linked via HostMentor or is superuser
        from corporate.models import HostEmployer, HostMentor
        
        host_employer = None
        
        # First check if user is a mentor at a host employer
        mentor = HostMentor.objects.filter(user=user).select_related('host').first()
        if mentor and mentor.host:
            host_employer = mentor.host
        
        # For superusers, get the first host employer if none found
        if not host_employer and user.is_superuser:
            host_employer = HostEmployer.objects.first()
        
        if host_employer:
            context['employer'] = host_employer
            context['host_employer'] = host_employer
            
            # Get placed learners via WorkplacePlacement
            from corporate.models import WorkplacePlacement
            placements = WorkplacePlacement.objects.filter(
                host=host_employer,
                status='ACTIVE'
            ).select_related('learner', 'enrollment')
            context['placements'] = placements
            
            # Logbook entries pending mentor/employer signature
            from learners.models import WorkplaceLogbookEntry
            context['pending_logbooks'] = WorkplaceLogbookEntry.objects.filter(
                placement__host=host_employer,
                mentor_signed=False
            ).count()
            
            # Count total learners
            context['total_learners'] = placements.count()
            
            # Pending signoffs (logbooks needing facilitator sign-off after mentor signed)
            context['pending_signoffs'] = WorkplaceLogbookEntry.objects.filter(
                placement__host=host_employer,
                mentor_signed=True,
                facilitator_signed=False
            ).count()
        else:
            context['employer'] = None
            context['host_employer'] = None
            context['placements'] = []
            context['pending_logbooks'] = 0
            context['total_learners'] = 0
            context['pending_signoffs'] = 0
        
        context['tasks'] = self.get_pending_tasks(user)
        context['notifications'] = self.get_notifications(user)
        context['announcements'] = self.get_announcements('host_employer')
        
        return context
        
        return context


# =====================================================
# Staff Portal
# =====================================================

class StaffDashboardView(LoginRequiredMixin, DashboardMixin, TemplateView):
    """
    Staff Dashboard - Hub for internal staff.
    
    Shows role-specific information based on user's roles:
    - Admin: System overview, user management
    - Finance: Invoices, payments, aged debtors
    - Academic: Enrollments, certifications
    - CRM: Leads, conversions
    """
    template_name = 'portals/staff/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Determine user's role-based widgets
        widgets = []
        
        if user.is_superuser or self._has_role(user, 'admin'):
            widgets.extend(self._get_admin_widgets())
        
        if self._has_role(user, 'finance'):
            widgets.extend(self._get_finance_widgets())
        
        if self._has_role(user, 'academic'):
            widgets.extend(self._get_academic_widgets())
        
        if self._has_role(user, 'crm'):
            widgets.extend(self._get_crm_widgets())
        
        context['widgets'] = widgets
        context['tasks'] = self.get_pending_tasks(user)
        context['notifications'] = self.get_notifications(user)
        context['announcements'] = self.get_announcements('staff')
        
        return context
    
    def _has_role(self, user, role_name):
        """Check if user has a specific role."""
        from core.models import UserRole
        return UserRole.objects.filter(user=user, role__name=role_name, is_active=True).exists()
    
    def _get_admin_widgets(self):
        """Get admin dashboard widgets."""
        from core.models import User
        from learners.models import Learner
        
        return [{
            'title': 'System Overview',
            'type': 'stats',
            'data': {
                'total_users': User.objects.filter(is_active=True).count(),
                'total_learners': Learner.objects.count(),
            }
        }]
    
    def _get_finance_widgets(self):
        """Get finance dashboard widgets."""
        from finance.models import Invoice, Payment
        from django.db.models import Sum
        
        return [{
            'title': 'Finance Overview',
            'type': 'stats',
            'data': {
                'pending_invoices': Invoice.objects.filter(status='pending').count(),
                'pending_amount': Invoice.objects.filter(status='pending').aggregate(
                    total=Sum('total_amount')
                )['total'] or 0,
            }
        }]
    
    def _get_academic_widgets(self):
        """Get academic dashboard widgets."""
        from academics.models import Enrollment
        
        return [{
            'title': 'Academic Overview',
            'type': 'stats',
            'data': {
                'active_enrollments': Enrollment.objects.filter(status='active').count(),
                'pending_certifications': Enrollment.objects.filter(status='pending_certification').count(),
            }
        }]
    
    def _get_crm_widgets(self):
        """Get CRM dashboard widgets."""
        from crm.models import Lead
        
        return [{
            'title': 'CRM Overview',
            'type': 'stats',
            'data': {
                'new_leads': Lead.objects.filter(status='new').count(),
                'qualified_leads': Lead.objects.filter(status='qualified').count(),
            }
        }]


class StaffLeaveView(LoginRequiredMixin, DashboardMixin, TemplateView):
    """Staff leave management view."""
    template_name = 'portals/staff/leave.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get leave requests for the current user
        from hr.models import LeaveRequest
        
        context['leave_requests'] = LeaveRequest.objects.filter(
            staff_profile__user=user
        ).order_by('-created_at')[:20]
        
        context['leave_balance'] = {
            'annual': 20,
            'sick': 30,
            'family': 3,
            'study': 0,
        }
        
        return context


class StaffDocumentsView(LoginRequiredMixin, DashboardMixin, TemplateView):
    """Staff documents view - payslips, contracts, etc."""
    template_name = 'portals/staff/documents.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get documents for the current user
        context['documents'] = []  # To be populated from HR documents
        
        return context


class StaffProfileView(LoginRequiredMixin, DashboardMixin, TemplateView):
    """Staff profile view."""
    template_name = 'portals/staff/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context['user'] = user
        
        # Get employee profile if exists
        from hr.models import Employee
        context['employee'] = Employee.objects.filter(user=user).first()
        
        return context


# =====================================================
# Batch Assessment Capture
# =====================================================

class BatchAssessView(LoginRequiredMixin, TemplateView):
    """
    Mobile-first batch assessment capture.
    Facilitators can rapidly assess all learners in a cohort for a specific assessment.
    
    Features:
    - Swipeable card interface
    - Quick C/NYC/ABS buttons
    - Inline signature capture
    - Photo evidence capture
    - Offline support via PWA
    """
    template_name = 'portals/facilitator/batch_assess.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from assessments.models import AssessmentSchedule, AssessmentResult
        from academics.models import Enrollment
        
        schedule_id = self.kwargs.get('schedule_id')
        schedule = get_object_or_404(
            AssessmentSchedule.objects.select_related('cohort', 'activity', 'activity__module'),
            pk=schedule_id
        )
        
        context['schedule'] = schedule
        context['activity'] = schedule.activity
        context['cohort'] = schedule.cohort
        
        # Get all enrollments for the cohort
        enrollments = Enrollment.objects.filter(
            cohort=schedule.cohort,
            status__in=['ENROLLED', 'ACTIVE']
        ).select_related('learner', 'learner__user').order_by('learner__last_name')
        
        learners_data = []
        for enrollment in enrollments:
            learner = enrollment.learner
            
            # Get existing result
            existing = AssessmentResult.objects.filter(
                enrollment=enrollment,
                activity=schedule.activity
            ).order_by('-attempt_number').first()
            
            learners_data.append({
                'enrollment': enrollment,
                'learner': learner,
                'existing_result': existing,
                'attempt_count': AssessmentResult.objects.filter(
                    enrollment=enrollment,
                    activity=schedule.activity
                ).count(),
                'can_assess': True
            })
        
        context['learners'] = learners_data
        context['total_count'] = len(learners_data)
        
        # Count already assessed
        context['assessed_count'] = sum(1 for l in learners_data if l['existing_result'])
        
        return context


class FacilitatorTodayAssessmentsView(LoginRequiredMixin, TemplateView):
    """Today's assessments for the facilitator."""
    template_name = 'portals/facilitator/today_assessments.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from assessments.models import AssessmentSchedule
        from academics.models import Enrollment
        
        today = timezone.now().date()
        schedules = AssessmentSchedule.objects.filter(
            scheduled_date=today,
            status='SCHEDULED'
        ).select_related('cohort', 'activity', 'activity__module', 'venue')
        
        if not self.request.user.is_superuser:
            schedules = schedules.filter(cohort__facilitator=self.request.user)
        
        assessments_data = []
        for schedule in schedules:
            learner_count = Enrollment.objects.filter(
                cohort=schedule.cohort,
                status__in=['ENROLLED', 'ACTIVE']
            ).count()
            
            assessments_data.append({
                'schedule': schedule,
                'learner_count': learner_count
            })
        
        context['assessments'] = assessments_data
        context['today'] = today
        
        return context


# =====================================================
# Parent/Guardian Portal
# =====================================================

class ParentLoginView(View):
    """
    Parent portal login.
    Parents login using learner ID + their email OR access code.
    """
    template_name = 'portals/parent/login.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        from learners.models import Learner, Guardian, GuardianPortalAccess
        
        learner_number = request.POST.get('learner_number', '').strip()
        email = request.POST.get('email', '').strip().lower()
        access_code = request.POST.get('access_code', '').strip()
        
        error = None
        
        if access_code:
            # Login via access code
            try:
                portal_access = GuardianPortalAccess.objects.select_related(
                    'guardian', 'guardian__learner'
                ).get(access_code=access_code, is_active=True)
                
                # Check expiry
                if portal_access.access_code_expires and portal_access.access_code_expires < timezone.now():
                    error = 'Access code has expired. Please request a new one.'
                else:
                    portal_access.record_login()
                    request.session['parent_guardian_id'] = portal_access.guardian.id
                    request.session['parent_learner_id'] = portal_access.guardian.learner.id
                    return redirect('portals:parent_dashboard')
                    
            except GuardianPortalAccess.DoesNotExist:
                error = 'Invalid access code.'
        
        elif learner_number and email:
            # Login via learner number + email
            try:
                learner = Learner.objects.get(learner_number=learner_number)
                guardian = Guardian.objects.filter(
                    learner=learner,
                    email__iexact=email
                ).first()
                
                if guardian:
                    # Ensure portal access exists
                    portal_access, created = GuardianPortalAccess.objects.get_or_create(
                        guardian=guardian,
                        defaults={'is_active': True}
                    )
                    if created or not portal_access.access_code:
                        portal_access.generate_access_code()
                    
                    portal_access.record_login()
                    request.session['parent_guardian_id'] = guardian.id
                    request.session['parent_learner_id'] = learner.id
                    return redirect('portals:parent_dashboard')
                else:
                    error = 'No guardian found with this email for this learner.'
                    
            except Learner.DoesNotExist:
                error = 'Learner not found.'
        else:
            error = 'Please enter learner number and email, or access code.'
        
        return render(request, self.template_name, {'error': error})


class ParentPortalMixin:
    """Mixin for parent portal views requiring authentication."""
    
    def dispatch(self, request, *args, **kwargs):
        if 'parent_guardian_id' not in request.session:
            return redirect('portals:parent_login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_guardian(self):
        from learners.models import Guardian
        return get_object_or_404(Guardian, pk=self.request.session['parent_guardian_id'])
    
    def get_learner(self):
        from learners.models import Learner
        return get_object_or_404(Learner, pk=self.request.session['parent_learner_id'])


class ParentDashboardView(ParentPortalMixin, TemplateView):
    """
    Parent dashboard showing learner overview.
    """
    template_name = 'portals/parent/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from assessments.models import AssessmentResult, AssessmentSchedule
        from academics.models import Enrollment
        
        guardian = self.get_guardian()
        learner = self.get_learner()
        
        context['guardian'] = guardian
        context['learner'] = learner
        
        # Get active enrollment
        enrollment = Enrollment.objects.filter(
            learner=learner,
            status__in=['ENROLLED', 'ACTIVE']
        ).select_related('qualification', 'cohort').first()
        context['enrollment'] = enrollment
        
        if enrollment:
            # Get upcoming assessments
            upcoming = AssessmentSchedule.objects.filter(
                cohort=enrollment.cohort,
                scheduled_date__gte=timezone.now().date(),
                status='SCHEDULED'
            ).select_related('activity', 'activity__module').order_by('scheduled_date')[:5]
            context['upcoming_assessments'] = upcoming
            
            # Get recent results
            recent_results = AssessmentResult.objects.filter(
                enrollment=enrollment,
                status='FINALIZED'
            ).select_related('activity', 'activity__module').order_by('-assessment_date')[:5]
            context['recent_results'] = recent_results
            
            # Calculate progress
            total_activities = enrollment.qualification.modules.aggregate(
                total=models.Count('assessment_activities')
            )['total'] or 0
            completed = AssessmentResult.objects.filter(
                enrollment=enrollment,
                result='C',
                status='FINALIZED'
            ).values('activity').distinct().count()
            
            context['progress'] = {
                'completed': completed,
                'total': total_activities,
                'percentage': round((completed / total_activities * 100) if total_activities else 0, 1)
            }
        
        return context


class ParentAssessmentScheduleView(ParentPortalMixin, TemplateView):
    """
    Assessment schedule calendar for parents.
    Shows all upcoming assessments for their child.
    """
    template_name = 'portals/parent/schedule.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from assessments.models import AssessmentSchedule
        from academics.models import Enrollment
        
        learner = self.get_learner()
        context['learner'] = learner
        
        # Get active enrollment
        enrollment = Enrollment.objects.filter(
            learner=learner,
            status__in=['ENROLLED', 'ACTIVE']
        ).select_related('cohort').first()
        
        if enrollment:
            schedules = AssessmentSchedule.objects.filter(
                cohort=enrollment.cohort,
                scheduled_date__gte=timezone.now().date() - timezone.timedelta(days=30)
            ).select_related('activity', 'activity__module').order_by('scheduled_date')
            
            context['schedules'] = schedules
            context['enrollment'] = enrollment
        
        return context


class ParentResultsView(ParentPortalMixin, TemplateView):
    """
    Assessment results history for parents.
    Shows all completed assessments with C/NYC status.
    """
    template_name = 'portals/parent/results.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from assessments.models import AssessmentResult
        from academics.models import Enrollment
        
        learner = self.get_learner()
        context['learner'] = learner
        
        # Get active enrollment
        enrollment = Enrollment.objects.filter(
            learner=learner,
            status__in=['ENROLLED', 'ACTIVE']
        ).first()
        
        if enrollment:
            results = AssessmentResult.objects.filter(
                enrollment=enrollment
            ).select_related(
                'activity', 'activity__module', 'assessor'
            ).order_by('-assessment_date')
            
            context['results'] = results
            context['enrollment'] = enrollment
            
            # Summary stats
            context['stats'] = {
                'competent': results.filter(result='C', status='FINALIZED').count(),
                'nyc': results.filter(result='NYC', status='FINALIZED').count(),
                'pending': results.filter(status__in=['DRAFT', 'PENDING_MOD']).count()
            }
        
        return context


class ParentLogoutView(View):
    """Logout from parent portal."""
    
    def get(self, request):
        if 'parent_guardian_id' in request.session:
            del request.session['parent_guardian_id']
        if 'parent_learner_id' in request.session:
            del request.session['parent_learner_id']
        return redirect('portals:parent_login')


# =====================================================
# Student Assessment Calendar
# =====================================================

class StudentAssessmentCalendarView(LoginRequiredMixin, TemplateView):
    """
    Assessment calendar for students.
    Shows upcoming assessments based on their enrollment and cohort schedule.
    """
    template_name = 'portals/student/assessment_calendar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from assessments.models import AssessmentSchedule
        from academics.models import Enrollment
        
        # Get learner's enrollment
        if hasattr(self.request.user, 'learner_profile'):
            learner = self.request.user.learner_profile
            enrollment = Enrollment.objects.filter(
                learner=learner,
                status__in=['ENROLLED', 'ACTIVE']
            ).select_related('cohort').first()
            
            if enrollment and enrollment.cohort:
                schedules = AssessmentSchedule.objects.filter(
                    cohort=enrollment.cohort,
                    scheduled_date__gte=timezone.now().date()
                ).select_related('activity', 'activity__module', 'venue').order_by('scheduled_date')
                
                context['schedules'] = schedules
                context['enrollment'] = enrollment
        
        return context


# Create your views here.
