"""
apps/leaves/models.py

BFAR Region III — HRIS
Leave Credit and Undertime Conversion Models

Models:
    1. LeaveCredit          → TABLE 17   (leave_credits)
    2. UndertimeConversion  → TABLE 17b  (undertime_conversion)

Leave Rules (from schema):
    - ONLY Permanent employees have leave credits (VL + SL).
    - COS and JO have NO leave — absences deduct directly from salary.
    - Earned = 1.25 per month for both VL and SL.
    - First month is prorated based on date_hired (handled in leaves/engine.py).
    - Balance formula:
          balance = prev_balance + earned - undertime_days - abs_wp - special_leave_used
    - If balance reaches 0 and employee applies leave → deducted from salary instead.
    - Undertime conversion uses the official conversion table (UndertimeConversion).
    - Wellness Leave applies to Permanent now; pending approval for COS/JO.

Cross-app imports:
    - apps.employees.models.Employee (FK)
"""

from django.db import models
from decimal import Decimal
import pytz


# ─────────────────────────────────────────────────────────────────────────────
# SHARED PH TIME MIXIN
# ─────────────────────────────────────────────────────────────────────────────

class PhilippinesTimeMixin:
    def _to_ph(self, dt):
        if dt:
            return dt.astimezone(pytz.timezone('Asia/Manila'))
        return None

    def get_formatted_ph_time(self, field_name):
        ph = self._to_ph(getattr(self, field_name, None))
        return ph.strftime('%B %d, %Y at %I:%M %p') if ph else None


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 17b — UndertimeConversion
# Official conversion table from the Employee Leave Record PDF.
# Based on 8-hour workday.
# Used by leaves/engine.py to convert undertime minutes/hours into
# a fraction-of-a-day for leave credit deduction.
#
# Build order: seed this table FIRST before computing any LeaveCredit rows.
# ─────────────────────────────────────────────────────────────────────────────

class UndertimeConversion(models.Model):

    UNIT_TYPE_CHOICES = [
        ('HOURS',   'Hours'),
        ('MINUTES', 'Minutes'),
    ]

    # ── Primary Key ───────────────────────────────────────────────────────────
    id = models.AutoField(primary_key=True)

    # ── Conversion Values ─────────────────────────────────────────────────────
    unit_type = models.CharField(
        max_length=10,
        choices=UNIT_TYPE_CHOICES,
        help_text="'HOURS' (1–8) or 'MINUTES' (1–60)"
    )
    value = models.IntegerField(
        help_text="Number of hours (1–8) or minutes (1–60)"
    )
    equivalent_day = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        help_text=(
            "Fraction of a working day. "
            "e.g. 1 min=0.002 | 30 min=0.062 | "
            "1 hr=0.125 | 4 hrs=0.500 | 8 hrs=1.000"
        )
    )

    # ── Lookup Helper ─────────────────────────────────────────────────────────
    @classmethod
    def get_equivalent(cls, unit_type: str, value: int) -> Decimal:
        """
        Look up the fractional day equivalent for a given undertime value.

        Usage in engine.py:
            fraction = UndertimeConversion.get_equivalent('HOURS', 2)
            # returns Decimal('0.250')

            fraction = UndertimeConversion.get_equivalent('MINUTES', 30)
            # returns Decimal('0.062')
        """
        try:
            record = cls.objects.get(unit_type=unit_type.upper(), value=value)
            return record.equivalent_day
        except cls.DoesNotExist:
            return Decimal('0.000')

    @classmethod
    def convert_total_minutes(cls, total_minutes: int) -> Decimal:
        """
        Convert a raw total-minutes-late figure into a fractional day.
        Breaks down into full hours + remaining minutes,
        then sums both lookups.

        Usage in engine.py:
            undertime_fraction = UndertimeConversion.convert_total_minutes(135)
            # 2 hrs + 15 mins → 0.250 + 0.031 = 0.281
        """
        if total_minutes <= 0:
            return Decimal('0.000')

        hours, mins = divmod(total_minutes, 60)
        total = Decimal('0.000')

        if hours > 0:
            total += cls.get_equivalent('HOURS', min(hours, 8))
        if mins > 0:
            total += cls.get_equivalent('MINUTES', min(mins, 60))

        return total.quantize(Decimal('0.001'))

    def __str__(self):
        return (
            f"{self.value} {self.get_unit_type_display()} "
            f"= {self.equivalent_day} day"
        )

    class Meta:
        db_table  = 'undertime_conversion'
        ordering  = ['unit_type', 'value']
        unique_together = ('unit_type', 'value')
        verbose_name        = 'Undertime Conversion'
        verbose_name_plural = 'Undertime Conversions'

    # ── Seed Data Reference ───────────────────────────────────────────────────
    # Minutes (1–60):
    #   1 min  = 0.002 | 15 min = 0.031 | 30 min = 0.062 |
    #   45 min = 0.094 | 60 min = 0.125
    # Hours (1–8):
    #   1 hr   = 0.125 | 2 hrs  = 0.250 | 3 hrs  = 0.375 |
    #   4 hrs  = 0.500 | 5 hrs  = 0.625 | 6 hrs  = 0.750 |
    #   7 hrs  = 0.875 | 8 hrs  = 1.000
    #
    # Load via: python manage.py loaddata undertime_conversion.json


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 17 — LeaveCredit
# Monthly leave credit tracking — Permanent employees ONLY.
# One row per employee per leave_type per year per month.
# ─────────────────────────────────────────────────────────────────────────────

class LeaveCredit(PhilippinesTimeMixin, models.Model):

    LEAVE_TYPE_CHOICES = [
        ('VL', 'Vacation Leave'),
        ('SL', 'Sick Leave'),
    ]

    # Month choices for display
    MONTH_CHOICES = [
        (1,  'January'),
        (2,  'February'),
        (3,  'March'),
        (4,  'April'),
        (5,  'May'),
        (6,  'June'),
        (7,  'July'),
        (8,  'August'),
        (9,  'September'),
        (10, 'October'),
        (11, 'November'),
        (12, 'December'),
    ]

    # ── Primary Key ───────────────────────────────────────────────────────────
    credit_id = models.AutoField(primary_key=True)

    # ── Employee Reference (Permanent only) ───────────────────────────────────
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.PROTECT,
        related_name='leave_credits',
        help_text="Permanent employee only — COS/JO have no leave credits"
    )

    # ── Leave Type & Period ───────────────────────────────────────────────────
    leave_type = models.CharField(
        max_length=2,
        choices=LEAVE_TYPE_CHOICES,
        help_text="VL = Vacation Leave | SL = Sick Leave"
    )
    year = models.IntegerField(
        help_text="Calendar year e.g. 2025"
    )
    month = models.IntegerField(
        choices=MONTH_CHOICES,
        help_text="Calendar month number (1–12)"
    )

    # ── Credit Components ─────────────────────────────────────────────────────
    earned = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal('1.250'),
        help_text=(
            "Credits earned this month. "
            "Default = 1.25. "
            "First month is prorated based on date_hired (set by engine.py)."
        )
    )
    undertime_days = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal('0.000'),
        help_text=(
            "UT fraction deducted. "
            "Sourced from UndertimeConversion lookup. "
            "e.g. UT=4hrs → 0.500"
        )
    )
    abs_wp = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal('0.000'),
        help_text=(
            "Absences Without Pay in fraction of a day. "
            "If leave credits = 0 and employee is absent, "
            "deducted from salary instead."
        )
    )
    special_leave_used = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal('0.000'),
        help_text="SPL or other special leave used this month in days"
    )
    special_leave_label = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="e.g. SPL (2-0-0) | SPL (1-0-0)"
    )

    # ── Running Balance ───────────────────────────────────────────────────────
    balance = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        help_text=(
            "Running balance: "
            "prev_balance + earned - undertime_days - abs_wp - special_leave_used"
        )
    )

    # ── Remarks ───────────────────────────────────────────────────────────────
    remarks = models.TextField(
        null=True,
        blank=True,
        help_text=(
            "HR notes e.g. 'NO OUT July 21' | "
            "'Oct. 24 no PM in' | "
            "'Dec. 26-27 absent'"
        )
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Balance Computation ───────────────────────────────────────────────────
    def compute_balance(self, previous_balance: Decimal = Decimal('0.000')) -> Decimal:
        """
        Compute and set the running balance for this month.
        Call from leaves/engine.py after setting all credit components.

        Args:
            previous_balance: The balance from the previous month's LeaveCredit row.
                              Pass Decimal('0.000') for the employee's first month.

        Returns:
            The computed balance (also sets self.balance).
        """
        self.balance = (
            previous_balance +
            self.earned -
            self.undertime_days -
            self.abs_wp -
            self.special_leave_used
        ).quantize(Decimal('0.001'))

        # Balance cannot go below 0 in this field.
        # Negative amounts become salary deductions handled separately.
        if self.balance < Decimal('0.000'):
            self.balance = Decimal('0.000')

        return self.balance

    @classmethod
    def get_previous_balance(
        cls,
        employee,
        leave_type: str,
        year: int,
        month: int
    ) -> Decimal:
        """
        Retrieve the balance from the immediately preceding LeaveCredit row.
        Handles year boundary (December → January).

        Usage in engine.py:
            prev = LeaveCredit.get_previous_balance(emp, 'VL', 2026, 3)
        """
        prev_month = month - 1
        prev_year  = year

        if prev_month == 0:
            prev_month = 12
            prev_year  = year - 1

        try:
            prev = cls.objects.get(
                employee=employee,
                leave_type=leave_type,
                year=prev_year,
                month=prev_month,
            )
            return prev.balance
        except cls.DoesNotExist:
            return Decimal('0.000')

    # ── Display Helpers ───────────────────────────────────────────────────────
    def get_month_name(self):
        return dict(self.MONTH_CHOICES).get(self.month, str(self.month))

    def get_period_display(self):
        return f"{self.get_month_name()} {self.year}"

    def get_balance_display(self):
        """Format balance as e.g. '12.500 days'."""
        return f"{self.balance:.3f} days"

    def is_zero_balance(self):
        return self.balance == Decimal('0.000')

    # ── PH Time Helpers ───────────────────────────────────────────────────────
    def get_created_at_ph(self):
        return self._to_ph(self.created_at)

    def get_updated_at_ph(self):
        return self._to_ph(self.updated_at)

    def get_formatted_created_at_ph(self):
        return self.get_formatted_ph_time('created_at')

    def get_formatted_updated_at_ph(self):
        return self.get_formatted_ph_time('updated_at')

    def __str__(self):
        return (
            f"{self.employee.get_full_name()} — "
            f"{self.leave_type} {self.get_period_display()} "
            f"Balance: {self.balance:.3f}"
        )

    class Meta:
        db_table  = 'leave_credits'
        ordering  = ['employee__last_name', 'leave_type', '-year', '-month']
        # One row per employee per leave type per month per year
        unique_together = ('employee', 'leave_type', 'year', 'month')
        verbose_name        = 'Leave Credit'
        verbose_name_plural = 'Leave Credits'