from django.urls import path

from core import api_auth_views
from core import api_2fa_views


urlpatterns = [
    path("login/", api_auth_views.api_login, name="api_login"),
    path("refresh/", api_auth_views.api_refresh, name="api_refresh"),
    path("logout/", api_auth_views.api_logout, name="api_logout"),
    path("me/", api_auth_views.api_me, name="api_me"),
    path("sessions/", api_auth_views.api_sessions, name="api_sessions"),
    path("sessions/<uuid:session_id>/revoke/", api_auth_views.api_revoke_session, name="api_revoke_session"),
    
    # Two-Factor Authentication (TOTP/Google Authenticator)
    path("2fa/setup/", api_2fa_views.api_2fa_setup_initiate, name="api_2fa_setup_initiate"),
    path("2fa/setup/confirm/", api_2fa_views.api_2fa_setup_confirm, name="api_2fa_setup_confirm"),
    path("2fa/verify/", api_2fa_views.api_2fa_verify, name="api_2fa_verify"),
    path("2fa/disable/", api_2fa_views.api_2fa_disable, name="api_2fa_disable"),
    path("2fa/status/", api_2fa_views.api_2fa_status, name="api_2fa_status"),
    path("2fa/backup-codes/regenerate/", api_2fa_views.api_2fa_regenerate_backup_codes, name="api_2fa_regenerate_backup_codes"),
]
