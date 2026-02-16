"""
HR Admin Views for SkillsFlow ERP
Custom admin views for managing HR models with unified Tailwind theme
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Count, Q
from django import forms

from .models import (
    Department, Position, PositionTask, StaffProfile,
    StaffPositionHistory, StaffTaskAssignment, PerformanceReview
)
from core.models import User


class StaffRequiredMixin(UserPassesTestMixin):
    """Require staff or superuser status"""
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


# =====================================================
# DEPARTMENT VIEWS
# =====================================================

class DepartmentListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    """List all departments"""
    model = Department
    template_name = 'admin/hr/department_list.html'
    context_object_name = 'departments'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Department.objects.filter(is_deleted=False).select_related('parent', 'head__user')
        queryset = queryset.annotate(staff_count=Count('staff_members', filter=Q(staff_members__is_deleted=False)))
        
        # Search
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset.order_by('sort_order', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['total_count'] = Department.objects.filter(is_deleted=False).count()
        return context


class DepartmentDetailView(LoginRequiredMixin, StaffRequiredMixin, DetailView):
    """View department details"""
    model = Department
    template_name = 'admin/hr/department_detail.html'
    context_object_name = 'department'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_members'] = self.object.staff_members.filter(is_deleted=False).select_related('user', 'position')
        context['sub_departments'] = self.object.children.filter(is_deleted=False)
        context['positions'] = self.object.positions.filter(is_deleted=False)
        return context


class DepartmentForm(forms.ModelForm):
    """Form for Department"""
    class Meta:
        model = Department
        fields = ['code', 'name', 'description', 'parent', 'head', 'is_active', 'sort_order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class DepartmentCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Create a new department"""
    model = Department
    form_class = DepartmentForm
    template_name = 'admin/hr/department_form.html'
    success_url = reverse_lazy('hr_admin:department_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Department "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class DepartmentUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Update a department"""
    model = Department
    form_class = DepartmentForm
    template_name = 'admin/hr/department_form.html'
    success_url = reverse_lazy('hr_admin:department_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Department "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class DepartmentDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    """Delete a department (soft delete)"""
    model = Department
    template_name = 'admin/hr/department_confirm_delete.html'
    success_url = reverse_lazy('hr_admin:department_list')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete(request.user)
        messages.success(request, f'Department "{self.object.name}" deleted successfully.')
        return redirect(self.success_url)


# =====================================================
# POSITION VIEWS
# =====================================================

class PositionListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    """List all positions"""
    model = Position
    template_name = 'admin/hr/position_list.html'
    context_object_name = 'positions'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Position.objects.filter(is_deleted=False).select_related('department', 'reports_to')
        queryset = queryset.annotate(staff_count=Count('staff_members', filter=Q(staff_members__is_deleted=False)))
        
        # Search
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(code__icontains=search) |
                Q(job_description_text__icontains=search)
            )
        
        # Filter by department
        department = self.request.GET.get('department', '')
        if department:
            queryset = queryset.filter(department_id=department)
        
        return queryset.order_by('department__name', 'title')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['department_filter'] = self.request.GET.get('department', '')
        context['departments'] = Department.objects.filter(is_deleted=False, is_active=True)
        context['total_count'] = Position.objects.filter(is_deleted=False).count()
        return context


class PositionDetailView(LoginRequiredMixin, StaffRequiredMixin, DetailView):
    """View position details"""
    model = Position
    template_name = 'admin/hr/position_detail.html'
    context_object_name = 'position'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tasks'] = self.object.tasks.filter(is_deleted=False).order_by('sort_order', '-priority')
        context['staff_members'] = self.object.staff_members.filter(is_deleted=False).select_related('user')
        return context


class PositionForm(forms.ModelForm):
    """Form for Position"""
    class Meta:
        model = Position
        fields = [
            'code', 'title', 'department', 'reports_to',
            'job_description', 'job_description_text',
            'minimum_qualifications', 'preferred_qualifications', 'experience_required',
            'salary_band', 'salary_min', 'salary_max',
            'is_active'
        ]
        widgets = {
            'job_description_text': forms.Textarea(attrs={'rows': 5}),
            'minimum_qualifications': forms.Textarea(attrs={'rows': 3}),
            'preferred_qualifications': forms.Textarea(attrs={'rows': 3}),
        }


class PositionCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Create a new position"""
    model = Position
    form_class = PositionForm
    template_name = 'admin/hr/position_form.html'
    success_url = reverse_lazy('hr_admin:position_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Position "{form.instance.title}" created successfully.')
        return super().form_valid(form)


class PositionUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Update a position"""
    model = Position
    form_class = PositionForm
    template_name = 'admin/hr/position_form.html'
    success_url = reverse_lazy('hr_admin:position_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Position "{form.instance.title}" updated successfully.')
        return super().form_valid(form)


class PositionDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    """Delete a position (soft delete)"""
    model = Position
    template_name = 'admin/hr/position_confirm_delete.html'
    success_url = reverse_lazy('hr_admin:position_list')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete(request.user)
        messages.success(request, f'Position "{self.object.title}" deleted successfully.')
        return redirect(self.success_url)


# =====================================================
# STAFF PROFILE VIEWS
# =====================================================

class StaffProfileListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    """List all staff profiles"""
    model = StaffProfile
    template_name = 'admin/hr/staff_list.html'
    context_object_name = 'staff_profiles'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = StaffProfile.objects.filter(is_deleted=False).select_related(
            'user', 'position', 'department', 'reports_to__user'
        )
        
        # Search
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(employee_number__icontains=search)
            )
        
        # Filter by department
        department = self.request.GET.get('department', '')
        if department:
            queryset = queryset.filter(department_id=department)
        
        # Filter by status
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(employment_status=status)
        
        return queryset.order_by('user__last_name', 'user__first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['department_filter'] = self.request.GET.get('department', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['departments'] = Department.objects.filter(is_deleted=False, is_active=True)
        context['status_choices'] = StaffProfile.EMPLOYMENT_STATUS_CHOICES
        context['total_count'] = StaffProfile.objects.filter(is_deleted=False).count()
        return context


class StaffProfileDetailView(LoginRequiredMixin, StaffRequiredMixin, DetailView):
    """View staff profile details"""
    model = StaffProfile
    template_name = 'admin/hr/staff_detail.html'
    context_object_name = 'staff'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['position_history'] = self.object.get_position_history()
        context['direct_reports'] = self.object.get_direct_reports()
        context['task_assignments'] = self.object.task_assignments.filter(is_deleted=False).order_by('-period_start')[:10]
        context['performance_reviews'] = self.object.performance_reviews.filter(is_deleted=False).order_by('-review_period_end')[:5]
        return context


class StaffProfileForm(forms.ModelForm):
    """Form for StaffProfile"""
    class Meta:
        model = StaffProfile
        fields = [
            'user', 'employee_number', 'position', 'department', 'reports_to',
            'employment_type', 'employment_status',
            'date_joined', 'probation_end_date', 'termination_date',
            'current_salary', 'notes'
        ]
        widgets = {
            'date_joined': forms.DateInput(attrs={'type': 'date'}),
            'probation_end_date': forms.DateInput(attrs={'type': 'date'}),
            'termination_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class StaffProfileCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Create a new staff profile"""
    model = StaffProfile
    form_class = StaffProfileForm
    template_name = 'admin/hr/staff_form.html'
    success_url = reverse_lazy('hr_admin:staff_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Staff profile for "{form.instance.user.get_full_name()}" created successfully.')
        return super().form_valid(form)


class StaffProfileUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Update a staff profile"""
    model = StaffProfile
    form_class = StaffProfileForm
    template_name = 'admin/hr/staff_form.html'
    success_url = reverse_lazy('hr_admin:staff_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Staff profile for "{form.instance.user.get_full_name()}" updated successfully.')
        return super().form_valid(form)


class StaffProfileDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    """Delete a staff profile (soft delete)"""
    model = StaffProfile
    template_name = 'admin/hr/staff_confirm_delete.html'
    success_url = reverse_lazy('hr_admin:staff_list')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete(request.user)
        messages.success(request, f'Staff profile for "{self.object.user.get_full_name()}" deleted successfully.')
        return redirect(self.success_url)


# =====================================================
# POSITION TASK VIEWS
# =====================================================

class PositionTaskForm(forms.ModelForm):
    """Form for PositionTask"""
    class Meta:
        model = PositionTask
        fields = ['position', 'title', 'description', 'priority', 'weight', 'frequency', 'sort_order', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class PositionTaskCreateView(LoginRequiredMixin, StaffRequiredMixin, CreateView):
    """Create a new task for a position"""
    model = PositionTask
    form_class = PositionTaskForm
    template_name = 'admin/hr/task_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        position_id = self.request.GET.get('position')
        if position_id:
            initial['position'] = position_id
        return initial
    
    def get_success_url(self):
        return reverse_lazy('hr_admin:position_detail', kwargs={'pk': self.object.position_id})
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Task "{form.instance.title}" created successfully.')
        return super().form_valid(form)


class PositionTaskUpdateView(LoginRequiredMixin, StaffRequiredMixin, UpdateView):
    """Update a position task"""
    model = PositionTask
    form_class = PositionTaskForm
    template_name = 'admin/hr/task_form.html'
    
    def get_success_url(self):
        return reverse_lazy('hr_admin:position_detail', kwargs={'pk': self.object.position_id})
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Task "{form.instance.title}" updated successfully.')
        return super().form_valid(form)


class PositionTaskDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
    """Delete a position task (soft delete)"""
    model = PositionTask
    template_name = 'admin/hr/task_confirm_delete.html'
    
    def get_success_url(self):
        return reverse_lazy('hr_admin:position_detail', kwargs={'pk': self.object.position_id})
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        position_id = self.object.position_id
        self.object.soft_delete(request.user)
        messages.success(request, f'Task "{self.object.title}" deleted successfully.')
        return redirect(reverse_lazy('hr_admin:position_detail', kwargs={'pk': position_id}))


# =====================================================
# ORG CHART VIEW
# =====================================================

from django.http import JsonResponse
from django.views import View

class OrgChartView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    """Display interactive organization chart"""
    model = StaffProfile
    template_name = 'admin/hr/org_chart.html'
    context_object_name = 'staff_profiles'
    
    def get_queryset(self):
        return StaffProfile.objects.filter(
            is_deleted=False,
            employment_status='ACTIVE'
        ).select_related(
            'user', 'position', 'department', 'reports_to', 'reports_to__user',
            'primary_work_location'
        ).order_by('user__last_name', 'user__first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Build org chart data structure
        context['org_data'] = self._build_org_tree()
        context['departments'] = Department.objects.filter(is_deleted=False).order_by('name')
        
        # Stats
        all_staff = self.get_queryset()
        context['total_staff'] = all_staff.count()
        context['without_manager'] = all_staff.filter(reports_to__isnull=True).count()
        context['without_location'] = all_staff.filter(primary_work_location__isnull=True).count()
        
        return context
    
    def _build_org_tree(self):
        """Build hierarchical org chart data for D3.js"""
        import json
        
        staff = self.get_queryset()
        
        # Create nodes dictionary
        nodes = {}
        for s in staff:
            nodes[s.id] = {
                'id': s.id,
                'name': s.user.get_full_name(),
                'title': s.position.title if s.position else 'No Position',
                'department': s.department.name if s.department else 'No Department',
                'location': s.primary_work_location.name if s.primary_work_location else None,
                'reports_to_id': s.reports_to_id,
                'image': None,  # Could add profile image URL
                'children': []
            }
        
        # Build tree structure
        roots = []
        for node_id, node in nodes.items():
            parent_id = node['reports_to_id']
            if parent_id and parent_id in nodes:
                nodes[parent_id]['children'].append(node)
            else:
                roots.append(node)
        
        # If multiple roots, create a virtual root
        if len(roots) > 1:
            org_data = {
                'id': 0,
                'name': 'Organization',
                'title': '',
                'department': '',
                'location': None,
                'children': roots
            }
        elif len(roots) == 1:
            org_data = roots[0]
        else:
            org_data = {'id': 0, 'name': 'No Staff', 'title': '', 'department': '', 'children': []}
        
        return json.dumps(org_data)


class OrgChartDataView(LoginRequiredMixin, StaffRequiredMixin, View):
    """API endpoint for org chart data"""
    
    def get(self, request):
        """Return org chart data as JSON"""
        staff = StaffProfile.objects.filter(
            is_deleted=False,
            employment_status='ACTIVE'
        ).select_related(
            'user', 'position', 'department', 'reports_to', 'reports_to__user',
            'primary_work_location'
        )
        
        # Filter by department if specified
        department_id = request.GET.get('department')
        if department_id:
            staff = staff.filter(department_id=department_id)
        
        # Build nodes
        nodes = []
        for s in staff:
            nodes.append({
                'id': s.id,
                'name': s.user.get_full_name(),
                'title': s.position.title if s.position else 'No Position',
                'department': s.department.name if s.department else 'No Department',
                'department_id': s.department_id,
                'location': s.primary_work_location.name if s.primary_work_location else None,
                'reports_to_id': s.reports_to_id,
                'email': s.user.email,
            })
        
        return JsonResponse({'nodes': nodes})

