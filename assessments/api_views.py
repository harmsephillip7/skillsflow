"""
Assessment API Views

REST endpoints for assessment capture, offline sync, and scheduling.
Designed for PWA consumption with offline-first architecture.
"""
import json
import base64
from datetime import date, datetime
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import (
    AssessmentActivity, AssessmentResult, AssessmentSchedule,
    AssessmentEvidence, AssessmentSyncLog
)
from academics.models import Enrollment
from logistics.models import Cohort
from core.models import User


class AssessmentAPIBaseMixin:
    """Base mixin for assessment API views"""
    
    def json_response(self, data, status=200):
        return JsonResponse(data, status=status, safe=False)
    
    def error_response(self, message, status=400):
        return JsonResponse({'error': message, 'success': False}, status=status)
    
    def parse_json_body(self, request):
        try:
            return json.loads(request.body)
        except json.JSONDecodeError:
            return None


@method_decorator(csrf_exempt, name='dispatch')
class AssessmentScheduleListAPI(LoginRequiredMixin, AssessmentAPIBaseMixin, View):
    """
    GET /api/assessments/schedules/
    List assessment schedules with filtering.
    Supports offline caching with ETag.
    
    Query params:
    - cohort: filter by cohort ID
    - date_from: filter from date (YYYY-MM-DD)
    - date_to: filter to date (YYYY-MM-DD)
    - status: filter by status
    """
    
    def get(self, request):
        schedules = AssessmentSchedule.objects.select_related(
            'cohort', 'activity', 'activity__module', 'venue', 'assessor'
        )
        
        # Apply filters
        cohort_id = request.GET.get('cohort')
        if cohort_id:
            schedules = schedules.filter(cohort_id=cohort_id)
        
        date_from = request.GET.get('date_from')
        if date_from:
            schedules = schedules.filter(scheduled_date__gte=date_from)
        
        date_to = request.GET.get('date_to')
        if date_to:
            schedules = schedules.filter(scheduled_date__lte=date_to)
        
        status = request.GET.get('status')
        if status:
            schedules = schedules.filter(status=status)
        
        # Facilitator filter - show only their cohorts
        if not request.user.is_superuser:
            schedules = schedules.filter(cohort__facilitator=request.user)
        
        data = [{
            'id': s.id,
            'cohort_id': s.cohort_id,
            'cohort_code': s.cohort.code,
            'cohort_name': s.cohort.name,
            'activity_id': s.activity_id,
            'activity_code': s.activity.code,
            'activity_title': s.activity.title,
            'activity_type': s.activity.activity_type,
            'module_code': s.activity.module.code,
            'module_title': s.activity.module.title,
            'scheduled_date': s.scheduled_date.isoformat(),
            'scheduled_time': s.scheduled_time.isoformat() if s.scheduled_time else None,
            'duration_minutes': s.duration_minutes,
            'venue': s.venue.name if s.venue else None,
            'assessor': s.assessor.get_full_name() if s.assessor else None,
            'status': s.status,
            'preparation_notes': s.preparation_notes,
            'materials_required': s.materials_required,
            'is_auto_generated': s.is_auto_generated,
            'was_rescheduled': bool(s.original_date),
        } for s in schedules]
        
        return self.json_response({
            'success': True,
            'count': len(data),
            'schedules': data,
            'cached_at': timezone.now().isoformat()
        })


@method_decorator(csrf_exempt, name='dispatch')
class AssessmentScheduleRescheduleAPI(LoginRequiredMixin, AssessmentAPIBaseMixin, View):
    """
    PATCH /api/assessments/schedules/<id>/reschedule/
    Reschedule an assessment with audit trail.
    """
    
    def patch(self, request, schedule_id):
        data = self.parse_json_body(request)
        if not data:
            return self.error_response('Invalid JSON body')
        
        schedule = get_object_or_404(AssessmentSchedule, pk=schedule_id)
        
        new_date = data.get('new_date')
        new_time = data.get('new_time')
        reason = data.get('reason', '')
        
        if not new_date:
            return self.error_response('new_date is required')
        
        try:
            new_date = datetime.strptime(new_date, '%Y-%m-%d').date()
            new_time = datetime.strptime(new_time, '%H:%M').time() if new_time else None
        except ValueError:
            return self.error_response('Invalid date/time format')
        
        schedule.reschedule(new_date, new_time, reason, request.user)
        
        return self.json_response({
            'success': True,
            'schedule_id': schedule.id,
            'new_date': schedule.scheduled_date.isoformat(),
            'message': 'Assessment rescheduled successfully'
        })


@method_decorator(csrf_exempt, name='dispatch')
class BatchAssessmentDataAPI(LoginRequiredMixin, AssessmentAPIBaseMixin, View):
    """
    GET /api/assessments/batch/<schedule_id>/
    Get all learners for batch assessment capture.
    Returns learner list with photos, previous attempts, current status.
    """
    
    def get(self, request, schedule_id):
        schedule = get_object_or_404(
            AssessmentSchedule.objects.select_related('cohort', 'activity'),
            pk=schedule_id
        )
        
        # Get all enrollments for the cohort
        enrollments = Enrollment.objects.filter(
            cohort=schedule.cohort,
            status__in=['ENROLLED', 'ACTIVE']
        ).select_related('learner', 'learner__user')
        
        learners_data = []
        for enrollment in enrollments:
            learner = enrollment.learner
            
            # Get existing result for this activity
            existing_result = AssessmentResult.objects.filter(
                enrollment=enrollment,
                activity=schedule.activity
            ).order_by('-attempt_number').first()
            
            # Get attempt count
            attempt_count = AssessmentResult.objects.filter(
                enrollment=enrollment,
                activity=schedule.activity
            ).count()
            
            learner_data = {
                'enrollment_id': enrollment.id,
                'learner_id': learner.id,
                'learner_number': learner.learner_number,
                'first_name': learner.first_name,
                'last_name': learner.last_name,
                'full_name': f"{learner.first_name} {learner.last_name}",
                'photo_url': learner.user.profile_picture.url if learner.user and learner.user.profile_picture else None,
                'attempts': attempt_count,
                'max_attempts': schedule.activity.max_attempts,
                'current_result': existing_result.result if existing_result else None,
                'current_result_id': existing_result.id if existing_result else None,
                'current_status': existing_result.status if existing_result else None,
                'can_assess': attempt_count < schedule.activity.max_attempts or (existing_result and existing_result.result == 'NYC'),
            }
            learners_data.append(learner_data)
        
        # Sort by last name
        learners_data.sort(key=lambda x: x['last_name'])
        
        return self.json_response({
            'success': True,
            'schedule': {
                'id': schedule.id,
                'activity_code': schedule.activity.code,
                'activity_title': schedule.activity.title,
                'activity_type': schedule.activity.activity_type,
                'cohort_code': schedule.cohort.code,
                'scheduled_date': schedule.scheduled_date.isoformat(),
            },
            'learners': learners_data,
            'total_count': len(learners_data),
            'cached_at': timezone.now().isoformat()
        })


@method_decorator(csrf_exempt, name='dispatch')
class QuickSaveResultAPI(LoginRequiredMixin, AssessmentAPIBaseMixin, View):
    """
    POST /api/assessments/results/quick-save/
    Quick save a single assessment result.
    Supports offline sync with client timestamp comparison.
    
    Body:
    {
        "enrollment_id": 123,
        "activity_id": 456,
        "result": "C" or "NYC" or "ABS" or "DEF",
        "percentage_score": 85.5 (optional),
        "feedback": "..." (optional),
        "signature": "data:image/png;base64,..." (optional),
        "client_timestamp": "2026-02-17T10:30:00Z",
        "offline_id": "uuid-from-client" (optional)
    }
    """
    
    def post(self, request):
        data = self.parse_json_body(request)
        if not data:
            return self.error_response('Invalid JSON body')
        
        enrollment_id = data.get('enrollment_id')
        activity_id = data.get('activity_id')
        result = data.get('result')
        
        if not all([enrollment_id, activity_id, result]):
            return self.error_response('enrollment_id, activity_id, and result are required')
        
        if result not in ['C', 'NYC', 'ABS', 'DEF']:
            return self.error_response('Invalid result value')
        
        enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
        activity = get_object_or_404(AssessmentActivity, pk=activity_id)
        
        client_timestamp = data.get('client_timestamp')
        if client_timestamp:
            try:
                client_timestamp = datetime.fromisoformat(client_timestamp.replace('Z', '+00:00'))
            except ValueError:
                client_timestamp = timezone.now()
        else:
            client_timestamp = timezone.now()
        
        with transaction.atomic():
            # Check for existing result
            existing = AssessmentResult.objects.filter(
                enrollment=enrollment,
                activity=activity
            ).order_by('-attempt_number').first()
            
            had_conflict = False
            resolution = ''
            changes = {}
            
            if existing and existing.status in ['DRAFT', 'PENDING_MOD']:
                # Update existing draft/pending result
                server_timestamp = existing.updated_at
                
                # Check for conflict (server was modified after client timestamp)
                if server_timestamp and server_timestamp > client_timestamp:
                    had_conflict = True
                    resolution = 'CLIENT_WINS'  # Client timestamp wins per requirements
                
                old_result = existing.result
                existing.result = result
                existing.percentage_score = data.get('percentage_score')
                existing.feedback = data.get('feedback', '')
                existing.assessment_date = date.today()
                existing.assessor = request.user
                existing.status = 'PENDING_MOD'
                
                # Handle signature
                signature = data.get('signature')
                if signature:
                    existing.assessor_signature = signature
                    existing.assessor_signed_at = timezone.now()
                
                existing.save()
                assessment_result = existing
                
                changes = {
                    'result': {'old': old_result, 'new': result}
                }
                
            else:
                # Create new result
                attempt_number = (existing.attempt_number + 1) if existing else 1
                
                assessment_result = AssessmentResult.objects.create(
                    enrollment=enrollment,
                    activity=activity,
                    attempt_number=attempt_number,
                    assessor=request.user,
                    result=result,
                    percentage_score=data.get('percentage_score'),
                    assessment_date=date.today(),
                    feedback=data.get('feedback', ''),
                    status='PENDING_MOD',
                    assessor_signature=data.get('signature', ''),
                    assessor_signed_at=timezone.now() if data.get('signature') else None
                )
                
                changes = {'created': True}
            
            # Log sync
            sync_log = AssessmentSyncLog.objects.create(
                assessment_result=assessment_result,
                sync_type='UPDATE' if existing else 'CREATE',
                synced_by=request.user,
                client_timestamp=client_timestamp,
                client_device_id=data.get('device_id', ''),
                offline_id=data.get('offline_id', ''),
                server_timestamp=existing.updated_at if existing else None,
                had_conflict=had_conflict,
                resolution=resolution,
                changes_applied=changes
            )
        
        return self.json_response({
            'success': True,
            'result_id': assessment_result.id,
            'status': assessment_result.status,
            'had_conflict': had_conflict,
            'sync_log_id': sync_log.id,
            'message': 'Result saved successfully'
        })


@method_decorator(csrf_exempt, name='dispatch')
class BulkSyncResultsAPI(LoginRequiredMixin, AssessmentAPIBaseMixin, View):
    """
    POST /api/assessments/results/bulk-sync/
    Bulk sync assessment results from offline queue.
    Processes multiple results with conflict resolution.
    
    Body:
    {
        "results": [
            {
                "offline_id": "uuid",
                "enrollment_id": 123,
                "activity_id": 456,
                "result": "C",
                "percentage_score": 85.5,
                "feedback": "...",
                "signature": "data:...",
                "client_timestamp": "2026-02-17T10:30:00Z"
            },
            ...
        ],
        "device_id": "device-uuid"
    }
    """
    
    def post(self, request):
        data = self.parse_json_body(request)
        if not data:
            return self.error_response('Invalid JSON body')
        
        results = data.get('results', [])
        device_id = data.get('device_id', '')
        
        if not results:
            return self.error_response('No results to sync')
        
        sync_results = []
        conflicts = []
        
        for item in results:
            try:
                with transaction.atomic():
                    enrollment = Enrollment.objects.get(pk=item['enrollment_id'])
                    activity = AssessmentActivity.objects.get(pk=item['activity_id'])
                    
                    client_timestamp = item.get('client_timestamp')
                    if client_timestamp:
                        try:
                            client_timestamp = datetime.fromisoformat(client_timestamp.replace('Z', '+00:00'))
                        except ValueError:
                            client_timestamp = timezone.now()
                    else:
                        client_timestamp = timezone.now()
                    
                    # Check for existing
                    existing = AssessmentResult.objects.filter(
                        enrollment=enrollment,
                        activity=activity
                    ).order_by('-attempt_number').first()
                    
                    had_conflict = False
                    
                    if existing and existing.status in ['DRAFT', 'PENDING_MOD']:
                        if existing.updated_at and existing.updated_at > client_timestamp:
                            had_conflict = True
                            conflicts.append({
                                'offline_id': item.get('offline_id'),
                                'enrollment_id': item['enrollment_id'],
                                'server_result': existing.result,
                                'client_result': item['result']
                            })
                        
                        # Client wins
                        existing.result = item['result']
                        existing.percentage_score = item.get('percentage_score')
                        existing.feedback = item.get('feedback', '')
                        existing.assessor = request.user
                        existing.status = 'PENDING_MOD'
                        if item.get('signature'):
                            existing.assessor_signature = item['signature']
                            existing.assessor_signed_at = timezone.now()
                        existing.save()
                        
                        result_id = existing.id
                    else:
                        attempt_number = (existing.attempt_number + 1) if existing else 1
                        new_result = AssessmentResult.objects.create(
                            enrollment=enrollment,
                            activity=activity,
                            attempt_number=attempt_number,
                            assessor=request.user,
                            result=item['result'],
                            percentage_score=item.get('percentage_score'),
                            assessment_date=date.today(),
                            feedback=item.get('feedback', ''),
                            status='PENDING_MOD',
                            assessor_signature=item.get('signature', ''),
                            assessor_signed_at=timezone.now() if item.get('signature') else None
                        )
                        result_id = new_result.id
                    
                    # Log sync
                    AssessmentSyncLog.objects.create(
                        assessment_result_id=result_id,
                        sync_type='UPDATE' if existing else 'CREATE',
                        synced_by=request.user,
                        client_timestamp=client_timestamp,
                        client_device_id=device_id,
                        offline_id=item.get('offline_id', ''),
                        had_conflict=had_conflict,
                        resolution='CLIENT_WINS' if had_conflict else '',
                        changes_applied={'result': item['result']}
                    )
                    
                    sync_results.append({
                        'offline_id': item.get('offline_id'),
                        'result_id': result_id,
                        'success': True
                    })
                    
            except Exception as e:
                sync_results.append({
                    'offline_id': item.get('offline_id'),
                    'success': False,
                    'error': str(e)
                })
        
        return self.json_response({
            'success': True,
            'synced_count': len([r for r in sync_results if r['success']]),
            'failed_count': len([r for r in sync_results if not r['success']]),
            'conflicts_count': len(conflicts),
            'results': sync_results,
            'conflicts': conflicts
        })


@method_decorator(csrf_exempt, name='dispatch')
class EvidenceUploadAPI(LoginRequiredMixin, AssessmentAPIBaseMixin, View):
    """
    POST /api/assessments/evidence/upload/
    Upload photo/file evidence for an assessment result.
    Supports base64 encoded images from mobile devices.
    
    Body:
    {
        "result_id": 123,
        "evidence_type": "PHOTO",
        "file_data": "data:image/jpeg;base64,...",
        "description": "...",
        "offline_id": "uuid",
        "latitude": 123.456,
        "longitude": 78.901
    }
    """
    
    def post(self, request):
        data = self.parse_json_body(request)
        if not data:
            return self.error_response('Invalid JSON body')
        
        result_id = data.get('result_id')
        file_data = data.get('file_data')
        
        if not result_id or not file_data:
            return self.error_response('result_id and file_data are required')
        
        assessment_result = get_object_or_404(AssessmentResult, pk=result_id)
        
        # Parse base64 image
        try:
            format_data, imgstr = file_data.split(';base64,')
            ext = format_data.split('/')[-1]
            file_content = ContentFile(base64.b64decode(imgstr), name=f'evidence_{result_id}_{timezone.now().timestamp()}.{ext}')
        except Exception as e:
            return self.error_response(f'Invalid file data: {str(e)}')
        
        evidence = AssessmentEvidence.objects.create(
            assessment_result=assessment_result,
            evidence_type=data.get('evidence_type', 'PHOTO'),
            file=file_content,
            description=data.get('description', ''),
            captured_by=request.user,
            captured_at=timezone.now(),
            offline_id=data.get('offline_id', ''),
            synced_at=timezone.now(),
            latitude=data.get('latitude'),
            longitude=data.get('longitude')
        )
        
        return self.json_response({
            'success': True,
            'evidence_id': evidence.id,
            'file_url': evidence.file.url,
            'message': 'Evidence uploaded successfully'
        })


@method_decorator(csrf_exempt, name='dispatch')
class TodaysAssessmentsAPI(LoginRequiredMixin, AssessmentAPIBaseMixin, View):
    """
    GET /api/assessments/today/
    Get today's scheduled assessments for the current facilitator.
    Used for dashboard widget.
    """
    
    def get(self, request):
        today = date.today()
        
        schedules = AssessmentSchedule.objects.filter(
            scheduled_date=today,
            status='SCHEDULED'
        ).select_related('cohort', 'activity', 'activity__module', 'venue')
        
        if not request.user.is_superuser:
            schedules = schedules.filter(cohort__facilitator=request.user)
        
        data = [{
            'id': s.id,
            'cohort_code': s.cohort.code,
            'cohort_name': s.cohort.name,
            'activity_code': s.activity.code,
            'activity_title': s.activity.title,
            'activity_type': s.activity.activity_type,
            'scheduled_time': s.scheduled_time.isoformat() if s.scheduled_time else None,
            'venue': s.venue.name if s.venue else 'TBA',
            'learner_count': Enrollment.objects.filter(
                cohort=s.cohort,
                status__in=['ENROLLED', 'ACTIVE']
            ).count()
        } for s in schedules]
        
        return self.json_response({
            'success': True,
            'date': today.isoformat(),
            'assessments': data,
            'count': len(data)
        })


@method_decorator(csrf_exempt, name='dispatch')
class BulkSignOffAPI(LoginRequiredMixin, AssessmentAPIBaseMixin, View):
    """
    POST /api/assessments/bulk-signoff/
    Apply a single signature to multiple assessment results.
    Used for session-end bulk sign-off.
    
    Body:
    {
        "result_ids": [1, 2, 3, ...],
        "signature": "data:image/png;base64,..."
    }
    """
    
    def post(self, request):
        data = self.parse_json_body(request)
        if not data:
            return self.error_response('Invalid JSON body')
        
        result_ids = data.get('result_ids', [])
        signature = data.get('signature')
        
        if not result_ids or not signature:
            return self.error_response('result_ids and signature are required')
        
        signed_at = timezone.now()
        updated_count = AssessmentResult.objects.filter(
            id__in=result_ids,
            assessor=request.user,
            status__in=['DRAFT', 'PENDING_MOD']
        ).update(
            assessor_signature=signature,
            assessor_signed_at=signed_at
        )
        
        return self.json_response({
            'success': True,
            'signed_count': updated_count,
            'signed_at': signed_at.isoformat()
        })


# Schedule generation command helper
class GenerateSchedulesAPI(LoginRequiredMixin, AssessmentAPIBaseMixin, View):
    """
    POST /api/assessments/schedules/generate/
    Generate assessment schedules from cohort implementation plan.
    """
    
    def post(self, request):
        data = self.parse_json_body(request)
        if not data:
            return self.error_response('Invalid JSON body')
        
        cohort_id = data.get('cohort_id')
        if not cohort_id:
            return self.error_response('cohort_id is required')
        
        cohort = get_object_or_404(Cohort, pk=cohort_id)
        
        schedules = AssessmentSchedule.generate_from_cohort_plan(cohort, request.user)
        
        return self.json_response({
            'success': True,
            'schedules_created': len(schedules),
            'cohort_code': cohort.code,
            'message': f'Generated {len(schedules)} assessment schedules'
        })
