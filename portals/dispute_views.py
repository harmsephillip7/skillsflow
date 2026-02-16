"""
Stipend Dispute Resolution Views

Handles dispute submission, review, escalation, and resolution workflows
for learners, workplace officers, and management.
"""
import json
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.generic import ListView, DetailView, TemplateView

from learners.models import (
    Learner,
    StipendCalculation,
    StipendDispute,
)
from corporate.models import WorkplacePlacement


# ==================== LEARNER VIEWS ====================

@login_required
def student_submit_dispute(request, calculation_id):
    """
    Learner submits a dispute for a stipend calculation.
    """
    learner = Learner.objects.filter(user=request.user).first()
    if not learner:
        return JsonResponse({'error': 'No learner profile'}, status=403)
    
    calculation = get_object_or_404(
        StipendCalculation.objects.select_related('placement'),
        id=calculation_id,
        placement__learner=learner
    )
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        reason = data.get('reason', '').strip()
        if not reason:
            return JsonResponse({'error': 'Dispute reason is required'}, status=400)
        
        # Check if dispute already exists
        existing = StipendDispute.objects.filter(
            stipend_calculation=calculation,
            learner=learner,
            status__in=['PENDING', 'UNDER_REVIEW', 'ESCALATED']
        ).first()
        
        if existing:
            return JsonResponse({
                'error': 'A dispute is already open for this calculation',
                'dispute_id': existing.id
            }, status=400)
        
        # Create dispute
        dispute = StipendDispute.objects.create(
            stipend_calculation=calculation,
            learner=learner,
            reason=reason
        )
        
        return JsonResponse({
            'success': True,
            'dispute_id': dispute.id,
            'message': 'Dispute submitted successfully. You will receive a response within 3 working days.'
        })
    
    # GET request - show form
    context = {
        'learner': learner,
        'calculation': calculation,
    }
    return render(request, 'portals/student/dispute_submit.html', context)


class StudentDisputeListView(LoginRequiredMixin, ListView):
    """
    View all disputes submitted by the learner.
    """
    template_name = 'portals/student/dispute_list.html'
    context_object_name = 'disputes'
    paginate_by = 20
    
    def get_queryset(self):
        learner = Learner.objects.filter(user=self.request.user).first()
        if not learner:
            return StipendDispute.objects.none()
        
        return StipendDispute.objects.filter(
            learner=learner
        ).select_related(
            'stipend_calculation__placement',
            'reviewed_by',
            'escalated_to'
        ).order_by('-submitted_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        learner = Learner.objects.filter(user=self.request.user).first()
        context['learner'] = learner
        
        if learner:
            # Summary stats
            context['stats'] = {
                'pending': StipendDispute.objects.filter(learner=learner, status='PENDING').count(),
                'under_review': StipendDispute.objects.filter(learner=learner, status='UNDER_REVIEW').count(),
                'resolved': StipendDispute.objects.filter(learner=learner, status='RESOLVED').count(),
                'escalated': StipendDispute.objects.filter(learner=learner, status='ESCALATED').count(),
            }
        
        return context


class StudentDisputeDetailView(LoginRequiredMixin, DetailView):
    """
    View details of a specific dispute.
    """
    template_name = 'portals/student/dispute_detail.html'
    context_object_name = 'dispute'
    
    def get_queryset(self):
        learner = Learner.objects.filter(user=self.request.user).first()
        if not learner:
            return StipendDispute.objects.none()
        
        return StipendDispute.objects.filter(
            learner=learner
        ).select_related(
            'stipend_calculation__placement',
            'reviewed_by',
            'escalated_to'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        learner = Learner.objects.filter(user=self.request.user).first()
        context['learner'] = learner
        return context


# ==================== OFFICER VIEWS ====================

class OfficerDisputeListView(LoginRequiredMixin, ListView):
    """
    Workplace officer view of all disputes requiring review.
    """
    template_name = 'portals/officer/dispute_list.html'
    context_object_name = 'disputes'
    paginate_by = 30
    
    def get_queryset(self):
        # Officers can see all disputes (or filter by campus if needed)
        status_filter = self.request.GET.get('status', 'pending')
        
        qs = StipendDispute.objects.select_related(
            'learner',
            'stipend_calculation__placement__campus',
            'reviewed_by',
            'escalated_to'
        ).order_by('-submitted_at')
        
        if status_filter == 'pending':
            qs = qs.filter(status='PENDING')
        elif status_filter == 'under_review':
            qs = qs.filter(status='UNDER_REVIEW')
        elif status_filter == 'escalated':
            qs = qs.filter(status='ESCALATED')
        elif status_filter == 'resolved':
            qs = qs.filter(status='RESOLVED')
        elif status_filter == 'overdue':
            # SLA overdue
            qs = qs.filter(status='PENDING')
            # Filter in Python since we need to call property
            disputes = list(qs)
            return [d for d in disputes if d.is_overdue]
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', 'pending')
        
        # Summary stats
        context['stats'] = {
            'pending': StipendDispute.objects.filter(status='PENDING').count(),
            'under_review': StipendDispute.objects.filter(status='UNDER_REVIEW').count(),
            'escalated': StipendDispute.objects.filter(status='ESCALATED').count(),
            'resolved': StipendDispute.objects.filter(status='RESOLVED').count(),
            'overdue': len([d for d in StipendDispute.objects.filter(status='PENDING') if d.is_overdue]),
        }
        
        return context


class OfficerDisputeDetailView(LoginRequiredMixin, DetailView):
    """
    Officer detail view with response/escalation options.
    """
    template_name = 'portals/officer/dispute_detail.html'
    context_object_name = 'dispute'
    model = StipendDispute
    
    def get_queryset(self):
        return StipendDispute.objects.select_related(
            'learner',
            'stipend_calculation__placement__learner',
            'stipend_calculation__placement__campus',
            'reviewed_by',
            'escalated_to'
        )


@login_required
def officer_dispute_respond(request, dispute_id):
    """
    Officer responds to a dispute (resolve or escalate).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    dispute = get_object_or_404(StipendDispute, id=dispute_id)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    action = data.get('action')  # 'resolve' or 'escalate'
    response_text = data.get('response', '').strip()
    
    if not response_text:
        return JsonResponse({'error': 'Response is required'}, status=400)
    
    with transaction.atomic():
        if action == 'resolve':
            dispute.status = 'RESOLVED'
            dispute.response = response_text
            dispute.reviewed_by = request.user
            dispute.reviewed_at = timezone.now()
            dispute.resolution = response_text
            dispute.save()
            
            message = 'Dispute resolved successfully'
            
        elif action == 'escalate':
            # Get escalation recipient (could be configurable)
            escalate_to_user_id = data.get('escalate_to')
            if escalate_to_user_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                escalate_to = User.objects.get(id=escalate_to_user_id)
            else:
                escalate_to = None
            
            dispute.status = 'ESCALATED'
            dispute.response = response_text
            dispute.reviewed_by = request.user
            dispute.reviewed_at = timezone.now()
            dispute.escalated_to = escalate_to
            dispute.escalated_at = timezone.now()
            dispute.save()
            
            message = 'Dispute escalated to management'
            
        elif action == 'under_review':
            dispute.status = 'UNDER_REVIEW'
            dispute.response = response_text
            dispute.reviewed_by = request.user
            dispute.reviewed_at = timezone.now()
            dispute.save()
            
            message = 'Dispute marked as under review'
            
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
    
    return JsonResponse({
        'success': True,
        'message': message,
        'new_status': dispute.status
    })


@login_required
def officer_dispute_bulk_action(request):
    """
    Bulk actions on multiple disputes.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    dispute_ids = data.get('dispute_ids', [])
    action = data.get('action')  # 'mark_under_review', 'escalate_all'
    
    if not dispute_ids:
        return JsonResponse({'error': 'No disputes selected'}, status=400)
    
    disputes = StipendDispute.objects.filter(id__in=dispute_ids)
    
    with transaction.atomic():
        if action == 'mark_under_review':
            updated = disputes.update(
                status='UNDER_REVIEW',
                reviewed_by=request.user,
                reviewed_at=timezone.now()
            )
            message = f'{updated} dispute(s) marked as under review'
            
        elif action == 'assign_to_me':
            updated = disputes.update(
                reviewed_by=request.user,
                reviewed_at=timezone.now()
            )
            message = f'{updated} dispute(s) assigned to you'
            
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
    
    return JsonResponse({
        'success': True,
        'message': message,
        'count': updated
    })
