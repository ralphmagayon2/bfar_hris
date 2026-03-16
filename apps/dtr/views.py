"""
apps/dtr/views.py
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages
from datetime import date, timedelta
from calendar import monthrange
import datetime as dt_module
import pytz

from apps.employees.models import Employee
from apps.dtr.models import DTRRecord


def _ph_today() -> date:
    ph_tz = pytz.timezone('Asia/Manila')
    return timezone.now().astimezone(ph_tz).date()


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


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 1 — dtr_list
# ─────────────────────────────────────────────────────────────────────────────

def dtr_list(request):
    today = _ph_today()

    raw_date  = request.GET.get('date', '')
    raw_month = request.GET.get('month', '')

    if raw_month:
        selected_month = _parse_month(raw_month, today)
        selected_date  = None
        last_day = monthrange(selected_month.year, selected_month.month)[1]
        qs = DTRRecord.objects.filter(
            dtr_date__range=(selected_month, selected_month.replace(day=last_day))
        ).select_related('employee', 'employee__division', 'employee__position')
    else:
        selected_date  = _parse_date(raw_date, today)
        selected_month = None
        qs = DTRRecord.objects.filter(
            dtr_date=selected_date
        ).select_related('employee', 'employee__division', 'employee__position')

    qs = qs.order_by('employee__last_name', 'employee__first_name')

    def _derive_status(rec):
        if rec.is_holiday:
            return 'holiday'
        if rec.am_in_status == 'leave' or rec.pm_in_status == 'leave':
            return 'leave'
        if rec.am_in_status in ('to', 'tt') or rec.pm_in_status in ('to', 'tt'):
            return 'on_travel'
        if rec.is_half_day_absent():
            return 'halfday'
        if rec.minutes_late and rec.minutes_late > 0:
            return 'late'
        if rec.am_in_status == 'absent' and rec.pm_in_status == 'absent':
            return 'absent'
        if rec.am_in is not None:
            return 'present'
        return 'absent'

    summary = {'present': 0, 'absent': 0, 'late': 0, 'on_travel': 0, 'on_leave': 0, 'holiday': 0, 'halfday': 0}
    records_list = list(qs)
    for rec in records_list:
        rec.status = _derive_status(rec)
        rec.undertime_minutes = int((rec.hours_undertime or 0) * 60)
        if rec.status in summary:
            summary[rec.status] += 1

    paginator   = Paginator(records_list, 30)
    dtr_records = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dtr/list.html', {
        'today':          today,
        'selected_date':  selected_date,
        'selected_month': selected_month,
        'dtr_records':    dtr_records,
        'summary':        summary,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 2 — dtr_detail
# ─────────────────────────────────────────────────────────────────────────────

def dtr_detail(request, emp_id):
    today    = _ph_today()
    employee = get_object_or_404(
        Employee.objects.select_related('division', 'unit', 'position'),
        employee_id=emp_id
    )

    raw_month      = request.GET.get('month', '')
    selected_month = _parse_month(raw_month, today)
    last_day       = monthrange(selected_month.year, selected_month.month)[1]

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

    for rec in records_list:
        rec.date = rec.dtr_date
        rec.is_late = (rec.minutes_late or 0) > 0
        rec.late_minutes = rec.minutes_late or 0
        rec.undertime_minutes = int((rec.hours_undertime or 0) * 60)

        if rec.is_holiday:
            rec.status = 'holiday'
        elif rec.am_in_status == 'leave' or rec.pm_in_status == 'leave':
            rec.status = 'leave'
        elif rec.am_in_status in ('to', 'tt') or rec.pm_in_status in ('to', 'tt'):
            rec.status = 'to'
        elif rec.is_half_day_absent():
            rec.status = 'halfday'
        elif rec.is_late:
            rec.status = 'late'
        elif rec.am_in is None and rec.pm_in is None:
            rec.status = 'absent'
        else:
            rec.status = 'present'

        if rec.status == 'present':   month_summary['present']   += 1
        elif rec.status == 'absent':  month_summary['absent']    += 1
        elif rec.status == 'late':    month_summary['late']      += 1
        elif rec.status == 'to':      month_summary['on_travel'] += 1
        elif rec.status == 'leave':   month_summary['on_leave']  += 1
        elif rec.status == 'holiday': month_summary['holidays']  += 1
        month_summary['undertime_hours'] += float(rec.hours_undertime or 0)

    month_summary['undertime_hours'] = round(month_summary['undertime_hours'], 2)

    return render(request, 'dtr/detail.html', {
        'today':          today,
        'employee':       employee,
        'selected_month': selected_month,
        'prev_month':     prev_month,
        'next_month':     next_month,
        'dtr_records':    records_list,
        'month_summary':  month_summary,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 3 — dtr_edit
# ─────────────────────────────────────────────────────────────────────────────

STATUS_CHOICES = [
    ('present', 'Present'),
    ('late',    'Late'),
    ('absent',  'Absent'),
    ('to',      'Travel'),
    ('tt',      'Trip Tkt'),
    ('leave',   'Leave'),
    ('holiday', 'Holiday'),
]


def dtr_edit(request, dtr_id):
    dtr = get_object_or_404(
        DTRRecord.objects.select_related('employee', 'employee__division', 'employee__position'),
        dtr_id=dtr_id
    )

    slot_statuses = [
        ('AM Time-In Status',  'am_in_status',  dtr.am_in_status),
        ('AM Time-Out Status', 'am_out_status', dtr.am_out_status),
        ('PM Time-In Status',  'pm_in_status',  dtr.pm_in_status),
        ('PM Time-Out Status', 'pm_out_status', dtr.pm_out_status),
    ]

    ph_tz = pytz.timezone('Asia/Manila')

    def _fmt_time(dt):
        if not dt:
            return None
        return dt.astimezone(ph_tz).strftime('%I:%M %p')

    original_values = [
        ('AM In',    _fmt_time(dtr.am_in)),
        ('AM Out',   _fmt_time(dtr.am_out)),
        ('PM In',    _fmt_time(dtr.pm_in)),
        ('PM Out',   _fmt_time(dtr.pm_out)),
        ('Remarks',  dtr.remarks),
    ]

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()

        if dtr.is_locked and not reason:
            messages.error(request, 'A reason for correction is required for locked records.')
            return render(request, 'dtr/form.html', {
                'dtr':             dtr,
                'today':           _ph_today(),
                'status_choices':  STATUS_CHOICES,
                'slot_statuses':   slot_statuses,
                'original_values': original_values,
            })

        # Snapshot for audit log
        old_snapshot = {
            'am_in': str(dtr.am_in), 'am_out': str(dtr.am_out),
            'pm_in': str(dtr.pm_in), 'pm_out': str(dtr.pm_out),
            'am_in_status': dtr.am_in_status, 'am_out_status': dtr.am_out_status,
            'pm_in_status': dtr.pm_in_status, 'pm_out_status': dtr.pm_out_status,
            'remarks': dtr.remarks,
        }

        def _combine(time_str):
            if not time_str:
                return None
            try:
                h, m = map(int, time_str.split(':'))
                naive = dt_module.datetime.combine(dtr.dtr_date, dt_module.time(h, m))
                return ph_tz.localize(naive)
            except (ValueError, AttributeError):
                return None

        dtr.am_in  = _combine(request.POST.get('am_in', '').strip())
        dtr.am_out = _combine(request.POST.get('am_out', '').strip())
        dtr.pm_in  = _combine(request.POST.get('pm_in', '').strip())
        dtr.pm_out = _combine(request.POST.get('pm_out', '').strip())

        valid_statuses = {v for v, _ in STATUS_CHOICES}
        for _, field, _ in slot_statuses:
            val = request.POST.get(field, '').strip()
            setattr(dtr, field, val if val in valid_statuses else None)

        dtr.remarks = request.POST.get('remarks', '').strip() or None

        # Recompute minutes late (no grace period — any scan after 08:00 is late)
        if dtr.am_in:
            cutoff = ph_tz.localize(dt_module.datetime.combine(dtr.dtr_date, dt_module.time(8, 0)))
            delta  = (dtr.am_in - cutoff).total_seconds()
            dtr.minutes_late = max(0, int(delta // 60))
        else:
            dtr.minutes_late = 0

        dtr.save()

        # ── Audit log (uncomment once session auth is wired) ──────────────────
        # new_snapshot = { ... }
        # create_audit_log(
        #     table_affected='dtr_records', record_id=dtr.dtr_id, action='update',
        #     performed_by=request.session_user,
        #     old_value=old_snapshot, new_value=new_snapshot,
        #     ip_address=request.META.get('REMOTE_ADDR'), reason=reason or None,
        # )

        messages.success(request, f'DTR record for {dtr.dtr_date|date:"F d, Y"} updated successfully.')
        return redirect('dtr:detail', emp_id=dtr.employee.employee_id)

    return render(request, 'dtr/form.html', {
        'dtr':             dtr,
        'today':           _ph_today(),
        'status_choices':  STATUS_CHOICES,
        'slot_statuses':   slot_statuses,
        'original_values': original_values,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 4 — dtr_print
# ─────────────────────────────────────────────────────────────────────────────

def dtr_print(request, emp_id):
    today    = _ph_today()
    employee = get_object_or_404(Employee, employee_id=emp_id)

    raw_month      = request.GET.get('month', '')
    selected_month = _parse_month(raw_month, today)
    last_day       = monthrange(selected_month.year, selected_month.month)[1]

    dtr_records = DTRRecord.objects.filter(
        employee=employee,
        dtr_date__range=(selected_month, selected_month.replace(day=last_day))
    ).order_by('dtr_date')

    return render(request, 'dtr/print_dtr.html', {
        'today':          today,
        'employee':       employee,
        'selected_month': selected_month,
        'dtr_records':    dtr_records,
    })