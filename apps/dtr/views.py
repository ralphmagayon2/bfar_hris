"""
apps/dtr/views.py

BFAR HRIS Region III - Daily time record views

"""

from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from datetime import date, timedelta, time
from calendar import monthrange
import datetime as dt_module
import pytz

from apps.employees.models import Employee
from apps.dtr.models import DTRRecord
from apps.dtr.engine import compute_dtr_day, apply_dtr_record, get_effective_schedule
from apps.accounts.views import login_required, admin_required, role_required
from apps.audit.models import create_audit_log
from apps.accounts.utils import get_client_ip

PH_TZ = pytz.timezone('Asia/Manila')

# Expected times in minutes-since-midnight (PH local)
_SLOT_EXPECTED = {
    'am_in': 8 * 60, # 8:00
    'am_out': 12 * 60, # 12:00
    'pm_in': 13 * 60, # 13:00
    'pm_out': 17 * 60, # 17:00
}

def _slot_sublabel(slot: str, aware_dt, sched_ctx: dict) -> str:
    """
    Return a short sub-label for a single biometric slot.
    slot: 'am_in' | 'am_out' | 'pm_in' | 'pm_out'
    aware_dt: timezone-aware datetime or None

    Schedule-aware: uses flex window for am_in if is_flexible
    """
    # Free Schedule - no sub-labels, always on time
    if sched_ctx.get('is_free', False):
        return 'on-time' if aware_dt else 'missing'
    
    is_flexible = sched_ctx.get('is_flexible', False)
    working_hours_per_day = sched_ctx.get('working_hours_per_day', 8.0)
    flex_start_latest = sched_ctx.get('flex_start_latest', time(8, 0))

    if aware_dt is None:
        return 'missing'
    
    local = aware_dt.astimezone(PH_TZ)
    actual_min = local.hour * 60 + local.minute
    
    if slot == 'am_in':
        if is_flexible:
            # No penalty within the flex window
            latest_min = flex_start_latest.hour * 60 + flex_start_latest.minute
            diff = actual_min - latest_min
            return f'+{diff} min late' if diff > 0 else 'on-time'
        else:
            diff = actual_min - _SLOT_EXPECTED['am_in']
            return f'+{diff} min late' if diff > 0 else 'on-time'

    elif slot == 'am_out':
        expected = sched_ctx.get('am_out_expected', time(12, 0))
        exp_min = expected.hour * 60 + expected.minute
        diff = exp_min - actual_min
        return f'-{diff} min early' if diff > 0 else 'on-time'
    
    elif slot == 'pm_in':
        expected = sched_ctx.get('pm_in_expected', time(13, 0))
        exp_min = expected.hour * 60 + expected.minute
        diff = actual_min - exp_min
        return f'+{diff} min late' if diff > 0 else 'on-time'
    
    elif slot == 'pm_out':
        if is_flexible:
            # Sub-label shows how far from their personal required out
            # We need am_in to compute this handled seperately via required_out_str
            return 'on-time'
        expected = sched_ctx.get('pm_out_expected', time(17, 0))
        exp_min = expected.hour * 60 + expected.minute
        diff = exp_min - actual_min
        return f'-{diff} min early' if diff > 0 else 'on-time'

    return ''

# ------ DATE HELPERS -------

def _ph_today() -> date:
    return timezone.now().astimezone(PH_TZ).date()


def _parse_date(raw: str, fallback: date) -> date:
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        return fallback


def _parse_month(raw: str, fallback: date) -> date:
    try:
        year, month = raw.split('-')
        return date(int(year), int(month), 1)
    except (TypeError, ValueError, AttributeError):
        return fallback.replace(day=1)
    
def _ph_time_str(aware_dt) -> str | None:
    """Extract HH:MM string from aware datetime in PH timezone."""
    if not aware_dt:
        return None
    return aware_dt.astimezone(PH_TZ).strftime('%I:%M %p') # Before it's %H:%M


# STATUS HELPERS (shared with templates)
STATUS_CHOICES = [
    ('present', 'Present'),
    ('late',    'Late'),
    ('absent',  'Absent'),
    ('to',      'Travel Order'),
    ('tt',      'Trip Ticket'),
    ('leave',   'Leave'),
    ('holiday', 'Holiday'),
]

def _derive_display_status(rec: DTRRecord) -> str:
    """Derive a single summary status string for list/summary display."""
    if rec.is_holiday:
        return 'holiday'
    if rec.am_in_status == 'leave' or rec.pm_in_status == 'leave':
        return 'leave'
    if rec.am_in_status in ('to', 'tt') or rec.pm_in_status in ('to', 'tt'):
        return 'on_travel'
    if rec.is_half_day_absent():
        return 'halfday'
    # if rec.minutes_late and rec.minutes_late > 0:
    #     return 'late'
    if rec.am_in_status == 'absent' and rec.pm_in_status == 'absent':
        return 'absent'
    if rec.am_in is None and rec.pm_in is None:
        return 'absent'
    return 'present'

def _flex_required_out_str(am_in_dt, working_hours: float = 10.0) -> str:
    """Given an aware am_in datetime, return the required out time string (PH time). Only meaningful for flexible schedules.
    """
    if not am_in_dt:
        return ''
    local    = am_in_dt.astimezone(PH_TZ)
    in_min   = local.hour * 60 + local.minute
    out_min  = in_min + int(working_hours * 60) + 60   # +60 lunch
    h        = (out_min // 60) % 24
    m        = out_min % 60
    suffix   = 'AM' if h < 12 else 'PM'
    h12      = h % 12 or 12
    return f'{h12}:{m:02d} {suffix}'

# VIEW 1 — dtr_list
# HR staff/admin: see all employees for a date or month.
# Viewer: redirected to their own detail page.

@login_required
def dtr_list(request):      
    # Viewers only see their own records
    current_user = request.current_user
    if current_user.role == 'viewer':
        if current_user.employee:
            return redirect('dtr:detail', emp_id=current_user.employee.employee_id)
        messages.warning(request, 'Your account is not linked to an employee record. Contact HR.')
        return redirect('core:dashboard')
 
    today = _ph_today()
    raw_date  = request.GET.get('date', '')
    raw_month = request.GET.get('month', '')
 
    if raw_month:
        selected_month = _parse_month(raw_month, today)
        selected_date  = None
        last_day = monthrange(selected_month.year, selected_month.month)[1]
        qs = DTRRecord.objects.filter(
            dtr_date__range=(selected_month, selected_month.replace(day=last_day))
        ).select_related(
            'employee', 
            'employee__division', 
            'employee__division__default_schedule',
            'employee__unit',
            'employee__unit__default_schedule',
            'employee__position',
        )
    else:
        selected_date  = _parse_date(raw_date, today)
        selected_month = None
        qs = DTRRecord.objects.filter(
            dtr_date=selected_date
        ).select_related(
            'employee', 
            'employee__division', 
            'employee__division__default_schedule',
            'employee__unit',
            'employee__unit__default_schedule',
            'employee__position',
        )
 
    qs = qs.order_by('employee__last_name', 'employee__first_name')
 
    summary = {
        'present': 0, 'absent': 0, # 'late': 0,
        'on_travel': 0, 'on_leave': 0, 'holiday': 0, 'halfday': 0,
    }
    records_list = list(qs)
    for rec in records_list:
        rec.date = rec.dtr_date

        if rec.date.weekday() >= 5:
            rec.is_restday = True

        rec.status = _derive_display_status(rec)
        rec.undertime_minutes = int((rec.hours_undertime or 0) * 60)
        key = rec.status
        if key == 'leave':
            summary['on_leave'] += 1
        elif key in summary:
            summary[key] += 1

        # Sub-labels — skip for rest/holiday/leave rows
        if rec.status not in ('restday', 'holiday', 'leave'):
            # Resolved schedule per employee since this is a multi-employee list
            rec_sched = get_effective_schedule(rec.employee, rec.dtr_date)

            rec.sub_am_in  = _slot_sublabel('am_in',  rec.am_in, rec_sched)
            rec.sub_am_out = _slot_sublabel('am_out', rec.am_out, rec_sched)
            rec.sub_pm_in  = _slot_sublabel('pm_in',  rec.pm_in, rec_sched)
            rec.sub_pm_out = _slot_sublabel('pm_out', rec.pm_out, rec_sched)
        else:
            rec.sub_am_in = rec.sub_am_out = rec.sub_pm_in = rec.sub_pm_out = ''

        # PH-localized time strings (fix the UTC display bug)
        rec.ph_am_in  = _ph_time_str(rec.am_in)
        rec.ph_am_out = _ph_time_str(rec.am_out)
        rec.ph_pm_in  = _ph_time_str(rec.pm_in)
        rec.ph_pm_out = _ph_time_str(rec.pm_out)
 
    paginator   = Paginator(records_list, 30)
    dtr_records = paginator.get_page(request.GET.get('page', 1))
 
    return render(request, 'dtr/list.html', {
        'today':          today,
        'selected_date':  selected_date,
        'selected_month': selected_month,
        'dtr_records':    dtr_records,
        'summary':        summary,
    })


# VIEW 2 — dtr_detail
# Monthly DTR for one employee.
# Viewer: only their own employee_id is permitted.

@login_required
def dtr_detail(request, emp_id):
    today    = _ph_today()

    # viewer access control
    current_user = request.current_user
    if current_user.role == 'viewer':
        if not current_user.employee or current_user.employee.employee_id != emp_id:
            messages.error(request, 'You can only view your own DTR records.')
            return redirect('core:dashboard')

    employee = get_object_or_404(
        Employee.objects.select_related('division', 'unit', 'position'),
        employee_id=emp_id
    )

    raw_month      = request.GET.get('month', '')
    selected_month = _parse_month(raw_month, today)
    last_day       = monthrange(selected_month.year, selected_month.month)[1]

    # Prev/next month navigation
    first_of_prev = (selected_month - timedelta(days=1)).replace(day=1)
    first_of_next = (selected_month.replace(day=last_day) + timedelta(days=1)).replace(day=1)
    prev_month    = first_of_prev.strftime('%Y-%m')
    next_month    = first_of_next.strftime('%Y-%m')

    qs = DTRRecord.objects.filter(
        employee=employee,
        dtr_date__range=(selected_month, selected_month.replace(day=last_day))
    ).order_by('dtr_date')

    records_list = list(qs)
    month_summary = {'present': 0, 'absent': 0, 'late': 0, 'undertime_hours': 0.0, 'on_travel': 0, 'on_leave': 0, 'holidays': 0}

    # This is new - resolve the employees effective schedule for month
    sched_ctx = get_effective_schedule(employee, selected_month)
    is_flexible = sched_ctx['is_flexible']
    working_hrs = sched_ctx['working_hours_per_day']

    for rec in records_list:
        rec.date = rec.dtr_date
        rec.is_late = (rec.minutes_late or 0) > 0
        rec.late_minutes = rec.minutes_late or 0
        rec.undertime_minutes = int((rec.hours_undertime or 0) * 60)

        # Automaticall tag Saturdays(5) and Sundays (6) as restday
        if rec.date.weekday() >= 5:
            rec.is_restday = True

        if rec.is_restday:
            rec.status = 'restday'
        elif rec.is_holiday:
            rec.status = 'holiday'
        elif rec.am_in_status == 'leave' or rec.pm_in_status == 'leave':
            rec.status = 'leave'
        elif rec.am_in_status in ('to', 'tt') or rec.pm_in_status in ('to', 'tt'):
            rec.status = 'to'
        elif rec.is_half_day_absent():
            rec.status = 'halfday'
        elif rec.am_in is None and rec.pm_in is None:
            rec.status = 'absent'
        else:
            rec.status = 'present'

        # Sub-labels and PH time strings
        rec.ph_am_in = _ph_time_str(rec.am_in)
        rec.ph_am_out = _ph_time_str(rec.am_out)
        rec.ph_pm_in = _ph_time_str(rec.pm_in)
        rec.ph_pm_out = _ph_time_str(rec.pm_out)

        # Sub-labels — skip for rest/holiday/leave rows
        if rec.status not in ('restday', 'holiday', 'leave'):
            rec.sub_am_in  = _slot_sublabel('am_in',  rec.am_in, sched_ctx)
            rec.sub_am_out = _slot_sublabel('am_out', rec.am_out, sched_ctx)
            rec.sub_pm_in  = _slot_sublabel('pm_in',  rec.pm_in, sched_ctx)
            rec.sub_pm_out = _slot_sublabel('pm_out', rec.pm_out, sched_ctx)
        else:
            rec.sub_am_in = rec.sub_am_out = rec.sub_pm_in = rec.sub_pm_out = ''

        # For flexible schedules, show the required out time in the PM Out cell
        rec.required_out_str = (
            _flex_required_out_str(rec.am_in, working_hrs)
            if is_flexible else ''
        )

        # This is for summary counting 
        if rec.status == 'present':   month_summary['present']   += 1
        elif rec.status == 'absent':  month_summary['absent']    += 1
        elif rec.status == 'to':      month_summary['on_travel'] += 1
        elif rec.status == 'leave':   month_summary['on_leave']  += 1
        elif rec.status == 'holiday': month_summary['holidays']  += 1
        month_summary['undertime_hours'] += float(rec.hours_undertime or 0)

    month_summary['undertime_hours'] = round(month_summary['undertime_hours'], 2)

    # Is viewer role? Hides edit/add buttons in template
    is_viewer = (current_user.role == 'viewer')

    return render(request, 'dtr/detail.html', {
        'today':          today,
        'employee':       employee,
        'selected_month': selected_month,
        'prev_month':     prev_month,
        'next_month':     next_month,
        'dtr_records':    records_list,
        'month_summary':  month_summary,
        'is_flexible': is_flexible,
        'working_hrs': working_hrs,
        'is_viewer': is_viewer,
    })


# VIEW 3 — dtr_edit
# Correct time entries on an existing DTR records,
# HR staff, HR admin, superadmin only.

# @login_required
# def dtr_edit(request, dtr_id):
#     dtr = get_object_or_404(
#         DTRRecord.objects.select_related(
#             'employee', 'employee__division', 'employee__position'
#         ),
#         dtr_id=dtr_id
#     )

#     slot_statuses = [
#         ('AM Time-In Status',  'am_in_status',  dtr.am_in_status),
#         ('AM Time-Out Status', 'am_out_status', dtr.am_out_status),
#         ('PM Time-In Status',  'pm_in_status',  dtr.pm_in_status),
#         ('PM Time-Out Status', 'pm_out_status', dtr.pm_out_status),
#     ]

#     ph_tz = pytz.timezone('Asia/Manila')

#     def _fmt_time(dt):
#         if not dt:
#             return None
#         return dt.astimezone(ph_tz).strftime('%I:%M %p')

#     original_values = [
#         ('AM In',    _fmt_time(dtr.am_in)),
#         ('AM Out',   _fmt_time(dtr.am_out)),
#         ('PM In',    _fmt_time(dtr.pm_in)),
#         ('PM Out',   _fmt_time(dtr.pm_out)),
#         ('Remarks',  dtr.remarks),
#     ]

#     if request.method == 'POST':
#         reason = request.POST.get('reason', '').strip()

#         if dtr.is_locked and not reason:
#             messages.error(request, 'A reason for correction is required for locked records.')
#             return render(request, 'dtr/form.html', {
#                 'dtr':             dtr,
#                 'today':           _ph_today(),
#                 'status_choices':  STATUS_CHOICES,
#                 'slot_statuses':   slot_statuses,
#                 'original_values': original_values,
#             })

#         # Snapshot for audit log
#         old_snapshot = {
#             'am_in': str(dtr.am_in), 'am_out': str(dtr.am_out),
#             'pm_in': str(dtr.pm_in), 'pm_out': str(dtr.pm_out),
#             'am_in_status': dtr.am_in_status, 'am_out_status': dtr.am_out_status,
#             'pm_in_status': dtr.pm_in_status, 'pm_out_status': dtr.pm_out_status,
#             'remarks': dtr.remarks,
#         }

#         def _combine(time_str):
#             if not time_str:
#                 return None
#             try:
#                 h, m = map(int, time_str.split(':'))
#                 naive = dt_module.datetime.combine(dtr.dtr_date, dt_module.time(h, m))
#                 return ph_tz.localize(naive)
#             except (ValueError, AttributeError):
#                 return None

#         dtr.am_in  = _combine(request.POST.get('am_in', '').strip())
#         dtr.am_out = _combine(request.POST.get('am_out', '').strip())
#         dtr.pm_in  = _combine(request.POST.get('pm_in', '').strip())
#         dtr.pm_out = _combine(request.POST.get('pm_out', '').strip())

#         valid_statuses = {v for v, _ in STATUS_CHOICES}
#         for _, field, _ in slot_statuses:
#             val = request.POST.get(field, '').strip()
#             setattr(dtr, field, val if val in valid_statuses else None)

#         dtr.remarks = request.POST.get('remarks', '').strip() or None

#         # Recompute minutes late (no grace period — any scan after 08:00 is late)
        
#         computed = compute_dtr_day(
#             dtr_date    = dtr.dtr_date,
#             am_in_str   = _ph_time_str(dtr.am_in),
#             am_out_str  = _ph_time_str(dtr.am_out),
#             pm_in_str   = _ph_time_str(dtr.pm_in),
#             pm_out_str  = _ph_time_str(dtr.pm_out),
#             is_holiday  = dtr.is_holiday,
#             is_restday  = dtr.is_restday,
#             holiday_type= dtr.holiday_type,
#             remarks     = dtr.remarks,
#             am_in_override  = dtr.am_in_status,
#             am_out_override = dtr.am_out_status,
#             pm_in_override  = dtr.pm_in_status,
#             pm_out_override = dtr.pm_out_status,
#         )

#         dtr.minutes_late       = computed['minutes_late']
#         dtr.hours_undertime    = computed['hours_undertime']
#         dtr.hours_overtime     = computed['hours_overtime']
#         dtr.total_hours_worked = computed['total_hours_worked']
#         dtr.save()

#         # Audit log
#         try:
#             new_snapshot = {
#                 'am_in': str(dtr.am_in), 'am_out': str(dtr.am_out),
#                 'pm_in': str(dtr.pm_in), 'pm_out': str(dtr.pm_out),
#                 'minutes_late': dtr.minutes_late,
#                 'hours_undertime': str(dtr.hours_undertime),
#             }
#             create_audit_log(
#                 table_affected='dtr_records',
#                 record_id=dtr.dtr_id,
#                 action='update',
#                 performed_by=request.current_user,
#                 old_value=old_snapshot,
#                 new_value=new_snapshot,
#                 ip_address=get_client_ip(request),
#                 description=reason or None,
#             )
#         except Exception:
#             pass

#         messages.success(
#             request, 
#             f'DTR record for {dtr.dtr_date.strftime("%B %d, %Y")} updated successfully.',
#             f'Late: {dtr.minutes_late} min, Undertime: {dtr.hours_undertime} hrs.',
#         )
#         return redirect('dtr:detail', emp_id=dtr.employee.employee_id)

#     return render(request, 'dtr/form.html', {
#         'dtr':             dtr,
#         'today':           _ph_today(),
#         'status_choices':  STATUS_CHOICES,
#         'slot_statuses':   slot_statuses,
#         'original_values': original_values,
#     })


# VIEW 4 — dtr_print

def dtr_print(request, emp_id):
    today    = _ph_today()
    employee = get_object_or_404(Employee, employee_id=emp_id)

    raw_month      = request.GET.get('month', '')
    selected_month = _parse_month(raw_month, today)
    last_day       = monthrange(selected_month.year, selected_month.month)[1]

    dtr_records = list(DTRRecord.objects.filter(    # ← cast to list so we can iterate twice
        employee=employee,
        dtr_date__range=(selected_month, selected_month.replace(day=last_day))
    ).order_by('dtr_date'))

    # same totals block as my_dtr_print
    total_late_min   = sum(r.minutes_late or 0 for r in dtr_records)
    total_undertime  = sum(float(r.hours_undertime or 0) for r in dtr_records)
    total_hrs_worked = sum(float(r.total_hours_worked or 0) for r in dtr_records)
    days_present     = sum(1 for r in dtr_records if r.am_in is not None and not r.is_holiday)
    days_absent      = sum(1 for r in dtr_records if r.am_in is None and not r.is_holiday and not r.is_restday)

    # AUDIT LOG: Track HR printing an employee's DTR
    try:
        create_audit_log(
            table_affected='dtr_records',
            record_id=employee.employee_id,
            action='print',
            performed_by=request.current_user,
            ip_address=get_client_ip(request),
            description=f'{request.current_user.username} printed DTR for {employee.get_full_name()} (Month: {selected_month.strftime("%B %Y")}).'
        )
    except Exception:
        pass

    return render(request, 'dtr/print_dtr.html', {
        'today':           today,
        'employee':        employee,
        'selected_month':  selected_month,
        'dtr_records':     dtr_records,
        'total_late_min':  total_late_min,
        'total_undertime': round(total_undertime, 2),
        'total_hrs_worked':round(total_hrs_worked, 2),
        'days_present':    days_present,
        'days_absent':     days_absent,
    })

@login_required
@role_required('superadmin', 'hr_admin', 'hr_staff')
def dtr_manual_entry(request, emp_id):
    """
    HR manually enters DTR for one employee for one day.
    Used when biometric device is offline or employee forgot to scan.
    Engine recomputes all deductions on save.
    HR Staff, HR Admin, superadmin only
    """
    today    = _ph_today()
    employee = get_object_or_404(
        Employee.objects.select_related('division', 'unit', 'position'),
        employee_id=emp_id
    )

    # Pre-fill date from query param (e.g. clicking from list)
    initial_date = _parse_date(request.GET.get('date', ''), today)
    sched_ctx = get_effective_schedule(employee, initial_date)

    if request.method == 'POST':
        p = request.POST

        raw_date   = p.get('dtr_date', '').strip()
        dtr_date   = _parse_date(raw_date, today)

        post_sched_ctx = get_effective_schedule(employee, dtr_date)

        am_in_str  = p.get('am_in',  '').strip() or None
        am_out_str = p.get('am_out', '').strip() or None
        pm_in_str  = p.get('pm_in',  '').strip() or None
        pm_out_str = p.get('pm_out', '').strip() or None
        is_holiday = p.get('is_holiday') == '1'
        is_restday = p.get('is_restday') == '1'
        holiday_type = p.get('holiday_type', '').strip() or None
        remarks      = p.get('remarks', '').strip() or None
        reason     = p.get('reason', '').strip() or None

        # Per-slot overrides from HR
        valid_statuses = {v for v, _ in STATUS_CHOICES}
        def _ov(key):
            v = p.get(key, '').strip()
            return v if v in valid_statuses else None

        computed = compute_dtr_day(
            dtr_date=dtr_date,
            am_in_str=am_in_str, 
            am_out_str=am_out_str,
            pm_in_str=pm_in_str, 
            pm_out_str=pm_out_str,
            is_holiday=is_holiday, 
            is_restday=is_restday,
            holiday_type=holiday_type, 
            remarks=remarks,
            am_in_override = _ov('am_in_status'),
            am_out_override = _ov('am_out_status'),
            pm_in_override = _ov('pm_in_status'),
            pm_out_override = _ov('pm_out_status'),
            schedule=post_sched_ctx,
        )

        record, created = apply_dtr_record(employee, computed)

        # Audit log
        try:
            create_audit_log(
                table_affected='dtr_records',
                record_id=record.dtr_id,
                action='create' if created else 'update',
                performed_by=request.current_user,
                new_value={
                    'dtr_date':      str(dtr_date),
                    'am_in':         am_in_str,
                    'am_out':        am_out_str,
                    'pm_in':         pm_in_str,
                    'pm_out':        pm_out_str,
                    'minutes_late':  computed['minutes_late'],
                    'hours_undertime': str(computed['hours_undertime']),
                    'manual_entry':  True,
                },
                ip_address=get_client_ip(request),
                description=(
                    f'Manual DTR entry for {employee.get_full_name()} on {dtr_date}.'
                    + (f' Reason: {reason}' if reason else '')
                ),
            )
        except Exception:
            pass

        action = 'created' if created else 'updated'
        messages.success(
            request,
            f'DTR for {employee.get_full_name()} on {dtr_date.strftime("%B %d, %Y")} {action}. '
            f'Late: {computed["minutes_late"]} min, Undertime: {computed["hours_undertime"]} hrs.'
        )
        return redirect('dtr:detail', emp_id=emp_id)

    # Pre-fill from existing record on the initial date (if any)
    existing = None
    try:
        existing = DTRRecord.objects.get(employee=employee, dtr_date=initial_date)
    except Exception:
        pass

    def _fmt_ph_time(dt):
        """Return HH:MM in PH time for pre-filling <input type='time'>."""
        if not dt:
            return ''
        return dt.astimezone(PH_TZ).strftime('%H:%M') # Fixed

    # Pass pre-filled time strings directly to context so the template
    # doesn't rely on the |time filter (which outputs UTC on aware datetimes)
    prefill = {
        'am_in':  _fmt_ph_time(existing.am_in)  if existing else '',
        'am_out': _fmt_ph_time(existing.am_out) if existing else '',
        'pm_in':  _fmt_ph_time(existing.pm_in)  if existing else '',
        'pm_out': _fmt_ph_time(existing.pm_out) if existing else '',
    }

    current_values = []
    if existing:
        current_values = [
            ('AM In', _fmt_ph_time(existing.am_in) or '—'),
            ('AM Out', _fmt_ph_time(existing.am_out) or '—'),
            ('PM In', _fmt_ph_time(existing.pm_in) or '—'),
            ('PM Out', _fmt_ph_time(existing.pm_out) or '—'),
            ('Late (min)', existing.minutes_late or '0'),
            ('Undertime (hrs)', existing.hours_undertime or '0.00'),
            ('Remarks', existing.remarks or '—'),
        ]

    # Build slot_fields with current_values for pre-selection in template
    slot_fields_with_values = [
        ('am_in_status', 'AM In Status', existing.am_in_status if existing else ''),
        ('am_out_status', 'AM Out Status', existing.am_out_status if existing else ''),
        ('pm_in_status', 'PM In Status', existing.pm_in_status if existing else ''),
        ('pm_out_status', 'PM Out Status', existing.pm_out_status if existing else ''),
    ]
        
    return render(request, 'dtr/manual_entry.html', {
        'today':        today,
        'employee':     employee,
        'initial_date': initial_date,
        'existing':     existing,
        'prefill':      prefill,
        'current_values': current_values,
        'status_choices': STATUS_CHOICES,
        'slot_fields': slot_fields_with_values,
        'holiday_choices': [
            ('regular', 'Regular Holiday'),
            ('special', 'Special Non-Working'),
            ('local',   'Local Holiday'),
        ],
        'is_flexible': sched_ctx['is_flexible'],
        'working_hours': sched_ctx['working_hours_per_day'],
        'flex_latest': (
            sched_ctx.get('flex_start_latest', time(8, 0)).strftime('%H:%M')
        ),
    })

# DTR Views for regular employee, role = viewer
# ADD at the bottom of dtr/views.py

@login_required
def my_dtr(request):
    """
    Viewer self-service DTR — read-only, uses base_viewer.html.
    Redirects non-viewers to the full dtr_detail page.
    """
    current_user = request.current_user

    # HR staff/admin use the full detail page instead
    if current_user.role != 'viewer':
        if current_user.employee:
            return redirect('dtr:detail', emp_id=current_user.employee.employee_id)
        return redirect('dtr:dtr_list')

    # Viewer must have a linked employee
    if not current_user.employee:
        messages.warning(request, 'Your account is not linked to an employee record. Contact HR.')
        return redirect('core:dashboard')

    employee = current_user.employee
    today    = _ph_today()

    raw_month      = request.GET.get('month', '')
    selected_month = _parse_month(raw_month, today)
    last_day       = monthrange(selected_month.year, selected_month.month)[1]

    first_of_prev  = (selected_month - timedelta(days=1)).replace(day=1)
    first_of_next  = (selected_month.replace(day=last_day) + timedelta(days=1)).replace(day=1)
    prev_month     = first_of_prev.strftime('%Y-%m')
    next_month     = first_of_next.strftime('%Y-%m')

    qs = DTRRecord.objects.filter(
        employee=employee,
        dtr_date__range=(selected_month, selected_month.replace(day=last_day))
    ).order_by('dtr_date')

    records_list  = list(qs)
    month_summary = {
        'present': 0, 'absent': 0, 'late': 0,
        'undertime_hours': 0.0, 'on_travel': 0,
        'on_leave': 0, 'holidays': 0,
    }

    sched_ctx = get_effective_schedule(employee, selected_month)
    is_flexible = sched_ctx['is_flexible']
    working_hrs = sched_ctx['working_hours_per_day']

    for rec in records_list:
        rec.date              = rec.dtr_date
        rec.is_late           = (rec.minutes_late or 0) > 0
        rec.late_minutes      = rec.minutes_late or 0
        rec.undertime_minutes = int((rec.hours_undertime or 0) * 60)

        # Automatically tag Saturdays (5) and Sundays (6) as rest days
        if rec.date.weekday() >= 5:
            rec.is_restday = True

        if rec.is_restday:
            rec.status = 'restday'
        elif rec.is_holiday:
            rec.status = 'holiday'
        elif rec.am_in_status == 'leave' or rec.pm_in_status == 'leave':
            rec.status = 'leave'
        elif rec.am_in_status in ('to', 'tt') or rec.pm_in_status in ('to', 'tt'):
            rec.status = 'to'
        elif rec.is_half_day_absent():
            rec.status = 'halfday'
        elif rec.am_in is None and rec.pm_in is None:
            rec.status = 'absent'
        else:
            rec.status = 'present'

        # PH-localized time strings (fix the UTC display bug)
        # Also, Sub-labels
        rec.ph_am_in  = _ph_time_str(rec.am_in)
        rec.ph_am_out = _ph_time_str(rec.am_out)
        rec.ph_pm_in  = _ph_time_str(rec.pm_in)
        rec.ph_pm_out = _ph_time_str(rec.pm_out)

        # Sub-labels — skip for rest/holiday/leave rows
        if rec.status not in ('restday', 'holiday', 'leave'):
            rec.sub_am_in  = _slot_sublabel('am_in',  rec.am_in, sched_ctx)
            rec.sub_am_out = _slot_sublabel('am_out', rec.am_out, sched_ctx)
            rec.sub_pm_in  = _slot_sublabel('pm_in',  rec.pm_in, sched_ctx)
            rec.sub_pm_out = _slot_sublabel('pm_out', rec.pm_out, sched_ctx)
        else:
            rec.sub_am_in = rec.sub_am_out = rec.sub_pm_in = rec.sub_pm_out = ''

        # For flexible schedules, show the required out time in the PM Out cell
        rec.required_out_str = (
            _flex_required_out_str(rec.am_in, working_hrs)
            if is_flexible else ''
        )

        # Summary counting (no 'late' bucket - late is inside present)
        if rec.status == 'present':   month_summary['present']        += 1
        elif rec.status == 'absent':  month_summary['absent']         += 1
        elif rec.status == 'to':      month_summary['on_travel']      += 1
        elif rec.status == 'leave':   month_summary['on_leave']       += 1
        elif rec.status == 'holiday': month_summary['holidays']       += 1
        month_summary['undertime_hours'] += float(rec.hours_undertime or 0)

    month_summary['undertime_hours'] = round(month_summary['undertime_hours'], 2)

    return render(request, 'dtr/my_dtr.html', {
        'today':          today,
        'employee':       employee,
        'selected_month': selected_month,
        'prev_month':     prev_month,
        'next_month':     next_month,
        'dtr_records':    records_list,
        'month_summary':  month_summary,
        'is_flexible': is_flexible,
        'working_hrs': working_hrs,
    })


@login_required
def my_dtr_print(request):
    """
    Print-ready DTR for viewer — uses DTR Generator layout via base_print.html.
    """
    current_user = request.current_user

    if not current_user.employee:
        messages.warning(request, 'No employee record linked to your account.')
        return redirect('core:dashboard')

    employee = current_user.employee
    today    = _ph_today()

    raw_month      = request.GET.get('month', '')
    selected_month = _parse_month(raw_month, today)
    last_day       = monthrange(selected_month.year, selected_month.month)[1]

    dtr_records = DTRRecord.objects.filter(
        employee=employee,
        dtr_date__range=(selected_month, selected_month.replace(day=last_day))
    ).order_by('dtr_date')

    # Compute totals for the print footer
    total_late_min   = sum(r.minutes_late or 0 for r in dtr_records)
    total_undertime  = sum(float(r.hours_undertime or 0) for r in dtr_records)
    total_hrs_worked = sum(float(r.total_hours_worked or 0) for r in dtr_records)
    days_present     = sum(1 for r in dtr_records if r.am_in is not None and not r.is_holiday)
    days_absent      = sum(1 for r in dtr_records if r.am_in is None and not r.is_holiday and not r.is_restday)

    # AUDIT LOG: Track Employee printing their own DTR
    try:
        create_audit_log(
            table_affected='dtr_records',
            record_id=employee.employee_id,
            action='print',
            performed_by=request.current_user,
            ip_address=get_client_ip(request),
            description=f'{employee.get_full_name()} printed their own DTR (Month: {selected_month.strftime("%B %Y")}).'
        )
    except Exception:
        pass

    return render(request, 'dtr/print_dtr.html', {
        'today':           today,
        'employee':        employee,
        'selected_month':  selected_month,
        'dtr_records':     dtr_records,
        'total_late_min':  total_late_min,
        'total_undertime': round(total_undertime, 2),
        'total_hrs_worked':round(total_hrs_worked, 2),
        'days_present':    days_present,
        'days_absent':     days_absent,
        'is_viewer_print': True,
    })

# API Response - live updating the manual entry form
# when choosing different date
@login_required
def get_dtr_by_date(request, emp_id):
    date_str = request.GET.get('date')

    if not date_str:
        return JsonResponse({'error': 'No date provided'}, status=400)

    try:
        dtr_date = date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    employee = get_object_or_404(Employee, employee_id=emp_id)
    sched_ctx = get_effective_schedule(employee, dtr_date)

    # --- NEW: resolve which EmployeeSchedule row is active on this date ---
    from apps.employees.models import EmployeeSchedule, WorkSchedule as WS
    
    active_sched_row = (
        EmployeeSchedule.objects
        .select_related('schedule')
        .filter(employee=employee, effective_date__lte=dtr_date)
        .order_by('-effective_date')
        .first()
    )

    # Next schedule: the earliest row AFTER the active one's effective_date
    next_sched_row = None
    if active_sched_row:
        next_sched_row = (
            EmployeeSchedule.objects
            .select_related('schedule')
            .filter(
                employee=employee,
                effective_date__gt=active_sched_row.effective_date
            )
            .order_by('effective_date')
            .first()
        )

    sched_info = {
        'is_flexible': sched_ctx.get('is_flexible', False),
        'is_free': sched_ctx.get('is_free', False),
        'working_hours': sched_ctx.get('working_hours_per_day', 8.0),
        'flex_latest': (
            sched_ctx.get('flex_start_latest', time(8, 0)).strftime('%H:%M')
        ),
        # NEW fields
        'active_schedule_name': (
            active_sched_row.schedule.schedule_name if active_sched_row else 'System default (8AM–5PM)'
        ),
        'active_effective_date': (
            active_sched_row.effective_date.strftime('%b %d, %Y') if active_sched_row else None
        ),
        'next_schedule_name': (
            next_sched_row.schedule.schedule_name if next_sched_row else None
        ),
        'next_effective_date': (
            next_sched_row.effective_date.strftime('%b %d, %Y') if next_sched_row else None
        ),
    }

    try:
        rec = DTRRecord.objects.get(employee__employee_id=emp_id, dtr_date=dtr_date)

        def fmt(dt):
            return dt.astimezone(PH_TZ).strftime('%H:%M') if dt else ''

        return JsonResponse({
            'exists': True,
            'am_in': fmt(rec.am_in),
            'am_out': fmt(rec.am_out),
            'pm_in': fmt(rec.pm_in),
            'pm_out': fmt(rec.pm_out),
            'remarks': rec.remarks or '',
            'is_holiday': rec.is_holiday,
            'is_restday': rec.is_restday,
            'holiday_type': rec.holiday_type,
            'am_in_status': rec.am_in_status or '',
            'am_out_status': rec.am_out_status or '',
            'pm_in_status': rec.pm_in_status or '',
            'pm_out_status': rec.pm_out_status or '',
            **sched_info,
        })

    except DTRRecord.DoesNotExist:
        return JsonResponse({'exists': False, **sched_info})