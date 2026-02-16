"""
Quick Data Capture Views

Streamlined forms for fast data entry:
- Bulk assessment marking
- Attendance capture
- Learning plan creation
- Stipend management
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, View
from django.http import JsonResponse
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse
from datetime import date, timedelta
from decimal import Decimal
import json

from learners.models import Learner
from academics.models import Enrollment, Module
from assessments.models import AssessmentActivity, AssessmentResult
from logistics.models import Cohort, ScheduleSession, Attendance
from core.tasks import (
    Task, TaskCategory, TaskStatus,
    StipendType, StipendAllocation, StipendPayment,
    LearningPlan, LearningPlanModule, LearningPlanMilestone
)


# =====================================================
# BULK ASSESSMENT MARKING
# =====================================================

class BulkMarkEntryView(LoginRequiredMixin, TemplateView):
    """
    Quick bulk mark entry for an assessment activity.
    Shows all learners in a cohort for rapid grading.
    """
    template_name = 'capture/bulk_marks.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        cohort_id = self.request.GET.get('cohort')
        activity_id = self.request.GET.get('activity')
        
        # Get facilitator's cohorts
        user = self.request.user
        cohorts = Cohort.objects.filter(
            Q(facilitator=user),
            status__in=['ACTIVE', 'OPEN']
        ).select_related('qualification')
        context['cohorts'] = cohorts
        
        # If cohort selected, get activities
        if cohort_id:
            cohort = get_object_or_404(Cohort, pk=cohort_id)
            context['selected_cohort'] = cohort
            
            # Get activities for this qualification
            activities = AssessmentActivity.objects.filter(
                module__qualification=cohort.qualification,
                is_active=True
            ).select_related('module')
            context['activities'] = activities
            
            # If activity selected, get learners and existing results
            if activity_id:
                activity = get_object_or_404(AssessmentActivity, pk=activity_id)
                context['selected_activity'] = activity
                
                # Get enrollments in this cohort
                enrollments = Enrollment.objects.filter(
                    cohort=cohort,
                    status__in=['ACTIVE', 'ENROLLED']
                ).select_related('learner').order_by('learner__last_name')
                
                # Get existing results
                existing_results = {
                    r.enrollment_id: r
                    for r in AssessmentResult.objects.filter(
                        enrollment__in=enrollments,
                        activity=activity
                    )
                }
                
                # Build learner data
                learner_data = []
                for enrollment in enrollments:
                    result = existing_results.get(enrollment.id)
                    learner_data.append({
                        'enrollment': enrollment,
                        'learner': enrollment.learner,
                        'existing_result': result,
                    })
                context['learner_data'] = learner_data
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Process bulk mark submission"""
        activity_id = request.POST.get('activity_id')
        activity = get_object_or_404(AssessmentActivity, pk=activity_id)
        
        saved_count = 0
        errors = []
        
        # Process each learner
        enrollment_ids = request.POST.getlist('enrollment_ids')
        for enrollment_id in enrollment_ids:
            result_code = request.POST.get(f'result_{enrollment_id}')
            score = request.POST.get(f'score_{enrollment_id}')
            feedback = request.POST.get(f'feedback_{enrollment_id}', '')
            
            if result_code:
                try:
                    enrollment = Enrollment.objects.get(pk=enrollment_id)
                    
                    # Get or create result
                    result, created = AssessmentResult.objects.get_or_create(
                        enrollment=enrollment,
                        activity=activity,
                        defaults={
                            'assessor': request.user,
                            'result': result_code,
                            'percentage_score': Decimal(score) if score else None,
                            'feedback': feedback,
                            'assessment_date': timezone.now().date(),
                            'status': 'PENDING_MOD',
                        }
                    )
                    
                    if not created:
                        result.result = result_code
                        result.percentage_score = Decimal(score) if score else None
                        result.feedback = feedback
                        result.assessor = request.user
                        result.assessment_date = timezone.now().date()
                        result.status = 'PENDING_MOD'
                        result.save()
                    
                    saved_count += 1
                except Exception as e:
                    errors.append(f'Error saving result for enrollment {enrollment_id}: {str(e)}')
        
        if saved_count:
            messages.success(request, f'Successfully saved {saved_count} assessment results.')
        if errors:
            for error in errors[:5]:
                messages.error(request, error)
        
        return redirect(request.META.get('HTTP_REFERER', 'core:task_hub'))


class QuickMarkView(LoginRequiredMixin, View):
    """
    Quick single learner mark entry (inline from task list)
    """
    def post(self, request, pk):
        result = get_object_or_404(AssessmentResult, pk=pk)
        
        result_code = request.POST.get('result')
        score = request.POST.get('score')
        feedback = request.POST.get('feedback', '')
        
        if result_code in ['C', 'NYC', 'ABS', 'DEF']:
            result.result = result_code
            result.percentage_score = Decimal(score) if score else None
            result.feedback = feedback
            result.assessor = request.user
            result.assessment_date = timezone.now().date()
            result.status = 'PENDING_MOD' if result_code in ['C', 'NYC'] else 'COMPLETED'
            result.save()
            
            # Complete related task
            Task.objects.filter(
                object_id=pk,
                category=TaskCategory.ASSESSMENT_MARK,
                status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
            ).update(status=TaskStatus.COMPLETED, completed_at=timezone.now())
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Result saved'})
            messages.success(request, 'Assessment result saved')
        
        return redirect(request.META.get('HTTP_REFERER', 'core:task_hub'))


# =====================================================
# ATTENDANCE CAPTURE
# =====================================================

class AttendanceCaptureView(LoginRequiredMixin, TemplateView):
    """
    Quick attendance capture for a session.
    Supports manual checkbox and QR code options.
    """
    template_name = 'capture/attendance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session_id = self.kwargs.get('session_id')
        
        if session_id:
            session = get_object_or_404(ScheduleSession, pk=session_id)
            context['session'] = session
            
            # Get learners in this cohort
            enrollments = Enrollment.objects.filter(
                cohort=session.cohort,
                status__in=['ACTIVE', 'ENROLLED']
            ).select_related('learner').order_by('learner__last_name')
            
            # Get existing attendance records
            existing_attendance = {
                a.enrollment_id: a
                for a in Attendance.objects.filter(session=session)
            }
            
            # Build attendance data
            attendance_data = []
            for enrollment in enrollments:
                existing = existing_attendance.get(enrollment.id)
                attendance_data.append({
                    'enrollment': enrollment,
                    'learner': enrollment.learner,
                    'existing': existing,
                })
            context['attendance_data'] = attendance_data
            context['status_choices'] = Attendance.STATUS_CHOICES
        else:
            # Show list of sessions needing attendance
            user = self.request.user
            today = timezone.now().date()
            
            sessions = ScheduleSession.objects.filter(
                Q(facilitator=user) | Q(cohort__facilitator=user),
                date__lte=today,
                is_cancelled=False
            ).select_related('cohort', 'module', 'venue').order_by('-date')[:20]
            
            # Check which have attendance
            for session in sessions:
                session.has_attendance = session.attendance_records.exists()
            
            context['sessions'] = sessions
        
        return context
    
    def post(self, request, session_id, *args, **kwargs):
        """Process attendance submission"""
        session = get_object_or_404(ScheduleSession, pk=session_id)
        
        saved_count = 0
        enrollment_ids = request.POST.getlist('enrollment_ids')
        
        for enrollment_id in enrollment_ids:
            status = request.POST.get(f'status_{enrollment_id}', 'ABSENT')
            notes = request.POST.get(f'notes_{enrollment_id}', '')
            
            try:
                enrollment = Enrollment.objects.get(pk=enrollment_id)
                
                attendance, created = Attendance.objects.update_or_create(
                    session=session,
                    enrollment=enrollment,
                    defaults={
                        'status': status,
                        'check_in_method': 'MANUAL',
                        'check_in_time': timezone.now() if status == 'PRESENT' else None,
                        'recorded_by': request.user,
                        'notes': notes,
                    }
                )
                saved_count += 1
            except Exception as e:
                messages.error(request, f'Error saving attendance: {str(e)}')
        
        # Complete related task
        Task.objects.filter(
            object_id=session_id,
            category=TaskCategory.ATTENDANCE_CAPTURE,
            status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        ).update(status=TaskStatus.COMPLETED, completed_at=timezone.now())
        
        messages.success(request, f'Attendance saved for {saved_count} learners.')
        return redirect('capture:attendance_list')


class AttendanceQRView(LoginRequiredMixin, View):
    """
    QR code attendance check-in
    """
    def get(self, request, session_id):
        session = get_object_or_404(ScheduleSession, pk=session_id)
        
        # Generate QR code if not exists
        if not session.qr_code:
            session.generate_qr_code()
        
        # Return QR code data
        qr_data = {
            'session_id': session.id,
            'qr_code': session.qr_code,
            'date': str(session.date),
            'module': session.module.title,
            'cohort': session.cohort.code,
        }
        
        return JsonResponse(qr_data)
    
    def post(self, request, session_id):
        """Process QR check-in"""
        session = get_object_or_404(ScheduleSession, pk=session_id)
        
        # Get learner from QR scan
        learner_id = request.POST.get('learner_id')
        qr_code = request.POST.get('qr_code')
        
        # Verify QR code
        if qr_code != session.qr_code:
            return JsonResponse({'success': False, 'error': 'Invalid QR code'}, status=400)
        
        # Find enrollment
        enrollment = Enrollment.objects.filter(
            learner_id=learner_id,
            cohort=session.cohort
        ).first()
        
        if not enrollment:
            return JsonResponse({'success': False, 'error': 'Learner not enrolled in this cohort'}, status=400)
        
        # Record attendance
        attendance, created = Attendance.objects.update_or_create(
            session=session,
            enrollment=enrollment,
            defaults={
                'status': 'PRESENT',
                'check_in_method': 'QR',
                'check_in_time': timezone.now(),
                'recorded_by': request.user,
            }
        )
        
        return JsonResponse({
            'success': True,
            'learner': f'{enrollment.learner.first_name} {enrollment.learner.last_name}',
            'time': timezone.now().strftime('%H:%M:%S')
        })


# =====================================================
# LEARNING PLAN WIZARD
# =====================================================

class LearningPlanWizardView(LoginRequiredMixin, TemplateView):
    """
    Step-by-step learning plan creation
    """
    template_name = 'capture/learning_plan_wizard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enrollment_id = self.kwargs.get('enrollment_id')
        
        if enrollment_id:
            enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
            context['enrollment'] = enrollment
            
            # Check for existing plan
            existing_plan = LearningPlan.objects.filter(enrollment=enrollment).first()
            context['existing_plan'] = existing_plan
            
            # Get modules for this qualification
            modules = Module.objects.filter(
                qualification=enrollment.qualification,
                is_active=True
            ).order_by('code')
            context['modules'] = modules
            
            # Get facilitators
            from core.models import User
            facilitators = User.objects.filter(
                is_active=True,
                user_roles__role__code__in=['FACILITATOR', 'ASSESSOR']
            ).distinct()
            context['facilitators'] = facilitators
            
            # Get venues
            from logistics.models import Venue
            venues = Venue.objects.filter(
                is_active=True,
                campus=enrollment.campus
            ) if enrollment.campus else Venue.objects.filter(is_active=True)
            context['venues'] = venues
        else:
            # Show list of enrollments needing learning plans
            enrollments = Enrollment.objects.filter(
                status__in=['ENROLLED', 'ACTIVE'],
                learning_plan__isnull=True
            ).select_related('learner', 'qualification', 'campus')[:50]
            context['enrollments_without_plan'] = enrollments
        
        return context
    
    def post(self, request, enrollment_id, *args, **kwargs):
        """Create or update learning plan"""
        enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
        
        # Create learning plan
        plan, created = LearningPlan.objects.update_or_create(
            enrollment=enrollment,
            defaults={
                'title': request.POST.get('title', f'Learning Plan - {enrollment.learner}'),
                'objectives': request.POST.get('objectives', ''),
                'learning_style': request.POST.get('learning_style', ''),
                'special_requirements': request.POST.get('special_requirements', ''),
                'start_date': request.POST.get('start_date', enrollment.start_date),
                'target_completion': request.POST.get('target_completion', enrollment.expected_completion),
                'status': 'DRAFT',
                'created_by': request.user,
            }
        )
        
        # Process module schedule
        module_ids = request.POST.getlist('module_ids')
        for i, module_id in enumerate(module_ids):
            planned_start = request.POST.get(f'module_start_{module_id}')
            planned_end = request.POST.get(f'module_end_{module_id}')
            facilitator_id = request.POST.get(f'module_facilitator_{module_id}')
            venue_id = request.POST.get(f'module_venue_{module_id}')
            delivery_mode = request.POST.get(f'module_delivery_{module_id}', 'CONTACT')
            
            if planned_start and planned_end:
                LearningPlanModule.objects.update_or_create(
                    learning_plan=plan,
                    module_id=module_id,
                    defaults={
                        'sequence': i + 1,
                        'planned_start': planned_start,
                        'planned_end': planned_end,
                        'facilitator_id': facilitator_id if facilitator_id else None,
                        'venue_id': venue_id if venue_id else None,
                        'delivery_mode': delivery_mode,
                    }
                )
        
        messages.success(request, f'Learning plan {"created" if created else "updated"} successfully.')
        return redirect('capture:learning_plan_detail', pk=plan.pk)


class LearningPlanDetailView(LoginRequiredMixin, TemplateView):
    """View and manage a learning plan"""
    template_name = 'capture/learning_plan_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan = get_object_or_404(LearningPlan, pk=self.kwargs.get('pk'))
        context['plan'] = plan
        context['modules'] = plan.modules.select_related('module', 'facilitator', 'venue').order_by('sequence')
        context['milestones'] = plan.milestones.order_by('target_date')
        return context


# =====================================================
# STIPEND MANAGEMENT
# =====================================================

class StipendCalculatorView(LoginRequiredMixin, TemplateView):
    """
    Calculate and manage stipend payments
    """
    template_name = 'capture/stipend_calculator.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        cohort_id = self.request.GET.get('cohort')
        month = self.request.GET.get('month')
        year = self.request.GET.get('year')
        
        today = timezone.now().date()
        if not month:
            month = today.month
        if not year:
            year = today.year
        
        context['selected_month'] = int(month)
        context['selected_year'] = int(year)
        
        # Get cohorts with stipend allocations
        cohorts = Cohort.objects.filter(
            status__in=['ACTIVE', 'OPEN']
        ).annotate(
            stipend_count=Count('enrollments__stipend_allocations')
        ).filter(stipend_count__gt=0).select_related('qualification')
        context['cohorts'] = cohorts
        
        if cohort_id:
            cohort = get_object_or_404(Cohort, pk=cohort_id)
            context['selected_cohort'] = cohort
            
            # Get allocations for this cohort
            allocations = StipendAllocation.objects.filter(
                enrollment__cohort=cohort,
                status='ACTIVE'
            ).select_related('enrollment__learner', 'stipend_type')
            
            # Calculate for selected period
            period_start = date(int(year), int(month), 1)
            if int(month) == 12:
                period_end = date(int(year) + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = date(int(year), int(month) + 1, 1) - timedelta(days=1)
            
            # Get attendance for this period
            stipend_data = []
            for allocation in allocations:
                # Get attendance stats
                sessions = ScheduleSession.objects.filter(
                    cohort=cohort,
                    date__range=[period_start, period_end],
                    is_cancelled=False
                )
                total_sessions = sessions.count()
                
                attended = Attendance.objects.filter(
                    enrollment=allocation.enrollment,
                    session__in=sessions,
                    status='PRESENT'
                ).count()
                
                # Check for existing payment
                existing_payment = StipendPayment.objects.filter(
                    allocation=allocation,
                    period_start=period_start,
                    period_end=period_end
                ).first()
                
                # Calculate
                attendance_rate = (attended / total_sessions * 100) if total_sessions > 0 else 100
                calculated_amount = allocation.amount_per_period * (attended / total_sessions) if total_sessions > 0 else allocation.amount_per_period
                
                stipend_data.append({
                    'allocation': allocation,
                    'total_sessions': total_sessions,
                    'attended': attended,
                    'attendance_rate': round(attendance_rate, 1),
                    'base_amount': allocation.amount_per_period,
                    'calculated_amount': round(calculated_amount, 2),
                    'existing_payment': existing_payment,
                })
            
            context['stipend_data'] = stipend_data
            context['period_start'] = period_start
            context['period_end'] = period_end
        
        # Stipend types
        context['stipend_types'] = StipendType.objects.filter(is_active=True)
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Create stipend payments"""
        cohort_id = request.POST.get('cohort_id')
        period_start = request.POST.get('period_start')
        period_end = request.POST.get('period_end')
        
        created_count = 0
        allocation_ids = request.POST.getlist('allocation_ids')
        
        for allocation_id in allocation_ids:
            net_amount = request.POST.get(f'amount_{allocation_id}')
            days_attended = request.POST.get(f'attended_{allocation_id}')
            days_expected = request.POST.get(f'expected_{allocation_id}')
            deductions = request.POST.get(f'deductions_{allocation_id}', '0')
            deduction_reason = request.POST.get(f'deduction_reason_{allocation_id}', '')
            
            if net_amount:
                try:
                    allocation = StipendAllocation.objects.get(pk=allocation_id)
                    
                    payment, created = StipendPayment.objects.update_or_create(
                        allocation=allocation,
                        period_start=period_start,
                        period_end=period_end,
                        defaults={
                            'base_amount': allocation.amount_per_period,
                            'deductions': Decimal(deductions or '0'),
                            'net_amount': Decimal(net_amount),
                            'days_attended': int(days_attended) if days_attended else None,
                            'days_expected': int(days_expected) if days_expected else None,
                            'status': 'PENDING',
                            'deduction_reason': deduction_reason,
                            'created_by': request.user,
                        }
                    )
                    
                    if payment.days_attended and payment.days_expected:
                        payment.attendance_rate = (payment.days_attended / payment.days_expected) * 100
                        payment.save()
                    
                    created_count += 1
                except Exception as e:
                    messages.error(request, f'Error creating payment: {str(e)}')
        
        messages.success(request, f'Created {created_count} stipend payment records.')
        return redirect(request.META.get('HTTP_REFERER', 'capture:stipend_calculator'))


class StipendApprovalView(LoginRequiredMixin, TemplateView):
    """
    Approve stipend payments for processing
    """
    template_name = 'capture/stipend_approval.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get pending payments
        pending = StipendPayment.objects.filter(
            status='PENDING'
        ).select_related(
            'allocation__enrollment__learner',
            'allocation__stipend_type'
        ).order_by('period_start', 'allocation__enrollment__learner__last_name')
        
        context['pending_payments'] = pending
        context['total_pending'] = sum(p.net_amount for p in pending)
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Approve selected payments"""
        payment_ids = request.POST.getlist('payment_ids')
        action = request.POST.get('action', 'approve')
        
        payments = StipendPayment.objects.filter(pk__in=payment_ids)
        
        if action == 'approve':
            payments.update(
                status='APPROVED',
                approved_by=request.user,
                approved_at=timezone.now()
            )
            messages.success(request, f'Approved {len(payment_ids)} payments.')
        elif action == 'reject':
            payments.update(status='CANCELLED')
            messages.info(request, f'Rejected {len(payment_ids)} payments.')
        
        return redirect('capture:stipend_approval')
