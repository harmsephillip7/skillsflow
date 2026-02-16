from __future__ import annotations

from django.contrib import auth
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone

from core.jwt_utils import (
    authenticate_request,
    clear_auth_cookies,
    get_cookie_names,
    revoke_by_refresh_token,
)


class JWTAuthenticationMiddleware:
    """Authenticate API requests via JWT access token.

    This middleware is intentionally conservative: it only runs for requests
    that look like API calls (path starts with /api/ or Accept JSON).

    If a Django session already authenticated the user, we keep it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            return self.get_response(request)

        is_api = request.path.startswith("/api/") or "application/json" in (request.META.get("HTTP_ACCEPT") or "")
        if not is_api:
            return self.get_response(request)

        user, session, err = authenticate_request(request)
        if user is not None and err is None:
            request.user = user
            request.jwt_session = session

        return self.get_response(request)


class IdleLogoutMiddleware:
    """Auto-logout for idle users.

    - For session-authenticated browser traffic: tracks last activity in session.
    - For JWT-authenticated API traffic: handled by authenticate_request() via session idle timeout.

    On idle timeout: clears Django session and JWT cookies.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return self.get_response(request)

        # If the user was authenticated by JWT middleware, enforce idle timeout via
        # the JWT session model (handled in authenticate_request) and avoid touching
        # Django sessions/cookies.
        if hasattr(request, "jwt_session"):
            return self.get_response(request)

        from django.conf import settings
        seconds = getattr(settings, "AUTH_IDLE_TIMEOUT_SECONDS", None)
        if not seconds:
            return self.get_response(request)

        try:
            seconds = int(seconds)
        except Exception:
            return self.get_response(request)

        now = timezone.now()
        if not hasattr(request, "session"):
            return self.get_response(request)

        last_activity_ts = request.session.get("last_activity_ts")

        if last_activity_ts:
            try:
                last_activity = timezone.datetime.fromtimestamp(float(last_activity_ts), tz=timezone.get_current_timezone())
                if (now - last_activity).total_seconds() > seconds:
                    # Revoke refresh token session (if cookie still present)
                    _, refresh_cookie_name = get_cookie_names()
                    refresh = request.COOKIES.get(refresh_cookie_name)
                    if refresh:
                        revoke_by_refresh_token(refresh_token=refresh)

                    auth.logout(request)

                    response = self._idle_response(request)
                    clear_auth_cookies(response)
                    try:
                        request.session.flush()
                    except Exception:
                        pass
                    return response
            except Exception:
                pass

        # touch
        request.session["last_activity_ts"] = now.timestamp()

        return self.get_response(request)

    def _idle_response(self, request):
        is_api = request.path.startswith("/api/") or "application/json" in (request.META.get("HTTP_ACCEPT") or "")
        if is_api:
            return JsonResponse({"ok": False, "error": {"code": "idle_timeout", "message": "Logged out"}}, status=401)
        return redirect("core:login")
