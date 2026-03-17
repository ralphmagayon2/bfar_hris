# apps/accounts/decorators.py

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render


# ----- DECORATORS -----

def login_required(view_func):
    """Any authenticated SystemUser."""
    def wrapper(request, *args, **kwargs):
        if not request.session.get('_auth_user_id'):
            messages.warning(request, 'Please sign in to continue.')
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper

def admin_required(view_func):
    """HR staff, HR Admin, or Superadmin."""
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
            if request.session.get('_auth_user_role') not in roles:
                messages.error(request, 'You do not have permissions to access this page.')
                return redirect('accounts:admin_login')
            return view_func(request, *args, **kwargs)
        wrapper.__name__ = view_func.__name__
        return wrapper
    return decorator