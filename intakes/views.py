from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.http import JsonResponse
from datetime import date, timedelta
from decimal import Decimal

from .models import Intake, IntakeEnrollment, IntakeDocument, IntakeCapacitySnapshot
from learners.models import Learner, Guardian
from academics.models import Qualification
from tenants.models import Campus
from finance.models import BursaryProvider, BursaryApplication, DebitOrderMandate
from core.context_processors import get_selected_campus


class IntakeDashboardView(LoginRequiredMixin, View):
    """
    Main dashboard for the Intakes section.
    Shows overview stats, upcoming intakes, and quick actions.
    """
    
    def get(self, request):
        today = date.today()
        
        # Apply global campus filter
        selected_campus = get_selected_campus(request)
        
        # Get all intakes with counts
        intakes = Intake.objects.select_related(
            'qualification', 'campus', 'facilitator'
        ).prefetch_related('enrollments')
        
        # Apply campus filter
        if selected_campus:
            intakes = intakes.filter(campus=selected_campus)
        
        # Stats
        active_intakes = intakes.filter(status__in=['RECRUITING', 'ENROLLMENT_OPEN', 'ACTIVE'])
        upcoming_intakes = intakes.filter(
            start_date__gt=today,
            status__in=['PLANNED', 'RECRUITING', 'ENROLLMENT_OPEN']
        ).order_by('start_date')[:10]
        
        # Calculate total capacity and enrollment
        total_capacity = active_intakes.aggregate(Sum('max_capacity'))['max_capacity__sum'] or 0
        total_enrolled = sum(i.enrolled_count for i in active_intakes)
        total_pending = sum(i.pending_count for i in active_intakes)
        total_available = sum(i.available_spots for i in active_intakes)
        
        # Intakes by status
        status_counts = intakes.values('status').annotate(count=Count('id'))
        
        # Intakes by campus (only filter campuses if global filter set)
        campus_stats = []
        campus_queryset = Campus.objects.filter(is_active=True)
        if selected_campus:
            campus_queryset = campus_queryset.filter(pk=selected_campus.pk)
        
        for campus in campus_queryset:
            campus_intakes = intakes.filter(campus=campus, status__in=['RECRUITING', 'ENROLLMENT_OPEN', 'ACTIVE'])
            if campus_intakes.exists():
                campus_stats.append({
                    'campus': campus,
                    'intake_count': campus_intakes.count(),
                    'total_capacity': sum(i.max_capacity for i in campus_intakes),
                    'enrolled': sum(i.enrolled_count for i in campus_intakes),
                    'available': sum(i.available_spots for i in campus_intakes),
                })
        
        # Recent enrollments
        recent_enrollments = IntakeEnrollment.objects.select_related(
            'intake', 'learner'
        ).order_by('-created_at')[:10]
        
        # Intakes needing attention (low fill rate, deadline approaching)
        attention_intakes = []
        for intake in active_intakes:
            if intake.enrollment_deadline:
                days_to_deadline = (intake.enrollment_deadline - today).days
                if days_to_deadline <= 14 and intake.fill_percentage < 80:
                    attention_intakes.append({
                        'intake': intake,
                        'days_to_deadline': days_to_deadline,
                        'fill_percentage': intake.fill_percentage,
                    })
        
        context = {
            'total_capacity': total_capacity,
            'total_enrolled': total_enrolled,
            'total_pending': total_pending,
            'total_available': total_available,
            'fill_rate': round((total_enrolled / total_capacity * 100), 1) if total_capacity > 0 else 0,
            'status_counts': {s['status']: s['count'] for s in status_counts},
            'campus_stats': campus_stats,
            'upcoming_intakes': upcoming_intakes,
            'recent_enrollments': recent_enrollments,
            'attention_intakes': attention_intakes,
        }
        
        return render(request, 'intakes/dashboard.html', context)


class IntakeBucketListView(LoginRequiredMixin, View):
    """
    Visual bucket view showing all intakes with capacity bars.
    Grouped by campus with filtering options.
    """
    
    def get(self, request):
        today = date.today()
        
        # Get filter parameters
        campus_filter = request.GET.get('campus')
        status_filter = request.GET.get('status')
        qualification_filter = request.GET.get('qualification')
        show_past = request.GET.get('show_past') == 'true'
        
        # Apply global campus filter if no explicit campus filter
        if not campus_filter:
            selected_campus = get_selected_campus(request)
            if selected_campus:
                campus_filter = str(selected_campus.pk)
        
        # Base queryset
        intakes = Intake.objects.select_related(
            'qualification', 'campus', 'facilitator', 'training_notification'
        ).prefetch_related('enrollments')
        
        # Apply filters
        if campus_filter:
            intakes = intakes.filter(campus_id=campus_filter)
        if status_filter:
            intakes = intakes.filter(status=status_filter)
        if qualification_filter:
            intakes = intakes.filter(qualification_id=qualification_filter)
        if not show_past:
            intakes = intakes.exclude(status__in=['COMPLETED', 'CANCELLED'])
            intakes = intakes.filter(end_date__gte=today)
        
        intakes = intakes.order_by('start_date')
        
        # Group by campus
        campuses = Campus.objects.filter(is_active=True).order_by('name')
        campus_intakes = {}
        for campus in campuses:
            campus_list = [i for i in intakes if i.campus_id == campus.id]
            if campus_list:
                campus_intakes[campus] = campus_list
        
        # Get filter options
        all_campuses = Campus.objects.filter(is_active=True)
        all_qualifications = Qualification.objects.filter(is_active=True)
        
        context = {
            'campus_intakes': campus_intakes,
            'all_campuses': all_campuses,
            'all_qualifications': all_qualifications,
            'status_choices': Intake.STATUS_CHOICES,
            'selected_campus': campus_filter,
            'selected_status': status_filter,
            'selected_qualification': qualification_filter,
            'show_past': show_past,
        }
        
        return render(request, 'intakes/bucket_list.html', context)


class IntakeDetailView(LoginRequiredMixin, View):
    """
    Detailed view of a single intake with enrollment management.
    """
    
    def get(self, request, pk):
        intake = get_object_or_404(
            Intake.objects.select_related(
                'qualification', 'campus', 'facilitator', 'training_notification', 'venue'
            ),
            pk=pk
        )
        
        # Get enrollments grouped by status
        enrollments = intake.enrollments.select_related(
            'learner', 'responsible_payer', 'corporate_client', 'bursary_application'
        ).order_by('-created_at')
        
        enrolled_list = enrollments.filter(status__in=['ENROLLED', 'ACTIVE'])
        pending_list = enrollments.filter(status__in=['APPLIED', 'DOC_CHECK', 'PAYMENT_PENDING'])
        other_list = enrollments.exclude(status__in=['ENROLLED', 'ACTIVE', 'APPLIED', 'DOC_CHECK', 'PAYMENT_PENDING'])
        
        # Get funding breakdown
        funding_breakdown = intake.get_funding_breakdown()
        
        # Get capacity snapshots for chart
        snapshots = intake.capacity_snapshots.order_by('snapshot_date')[:30]
        
        context = {
            'intake': intake,
            'enrolled_list': enrolled_list,
            'pending_list': pending_list,
            'other_list': other_list,
            'funding_breakdown': funding_breakdown,
            'snapshots': snapshots,
            'funding_choices': IntakeEnrollment.FUNDING_TYPE_CHOICES,
        }
        
        return render(request, 'intakes/detail.html', context)


class IntakeCreateView(LoginRequiredMixin, View):
    """
    Create a new intake.
    """
    
    def get(self, request):
        campuses = Campus.objects.filter(is_active=True)
        qualifications = Qualification.objects.filter(is_active=True)
        
        context = {
            'campuses': campuses,
            'qualifications': qualifications,
            'status_choices': Intake.STATUS_CHOICES,
            'delivery_choices': Intake.DELIVERY_MODE_CHOICES,
        }
        return render(request, 'intakes/create.html', context)
    
    def post(self, request):
        try:
            intake = Intake.objects.create(
                code=request.POST.get('code') or '',
                name=request.POST.get('name'),
                description=request.POST.get('description', ''),
                qualification_id=request.POST.get('qualification'),
                campus_id=request.POST.get('campus'),
                delivery_mode=request.POST.get('delivery_mode', 'ON_CAMPUS'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                enrollment_deadline=request.POST.get('enrollment_deadline') or None,
                max_capacity=int(request.POST.get('max_capacity', 30)),
                min_viable=int(request.POST.get('min_viable', 10)),
                status=request.POST.get('status', 'PLANNED'),
                registration_fee=Decimal(request.POST.get('registration_fee') or '0'),
                tuition_fee=Decimal(request.POST.get('tuition_fee') or '0'),
                materials_fee=Decimal(request.POST.get('materials_fee') or '0'),
                notes=request.POST.get('notes', ''),
                created_by=request.user,
            )
            messages.success(request, f'Intake {intake.code} created successfully!')
            return redirect('intakes:detail', pk=intake.pk)
        except Exception as e:
            messages.error(request, f'Error creating intake: {str(e)}')
            return redirect('intakes:create')


class IntakeEnrollView(LoginRequiredMixin, View):
    """
    Enroll a learner into an intake.
    Supports both selecting existing learner and creating new one.
    """
    
    def get(self, request, pk):
        intake = get_object_or_404(Intake, pk=pk)
        
        # Check if intake is open for enrollment
        if intake.status not in ['PLANNED', 'RECRUITING', 'ENROLLMENT_OPEN']:
            messages.error(request, 'This intake is not open for enrollment.')
            return redirect('intakes:detail', pk=pk)
        
        # Get existing learners (for quick select)
        learners = Learner.objects.all().order_by('last_name', 'first_name')[:100]
        
        # Get bursary providers
        bursary_providers = BursaryProvider.objects.filter(is_active=True)
        
        context = {
            'intake': intake,
            'learners': learners,
            'bursary_providers': bursary_providers,
            'funding_choices': IntakeEnrollment.FUNDING_TYPE_CHOICES,
            'payment_choices': IntakeEnrollment.PAYMENT_METHOD_CHOICES,
        }
        
        return render(request, 'intakes/enroll.html', context)
    
    def post(self, request, pk):
        intake = get_object_or_404(Intake, pk=pk)
        
        # Check capacity
        if intake.is_full:
            messages.error(request, 'This intake is at full capacity.')
            return redirect('intakes:detail', pk=pk)
        
        # Get or create learner
        learner_id = request.POST.get('learner_id')
        if learner_id:
            learner = get_object_or_404(Learner, pk=learner_id)
        else:
            # Create new learner
            try:
                learner = Learner.objects.create(
                    first_name=request.POST.get('first_name'),
                    last_name=request.POST.get('last_name'),
                    id_number=request.POST.get('id_number', ''),
                    email=request.POST.get('email', ''),
                    phone_mobile=request.POST.get('phone', ''),
                    created_by=request.user,
                )
            except Exception as e:
                messages.error(request, f'Error creating learner: {str(e)}')
                return redirect('intakes:enroll', pk=pk)
        
        # Check for duplicate enrollment
        if IntakeEnrollment.objects.filter(intake=intake, learner=learner).exists():
            messages.error(request, f'{learner} is already enrolled in this intake.')
            return redirect('intakes:detail', pk=pk)
        
        # Create enrollment
        funding_type = request.POST.get('funding_type', 'SELF_FUNDED')
        payment_method = request.POST.get('payment_method', '')
        
        enrollment = IntakeEnrollment.objects.create(
            intake=intake,
            learner=learner,
            funding_type=funding_type,
            payment_method=payment_method,
            status='APPLIED',
            created_by=request.user,
        )
        
        # Handle guardian if parent-funded
        if funding_type == 'PARENT_FUNDED':
            guardian_id = request.POST.get('guardian_id')
            if guardian_id:
                enrollment.responsible_payer_id = guardian_id
                enrollment.save()
            elif request.POST.get('guardian_first_name'):
                # Create new guardian
                guardian = Guardian.objects.create(
                    learner=learner,
                    relationship=request.POST.get('guardian_relationship', 'PARENT'),
                    first_name=request.POST.get('guardian_first_name'),
                    last_name=request.POST.get('guardian_last_name'),
                    email=request.POST.get('guardian_email', ''),
                    phone_mobile=request.POST.get('guardian_phone', ''),
                    is_financially_responsible=True,
                    created_by=request.user,
                )
                enrollment.responsible_payer = guardian
                enrollment.save()
        
        # Handle corporate funding
        if funding_type == 'EMPLOYER_FUNDED':
            corporate_id = request.POST.get('corporate_client_id')
            if corporate_id:
                enrollment.corporate_client_id = corporate_id
                enrollment.save()
        
        messages.success(request, f'{learner} enrolled successfully! Enrollment #{enrollment.enrollment_number}')
        return redirect('intakes:enrollment_detail', pk=enrollment.pk)


class IntakeEnrollmentDetailView(LoginRequiredMixin, View):
    """
    View and manage a single enrollment.
    Handle document uploads, payment confirmation, status changes.
    """
    
    def get(self, request, pk):
        enrollment = get_object_or_404(
            IntakeEnrollment.objects.select_related(
                'intake', 'learner', 'responsible_payer', 
                'corporate_client', 'bursary_application', 'debit_order_mandate'
            ),
            pk=pk
        )
        
        # Get learner's guardians
        guardians = enrollment.learner.guardians.all()
        
        # Get documents
        documents = enrollment.documents.all()
        
        # Get bursary providers for potential application
        bursary_providers = BursaryProvider.objects.filter(is_active=True)
        
        context = {
            'enrollment': enrollment,
            'guardians': guardians,
            'documents': documents,
            'bursary_providers': bursary_providers,
            'status_choices': IntakeEnrollment.STATUS_CHOICES,
            'document_types': IntakeDocument.DOCUMENT_TYPE_CHOICES,
        }
        
        return render(request, 'intakes/enrollment_detail.html', context)
    
    def post(self, request, pk):
        enrollment = get_object_or_404(IntakeEnrollment, pk=pk)
        action = request.POST.get('action')
        
        if action == 'update_status':
            new_status = request.POST.get('status')
            if new_status:
                enrollment.status = new_status
                if new_status == 'ENROLLED':
                    enrollment.enrollment_date = date.today()
                enrollment.save()
                messages.success(request, f'Status updated to {enrollment.get_status_display()}')
        
        elif action == 'confirm_registration_payment':
            enrollment.registration_paid = True
            enrollment.registration_paid_date = date.today()
            enrollment.registration_payment_reference = request.POST.get('payment_reference', '')
            enrollment.status = 'ENROLLED'
            enrollment.enrollment_date = date.today()
            enrollment.save()
            messages.success(request, 'Registration payment confirmed! Learner is now enrolled.')
        
        elif action == 'sign_bursary_contract':
            enrollment.bursary_contract_signed = True
            enrollment.bursary_contract_date = date.today()
            if request.FILES.get('bursary_contract_file'):
                enrollment.bursary_contract_file = request.FILES['bursary_contract_file']
            enrollment.status = 'ENROLLED'
            enrollment.enrollment_date = date.today()
            enrollment.save()
            messages.success(request, 'Bursary contract signed! Learner is now enrolled.')
        
        elif action == 'upload_document':
            doc_type = request.POST.get('document_type')
            doc_file = request.FILES.get('document_file')
            if doc_type and doc_file:
                IntakeDocument.objects.create(
                    enrollment=enrollment,
                    document_type=doc_type,
                    file=doc_file,
                    original_filename=doc_file.name,
                    created_by=request.user,
                )
                messages.success(request, f'Document uploaded successfully.')
        
        return redirect('intakes:enrollment_detail', pk=pk)


class IntakeCapacityReportView(LoginRequiredMixin, View):
    """
    Historical capacity and fill rate reports.
    """
    
    def get(self, request):
        # Get filter parameters
        campus_filter = request.GET.get('campus')
        months_back = int(request.GET.get('months', 6))
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=months_back * 30)
        
        # Get snapshots
        snapshots = IntakeCapacitySnapshot.objects.filter(
            snapshot_date__gte=start_date
        ).select_related('intake', 'intake__campus', 'intake__qualification')
        
        if campus_filter:
            snapshots = snapshots.filter(intake__campus_id=campus_filter)
        
        # Aggregate by date
        daily_data = {}
        for snapshot in snapshots:
            date_str = snapshot.snapshot_date.isoformat()
            if date_str not in daily_data:
                daily_data[date_str] = {
                    'date': snapshot.snapshot_date,
                    'total_capacity': 0,
                    'total_enrolled': 0,
                    'total_pending': 0,
                }
            daily_data[date_str]['total_capacity'] += snapshot.max_capacity
            daily_data[date_str]['total_enrolled'] += snapshot.enrolled_count
            daily_data[date_str]['total_pending'] += snapshot.pending_count
        
        # Sort by date
        chart_data = sorted(daily_data.values(), key=lambda x: x['date'])
        
        # Get completed intakes for historical comparison
        completed_intakes = Intake.objects.filter(
            status='COMPLETED',
            end_date__gte=start_date
        ).select_related('campus', 'qualification')
        
        # Calculate average fill rates by qualification
        qualification_stats = {}
        for intake in completed_intakes:
            qual_name = intake.qualification.name
            if qual_name not in qualification_stats:
                qualification_stats[qual_name] = {
                    'count': 0,
                    'total_fill_rate': 0,
                }
            qualification_stats[qual_name]['count'] += 1
            qualification_stats[qual_name]['total_fill_rate'] += intake.fill_percentage
        
        for qual in qualification_stats.values():
            qual['avg_fill_rate'] = round(qual['total_fill_rate'] / qual['count'], 1) if qual['count'] > 0 else 0
        
        # Get campuses for filter
        campuses = Campus.objects.filter(is_active=True)
        
        context = {
            'chart_data': chart_data,
            'qualification_stats': qualification_stats,
            'completed_intakes': completed_intakes,
            'campuses': campuses,
            'selected_campus': campus_filter,
            'selected_months': months_back,
        }
        
        return render(request, 'intakes/capacity_report.html', context)


class LearnerSearchAPIView(LoginRequiredMixin, View):
    """
    AJAX endpoint for searching learners during enrollment.
    """
    
    def get(self, request):
        query = request.GET.get('q', '')
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        learners = Learner.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(id_number__icontains=query) |
            Q(email__icontains=query)
        )[:20]
        
        results = [{
            'id': l.id,
            'text': f"{l.first_name} {l.last_name}",
            'id_number': l.id_number or '',
            'email': l.email or '',
        } for l in learners]
        
        return JsonResponse({'results': results})
