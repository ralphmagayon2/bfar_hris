"""
apps/dtr/management/commands/seed_dtr_data.py

Seed DTR records for 3 months for all active employees.
Schedule-aware: reads each employee's effective schedule and seeds
realistic data matching their schedule type (fixed, flexible, free).

Usage:
    python manage.py seed_dtr_data
    python manage.py seed_dtr_data --months 3
    python manage.py seed_dtr_data --month 2026-03
    python manage.py seed_dtr_data --clear
    python manage.py seed_dtr_data --employee 000000037
    
    # Clear April only
    python manage.py seed_dtr_data --clear-month 2026-04

    # Clear April then re-seed April
    python manage.py seed_dtr_data --clear-month 2026-04 --month 2026-04

    # Clear April for one employee only then re-seed
    python manage.py seed_dtr_data --clear-month 2026-04 --month 2026-04 --employee 000000088
"""

import random
from datetime import date, timedelta
from calendar import monthrange

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.employees.models import Employee
from apps.dtr.models import DTRRecord
from apps.dtr.engine import compute_dtr_day, apply_dtr_record, get_effective_schedule

# ── Philippine holidays 2025-2026 ─────────────────────────────────────────────
PH_HOLIDAYS = {
    # 2025
    date(2025, 1, 1):   ('New Year\'s Day',             'regular'),
    date(2025, 4, 9):   ('Araw ng Kagitingan',          'regular'),
    date(2025, 4, 17):  ('Maundy Thursday',             'regular'),
    date(2025, 4, 18):  ('Good Friday',                 'regular'),
    date(2025, 5, 1):   ('Labor Day',                   'regular'),
    date(2025, 6, 12):  ('Independence Day',            'regular'),
    date(2025, 8, 25):  ('National Heroes Day',         'regular'),
    date(2025, 11, 1):  ('All Saints Day',              'special'),
    date(2025, 11, 30): ('Bonifacio Day',               'regular'),
    date(2025, 12, 8):  ('Immaculate Conception',       'special'),
    date(2025, 12, 25): ('Christmas Day',               'regular'),
    date(2025, 12, 30): ('Rizal Day',                   'regular'),
    date(2025, 12, 31): ('Last Day of the Year',        'special'),
    # 2026
    date(2026, 1, 1):   ('New Year\'s Day',             'regular'),
    date(2026, 4, 2):   ('Maundy Thursday',             'regular'),
    date(2026, 4, 3):   ('Good Friday',                 'regular'),
    date(2026, 4, 9):   ('Araw ng Kagitingan',          'regular'),
    date(2026, 5, 1):   ('Labor Day',                   'regular'),
    date(2026, 6, 12):  ('Independence Day',            'regular'),
    date(2026, 8, 31):  ('National Heroes Day',         'regular'),
    date(2026, 11, 1):  ('All Saints Day',              'special'),
    date(2026, 11, 30): ('Bonifacio Day',               'regular'),
    date(2026, 12, 25): ('Christmas Day',               'regular'),
    date(2026, 12, 30): ('Rizal Day',                   'regular'),
}


# ── Time helpers ──────────────────────────────────────────────────────────────

def _rtime(base_hour: int, base_min: int, jitter: int = 15) -> str:
    """Return HH:MM string with ±jitter minutes of randomness."""
    delta = random.randint(-2, jitter)
    total = base_hour * 60 + base_min + delta
    total = max(0, min(total, 23 * 60 + 59))
    return f'{total // 60:02d}:{total % 60:02d}'


def _maybe_none(val, prob_missing: float = 0.05):
    """Return None with probability prob_missing, else return val."""
    return None if random.random() < prob_missing else val


def _day_type(d: date) -> str:
    """Classify a date for seeding purposes."""
    if d.weekday() >= 5:
        return 'weekend'
    if d in PH_HOLIDAYS:
        return 'holiday'
    r = random.random()
    if r < 0.03:
        return 'absent'
    if r < 0.055:
        return 'travel'
    if r < 0.075:
        return 'leave'
    return 'regular'


# ── Per-schedule-type seed logic ─────────────────────────────────────────────

def _seed_regular_day_fixed(employee, d: date, sched_ctx: dict) -> dict:
    """Seed a regular workday for a fixed-schedule employee."""
    profile = employee.employee_id % 4

    # Get expected times from schedule
    am_in_exp  = sched_ctx.get('flex_start_latest')   # for fixed, this IS 8:00
    am_out_exp = sched_ctx.get('am_out_expected')
    pm_in_exp  = sched_ctx.get('pm_in_expected')
    pm_out_exp = sched_ctx.get('pm_out_expected')

    ah = am_in_exp.hour  if am_in_exp  else 8
    am = am_in_exp.minute if am_in_exp else 0
    ouh = am_out_exp.hour  if am_out_exp else 12
    pih = pm_in_exp.hour   if pm_in_exp  else 13
    poh = pm_out_exp.hour  if pm_out_exp else 17

    if profile == 0:  # punctual
        am_in  = _rtime(ah - 1, 55, 5)
        am_out = _rtime(ouh, 0, 3)
        pm_in  = _rtime(pih, 0, 5)
        pm_out = _rtime(poh, 0, 30)
    elif profile == 1:  # sometimes late
        am_in  = _rtime(ah, 0, 20)
        am_out = _rtime(ouh, 0, 3)
        pm_in  = _rtime(pih, 0, 10)
        pm_out = _rtime(poh, 0, 10)
    elif profile == 2:  # often late
        am_in  = _rtime(ah, 10, 30)
        am_out = _rtime(ouh, -10, 5)
        pm_in  = _rtime(pih, 5, 15)
        pm_out = _rtime(poh, -15, 10)
    else:  # mixed
        am_in  = _rtime(ah, 0, 25)
        am_out = _rtime(ouh, 0, 5)
        pm_in  = _rtime(pih, 0, 12)
        pm_out = _maybe_none(_rtime(poh, 0, 5), 0.08)

    return compute_dtr_day(
        dtr_date=d,
        am_in_str=am_in, am_out_str=am_out,
        pm_in_str=pm_in, pm_out_str=pm_out,
        schedule=sched_ctx,
    )


def _seed_regular_day_flexible(employee, d: date, sched_ctx: dict) -> dict:
    """Seed a regular workday for a flexible-schedule employee."""
    flex_e = sched_ctx.get('flex_start_earliest')
    flex_l = sched_ctx.get('flex_start_latest')
    hrs    = sched_ctx.get('working_hours_per_day', 10.0)

    # Random arrival within or slightly after flex window
    e_min  = (flex_e.hour * 60 + flex_e.minute) if flex_e else 420
    l_min  = (flex_l.hour * 60 + flex_l.minute) if flex_l else 480
    # 80% on-time within window, 20% slightly late
    if random.random() < 0.8:
        in_min = random.randint(e_min, l_min)
    else:
        in_min = l_min + random.randint(5, 25)

    # Required out = in + working_hours + 60 (lunch)
    req_out = in_min + int(hrs * 60) + 60
    # Actual out: 70% on time or OT, 30% early (undertime)
    if random.random() < 0.7:
        out_min = req_out + random.randint(0, 20)
    else:
        out_min = req_out - random.randint(5, 30)

    am_out_exp = sched_ctx.get('am_out_expected')
    pm_in_exp  = sched_ctx.get('pm_in_expected')

    ouh = am_out_exp.hour if am_out_exp else 12
    pih = pm_in_exp.hour  if pm_in_exp  else 13

    am_in  = f'{in_min // 60:02d}:{in_min % 60:02d}'
    am_out = _maybe_none(_rtime(ouh, 0, 3), 0.15)  # 15% miss AM out
    pm_in  = _maybe_none(_rtime(pih, 0, 5), 0.15)  # 15% miss PM in
    pm_out = f'{out_min // 60 % 24:02d}:{out_min % 60:02d}'

    return compute_dtr_day(
        dtr_date=d,
        am_in_str=am_in, am_out_str=am_out,
        pm_in_str=pm_in, pm_out_str=pm_out,
        schedule=sched_ctx,
    )


def _seed_regular_day_free(employee, d: date, sched_ctx: dict) -> dict:
    """
    Free schedule — just record some scans.
    No deductions regardless of times.
    Some days employees scan all 4, some scan only in/out.
    """
    in_min  = random.randint(7 * 60, 9 * 60)    # 7AM–9AM
    out_min = in_min + random.randint(8 * 60, 11 * 60)  # 8–11hrs later

    am_in  = f'{in_min // 60:02d}:{in_min % 60:02d}'
    pm_out = f'{out_min // 60 % 24:02d}:{out_min % 60:02d}'
    # Middle scans sometimes missing for free employees
    am_out = _maybe_none(_rtime(12, 0, 10), 0.3)
    pm_in  = _maybe_none(_rtime(13, 0, 10), 0.3)

    return compute_dtr_day(
        dtr_date=d,
        am_in_str=am_in, am_out_str=am_out,
        pm_in_str=pm_in, pm_out_str=pm_out,
        schedule=sched_ctx,
    )


# ── Main per-employee per-month seeder ────────────────────────────────────────

def _seed_employee_month(employee, year: int, month: int) -> tuple[int, int]:
    last_day = monthrange(year, month)[1]
    created_count = 0
    skipped_count = 0

    # Use first-of-month to resolve schedule (stable for the month)
    month_start = date(year, month, 1)
    sched_ctx   = get_effective_schedule(employee, month_start)
    is_flexible = sched_ctx.get('is_flexible', False)
    is_free     = sched_ctx.get('is_free', False)

    for day in range(1, last_day + 1):
        d = date(year, month, day)
        day_type = _day_type(d)

        # ── Weekend ──────────────────────────────────────────────────────────
        if day_type == 'weekend':
            computed = compute_dtr_day(dtr_date=d, is_restday=True)
            _, created = apply_dtr_record(employee, computed)
            if created:
                created_count += 1
            continue

        # ── Holiday ──────────────────────────────────────────────────────────
        if day_type == 'holiday':
            holiday_name, holiday_type = PH_HOLIDAYS[d]
            computed = compute_dtr_day(
                dtr_date=d,
                is_holiday=True,
                holiday_type=holiday_type,
                remarks=holiday_name,
            )
            _, created = apply_dtr_record(employee, computed)
            if created:
                created_count += 1
            continue

        # ── Absent ───────────────────────────────────────────────────────────
        if day_type == 'absent':
            computed = compute_dtr_day(dtr_date=d, schedule=sched_ctx)
            _, created = apply_dtr_record(employee, computed)
            if created:
                created_count += 1
            continue

        # ── Travel Order ─────────────────────────────────────────────────────
        if day_type == 'travel':
            to_num = random.randint(1000, 9999)
            computed = compute_dtr_day(
                dtr_date=d,
                am_in_str='08:00', am_out_str='12:00',
                pm_in_str='13:00', pm_out_str='17:00',
                am_in_override='to', am_out_override='to',
                pm_in_override='to', pm_out_override='to',
                remarks=f'TO#{year}-{month:02d}-{to_num}HR',
                schedule=sched_ctx,
            )
            _, created = apply_dtr_record(employee, computed)
            if created:
                created_count += 1
            continue

        # ── Leave ─────────────────────────────────────────────────────────────
        if day_type == 'leave':
            leave_type = random.choice(['Sick Leave', 'Vacation Leave', 'Special Leave'])
            computed = compute_dtr_day(
                dtr_date=d,
                am_in_override='leave', am_out_override='leave',
                pm_in_override='leave', pm_out_override='leave',
                remarks=leave_type,
                schedule=sched_ctx,
            )
            _, created = apply_dtr_record(employee, computed)
            if created:
                created_count += 1
            continue

        # ── Regular workday — route by schedule type ──────────────────────────
        if is_free:
            computed = _seed_regular_day_free(employee, d, sched_ctx)
        elif is_flexible:
            computed = _seed_regular_day_flexible(employee, d, sched_ctx)
        else:
            computed = _seed_regular_day_fixed(employee, d, sched_ctx)

        _, created = apply_dtr_record(employee, computed)
        if created:
            created_count += 1
        else:
            skipped_count += 1

    return created_count, skipped_count


# ── Management command ────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        'Seed DTR records for all active employees. '
        'Schedule-aware: uses each employee\'s effective schedule.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--months', type=int, default=3,
            help='Number of recent months to seed (default: 3)',
        )
        parser.add_argument(
            '--month', type=str, default='',
            help='Seed a specific month only, YYYY-MM format',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete all existing DTR records before seeding',
        )
        parser.add_argument(
            '--employee', type=str, default='',
            help='Seed only this employee by id_number',
        )
        parser.add_argument(
            '--clear-month', type=str, default='',
            help='Clear DTR records for a specific month only, YYYY-MM format',
        )

    def handle(self, *args, **options):
        verbosity = options['verbosity']

        if options['clear']:
            count = DTRRecord.objects.count()
            DTRRecord.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'Cleared {count} existing DTR records.')
            )

        # Determine months to seed
        today = timezone.now().date()

        if options['month']:
            try:
                y, m = options['month'].split('-')
                months = [(int(y), int(m))]
            except ValueError:
                self.stderr.write('Invalid --month format. Use YYYY-MM.')
                return
        else:
            n = options['months']
            months = []
            cur = today.replace(day=1)
            for _ in range(n):
                months.insert(0, (cur.year, cur.month))
                cur = (cur - timedelta(days=1)).replace(day=1)

        # Get employees
        if options['employee']:
            employees = Employee.objects.filter(
                id_number=options['employee'], status='active'
            ).select_related(
                'division', 'division__default_schedule',
                'unit', 'unit__default_schedule',
                'unit__parent_unit', 'unit__parent_unit__default_schedule',
            )
            if not employees.exists():
                self.stderr.write(
                    f'Employee id_number={options["employee"]} not found or not active.'
                )
                return
        else:
            employees = Employee.objects.filter(status='active').select_related(
                'division', 'division__default_schedule',
                'unit', 'unit__default_schedule',
                'unit__parent_unit', 'unit__parent_unit__default_schedule',
            ).order_by('last_name', 'first_name')

        if options['clear_month']:
            try:
                y, m = options['clear_month'].split('-')
                y, m = int(y), int(m)
                last_day = monthrange(y, m)[1]
                deleted, _ = DTRRecord.objects.filter(
                    dtr_date__range=(date(y, m, 1), date(y, m, last_day))
                ).delete()
                self.stdout.write(
                    self.style.WARNING(f'Cleared {deleted} DTR records for {options["clear_month"]}.')
                )
            except ValueError:
                self.stderr.write('Invalid --clear-month format. Use YYYY-MM.')
                return

        emp_count     = employees.count()
        total_created = 0
        total_skipped = 0

        self.stdout.write(
            f'\nSeeding DTR for {emp_count} employee(s) '
            f'across {len(months)} month(s)...\n'
        )

        for year, month in months:
            label = date(year, month, 1).strftime('%B %Y')
            self.stdout.write(f'  ── {label} ──')

            for emp in employees:
                created, skipped = _seed_employee_month(emp, year, month)
                total_created += created
                total_skipped += skipped

                if verbosity >= 2:
                    # Resolve schedule for display
                    sched_ctx = get_effective_schedule(emp, date(year, month, 1))
                    sched_type = (
                        'free' if sched_ctx.get('is_free') else
                        'flex' if sched_ctx.get('is_flexible') else
                        'fixed'
                    )
                    self.stdout.write(
                        f'    [{sched_type:5s}] {emp.get_full_name():<40} '
                        f'created={created} skipped={skipped}'
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. Created {total_created} records, '
                f'skipped {total_skipped} existing.'
            )
        )