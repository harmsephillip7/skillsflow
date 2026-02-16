"""
Tranche Payment & Evidence Management Views
Handles dashboard, listing, detail views, evidence collection, and QC workflows.
"""

from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Q, F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, TemplateView, FormView
)

from .models import (
    TrainingNotification, TrancheSchedule, TrancheEvidenceRequirement,
    TrancheEvidence, TrancheSubmission, TrancheComment,
    TrancheTemplate, TrancheTemplateItem
)


def get_tranche_stats():
    """Calculate statistics for the tranche dashboard"""
    today = timezone.now().date()
    week_ahead = today + timedelta(days=7)
    month_ahead = today + timedelta(days=30)
    
    active_statuses = [
        'SCHEDULED', 'EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE',
        'PENDING_QC', 'QC_FAILED', 'QC_PASSED', 'SUBMITTED', 'QUERY'
    ]
    
    base_qs = TrancheSchedule.objects.filter(
        is_deleted=False,
        status__in=active_statuses
    )
    
    return {
        'total_active': base_qs.count(),
        'due_today': base_qs.filter(due_date=today).count(),
        'due_this_week': base_qs.filter(due_date__gt=today, due_date__lte=week_ahead).count(),
        'due_this_month': base_qs.filter(due_date__gt=week_ahead, due_date__lte=month_ahead).count(),
        'overdue': base_qs.filter(due_date__lt=today).count(),
        'pending_qc': base_qs.filter(status='PENDING_QC').count(),
        'qc_failed': base_qs.filter(status='QC_FAILED').count(),
        'submitted': base_qs.filter(status='SUBMITTED').count(),
        'with_queries': base_qs.filter(status='QUERY').count(),
        'awaiting_payment': TrancheSchedule.objects.filter(
            is_deleted=False,
            status__in=['APPROVED', 'INVOICED']
        ).count(),
        'total_value_pending': base_qs.aggregate(total=Sum('amount'))['total'] or 0,
    }


class TrancheDashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard for tranche payment management"""
    template_name = 'tranches/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        week_ahead = today + timedelta(days=7)
        month_ahead = today + timedelta(days=30)
        
        # Stats
        context['stats'] = get_tranche_stats()
        
        # Due today - urgent action required
        context['due_today'] = TrancheSchedule.objects.filter(
            is_deleted=False,
            due_date=today,
            status__in=['SCHEDULED', 'EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE']
        ).select_related('training_notification')[:10]
        
        # Overdue tranches
        context['overdue_tranches'] = TrancheSchedule.objects.filter(
            is_deleted=False,
            due_date__lt=today,
            status__in=['SCHEDULED', 'EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE', 'PENDING_QC', 'QC_FAILED']
        ).select_related('training_notification').order_by('due_date')[:10]
        
        # Due this week
        context['due_this_week'] = TrancheSchedule.objects.filter(
            is_deleted=False,
            due_date__gt=today,
            due_date__lte=week_ahead,
            status__in=['SCHEDULED', 'EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE']
        ).select_related('training_notification').order_by('due_date')[:10]
        
        # Pending QC
        context['pending_qc'] = TrancheSchedule.objects.filter(
            is_deleted=False,
            status='PENDING_QC'
        ).select_related('training_notification').order_by('due_date')[:10]
        
        # QC Failed - rework required
        context['qc_failed'] = TrancheSchedule.objects.filter(
            is_deleted=False,
            status='QC_FAILED'
        ).select_related('training_notification').order_by('due_date')[:10]
        
        # Funder queries
        context['funder_queries'] = TrancheSchedule.objects.filter(
            is_deleted=False,
            status='QUERY'
        ).select_related('training_notification').order_by('submitted_to_funder_date')[:10]
        
        # Recent submissions
        context['recent_submissions'] = TrancheSubmission.objects.filter(
            tranche__is_deleted=False
        ).select_related('tranche', 'tranche__training_notification').order_by('-submission_date')[:10]
        
        # Upcoming calendar - next 30 days
        context['upcoming_calendar'] = TrancheSchedule.objects.filter(
            is_deleted=False,
            due_date__gte=today,
            due_date__lte=month_ahead,
            status__in=['SCHEDULED', 'EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE', 'PENDING_QC']
        ).select_related('training_notification').order_by('due_date')[:20]
        
        # By funder type breakdown
        context['by_funder'] = TrancheSchedule.objects.filter(
            is_deleted=False,
            status__in=['SCHEDULED', 'EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE', 'PENDING_QC', 'SUBMITTED']
        ).values('training_notification__funder').annotate(
            count=Count('id'),
            total_value=Sum('amount')
        ).order_by('-count')
        
        # By project type breakdown
        context['by_project_type'] = TrancheSchedule.objects.filter(
            is_deleted=False,
            status__in=['SCHEDULED', 'EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE', 'PENDING_QC', 'SUBMITTED']
        ).values('training_notification__project_type').annotate(
            count=Count('id'),
            total_value=Sum('amount')
        ).order_by('-count')
        
        return context


class TrancheListView(LoginRequiredMixin, ListView):
    """List all tranches with filtering"""
    model = TrancheSchedule
    template_name = 'tranches/list.html'
    context_object_name = 'tranches'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = TrancheSchedule.objects.filter(
            is_deleted=False
        ).select_related(
            'training_notification', 'training_notification__qualification'
        ).order_by('due_date')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by tranche type
        tranche_type = self.request.GET.get('type')
        if tranche_type:
            queryset = queryset.filter(tranche_type=tranche_type)
        
        # Filter by funder
        funder = self.request.GET.get('funder')
        if funder:
            queryset = queryset.filter(training_notification__funder=funder)
        
        # Filter by project type
        project_type = self.request.GET.get('project_type')
        if project_type:
            queryset = queryset.filter(training_notification__project_type=project_type)
        
        # Filter by NOT reference
        not_ref = self.request.GET.get('not')
        if not_ref:
            queryset = queryset.filter(training_notification__reference_number__icontains=not_ref)
        
        # Filter by due date range
        due_from = self.request.GET.get('due_from')
        due_to = self.request.GET.get('due_to')
        if due_from:
            queryset = queryset.filter(due_date__gte=due_from)
        if due_to:
            queryset = queryset.filter(due_date__lte=due_to)
        
        # Quick filters
        quick_filter = self.request.GET.get('quick')
        today = timezone.now().date()
        if quick_filter == 'overdue':
            queryset = queryset.filter(
                due_date__lt=today,
                status__in=['SCHEDULED', 'EVIDENCE_COLLECTION', 'EVIDENCE_COMPLETE', 'PENDING_QC', 'QC_FAILED']
            )
        elif quick_filter == 'due_today':
            queryset = queryset.filter(due_date=today)
        elif quick_filter == 'due_week':
            queryset = queryset.filter(
                due_date__gt=today,
                due_date__lte=today + timedelta(days=7)
            )
        elif quick_filter == 'pending_qc':
            queryset = queryset.filter(status='PENDING_QC')
        elif quick_filter == 'queries':
            queryset = queryset.filter(status='QUERY')
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(reference_number__icontains=search) |
                Q(name__icontains=search) |
                Q(training_notification__reference_number__icontains=search) |
                Q(training_notification__title__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['status_choices'] = TrancheSchedule.STATUS_CHOICES
        context['tranche_type_choices'] = TrancheSchedule.TRANCHE_TYPE_CHOICES
        context['funder_choices'] = TrainingNotification.FUNDER_CHOICES
        context['project_type_choices'] = TrainingNotification.PROJECT_TYPE_CHOICES
        
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'type': self.request.GET.get('type', ''),
            'funder': self.request.GET.get('funder', ''),
            'project_type': self.request.GET.get('project_type', ''),
            'not': self.request.GET.get('not', ''),
            'due_from': self.request.GET.get('due_from', ''),
            'due_to': self.request.GET.get('due_to', ''),
            'quick': self.request.GET.get('quick', ''),
            'search': self.request.GET.get('search', ''),
        }
        
        context['stats'] = get_tranche_stats()
        
        return context


class TrancheDetailView(LoginRequiredMixin, DetailView):
    """Detailed view of a single tranche with evidence and submissions"""
    model = TrancheSchedule
    template_name = 'tranches/detail.html'
    context_object_name = 'tranche'
    
    def get_queryset(self):
        return TrancheSchedule.objects.filter(
            is_deleted=False
        ).select_related(
            'training_notification',
            'training_notification__qualification',
            'training_notification__corporate_client',
            'qc_performed_by',
            'invoice'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tranche = self.object
        
        # Evidence requirements and collected evidence
        context['evidence_requirements'] = tranche.evidence_requirements.all().prefetch_related('evidence')
        
        # Calculate evidence stats
        total_requirements = tranche.evidence_requirements.count()
        fulfilled_requirements = tranche.evidence_requirements.filter(
            evidence__status='VERIFIED'
        ).distinct().count()
        
        context['evidence_stats'] = {
            'total': total_requirements,
            'fulfilled': fulfilled_requirements,
            'pending': total_requirements - fulfilled_requirements,
            'percentage': int((fulfilled_requirements / total_requirements) * 100) if total_requirements > 0 else 0
        }
        
        # Submissions
        context['submissions'] = tranche.submissions.all().select_related('submitted_by', 'qc_completed_by')
        
        # Comments/communication log
        context['comments'] = tranche.comments.all().select_related('created_by')
        
        # Timeline/audit trail
        context['timeline'] = self._build_timeline(tranche)
        
        # Related tranches from same NOT
        context['related_tranches'] = TrancheSchedule.objects.filter(
            training_notification=tranche.training_notification,
            is_deleted=False
        ).exclude(pk=tranche.pk).order_by('sequence_number')
        
        return context
    
    def _build_timeline(self, tranche):
        """Build a timeline of events for this tranche"""
        timeline = []
        
        # Created
        timeline.append({
            'date': tranche.created_at,
            'event': 'Tranche Created',
            'type': 'created',
            'user': tranche.created_by
        })
        
        # Evidence submitted
        if tranche.evidence_submitted_date:
            timeline.append({
                'date': tranche.evidence_submitted_date,
                'event': 'Evidence Collection Completed',
                'type': 'evidence',
                'user': None
            })
        
        # QC completed
        if tranche.qc_completed_date:
            timeline.append({
                'date': tranche.qc_completed_date,
                'event': f'QC {"Passed" if tranche.qc_passed else "Failed"}',
                'type': 'qc_passed' if tranche.qc_passed else 'qc_failed',
                'user': tranche.qc_performed_by
            })
        
        # Submitted to funder
        if tranche.submitted_to_funder_date:
            timeline.append({
                'date': tranche.submitted_to_funder_date,
                'event': 'Submitted to Funder',
                'type': 'submitted',
                'user': None
            })
        
        # Funder approved
        if tranche.funder_approved_date:
            timeline.append({
                'date': tranche.funder_approved_date,
                'event': 'Funder Approved',
                'type': 'approved',
                'user': None
            })
        
        # Invoice sent
        if tranche.invoice_sent_date:
            timeline.append({
                'date': tranche.invoice_sent_date,
                'event': 'Invoice Sent',
                'type': 'invoiced',
                'user': None
            })
        
        # Payment received
        if tranche.payment_received_date:
            timeline.append({
                'date': tranche.payment_received_date,
                'event': f'Payment Received - R{tranche.actual_amount_received or tranche.amount:,.2f}',
                'type': 'paid',
                'user': None
            })
        
        # Sort by date descending
        timeline.sort(key=lambda x: x['date'] if x['date'] else timezone.now(), reverse=True)
        
        return timeline


class TrancheCreateView(LoginRequiredMixin, CreateView):
    """Create a new tranche for a NOT"""
    model = TrancheSchedule
    template_name = 'tranches/create.html'
    fields = [
        'sequence_number', 'tranche_type', 'name', 'description',
        'due_date', 'amount', 'learner_count_target', 'priority', 'notes'
    ]
    
    def dispatch(self, request, *args, **kwargs):
        self.notification = get_object_or_404(
            TrainingNotification,
            pk=kwargs.get('not_pk'),
            is_deleted=False
        )
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notification'] = self.notification
        context['tranche_type_choices'] = TrancheSchedule.TRANCHE_TYPE_CHOICES
        context['priority_choices'] = TrancheSchedule.PRIORITY_CHOICES
        
        # Get existing tranches for reference
        context['existing_tranches'] = self.notification.tranches.filter(
            is_deleted=False
        ).order_by('sequence_number')
        
        # Suggest next sequence number
        last_tranche = context['existing_tranches'].last()
        context['suggested_sequence'] = (last_tranche.sequence_number + 1) if last_tranche else 1
        
        return context
    
    def form_valid(self, form):
        form.instance.training_notification = self.notification
        form.instance.created_by = self.request.user
        
        # Set reminder date (14 days before due)
        if form.instance.due_date:
            form.instance.reminder_date = form.instance.due_date - timedelta(days=14)
        
        response = super().form_valid(form)
        messages.success(self.request, f'Tranche {self.object.reference_number} created successfully!')
        return response
    
    def get_success_url(self):
        return reverse('tranches:tranche_detail', kwargs={'pk': self.object.pk})


class TrancheUpdateView(LoginRequiredMixin, UpdateView):
    """Update a tranche"""
    model = TrancheSchedule
    template_name = 'tranches/edit.html'
    fields = [
        'name', 'description', 'tranche_type', 'due_date', 'amount',
        'learner_count_target', 'priority', 'notes'
    ]
    
    def get_queryset(self):
        return TrancheSchedule.objects.filter(is_deleted=False)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notification'] = self.object.training_notification
        context['tranche_type_choices'] = TrancheSchedule.TRANCHE_TYPE_CHOICES
        context['priority_choices'] = TrancheSchedule.PRIORITY_CHOICES
        return context
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        
        # Update reminder date if due date changed
        if form.instance.due_date:
            form.instance.reminder_date = form.instance.due_date - timedelta(days=14)
        
        messages.success(self.request, 'Tranche updated successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('tranches:tranche_detail', kwargs={'pk': self.object.pk})


class TrancheAddEvidenceRequirementView(LoginRequiredMixin, CreateView):
    """Add an evidence requirement to a tranche"""
    model = TrancheEvidenceRequirement
    template_name = 'tranches/add_evidence_requirement.html'
    fields = [
        'evidence_type', 'name', 'description', 'is_mandatory',
        'expected_count', 'deadline', 'requires_verification', 'verification_notes'
    ]
    
    def dispatch(self, request, *args, **kwargs):
        self.tranche = get_object_or_404(
            TrancheSchedule,
            pk=kwargs.get('pk'),
            is_deleted=False
        )
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tranche'] = self.tranche
        context['evidence_type_choices'] = TrancheEvidenceRequirement.EVIDENCE_TYPE_CHOICES
        return context
    
    def form_valid(self, form):
        form.instance.tranche = self.tranche
        form.instance.created_by = self.request.user
        
        # Default deadline to tranche due date if not set
        if not form.instance.deadline:
            form.instance.deadline = self.tranche.due_date
        
        response = super().form_valid(form)
        messages.success(self.request, f'Evidence requirement "{self.object.name}" added!')
        return response
    
    def get_success_url(self):
        return reverse('tranches:tranche_detail', kwargs={'pk': self.tranche.pk})


class TrancheUploadEvidenceView(LoginRequiredMixin, View):
    """Upload evidence for a requirement"""
    
    def get(self, request, pk, requirement_pk):
        tranche = get_object_or_404(TrancheSchedule, pk=pk, is_deleted=False)
        requirement = get_object_or_404(
            TrancheEvidenceRequirement,
            pk=requirement_pk,
            tranche=tranche
        )
        
        context = {
            'tranche': tranche,
            'requirement': requirement,
            'existing_evidence': requirement.evidence.all()
        }
        
        from django.shortcuts import render
        return render(request, 'tranches/upload_evidence.html', context)
    
    def post(self, request, pk, requirement_pk):
        tranche = get_object_or_404(TrancheSchedule, pk=pk, is_deleted=False)
        requirement = get_object_or_404(
            TrancheEvidenceRequirement,
            pk=requirement_pk,
            tranche=tranche
        )
        
        # Handle file upload - creates Document and TrancheEvidence
        from learners.models import Document
        
        uploaded_file = request.FILES.get('document')
        if uploaded_file:
            # Create document
            document = Document.objects.create(
                document_type='POE',  # Portfolio of Evidence
                file=uploaded_file,
                original_filename=uploaded_file.name,
                description=request.POST.get('description', ''),
                uploaded_by=request.user,
                created_by=request.user
            )
            
            # Create tranche evidence link
            TrancheEvidence.objects.create(
                requirement=requirement,
                document=document,
                title=request.POST.get('title', uploaded_file.name),
                description=request.POST.get('description', ''),
                created_by=request.user
            )
            
            # Update tranche status if first evidence
            if tranche.status == 'SCHEDULED':
                tranche.status = 'EVIDENCE_COLLECTION'
                tranche.save()
            
            messages.success(request, 'Evidence uploaded successfully!')
        else:
            messages.error(request, 'No file was uploaded.')
        
        return redirect('tranches:tranche_detail', pk=tranche.pk)


class TrancheStartQCView(LoginRequiredMixin, View):
    """Start QC process for a tranche"""
    
    def post(self, request, pk):
        tranche = get_object_or_404(TrancheSchedule, pk=pk, is_deleted=False)
        
        if tranche.status not in ['EVIDENCE_COMPLETE', 'QC_FAILED']:
            messages.error(request, 'Tranche must have complete evidence before QC can start.')
            return redirect('tranches:tranche_detail', pk=pk)
        
        tranche.status = 'PENDING_QC'
        tranche.updated_by = request.user
        tranche.save()
        
        messages.success(request, 'Tranche moved to QC queue.')
        return redirect('tranches:tranche_detail', pk=pk)


class TrancheCompleteQCView(LoginRequiredMixin, View):
    """Complete QC for a tranche"""
    
    def post(self, request, pk):
        tranche = get_object_or_404(TrancheSchedule, pk=pk, is_deleted=False)
        
        if tranche.status != 'PENDING_QC':
            messages.error(request, 'Tranche must be in QC queue.')
            return redirect('tranches:tranche_detail', pk=pk)
        
        qc_result = request.POST.get('qc_result')
        qc_notes = request.POST.get('qc_notes', '')
        
        tranche.qc_performed_by = request.user
        tranche.qc_completed_date = timezone.now().date()
        tranche.qc_notes = qc_notes
        tranche.updated_by = request.user
        
        if qc_result == 'pass':
            tranche.qc_passed = True
            tranche.status = 'QC_PASSED'
            messages.success(request, 'QC passed! Tranche ready for submission.')
        else:
            tranche.qc_passed = False
            tranche.status = 'QC_FAILED'
            messages.warning(request, 'QC failed. Tranche requires rework.')
        
        tranche.save()
        
        # Add QC comment
        TrancheComment.objects.create(
            tranche=tranche,
            comment_type='QC_NOTE',
            comment=f"QC {'Passed' if tranche.qc_passed else 'Failed'}: {qc_notes}",
            created_by=request.user
        )
        
        return redirect('tranches:tranche_detail', pk=pk)


class TrancheSubmitToFunderView(LoginRequiredMixin, View):
    """Submit tranche claim to funder"""
    
    def get(self, request, pk):
        tranche = get_object_or_404(TrancheSchedule, pk=pk, is_deleted=False)
        
        context = {
            'tranche': tranche,
            'submission_methods': TrancheSubmission.SUBMISSION_METHOD_CHOICES,
            'evidence': tranche.evidence_requirements.all().prefetch_related('evidence')
        }
        
        from django.shortcuts import render
        return render(request, 'tranches/submit_to_funder.html', context)
    
    def post(self, request, pk):
        tranche = get_object_or_404(TrancheSchedule, pk=pk, is_deleted=False)
        
        if tranche.status not in ['QC_PASSED', 'QUERY']:
            messages.error(request, 'Tranche must pass QC before submission.')
            return redirect('tranches:tranche_detail', pk=pk)
        
        # Create submission record
        submission = TrancheSubmission.objects.create(
            tranche=tranche,
            status='SUBMITTED',
            submission_method=request.POST.get('submission_method', 'PORTAL'),
            submitted_by=request.user,
            submission_date=timezone.now(),
            portal_reference=request.POST.get('portal_reference', ''),
            claimed_amount=tranche.amount,
            notes=request.POST.get('notes', ''),
            created_by=request.user
        )
        
        # Update tranche status
        tranche.status = 'SUBMITTED'
        tranche.submitted_to_funder_date = timezone.now().date()
        tranche.updated_by = request.user
        tranche.save()
        
        # Add comment
        TrancheComment.objects.create(
            tranche=tranche,
            submission=submission,
            comment_type='STATUS_UPDATE',
            comment=f"Submitted to funder via {submission.get_submission_method_display()}. Reference: {submission.portal_reference or 'N/A'}",
            created_by=request.user
        )
        
        messages.success(request, f'Tranche submitted to funder. Submission reference: {submission.submission_reference}')
        return redirect('tranches:tranche_detail', pk=pk)


class TrancheRecordFunderResponseView(LoginRequiredMixin, View):
    """Record funder response (approval, query, rejection)"""
    
    def post(self, request, pk):
        tranche = get_object_or_404(TrancheSchedule, pk=pk, is_deleted=False)
        
        response_type = request.POST.get('response_type')
        funder_reference = request.POST.get('funder_reference', '')
        funder_notes = request.POST.get('funder_notes', '')
        approved_amount = request.POST.get('approved_amount')
        
        tranche.funder_reference = funder_reference
        tranche.funder_response_notes = funder_notes
        tranche.updated_by = request.user
        
        if response_type == 'approved':
            tranche.status = 'APPROVED'
            tranche.funder_approved_date = timezone.now().date()
            if approved_amount:
                tranche.actual_amount_received = approved_amount
            messages.success(request, 'Funder approval recorded!')
        elif response_type == 'query':
            tranche.status = 'QUERY'
            messages.warning(request, 'Funder query recorded. Please address and resubmit.')
        elif response_type == 'rejected':
            tranche.status = 'CANCELLED'
            messages.error(request, 'Funder rejection recorded.')
        
        tranche.save()
        
        # Update latest submission
        latest_submission = tranche.submissions.order_by('-submission_date').first()
        if latest_submission:
            latest_submission.funder_response_date = timezone.now()
            latest_submission.funder_reference = funder_reference
            latest_submission.funder_notes = funder_notes
            if response_type == 'approved':
                latest_submission.status = 'APPROVED'
                latest_submission.approved_amount = approved_amount
            elif response_type == 'query':
                latest_submission.status = 'QUERY'
            elif response_type == 'rejected':
                latest_submission.status = 'REJECTED'
            latest_submission.save()
        
        # Add comment
        TrancheComment.objects.create(
            tranche=tranche,
            submission=latest_submission,
            comment_type='FUNDER_RESPONSE' if response_type != 'query' else 'FUNDER_QUERY',
            comment=f"Funder {response_type}: {funder_notes}",
            created_by=request.user
        )
        
        return redirect('tranches:tranche_detail', pk=pk)


class TrancheRecordPaymentView(LoginRequiredMixin, View):
    """Record payment received for a tranche"""
    
    def post(self, request, pk):
        tranche = get_object_or_404(TrancheSchedule, pk=pk, is_deleted=False)
        
        payment_date = request.POST.get('payment_date')
        payment_amount = request.POST.get('payment_amount')
        payment_reference = request.POST.get('payment_reference', '')
        
        tranche.status = 'PAID'
        tranche.payment_received_date = payment_date
        tranche.actual_amount_received = payment_amount
        tranche.updated_by = request.user
        tranche.save()
        
        # Update latest submission
        latest_submission = tranche.submissions.order_by('-submission_date').first()
        if latest_submission:
            latest_submission.status = 'PAID'
            latest_submission.payment_date = payment_date
            latest_submission.payment_amount = payment_amount
            latest_submission.payment_reference = payment_reference
            latest_submission.save()
        
        # Add comment
        TrancheComment.objects.create(
            tranche=tranche,
            submission=latest_submission,
            comment_type='STATUS_UPDATE',
            comment=f"Payment received: R{float(payment_amount):,.2f} on {payment_date}. Reference: {payment_reference}",
            created_by=request.user
        )
        
        messages.success(request, f'Payment of R{float(payment_amount):,.2f} recorded!')
        return redirect('tranches:tranche_detail', pk=pk)


class TrancheAddCommentView(LoginRequiredMixin, View):
    """Add a comment to a tranche"""
    
    def post(self, request, pk):
        tranche = get_object_or_404(TrancheSchedule, pk=pk, is_deleted=False)
        
        comment_type = request.POST.get('comment_type', 'INTERNAL')
        comment_text = request.POST.get('comment', '').strip()
        
        if comment_text:
            TrancheComment.objects.create(
                tranche=tranche,
                comment_type=comment_type,
                comment=comment_text,
                created_by=request.user
            )
            messages.success(request, 'Comment added.')
        
        return redirect('tranches:tranche_detail', pk=pk)


class GenerateTranchesFromTemplateView(LoginRequiredMixin, View):
    """Generate tranches for a NOT from a template"""
    
    def get(self, request, not_pk):
        notification = get_object_or_404(TrainingNotification, pk=not_pk, is_deleted=False)
        
        # Find matching templates
        templates = TrancheTemplate.objects.filter(
            is_active=True,
            project_type=notification.project_type,
            funder_type=notification.funder
        )
        
        context = {
            'notification': notification,
            'templates': templates,
            'existing_tranches': notification.tranches.filter(is_deleted=False).count()
        }
        
        from django.shortcuts import render
        return render(request, 'tranches/generate_from_template.html', context)
    
    def post(self, request, not_pk):
        notification = get_object_or_404(TrainingNotification, pk=not_pk, is_deleted=False)
        template_pk = request.POST.get('template')
        
        if not template_pk:
            messages.error(request, 'Please select a template.')
            return redirect('tranches:generate_tranches_from_template', not_pk=not_pk)
        
        template = get_object_or_404(TrancheTemplate, pk=template_pk, is_active=True)
        
        # Get start date from NOT or use today
        start_date = notification.planned_start_date or timezone.now().date()
        contract_value = notification.contract_value or 0
        
        created_count = 0
        for item in template.items.all().order_by('sequence_number'):
            due_date = start_date + timedelta(days=item.months_from_start * 30)
            amount = (contract_value * item.percentage_of_total / 100) if contract_value else 0
            
            tranche = TrancheSchedule.objects.create(
                training_notification=notification,
                template_item=item,
                sequence_number=item.sequence_number,
                tranche_type=item.tranche_type,
                name=item.name,
                description=item.description,
                due_date=due_date,
                reminder_date=due_date - timedelta(days=item.days_before_deadline_reminder),
                amount=amount,
                learner_count_target=notification.expected_learner_count,
                created_by=request.user
            )
            
            # Create evidence requirements from template
            if item.evidence_requirements:
                for evidence_type in item.evidence_requirements:
                    # Get display name for evidence type
                    type_display = dict(TrancheEvidenceRequirement.EVIDENCE_TYPE_CHOICES).get(evidence_type, evidence_type)
                    
                    TrancheEvidenceRequirement.objects.create(
                        tranche=tranche,
                        evidence_type=evidence_type,
                        name=type_display,
                        is_mandatory=True,
                        deadline=due_date,
                        created_by=request.user
                    )
            
            created_count += 1
        
        messages.success(request, f'{created_count} tranches created from template "{template.name}"!')
        return redirect('not_detail', pk=not_pk)


class TrancheCalendarView(LoginRequiredMixin, TemplateView):
    """Calendar view of upcoming tranches"""
    template_name = 'tranches/calendar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range from query params or default to current month
        today = timezone.now().date()
        year = int(self.request.GET.get('year', today.year))
        month = int(self.request.GET.get('month', today.month))
        
        # Calculate date range for the month
        import calendar
        _, last_day = calendar.monthrange(year, month)
        start_date = timezone.datetime(year, month, 1).date()
        end_date = timezone.datetime(year, month, last_day).date()
        
        # Get tranches for the month
        tranches = TrancheSchedule.objects.filter(
            is_deleted=False,
            due_date__gte=start_date,
            due_date__lte=end_date
        ).select_related('training_notification').order_by('due_date')
        
        # Group by date
        tranches_by_date = {}
        for tranche in tranches:
            date_key = tranche.due_date.isoformat()
            if date_key not in tranches_by_date:
                tranches_by_date[date_key] = []
            tranches_by_date[date_key].append(tranche)
        
        context['year'] = year
        context['month'] = month
        context['month_name'] = calendar.month_name[month]
        context['tranches_by_date'] = tranches_by_date
        context['calendar'] = calendar.monthcalendar(year, month)
        
        # Navigation
        if month == 1:
            context['prev_year'], context['prev_month'] = year - 1, 12
        else:
            context['prev_year'], context['prev_month'] = year, month - 1
        
        if month == 12:
            context['next_year'], context['next_month'] = year + 1, 1
        else:
            context['next_year'], context['next_month'] = year, month + 1
        
        return context


class TrancheDeleteView(LoginRequiredMixin, View):
    """Soft delete a tranche"""
    
    def post(self, request, pk):
        tranche = get_object_or_404(TrancheSchedule, pk=pk, is_deleted=False)
        
        # Only allow deletion of scheduled tranches
        if tranche.status != 'SCHEDULED':
            messages.error(request, 'Only scheduled tranches can be deleted.')
            return redirect('tranches:tranche_detail', pk=pk)
        
        # Soft delete
        tranche.soft_delete(user=request.user)
        
        messages.success(request, f'Tranche {tranche.reference_number} has been deleted.')
        return redirect('not_detail', pk=tranche.training_notification.pk)
