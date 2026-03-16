"""
apps/dtr/models.py

BFAR Region III — HRIS
Daily Time Record Models

Models:
    1. DTRRecord  → TABLE 8  (dtr_records)

Business Rules (from schema):
    - No grace period — any scan after 08:00 is immediately counted as late.
    - Half-day: AM IN present but no AM OUT + no PM IN + only PM OUT = half day absent.
    - FishCore flexible employees still have 4 biometric scans per day.
    - If biometric device is offline, HR manually logs via logbook then encodes corrections here.
    - OT hours are recorded for REFERENCE ONLY — Overtime Thank You means no additional pay.
    - Holidays also have no pay effect — recorded for display/reference only.

Cross-app imports:
    - apps.employees.models.Employee (FK)
"""

from django.db import models
import pytz


class DTRRecord(models.Model):

    # ── Status Choices (shared across all 4 time slots) ──────────────────────
    SLOT_STATUS_CHOICES = [
        ('present', 'Present'),
        ('late',    'Late'),
        ('absent',  'Absent'),
        ('to',      'Travel Order'),
        ('tt',      'Trip Ticket'),
        ('leave',   'On Leave'),
        ('holiday', 'Holiday'),
    ]

    HOLIDAY_TYPE_CHOICES = [
        ('regular', 'Regular Holiday'),
        ('special', 'Special Non-Working Holiday'),
        ('local',   'Local Holiday'),
    ]

    # ── Primary Key ───────────────────────────────────────────────────────────
    dtr_id = models.AutoField(primary_key=True)

    # ── Employee Reference ────────────────────────────────────────────────────
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.PROTECT,
        related_name='dtr_records',
        help_text="Employee reference"
    )

    # ── Date ──────────────────────────────────────────────────────────────────
    dtr_date = models.DateField(
        help_text="The date of this attendance record"
    )

    # ── Biometric Scan Timestamps ─────────────────────────────────────────────
    am_in  = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Biometric scan timestamp for AM time-in"
    )
    am_out = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Biometric scan timestamp for AM time-out"
    )
    pm_in  = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Biometric scan timestamp for PM time-in"
    )
    pm_out = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Biometric scan timestamp for PM time-out"
    )

    # ── Holiday / Rest Day Flags ──────────────────────────────────────────────
    is_holiday = models.BooleanField(
        default=False,
        help_text="Marked if the day is a holiday (national or local)"
    )
    holiday_type = models.CharField(
        max_length=10,
        choices=HOLIDAY_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text=(
            "Type of holiday — for record/display only. "
            "No pay effect per agency rules."
        )
    )
    is_restday = models.BooleanField(
        default=False,
        help_text="Saturday/Sunday or declared rest day"
    )

    # ── Computed DTR Values ───────────────────────────────────────────────────
    # These are computed by dtr/engine.py and stored here for fast querying.
    # The engine populates these fields when processing raw biometric logs.

    minutes_late = models.IntegerField(
        default=0,
        help_text=(
            "Total minutes late. No grace period. "
            "Any scan after 08:00 is late."
        )
    )
    hours_undertime = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Hours of undertime based on schedule"
    )
    hours_overtime = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text=(
            "Hours beyond PM out (17:00). "
            "OT Thank You — no additional pay."
        )
    )
    total_hours_worked = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Total actual hours worked"
    )

    # ── Per-Slot Status Flags ─────────────────────────────────────────────────
    am_in_status  = models.CharField(
        max_length=10,
        choices=SLOT_STATUS_CHOICES,
        null=True,
        blank=True,
        help_text="Status flag for AM time-in slot"
    )
    am_out_status = models.CharField(
        max_length=10,
        choices=SLOT_STATUS_CHOICES,
        null=True,
        blank=True,
        help_text="Status flag for AM time-out slot"
    )
    pm_in_status  = models.CharField(
        max_length=10,
        choices=SLOT_STATUS_CHOICES,
        null=True,
        blank=True,
        help_text="Status flag for PM time-in slot"
    )
    pm_out_status = models.CharField(
        max_length=10,
        choices=SLOT_STATUS_CHOICES,
        null=True,
        blank=True,
        help_text="Status flag for PM time-out slot"
    )

    # ── Remarks / Notes ───────────────────────────────────────────────────────
    remarks = models.TextField(
        null=True,
        blank=True,
        help_text=(
            "TO code (e.g. TO#26-02-1375HR), leave type, "
            "or manual correction note"
        )
    )

    # ── Lock Flag ─────────────────────────────────────────────────────────────
    is_locked = models.BooleanField(
        default=False,
        help_text=(
            "Locked after HR approves. "
            "Edit requires audit log reason."
        )
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── PH Time Helpers ───────────────────────────────────────────────────────
    def _to_ph(self, dt):
        if dt:
            return dt.astimezone(pytz.timezone('Asia/Manila'))
        return None

    def get_am_in_ph(self):
        return self._to_ph(self.am_in)

    def get_am_out_ph(self):
        return self._to_ph(self.am_out)

    def get_pm_in_ph(self):
        return self._to_ph(self.pm_in)

    def get_pm_out_ph(self):
        return self._to_ph(self.pm_out)

    def get_created_at_ph(self):
        return self._to_ph(self.created_at)

    def get_updated_at_ph(self):
        return self._to_ph(self.updated_at)

    # ── Display Helpers ───────────────────────────────────────────────────────
    def format_scan(self, dt):
        """Format a biometric scan timestamp for DTR display (12-hour, PH time)."""
        ph = self._to_ph(dt)
        return ph.strftime('%I:%M %p') if ph else ''

    def get_am_in_display(self):
        return self.format_scan(self.am_in)

    def get_am_out_display(self):
        return self.format_scan(self.am_out)

    def get_pm_in_display(self):
        return self.format_scan(self.pm_in)

    def get_pm_out_display(self):
        return self.format_scan(self.pm_out)

    def get_minutes_late_display(self):
        """Returns e.g. '1 hr 15 mins' or '45 mins'."""
        if not self.minutes_late:
            return ''
        hours, mins = divmod(self.minutes_late, 60)
        if hours and mins:
            return f"{hours} hr {mins} mins"
        elif hours:
            return f"{hours} hr"
        return f"{mins} mins"

    def is_half_day_absent(self):
        """
        Half-day rule from schema:
        AM IN present but no AM OUT + no PM IN + only PM OUT = half day absent.
        """
        return (
            self.am_in is not None and
            self.am_out is None and
            self.pm_in is None and
            self.pm_out is not None
        )

    def __str__(self):
        return (
            f"{self.employee.get_full_name()} — "
            f"{self.dtr_date} "
            f"({'Locked' if self.is_locked else 'Open'})"
        )

    class Meta:
        db_table     = 'dtr_records'
        ordering     = ['-dtr_date', 'employee__last_name']
        # One DTR row per employee per day
        unique_together = ('employee', 'dtr_date')
        verbose_name        = 'DTR Record'
        verbose_name_plural = 'DTR Records'