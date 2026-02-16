from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    MoodleInstance, MoodleCourse, MoodleCourseActivity,
    AssessmentMapping, GradeThreshold, MoodleSyncLog
)
from tenants.models import Brand
from academics.models import QCTOAssessmentCriteria, Module
from .services import MoodleClient, MoodleAPIError
from .forms import MoodleInstanceForm, GradeThresholdForm


def get_selected_brand(request):
    """Get the currently selected brand from session or return None"""
    brand_id = request.session.get('selected_brand_id')
    if brand_id:
        try:
            return Brand.objects.get(id=brand_id)
        except Brand.DoesNotExist:
            pass
    return None


def get_user_brands(user):
    """Get all brands the user has access to through their roles"""
    # Get brands from user roles
    user_brand_ids = user.user_roles.filter(
        is_active=True,
        brand__isnull=False
    ).values_list('brand_id', flat=True).distinct()
    
    # If user is superuser or has no specific brand restrictions, show all
    if user.is_superuser or not user_brand_ids:
        return Brand.objects.filter(is_active=True)
    
    return Brand.objects.filter(id__in=user_brand_ids, is_active=True)


@login_required
def dashboard(request):
    """LMS Integration Dashboard"""
    # Handle brand selection
    if request.method == 'POST' and 'brand_id' in request.POST:
        brand_id = request.POST.get('brand_id')
        if brand_id:
            request.session['selected_brand_id'] = int(brand_id)
            messages.success(request, "Brand selected successfully.")
            return redirect('lms_sync:dashboard')
    
    # Get available brands for user
    available_brands = get_user_brands(request.user)
    selected_brand = get_selected_brand(request)
    
    # If no brand selected yet and only one available, auto-select it
    if not selected_brand and available_brands.count() == 1:
        selected_brand = available_brands.first()
        request.session['selected_brand_id'] = selected_brand.id
    
    instance = None
    has_instance = False
    stats = {}
    recent_courses = []
    recent_logs = []
    global_threshold = None
    
    if selected_brand:
        try:
            instance = MoodleInstance.objects.get(brand=selected_brand)
            has_instance = True
            
            # Calculate stats
            stats = {
                'total_courses': MoodleCourse.objects.filter(instance=instance).count(),
                'active_courses': MoodleCourse.objects.filter(instance=instance, visible=True).count(),
                'total_enrollments': instance.enrollments.count(),
            'pending_mappings': AssessmentMapping.objects.filter(
                    moodle_activity__course__instance=instance,
                    status='PENDING'
                ).count(),
            }
            
            # Recent courses
            recent_courses = MoodleCourse.objects.filter(instance=instance).select_related('module')[:10]
            
            # Recent sync logs
            recent_logs = MoodleSyncLog.objects.filter(instance=instance)[:5]
            
        except MoodleInstance.DoesNotExist:
            pass
    
    # Global threshold
    global_threshold = GradeThreshold.objects.filter(is_global=True).first()
    
    context = {
        'instance': instance,
        'has_instance': has_instance,
        'stats': stats,
        'recent_courses': recent_courses,
        'recent_logs': recent_logs,
        'global_threshold': global_threshold.pass_percentage if global_threshold else 50,
        'available_brands': available_brands,
        'selected_brand': selected_brand,
    }
    
    return render(request, 'lms_sync/dashboard.html', context)


@login_required
def setup_wizard(request):
    """Multi-step Moodle setup wizard"""
    step = int(request.GET.get('step', 1))
    
    # Get available brands for user
    available_brands = get_user_brands(request.user)
    
    # Get brand from session or form
    brand_id = request.session.get('setup_brand_id')
    selected_brand = None
    if brand_id:
        try:
            selected_brand = Brand.objects.get(id=brand_id)
        except Brand.DoesNotExist:
            pass
    
    # Check if instance already exists for selected brand
    if selected_brand:
        try:
            instance = MoodleInstance.objects.get(brand=selected_brand)
            messages.info(request, f"Moodle instance already configured for {selected_brand.name}.")
            return redirect('lms_sync:dashboard')
        except MoodleInstance.DoesNotExist:
            pass
    
    if request.method == 'POST':
        action = request.POST.get('action', 'next')
        
        if action == 'back':
            step = max(1, step - 1)
            return redirect(f"{request.path}?step={step}")
        
        elif action == 'next':
            # Process current step and move to next
            if step == 1:
                # Store brand in session
                brand_id = request.POST.get('brand')
                if not brand_id:
                    messages.error(request, "Please select a brand.")
                    return redirect(f"{request.path}?step=1")
                
                request.session['setup_brand_id'] = int(brand_id)
                
                # Check if brand already has an instance
                try:
                    existing = MoodleInstance.objects.get(brand_id=brand_id)
                    messages.warning(request, f"Brand already has a Moodle instance configured.")
                    return redirect('lms_sync:dashboard')
                except MoodleInstance.DoesNotExist:
                    pass
                
                step = 2
            
            elif step == 2:
                # Save connection details in session
                request.session['moodle_name'] = request.POST.get('name')
                request.session['moodle_url'] = request.POST.get('base_url')
                request.session['moodle_token'] = request.POST.get('ws_token')
                step = 3
            
            elif step == 3:
                # Test connection and create instance
                class MockInstance:
                    def __init__(self, base_url, ws_token):
                        self.base_url = base_url
                        self.ws_token = ws_token
                
                mock = MockInstance(
                    request.session.get('moodle_url'),
                    request.session.get('moodle_token')
                )
                client = MoodleClient(mock)
                success, message = client.test_connection()
                
                if success:
                    # Create instance
                    brand = Brand.objects.get(id=request.session.get('setup_brand_id'))
                    instance = MoodleInstance.objects.create(
                        brand=brand,
                        name=request.session.get('moodle_name'),
                        base_url=request.session.get('moodle_url'),
                        ws_token=request.session.get('moodle_token'),
                        is_active=True,
                    )
                    request.session['instance_id'] = instance.id
                    request.session['selected_brand_id'] = brand.id
                    step = 4
                else:
                    # Connection failed, stay on step 3
                    context = {
                        'step': 3,
                        'connection_test': {'success': False, 'message': message},
                        'form': MoodleInstanceForm(),
                        'available_brands': available_brands,
                        'selected_brand': selected_brand,
                    }
                    return render(request, 'lms_sync/setup_wizard.html', context)
            
            elif step == 4:
                # Save sync settings
                instance = MoodleInstance.objects.get(id=request.session.get('instance_id'))
                instance.sync_enabled = request.POST.get('sync_enabled') == 'on'
                instance.save()
                
                # Save grade threshold if provided
                pass_percentage = request.POST.get('pass_percentage')
                brand = Brand.objects.get(id=request.session.get('setup_brand_id'))
                if pass_percentage:
                    GradeThreshold.objects.update_or_create(
                        brand=brand,
                        defaults={
                            'pass_percentage': pass_percentage,
                            'updated_by': request.user
                        }
                    )
                
                # Clear setup session data
                for key in ['setup_brand_id', 'moodle_name', 'moodle_url', 'moodle_token', 'instance_id']:
                    request.session.pop(key, None)
                
                step = 5
            
            return redirect(f"{request.path}?step={step}")
    
    # GET request - show current step
    form = MoodleInstanceForm()
    
    # Get global threshold for step 4
    global_threshold = GradeThreshold.objects.filter(is_global=True).first()
    
    context = {
        'step': step,
        'form': form,
        'global_threshold': global_threshold.pass_percentage if global_threshold else 50,
        'available_brands': available_brands,
        'selected_brand': selected_brand,
    }
    
    return render(request, 'lms_sync/setup_wizard.html', context)


@login_required
def moodle_tutorial(request):
    """In-app tutorial for Moodle token generation"""
    return render(request, 'lms_sync/moodle_tutorial.html')


@login_required
def review_mappings(request):
    """SME review interface for AI-suggested mappings"""
    selected_brand = get_selected_brand(request)
    
    if not selected_brand:
        messages.warning(request, "Please select a brand first.")
        return redirect('lms_sync:dashboard')
    
    try:
        instance = MoodleInstance.objects.get(brand=selected_brand)
    except MoodleInstance.DoesNotExist:
        messages.warning(request, "No Moodle instance configured for this brand.")
        return redirect('lms_sync:dashboard')
    
    if request.method == 'POST':
        mapping_id = request.POST.get('mapping_id')
        action = request.POST.get('action')
        review_notes = request.POST.get('review_notes', '')
        
        mapping = get_object_or_404(AssessmentMapping, id=mapping_id)
        
        if action == 'approve':
            mapping.status = 'APPROVED'
            mapping.reviewed_by = request.user
            mapping.reviewed_at = timezone.now()
            mapping.review_notes = review_notes
            mapping.save()
            messages.success(request, "Mapping approved successfully!")
        
        elif action == 'reject':
            mapping.status = 'REJECTED'
            mapping.reviewed_by = request.user
            mapping.reviewed_at = timezone.now()
            mapping.review_notes = review_notes
            mapping.save()
            messages.warning(request, "Mapping rejected.")
        
        return redirect('lms_sync:review_mappings')
    
    # Filter mappings
    mappings = AssessmentMapping.objects.filter(
        moodle_activity__course__instance=instance
    ).select_related(
        'moodle_activity', 'moodle_activity__course',
        'qcto_criteria', 'qcto_criteria__module',
        'reviewed_by'
    )
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        mappings = mappings.filter(status=status_filter)
    
    course_filter = request.GET.get('course')
    if course_filter:
        mappings = mappings.filter(moodle_activity__course_id=course_filter)
    
    min_confidence = request.GET.get('min_confidence')
    if min_confidence:
        mappings = mappings.filter(ai_confidence__gte=min_confidence)
    
    # Pagination
    paginator = Paginator(mappings, 10)
    page = request.GET.get('page', 1)
    mappings_page = paginator.get_page(page)
    
    # Stats
    stats = {
        'pending': AssessmentMapping.objects.filter(
            moodle_activity__course__instance=instance, status='PENDING'
        ).count(),
        'approved': AssessmentMapping.objects.filter(
            moodle_activity__course__instance=instance, status='APPROVED'
        ).count(),
        'rejected': AssessmentMapping.objects.filter(
            moodle_activity__course__instance=instance, status='REJECTED'
        ).count(),
        'avg_confidence': AssessmentMapping.objects.filter(
            moodle_activity__course__instance=instance
        ).aggregate(Avg('ai_confidence'))['ai_confidence__avg'] or 0,
    }
    
    # Get courses for filter
    courses = MoodleCourse.objects.filter(instance=instance)
    
    context = {
        'mappings': mappings_page,
        'stats': stats,
        'courses': courses,
        'selected_brand': selected_brand,
    }
    
    return render(request, 'lms_sync/review_mappings.html', context)


@login_required
@require_POST
def test_connection(request):
    """AJAX endpoint to test Moodle connection"""
    selected_brand = get_selected_brand(request)
    
    if not selected_brand:
        return JsonResponse({
            'success': False,
            'message': 'No brand selected'
        })
    
    try:
        instance = MoodleInstance.objects.get(brand=selected_brand)
        client = MoodleClient(instance)
        success, message = client.test_connection()
        
        return JsonResponse({
            'success': success,
            'message': message
        })
    except MoodleInstance.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'No Moodle instance configured for this brand'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
@require_POST
def trigger_sync(request):
    """AJAX endpoint to trigger manual sync"""
    selected_brand = get_selected_brand(request)
    
    if not selected_brand:
        return JsonResponse({
            'success': False,
            'message': 'No brand selected'
        })
    
    try:
        instance = MoodleInstance.objects.get(brand=selected_brand)
        
        # Start sync in background (would use Celery in production)
        # For now, just create a log entry
        sync_log = MoodleSyncLog.objects.create(
            instance=instance,
            sync_type='FULL',
            direction='PULL',
            status='STARTED',
            started_at=timezone.now()
        )
        
        # TODO: Trigger actual sync task here
        
        return JsonResponse({
            'success': True,
            'message': 'Sync started successfully'
        })
    except MoodleInstance.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'No Moodle instance configured for this brand'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
