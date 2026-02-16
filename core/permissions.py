"""
Permission system for SkillsFlow ERP
Defines permission codes and role-permission mappings
"""
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from datetime import date


class PermissionCode:
    """All permission codes in the system"""
    
    # Learner Permissions
    LEARNER_VIEW = 'learner.view'
    LEARNER_CREATE = 'learner.create'
    LEARNER_EDIT = 'learner.edit'
    LEARNER_DELETE = 'learner.delete'
    LEARNER_EXPORT = 'learner.export'
    
    # Assessment Permissions
    ASSESSMENT_VIEW = 'assessment.view'
    ASSESSMENT_CAPTURE = 'assessment.capture'
    ASSESSMENT_MODERATE = 'assessment.moderate'
    ASSESSMENT_FINALIZE = 'assessment.finalize'
    ASSESSMENT_APPEAL = 'assessment.appeal'
    
    # Finance Permissions
    FINANCE_VIEW = 'finance.view'
    FINANCE_CREATE_INVOICE = 'finance.create_invoice'
    FINANCE_RECORD_PAYMENT = 'finance.record_payment'
    FINANCE_APPLY_HOLD = 'finance.apply_hold'
    FINANCE_EXPORT = 'finance.export'
    
    # Corporate Permissions
    CORPORATE_VIEW = 'corporate.view'
    CORPORATE_MANAGE_CLIENTS = 'corporate.manage_clients'
    CORPORATE_MANAGE_WSP = 'corporate.manage_wsp'
    CORPORATE_MANAGE_EE = 'corporate.manage_ee'
    CORPORATE_MANAGE_BBBEE = 'corporate.manage_bbbee'
    CORPORATE_MANAGE_GRANTS = 'corporate.manage_grants'
    
    # CRM Permissions
    CRM_VIEW = 'crm.view'
    CRM_CREATE_LEAD = 'crm.create_lead'
    CRM_EDIT_LEAD = 'crm.edit_lead'
    CRM_CONVERT_LEAD = 'crm.convert_lead'
    
    # Report Permissions
    REPORT_VIEW_OWN = 'report.view_own'
    REPORT_VIEW_CAMPUS = 'report.view_campus'
    REPORT_VIEW_BRAND = 'report.view_brand'
    REPORT_VIEW_ALL = 'report.view_all'
    REPORT_EXPORT = 'report.export'
    
    # Settings Permissions
    SETTINGS_VIEW = 'settings.view'
    SETTINGS_EDIT = 'settings.edit'
    SETTINGS_MANAGE_USERS = 'settings.manage_users'
    SETTINGS_MANAGE_ROLES = 'settings.manage_roles'
    
    # Scheduling Permissions
    SCHEDULE_VIEW = 'schedule.view'
    SCHEDULE_CREATE = 'schedule.create'
    SCHEDULE_EDIT = 'schedule.edit'
    
    # Attendance Permissions
    ATTENDANCE_VIEW = 'attendance.view'
    ATTENDANCE_CAPTURE = 'attendance.capture'
    ATTENDANCE_EDIT = 'attendance.edit'


# Role permission mappings
ROLE_PERMISSIONS = {
    'SUPER_ADMIN': ['*'],  # All permissions
    
    'SYSTEM_ADMIN': ['*'],
    
    'HEAD_OFFICE_MANAGER': [
        PermissionCode.LEARNER_VIEW, PermissionCode.LEARNER_CREATE, 
        PermissionCode.LEARNER_EDIT, PermissionCode.LEARNER_EXPORT,
        PermissionCode.ASSESSMENT_VIEW, PermissionCode.ASSESSMENT_FINALIZE,
        PermissionCode.FINANCE_VIEW, PermissionCode.FINANCE_EXPORT,
        PermissionCode.CORPORATE_VIEW, PermissionCode.CORPORATE_MANAGE_CLIENTS,
        PermissionCode.CRM_VIEW, PermissionCode.CRM_CREATE_LEAD,
        PermissionCode.REPORT_VIEW_ALL, PermissionCode.REPORT_EXPORT,
        PermissionCode.SETTINGS_VIEW,
    ],
    
    'FINANCE_DIRECTOR': [
        PermissionCode.LEARNER_VIEW,
        PermissionCode.FINANCE_VIEW, PermissionCode.FINANCE_CREATE_INVOICE,
        PermissionCode.FINANCE_RECORD_PAYMENT, PermissionCode.FINANCE_APPLY_HOLD,
        PermissionCode.FINANCE_EXPORT,
        PermissionCode.CORPORATE_VIEW,
        PermissionCode.REPORT_VIEW_ALL, PermissionCode.REPORT_EXPORT,
    ],
    
    'ACADEMIC_DIRECTOR': [
        PermissionCode.LEARNER_VIEW, PermissionCode.LEARNER_EXPORT,
        PermissionCode.ASSESSMENT_VIEW, PermissionCode.ASSESSMENT_FINALIZE,
        PermissionCode.SCHEDULE_VIEW, PermissionCode.SCHEDULE_CREATE,
        PermissionCode.ATTENDANCE_VIEW,
        PermissionCode.REPORT_VIEW_ALL, PermissionCode.REPORT_EXPORT,
    ],
    
    'BRAND_MANAGER': [
        PermissionCode.LEARNER_VIEW, PermissionCode.LEARNER_CREATE,
        PermissionCode.LEARNER_EDIT, PermissionCode.LEARNER_EXPORT,
        PermissionCode.ASSESSMENT_VIEW,
        PermissionCode.FINANCE_VIEW,
        PermissionCode.CORPORATE_VIEW,
        PermissionCode.CRM_VIEW, PermissionCode.CRM_CREATE_LEAD,
        PermissionCode.REPORT_VIEW_BRAND, PermissionCode.REPORT_EXPORT,
    ],
    
    'CAMPUS_PRINCIPAL': [
        PermissionCode.LEARNER_VIEW, PermissionCode.LEARNER_CREATE,
        PermissionCode.LEARNER_EDIT,
        PermissionCode.ASSESSMENT_VIEW,
        PermissionCode.FINANCE_VIEW,
        PermissionCode.SCHEDULE_VIEW, PermissionCode.SCHEDULE_CREATE,
        PermissionCode.ATTENDANCE_VIEW,
        PermissionCode.REPORT_VIEW_CAMPUS,
    ],
    
    'CAMPUS_ADMIN': [
        PermissionCode.LEARNER_VIEW, PermissionCode.LEARNER_CREATE,
        PermissionCode.LEARNER_EDIT,
        PermissionCode.SCHEDULE_VIEW, PermissionCode.SCHEDULE_CREATE,
        PermissionCode.ATTENDANCE_VIEW, PermissionCode.ATTENDANCE_CAPTURE,
        PermissionCode.REPORT_VIEW_CAMPUS,
    ],
    
    'REGISTRAR': [
        PermissionCode.LEARNER_VIEW, PermissionCode.LEARNER_CREATE,
        PermissionCode.LEARNER_EDIT,
        PermissionCode.CRM_VIEW, PermissionCode.CRM_CREATE_LEAD,
        PermissionCode.CRM_CONVERT_LEAD,
    ],
    
    'FACILITATOR': [
        PermissionCode.LEARNER_VIEW,
        PermissionCode.ASSESSMENT_VIEW, PermissionCode.ASSESSMENT_CAPTURE,
        PermissionCode.SCHEDULE_VIEW,
        PermissionCode.ATTENDANCE_VIEW, PermissionCode.ATTENDANCE_CAPTURE,
        PermissionCode.REPORT_VIEW_OWN,
    ],
    
    'ASSESSOR': [
        PermissionCode.LEARNER_VIEW,
        PermissionCode.ASSESSMENT_VIEW, PermissionCode.ASSESSMENT_CAPTURE,
        PermissionCode.REPORT_VIEW_OWN,
    ],
    
    'MODERATOR': [
        PermissionCode.LEARNER_VIEW,
        PermissionCode.ASSESSMENT_VIEW, PermissionCode.ASSESSMENT_MODERATE,
        PermissionCode.REPORT_VIEW_OWN,
    ],
    
    'QCTO_INTERNAL_MODERATOR': [
        PermissionCode.LEARNER_VIEW,
        PermissionCode.ASSESSMENT_VIEW, PermissionCode.ASSESSMENT_MODERATE,
        PermissionCode.ASSESSMENT_FINALIZE,
        PermissionCode.REPORT_VIEW_CAMPUS,
    ],
    
    'SDF': [
        PermissionCode.CORPORATE_VIEW, PermissionCode.CORPORATE_MANAGE_WSP,
        PermissionCode.CORPORATE_MANAGE_EE, PermissionCode.CORPORATE_MANAGE_BBBEE,
        PermissionCode.CORPORATE_MANAGE_GRANTS,
        PermissionCode.REPORT_VIEW_OWN,
    ],
    
    'SALES_MANAGER': [
        PermissionCode.LEARNER_VIEW,
        PermissionCode.CRM_VIEW, PermissionCode.CRM_CREATE_LEAD,
        PermissionCode.CRM_EDIT_LEAD, PermissionCode.CRM_CONVERT_LEAD,
        PermissionCode.FINANCE_VIEW,
        PermissionCode.REPORT_VIEW_CAMPUS,
    ],
    
    'SALES_REP': [
        PermissionCode.LEARNER_CREATE,
        PermissionCode.CRM_VIEW, PermissionCode.CRM_CREATE_LEAD,
        PermissionCode.CRM_EDIT_LEAD,
        PermissionCode.REPORT_VIEW_OWN,
    ],
    
    'FINANCE_MANAGER': [
        PermissionCode.LEARNER_VIEW,
        PermissionCode.FINANCE_VIEW, PermissionCode.FINANCE_CREATE_INVOICE,
        PermissionCode.FINANCE_RECORD_PAYMENT, PermissionCode.FINANCE_APPLY_HOLD,
        PermissionCode.REPORT_VIEW_CAMPUS,
    ],
    
    'FINANCE_CLERK': [
        PermissionCode.LEARNER_VIEW,
        PermissionCode.FINANCE_VIEW, PermissionCode.FINANCE_RECORD_PAYMENT,
        PermissionCode.REPORT_VIEW_OWN,
    ],
    
    'STUDENT': [
        PermissionCode.LEARNER_VIEW,  # Own only
        PermissionCode.ASSESSMENT_VIEW,  # Own only
        PermissionCode.FINANCE_VIEW,  # Own only
        PermissionCode.REPORT_VIEW_OWN,
    ],
    
    'CORPORATE_CLIENT_ADMIN': [
        PermissionCode.CORPORATE_VIEW, PermissionCode.CORPORATE_MANAGE_CLIENTS,
        PermissionCode.CORPORATE_MANAGE_WSP, PermissionCode.CORPORATE_MANAGE_EE,
        PermissionCode.CORPORATE_MANAGE_BBBEE,
        PermissionCode.FINANCE_VIEW,
        PermissionCode.REPORT_VIEW_OWN,
    ],
    
    'CORPORATE_CLIENT_HR': [
        PermissionCode.CORPORATE_VIEW,
        PermissionCode.CORPORATE_MANAGE_WSP,
        PermissionCode.CORPORATE_MANAGE_EE,
        PermissionCode.FINANCE_VIEW,
        PermissionCode.REPORT_VIEW_OWN,
    ],
    
    'CORPORATE_CLIENT_SDF': [
        PermissionCode.CORPORATE_VIEW,
        PermissionCode.CORPORATE_MANAGE_WSP,
        PermissionCode.REPORT_VIEW_OWN,
    ],
    
    'CORPORATE_EMPLOYEE': [
        PermissionCode.REPORT_VIEW_OWN,  # Own IDP only
    ],
}


def check_user_permission(user, permission_code):
    """
    Check if user has a specific permission
    Returns True if permission granted, False otherwise
    """
    from .models import UserRole
    
    if not user.is_authenticated:
        return False
    
    # Superusers have all permissions
    if user.is_superuser:
        return True
    
    # Get active roles for user
    user_roles = UserRole.objects.filter(
        user=user,
        is_active=True,
        valid_from__lte=date.today()
    ).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gte=date.today())
    ).select_related('role')
    
    for user_role in user_roles:
        role_perms = ROLE_PERMISSIONS.get(user_role.role.code, [])
        if '*' in role_perms or permission_code in role_perms:
            return True
    
    return False


def has_permission(permission_code):
    """
    Decorator to check user permissions on views
    Usage: @has_permission(PermissionCode.LEARNER_VIEW)
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not check_user_permission(request.user, permission_code):
                raise PermissionDenied(f"Permission denied: {permission_code}")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def has_any_permission(*permission_codes):
    """
    Decorator to check if user has any of the specified permissions
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            for perm in permission_codes:
                if check_user_permission(request.user, perm):
                    return view_func(request, *args, **kwargs)
            raise PermissionDenied("Permission denied")
        return _wrapped_view
    return decorator
