"""
apps/travel_orders/models.py

BFAR Region III — HRIS
Travel Order and Trip Ticket Models

Models:
    1. TravelOrder  → TABLE 9  (travel_orders)

Business Rules (from schema):
    - Covers both Travel Orders (all employees, max 5 days) and
      Trip Tickets (drivers only).
    - HR encodes the TO/TT code which auto-marks the employee as
      present in DTR for the covered dates.
    - Maximum 5 days from date_from for Travel Orders.
    - TO code format : TO#26-02-1375HR
    - TT code format : TT#26-02-XXXX

Cross-app imports:
    - apps.employees.models.Employee  (FK — the traveling employee)
    - apps.accounts.models.SystemUser (FK — the HR staff who encoded this)
"""

from django.db import models
import pytz


class TravelOrder(models.Model):

    TICKET_TYPE_CHOICES = [
        ('TO', 'Travel Order'),
        ('TT', 'Trip Ticket'),
    ]

    # ── Primary Key ───────────────────────────────────────────────────────────
    to_id = models.AutoField(primary_key=True)

    # ── Employee Reference ────────────────────────────────────────────────────
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.PROTECT,
        related_name='travel_orders',
        help_text="The employee covered by this TO or TT"
    )

    # ── TO / TT Details ───────────────────────────────────────────────────────
    to_code = models.CharField(
        max_length=50,
        help_text="Format: TO#26-02-1375HR or TT#26-02-XXXX"
    )
    ticket_type = models.CharField(
        max_length=2,
        choices=TICKET_TYPE_CHOICES,
        help_text="TO = Travel Order (all employees) | TT = Trip Ticket (drivers only)"
    )
    destination = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Where the employee is traveling"
    )
    purpose = models.TextField(
        null=True,
        blank=True,
        help_text="Purpose of travel"
    )

    # ── Date / Time Coverage ──────────────────────────────────────────────────
    date_from = models.DateField(
        help_text="Start date of travel"
    )
    date_to = models.DateField(
        help_text="End date of travel (max 5 days from date_from)"
    )
    time_from = models.TimeField(
        null=True,
        blank=True,
        help_text="Start time if partial-day TO"
    )
    time_to = models.TimeField(
        null=True,
        blank=True,
        help_text="End time if partial-day TO"
    )

    # ── Overtime ──────────────────────────────────────────────────────────────
    with_overtime = models.BooleanField(
        default=False,
        help_text="Whether overtime is included in this TO"
    )
    ot_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Manual OT hours entered by HR if with_overtime = True"
    )

    # ── Created By ────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.PROTECT,
        related_name='encoded_travel_orders',
        null=True,
        blank=True,
        help_text="HR staff who encoded this TO/TT"
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── PH Time Helpers ───────────────────────────────────────────────────────
    def _to_ph(self, dt):
        if dt:
            return dt.astimezone(pytz.timezone('Asia/Manila'))
        return None

    def get_created_at_ph(self):
        return self._to_ph(self.created_at)

    def get_updated_at_ph(self):
        return self._to_ph(self.updated_at)

    def get_formatted_created_at_ph(self):
        ph = self.get_created_at_ph()
        return ph.strftime('%B %d, %Y at %I:%M %p') if ph else None

    # ── Display / Validation Helpers ──────────────────────────────────────────
    def get_duration_days(self):
        """Returns number of calendar days covered by this TO."""
        if self.date_from and self.date_to:
            return (self.date_to - self.date_from).days + 1
        return 0

    def is_within_max_days(self):
        """Travel Orders are capped at 5 days per schema rule."""
        return self.get_duration_days() <= 5

    def is_trip_ticket(self):
        return self.ticket_type == 'TT'

    def is_travel_order(self):
        return self.ticket_type == 'TO'

    def get_covered_dates(self):
        """Returns a list of all dates covered by this TO/TT."""
        from datetime import timedelta
        if not self.date_from or not self.date_to:
            return []
        dates = []
        current = self.date_from
        while current <= self.date_to:
            dates.append(current)
            current += timedelta(days=1)
        return dates

    def __str__(self):
        return (
            f"{self.to_code} — "
            f"{self.employee.get_full_name()} "
            f"({self.date_from} to {self.date_to})"
        )

    class Meta:
        db_table  = 'travel_orders'
        ordering  = ['-date_from', 'employee__last_name']
        verbose_name        = 'Travel Order'
        verbose_name_plural = 'Travel Orders'