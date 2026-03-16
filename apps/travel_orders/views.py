"""
apps/travel_orders/views.py

Bug fixes found in travel_orders/list.html (audited alongside form creation):
    1. to.travel_type       → model field is ticket_type
    2. to.num_days          → no such field; use get_duration_days() method
    3. to.employee.division.name → Division has no .name; use division_name
    4. to.employee.profile_picture → Employee model has no profile_picture; use get_initials()
    5. {% url 'travel_orders:edit' to.id %} → PK is to_id not id
    6. {% url 'travel_orders:form' %}        → URL name should be travel_orders:create
    7. data-type="{{ to.travel_type|lower }}" → should be ticket_type
    8. {{ travel_orders|length }}             → dtr_records is a Page object; use paginator.count
    9. summary.to_count / summary.tt_count / summary.active_today → must be passed from view
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from datetime import date
import pytz

from apps.employees.models import Employee
from apps.travel_orders.models import TravelOrder


def _ph_today() -> date:
    return timezone.now().astimezone(pytz.timezone('Asia/Manila')).date()


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 1 — to_list
# URL  : /travel-orders/
# Name : travel_orders:list
# Template: travel_orders/list.html
# ─────────────────────────────────────────────────────────────────────────────

def to_list(request):
    today = _ph_today()

    qs = TravelOrder.objects.select_related(
        'employee', 'employee__division', 'created_by'
    ).order_by('-date_from', 'employee__last_name')

    # Annotate template-friendly aliases
    records = list(qs)
    for to in records:
        # BUG FIX 1: template uses to.travel_type → alias ticket_type
        to.travel_type = to.ticket_type
        # BUG FIX 2: template uses to.num_days → use method
        to.num_days = to.get_duration_days()

    # ── Summary chips ─────────────────────────────────────────────────────────
    summary = {
        'to_count':     qs.filter(ticket_type='TO').count(),
        'tt_count':     qs.filter(ticket_type='TT').count(),
        # active_today: TOs/TTs whose date range covers today
        'active_today': qs.filter(date_from__lte=today, date_to__gte=today).count(),
    }

    # ── Pagination ────────────────────────────────────────────────────────────
    paginator      = Paginator(records, 25)
    travel_orders  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'travel_orders/list.html', {
        'today':         today,
        'travel_orders': travel_orders,
        'total_to':      qs.count(),
        'summary':       summary,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 2 — to_create
# URL  : /travel-orders/add/
# Name : travel_orders:create
# Template: travel_orders/form.html
# ─────────────────────────────────────────────────────────────────────────────

def to_create(request):
    employees = Employee.objects.filter(is_active=True).order_by('last_name', 'first_name')

    if request.method == 'POST':
        errors = _validate_to_form(request.POST)
        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'travel_orders/form.html', {
                'employees':    employees,
                'travel_order': None,
                'today':        _ph_today(),
            })

        to = _build_travel_order(request.POST, request)
        to.save()

        messages.success(request, f'Travel order {to.to_code} created successfully.')
        return redirect('travel_orders:list')

    return render(request, 'travel_orders/form.html', {
        'employees':    employees,
        'travel_order': None,
        'today':        _ph_today(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 3 — to_edit
# URL  : /travel-orders/<id>/edit/
# Name : travel_orders:edit
# Template: travel_orders/form.html
# ─────────────────────────────────────────────────────────────────────────────

def to_edit(request, to_id):
    # BUG FIX 5: use to_id not id
    travel_order = get_object_or_404(
        TravelOrder.objects.select_related('employee', 'created_by'),
        to_id=to_id
    )
    employees = Employee.objects.filter(is_active=True).order_by('last_name', 'first_name')

    if request.method == 'POST':
        errors = _validate_to_form(request.POST)
        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'travel_orders/form.html', {
                'employees':    employees,
                'travel_order': travel_order,
                'today':        _ph_today(),
            })

        travel_order = _apply_to_form(travel_order, request.POST)
        travel_order.save()

        messages.success(request, f'Travel order {travel_order.to_code} updated successfully.')
        return redirect('travel_orders:list')

    return render(request, 'travel_orders/form.html', {
        'employees':    employees,
        'travel_order': travel_order,
        'today':        _ph_today(),
    })


# ─────────────────────────────────────────────────────────────────────────────
# VIEW 4 — to_delete
# URL  : /travel-orders/<id>/delete/
# Name : travel_orders:delete
# POST only — no template.
# ─────────────────────────────────────────────────────────────────────────────

def to_delete(request, to_id):
    if request.method != 'POST':
        return redirect('travel_orders:list')

    travel_order = get_object_or_404(TravelOrder, to_id=to_id)
    code = travel_order.to_code
    travel_order.delete()

    messages.success(request, f'Travel order {code} deleted.')
    return redirect('travel_orders:list')


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _validate_to_form(post) -> list:
    """Return a list of error messages. Empty list = valid."""
    errors = []

    if not post.get('ticket_type') in ('TO', 'TT'):
        errors.append('Document type must be TO or TT.')

    if not post.get('employee_id', '').strip():
        errors.append('Please select an employee.')

    if not post.get('to_code', '').strip():
        errors.append('TO/TT Code is required.')

    date_from_raw = post.get('date_from', '')
    date_to_raw   = post.get('date_to',   '')

    if not date_from_raw or not date_to_raw:
        errors.append('Both Date From and Date To are required.')
    else:
        try:
            from datetime import date as date_cls
            d_from = date_cls.fromisoformat(date_from_raw)
            d_to   = date_cls.fromisoformat(date_to_raw)
            if d_to < d_from:
                errors.append('Date To cannot be earlier than Date From.')
            duration = (d_to - d_from).days + 1
            if post.get('ticket_type') == 'TO' and duration > 5:
                errors.append(f'Travel Orders have a maximum of 5 days. Selected range is {duration} days.')
        except ValueError:
            errors.append('Invalid date format.')

    return errors


def _build_travel_order(post, request) -> TravelOrder:
    """Create a new TravelOrder from POST data."""
    to = TravelOrder()
    return _apply_to_form(to, post, request)


def _apply_to_form(to: TravelOrder, post, request=None) -> TravelOrder:
    """Apply POST data to a TravelOrder instance (create or update)."""
    from datetime import date as date_cls, time as time_cls

    to.ticket_type = post.get('ticket_type', 'TO')

    employee_id = post.get('employee_id', '').strip()
    if employee_id:
        to.employee = Employee.objects.get(employee_id=employee_id)

    to.to_code    = post.get('to_code', '').strip()
    to.destination = post.get('destination', '').strip() or None
    to.purpose    = post.get('purpose', '').strip() or None

    to.date_from = date_cls.fromisoformat(post.get('date_from'))
    to.date_to   = date_cls.fromisoformat(post.get('date_to'))

    # Optional partial-day times
    def _parse_time(raw):
        if not raw:
            return None
        try:
            h, m = map(int, raw.split(':'))
            return time_cls(h, m)
        except (ValueError, AttributeError):
            return None

    to.time_from = _parse_time(post.get('time_from', '').strip())
    to.time_to   = _parse_time(post.get('time_to', '').strip())

    # Overtime
    to.with_overtime = 'with_overtime' in post
    if to.with_overtime:
        try:
            to.ot_hours = float(post.get('ot_hours', 0) or 0)
        except ValueError:
            to.ot_hours = None
    else:
        to.ot_hours = None

    # Set created_by only on new records
    if not to.to_id and request:
        # Uncomment once session auth is wired:
        # from apps.accounts.models import SystemUser
        # to.created_by = SystemUser.objects.get(user_id=request.session['user_id'])
        pass

    return to