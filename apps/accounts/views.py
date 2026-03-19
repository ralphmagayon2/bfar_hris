# apps/accounts/views.py
# from django.shortcuts import render, redirect

# def login(request):
#     return render(request, 'accounts/login.html')

# def profile(request):
#     return render(request, 'accounts/profile.html')

# def logout(request):
#     return render(request, 'accounts/logout.html')

# def user_list(request):
#     return render(request, 'accounts/user_list.html')

# def signup_view(request):
#     return render(request, 'accounts/signup.html')

# def forgot_password_view(request):
#     return render(request, 'accounts/forgot_password.html')

# def admin_login_view(request):
#     return render(request, 'accounts/admin/admin_login.html')

# def admin_signup_view(request):
#     return render(request, 'accounts/admin/admin_signup.html')

# def admin_forgot_password_view(request):
#     return render(request, 'accounts/admin/admin_forgot_password.html')

"""
apps/accounts/views.py
 
BFAR Region III — HRIS
All authentication + user-management views.
 
URL map:
    /accounts/login/                     employee_login
    /accounts/admin/login/               admin_login
    /accounts/logout/                    logout
    /accounts/forgot-password/           forgot_password
    /accounts/admin/forgot-password/     admin_forgot_password
    /accounts/reset-password/<token>/    reset_password
    /accounts/employees/create/          create_employee         [superadmin]
    /accounts/users/create/              create_system_user      [superadmin]
    /accounts/users/                     user_list               [superadmin]
    /accounts/users/<id>/toggle/         toggle_user_active      [superadmin, POST]
    /accounts/api/employee-lookup/       employee_lookup         [admin+, GET, AJAX]
 
Decorators exported for other apps:
    login_required      any authenticated user
    admin_required      superadmin / hr_admin / hr_staff
    role_required(*r)   specific roles

NEW: Two new views to add at the bottom of the file (before the private helpers section).
Also add two new URL patterns to apps/accounts/urls.py.
 
────────────────────────────────────────────────────────
VIEW: signup  /accounts/signup/
────────────────────────────────────────────────────────
The employee self-registration wizard (signup.html).
Step 1: Employee verifies their ID number (AJAX lookup via employee_lookup).
Step 2: Employee sets their username and password.
 
The signup.html's AJAX call uses: /api/employees/lookup/?id_number=...
We need to expose that via an unauthenticated route so employees can
verify themselves before they have an account.
 
────────────────────────────────────────────────────────
VIEW: admin_signup  /accounts/admin/signup/
────────────────────────────────────────────────────────
The existing admin_signup.html (extends base_admin_auth.html which we
are replacing with a simpler standalone layout).
 
This is the same logic as create_system_user, but:
  - Accessible at /accounts/admin/signup/ (linked from user_list)
  - Only for superadmin
  - Does NOT use a temp password — HR sets the password directly
 
The existing create_system_user.html is the inline user management page
that lives inside base.html. The admin_signup.html is the standalone
creation form you already built (in the dark admin portal style).
Both submit to the same underlying logic — but we give them separate
URLs so they can have separate templates.
"""

import logging
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_GET

from apps.accounts.models import SystemUser

# UTILITIES from apps/account/utils.py
from apps.accounts.utils import (
    MAX_ATTEMPTS, LOCKOUT_MINUTES,
    get_attempts, increment_attempts, lock_account, is_locked, clear_attempts,
    get_client_ip, generate_temp_password, validate_password_strength,
    generate_reset_token, hash_token, generate_username, mask_email,
    clean_input, is_valid_email
)

# DECORATORS from apps/accounts/decorators.py
from apps.accounts.decorators import (
    login_required, admin_required, role_required
)

logger = logging.getLogger(__name__)

RESET_TOKEN_EXPIRY_HOURS = 1
ADMIN_ROLES = ('superadmin', 'hr_admin', 'hr_staff') # Connected to _start_session function below

# ----- SESSION HELPERS -----

def _start_session(request, user: SystemUser) -> None:
    request.session.cycle_key()          # prevent session fixation
    request.session['_auth_user_id']   = user.user_id
    request.session['_auth_user_role'] = user.role
    request.session['_auth_user_name'] = user.get_display_name()
    request.session['_auth_is_admin']  = user.role in ADMIN_ROLES
    user.record_login()

def _clear_session(request) -> None:
    for key in ('_auth_user_id', '_auth_user_role', '_auth_user_name', 'auth_is_admin'):
        request.session.pop(key, None)

# ----- HELPER FUNCTION -----

def _set_flash(request, message, level='success'):
    """
    Store a message to be shown after the next page reload.
    Works for both AJAX and regular POST responses.
    """
    if level == 'success':
        messages.success(request, message)
    elif level == 'error':
        messages.error(request, message)
    elif level == 'warning':
        messages.warning(request, message)


# ----- EMPLOYEE LOGIN / ----- path: accounts/login/

@require_http_methods(['GET', 'POST'])
def employee_login(request):
    # Only redirect if logged in as a non-admin (viewer role)
    if request.session.get('_auth_user_id') and request.session.get('_auth_user_role') == 'viewer':
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        remember = bool(request.POST.get('remember_me'))

        if is_locked(username):
            messages.error(request, f'Account locked for {LOCKOUT_MINUTES} minutes due to many failed attempts.')
            return render(request, 'accounts/login.html', {'username': username})

        try:
            user = SystemUser.objects.select_related('employee').get(
                username=username, role='viewer',
            )   
        except SystemUser.DoesNotExist:
            _record_failure(username, request)
            messages.error(request, 'Invalid username or password.')
            return render(request, 'accounts/login.html', {'username': username})
        except Exception as exc:
            logger.error('[accounts] employee_login DB error: %s', exc)
            messages.error(request, 'A system error occured. Please try again.')
            return render(request, 'accounts/login.html', {'username': username})
        
        try:
            password_ok = user.check_password(password)
        except Exception as exc:
            logger.error('[accounts] employee_login check_password error: %s', exc)
            messages.error(request, 'A system error occured. Please try again.')
            return render(request, 'accounts/login.html', {'username': username})
        
        if not password_ok:
            _record_failure(username, request)
            attempts_left = MAX_ATTEMPTS - get_attempts(username)
            messages.error(request, f'Invalid username or password. {attempts_left} attempt(s) remaining.')
            return render(request, 'accounts/login.html', {'username': username})
        
        if not user.is_active:
            messages.error(request, 'Your account is inactive. Please contact HR.')
            return render(request, 'accounts/login.html', {'username': username})
        
        try:
            clear_attempts(username)
            _start_session(request, user)
        except Exception as exc:
            logger.error('[accounts] employee_login session error: %s', exc)
            messages.error(request, 'Login failed due to a session error. Please try again.')
            return render(request, 'accounts/login.html', {'username': username})
        
        if remember:
            request.session.set_expiry(30 * 24 * 60 * 60)

        logger.info('[accounts] Employee login: %s from %s', username, get_client_ip(request))
        return redirect('core:dashboard')

    return render(request, 'accounts/login.html')
        

# ----- EMPLOYEE SIGUP / ----- path: accounts/signup/
@require_http_methods(['GET', 'POST'])
def signup(request):
    # Only redirect if logged in as a non-admin (viewer role)
    if request.session.get('_auth_user_id') and request.session.get('_auth_user_role') == 'viewer':
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        id_number    = clean_input(request.POST.get('id_number', ''), 50)
        employee_pk  = request.POST.get('employee_pk', '').strip()
        username     = clean_input(request.POST.get('username', ''), 50)
        password1    = request.POST.get('password1', '')
        password2    = request.POST.get('password2', '')
 
        errors = []
 
        # ── Validate inputs ──────────────────────────────────────────────────
        if not id_number or not employee_pk:
            errors.append('Employee ID verification is required. Please complete Step 1.')
 
        if not username:
            errors.append('Username is required.')
        elif len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        elif SystemUser.objects.filter(username=username).exists():
            errors.append(f'Username "{username}" is already taken.')
 
        pw_errors = validate_password_strength(password1)
        if pw_errors:
            errors.extend(pw_errors)
 
        if password1 and password2 and password1 != password2:
            errors.append('Passwords do not match.')
 
        # ── Validate employee ─────────────────────────────────────────────────
        employee = None
        if employee_pk and not errors:
            try:
                from apps.employees.models import Employee
                employee = Employee.objects.get(employee_id=int(employee_pk), id_number=id_number)
 
                if hasattr(employee, 'system_user'):
                    errors.append('This employee ID already has an HRIS account. Use "Forgot Password" if locked out.')
 
            except Exception:
                errors.append('Employee verification failed. Please go back to Step 1 and re-verify.')
 
        if errors:
            for e in errors:
                messages.error(request, e)
            # Pass form back so the wizard can jump to pane 2
            return render(request, 'accounts/signup.html', {
                'form': {
                    'username': {'value': username, 'errors': []},
                    'password1': {'errors': pw_errors if pw_errors else []},
                    'password2': {'errors': []},
                },
                'has_errors': True,
            })
 
        # ── Create the account ────────────────────────────────────────────────
        try:
            with transaction.atomic():
                user = SystemUser(
                    employee       = employee,
                    username       = username,
                    role           = 'viewer',      # always viewer for self-registered employees
                    is_active      = True,
                )
                user.set_password(password1)
                user.save()
 
        except IntegrityError as exc:
            logger.error('[accounts] signup IntegrityError: %s', exc)
            messages.error(request, 'A conflict occurred. Username may already be taken.')
            return render(request, 'accounts/signup.html', {
                'form': {'username': {'value': username, 'errors': []}},
                'has_errors': True,
            })
 
        logger.info(
            '[accounts] Self-signup: user_id=%s username=%s employee_id=%s',
            user.user_id, username, employee.employee_id if employee else None,
        )
 
        # Return to signup page with success flag — the JS will show pane 3
        return render(request, 'accounts/signup.html', {'signup_success': True})
 
    return render(request, 'accounts/signup.html')


# EMPLOYEE LOOKUP (PUBLIC) — for the signup wizard pane 1
# URL: /accounts/api/employee-lookup-public/
# Access: PUBLIC (unauthenticated — needed during signup)
#
# Different from the authenticated employee_lookup (used in user management):
#   - No login required
#   - Returns 'already_has_account' so the wizard can block double-registration
#   - Checks is_active on the Employee record

@require_GET
def employee_lookup_public(request):
    """
    Public AJAX endpoint for the signup wizard to verify an employee ID.
    Returns enough info to populate the lookup card in pane 1.
 
    Response JSON:
        {found, full_name, initials, position, division, employment_type,
         already_has_account, is_inactive}
    """
    id_number = request.GET.get('id_number', '').strip()
 
    if not id_number:
        return JsonResponse({'found': False, 'message': 'Employee ID is required.'})
 
    try:
        from apps.employees.models import Employee
        emp = Employee.objects.select_related(
            'position', 'division'
        ).get(id_number=id_number)
 
        already_has_account = hasattr(emp, 'system_user')
 
        return JsonResponse({
            'found':               True,
            'employee_pk':         emp.employee_id,
            'full_name':           emp.get_full_name(),
            'initials':            emp.get_initials(),
            'position':            emp.position.position_title if emp.position else '—',
            'division':            emp.division.division_name  if emp.division else '—',
            'employment_type':     emp.employment_type,
            'already_has_account': already_has_account,
            'is_inactive':         not emp.is_active,
        })
 
    except Exception:
        return JsonResponse({'found': False, 'message': 'Employee ID not found in the system.'})


# ------ ADMIN LOGIN -----
@require_http_methods(['GET', 'POST'])
def admin_login(request):
    if request.session.get('_auth_is_admin'):
        return redirect('core:dashboard')
 
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember = bool(request.POST.get('remember_me'))
 
        if is_locked(username):
            messages.error(request, f'Account locked for {LOCKOUT_MINUTES} minutes due to too many failed attempts.')
            return render(request, 'accounts/admin/admin_login.html', {'username': username})
 
        try:
            user = SystemUser.objects.select_related('employee').get(username=username)
        except SystemUser.DoesNotExist:
            _record_failure(username, request)
            messages.error(request, 'Invalid username or password.')
            return render(request, 'accounts/admin/admin_login.html', {'username': username})
        except Exception as exc:
            logger.error('[accounts] admin_login DB error: %s', exc)
            messages.error(request, 'A system error occurred. Please try again.')
            return render(request, 'accounts/admin/admin_login.html', {'username': username})
        
        try:
            password_ok = user.check_password(password)
        except Exception as exc:
            logger.error('[accounts] admin_login check_password error: %s', exc)
            messages.error(request, 'A system error occured. Please try again.')
            return render(request, 'accounts/admin/admin_login.html', {'username': username})
        
        if not password_ok:
            _record_failure(username, request)
            attempts_left = MAX_ATTEMPTS - get_attempts(username)
            messages.error(request, f'Invalid username or password. {attempts_left} attempt(s) remaining.')
            return render(request, 'accounts/admin/admin_login.html', {'username': username})

        if not user.is_active:
            messages.error(request, 'Account is deactivated. Contact IT')
            return render(request, 'accounts/admin/admin_login.html', {'username': username})
        
        if user.role == 'viewer':
            messages.error(request, 'Employee accounts must user the employee portal.')
            return render(request, 'accounts/login.html', {'username': username})

        try:
            clear_attempts(username)
            _start_session(request, user)
        except Exception as exc:
            logger.error('[accounts] admin_login session error: %s', exc)
            messages.error(request, 'Login failed due to a session error. Please try again.')
            return render(request, 'accounts/admin/admin_login.html', {'username': username})

        if remember:
            request.session.set_expiry(8 * 60 * 60)
 
        logger.info('[accounts] Admin login: %s (%s) from %s', username, user.role, get_client_ip(request))
        return redirect('core:dashboard')
 
    return render(request, 'accounts/admin/admin_login.html')


# ADMIN SIGNUP — Superadmin creates a new HR admin/staff account
# URL: /accounts/admin/signup/
# Template: accounts/admin/admin_signup.html
# Access: superadmin only
#
# Uses the admin_signup.html wizard (dark portal style) you already have.
# Difference from create_system_user:
#   - Admin sets the password directly (not a temp password)
#   - Linked employee is chosen from a dropdown
#   - Template is the full-page dark admin form, not the sidebar base.html page

@role_required('superadmin', 'hr_admin')
@require_http_methods(['GET', 'POST'])
def admin_signup(request):
    """
    Standalone admin account creation wizard.
    Uses the full-page dark admin_signup.html template.
 
    For the simpler inline creation form inside base.html, use create_system_user.
    """
    from apps.employees.models import Employee
 
    # All active employees for the "link to employee" dropdown
    employees = (
        Employee.objects
        .filter(is_active=True)
        .select_related('position')
        .order_by('last_name', 'first_name')
    )
 
    ctx = {
        'employees': employees,
        'form': {},     # will be repopulated on validation error
    }
 
    if request.method == 'POST':
        p = request.POST
 
        role            = p.get('role', '').strip()
        username        = clean_input(p.get('username', ''), 50)
        password1       = p.get('password1', '')
        password2       = p.get('password2', '')
        is_active       = p.get('is_active', '1') == '1'
        linked_emp_id   = p.get('linked_employee', '').strip()
        personal_email  = p.get('personal_email', '').strip().lower()
 
        errors = []
 
        # ── Role 
        if not role or role not in dict(SystemUser.ROLE_CHOICES):
            errors.append('Please select a valid role.')
 
        # ── Username 
        if not username:
            errors.append('Username is required.')
        elif SystemUser.objects.filter(username=username).exists():
            errors.append(f'Username "{username}" is already taken.')
 
        # ── Password
        pw_errors = validate_password_strength(password1)
        if pw_errors:
            errors.extend(pw_errors)
        if password1 and password2 and password1 != password2:
            errors.append('Passwords do not match.')
 
        # ── Personal email 
        if personal_email and not is_valid_email(personal_email):
            errors.append('Please enter a valid personal email address.')
        elif personal_email and SystemUser.objects.filter(personal_email__iexact=personal_email).exists():
            errors.append('That personal email is already registered to another account.')
 
        # ── Optional employee link 
        linked_employee = None
        if linked_emp_id:
            try:
                linked_employee = Employee.objects.get(employee_id=int(linked_emp_id))
                if hasattr(linked_employee, 'system_user'):
                    errors.append(f'{linked_employee.get_full_name()} already has a system account.')
            except Exception:
                errors.append('Selected employee record not found.')
 
        if errors:
            for e in errors:
                messages.error(request, e)
            ctx['form'] = {
                'role':             {'value': role,           'errors': []},
                'username':         {'value': username,       'errors': []},
                'password1':        {'errors': pw_errors},
                'password2':        {'errors': []},
                'is_active':        {'value': is_active},
                'linked_employee':  {'value': linked_emp_id,  'errors': []},
                'non_field_errors': errors,
            }
            return render(request, 'accounts/admin/admin_signup.html', ctx)
 
        # ── Create ────────────────────────────────────────────────────────────
        try:
            with transaction.atomic():
                user = SystemUser(
                    username       = username,
                    role           = role,
                    personal_email = personal_email,
                    employee       = linked_employee,
                    is_active      = is_active,
                )
                user.set_password(password1)
                user.save()
 
        except IntegrityError as exc:
            logger.error('[accounts] admin_signup IntegrityError: %s', exc)
            messages.error(request, 'A database conflict occurred. Please try again.')
            ctx['form'] = p
            return render(request, 'accounts/admin/admin_signup.html', ctx)
 
        # ── Audit log ─────────────────────────────────────────────────────────
        try:
            from apps.audit.models import create_audit_log
            create_audit_log(
                table_affected='system_users',
                record_id=user.user_id,
                action='create',
                performed_by=request.current_user,
                new_value={
                    'username':    username,
                    'role':        role,
                    'employee_id': linked_employee.id_number if linked_employee else None,
                    'is_active':   is_active,
                },
                ip_address=get_client_ip(request),
            )
        except Exception as exc:
            logger.error('[accounts] admin_signup audit log failed: %s', exc)
 
        logger.info(
            '[accounts] admin_signup: user_id=%s role=%s created by user_id=%s',
            user.user_id, role, request.current_user.user_id,
        )
 
        messages.success(request, f'Admin account "{username}" ({user.get_role_display()}) created successfully.')
        return redirect('accounts:user_list')
 
    return render(request, 'accounts/admin/admin_signup.html', ctx)


# ------ LOGOUT /accounts/logout/ ------

@require_POST
def logout(request):
    user_id = request.session.get('_auth_user_id')
    role = request.session.get('_auth_user_role', 'viewer')
    
    if user_id:
        logger.info('[accounts] Logout: user_id=%s', user_id)
    _clear_session(request)
    request.session.flush()
    messages.success(request, 'You have signed out.')
    
    if role in ADMIN_ROLES:
        return redirect('accounts:admin_login')
    return redirect('accounts:login')


# ----- FORGOT PASSWORD ------

@require_http_methods(['GET', 'POST'])
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
 
        if not email:
            messages.error(request, 'Please enter your personal email address.')
            return render(request, 'accounts/forgot_password.html')
        
        if not is_valid_email(email):
            # Show same screen as "email not found" — don't confirm email format is wrong
            ctx = {'success_email': mask_email(email)}
            return render(request, 'accounts/forgot_password.html', ctx)
 
        # Always show the same success screen whether email exists or not
        ctx = {'success_email': mask_email(email)}
 
        try:
            user = SystemUser.objects.get(personal_email__iexact=email, role='viewer')
        except SystemUser.DoesNotExist:
            return render(request, 'accounts/forgot_password.html', ctx)
 
        if not user.is_active:
            return render(request, 'accounts/forgot_password.html', ctx)
 
        # Throttle: don't issue a new token if one is still valid
        if user.has_valid_reset_token():
            return render(request, 'accounts/forgot_password.html', ctx)
 
        try:
            token = generate_reset_token()
            user.reset_token_hash       = hash_token(token)
            user.reset_token_expires_at = timezone.now() + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)
            user.save(update_fields=['reset_token_hash', 'reset_token_expires_at'])
        except Exception as exc:
            logger.error('[accounts] forgot_password token save error: %s', exc)
            # Still show the sucess screen — don't leak whether the email exists
            return render(request, 'accounts/forgot_password.html', ctx)
    
        try:
            from apps.accounts.tasks import send_password_reset_email
            reset_url = request.build_absolute_uri(f'/accounts/reset-password/{token}/')
            send_password_reset_email.delay(user_id=user.user_id, reset_url=reset_url, is_admin=False)
        except Exception as exc:
            logger.error('[accounts] Failed to queue reset email: %s', exc)
 
        logger.info('[accounts] Password reset token issued: user_id=%s', user.user_id)
        return render(request, 'accounts/forgot_password.html', ctx)
 
    return render(request, 'accounts/forgot_password.html')


# FORGOT PASSWORD — ADMIN  /accounts/admin/forgot-password/
# Requires BOTH username AND personal_email (extra verification for admin)

@require_http_methods(['GET', 'POST'])
def admin_forgot_password(request):
    if request.method == 'POST':
        username       = request.POST.get('username', '').strip()
        personal_email = request.POST.get('personal_email', '').strip().lower()
 
        ctx = {
            'form_username': username,
            'form_email':    personal_email,
        }
 
        if not username or not personal_email:
            messages.error(request, 'Both username and personal email are required.')
            return render(request, 'accounts/admin/admin_forgot_password.html', ctx)
        
        if not is_valid_email(personal_email):
            # Show success screen — don't reveal format mismatch
            return render(request, 'accounts/admin/admin_forgot_password.html', {
            **ctx, 'success_email': mask_email(personal_email),
        })
 
        # Same response whether match found or not (security)
        success_ctx = {**ctx, 'success_email': mask_email(personal_email)}
 
        try:
            user = SystemUser.objects.get(
                username=username,
                personal_email__iexact=personal_email,
            )
            if user.role == 'viewer':
                raise SystemUser.DoesNotExist
        except SystemUser.DoesNotExist:
            return render(request, 'accounts/admin/admin_forgot_password.html', success_ctx)
 
        if not user.is_active:
            return render(request, 'accounts/admin/admin_forgot_password.html', success_ctx)
 
        if user.has_valid_reset_token():
            return render(request, 'accounts/admin/admin_forgot_password.html', success_ctx)
 
        try:
            token = generate_reset_token()
            user.reset_token_hash       = hash_token(token)
            user.reset_token_expires_at = timezone.now() + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)
            user.save(update_fields=['reset_token_hash', 'reset_token_expires_at'])
        except Exception as exc:
            logger.error('[accounts] admin_fogot_password token save error: %s', exc)
            return render(request, 'accounts/admin/admin_forgot_password.html', success_ctx)
 
        try:
            from apps.accounts.tasks import send_password_reset_email
            reset_url = request.build_absolute_uri(f'/accounts/reset-password/{token}/')
            send_password_reset_email.delay(user_id=user.user_id, reset_url=reset_url, is_admin=True)
        except Exception as exc:
            logger.error('[accounts] Failed to queue admin reset email: %s', exc)
 
        logger.warning('[accounts] Admin reset requested: %s from %s', username, get_client_ip(request))
        return render(request, 'accounts/admin/admin_forgot_password.html', success_ctx)
 
    return render(request, 'accounts/admin/admin_forgot_password.html')


# RESET PASSWORD  /accounts/reset-password/<token>/
# Shared by both employee and admin reset flows

@require_http_methods(['GET', 'POST'])
def reset_password(request, token: str):
    token_hash = hash_token(token)
 
    try:
        user = SystemUser.objects.get(reset_token_hash=token_hash)
    except SystemUser.DoesNotExist:
        messages.error(request, 'Invalid or expired reset link.')
        return redirect('accounts:login')
 
    if not user.has_valid_reset_token():
        messages.error(request, 'This reset link has expired. Please request a new one.')
        target = 'accounts:admin_forgot_password' if user.role != 'viewer' else 'accounts:forgot_password'
        return redirect(target)
 
    if request.method == 'POST':
        new_password     = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
 
        errors = validate_password_strength(new_password)
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'accounts/reset_password.html', {'token': token})
 
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'accounts/reset_password.html', {'token': token})

        try:
            with transaction.atomic():
                user.set_password(new_password)
                user.clear_reset_token()
                clear_attempts(user.username)
                user.save(update_fields=['password_hash'])
        except Exception as exc:
            logger.error('[accounts] reset_password save error: %s', exc)
            messages.error(request, 'A system error occured while saving your password. Please try again.')
            return render(request, 'accounts/reset_password.html', {'token': token})
 
        messages.success(request, 'Password updated successfully. Please sign in.')
        logger.info('[accounts] Password reset completed: user_id=%s', user.user_id)
        return redirect('accounts:admin_login' if user.role != 'viewer' else 'accounts:login')
 
    return render(request, 'accounts/reset_password.html', {'token': token, 'username': user.username})


# CREATE EMPLOYEE  /accounts/employees/create/   [superadmin only]
# Creates an Employee record + linked viewer SystemUser in one transaction.

@login_required
@role_required('superadmin')
@require_http_methods(['GET', 'POST'])
def create_employee(request):
    from apps.employees.models import Division, Unit, PayrollGroup, Position
 
    ctx = {
        'divisions':      Division.objects.order_by('division_code'),
        'units':          Unit.objects.select_related('division').order_by('division__division_code', 'unit_name'),
        'payroll_groups': PayrollGroup.objects.order_by('group_name'),
        'positions':      Position.objects.order_by('employment_type', 'position_title'),
        'employment_types': [
            ('Permanent', 'Permanent'),
            ('COS',       'Contract of Service'),
            ('JO',        'Job Order'),
        ],
        'suffix_choices': ['', 'Jr.', 'Sr.', 'II', 'III', 'IV'],
    }
 
    if request.method == 'POST':
        p = request.POST
        errors = []
 
        # ── Validation ────────────────────────────────────────────────────────
        for field, label in [
            ('id_number',   'Employee ID number'),
            ('last_name',   'Last name'),
            ('first_name',  'First name'),
            ('employment_type', 'Employment type'),
            ('date_hired',  'Date hired'),
            ('monthly_salary', 'Monthly salary'),
            ('personal_email', 'Personal email'),
        ]:
            if not p.get(field, '').strip():
                errors.append(f'{label} is required.')
 
        from apps.employees.models import Employee
        id_number = clean_input(p.get('id_number', ''), 50)
        if id_number and Employee.objects.filter(id_number=id_number).exists():
            errors.append(f'Employee ID "{id_number}" is already registered.')
 
        personal_email = p.get('personal_email', '').strip().lower()
        if personal_email and not is_valid_email(personal_email):
            errors.append('Please enter a valid email address.')
        elif personal_email and SystemUser.objects.filter(personal_email__iexact=personal_email).exists():
            errors.append('That personal email is already been used.')
 
        if errors:
            for e in errors:
                messages.error(request, e)
            ctx['form'] = p
            return render(request, 'accounts/create_employee.html', ctx)
 
        # ── Create ────────────────────────────────────────────────────────────
        try:
            with transaction.atomic():
                from apps.employees.models import Division, Unit, PayrollGroup, Position
 
                def _fk(model, pk_name):
                    pk = p.get(pk_name, '').strip()
                    if pk:
                        try:
                            return model.objects.get(pk=int(pk))
                        except (model.DoesNotExist, ValueError):
                            pass
                    return None
 
                employee = Employee.objects.create(
                    id_number       = id_number,
                    last_name       = clean_input(p.get('last_name',''), 100).upper(),
                    first_name      = clean_input(p.get('first_name', ''), 100),
                    middle_name     = clean_input(p.get('middle_name', ''), 100) or None,
                    suffix = p.get('suffix', '').strip() or None,
                    employment_type = p.get('employment_type', 'COS'),
                    division        = _fk(Division,     'division_id'),
                    unit            = _fk(Unit,         'unit_id'),
                    payroll_group   = _fk(PayrollGroup, 'payroll_group_id'),
                    position        = _fk(Position,     'position_id'),
                    monthly_salary  = p.get('monthly_salary', '0').replace(',', '') or '0',
                    pera            = p.get('pera', '2000').replace(',', '') or '2000',
                    date_hired      = p.get('date_hired'),
                    is_active       = True,
                )
 
                temp_password = generate_temp_password()
                username      = generate_username(employee.first_name, employee.last_name)
 
                sys_user = SystemUser(
                    employee       = employee,
                    username       = username,
                    role           = 'viewer',
                    personal_email = personal_email,
                    is_active      = True,
                )
                sys_user.set_password(temp_password)
                sys_user.save()
 
        except IntegrityError as exc:
            logger.error('[accounts] create_employee IntegrityError: %s', exc)
            messages.error(request, 'A database conflict occurred. Check for duplicate ID or username.')
            ctx['form'] = p
            return render(request, 'accounts/create_employee.html', ctx)
 
        # ── Queue email ───────────────────────────────────────────────────────
        try:
            from apps.accounts.tasks import send_account_created_email
            send_account_created_email.delay(
                user_id=sys_user.user_id,
                temp_password=temp_password,
                login_url=request.build_absolute_uri('/accounts/login/'),
            )
        except Exception as exc:
            logger.error('[accounts] Failed to queue account-created email: %s', exc)
            messages.warning(request, 'Account created but notification email failed to queue.')
 
        # ── Audit log ─────────────────────────────────────────────────────────
        try:
            from apps.audit.models import create_audit_log
            create_audit_log(
                table_affected='employees',
                record_id=employee.employee_id,
                action='create',
                performed_by=request.current_user,
                new_value={
                    'id_number':       employee.id_number,
                    'full_name':       employee.get_full_name(),
                    'employment_type': employee.employment_type,
                    'system_username': username,
                },
                ip_address=get_client_ip(request),
            )
        except Exception as exc:
            logger.error('[accounts] Audit log failed for create_employee: %s', exc)
 
        messages.success(
            request,
            f'Employee account created for {employee.get_full_name()}. '
            f'Username: {username}  |  Temp password: {temp_password}',
        )
        return redirect('accounts:user_list')
 
    return render(request, 'accounts/create_employee.html', ctx)

# CREATE SYSTEM USER  /accounts/users/create/   [superadmin only]
# Creates a standalone admin/staff SystemUser, optionally linked to an Employee.

@login_required
@role_required('superadmin')
@require_http_methods(['GET', 'POST'])
def create_system_user(request):
    ctx = {
        'role_choices': [
            ('hr_admin',   'HR Admin — full HR access, can approve records'),
            ('hr_staff',   'HR Staff — can view and encode, cannot approve'),
            ('superadmin', 'Super Admin — full system access (IT only)'),
        ],
    }
 
    if request.method == 'POST':
        p = request.POST
        errors = []
 
        username       = clean_input(p.get('username', ''), 50)
        role           = p.get('role', '').strip()
        personal_email = p.get('personal_email', '').strip().lower()
        employee_id_input = clean_input(p.get('employee_id_number', ''), 50)
 
        if not username:
            errors.append('Username is required.')
        elif SystemUser.objects.filter(username=username).exists():
            errors.append(f'Username "{username}" is already taken.')
 
        if not role or role not in dict(SystemUser.ROLE_CHOICES):
            errors.append('Please select a valid role.')
 
        if not personal_email:
            errors.append('Personal email is required for password recovery.')
        elif not is_valid_email(personal_email):
            errors.append('Please enter a valid email address')
        elif SystemUser.objects.filter(personal_email__iexact=personal_email).exists():
            errors.append('That personal email is already been used.')
 
        # Optional employee link
        linked_employee = None
        if employee_id_input:
            try:
                from apps.employees.models import Employee
                linked_employee = Employee.objects.get(id_number=employee_id_input)
                if hasattr(linked_employee, 'system_user'):
                    errors.append(f'Employee {employee_id_input} already has a system account.')
            except Exception:
                errors.append(f'Employee ID "{employee_id_input}" not found.')
 
        if errors:
            for e in errors:
                messages.error(request, e)
            ctx['form'] = p
            return render(request, 'accounts/create_system_user.html', ctx)
 
        temp_password = generate_temp_password()
 
        try:
            with transaction.atomic():
                user = SystemUser(
                    username       = username,
                    role           = role,
                    personal_email = personal_email,
                    employee       = linked_employee,
                    is_active      = True,
                )
                user.set_password(temp_password)
                user.save()
        except IntegrityError as exc:
            logger.error('[accounts] create_system_user IntegrityError: %s', exc)
            messages.error(request, 'A database conflict occurred. Please try again.')
            ctx['form'] = p
            return render(request, 'accounts/create_system_user.html', ctx)
 
        try:
            from apps.accounts.tasks import send_account_created_email
            login_url = request.build_absolute_uri('/accounts/admin/login/')
            send_account_created_email.delay(
                user_id=user.user_id,
                temp_password=temp_password,
                login_url=login_url,
            )
        except Exception as exc:
            logger.error('[accounts] Failed to queue system user email: %s', exc)
            messages.warning(request, 'User created but notification email failed to queue.')
 
        # ── Audit log ─────────────────────────────────────────────────────────
        try:
            from apps.audit.models import create_audit_log
            create_audit_log(
                table_affected='system_users',
                record_id=user.user_id,
                action='create',
                performed_by=request.current_user,
                new_value={
                    'username':    username,
                    'role':        role,
                    'employee_id': linked_employee.id_number if linked_employee else None,
                },
                ip_address=get_client_ip(request),
            )
        except Exception as exc:
            logger.error('[accounts] Audit log failed for create_system_user: %s', exc)
 
        messages.success(
            request,
            f'System user "{username}" ({user.get_role_display()}) created. '
            f'Temp password: {temp_password}',
        )
        logger.info('[accounts] SystemUser created: %s (%s) by user_id=%s',
                    username, role, request.current_user.user_id)
        return redirect('accounts:user_list')
 
    return render(request, 'accounts/create_system_user.html', ctx)

# ------ USER LIST /accounts/users ------
# ─── Roles that can reach the user management page
_PAGE_ROLES = ('superadmin', 'hr_admin', 'hr_staff')
 
# ─── Roles that hr_admin / hr_staff are allowed to manage
_MANAGEABLE_BY_NON_SA = ('hr_admin', 'hr_staff', 'viewer')
 
# ─── Roles that hr_admin can create
_HR_ADMIN_CREATABLE = ('hr_admin', 'hr_staff', 'viewer')

# ─── Roles that hr_admin can DELETE (stricter than edit)
_DELETABLE_BY_HR_ADMIN = ('hr_staff', 'viewer')

# ─── Roles that hr_staff specifically can manage
_MANAGEABLE_BY_HR_STAFF = ('hr_staff', 'viewer')
 
 
# PRIVATE HELPER — permission guard for a target user
 
def _check_target_permission(actor: SystemUser, target: SystemUser, action='modify') -> tuple[bool, str]:
    """
    Returns (allowed: bool, error_message: str).
 
    Rules:
      - No one can modify themselves (self-protection).
      - Only superadmin can modify another superadmin.
      - hr_admin / hr_staff can modify hr_admin / hr_staff / viewer only.
    """
    if actor.user_id == target.user_id:
        return False, "You cannot modify your own account here."
 
    if target.role == 'superadmin' and actor.role != 'superadmin':
        return False, "You do not have permission to modify a Super Admin account."
 
    if actor.role in ('hr_admin', 'hr_staff') and target.role not in _MANAGEABLE_BY_NON_SA:
        return False, "You do not have permission to modify this account."
    
    # hr_staff cannot modify hr_admin
    if actor.role == 'hr_staff' and target.role == 'hr_admin':
        return False, "HR Staff cannot modify an HR Admin account."

    # Delete-specific rules
    if action == 'delete':
        if actor.role == 'hr_staff':
            return False, "HR Staff cannot delete accounts."
        if actor.role == 'hr_admin' and target.role not in _DELETABLE_BY_HR_ADMIN:
            return False, f"HR Admin cannot delete a {target.get_role_display()} account."
 
    return True, ""
 
 
# USER LIST  /accounts/users/
#
# GET  → render the list (superadmin + hr_admin + hr_staff)
# POST → handle add_user / edit_user / reset_password / toggle_active
#        (inline form actions — each action re-checks permissions)
 
@login_required
@role_required(*_PAGE_ROLES)
@require_http_methods(['GET', 'POST'])
def user_list(request):
 
    # ── POST dispatcher
    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
 
        if action == 'add_user':
            return _action_add_user(request)
 
        if action == 'edit_user':
            return _action_edit_user(request)
 
        if action == 'reset_password':
            return _action_reset_password(request)
 
        if action == 'toggle_active':
            return _action_toggle_active(request)

        if action == 'delete_user':
            return _action_delete_user(request)
 
        messages.error(request, 'Unknown action.')
        return redirect('accounts:user_list')
 
    # ── GET — build queryset
    actor: SystemUser = request.current_user

    # Pick up any pending bulk message from previous AJAX action
    _bulk_msg   = request.session.pop('_bulk_message', None)
    _bulk_level = request.session.pop('_bulk_level', 'success')
    if _bulk_msg:
        if _bulk_level == 'success':
            messages.success(request, _bulk_msg)
        elif _bulk_level == 'warning':
            messages.warning(request, _bulk_msg)
        elif _bulk_level == 'error':
            messages.error(request, _bulk_msg)

    qs = (
        SystemUser.objects
        .filter(is_deleted=False)
        .select_related('employee__division', 'employee__position')
        .order_by('role', 'username')
    )
 
    # hr_admin and hr_staff can only *see* non-superadmin accounts
    if actor.role == 'hr_admin':
        qs = qs.filter(role__in=_MANAGEABLE_BY_NON_SA)
    elif actor.role == 'hr_staff':
        qs = qs.filter(role__in=_MANAGEABLE_BY_HR_STAFF)
 
    role_filter   = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()
    search_q      = request.GET.get('q', '').strip()
 
    if role_filter:
        qs = qs.filter(role=role_filter)
 
    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)
 
    if search_q:
        from django.db.models import Q
        qs = qs.filter(
            Q(username__icontains=search_q) |
            Q(employee__last_name__icontains=search_q) |
            Q(employee__first_name__icontains=search_q)
        )
 
    # Role statistics — superadmin sees all, others see their subset
    if actor.role == 'superadmin':
        active_qs = SystemUser.objects.filter(is_deleted=False)
        role_stats = {
            'superadmin': active_qs.filter(role='superadmin').count(),
            'hr_admin':   active_qs.filter(role='hr_admin').count(),
            'hr_staff':   active_qs.filter(role='hr_staff').count(),
            'viewer':     active_qs.filter(role='viewer').count(),
        }
        total_users    = active_qs.count()
        active_users   = active_qs.filter(is_active=True).count()
        inactive_users = active_qs.filter(is_active=False).count()
    else:
        manageable = SystemUser.objects.filter(
            role__in=_MANAGEABLE_BY_NON_SA, is_deleted=False
        )
        role_stats = {
            'hr_admin': manageable.filter(role='hr_admin').count(),
            'hr_staff': manageable.filter(role='hr_staff').count(),
            'viewer':   manageable.filter(role='viewer').count(),
        }
        total_users    = manageable.count()
        active_users   = manageable.filter(is_active=True).count()
        inactive_users = manageable.filter(is_active=False).count()
 
    # Pagination — 25 per page
    paginator   = Paginator(qs, 25)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)
 
    # Build role choices available for the "Add User" modal (role-gated)
    if actor.role == 'superadmin':
        add_role_choices = SystemUser.ROLE_CHOICES          # all 4 roles
    elif actor.role == 'hr_admin':
        add_role_choices = [
            r for r in SystemUser.ROLE_CHOICES
            if r[0] in _HR_ADMIN_CREATABLE
        ]
    else:
        add_role_choices = []   # hr_staff cannot add users
 
    context = {
        'users':          page_obj.object_list,   # current page items
        'page_obj':       page_obj,               # paginator object for template
 
        'role_filter':    role_filter,
        'status_filter':  status_filter,
        'search_q':       search_q,
 
        'total_users':    total_users,
        'active_users':   active_users,
        'inactive_users': inactive_users,
 
        'role_stats':     role_stats,
        'role_choices':   SystemUser.ROLE_CHOICES,
 
        # Permission flags used by the template to show/hide UI elements
        'can_add_user':         actor.role in ('superadmin', 'hr_admin'),
        'can_reset_password':   actor.role in ('superadmin', 'hr_admin'),
        'can_bulk_action':     actor.role in ('superadmin', 'hr_admin'),
        'is_superadmin_actor':  actor.role == 'superadmin',
        'actor_role':           actor.role,

        'current_user_id':  actor.user_id,
 
        # Role choices for the Add User modal (filtered by actor role)
        'add_role_choices': add_role_choices,
    }
 
    return render(request, 'accounts/user_list.html', context)
 
# AJAX TOGGLE  /accounts/users/<id>/toggle/   POST → JSON
#
# Called by the JS toast-confirm widget (not a page reload).
# Returns JSON so the JS can update the row in-place.
 
@login_required
@role_required(*_PAGE_ROLES)
@require_POST
def toggle_user_active(request, user_id: int):
    actor: SystemUser = request.current_user
 
    # hr_staff can deactivate; superadmin and hr_admin also can
    # (all three roles are in _PAGE_ROLES, so they reach here)
 
    target = get_object_or_404(SystemUser, user_id=user_id)
 
    allowed, err = _check_target_permission(actor, target)
    if not allowed:
        return JsonResponse({'ok': False, 'error': err}, status=403)
 
    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
 
    action_word = 'activated' if target.is_active else 'deactivated'
 
    # Audit log (non-fatal)
    try:
        from apps.audit.models import create_audit_log
        create_audit_log(
            table_affected='system_users',
            record_id=target.user_id,
            action='update',
            performed_by=actor,
            new_value={'is_active': target.is_active},
            ip_address=get_client_ip(request),
        )
    except Exception as exc:
        logger.error('[accounts] toggle audit log failed: %s', exc)
 
    logger.info(
        '[accounts] User %s %s by %s (user_id=%s)',
        target.username, action_word, actor.username, actor.user_id,
    )
 
    msg = f'✓ User "{target.username}" has been {action_word}.'
    request.session['_bulk_message'] = msg
    request.session['_bulk_level']   = 'success'

    return JsonResponse({
        'ok':        True,
        'is_active': target.is_active,
        'message':   f'User "{target.username}" has been {action_word}.',
    })
 
# PRIVATE ACTION HANDLERS  (called from user_list POST dispatcher)
 
def _action_add_user(request):
    """
    Only superadmin and hr_admin can add users.
    hr_admin cannot create superadmin accounts.
    """
    actor: SystemUser = request.current_user
 
    if actor.role not in ('superadmin', 'hr_admin'):
        messages.error(request, 'You do not have permission to add users.')
        return redirect('accounts:user_list')
 
    p = request.POST
    # first_name = clean_input(p.get('first_name', ''), 100)
    # last_name  = clean_input(p.get('last_name', ''),  100)
    email      = p.get('email', '').strip().lower()
    username   = clean_input(p.get('username', ''), 50)
    role       = p.get('admin_role', '').strip()
    password1  = p.get('password1', '')
    password2  = p.get('password2', '')
 
    errors = []
 
    if not email or not is_valid_email(email):
        errors.append('A valid email address is required.')
    elif SystemUser.objects.filter(personal_email__iexact=email).exists():
        errors.append('That email is already registered.')
 
    if not username:
        errors.append('Username is required.')
    elif len(username) < 3:
        errors.append('Username must be at least 3 characters.')
    elif SystemUser.objects.filter(username=username).exists():
        errors.append(f'Username "{username}" is already taken.')
 
    # Role gate — hr_admin cannot create superadmin
    valid_roles = dict(SystemUser.ROLE_CHOICES)
    if not role or role not in valid_roles:
        errors.append('Please select a valid role.')
    elif actor.role == 'hr_admin' and role not in _HR_ADMIN_CREATABLE:
        errors.append('You do not have permission to create an account with that role.')
 
    pw_errors = validate_password_strength(password1)
    errors.extend(pw_errors)
    if password1 and password2 and password1 != password2:
        errors.append('Passwords do not match.')
 
    if errors:
        for e in errors:
            messages.error(request, e)
        return redirect('accounts:user_list')
 
    try:
        with transaction.atomic():
            linked_employee = None
            emp_id_input = p.get('employee_id', '').strip()

            if emp_id_input:
                try:
                    from apps.employees.models import Employee
                    linked_employee = Employee.objects.get(employee_id=int(emp_id_input))
                    if hasattr(linked_employee, 'system_user'):
                        errors.append(f'{linked_employee.get_full_name()} is already linked to another account.')
                except Exception:
                    errors.append('Select employee record not found.')

            if errors:
                for e in errors:
                    messages.error(request, e)
                return redirect('accounts:user_list')
            
            user = SystemUser(
                username = username,
                role = role,
                personal_email = email,
                employee = linked_employee,
                is_active = True,
            )
            user.set_password(password1)
            user.save()
    except IntegrityError as exc:
        logger.error('[accounts] _action_add_user IntegrityError: %s', exc)
        messages.error(request, 'A database conflict occurred. Username or email may already be taken.')
        return redirect('accounts:user_list')
 
    # Audit log (non-fatal)
    try:
        from apps.audit.models import create_audit_log
        create_audit_log(
            table_affected='system_users',
            record_id=user.user_id,
            action='create',
            performed_by=actor,
            new_value={
                'username':  username,
                'role':      role,
                'email':     email,
            },
            ip_address=get_client_ip(request),
        )
    except Exception as exc:
        logger.error('[accounts] _action_add_user audit log failed: %s', exc)
 
    logger.info(
        '[accounts] User created: %s (%s) by %s (user_id=%s)',
        username, role, actor.username, actor.user_id,
    )
    messages.success(request, f'User "{username}" ({valid_roles[role]}) created successfully.')
    return redirect('accounts:user_list')
 
 
def _action_edit_user(request):
    """
    Edit a system user's email, role, active status, and optionally
    link/unlink to an employee record.
 
    superadmin  → can edit anyone
    hr_admin    → can edit hr_admin / hr_staff / viewer only
    hr_staff    → can edit hr_staff / viewer only
    """
    actor = request.current_user
 
    if actor.role not in ('superadmin', 'hr_admin', 'hr_staff'):
        messages.error(request, 'You do not have permission to edit users.')
        return redirect('accounts:user_list')
 
    p         = request.POST
    target_id = p.get('user_id', '').strip()
    email     = p.get('email', '').strip().lower()
    role      = p.get('admin_role', '').strip()
    is_active = p.get('is_active', '1') == '1'
    link_emp  = p.get('employee_id', '').strip()   # employee_id or '' to unlink
 
    if not target_id:
        messages.error(request, 'Invalid request.')
        return redirect('accounts:user_list')
 
    target = get_object_or_404(SystemUser, user_id=target_id, is_deleted=False)
 
    allowed, err = _check_target_permission(actor, target)
    if not allowed:
        messages.error(request, err)
        return redirect('accounts:user_list')
 
    errors = []
 
    # Email validation
    if not email or not is_valid_email(email):
        errors.append('A valid email address is required.')
    elif (
        SystemUser.objects
        .filter(personal_email__iexact=email)
        .exclude(user_id=target.user_id)
        .exists()
    ):
        errors.append('That email is already registered to another account.')
 
    # Role gate
    valid_roles = dict(SystemUser.ROLE_CHOICES)
    if not role or role not in valid_roles:
        errors.append('Please select a valid role.')
    elif actor.role in ('hr_admin', 'hr_staff') and role not in _MANAGEABLE_BY_NON_SA:
        errors.append('You cannot assign that role.')
    elif actor.role in ('hr_admin', 'hr_staff') and target.role == 'superadmin':
        errors.append('You cannot change a Super Admin account.')
 
    # Employee link resolution
    linked_employee = None
    unlink = p.get('unlink_employee', '') == '1'
 
    if not unlink and link_emp:
        try:
            from apps.employees.models import Employee
            linked_employee = Employee.objects.get(employee_id=int(link_emp))
            # Allow re-linking to the same employee; block linking to someone else's account
            existing = SystemUser.objects.filter(
                employee=linked_employee
            ).exclude(user_id=target.user_id).first()
            if existing:
                errors.append(
                    f'{linked_employee.get_full_name()} is already linked to another account ({existing.username}).'
                )
        except Exception:
            errors.append('Selected employee record not found.')
 
    if errors:
        for e in errors:
            messages.error(request, e)
        return redirect('accounts:user_list')
 
    new_username = clean_input(p.get('username', ''), 50)
    if new_username and new_username != target.username:
        if SystemUser.objects.filter(username=new_username).exclude(user_id=target.user_id).exists():
            messages.error(request, f'Username "{new_username}" is already taken.')
            return redirect('accounts:user_list')
        target.username = new_username
        
    # Apply changes
    target.personal_email = email
    target.role           = role
    target.is_active      = is_active
 
    if unlink:
        target.employee = None
    elif linked_employee:
        target.employee = linked_employee
 
    target.save(update_fields=['username', 'personal_email', 'role', 'is_active', 'employee'])
 
    # Audit log (non-fatal)
    try:
        from apps.audit.models import create_audit_log
        create_audit_log(
            table_affected='system_users',
            record_id=target.user_id,
            action='update',
            performed_by=actor,
            new_value={
                'email':       email,
                'role':        role,
                'is_active':   is_active,
                'employee_id': linked_employee.employee_id if linked_employee else (None if unlink else 'unchanged'),
            },
            ip_address=get_client_ip(request),
        )
    except Exception as exc:
        logger.error('[accounts] _action_edit_user audit log failed: %s', exc)
 
    logger.info('[accounts] User edited: %s by %s', target.username, actor.username)
    messages.success(request, f'User "{target.username}" updated successfully.')
    return redirect('accounts:user_list')
 
def _action_reset_password(request):
    """
    Only superadmin can reset passwords.
    Cannot reset their own password here (use Change Password instead).
    """
    actor: SystemUser = request.current_user
 
    if actor.role not in ('superadmin', 'hr_admin'):
        messages.error(request, 'Only Super Admins can reset passwords.')
        return redirect('accounts:user_list')
 
    target_id    = request.POST.get('user_id', '').strip()
    new_password = request.POST.get('new_password', '')
 
    if not target_id:
        messages.error(request, 'Invalid request.')
        return redirect('accounts:user_list')
 
    target = get_object_or_404(SystemUser, user_id=target_id)
 
    allowed, err = _check_target_permission(actor, target)
    if not allowed:
        messages.error(request, err)
        return redirect('accounts:user_list')
 
    errors = validate_password_strength(new_password)
    if errors:
        for e in errors:
            messages.error(request, e)
        return redirect('accounts:user_list')
 
    try:
        with transaction.atomic():
            target.set_password(new_password)
            target.save(update_fields=['password_hash'])
    except Exception as exc:
        logger.error('[accounts] _action_reset_password save error: %s', exc)
        messages.error(request, 'A system error occurred while resetting the password.')
        return redirect('accounts:user_list')
 
    # Audit log (non-fatal)
    try:
        from apps.audit.models import create_audit_log
        create_audit_log(
            table_affected='system_users',
            record_id=target.user_id,
            action='update',
            performed_by=actor,
            new_value={'password_reset': True},
            ip_address=get_client_ip(request),
        )
    except Exception as exc:
        logger.error('[accounts] _action_reset_password audit log failed: %s', exc)
 
    logger.info(
        '[accounts] Password reset for %s by superadmin %s (user_id=%s)',
        target.username, actor.username, actor.user_id,
    )
    messages.success(request, f'Password for "{target.username}" has been reset.')
    return redirect('accounts:user_list')
 
 
def _action_toggle_active(request):
    """
    Form-based fallback toggle (non-AJAX).
    The JS toast path uses the AJAX endpoint above; this handles no-JS fallback.
    """
    actor: SystemUser = request.current_user
    target_id = request.POST.get('user_id', '').strip()
 
    if not target_id:
        messages.error(request, 'Invalid request.')
        return redirect('accounts:user_list')
 
    target = get_object_or_404(SystemUser, user_id=target_id)
 
    allowed, err = _check_target_permission(actor, target)
    if not allowed:
        messages.error(request, err)
        return redirect('accounts:user_list')
 
    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
 
    action_word = 'activated' if target.is_active else 'deactivated'
    messages.success(request, f'User "{target.username}" has been {action_word}.')
    return redirect('accounts:user_list')

def _action_delete_user(request):
    """
    Soft-delete a single user.
    superadmin  → can delete any non-self (including other superadmins)
    hr_admin    → can delete hr_staff and viewer only
    hr_staff    → cannot delete
    """
    from apps.accounts.models import SystemUser
    actor = request.current_user

    if actor.role not in ('superadmin', 'hr_admin'):
        messages.error(request, 'You do not have permission to delete users.')
        return redirect('accounts:user_list')
    
    target_id = request.POST.get('user_id', '').strip()
    if not target_id:
        messages.error(request, 'Invalid request.')
        return redirect('accounts:user_list')
    
    target = get_object_or_404(SystemUser, user_id=target_id, is_deleted=False)

    allowed, err = _check_target_permission(actor, target, action='delete')
    if not allowed:
        messages.error(request, err)
        return redirect('accounts:user_list')
    
    try:
        with transaction.atomic():
            target.is_deleted = True
            target.is_active = False
            target.save(update_fields=['is_deleted', 'is_active'])
    except Exception as exc:
        logger.error('[accounts] _action_delete_user save error: %s', exc)
        messages.error(request, 'A system error occured while deleting the user.')
        return redirect('accounts:user_list')

    # Audit log (non-fatal)
    try:
        from apps.audit.models import create_audit_log
        create_audit_log(
            table_affected='system_users',
            record_id=target.user_id,
            action='delete',
            performed_by=actor,
            new_value={'is_deleted': True, 'username': target.username},
            ip_address=get_client_ip(request),
        )
    except Exception as exc:
        logger.error('[accounts] action delete user audit log failed %s', exc)

    logger.info(
        '[accounts] User soft-deleted: %s by %s (user_id=%s)',
        target.user_id, actor.username, actor.user_id,
    )
    messages.success(request, f'User "{target.username}" has been deleted.')
    return redirect('accounts:user_list')
    

from django.views.decorators.http import require_POST as _require_POST

@login_required
@role_required('superadmin', 'hr_admin')   # hr_staff and viewer excluded
@_require_POST
def bulk_action(request):
    """
    AJAX endpoint for bulk deactivate / bulk delete.
 
    POST body (JSON):
        { "action": "deactivate" | "delete", "user_ids": [1, 2, 3] }
 
    Response JSON:
        {
          "ok": true,
          "actioned": 2,       # how many were successfully processed
          "skipped": 1,        # skipped (already inactive, permission denied, etc.)
          "skip_details": ["username1 — already inactive"],
          "message": "2 user(s) deactivated. 1 skipped."
        }
 
    Permission rules (same as single actions):
        superadmin  → bulk deactivate/delete anyone except self
        hr_admin    → bulk deactivate: hr_admin/hr_staff/viewer
                      bulk delete:     hr_staff/viewer only
    """
    import json
    from apps.accounts.models import SystemUser
 
    actor = request.current_user
 
    try:
        body        = json.loads(request.body)
        action      = body.get('action', '').strip()
        user_ids    = body.get('user_ids', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'ok': False, 'error': 'Invalid request body.'}, status=400)
 
    if action not in ('activate', 'deactivate', 'delete'):
        return JsonResponse({'ok': False, 'error': 'Invalid action.'}, status=400)
 
    if not isinstance(user_ids, list) or not user_ids:
        return JsonResponse({'ok': False, 'error': 'No users selected.'}, status=400)
 
    if len(user_ids) > 50:
        return JsonResponse({'ok': False, 'error': 'Maximum 50 users per bulk action.'}, status=400)
 
    # Sanitise IDs — integers only
    try:
        user_ids = [int(uid) for uid in user_ids]
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Invalid user ID format.'}, status=400)
 
    targets = SystemUser.objects.filter(user_id__in=user_ids, is_deleted=False)
 
    actioned      = 0
    skipped       = 0
    skip_details  = []
 
    for target in targets:
        # Permission check
        perm_action = 'delete' if action == 'delete' else 'modify'
        allowed, err = _check_target_permission(actor, target, action=perm_action)
        if not allowed:
            skipped += 1
            skip_details.append(f'{target.username} — {err}')
            continue
        
        if action == 'activate':
            if target.is_active:
                skipped += 1
                skip_details.append(f'{target.username} — already active')
                continue
            target.is_active = True
            target.save(update_fields=['is_active'])
            actioned += 1

            try:
                from apps.audit.models import create_audit_log
                create_audit_log(
                    table_affected='system_users',
                    record_id=target.user_id,
                    action='update',
                    performed_by=actor,
                    new_value={'is_active': True, 'bulk': True},
                    ip_address=get_client_ip(request),
                )
            except Exception as exc:
                logger.error('[accounts] bulk activate audit failed: %s', exc)

        elif action == 'deactivate':
            if not target.is_active:
                skipped += 1
                skip_details.append(f'{target.username} — already inactive')
                continue
            target.is_active = False
            target.save(update_fields=['is_active'])
            actioned += 1
 
            # Audit
            try:
                from apps.audit.models import create_audit_log
                create_audit_log(
                    table_affected='system_users',
                    record_id=target.user_id,
                    action='update',
                    performed_by=actor,
                    new_value={'is_active': False, 'bulk': True},
                    ip_address=get_client_ip(request),
                )
            except Exception as exc:
                logger.error('[accounts] bulk deactivate audit failed: %s', exc)
 
        elif action == 'delete':
            target.is_deleted = True
            target.is_active  = False
            target.save(update_fields=['is_deleted', 'is_active'])
            actioned += 1
 
            # Audit
            try:
                from apps.audit.models import create_audit_log
                create_audit_log(
                    table_affected='system_users',
                    record_id=target.user_id,
                    action='delete',
                    performed_by=actor,
                    new_value={'is_deleted': True, 'bulk': True, 'username': target.username},
                    ip_address=get_client_ip(request),
                )
            except Exception as exc:
                logger.error('[accounts] bulk delete audit failed: %s', exc)
 
    verb_map    = {'activate': 'activated', 'deactivate': 'deactivated', 'delete': 'deleted'}
    verb = verb_map.get(action, action)
    message = f'{actioned} user(s) {verb}.'
    if skipped:
        message += f' {skipped} skipped.'
 
    logger.info(
        '[accounts] Bulk %s: actioned=%s skipped=%s by %s (user_id=%s)',
        action, actioned, skipped, actor.username, actor.user_id,
    )
 
    # Build a richer message
    if action == 'activate':
        success_msg = f'✓ {actioned} user(s) activated successfully.'
        if skipped:
            success_msg += f' {skipped} skipped (already active or no permission).'
    elif action == 'deactivate':
        success_msg = f'✓ {actioned} user(s) deactivated successfully.'
        if skipped:
            success_msg += f' {skipped} skipped (already inactive or no permission).'
    elif action == 'delete':
        success_msg = f'✓ {actioned} user(s) moved to deleted accounts.'
        if skipped:
            success_msg += f' {skipped} skipped (no permission).'

    # Store in session so it appears after page reload
    request.session['_bulk_message'] = success_msg
    request.session['_bulk_level']   = 'success' if actioned > 0 else 'warning'

    return JsonResponse({
        'ok':           True,
        'actioned':     actioned,
        'skipped':      skipped,
        'skip_details': skip_details,
        'message':      message,
        'action':       action,
    })


# Kaka update lang
# Shows soft-deleted accounts. Superadmin only.

@login_required
@role_required('superadmin', 'hr_admin')
@require_http_methods(['GET'])
def deleted_users(request):
    """
    List of soft-deleted system users.
    Superadmin only — allows reviewing and restoring deleted accounts.
    """
    actor = request.current_user

    _bulk_msg   = request.session.pop('_bulk_message', None)
    _bulk_level = request.session.pop('_bulk_level', 'success')
    if _bulk_msg:
        if _bulk_level == 'success':
            messages.success(request, _bulk_msg)
        elif _bulk_level == 'warning':
            messages.warning(request, _bulk_msg)
        elif _bulk_level == 'error':
            messages.error(request, _bulk_msg)
 
    qs = (
        SystemUser.objects
        .filter(is_deleted=True)
        .select_related('employee__division', 'employee__position')
        .order_by('-created_at')
    )
 
    search_q = request.GET.get('q', '').strip()
    if search_q:
        from django.db.models import Q
        qs = qs.filter(
            Q(username__icontains=search_q) |
            Q(employee__last_name__icontains=search_q) |
            Q(employee__first_name__icontains=search_q)
        )
 
    paginator   = Paginator(qs, 25)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)
 
    deleted_qs = SystemUser.objects.filter(is_deleted=True)
    context = {
        'users':          page_obj.object_list,
        'page_obj':       page_obj,
        'search_q':       search_q,
        'total_deleted':  deleted_qs.count(),
        'deleted_by_role': {
            'superadmin': deleted_qs.filter(role='superadmin').count(),
            'hr_admin': deleted_qs.filter(role='hr_admin').count(),
            'hr_staff': deleted_qs.filter(role='hr_staff').count(),
            'viewer': deleted_qs.filter(role='viewer').count(),
        },
        'actor_role':     actor.role,
        'is_superadmin_actor': actor.role == 'superadmin',
    }
 
    return render(request, 'accounts/deleted_users.html', context)

# NEW VIEW: restore_user   /users/<id>/restore/   POST → JSON
# Superadmin and HR Admin only. Restores a soft-deleted user.

@login_required
@role_required('superadmin', 'hr_admin')
@require_POST
def restore_user(request, user_id: int):
    """
    Restore a soft-deleted user. Sets is_deleted=False, is_active=True.
    Returns JSON for AJAX update.
    """
    actor = request.current_user
 
    target = get_object_or_404(SystemUser, user_id=user_id, is_deleted=True)
 
    try:
        with transaction.atomic():
            target.is_deleted = False
            target.is_active  = True
            target.save(update_fields=['is_deleted', 'is_active'])
    except Exception as exc:
        logger.error('[accounts] restore_user save error: %s', exc)
        return JsonResponse({'ok': False, 'error': 'A system error occurred.'}, status=500)
 
    # Audit log (non-fatal)
    try:
        from apps.audit.models import create_audit_log
        create_audit_log(
            table_affected='system_users',
            record_id=target.user_id,
            action='update',
            performed_by=actor,
            new_value={'is_deleted': False, 'is_active': True, 'restored': True},
            ip_address=get_client_ip(request),
        )
    except Exception as exc:
        logger.error('[accounts] restore_user audit log failed: %s', exc)
 
    logger.info(
        '[accounts] User restored: %s by %s (user_id=%s)',
        target.username, actor.username, actor.user_id,
    )
 
    return JsonResponse({
        'ok':      True,
        'message': f'User "{target.username}" has been restored and reactivated.',
    })

# BULK ACTIONS
@login_required
@role_required('superadmin', 'hr_admin')
@require_POST
def bulk_restore(request):
    """Bulk restore soft-deleted users."""
    import json
    actor = request.current_user

    try:
        body     = json.loads(request.body)
        user_ids = [int(uid) for uid in body.get('user_ids', [])]
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid request.'}, status=400)

    if not user_ids or len(user_ids) > 50:
        return JsonResponse({'ok': False, 'error': 'Invalid selection.'}, status=400)

    targets      = SystemUser.objects.filter(user_id__in=user_ids, is_deleted=True)
    actioned_ids = []

    for target in targets:
        target.is_deleted = False
        target.is_active  = True
        target.save(update_fields=['is_deleted', 'is_active'])
        actioned_ids.append(target.user_id)

        try:
            from apps.audit.models import create_audit_log
            create_audit_log(
                table_affected='system_users',
                record_id=target.user_id,
                action='update',
                performed_by=actor,
                new_value={'is_deleted': False, 'restored': True, 'bulk': True},
                ip_address=get_client_ip(request),
            )
        except Exception as exc:
            logger.error('[accounts] bulk_restore audit failed: %s', exc)

    logger.info('[accounts] Bulk restore: %s users by %s', len(actioned_ids), actor.username)

    restore_msg = f'✓ {len(actioned_ids)} user(s) restored and reactivated.'
    request.session['_bulk_message'] = restore_msg
    request.session['_bulk_level']   = 'success'

    return JsonResponse({
        'ok':          True,
        'actioned_ids': actioned_ids,
        'message':     f'{len(actioned_ids)} user(s) restored successfully.',
    })


@login_required
@role_required('superadmin', 'hr_admin')
@require_POST
def bulk_permanent_delete(request):
    """Permanently delete soft-deleted users from the database."""
    import json
    actor = request.current_user

    try:
        body     = json.loads(request.body)
        user_ids = [int(uid) for uid in body.get('user_ids', [])]
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid request.'}, status=400)

    if not user_ids or len(user_ids) > 50:
        return JsonResponse({'ok': False, 'error': 'Invalid selection.'}, status=400)

    targets      = SystemUser.objects.filter(user_id__in=user_ids, is_deleted=True)
    actioned_ids = []

    for target in targets:
        uid      = target.user_id
        username = target.username
        target.delete()
        actioned_ids.append(uid)

        try:
            from apps.audit.models import create_audit_log
            create_audit_log(
                table_affected='system_users',
                record_id=uid,
                action='delete',
                performed_by=actor,
                new_value={'permanent_delete': True, 'username': username, 'bulk': True},
                ip_address=get_client_ip(request),
            )
        except Exception as exc:
            logger.error('[accounts] bulk_permanent_delete audit failed: %s', exc)

    logger.info('[accounts] Bulk permanent delete: %s users by %s', len(actioned_ids), actor.username)

    del_msg = f'✓ {len(actioned_ids)} user(s) permanently deleted from the database.'
    request.session['_bulk_message'] = del_msg
    request.session['_bulk_level']   = 'success'

    return JsonResponse({
        'ok':           True,
        'actioned_ids': actioned_ids,
        'message':      f'{len(actioned_ids)} user(s) permanently deleted.',
    })

# NEW AJAX ENDPOINT: employee_search   /api/employee-search/
# Used by the Edit modal's employee link autocomplete.
# Returns active employees not yet linked to any account.
@login_required
@role_required('superadmin', 'hr_admin', 'hr_staff')
@require_GET
def employee_search(request):
    q           = request.GET.get('q', '').strip()
    exclude_uid = request.GET.get('exclude', '').strip()

    if len(q) < 2:
        return JsonResponse({'results': []})

    try:
        from apps.employees.models import Employee
        from django.db.models import Q

        # Step 1 — search employees
        qs = Employee.objects.select_related('position').filter(
            is_active=True
        ).filter(
            Q(last_name__icontains=q)  |
            Q(first_name__icontains=q) |
            Q(id_number__icontains=q)
        )[:20]

        # Step 2 — get the current user's linked employee_id so we
        #           don't mark their own employee as "already linked"
        current_emp_id = None
        if exclude_uid:
            try:
                cu = SystemUser.objects.get(user_id=int(exclude_uid))
                if cu.employee_id:
                    current_emp_id = cu.employee_id
            except Exception:
                pass

        # Step 3 — get ALL employee IDs already linked to ANY system user
        #           (pure Python set — no annotate, no ORM expression)
        linked_emp_ids = set(
            SystemUser.objects
            .filter(employee__isnull=False, is_deleted=False)
            .values_list('employee_id', flat=True)
        )

        # Step 4 — build results
        results = []
        for emp in qs:
            # An employee is "already linked" if some OTHER user owns them
            already_linked = (
                emp.employee_id in linked_emp_ids
                and emp.employee_id != current_emp_id
            )
            results.append({
                'employee_id':    emp.employee_id,
                'full_name':      emp.get_full_name(),
                'first_name':     emp.first_name,
                'last_name':      emp.last_name,
                'id_number':      emp.id_number,
                'position':       emp.position.position_title if emp.position else '—',
                'already_linked': already_linked,
            })

        return JsonResponse({'results': results})

    except Exception as exc:
        logger.error('[accounts] employee_search error: %s', exc)
        return JsonResponse({'results': [], 'error': str(exc)})

# EMPLOYEE LOOKUP API  /accounts/api/employee-lookup/   [admin+, AJAX GET]
# Used by the create forms to auto-fill name/position from an ID number.
@login_required
@admin_required
@require_GET
def employee_lookup(request):
    id_number = request.GET.get('id_number', '').strip()
    if not id_number:
        return JsonResponse({'found': False, 'message': 'ID number required.'})
 
    try:
        from apps.employees.models import Employee
        emp = Employee.objects.select_related('position', 'division').get(id_number=id_number)
        already_linked = hasattr(emp, 'system_user')
        return JsonResponse({
            'found':            True,
            'employee_pk':      emp.employee_id,
            'full_name':        emp.get_full_name(),
            'initials':         emp.get_initials(),
            'position':         emp.position.position_title if emp.position else '—',
            'division':         emp.division.division_name  if emp.division else '—',
            'employment_type':  emp.employment_type,
            'already_linked':   already_linked,
        })
    except Exception:
        return JsonResponse({'found': False, 'message': 'Employee not found.'})

# ------ PRIVATE HELPERS -----
def _record_failure(username: str, request) -> None:
    count = increment_attempts(username)
    if count >= MAX_ATTEMPTS:
        lock_account(username)
        logger.warning('[accounts] Account locked: %s (%s failures) from %s', username, count, get_client_ip(request))

def profile(request):
    return render(request, 'accounts/profile.html')