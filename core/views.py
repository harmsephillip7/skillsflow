"""
Core Views - Authentication and Access Control
Single Sign-On with role-based portal access
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib import messages
from django.urls import reverse
from django.db.models import Q
from datetime import date
from corporate.models import WorkplacePlacement


class SSOLoginView(TemplateView):
    """
    Single Sign-On Login Page
    All users authenticate through this single entry point
    """
    template_name = 'auth/sso_login.html'
    
    def get(self, request, *args, **kwargs):
        # If already authenticated, redirect to dashboard
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')
        
        if not email or not password:
            messages.error(request, 'Please enter both email and password.')
            return render(request, self.template_name, {'email': email})
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                
                # Set session expiry based on remember me
                if not remember_me:
                    request.session.set_expiry(0)  # Browser close
                else:
                    request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
                
                messages.success(request, f'Welcome back, {user.get_full_name() or user.email}!')
                
                # Redirect to next URL or dashboard
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('core:dashboard')
            else:
                messages.error(request, 'Your account has been deactivated. Please contact support.')
        else:
            messages.error(request, 'Invalid email or password. Please try again.')
        
        return render(request, self.template_name, {'email': email})


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Main Dashboard Hub
    Shows personalized dashboard with sections based on user's access rights
    """
    template_name = 'auth/dashboard.html'
    login_url = '/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user's access rights and available sections
        access_info = self._get_user_access(user)
        
        context['user'] = user
        context['access_info'] = access_info
        context['available_sections'] = access_info['sections']
        context['primary_portal'] = access_info['primary_portal']
        context['user_roles'] = access_info['roles']
        context['quick_actions'] = self._get_quick_actions(user, access_info)
        context['recent_activity'] = self._get_recent_activity(user)
        context['notifications'] = self._get_notifications(user)
        
        return context
    
    def _get_user_access(self, user):
        """Determine user's access rights and available sections"""
        from core.models import UserRole, Role
        from learners.models import Learner
        from corporate.models import CorporateContact
        from learners.models import Employer
        
        sections = []
        roles = []
        primary_portal = None
        access_level = 'SELF'
        
        # Check if superuser - full access
        if user.is_superuser:
            sections = [
                {'name': 'Capacity Dashboard', 'icon': 'chart-bar', 'url': reverse('core:capacity_dashboard'), 'color': 'primary', 'description': 'Campus capacity, utilization & planning'},
                {'name': 'Projects', 'icon': 'folder', 'url': reverse('core:projects_dashboard'), 'color': 'cyan', 'description': 'Projects with deliverables, finance, evidence & timeline'},
                {'name': 'Academics', 'icon': 'book-open', 'url': '/academics/dashboard/', 'color': 'purple', 'description': 'Qualifications, accreditations, learning materials & assessments'},
                {'name': 'Corporate Services', 'icon': 'office-building', 'url': reverse('corporate:dashboard'), 'color': 'indigo', 'description': 'Corporate clients & services'},
                {'name': 'Training NOT', 'icon': 'bell', 'url': '/not/', 'color': 'yellow', 'description': 'Notification of Training - New projects & enrollments'},
                {'name': 'Intake Buckets', 'icon': 'collection', 'url': '/intakes/', 'color': 'teal', 'description': 'Manage learner intakes & enrollment capacity'},
                {'name': 'Tranche Payments', 'icon': 'currency-dollar', 'url': '/tranches/', 'color': 'emerald', 'description': 'Tranche payments, evidence & funder submissions'},
                {'name': 'Trade Tests', 'icon': 'clipboard-list', 'url': '/trade-tests/', 'color': 'orange', 'description': 'Trade test applications, bookings & NAMB submissions'},
                {'name': 'Staff Portal', 'icon': 'briefcase', 'url': '/portal/staff/', 'color': 'blue', 'description': 'Internal operations dashboard'},
                {'name': 'Learner Database', 'icon': 'academic-cap', 'url': '/learners/', 'color': 'green', 'description': 'Search and view learner profiles'},
                {'name': 'Workflows', 'icon': 'lightning-bolt', 'url': '/workflows/', 'color': 'orange', 'description': 'Process management'},
                {'name': 'Integrations', 'icon': 'plug', 'url': '/integrations/', 'color': 'cyan', 'description': 'Connect external services - Microsoft 365, Sage, Moodle & more'},
                {'name': 'Tenders', 'icon': 'document-text', 'url': '/tenders/', 'color': 'amber', 'description': 'Tender management, web scraping & revenue forecasting'},
                {'name': 'CRM / Leads', 'icon': 'user-add', 'url': '/crm/', 'color': 'pink', 'description': 'Lead management, school leavers & sales pipeline'},
            ]
            roles = ['Super Administrator']
            primary_portal = 'staff'
            access_level = 'SYSTEM'
        else:
            # Check for learner
            learner = Learner.objects.filter(user=user).first()
            if learner:
                sections.append({
                    'name': 'My Learning', 
                    'icon': 'academic-cap', 
                    'url': '/portal/learner/', 
                    'color': 'green',
                    'description': 'Access your courses and progress'
                })
                sections.append({
                    'name': 'My Assessments', 
                    'icon': 'clipboard-check', 
                    'url': '/portal/learner/assessments/', 
                    'color': 'blue',
                    'description': 'View upcoming and completed assessments'
                })
                sections.append({
                    'name': 'My Documents', 
                    'icon': 'document', 
                    'url': '/portal/learner/documents/', 
                    'color': 'purple',
                    'description': 'Upload and manage your documents'
                })
                sections.append({
                    'name': 'My Certificates', 
                    'icon': 'badge-check', 
                    'url': '/portal/learner/certificates/', 
                    'color': 'yellow',
                    'description': 'View earned certificates'
                })
                
                roles.append('Learner')
                
                # Check for active WBL placement
                active_placement = WorkplacePlacement.objects.filter(
                    learner=learner,
                    status='ACTIVE'
                ).first()
                if active_placement:
                    sections.insert(0, {
                        'name': 'Clock In / Attendance',
                        'icon': 'clock',
                        'url': '/portal/student/wbl/',
                        'color': 'emerald',
                        'description': 'Tap to clock in/out at your workplace'
                    })
                    # Make WBL the primary portal for learners with active placements
                    primary_portal = 'student_wbl'
                    roles.append('WBL Learner')
                elif not primary_portal:
                    primary_portal = 'learner'
            
            # Check for corporate contact
            corporate = CorporateContact.objects.filter(email=user.email).first()
            if corporate:
                sections.append({
                    'name': 'Company Dashboard', 
                    'icon': 'office-building', 
                    'url': '/portal/corporate/', 
                    'color': 'indigo',
                    'description': 'Company training overview'
                })
                sections.append({
                    'name': 'Employees', 
                    'icon': 'users', 
                    'url': '/portal/corporate/employees/', 
                    'color': 'blue',
                    'description': 'Manage employee training'
                })
                sections.append({
                    'name': 'WSP/ATR', 
                    'icon': 'document-report', 
                    'url': '/portal/corporate/wsp/', 
                    'color': 'green',
                    'description': 'Workplace Skills Plan'
                })
                sections.append({
                    'name': 'Invoices', 
                    'icon': 'receipt-tax', 
                    'url': '/portal/corporate/invoices/', 
                    'color': 'yellow',
                    'description': 'View and pay invoices'
                })
                roles.append(f'Corporate Contact ({corporate.client.name if corporate.client else ""})')
                if not primary_portal:
                    primary_portal = 'corporate'
            
            # Check for host employer
            employer = Employer.objects.filter(contact_email=user.email).first()
            if employer:
                sections.append({
                    'name': 'Host Employer Portal', 
                    'icon': 'briefcase', 
                    'url': '/portal/host-employer/', 
                    'color': 'orange',
                    'description': 'Manage workplace placements'
                })
                sections.append({
                    'name': 'Placed Learners', 
                    'icon': 'user-group', 
                    'url': '/portal/host-employer/learners/', 
                    'color': 'green',
                    'description': 'View learners at your workplace'
                })
                sections.append({
                    'name': 'Logbooks', 
                    'icon': 'book-open', 
                    'url': '/portal/host-employer/logbooks/', 
                    'color': 'blue',
                    'description': 'Sign and manage logbooks'
                })
                roles.append(f'Host Employer ({employer.name})')
                if not primary_portal:
                    primary_portal = 'host_employer'
            
            # Check user roles from UserRole model
            user_roles = UserRole.objects.filter(
                user=self.request.user,
                is_active=True,
                valid_from__lte=date.today()
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=date.today())
            ).select_related('role')
            
            for user_role in user_roles:
                role = user_role.role
                roles.append(role.name)
                
                # Map roles to sections
                if role.code in ['FACILITATOR', 'ASSESSOR', 'MODERATOR', 'QCTO_INTERNAL_MODERATOR']:
                    if not any(s['url'] == '/portal/facilitator/' for s in sections):
                        sections.append({
                            'name': 'Facilitator Portal', 
                            'icon': 'presentation-chart-bar', 
                            'url': '/portal/facilitator/', 
                            'color': 'green',
                            'description': 'Manage cohorts and assessments'
                        })
                        sections.append({
                            'name': 'My Cohorts', 
                            'icon': 'user-group', 
                            'url': '/portal/facilitator/cohorts/', 
                            'color': 'blue',
                            'description': 'View assigned cohorts'
                        })
                        sections.append({
                            'name': 'Attendance', 
                            'icon': 'clipboard-list', 
                            'url': '/portal/facilitator/attendance/', 
                            'color': 'yellow',
                            'description': 'Record attendance'
                        })
                    if not primary_portal:
                        primary_portal = 'facilitator'
                
                elif role.code in ['SUPER_ADMIN', 'SYSTEM_ADMIN', 'HEAD_OFFICE_MANAGER']:
                    sections.append({
                        'name': 'Staff Portal', 
                        'icon': 'briefcase', 
                        'url': '/portal/staff/', 
                        'color': 'blue',
                        'description': 'System administration'
                    })
                    sections.append({
                        'name': 'Training NOT', 
                        'icon': 'bell', 
                        'url': '/not/', 
                        'color': 'yellow',
                        'description': 'Notification of Training'
                    })
                    if not primary_portal:
                        primary_portal = 'staff'
                    access_level = 'SYSTEM'
                
                elif role.code in ['FINANCE_DIRECTOR', 'FINANCE_MANAGER', 'FINANCE_CLERK']:
                    sections.append({
                        'name': 'Finance', 
                        'icon': 'currency-dollar', 
                        'url': '/portal/staff/', 
                        'color': 'yellow',
                        'description': 'Financial operations'
                    })
                    if not primary_portal:
                        primary_portal = 'staff'
                
                elif role.code in ['ACADEMIC_DIRECTOR', 'ACADEMIC_COORDINATOR', 'BRAND_ACADEMIC_LEAD']:
                    sections.append({
                        'name': 'Academics', 
                        'icon': 'book-open', 
                        'url': '/academics/dashboard/', 
                        'color': 'purple',
                        'description': 'Qualifications, accreditations, learning materials & assessments'
                    })
                    sections.append({
                        'name': 'Training NOT', 
                        'icon': 'bell', 
                        'url': '/not/', 
                        'color': 'yellow',
                        'description': 'Notification of Training'
                    })
                    if not primary_portal:
                        primary_portal = 'staff'
                
                elif role.code in ['CAMPUS_PRINCIPAL', 'CAMPUS_ADMIN', 'REGISTRAR']:
                    sections.append({
                        'name': 'Campus Portal', 
                        'icon': 'library', 
                        'url': '/portal/staff/', 
                        'color': 'blue',
                        'description': 'Campus operations'
                    })
                    sections.append({
                        'name': 'CRM / Leads', 
                        'icon': 'user-add', 
                        'url': '/crm/', 
                        'color': 'pink',
                        'description': 'Lead management & prospective learners'
                    })
                    if not primary_portal:
                        primary_portal = 'staff'
                
                elif role.code in ['SALES_MANAGER', 'SALES_REP']:
                    sections.append({
                        'name': 'CRM / Leads', 
                        'icon': 'user-add', 
                        'url': '/crm/', 
                        'color': 'pink',
                        'description': 'Lead management, school leavers & sales pipeline'
                    })
                    sections.append({
                        'name': 'Training NOT', 
                        'icon': 'bell', 
                        'url': '/not/', 
                        'color': 'yellow',
                        'description': 'Notification of Training'
                    })
                    if not primary_portal:
                        primary_portal = 'staff'
                
                elif role.code in ['SDF', 'SDF_ADMIN']:
                    sections.append({
                        'name': 'Skills Development', 
                        'icon': 'sparkles', 
                        'url': '/portal/staff/', 
                        'color': 'teal',
                        'description': 'SETA submissions'
                    })
                    if not primary_portal:
                        primary_portal = 'staff'
        
        # Default section if no specific access
        if not sections:
            sections.append({
                'name': 'My Profile', 
                'icon': 'user', 
                'url': '/profile/', 
                'color': 'gray',
                'description': 'View and edit your profile'
            })
            primary_portal = 'profile'
        
        # Remove duplicate sections
        seen_urls = set()
        unique_sections = []
        for section in sections:
            if section['url'] not in seen_urls:
                seen_urls.add(section['url'])
                unique_sections.append(section)
        
        return {
            'sections': unique_sections,
            'roles': roles if roles else ['User'],
            'primary_portal': primary_portal or 'profile',
            'access_level': access_level,
        }
    
    def _get_quick_actions(self, user, access_info):
        """Get context-appropriate quick actions for the user"""
        actions = []
        
        if 'Learner' in access_info['roles']:
            actions.extend([
                {'label': 'View Schedule', 'icon': 'calendar', 'url': '#', 'color': 'blue'},
                {'label': 'Upload Document', 'icon': 'upload', 'url': '#', 'color': 'green'},
                {'label': 'Contact Support', 'icon': 'chat', 'url': '#', 'color': 'purple'},
            ])
        
        if any('Corporate' in r for r in access_info['roles']):
            actions.extend([
                {'label': 'Add Employee', 'icon': 'user-add', 'url': '#', 'color': 'blue'},
                {'label': 'Request Quote', 'icon': 'document', 'url': '#', 'color': 'green'},
            ])
        
        if access_info['access_level'] in ['SYSTEM', 'HEAD_OFFICE', 'BRAND']:
            actions.extend([
                {'label': 'New Enrollment', 'icon': 'plus', 'url': '/admin/academics/enrollment/add/', 'color': 'green'},
                {'label': 'View Reports', 'icon': 'chart-bar', 'url': '/admin/reporting/', 'color': 'blue'},
            ])
        
        return actions[:4]  # Max 4 quick actions
    
    def _get_recent_activity(self, user):
        """Get user's recent activity"""
        # Placeholder - would be populated from audit logs
        return []
    
    def _get_notifications(self, user):
        """Get unread notifications"""
        from portals.models import Notification
        return Notification.objects.filter(
            user=user,
            is_read=False
        ).order_by('-created_at')[:5]


def sso_logout(request):
    """Log out and redirect to login page"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('core:login')


@login_required
def profile_view(request):
    """User profile view"""
    context = {'user': request.user}
    
    # Try to get staff profile for HR information
    try:
        from hr.models import StaffProfile
        staff_profile = StaffProfile.objects.select_related(
            'position', 'department', 'reports_to__user'
        ).prefetch_related(
            'position__tasks'
        ).get(user=request.user)
        context['staff_profile'] = staff_profile
        
        # Get position tasks (KPIs) if staff has a position
        if staff_profile.position:
            context['position_tasks'] = staff_profile.position.tasks.filter(is_active=True).order_by('-priority', 'title')
    except:
        pass
    
    return render(request, 'auth/profile.html', context)
