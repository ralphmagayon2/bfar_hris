"""
apps/accounts/utils.py
 
BFAR Region III — HRIS
Shared helpers for the accounts app.
 
Imported by:
    apps/accounts/views.py
    apps/accounts/tasks.py
    Any other app that needs auth, input, or request utilities.
 
Functions added from reference (AISched IT utils.py):
    get_user_agent()         - pairs with get_client_ip for audit logging
    validate_phone()         - Philippine mobile number validation
    format_phone_number()    - formats as 09XX-XXX-XXXX
    clean_input()            - strips control chars + length-limits free text
    is_valid_email()         - wraps Django's validate_email
    set_user_session()       - moved from views._start_session to utils
    clear_session_data()     - moved from views._clear_session to utils
"""

import hashlib
import logging
import re
import secrets
import string

from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# ----- LOCKOUT CONSTANTS (single source of truth - views import from here) ------

MAX_ATTEMPTS = 5         # failed login attempts before lockout
LOCKOUT_MINUTES = 15     # minutes the account stay locked
ATTEMPT_WINDOW = 60 * 10 # cache TTL for the attempt counter (10 mins)

# CACHE-BASED LOGIN LOCKOUT 

def _attempt_key(username: str) -> str:
    return f"bfar:login_attempts:{username.lower().strip()}"

def _lockout_key(username: str) -> str:
    return f"bfar:login_locked:{username.lower().strip()}"

def get_attempts(username: str) -> int:
    return cache.get(_attempt_key(username), 0)

def increment_attempts(username: str) -> int:
    """Increment failure counter; returns new count."""
    key = _attempt_key(username)
    current = cache.get(key, 0)
    new_count = current + 1
    cache.set(key, new_count, ATTEMPT_WINDOW)
    return new_count
    
def lock_account(username: str) -> None:
    """Lock the account and clear the attempt counter."""

    expiry = timezone.now() + timedelta(minutes=LOCKOUT_MINUTES)
    cache.set(_lockout_key(username), True, LOCKOUT_MINUTES * 60)
    cache.set(
        f"bfar:login_locked_expiry:{username.lower().strip()}",
        expiry,
        LOCKOUT_MINUTES * 60
    )
    cache.delete(_attempt_key(username))

def is_locked(username: str) -> bool:
    return bool(cache.get(_lockout_key(username)))

def get_lockout_remaining(username: str) -> int:
    """
    Returns seconds remaining in the lockout window.
    Returns 0 if not locked or already expired.
    Reads the expiry timestamp stored by lock_account().
    """
    expiry = cache.get(f"bfar:login_locked_expiry:{username.lower().strip()}")
    if not expiry:
        return 0
    from django.utils import timezone
    remaining = (expiry - timezone.now()).total_seconds()
    return max(0, int(remaining))


def clear_attempts(username: str) -> None:
    """Call on successful login to wipe both counter and lock."""
    cache.delete(_attempt_key(username))
    cache.delete(_lockout_key(username))


# SESSION HELPERS
# Centralised here so view don't duplicate sessions key logic.
# Sessions key written:
#   _auth_user_id    → int   (SystemUser PK)
#   _auth_user_role  → str   (role slug)
#   _auth_user_name  → str   (display name)
#   _auth_is_admin   → bool  (True for non-viewer roles)
# These are read by InjectCurrentUserMiddleware and the login decorators.

_ADMIN_ROLES = ('superadmin', 'hr_admin', 'hr_staff')

def set_user_session(request, user) -> None:
    """
    Write auth session keys and update last_login.
    Call on every successful login (employee portal and admin portal.)

    Usage:
        from apps.accounts.utils import set_user_session
        set_user_session(request, user)
    """
    request.session.cycle_key()
    request.session['_auth_user_id'] = user.user_id
    request.session['_auth_user_role'] = user.role
    request.session['_auth_user_name'] = user.get_display_name()
    request.session['_auth_is_admin'] = user.role in _ADMIN_ROLES
    user.record_login()


def clear_session_data(request) -> None:
    """
    Remove only BFAR auth session keys - does not flush the whole session.
    Safer than session.flush() when you only want to log out the current user without destroying other session data (e.g. CSRF token)

    Usage:
        from apps.accounts.utils import clear_session_data
        clear_session_data(request)
    """
    for key in ('_auth_user_id', '_auth_user_role', '_auth_user_name', '_auth_is_admin'):
        request.session.pop(key, None)

# ------ PASSWORD HELPERS ------

_UPPER = string.ascii_uppercase
_LOWER = string.ascii_lowercase
_DIGITS = string.digits
_SPECIAL = '@$!%*?&_+-='


def generate_temp_password(length: int = 12) -> str:
    """
    Cryptographically secure temporary password.
    Guarantees at least one uppercase, lowercase, digit, and special char.
    """
    mandatory = [
        secrets.choice(_UPPER),
        secrets.choice(_LOWER),
        secrets.choice(_DIGITS),
        secrets.choice(_SPECIAL),
    ]
    pool = _UPPER + _LOWER + _DIGITS + _SPECIAL
    rest = [secrets.choice(pool) for _ in range(length - len(mandatory))]
    chars = mandatory + rest
    secrets.SystemRandom().shuffle(chars)
    return ''.join(chars)


def validate_password_strength(password: str) -> list:
    """Return a list of error strings. Empty list = password is valid."""
    errors = []
    if len(password) < 8:
        errors.append('Password must be at least 8 characters')
    if len(password) > 64:
        errors.append('Password must not exceed 64 characters.')
    if not re.search(r'[A-Z]', password):
        errors.append('Must contain at least one uppercase letter.')
    if not re.search(r'[a-z]', password):
        errors.append('Must contain at least one lowercase letter.')
    if not re.search(r'\d', password):
        errors.append('Must contain at least one number.')
    if not re.search(r'[@$!%*?&_+\-=]', password):
        errors.append('Must contain at least one special characters: @$!%*?&_+-=')
    return errors


# ------ TOKEN HELPERS ------

def generate_reset_token() -> str:
    """URL-safe 48-character plaintext token (48 chars -> safe in URLS)"""
    return secrets.token_urlsafe(36)

def hash_token(token: str) -> str:
    """SHA-256 digest — what we store in the DB, never the raw token."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

# -------------- REQUEST METADATA HELPERS -----------

def get_client_ip(request) -> str:
    
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')

def get_user_agent(request) -> str:
    """
    Returns the User-Agent string from the request headers.
    Used when writing audit log entries.

    Usage:
        from apps.accounts.utils import get_user_agent
        ua = get_user_agent(request)
    """
    return request.META.get('HTTP_USER_AGENT', '')


# ----- USERNAME GENERATION -----

def generate_username(first_name: str, last_name: str) -> str:
    """
    Pattern: first letter of first name + last name, all lowercase, no spaces.
    Appends a counter if already taken: jdelacruz + jdelacruz2 -> jdelarcruz3
    """
    from apps.accounts.models import SystemUser

    base = re.sub(r'[^a-z0-9]', '', (first_name[0] + last_name).lower())[:40]
    if not base:
        base = 'user'
    
    candidate = base
    counter = 2
    while SystemUser.objects.filter(username=candidate).exists():
        candidate = f'{base}{counter}'
        counter += 1
    return candidate

# EMAIL HELPERS
# EMAIL MASKING (for "we sent a reset link to the users email")

def mask_email(email: str) -> str:
    """
    Returns a masked version for user-facing feedback:
        juandelacruz@gmail.com -> ju**********@gmail.com
    """
    if '@' not in email:
        return email
    local, domain = email.split('@', 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f'{visible}{"*" * max(1, len(local) - len(visible))}@{domain}'

def is_valid_email(email: str) -> bool:
    """
    Returns True if the email passes Django's EmailValidator.

    Usage:
        from apps.accounts.utils import is_valid_email
        if not is_valid_email(email):
            messages.error(request, 'Invalid email.')
    """
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


# PHILIPPINE PHONE HELPERS
# From reference of my old project — adapted for BFAR HRIS.
# Only used when a phone number field is added to Employee or SystemUser

# Known Philippine mobile network prefixes (4-digit)
_PH_PREFIXES = {
    # Globe / TM
    '0905','0906','0915','0916','0917','0925','0926','0927','0935',
    '0936','0937','0945','0953','0954','0955','0956','0963','0964',
    '0965','0966','0975','0976','0977','0978','0979','0994','0995',
    '0996','0997',
    # Smart / TNT / Sun
    '0907','0908','0909','0910','0911','0912','0913','0914','0918',
    '0919','0920','0921','0922','0923','0928','0929','0930','0931',
    '0932','0933','0934','0938','0939','0940','0941','0942','0943',
    '0946','0947','0948','0949','0950','0951','0961','0962','0967',
    '0968','0969','0970','0980','0981','0982','0983','0984','0985',
    '0986','0987','0988','0989','0992','0993','0998','0999',
    # Dito
    '0895','0896','0897','0898','0991',
}

def validate_phone(phone: str) -> tuple:
    """
    Validate Philippine mobile number.
    Returns (True, '') on success or (False, error_message) on failure.

    Usage:
        from apps.accounts.utils import validate_phone
        is_valid, error = validate_phone(request.POST.get('phone', ''))
        if not is_valid:
            messages.error(request, error)
    """
    if not phone:
        return False, 'Phone is required.'
    
    digits = re.sub(r'\D', '', phone)

    if len(digits) != 11:
        return False, 'Phone number must be exactly 11 digits.'
    if not digits.startswith('09'):
        return False, 'Phone must start with 09.'
    if len(set(digits[2:])) == 1:
        return False, 'Invalid phone number pattern.'
    if re.search(r'(\d)\1{6,}', digits):
        return False, 'Invalid phone number pattern.'
    if digits[:4] not in _PH_PREFIXES:
        return False, 'Invalid Philippine mobile network prefix.'
    
    return True, ''


def format_phone_number(phone: str) -> str:
    """
    Format a Philippine mobile number as 09XX-XXX-XXXX.
    Returns the original string unchanged if it is shorter than expected.
 
    Usage:
        from apps.accounts.utils import format_phone_number
        formatted = format_phone_number('09171234567')  # → '0917-123-4567'
    """
    if not phone:
        return ''
    digits = re.sub(r'\D', '', phone)[:11]
    if len(digits) == 11:
        return f'{digits[:4]}-{digits[4:7]}-{digits[7:]}'
    if len(digits) >= 7:
        return f'{digits[:4]}-{digits[4:7]}-{digits[7:]}'
    if len(digits) >= 4:
        return f'{digits[:4]}-{digits[4:]}'
    return digits


# INPUT SANITATION

def clean_input(value: str, max_length: int = 1000) -> str:
    """
    Strip leading/trailing whitespace, collapse internal whitespace,
    and remove non-printable control characters.
    Intended for free-text fields (names, notes, reason fields).

    Usage:
        from apps.accounts.utils import clean_input
        reason = clean_input(request.POST.get('reason', ''))
    """
    if not value:
        return ''
    cleaned = str(value). strip()
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned[:max_length]