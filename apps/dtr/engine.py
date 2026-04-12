"""
apps/dtr/engine.py
"""

from __future__ import annotations
import datetime as dt_module
from datetime import date, time
from decimal import Decimal
import pytz
from apps.dtr.models import DTRRecord

PH_TZ = pytz.timezone('Asia/Manila')
EXPECTED_AM_IN = time(8, 0)
EXPECTED_AM_OUT = time(12, 0)
EXPECTED_PM_IN = time(13, 0)
EXPECTED_PM_OUT = time(17, 0)
WORK_HOURS_DAY = 8.0

# Time helpers


def _to_min(t: time | None) -> int:
    """Convert time object to minutes since midnight."""
    if t is None:
        return 0
    return t.hour * 60 + t.minute

def _parse_time_str(raw: str | None) -> time | None:
    """Parse HH:MM string to time object. Returns None if blank/invalid."""
    if not raw or not raw.strip():
        return None
    try:
        h, m = map(int, raw.strip().split(':'))
        return time(h, m)
    except (ValueError, AttributeError):
        return None
    
def _localize(dtr_date: date, t: time | None):
    """Combine a date and time into a PH-timezone-aware datetime. None if no time."""
    if t is None:
        return None
    naive = dt_module.datetime.combine(dtr_date, t)
    return PH_TZ.localize(naive)

# Scheedule Resolver

# Returned by _get_effective_schedule - used by compute_dtr_day and views
_SCHEDULE_DEFAULTS = {
    'is_flexible': False,
    'is_free': False, # New
    'working_hours_per_day': 8.0,
    'flex_start_earliest': time(7, 0),
    'flex_start_latest': time(8, 0),
    'am_out_expected': time(12, 0),
    'pm_in_expected': time(13, 0),
    'pm_out_expected': time(17, 0),
}

def _schedule_to_dict(ws) -> dict:
    """Convert a WorkSchedule instance to the engine's schedule dict."""
    return {
        'is_flexible': ws.is_flexible,
        'is_free': getattr(ws, 'is_free', False), # New
        'working_hours_per_day': float(ws.working_hours_per_day),
        'flex_start_earliest': ws.flex_start_earliest,
        'flex_start_latest': ws.flex_start_latest,
        # am_out / pm_in / pm_out come from the schedule's time fields
        'am_out_expected': ws.am_out,
        'pm_in_expected': ws.pm_in,
        'pm_out_expected': ws.pm_out,
    }

def get_effective_schedule(employee, dtr_date: date) -> dict:
    """
    Resolve the effective WorkSchedule for an employee.

    Priority (least → most specific):
        1. Division default_schedule
        2. Unit default_schedule (walks up parent_unit chain)
        3. EmployeeSchedule entry (most specific)

    For EmployeeSchedule, we look for the most recent entry
    with effective_date <= dtr_date. If none exists before dtr_date,
    we fall back to the most recent entry overall (handles pushed schedules
    that were created after the DTR date being viewed).
    """
    from apps.employees.models import EmployeeSchedule

    resolved = dict(_SCHEDULE_DEFAULTS)

    try:
        # 1. Division default
        if employee.division and employee.division.default_schedule:
            resolved = _schedule_to_dict(employee.division.default_schedule)

        # 2. Unit — walk up sub-unit → unit → division chain
        if employee.unit:
            unit_sched = employee.unit.get_schedule_with_fallback()
            if unit_sched:
                resolved = _schedule_to_dict(unit_sched)

        # 3. Employee-level override (most specific)
        # First try: exact date range (the schedule that was active on dtr_date)
        emp_sched = (
            EmployeeSchedule.objects
            .select_related('schedule')
            .filter(employee=employee, effective_date__lte=dtr_date)
            .order_by('-effective_date')
            .first()
        )

        # Fallback: if no schedule exists on or before dtr_date,
        # use the earliest one available (handles pushed schedules
        # that were created after the historical date being viewed)
        if not emp_sched:
            emp_sched = (
                EmployeeSchedule.objects
                .select_related('schedule')
                .filter(employee=employee)
                .order_by('effective_date')
                .first()
            )

        if emp_sched:
            resolved = _schedule_to_dict(emp_sched.schedule)

    except Exception:
        pass

    return resolved


# Deduction Helpers

# Individual deduction computers
def _late_minutes(am_in: time | None, am_in_expected: time = EXPECTED_AM_IN) -> int:
    """Minutes late — AM In after 08:00. No grace period."""
    if am_in is None:
        return 0
    return max(0, _to_min(am_in) - _to_min(am_in_expected))

def _early_lunch_minutes(am_out: time | None, am_out_expected: time = EXPECTED_AM_OUT) -> int:
    """AM Out before 12:00."""
    if am_out is None:
        return 0
    return max(0, _to_min(am_out_expected) - _to_min(am_out))

def _late_return_minutes(pm_in: time | None, pm_in_expected: time = EXPECTED_PM_IN) -> int:
    """PM In after 13:00."""
    if pm_in is None:
        return 0
    return max(0, _to_min(pm_in) - _to_min(pm_in_expected))

def _undertime_minutes(pm_out: time | None, pm_out_expected: time = EXPECTED_PM_OUT) -> int:
    """PM Out before 17:00."""
    if pm_out is None:
        return 0
    return max(0, _to_min(pm_out_expected) - _to_min(pm_out))

def _missing_deduction(am_in, am_out, pm_in, pm_out) -> int:
    """
    Deduction for missing entries (in minutes).
    Rule:
      1 missing entry           → 240 min (4 hrs)
      AM Out + PM In both missing → 240 min (lunch block = 1 deduction)
      3+ missing                → 480 min (full day)
      All 4 missing             → 480 min (absent)
    """
    missing = [am_in is None, am_out is None, pm_in is None, pm_out is None]
    count = sum(missing)
    
    if count == 0:
        return 0
    if count >= 3:
        return 480
    if am_out is None and pm_in is None:
        return 240 # lunch block — treated as one
    if count == 1:
        return 240
    return 480     # 2 missing, not the lunch pair

def _hours_worked(am_in, am_out, pm_in, pm_out) -> float:
    """Compute actual hours worked from available time entries."""
    total = 0
    if am_in and am_out:
        total += max(0, _to_min(am_out) - _to_min(am_in))

    if pm_in and pm_out:
        total += max(0, _to_min(pm_out) - _to_min(pm_in))

    # Edge case: only AM In + PM Out (biometric missed middle scans)
    if am_in and pm_out and not am_out and not pm_in:
        span = _to_min(pm_out) - _to_min(am_in)
        total = max(0, span - 60) # deduct 1hr assumed lunch break
    return round(total / 60, 2)


# Slot status derivation

def _derive_slot_status(
    am_in, am_out, pm_in, pm_out,
    is_holiday: bool,
    is_restday: bool,
    am_in_override: str | None = None,
    am_out_override: str | None = None,
    pm_in_override: str | None = None,
    pm_out_override: str | None = None,
    am_in_expected=EXPECTED_AM_IN,
) -> dict:
    """
    Return per-slot status strings.
    Override values take precedence (for HR manual corrections.)
    """
    def _slot(override, biometric_time, expected):
        if override:
            return override # HR set this explicitly
        if is_holiday:
            return 'holiday'
        if is_restday:
            return None
        if biometric_time is None:
            return 'absent'
        if biometric_time > expected:
            return 'late'
        return 'present'
    
    return {
        'am_in_status': am_in_override or _slot(None, am_in, am_in_expected),
        'am_out_status': am_out_override or _slot(None, am_out, EXPECTED_AM_OUT),
        'pm_in_status': pm_in_override or _slot(None, pm_in, EXPECTED_PM_IN),
        'pm_out_status': pm_out_override or _slot(None, pm_out, EXPECTED_PM_OUT),
    }

# Main compute function

def compute_dtr_day(
        dtr_date:   str | None = None,
        am_in_str:  str | None = None,
        am_out_str: str | None = None,
        pm_in_str:  str | None = None,
        pm_out_str: str | None = None,
        is_holiday: bool = False,
        is_restday: bool = False,
        holiday_type: str | None = None,
        remarks:    str | None = None,
        # Optional ovverides for per-slot status (set by HR)
        am_in_override: str | None = None,
        am_out_override: str | None = None,
        pm_in_override: str | None = None,
        pm_out_override: str | None = None,
        schedule: dict | None = None,
) -> dict:
    """
    Compute all DTR values for one employee on one day.
    Returns a dict ready to be saved to DTRRecord via apply_dtr_record().

    Args:
        dtr_date:      The date of this record.
        am_in_str:     HH:MM string or None.
        am_out_str:    HH:MM string or None.
        pm_in_str:     HH:MM string or None.
        pm_out_str:    HH:MM string or None.
        is_holiday:    True if this day is a declared holiday.
        is_restday:    True if Saturday/Sunday or declared rest day.
        holiday_type:  'regular', 'special', or 'local'.
        remarks:       Free text (TO code, leave type, etc.).
        *_override:    HR-set slot status overrides.

    Returns dict with keys matching DTTRecord fields.
    """
    sched = schedule or dict(_SCHEDULE_DEFAULTS)

    is_flexible = sched.get('is_flexible', False)
    is_free = sched.get('is_free', False)
    working_hours_per_day = sched.get('working_hours_per_day', 8.0)
    flex_start_earliest = sched.get('flex_start_earliest', time(7, 0))
    flex_start_latest = sched.get('flex_start_latest', time(8, 0))
    am_out_expected = sched.get('am_out_expected', EXPECTED_AM_OUT)
    pm_in_expected = sched.get('pm_in_expected', EXPECTED_PM_IN)
    pm_out_expected = sched.get('pm_out_expected', EXPECTED_PM_OUT)

    # Parse raw time strings
    am_in = _parse_time_str(am_in_str)
    am_out = _parse_time_str(am_out_str)
    pm_in = _parse_time_str(pm_in_str)
    pm_out = _parse_time_str(pm_out_str)

    # Holiday / rest day — no deductions, no late
    if is_holiday or is_restday:
        return {
            'dtr_date':     dtr_date,
            'am_in':        _localize(dtr_date, am_in),
            'am_out':       _localize(dtr_date, am_out),
            'pm_in':        _localize(dtr_date, pm_in),
            'pm_out':       _localize(dtr_date, pm_out),
            'is_holiday':   is_holiday,
            'holiday_type': holiday_type,
            'is_restday':   is_restday,
            'minutes_late': 0,
            'hours_undertime': Decimal('0.00'),
            'hours_overtime':  Decimal('0.00'),
            'total_hours_worked': Decimal(str(_hours_worked(am_in, am_out, pm_in, pm_out))),
            'am_in_status': 'holiday' if is_holiday else None,
            'am_out_status': 'holiday' if is_holiday else None,
            'pm_in_status': 'holiday' if is_holiday else None,
            'pm_out_status': 'holiday' if is_holiday else None,
            'remarks': remarks,
        }
    
    # New: Free schedule with zero deductions because FishCore has free or any time schedule
    if is_free:
        # Determine presence: present if any scan exists, absent if none
        has_any_scan = any([am_in, am_out, pm_in, pm_out])
        hours_worked = _hours_worked(am_in, am_out, pm_in, pm_out)

        def _free_slot(override, biometric_time):
            if override:
                return override
            if biometric_time is None:
                return 'absent'
            return 'present'

        return {
            'dtr_date': dtr_date,
            'am_in': _localize(dtr_date, am_in),
            'am_out': _localize(dtr_date, am_out),
            'pm_in': _localize(dtr_date, pm_in),
            'pm_out': _localize(dtr_date, pm_out),
            'is_holiday': is_holiday,
            'holiday_type': holiday_type,
            'is_restday': is_restday,
            'minutes_late': 0,
            'hours_undertime': Decimal('0.00'),
            'hours_overtime': Decimal('0.00'),
            'total_hours_worked': Decimal(str(hours_worked)),
            'am_in_status': am_in_override or _free_slot(None, am_in),
            'am_out_status': am_out_override or _free_slot(None, am_out),
            'pm_in_status': pm_in_override or _free_slot(None, pm_in),
            'pm_out_status': pm_out_override or _free_slot(None, pm_out),
            'remarks': remarks,
        }
    
    # Fleible schedule
    if is_flexible:
        # Late only if arrival is AFTER flex_start_latest
        if am_in and am_in > flex_start_latest:
            late = _to_min(am_in) - _to_min(flex_start_latest)
        else:
            late = 0

        # Required out = am_in + working_hours + 1hr lunch
        # If no am_in, treat as absent (full deduction)
        if am_in:
            in_min = _to_min(am_in)
            req_out_min = in_min + int(working_hours_per_day * 60) + 60
            req_out_h = (req_out_min // 60) % 24
            req_out_m = req_out_min % 60
            flex_req_out = time(req_out_h, req_out_m)

            # Undertime = how many minutes short of required out
            if pm_out:
                ut_min = max(0, _to_min(flex_req_out) - _to_min(pm_out))
            else:
                ut_min = max(0, _to_min(flex_req_out) - _to_min(pm_in_expected))

            lunch_ded = 0
        else:
            # No am_in = absent
            ut_min = int(working_hours_per_day * 60)
            lunch_ded = 0
            flex_req_out = None

        total_deduction_min = late + ut_min + lunch_ded
        hours_undertime = round(total_deduction_min / 60, 2)
        hours_worked = _hours_worked(am_in, am_out, pm_in, pm_out)

        # OT = anything worked past flex_req_out
        hours_overtime = 0.0
        if flex_req_out and pm_out and pm_out > flex_req_out:
            ot_min = _to_min(pm_out) - _to_min(flex_req_out)
            hours_overtime = round(ot_min / 60, 2)

        # For flex schedule, amin_in is 'late' only after the flex_start_latest
        # else it's always 'present' regardless of arrival time
        def _flex_slot(override, biometric_time, is_am_in=False):
            if override:
                return override
            if biometric_time is None:
                return 'absent'
            if is_am_in and am_in and am_in > flex_start_latest:
                return 'late'
            return 'present'
        
        statuses = {
            'am_in_status': am_in_override or _flex_slot(None, am_in, is_am_in=True),
            'am_out_status': am_out_override or _flex_slot(None, am_out),
            'pm_in_status': pm_in_override or _flex_slot(None, pm_in),
            'pm_out_status': pm_out_override or _flex_slot(None, pm_out),
        }

        return {
            'dtr_date':           dtr_date,
            'am_in':              _localize(dtr_date, am_in),
            'am_out':             _localize(dtr_date, am_out),
            'pm_in':              _localize(dtr_date, pm_in),
            'pm_out':             _localize(dtr_date, pm_out),
            'is_holiday':         is_holiday,
            'holiday_type':       holiday_type,
            'is_restday':         is_restday,
            'minutes_late':       late,
            'hours_undertime':    Decimal(str(hours_undertime)),
            'hours_overtime':     Decimal(str(hours_overtime)),
            'total_hours_worked': Decimal(str(hours_worked)),  # FIX: was missing
            'am_in_status':  am_in_override  or _flex_slot(None, am_in,  is_am_in=True),
            'am_out_status': am_out_override or _flex_slot(None, am_out),
            'pm_in_status':  pm_in_override  or _flex_slot(None, pm_in),
            'pm_out_status': pm_out_override or _flex_slot(None, pm_out),
            'remarks': remarks,
        }
    
    # Fixed schedule 
    # Compute deductions
    late        = _late_minutes(am_in, flex_start_latest)
    early_lunch = _early_lunch_minutes(am_out, am_out_expected)
    late_return = _late_return_minutes(pm_in, pm_in_expected)
    undertime_m = _undertime_minutes(pm_out, pm_out_expected)
    missing_ded = _missing_deduction(am_in, am_out, pm_in, pm_out)

    total_deduction_min = late + early_lunch + late_return + undertime_m + missing_ded
    hours_undertime     = round(total_deduction_min / 60, 2)

    hours_worked = _hours_worked(am_in, am_out, pm_in, pm_out)

    hours_overtime = 0.0
    if pm_out and pm_out > pm_out_expected:
        ot_min         = _to_min(pm_out) - _to_min(pm_out_expected)
        hours_overtime = round(ot_min / 60, 2)

    statuses = _derive_slot_status(
        am_in, am_out, pm_in, pm_out,
        is_holiday, is_restday,
        am_in_override, am_out_override,
        pm_in_override, pm_out_override,
        am_in_expected=flex_start_latest,
    )

    return {
        'dtr_date': dtr_date,
        'am_in': _localize(dtr_date, am_in),
        'am_out': _localize(dtr_date, am_out),
        'pm_in': _localize(dtr_date, pm_in),
        'pm_out': _localize(dtr_date, pm_out),
        'is_holiday': is_holiday,
        'holiday_type': holiday_type,
        'is_restday': is_restday,
        'minutes_late': late,
        'hours_undertime': Decimal(str(hours_undertime)),
        'hours_overtime': Decimal(str(hours_overtime)),
        'total_hours_worked': Decimal(str(hours_worked)),
        **statuses,
        'remarks':  remarks,
    }


_SKIP_FIELDS = {'dtr_date', 'flex_required_out'}

def apply_dtr_record(employee, computed: dict, is_locked: bool = False):
    """
    Save or update a DTRecord for the given employee using computed values.

    Creates the record if it doesn't exist (get_or_create by employee+date).
    Updates all computed fields. Does NOT overwrite is_locked unless passed.

    Args:
        employee: Employee model instance.
        computed: Dict returned by compute_dtr_day().
        is_locked: Whether to lock the record after saving.

    Returns:
        (DTRRecord instance, created: bool)
    """
    dtr_date = computed['dtr_date']

    record, created = DTRRecord.objects.get_or_create(
        employee=employee,
        dtr_date=dtr_date,
    )

    for field, value in computed.items():
        if field in _SKIP_FIELDS:
            continue # already set via get_or_create
        setattr(record, field, value)
    
    if is_locked:
        record.is_locked = True

    record.save()
    return record, created