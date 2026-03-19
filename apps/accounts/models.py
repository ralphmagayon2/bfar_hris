"""
apps/accounts/models.py

BFAR Region III — HRIS
System User and Signature Models

Models:
    1. SystemUser  → TABLE 12  (system_users)
    2. Signature   → TABLE 13  (signatures)  [Optional — pending client confirmation]

Role Hierarchy (from schema):
    superadmin → Full IT access to all modules
    hr_admin   → All HR modules (DTR, payroll, leaves, travel orders, employees)
    hr_staff   → View + encode only (no approve/delete)
    viewer     → Own records only (employee self-service, future feature)

Security Notes:
    - Passwords use bcrypt via django's make_password / check_password.
    - SystemUser.employee FK is nullable — IT admins are not BFAR employees.
    - Account locking after failed attempts should be handled in the login view.

Cross-app imports:
    - apps.employees.models.Employee (nullable FK on SystemUser)
"""

import hashlib
import secrets
import logging
import pytz

from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 12 — SystemUser
# HR and Admin accounts who log in to the system.
# Roles control access to modules.
# ─────────────────────────────────────────────────────────────────────────────

class SystemUser(models.Model):

    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('hr_admin',   'HR Admin'),
        ('hr_staff',   'HR Staff'),
        ('viewer',     'Viewer'),
    ]

    # ── Primary Key ───────────────────────────────────────────────────────────
    user_id = models.AutoField(primary_key=True)

    # ── Employee Link (nullable for IT admins) ────────────────────────────────
    employee = models.OneToOneField(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='system_user',
        help_text=(
            "NULL if this account belongs to an IT admin "
            "who is not a BFAR employee"
        )
    )

    # ── Login Credentials ─────────────────────────────────────────────────────
    username = models.CharField(max_length=50, unique=True, help_text="Login username")
    password_hash = models.CharField(
        max_length=255,
        help_text="Bcrypt hashed password (via Django's make_password)"
    )

    # -- Contact --
    personal_email = models.EmailField(
        max_length=254,
        blank=True, default='',
        help_text=(
            "Off-system personal email used ONLY for password-reset links. "
            "Required so the user recover their own account."
        ),
    ) 

    # ── Role / Access ─────────────────────────────────────────────────────────
    role = models.CharField(
        max_length=15,
        choices=ROLE_CHOICES,
        default='hr_staff',
        help_text=(
            "superadmin = IT full access | "
            "hr_admin = all HR modules | "
            "hr_staff = view + encode | "
            "viewer = own records only"
        )
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(default=True, help_text="Account active status")

    # Delete
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag — deleted accounts are hidden but kept for audit trail"
    )

    # ── Login Tracking ────────────────────────────────────────────────────────
    last_login = models.DateTimeField(null=True, blank=True, help_text="Last successful login timestamp")

    # -- Password Reset --
    reset_token_hash = models.CharField(
        max_length=64, blank=True, default='',
        help_text="SHA-256 hex of the one-time reset token"
    )

    reset_token_expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Token expiry - 1 hour from generation"
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Password Methods ──────────────────────────────────────────────────────
    def set_password(self, raw_password):
        """Hash and store password using Django's bcrypt-compatible hasher."""
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        """Verify a raw password against the stored hash."""
        if not raw_password or not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)

    def record_login(self):
        """Update last_login to now (call on successful authentication)."""
        self.last_login = timezone.now()
        self.save(update_fields=['last_login'])

    # -- Reset Token Methods --
    def has_valid_reset_token(self) -> bool:
        return bool(
            self.reset_token_hash and self.reset_token_expires_at and timezone.now() < self.reset_token_expires_at
        )
    
    def clear_reset_token(self) -> None:
        self.reset_token_hash = ''
        self.reset_token_expires_at = None
        self.save(update_fields=['reset_token_hash', 'reset_token_expires_at'])

    # ── Role Helpers ──────────────────────────────────────────────────────────
    def is_superadmin(self):
        return self.role == 'superadmin'

    def is_hr_admin(self):
        return self.role == 'hr_admin'

    def is_hr_staff(self):
        return self.role == 'hr_staff'

    def is_viewer(self):
        return self.role == 'viewer'

    def can_approve(self):
        """Only superadmin and hr_admin can approve DTR/payroll."""
        return self.role in ('superadmin', 'hr_admin')

    def can_encode(self):
        """hr_staff and above can encode records."""
        return self.role in ('superadmin', 'hr_admin', 'hr_staff')

    def can_manage_users(self):
        """Only superadmin can create/edit system user accounts."""
        return self.role == 'superadmin'

    # ── Display Helpers ───────────────────────────────────────────────────────
    def get_full_name(self) -> str:
        """
        Returns the user's full name.

        Priority:
            1. Linked Employee full name
            2. Username fallback (for IT admins without employee record)
        """
        if self.employee:
            try:
                return self.employee.get_full_name()
            except AttributeError:
                # fallback if employee models has no helper
                first = getattr(self.employee, 'first_name', '') or ''
                last = getattr(self.employee, 'last_name', '') or ''
                full = f"{first} {last}".strip()
                if full:
                    return full
        
        return self.username
    
    def get_display_name(self):
        """
        If linked to an employee record, show their full name.
        Otherwise fall back to the username.
        """
        if self.employee:
            return self.employee.get_full_name()
        return self.username
    
    def get_short_name(self) -> str:
        """First name, or username if no linked employee."""
        if self.employee:
            return self.employee.get_full_name()
        return self.username
    
    def get_initials(self) -> str:
        """Two letter initials for avatar badges."""
        if self.employee:
            return self.employee.get_initials()
        return self.username[:2].upper()

    def get_profile_picture_url(self) -> str:
        """Placeholder - returns '' until a photo field is added."""
        return ''

    # ── PH Time Helpers ───────────────────────────────────────────────────────
    def _to_ph(self, dt):
        if dt:
            return dt.astimezone(pytz.timezone('Asia/Manila'))
        return None

    def get_last_login_ph(self):
        return self._to_ph(self.last_login)

    def get_formatted_last_login_ph(self):
        ph = self.get_last_login_ph()
        return ph.strftime('%B %d, %Y at %I:%M %p') if ph else 'Never'

    def get_created_at_ph(self):
        return self._to_ph(self.created_at)

    def get_formatted_created_at_ph(self):
        ph = self.get_created_at_ph()
        return ph.strftime('%B %d, %Y at %I:%M %p') if ph else None

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    class Meta:
        db_table  = 'system_users'
        ordering  = ['username']
        verbose_name        = 'System User'
        verbose_name_plural = 'System Users'


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 13 — Signature
# Optional table for Ma'am Zen's signature block on printed documents.
# Currently set to display name only (ZENAIDA S. SIMON, Administrative Officer V).
# Activate when confirmed by client.
# ─────────────────────────────────────────────────────────────────────────────

class Signature(models.Model):

    # ── Primary Key ───────────────────────────────────────────────────────────
    signature_id = models.AutoField(primary_key=True)

    # ── Linked System User ────────────────────────────────────────────────────
    user = models.ForeignKey(
        SystemUser,
        on_delete=models.PROTECT,
        related_name='signatures',
        help_text="Whose signature this is"
    )

    # ── Printed Name Block ────────────────────────────────────────────────────
    display_name = models.CharField(
        max_length=200,
        default='ZENAIDA S. SIMON',
        help_text="Printed name e.g. ZENAIDA S. SIMON"
    )
    display_title = models.CharField(
        max_length=200,
        default='Administrative Officer V',
        help_text="e.g. Administrative Officer V"
    )

    # ── Optional Signature Image ──────────────────────────────────────────────
    signature_image = models.BinaryField(
        null=True,
        blank=True,
        help_text=(
            "Uploaded image of handwritten signature (optional). "
            "Stored as binary — activate when confirmed by client."
        )
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this signature is currently in use on printed documents"
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)

    # ── PH Time Helpers ───────────────────────────────────────────────────────
    def _to_ph(self, dt):
        if dt:
            return dt.astimezone(pytz.timezone('Asia/Manila'))
        return None

    def get_created_at_ph(self):
        return self._to_ph(self.created_at)

    def get_formatted_created_at_ph(self):
        ph = self.get_created_at_ph()
        return ph.strftime('%B %d, %Y at %I:%M %p') if ph else None

    # ── Display Helpers ───────────────────────────────────────────────────────
    def get_signature_block(self):
        """
        Returns the full signature block as a dict for template rendering.
        Used by DTR, payslip, and SED print templates.
        """
        return {
            'display_name':  self.display_name,
            'display_title': self.display_title,
            'has_image':     self.signature_image is not None,
        }

    def __str__(self):
        status = 'Active' if self.is_active else 'Inactive'
        return f"{self.display_name} — {self.display_title} ({status})"

    class Meta:
        db_table  = 'signatures'
        ordering  = ['-is_active', 'display_name']
        verbose_name        = 'Signature'
        verbose_name_plural = 'Signatures'