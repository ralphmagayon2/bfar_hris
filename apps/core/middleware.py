"""
apps/core/middleware.py

BFAR Region III — HRIS
Two focused middlewares, registered in settings.MIDDLEWARE.

NoCacheAuthPagesMiddleware
    Adds no-store headers on login/logout URLs so the browser
    back-button never shows a cached auth page after logout.

InjectCurrentUserMiddleware
    Reads _auth_user_id from the session and attaches a
    `request.current_user` (SystemUser instance or None).
    This lets views do `request.current_user` instead of a
    DB lookup every time, and lets context_processors.py
    read it without another query.
"""

import logging
from apps.accounts.models import SystemUser

logger = logging.getLogger(__name__)

# Auth-related URL prefixes that must never be cached.
_NO_CACHE_PREFIXES = (
    '/accounts/login/',
    '/accounts/logout/',
    '/accounts/admin/login/',
    '/accounts/admin/logout/',
)


class NoCacheAuthPagesMiddleware:
    """
    Sets Cache-Control: no-store on auth pages so that pressing the
    browser back-button after logout does not re-show the dashboard.
    All other pages get `private, max-age=0` (safe default — not stored
    in shared/proxy caches, but the browser can still use its own cache).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if any(request.path.startswith(p) for p in _NO_CACHE_PREFIXES):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma']        = 'no-cache'
            response['Expires']       = '0'
        else:
            # Safe for all other pages — doesn't break dev tools or browser cache.
            response['Cache-Control'] = 'private, max-age=0'

        return response


class InjectCurrentUserMiddleware:
    """
    Attaches the authenticated SystemUser to `request.current_user`.

    - If the session holds a valid _auth_user_id → loads SystemUser once
      per request and attaches it.
    - If the session is empty or the user no longer exists / is inactive
      → sets request.current_user = None and clears the stale session keys.

    Views and templates can then do:
        request.current_user          (in views)
        {{ current_user.get_display_name }}  (via context_processors.py)

    The DB hit is one SELECT per request on authenticated pages.
    On login/logout pages the session is empty, so there is no query.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.current_user = self._resolve_user(request)
        return self.get_response(request)

    @staticmethod
    def _resolve_user(request):
        user_id = request.session.get('_auth_user_id')
        if not user_id:
            return None

        try:
            user = (
                SystemUser.objects
                .select_related('employee')
                .get(pk=user_id, is_active=True)
            )
            return user
        except SystemUser.DoesNotExist:
            # Stale session — user deleted or deactivated.
            logger.warning(
                "InjectCurrentUserMiddleware: no active user for user_id=%s — "
                "clearing session", user_id
            )
            request.session.flush()
            return None