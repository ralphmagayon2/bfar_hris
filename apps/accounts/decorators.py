# apps/accounts/decorators.py

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

# Paths that indicate the user was on an admin page
_ADMIN_PATH_PREFIXES = (
    '/users/', '/employees/', '/audit/', '/dtr/', '/payroll/',
    '/leaves/', '/holidays/', '/travel-orders/', '/biometrics/',
    '/core/', '/admin/', '/deleted-users/',
)

def _is_admin_path(request):
    return any(request.path.startswith(p) for p in _ADMIN_PATH_PREFIXES)

# ----- DECORATORS -----

def login_required(view_func):
    """Any authenticated SystemUser — redirects to the appropriate login."""
    def wrapper(request, *args, **kwargs):
        if not request.session.get('_auth_user_id'):
            messages.warning(request, 'Please sign in to continue.')
            if _is_admin_path(request):
                return redirect('accounts:admin_login')
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def admin_required(view_func):
    """HR staff, HR Admin, or Superadmin — always redirects to admin login."""
    def wrapper(request, *args, **kwargs):
        if not request.session.get('_auth_is_admin'):
            messages.error(request, 'Admin access required.')
            return redirect('accounts:admin_login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def role_required(*roles):
    """Restrict to one or more specific roles."""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            user_role = request.session.get('_auth_user_role', '')
            if user_role not in roles:
                if not user_role:
                    # Not logged in at all
                    messages.warning(request, 'Please sign in to continue.')
                    return redirect('accounts:admin_login')
                # Logged in but wrong role
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        return wrapper
    return decorator