"""
Portal Views

User-friendly views for different portal types (Learner, Corporate, Facilitator, etc.)
These provide role-based dashboards and workflow-guided experiences.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView
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

# Create your views here.
