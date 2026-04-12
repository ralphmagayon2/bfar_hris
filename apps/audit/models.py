"""
apps/audit/models.py

BFAR Region III — HRIS
Audit Trail / Tamper Prevention Model

Models:
    1. AuditLog  → TABLE 11  (audit_logs)

Purpose:
    Every create/update/delete/approve/print action on critical tables
    is recorded here. This is the legal evidence against DTR tampering.

    CANNOT BE DELETED — enforce this via:
        - No delete view exposed in the UI (audit:list is read-only)
        - Django Admin: set has_delete_permission to return False
        - PostgreSQL: REVOKE DELETE ON audit_logs FROM bfar_user (recommended)

Business Rules (from schema):
    - reason field is REQUIRED when editing a record that was already approved.
    - old_value and new_value store full JSON snapshots for before/after diff.
    - performed_by is a FK to system_users — who did the action.
    - ip_address logs which workstation was used.

Cross-app imports:
    - apps.accounts.models.SystemUser (FK — performed_by)

NOTE ON JSONB:
    Django's JSONField maps to PostgreSQL's JSONB type natively.
    Use JSONField (not TextField) so you can query inside the JSON in admin/views.
"""

from django.db import models
import pytz


class AuditLog(models.Model):

    ACTION_CHOICES = [
        ('create',  'Create'),
        ('update',  'Update'),
        ('delete',  'Delete'),
        ('approve', 'Approve'),
        ('print',   'Print'),
    ]

    # ── Primary Key ───────────────────────────────────────────────────────────
    log_id = models.AutoField(primary_key=True)

    # ── What Was Affected ─────────────────────────────────────────────────────
    table_affected = models.CharField(
        max_length=50,
        help_text=(
            "Name of the DB table that was changed. "
            "e.g. dtr_records, payroll_records, leave_credits"
        )
    )
    record_id = models.IntegerField(
        help_text="The primary key value of the affected record"
    )

    # ── What Action Was Taken ─────────────────────────────────────────────────
    action = models.CharField(
        max_length=10,
        choices=ACTION_CHOICES,
        help_text="The type of action performed"
    )

    # ── Before / After Snapshots (JSONB) ──────────────────────────────────────
    old_value = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Full JSON snapshot of the record BEFORE the change. "
            "NULL for 'create' actions."
        )
    )
    new_value = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Full JSON snapshot of the record AFTER the change. "
            "NULL for 'delete' actions."
        )
    )

    # ── Who Did It ────────────────────────────────────────────────────────────
    # performed_by = models.ForeignKey(
    #     'accounts.SystemUser',
    #     on_delete=models.PROTECT,
    #     related_name='audit_logs',
    #     help_text="The system user who performed this action"
    # )

    performed_by = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="The system user who performed this action"
    )

    # ── When and Where ────────────────────────────────────────────────────────
    performed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Exact UTC timestamp of the action"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the workstation that was used"
    )

    # ── Reason (required for post-approval edits) ─────────────────────────────
    reason = models.TextField(
        null=True,
        blank=True,
        help_text=(
            "Reason for correction — MANDATORY if the record was already "
            "approved/locked before this edit. Enforced at the view level."
        )
    )

    # Description (required for what user does)
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Human-readable summary of what was done. Auto-generated or manually set."
    )

    # ── PH Time Helpers ───────────────────────────────────────────────────────
    def _to_ph(self, dt):
        if dt:
            return dt.astimezone(pytz.timezone('Asia/Manila'))
        return None

    def get_performed_at_ph(self):
        return self._to_ph(self.performed_at)

    def get_formatted_performed_at_ph(self):
        ph = self.get_performed_at_ph()
        return ph.strftime('%B %d, %Y at %I:%M %p') if ph else None

    def get_ph_date_short(self):
        ph = self.get_performed_at_ph()
        return ph.strftime('%b %d, %Y') if ph else None

    def get_ph_time_only(self):
        ph = self.get_performed_at_ph()
        return ph.strftime('%I:%M %p') if ph else None

    # ── Display Helpers ───────────────────────────────────────────────────────
    def get_diff(self):
        """
        Returns a dict of only the fields that changed between
        old_value and new_value. Useful for the audit detail view.
        """
        if not self.old_value or not self.new_value:
            return {}
        diff = {}
        all_keys = set(self.old_value.keys()) | set(self.new_value.keys())
        for key in all_keys:
            old = self.old_value.get(key)
            new = self.new_value.get(key)
            if old != new:
                diff[key] = {'before': old, 'after': new}
        return diff

    def has_changes(self):
        return bool(self.get_diff())

    def __str__(self):
        return (
            f"[{self.log_id}] {self.get_action_display()} on "
            f"{self.table_affected} #{self.record_id} "
            f"by {self.performed_by.username} "
            f"at {self.get_formatted_performed_at_ph()}"
        )

    class Meta:
        db_table  = 'audit_logs'
        ordering  = ['-performed_at']
        # No delete permission — enforced at the Admin and view level.
        verbose_name        = 'Audit Log'
        verbose_name_plural = 'Audit Logs'


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT HELPER FUNCTION
# Call this from any view that modifies critical records.
# ─────────────────────────────────────────────────────────────────────────────

def create_audit_log(
    table_affected: str,
    record_id: int,
    action: str,
    performed_by,
    old_value: dict = None,
    new_value: dict = None,
    ip_address: str = None,
    reason: str = None,
    description: str = None,
) -> AuditLog:
    """
    Convenience function to create an AuditLog entry.

    Usage example (in a view):

        from apps.audit.models import create_audit_log

        old_data = {'is_locked': False, 'minutes_late': 0}
        new_data = {'is_locked': True,  'minutes_late': 15}

        create_audit_log(
            table_affected='dtr_records',
            record_id=dtr.dtr_id,
            action='update',
            performed_by=request.session_user,
            old_value=old_data,
            new_value=new_data,
            ip_address=request.META.get('REMOTE_ADDR'),
            reason=form.cleaned_data.get('reason'),
        )
    """

    # Auto-generate description if not provided
    if not description:
        action_map = {
            'create': f'Created record #{record_id} in {table_affected}',
            'update': f'Updated record #{record_id} in {table_affected}',
            'delete': f'Deleted record #{record_id} in {table_affected}',
            'approve': f'Approved record #{record_id} in {table_affected}',
            'print': f'Printed record #{record_id} in {table_affected}',
        }
        description = action_map.get(action, f'{action} on {table_affected}')

        # Enrich with new_value details if available
        if new_value:
            for key in ('username', 'full_name', 'id_number', 'role'):
                if key in new_value:
                    description += f'— {key}: {new_value[key]}'
                    break

    # Save to database FIRST
    log = AuditLog.objects.create(
        table_affected=table_affected,
        record_id=record_id,
        action=action,
        performed_by=performed_by,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        reason=reason,
        description=description,
    )

    # THEN bust the cache so the next audit list page shows fresh stats
    try:
        from django.core.cache import cache
        cache.delete('audit:stats')
        cache.delete('audit:total_count')
    except Exception:
        pass # cache failure is non-fatal — never block the main action

    return log


# SESSION / AUTH ACTIVITY LOG
# Tracks login, logout, and auth events for all SystemUser roles.
# Seperate from AuditLog which tracks data changes on records.
# CANNOT BE DELETED - same enforcement rules as AuditLog.

class SystemUserActivityLog(models.Model):

    ACTION_CHOICES = [
        ('login', 'Logged In'),
        ('logout', 'Logged Out'),
        ('login_failed', 'Failed Login Attemp'),
        ('password_changed', 'Password Changed'),
        ('account_locked', 'Account Locked'),
    ]

    # PRIMARY KEY
    activity_id = models.AutoField(primary_key=True)

    # Who did it
    # Nullable because failed logins may references a username that doesn't exists.
    user = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
        help_text="NULL on failed login if the username does not exists in the system"
    )

    # Capture the attempt username even if FK is null (failed login case)
    attempted_username = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="The username string attempted - useful for failed login forensics"
    )

    # What Happened
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Optional detail e.g. 'Account locked after 5 failed attempts'"
    )

    # Where From
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Browser / client_info"
    )

    # When
    performed_at = models.DateTimeField(auto_now_add=True)
    
    # PH Time Helpers
    def to_ph(self, dt):
        if dt:
            return dt.astimezone(pytz.timezone('Asia/Manila'))
        return None
    
    def get_performed_at_ph(self):
        return self.to_ph(self.performed_at)
    
    def get_formatted_performed_at_ph(self):
        ph = self.get_performed_at_ph()
        return ph.strftime('%B %d, %Y at %I:%M: %p') if ph else None

    def get_ph_time_only(self):
        ph = self.get_performed_at_ph()
        return ph.strftime('%I:%M %p') if ph else None
    
    def __str__(self):
        who = self.user.username if self.user else (self.attempted_username or 'unknown')
        return (
            f"[{self.activity_id}] {who} —"
            f"{self.get_action_display()} "
            f"at {self.get_formatted_performed_at_ph()}"
        )
    
    class Meta:
        db_table = 'system_user_activity_logs'
        ordering = ['-performed_at']
        verbose_name = 'System User Activity Log'
        verbose_name_plural = 'System User Activity Logs'

# ACTIVITY LOG HELPER FUNCTION

def create_activity_log(
    action: str,
    user=None,
    attempted_username: str = None,
    description: str = None,
    ip_address: str = None,
    user_agent: str = None,
) -> 'SystemUserActivityLog':
    """
    Convenience function for logging session/auth events.

    Usage in login view:
        from apps.audit.models import create_activity_log

        # Successful login
        create_activity_log(
            action='login',
            user=system_user,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT'),
        )

        # Failed login (username may not exists)
        create_activity_log(
            action='login_failed',
            attempted_username=form_username,
            description='Invalid password',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
    """
    return SystemUserActivityLog.objects.create(
        user=user,
        attempted_username=attempted_username,
        action=action,
        description=description,
        ip_address=ip_address,
        # user_agent=user_agent,
    )