"""JWT + refresh-token session utilities.

This project primarily uses Django sessions for server-rendered pages, but we also
support stateless API auth via short-lived JWT access tokens + rotating refresh
tokens stored server-side.

Access tokens are JWTs (HS256) signed with settings.NINJA_JWT['SIGNING_KEY'].
Refresh tokens are opaque random strings and are stored hashed in the DB.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional, Tuple

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.utils import timezone


USER_MODEL = get_user_model()


@dataclass(frozen=True)
class TokenPair:
    access: str
    refresh: str


def _jwt_settings() -> dict:
    return getattr(settings, "NINJA_JWT", {}) or {}


def get_access_lifetime() -> timedelta:
    return _jwt_settings().get("ACCESS_TOKEN_LIFETIME", timedelta(hours=1))


def get_refresh_lifetime() -> timedelta:
    return _jwt_settings().get("REFRESH_TOKEN_LIFETIME", timedelta(days=7))


def get_rotate_refresh_tokens() -> bool:
    return bool(_jwt_settings().get("ROTATE_REFRESH_TOKENS", True))


def get_blacklist_after_rotation() -> bool:
    return bool(_jwt_settings().get("BLACKLIST_AFTER_ROTATION", True))


def get_algorithm() -> str:
    return _jwt_settings().get("ALGORITHM", "HS256")


def get_signing_key() -> str:
    return _jwt_settings().get("SIGNING_KEY", settings.SECRET_KEY)


def get_cookie_names() -> tuple[str, str]:
    access_name = getattr(settings, "JWT_ACCESS_COOKIE_NAME", "sf_access")
    refresh_name = getattr(settings, "JWT_REFRESH_COOKIE_NAME", "sf_refresh")
    return access_name, refresh_name


def get_idle_timeout() -> Optional[timedelta]:
    seconds = getattr(settings, "AUTH_IDLE_TIMEOUT_SECONDS", None)
    if seconds in (None, "", 0, "0"):
        return None
    try:
        return timedelta(seconds=int(seconds))
    except Exception:
        return None


def _now() -> timezone.datetime:
    return timezone.now()


def _hash_refresh_token(refresh_token: str) -> str:
    """Hash refresh tokens for storage/lookup.

    Uses HMAC(SECRET_KEY, token) to avoid direct SHA storage.
    """

    key = str(get_signing_key()).encode("utf-8")
    msg = refresh_token.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def issue_access_token(*, user: USER_MODEL, session_id: str) -> str:
    issued_at = _now()
    exp = issued_at + get_access_lifetime()

    payload = {
        "type": "access",
        "sub": str(user.pk),
        "email": getattr(user, "email", ""),
        "sid": str(session_id),
        "iat": int(issued_at.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(16),
    }

    token = jwt.encode(payload, get_signing_key(), algorithm=get_algorithm())
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decode_access_token(access_token: str) -> dict[str, Any]:
    return jwt.decode(
        access_token,
        get_signing_key(),
        algorithms=[get_algorithm()],
        options={"require": ["exp", "iat", "sub", "sid"]},
    )


def _get_client_ip(request: HttpRequest) -> Optional[str]:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        # Use first hop
        return forwarded_for.split(",")[0].strip()[:45]
    return request.META.get("REMOTE_ADDR")


def _get_user_agent(request: HttpRequest) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:500]


def _parse_json_body(request: HttpRequest) -> dict[str, Any]:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


def extract_access_token(request: HttpRequest) -> Optional[str]:
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip() or None

    access_cookie_name, _ = get_cookie_names()
    cookie_token = request.COOKIES.get(access_cookie_name)
    return cookie_token or None


def extract_refresh_token(request: HttpRequest) -> Optional[str]:
    body = _parse_json_body(request)
    if isinstance(body, dict) and body.get("refresh"):
        return str(body.get("refresh"))

    header_token = request.META.get("HTTP_X_REFRESH_TOKEN")
    if header_token:
        return header_token

    _, refresh_cookie_name = get_cookie_names()
    cookie_token = request.COOKIES.get(refresh_cookie_name)
    return cookie_token or None


def set_auth_cookies(response, *, access: str, refresh: str, refresh_expires_at) -> None:
    access_cookie_name, refresh_cookie_name = get_cookie_names()

    secure = bool(getattr(settings, "JWT_COOKIE_SECURE", not settings.DEBUG))
    samesite = getattr(settings, "JWT_COOKIE_SAMESITE", "Lax")
    domain = getattr(settings, "JWT_COOKIE_DOMAIN", None)
    path = getattr(settings, "JWT_COOKIE_PATH", "/")

    # Access cookie: session-ish; expires with token lifetime
    response.set_cookie(
        access_cookie_name,
        access,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path=path,
        max_age=int(get_access_lifetime().total_seconds()),
    )

    # Refresh cookie: persistent
    max_age = int((refresh_expires_at - _now()).total_seconds())
    if max_age < 0:
        max_age = 0

    response.set_cookie(
        refresh_cookie_name,
        refresh,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path=path,
        max_age=max_age,
    )


def clear_auth_cookies(response) -> None:
    access_cookie_name, refresh_cookie_name = get_cookie_names()
    domain = getattr(settings, "JWT_COOKIE_DOMAIN", None)
    path = getattr(settings, "JWT_COOKIE_PATH", "/")

    response.delete_cookie(access_cookie_name, domain=domain, path=path)
    response.delete_cookie(refresh_cookie_name, domain=domain, path=path)


def create_login_session(*, user: USER_MODEL, request: HttpRequest, refresh_lifetime: Optional[timedelta] = None) -> Tuple["UserAuthSession", TokenPair]:
    from core.models import UserAuthSession

    refresh_lifetime = refresh_lifetime or get_refresh_lifetime()
    refresh_token = secrets.token_urlsafe(48)
    refresh_hash = _hash_refresh_token(refresh_token)

    now = _now()
    session = UserAuthSession.objects.create(
        user=user,
        refresh_token_hash=refresh_hash,
        expires_at=now + refresh_lifetime,
        last_used_at=now,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    access_token = issue_access_token(user=user, session_id=str(session.id))
    return session, TokenPair(access=access_token, refresh=refresh_token)


def rotate_or_reuse_refresh_session(*, refresh_token: str, request: HttpRequest) -> Tuple["UserAuthSession", TokenPair]:
    """Validate refresh token and return a fresh access token.

    If rotation is enabled, a new refresh token is issued and the old one is
    revoked.
    """

    from core.models import UserAuthSession

    refresh_hash = _hash_refresh_token(refresh_token)
    try:
        session = UserAuthSession.objects.select_related("user").get(refresh_token_hash=refresh_hash)
    except UserAuthSession.DoesNotExist:
        raise PermissionError("Invalid refresh token")

    if not session.is_active:
        raise PermissionError("Refresh token revoked")

    now = _now()
    if session.expires_at and now >= session.expires_at:
        session.revoke(reason="expired")
        raise PermissionError("Refresh token expired")

    idle_timeout = get_idle_timeout()
    if idle_timeout and session.last_used_at and now - session.last_used_at > idle_timeout:
        session.revoke(reason="idle_timeout")
        raise PermissionError("Session expired")

    # Update telemetry
    session.last_used_at = now
    session.ip_address = _get_client_ip(request)
    session.user_agent = _get_user_agent(request)
    session.save(update_fields=["last_used_at", "ip_address", "user_agent"])

    # Rotate refresh token
    rotate = get_rotate_refresh_tokens()
    if rotate:
        new_refresh = secrets.token_urlsafe(48)
        new_refresh_hash = _hash_refresh_token(new_refresh)
        new_session = UserAuthSession.objects.create(
            user=session.user,
            refresh_token_hash=new_refresh_hash,
            expires_at=now + get_refresh_lifetime(),
            last_used_at=now,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            rotated_from=session,
        )

        if get_blacklist_after_rotation():
            session.revoke(reason="rotated")

        access = issue_access_token(user=new_session.user, session_id=str(new_session.id))
        return new_session, TokenPair(access=access, refresh=new_refresh)

    # No rotation, reuse
    access = issue_access_token(user=session.user, session_id=str(session.id))
    return session, TokenPair(access=access, refresh=refresh_token)


def revoke_by_refresh_token(*, refresh_token: str) -> None:
    from core.models import UserAuthSession

    refresh_hash = _hash_refresh_token(refresh_token)
    try:
        session = UserAuthSession.objects.get(refresh_token_hash=refresh_hash)
    except UserAuthSession.DoesNotExist:
        return
    session.revoke(reason="logout")


def authenticate_request(request: HttpRequest) -> Tuple[Optional[USER_MODEL], Optional["UserAuthSession"], Optional[str]]:
    """Authenticate request using access JWT from header/cookie.

    Returns (user, session, error_code).
    """

    from core.models import UserAuthSession

    token = extract_access_token(request)
    if not token:
        return None, None, "missing_token"

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        return None, None, "expired"
    except Exception:
        return None, None, "invalid"

    if payload.get("type") != "access":
        return None, None, "invalid_type"

    user_id = payload.get("sub")
    session_id = payload.get("sid")

    try:
        user = USER_MODEL.objects.get(pk=user_id)
    except USER_MODEL.DoesNotExist:
        return None, None, "user_not_found"

    try:
        session = UserAuthSession.objects.select_related("user").get(pk=session_id, user=user)
    except UserAuthSession.DoesNotExist:
        return None, None, "session_not_found"

    if not session.is_active:
        return None, None, "session_revoked"

    now = _now()
    if session.expires_at and now >= session.expires_at:
        session.revoke(reason="expired")
        return None, None, "session_expired"

    idle_timeout = get_idle_timeout()
    if idle_timeout and session.last_used_at and now - session.last_used_at > idle_timeout:
        session.revoke(reason="idle_timeout")
        return None, None, "session_idle"

    # Touch activity timestamp for active requests
    session.last_used_at = now
    session.save(update_fields=["last_used_at"])

    return user, session, None
