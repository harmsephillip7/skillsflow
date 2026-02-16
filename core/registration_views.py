"""
Registration Views - Self-Service User Registration with Access Request
Allows new staff to sign up, request access to sections, and await admin approval.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView, FormView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import timedelta

from .models import (
    AccessRequest, AccessRequestSection, AccessRequestSectionChoice,
    Role, UserRole, User
)
from tenants.models import Brand, Campus


# ==============================================
# PUBLIC REGISTRATION VIEWS
# ==============================================

class SignUpView(TemplateView):
    """
    Public registration page for new staff members.
    Collects profile information and access requests.
    """
    template_name = 'registration/signup.html'
    
    def get(self, request, *args, **kwargs):
        # If already logged in, redirect to dashboard
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get available sections for request
        context['sections'] = AccessRequestSection.objects.filter(is_active=True)
        
        # Get brands and campuses for selection
        context['brands'] = Brand.objects.filter(is_active=True)
        context['campuses'] = Campus.objects.filter(is_active=True).select_related('brand')
        
        # Get available roles (visible ones)
        context['roles'] = Role.objects.filter(
            access_level__in=['CAMPUS', 'BRAND', 'SELF']
        ).exclude(
            code__in=['SUPER_ADMIN', 'SYSTEM_ADMIN']  # Hide admin roles
        )
        
        return context
    
    def post(self, request, *args, **kwargs):
        # Collect form data
        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        employee_number = request.POST.get('employee_number', '').strip()
        job_title = request.POST.get('job_title', '').strip()
        department = request.POST.get('department', '').strip()
        brand_id = request.POST.get('brand')
        campus_id = request.POST.get('campus')
        justification = request.POST.get('justification', '').strip()
        
        # Get selected roles/sections
        selected_roles = request.POST.getlist('roles')
        selected_sections = request.POST.getlist('sections')
        
        # Validation
        errors = []
        
        if not email:
            errors.append('Email is required.')
        elif User.objects.filter(email=email).exists():
            errors.append('An account with this email already exists. Please login instead.')
        elif AccessRequest.objects.filter(email=email, status='PENDING').exists():
            errors.append('A pending registration request for this email already exists.')
        
        if not first_name:
            errors.append('First name is required.')
        if not last_name:
            errors.append('Last name is required.')
        if not password:
            errors.append('Password is required.')
        elif len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        elif password != password_confirm:
            errors.append('Passwords do not match.')
        
        if not selected_roles and not selected_sections:
            errors.append('Please select at least one role or section to request access to.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, self.template_name, {
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone,
                'employee_number': employee_number,
                'job_title': job_title,
                'department': department,
                'brand_id': brand_id,
                'campus_id': campus_id,
                'justification': justification,
                **self.get_context_data()
            })
        
        try:
            with transaction.atomic():
                # Create access request
                access_request = AccessRequest(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    employee_number=employee_number,
                    job_title=job_title,
                    department=department,
                    access_justification=justification,
                    expires_at=timezone.now() + timedelta(days=30)  # 30 day expiry
                )
                
                # Set password (hashed)
                access_request.set_password(password)
                
                # Set brand/campus if selected
                if brand_id:
                    access_request.requested_brand = Brand.objects.get(id=brand_id)
                if campus_id:
                    access_request.requested_campus = Campus.objects.get(id=campus_id)
                
                # Generate verification token
                access_request.generate_verification_token()
                
                access_request.save()
                
                # Add requested roles
                if selected_roles:
                    roles = Role.objects.filter(id__in=selected_roles)
                    access_request.requested_roles.set(roles)
                
                # Add section choices
                if selected_sections:
                    for section_id in selected_sections:
                        try:
                            section = AccessRequestSection.objects.get(id=section_id)
                            AccessRequestSectionChoice.objects.create(
                                access_request=access_request,
                                section=section
                            )
                            # Also add the section's default roles
                            for role in section.default_roles.all():
                                access_request.requested_roles.add(role)
                        except AccessRequestSection.DoesNotExist:
                            pass
                
                messages.success(
                    request,
                    f'Registration request submitted successfully! '
                    f'An administrator will review your request. '
                    f'You will receive an email once your access is approved.'
                )
                
                return redirect('core:signup_success')
                
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, self.template_name, {
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                **self.get_context_data()
            })


class SignUpSuccessView(TemplateView):
    """Success page after submitting registration request."""
    template_name = 'registration/signup_success.html'


class VerifyEmailView(View):
    """Verify email address using token."""
    
    def get(self, request, token):
        try:
            access_request = AccessRequest.objects.get(
                verification_token=token,
                email_verified=False,
                status='PENDING'
            )
            access_request.email_verified = True
            access_request.email_verified_at = timezone.now()
            access_request.save()
            
            messages.success(request, 'Email verified successfully! Your request is awaiting admin approval.')
            return redirect('core:login')
            
        except AccessRequest.DoesNotExist:
            messages.error(request, 'Invalid or expired verification link.')
            return redirect('core:login')


class CheckRequestStatusView(TemplateView):
    """Allow users to check their registration request status."""
    template_name = 'registration/check_status.html'
    
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').strip().lower()
        
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, self.template_name)
        
        try:
            access_request = AccessRequest.objects.get(email=email)
            context = {
                'request_found': True,
                'access_request': access_request
            }
        except AccessRequest.DoesNotExist:
            context = {
                'request_found': False,
                'email': email
            }
        
        return render(request, self.template_name, context)


# ==============================================
# ADMIN ACCESS REQUEST MANAGEMENT VIEWS
# ==============================================

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure user has admin access to manage registrations."""
    
    def test_func(self):
        user = self.request.user
        # Check if user has admin role
        admin_roles = ['SUPER_ADMIN', 'SYSTEM_ADMIN', 'HEAD_OFFICE_ADMIN', 'CAMPUS_ADMIN', 'BRAND_ADMIN']
        return UserRole.objects.filter(
            user=user,
            role__code__in=admin_roles,
            is_active=True
        ).exists() or user.is_superuser


class AccessRequestListView(AdminRequiredMixin, ListView):
    """List all access requests for admin review."""
    model = AccessRequest
    template_name = 'admin/access_requests/list.html'
    context_object_name = 'requests'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = AccessRequest.objects.select_related(
            'requested_brand', 'requested_campus', 'reviewed_by', 'created_user'
        ).prefetch_related('requested_roles', 'section_choices__section')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by brand (for brand admins)
        brand_id = self.request.GET.get('brand')
        if brand_id:
            queryset = queryset.filter(requested_brand_id=brand_id)
        
        # Filter by campus (for campus admins)
        campus_id = self.request.GET.get('campus')
        if campus_id:
            queryset = queryset.filter(requested_campus_id=campus_id)
        
        # Search
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(employee_number__icontains=search)
            )
        
        return queryset.order_by('-requested_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['status_choices'] = AccessRequest.REQUEST_STATUS
        context['brands'] = Brand.objects.filter(is_active=True)
        context['campuses'] = Campus.objects.filter(is_active=True)
        
        # Add counts
        context['pending_count'] = AccessRequest.objects.filter(status='PENDING').count()
        context['under_review_count'] = AccessRequest.objects.filter(status='UNDER_REVIEW').count()
        context['approved_count'] = AccessRequest.objects.filter(status='APPROVED').count()
        context['rejected_count'] = AccessRequest.objects.filter(status='REJECTED').count()
        
        # Current filters
        context['current_status'] = self.request.GET.get('status', '')
        context['current_brand'] = self.request.GET.get('brand', '')
        context['current_campus'] = self.request.GET.get('campus', '')
        context['current_search'] = self.request.GET.get('search', '')
        
        return context


class AccessRequestDetailView(AdminRequiredMixin, DetailView):
    """View and manage a single access request."""
    model = AccessRequest
    template_name = 'admin/access_requests/detail.html'
    context_object_name = 'access_request'
    
    def get_queryset(self):
        return AccessRequest.objects.select_related(
            'requested_brand', 'requested_campus', 
            'approved_brand', 'approved_campus',
            'reviewed_by', 'created_user'
        ).prefetch_related(
            'requested_roles', 'approved_roles', 
            'section_choices__section'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add all roles for modification
        context['all_roles'] = Role.objects.exclude(
            code__in=['SUPER_ADMIN', 'SYSTEM_ADMIN']
        )
        context['brands'] = Brand.objects.filter(is_active=True)
        context['campuses'] = Campus.objects.filter(is_active=True)
        
        return context


class ApproveAccessRequestView(AdminRequiredMixin, View):
    """Approve an access request and create user account."""
    
    def post(self, request, pk):
        access_request = get_object_or_404(AccessRequest, pk=pk)
        
        if access_request.status not in ['PENDING', 'UNDER_REVIEW']:
            messages.error(request, 'This request has already been processed.')
            return redirect('core:access_request_detail', pk=pk)
        
        # Get approved configuration
        notes = request.POST.get('notes', '')
        
        # Get approved roles (admin may have modified)
        approved_role_ids = request.POST.getlist('approved_roles')
        if approved_role_ids:
            approved_roles = Role.objects.filter(id__in=approved_role_ids)
        else:
            approved_roles = access_request.requested_roles.all()
        
        # Get approved brand/campus
        brand_id = request.POST.get('approved_brand')
        campus_id = request.POST.get('approved_campus')
        
        approved_brand = None
        approved_campus = None
        
        if brand_id:
            approved_brand = Brand.objects.get(id=brand_id)
        if campus_id:
            approved_campus = Campus.objects.get(id=campus_id)
        
        try:
            with transaction.atomic():
                user = access_request.approve(
                    reviewer=request.user,
                    approved_roles=approved_roles,
                    approved_brand=approved_brand,
                    approved_campus=approved_campus,
                    notes=notes
                )
                
                messages.success(
                    request,
                    f'Access request approved! User account created for {user.email}.'
                )
                
                # TODO: Send approval notification email
                
        except Exception as e:
            messages.error(request, f'Error approving request: {str(e)}')
        
        return redirect('core:access_request_list')


class RejectAccessRequestView(AdminRequiredMixin, View):
    """Reject an access request."""
    
    def post(self, request, pk):
        access_request = get_object_or_404(AccessRequest, pk=pk)
        
        if access_request.status not in ['PENDING', 'UNDER_REVIEW']:
            messages.error(request, 'This request has already been processed.')
            return redirect('core:access_request_detail', pk=pk)
        
        notes = request.POST.get('notes', '')
        
        try:
            access_request.reject(reviewer=request.user, notes=notes)
            messages.success(
                request,
                f'Access request for {access_request.email} has been rejected.'
            )
            
            # TODO: Send rejection notification email
            
        except Exception as e:
            messages.error(request, f'Error rejecting request: {str(e)}')
        
        return redirect('core:access_request_list')


class MarkUnderReviewView(AdminRequiredMixin, View):
    """Mark a request as under review."""
    
    def post(self, request, pk):
        access_request = get_object_or_404(AccessRequest, pk=pk)
        
        if access_request.status != 'PENDING':
            messages.error(request, 'Only pending requests can be marked as under review.')
            return redirect('core:access_request_detail', pk=pk)
        
        access_request.status = 'UNDER_REVIEW'
        access_request.save()
        
        messages.info(request, f'Request from {access_request.email} is now under review.')
        return redirect('core:access_request_detail', pk=pk)


# ==============================================
# AJAX ENDPOINTS
# ==============================================

def get_campuses_for_brand(request):
    """AJAX endpoint to get campuses for a selected brand."""
    brand_id = request.GET.get('brand_id')
    
    if not brand_id:
        return JsonResponse({'campuses': []})
    
    campuses = Campus.objects.filter(
        brand_id=brand_id,
        is_active=True
    ).values('id', 'name')
    
    return JsonResponse({'campuses': list(campuses)})


def get_request_count_badge(request):
    """AJAX endpoint to get pending request count for nav badge."""
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0})
    
    count = AccessRequest.objects.filter(status='PENDING').count()
    return JsonResponse({'count': count})
