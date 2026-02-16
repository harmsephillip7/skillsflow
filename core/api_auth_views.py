from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import Any

from django.contrib.auth import authenticate
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from core.jwt_utils import (
    authenticate_request,
    clear_auth_cookies,
    create_login_session,
    extract_refresh_token,
    get_access_lifetime,
    get_refresh_lifetime,
    revoke_by_refresh_token,
    rotate_or_reuse_refresh_session,
    set_auth_cookies,
)
from core.models import UserTOTPDevice
from core.services.totp_service import TOTPService


def _json_error(message: str, *, status: int = 400, code: str = "error") -> JsonResponse:
    return JsonResponse({"ok": False, "error": {"code": code, "message": message}}, status=status)


def _json_ok(data: dict[str, Any] | None = None) -> JsonResponse:
    payload: dict[str, Any] = {"ok": True}
    if data:
        payload.update(data)
    return JsonResponse(payload)


def _parse_body(request: HttpRequest) -> dict[str, Any]:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


@csrf_exempt
def api_login(request: HttpRequest) -> JsonResponse:
    """
    Enhanced login endpoint with TOTP 2FA support.
    
    Two-step process if 2FA enabled:
    1. POST with email/password -> returns temp_token if 2FA required
    2. POST with temp_token + code -> completes login
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])  # type: ignore[return-value]

    body = _parse_body(request)
    email = (body.get("email") or request.POST.get("email") or "").strip().lower()
    password = body.get("password") or request.POST.get("password") or ""
    temp_token = body.get("temp_token", "").strip()  # For 2FA step
    two_fa_code = (
        body.get("code")
        or body.get("token")
        or body.get("two_fa_code")
        or request.POST.get("two_fa_code")
        or ""
    ).strip()  # 2FA verification code

    # =====================================================
    # STEP 1: Verify 2FA if temp_token provided
    # =====================================================
    if temp_token:
        # Verify the temporary token and 2FA code
        try:
            session_data = cache.get(f"2fa_temp_{temp_token}")
            if not session_data:
                return _json_error("Invalid or expired temporary token", status=401, code="invalid_temp_token")

            user_id = session_data['user_id']
            from core.models import User
            user = User.objects.get(id=user_id)

            # Verify 2FA code
            try:
                totp_device = user.totp_device
            except UserTOTPDevice.DoesNotExist:
                return _json_error("2FA configuration not found", status=400, code="2fa_not_configured")

            # Check for backup code or TOTP code
            use_backup = bool(body.get("use_backup"))
            if use_backup:
                success, remaining = TOTPService.consume_backup_code(totp_device.backup_codes, two_fa_code)
                if not success:
                    return _json_error("Invalid backup code", status=400, code="invalid_backup_code")
                totp_device.backup_codes = remaining
                totp_device.save()
            else:
                if not two_fa_code or not TOTPService.verify_token(totp_device.secret, two_fa_code):
                    return _json_error("Invalid verification code", status=400, code="invalid_code")

            # Update last used
            totp_device.last_used = timezone.now()
            totp_device.save()

            # Clear temp token
            cache.delete(f"2fa_temp_{temp_token}")

            # Complete login
            remember_me = session_data.get("remember_me", False)
            refresh_lifetime = get_refresh_lifetime()
            if remember_me:
                refresh_lifetime = timedelta(days=30)

            session, tokens = create_login_session(
                user=user,
                request=request,
                refresh_lifetime=refresh_lifetime
            )

            resp = _json_ok({
                "access": tokens.access,
                "refresh": tokens.refresh,
                "expires_in": int(get_access_lifetime().total_seconds()),
                "user": {
                    "id": str(user.pk),
                    "email": user.email,
                    "name": user.get_full_name() if hasattr(user, "get_full_name") else "",
                },
            })

            set_auth_cookies(resp, access=tokens.access, refresh=tokens.refresh, refresh_expires_at=session.expires_at)
            return resp

        except Exception as e:
            return _json_error(f"2FA verification failed: {str(e)}", status=400, code="2fa_error")

    # =====================================================
    # STEP 2: Initial password authentication
    # =====================================================
    if not email or not password:
        return _json_error("Email and password are required", status=400, code="missing_credentials")

    user = authenticate(request, username=email, password=password)
    if user is None or not user.is_active:
        return _json_error("Invalid credentials", status=401, code="invalid_credentials")

    # =====================================================
    # CHECK: Is 2FA enabled?
    # =====================================================
    try:
        totp_device = user.totp_device
        if totp_device.is_active and totp_device.is_confirmed:
            # 2FA is enabled - require second factor
            # Generate temporary token for 2FA verification
            temp_token = str(uuid.uuid4())
            remember_me = bool(body.get("remember_me"))

            # Store temp session (expires in 5 minutes)
            session_data = {
                'user_id': user.id,
                'email': email,
                'remember_me': remember_me,
            }
            cache.set(f"2fa_temp_{temp_token}", session_data, timeout=300)

            # Return 2FA required response
            return _json_ok({
                "requires_2fa": True,
                "temp_token": temp_token,
                "user_id": str(user.id),
                "message": "Please enter your 2FA code",
                "backup_code_available": bool(totp_device.backup_codes)
            })

    except UserTOTPDevice.DoesNotExist:
        # 2FA not configured, continue with normal login
        pass

    # =====================================================
    # Normal login (no 2FA or 2FA not enabled)
    # =====================================================
    remember_me = bool(body.get("remember_me"))
    refresh_lifetime = get_refresh_lifetime()
    if remember_me:
        refresh_lifetime = timedelta(days=30)

    session, tokens = create_login_session(user=user, request=request, refresh_lifetime=refresh_lifetime)

    resp = _json_ok(
        {
            "access": tokens.access,
            "refresh": tokens.refresh,
            "expires_in": int(get_access_lifetime().total_seconds()),
            "user": {
                "id": str(user.pk),
                "email": user.email,
                "name": user.get_full_name() if hasattr(user, "get_full_name") else "",
            },
        }
    )

    # By default set httpOnly cookies as well (safe for browser and allows same-origin API calls)
    set_auth_cookies(resp, access=tokens.access, refresh=tokens.refresh, refresh_expires_at=session.expires_at)
    return resp


@csrf_exempt
def api_refresh(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])  # type: ignore[return-value]

    refresh = extract_refresh_token(request)
    if not refresh:
        return _json_error("Refresh token required", status=401, code="missing_refresh")

    try:
        session, tokens = rotate_or_reuse_refresh_session(refresh_token=refresh, request=request)
    except PermissionError as e:
        return _json_error(str(e), status=401, code="invalid_refresh")

    resp = _json_ok({"access": tokens.access, "refresh": tokens.refresh})
    set_auth_cookies(resp, access=tokens.access, refresh=tokens.refresh, refresh_expires_at=session.expires_at)
    return resp


@csrf_exempt
def api_logout(request: HttpRequest) -> JsonResponse:
    if request.method not in ("POST", "DELETE"):
        return HttpResponseNotAllowed(["POST", "DELETE"])  # type: ignore[return-value]

    refresh = extract_refresh_token(request)
    if refresh:
        revoke_by_refresh_token(refresh_token=refresh)

    resp = _json_ok({"message": "Logged out"})
    clear_auth_cookies(resp)
    return resp


def api_me(request: HttpRequest) -> JsonResponse:
    user, session, err = authenticate_request(request)
    if err or user is None:
        return _json_error("Unauthorized", status=401, code=err or "unauthorized")

    return _json_ok(
        {
            "user": {
                "id": str(user.pk),
                "email": user.email,
                "name": user.get_full_name() if hasattr(user, "get_full_name") else "",
                "is_staff": bool(getattr(user, "is_staff", False)),
                "is_superuser": bool(getattr(user, "is_superuser", False)),
            },
            "session": {
                "id": str(session.id) if session else None,
                "last_used_at": session.last_used_at.isoformat() if session and session.last_used_at else None,
                "expires_at": session.expires_at.isoformat() if session and session.expires_at else None,
            },
        }
    )


def api_sessions(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])  # type: ignore[return-value]

    user, session, err = authenticate_request(request)
    if err or user is None:
        return _json_error("Unauthorized", status=401, code=err or "unauthorized")

    from core.models import UserAuthSession

    sessions = (
        UserAuthSession.objects.filter(user=user, revoked_at__isnull=True)
        .order_by("-last_used_at")
        .values("id", "created_at", "last_used_at", "expires_at", "ip_address", "user_agent")
    )

    return _json_ok({"sessions": list(sessions)})


@csrf_exempt
def api_revoke_session(request: HttpRequest, session_id: str) -> JsonResponse:
    if request.method not in ("POST", "DELETE"):
        return HttpResponseNotAllowed(["POST", "DELETE"])  # type: ignore[return-value]

    user, _, err = authenticate_request(request)
    if err or user is None:
        return _json_error("Unauthorized", status=401, code=err or "unauthorized")

    from core.models import UserAuthSession

    try:
        sess = UserAuthSession.objects.get(pk=session_id, user=user)
    except UserAuthSession.DoesNotExist:
        return _json_error("Session not found", status=404, code="not_found")

    sess.revoke(reason="revoked_by_user")

    return _json_ok({"message": "Session revoked", "session_id": session_id})
