"""
apps/holidays/models.py

BFAR Region III — HRIS
Holiday Calendar Model

Models:
    1. Holiday  → TABLE 10  (holidays)

Business Rules (from schema):
    - National and local holidays.
    - Holiday work = Overtime Thank You only (no pay effect whatsoever).
    - Used for display on DTR and for flagging dtr_records.is_holiday only.
    - Local holidays are those declared by LGU or agency.
    - No cross-app FKs needed — this is a standalone lookup table.
"""

from django.db import models
import pytz


class Holiday(models.Model):

    HOLIDAY_TYPE_CHOICES = [
        ('regular', 'Regular Holiday'),
        ('special', 'Special Non-Working Holiday'),
        ('local',   'Local Holiday'),
    ]

    # ── Primary Key ───────────────────────────────────────────────────────────
    holiday_id = models.AutoField(primary_key=True)

    # ── Holiday Details ───────────────────────────────────────────────────────
    holiday_name = models.CharField(
        max_length=200,
        help_text="e.g. Independence Day, Holy Wednesday, Pampanga Day"
    )

    holiday_date = models.DateField(
        unique=True,
        help_text="The actual holiday date"
    )
    
    holiday_type = models.CharField(
        max_length=10,
        choices=HOLIDAY_TYPE_CHOICES,
        help_text=(
            "regular = Regular Holiday per PH law | "
            "special = Special Non-Working | "
            "local = Declared by LGU or agency"
        )
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
    def get_holiday_date_display(self):
        """Returns e.g. 'June 12, 2026 (Thursday)'."""
        return self.holiday_date.strftime('%B %d, %Y (%A)')

    def is_regular(self):
        return self.holiday_type == 'regular'

    def is_special(self):
        return self.holiday_type == 'special'

    def is_local(self):
        return self.holiday_type == 'local'

    def __str__(self):
        return (
            f"{self.holiday_name} — "
            f"{self.holiday_date.strftime('%B %d, %Y')} "
            f"({self.get_holiday_type_display()})"
        )

    class Meta:
        db_table  = 'holidays'
        ordering  = ['holiday_date']
        verbose_name        = 'Holiday'
        verbose_name_plural = 'Holidays'