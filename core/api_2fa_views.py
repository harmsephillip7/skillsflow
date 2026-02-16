"""
Two-Factor Authentication (TOTP) API Views
Handles Google Authenticator setup and verification
"""
import json
from django.http import HttpRequest, JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.models import UserTOTPDevice
from core.services.totp_service import TOTPService
from core.jwt_utils import authenticate_request

User = get_user_model()


def _get_authenticated_user(request: HttpRequest):
    """Return user from session or JWT token."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user
    return authenticate_request(request)


def _json_error(message: str, *, status: int = 400, code: str = "error") -> JsonResponse:
    """Return JSON error response"""
    return JsonResponse(
        {"ok": False, "error": {"code": code, "message": message}},
        status=status
    )


def _json_ok(data: dict = None) -> JsonResponse:
    """Return JSON success response"""
    payload = {"ok": True}
    if data:
        payload.update(data)
    return JsonResponse(payload)


def _parse_body(request: HttpRequest) -> dict:
    """Parse JSON request body"""
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


@csrf_exempt
def api_2fa_setup_initiate(request: HttpRequest) -> JsonResponse:
    """
    Initiate 2FA setup - generate secret and QR code
    GET /api/auth/2fa/setup/
    
    Returns:
        - secret: Base32 secret for manual entry
        - qr_code: Base64-encoded QR code data URL
        - backup_codes: List of recovery codes
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    
    user = _get_authenticated_user(request)
    if not user:
        return _json_error("Authentication required", status=401, code="unauthorized")
    
    # Check if user already has TOTP enabled
    try:
        totp_device = user.totp_device
        if totp_device.is_confirmed and totp_device.is_active:
            return _json_error(
                "2FA is already enabled for this account",
                status=400,
                code="2fa_already_enabled"
            )
    except UserTOTPDevice.DoesNotExist:
        pass
    
    # Generate setup info
    setup_info = TOTPService.get_totp_setup_info(user.email)
    
    return _json_ok({
        "secret": setup_info["secret"],
        "qr_code": setup_info["qr_code"],
        "backup_codes": setup_info["backup_codes"],
    })


@csrf_exempt
def api_2fa_setup_confirm(request: HttpRequest) -> JsonResponse:
    """
    Confirm 2FA setup by verifying initial token
    POST /api/auth/2fa/setup/confirm/
    
    Body:
        - secret: The secret from setup initiation
        - token: 6-digit code from Google Authenticator
        - backup_codes: Backup codes to store
    
    Returns:
        - Success/failure confirmation
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    
    user = _get_authenticated_user(request)
    if not user:
        return _json_error("Authentication required", status=401, code="unauthorized")
    
    body = _parse_body(request)
    secret = body.get("secret", "").strip()
    token = body.get("token", "").strip()
    backup_codes = body.get("backup_codes", [])
    
    if not secret or not token:
        return _json_error(
            "Secret and token are required",
            status=400,
            code="missing_fields"
        )
    
    # Verify the token
    if not TOTPService.verify_token(secret, token):
        return _json_error(
            "Invalid verification code",
            status=400,
            code="invalid_token"
        )
    
    if not backup_codes:
        backup_codes = TOTPService.generate_backup_codes()

    # Create or update TOTP device
    totp_device, created = UserTOTPDevice.objects.update_or_create(
        user=user,
        defaults={
            "secret": secret,
            "is_confirmed": True,
            "is_active": True,
            "backup_codes": TOTPService.format_backup_codes(backup_codes),
            "confirmed_at": timezone.now(),
        }
    )
    
    return _json_ok({
        "message": "2FA has been successfully enabled",
        "created": created,
    })


@csrf_exempt
def api_2fa_verify(request: HttpRequest) -> JsonResponse:
    """
    Verify TOTP token during login
    POST /api/auth/2fa/verify/
    
    Body:
        - user_id or email: User identifier
        - token: 6-digit code from Google Authenticator
        - use_backup: Boolean if using backup code instead
    
    Returns:
        - verified: Boolean success
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    
    body = _parse_body(request)
    user_identifier = body.get("user_id") or body.get("email")
    token = body.get("token", "").strip()
    use_backup = body.get("use_backup", False)
    
    if not user_identifier or not token:
        return _json_error(
            "User identifier and token are required",
            status=400,
            code="missing_fields"
        )
    
    # Get user
    try:
        if "@" in str(user_identifier):
            user = User.objects.get(email=user_identifier)
        else:
            user = User.objects.get(id=user_identifier)
    except User.DoesNotExist:
        return _json_error("User not found", status=404, code="user_not_found")
    
    # Get TOTP device
    try:
        totp_device = user.totp_device
        if not totp_device.is_confirmed or not totp_device.is_active:
            return _json_error(
                "2FA is not enabled for this account",
                status=400,
                code="2fa_not_enabled"
            )
    except UserTOTPDevice.DoesNotExist:
        return _json_error(
            "2FA is not enabled for this account",
            status=400,
            code="2fa_not_enabled"
        )
    
    # Verify token or backup code
    if use_backup:
        success, remaining_codes = TOTPService.consume_backup_code(
            totp_device.backup_codes,
            token
        )
        if not success:
            return _json_error(
                "Invalid backup code",
                status=400,
                code="invalid_backup_code"
            )
        # Update remaining codes
        totp_device.backup_codes = remaining_codes
        totp_device.save()
    else:
        if not TOTPService.verify_token(totp_device.secret, token):
            return _json_error(
                "Invalid verification code",
                status=400,
                code="invalid_token"
            )
    
    # Update last used timestamp
    totp_device.last_used = timezone.now()
    totp_device.save()
    
    return _json_ok({"verified": True})


@csrf_exempt
def api_2fa_disable(request: HttpRequest) -> JsonResponse:
    """
    Disable 2FA for the authenticated user
    POST /api/auth/2fa/disable/
    
    Body:
        - token: 6-digit code to verify before disabling
    
    Returns:
        - Success/failure confirmation
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    
    user = _get_authenticated_user(request)
    if not user:
        return _json_error("Authentication required", status=401, code="unauthorized")
    
    body = _parse_body(request)
    token = body.get("token", "").strip()
    
    try:
        totp_device = user.totp_device
    except UserTOTPDevice.DoesNotExist:
        return _json_error(
            "2FA is not enabled for this account",
            status=400,
            code="2fa_not_enabled"
        )
    
    # Verify token before allowing disabling
    if not token or not TOTPService.verify_token(totp_device.secret, token):
        return _json_error(
            "Invalid verification code",
            status=400,
            code="invalid_token"
        )
    
    # Disable 2FA
    totp_device.is_active = False
    totp_device.save()
    
    return _json_ok({"message": "2FA has been disabled"})


@csrf_exempt
def api_2fa_status(request: HttpRequest) -> JsonResponse:
    """
    Get 2FA status for authenticated user
    GET /api/auth/2fa/status/
    
    Returns:
        - is_enabled: Boolean
        - backup_codes_remaining: Count of remaining backup codes
        - last_used: Timestamp of last verification
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    
    user = _get_authenticated_user(request)
    if not user:
        return _json_error("Authentication required", status=401, code="unauthorized")
    
    try:
        totp_device = user.totp_device
        backup_codes = TOTPService.parse_backup_codes(totp_device.backup_codes)
        
        return _json_ok({
            "is_enabled": totp_device.is_active and totp_device.is_confirmed,
            "backup_codes_remaining": len(backup_codes),
            "total_backup_codes": len(backup_codes),
            "backup_codes": backup_codes,
            "last_used": totp_device.last_used.isoformat() if totp_device.last_used else None,
            "confirmed_at": totp_device.confirmed_at.isoformat() if totp_device.confirmed_at else None,
            "created_at": totp_device.created_at.isoformat(),
        })
    except UserTOTPDevice.DoesNotExist:
        return _json_ok({
            "is_enabled": False,
            "backup_codes_remaining": 0,
            "total_backup_codes": 0,
            "backup_codes": [],
            "last_used": None,
        })


@csrf_exempt
def api_2fa_regenerate_backup_codes(request: HttpRequest) -> JsonResponse:
    """
    Regenerate backup codes for authenticated user.
    POST /api/auth/2fa/backup-codes/regenerate/

    Body:
        - token: 6-digit code from authenticator
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user = _get_authenticated_user(request)
    if not user:
        return _json_error("Authentication required", status=401, code="unauthorized")

    body = _parse_body(request)
    token = body.get("token", "").strip()

    try:
        totp_device = user.totp_device
    except UserTOTPDevice.DoesNotExist:
        return _json_error("2FA is not enabled for this account", status=400, code="2fa_not_enabled")

    if not token or not TOTPService.verify_token(totp_device.secret, token):
        return _json_error("Invalid verification code", status=400, code="invalid_token")

    new_codes = TOTPService.generate_backup_codes()
    totp_device.backup_codes = TOTPService.format_backup_codes(new_codes)
    totp_device.save()

    return _json_ok({
        "message": "Backup codes regenerated",
        "backup_codes": new_codes,
        "backup_codes_remaining": len(new_codes),
        "total_backup_codes": len(new_codes),
    })
