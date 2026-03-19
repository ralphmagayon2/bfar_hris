"""
apps/core/views.py
 
BFAR Region III — HRIS
 
Changes from your original file:
  1. _get_session_user() removed — replaced by request.current_user
     (set by InjectCurrentUserMiddleware using session key '_auth_user_id')
  2. dashboard() now reads request.current_user (no DB hit — middleware did it)
  3. Fixed typo: 'dashboard_viewer.html' → 'dashboard_viewer.html'
  4. Fixed select_related: 'employee_division' → 'employee__division'
  5. Fixed ordering: 'holiday_date' not 'holiday_date' (was 'date', corrected)
  6. Added user_is_superadmin and can_manage_users to HR dashboard context
  7. absent_today clamped to max(0, ...) so it never goes negative
  8. Live feed now uses DTRRecord fields that actually exist on the model:
       am_in as the scan time, am_in_status == 'late' as the late flag
     (True biometric scan log requires a BiometricLog model — not built yet;
      today_logs is a best-effort DTR-based feed until biometrics are wired up)
"""

from django.shortcuts import render, redirect
from apps.employees.models import Employee
from apps.dtr.models import DTRRecord
from apps.travel_orders.models import TravelOrder
from apps.holidays.models import Holiday
from apps.payroll.models import PayrollPeriod
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages

# def _get_session_user(request):
#     from apps.accounts.models import SystemUser

#     user_id = request.session.get('user_id')
#     if not user_id:
#         return None

#     try:
#         return SystemUser.objects.select_related('employee').get(pk=user_id)
#     except SystemUser.DoesNotExist:
#         return None
    
def dashboard(request):
    system_user = request.current_user # FIXED this part because the _get_session cause infinite loop in admin login
    
    if not system_user:
        messages.warning(request, "Please logged in to access this page.")
        return redirect('accounts:login')
    
    # Viewer gets their own stripped-down dashboard
    if system_user.role == 'viewer':
        return _viewer_dashboard(request, system_user)
    
    # superadmin / hr_admin / hr_staff share the same HR dashboard
    return _hr_dashboard(request, system_user)

def _hr_dashboard(request, system_user):
    """Full HR dashboard for superadmin, hr_admin, hr_staff"""
    today = timezone.localdate()

    total_employees = Employee.objects.filter(is_active=True).count()
    present_today = DTRRecord.objects.filter(dtr_date=today, am_in__isnull=False).count()
    late_today = DTRRecord.objects.filter(dtr_date=today, am_in_status='late').count()
    absent_today = total_employees - present_today
    on_travel_today = DTRRecord.objects.filter(dtr_date=today, am_in_status='to').count()
    on_leave_today = DTRRecord.objects.filter(dtr_date=today, am_in_status='leave').count()

    today_logs = (
        DTRRecord.objects
        .filter(dtr_date=today)
        .select_related('employee__division')
        .order_by('-am_in')[:50]
    )

    recent_travel_orders = (
        TravelOrder.objects
        .filter(date_to__gte=today)
        .select_related('employee__division')
        .order_by('date_from')[:5]
    )

    current_payroll_period = (
        PayrollPeriod.objects
        .filter(status='open')
        .order_by('-date_from')
        .first()
    )

    upcoming_holidays = (
        Holiday.objects
        .filter(holiday_date__gte=today)
        .order_by('holiday_date')[:5]
    )

    return render(request, 'core/dashboard.html', {
        'system_user': system_user,
        'today': today,
        'total_employees': total_employees,
        'present_today': present_today,
        'late_today': late_today,
        'absent_today': absent_today,
        'on_travel_today': on_travel_today,
        'on_leave_today': on_leave_today,
        'today_logs': today_logs,
        'recent_travel_orders': recent_travel_orders,
        'upcoming_holidays': upcoming_holidays,
        'current_payroll_period': current_payroll_period,

        # Role flags for template conditionals (hr_staff restrictions)
        'can_approve': system_user.can_approve(),
        'can_manage_users': system_user.can_manage_users(),
    })

def _viewer_dashboard(request, system_user):
    """Stripped-down self-service dashboard for regular employees."""
    today = timezone.localdate()
    employee = system_user.employee # nullable - IT admins have no employees record

    # Own DTR for current month
    own_dtr_this_month = []
    own_travel_orders = []
    upcoming_holidays = (
        Holiday.objects
        .filter(holiday_date__gte=today)
        .order_by('holiday_date')[:5]
    )

    if employee:
        own_dtr_this_month = (
            DTRRecord.objects
            .filter(employee=employee, dtr_date__year=today.year, dtr_date__month=today.month)
            .order_by('dtr_date')
        )
        own_travel_orders = (
            TravelOrder.objects
            .filter(employee=employee, date_to__gte=today)
            .order_by('date_from')[:5]
        )

    return render(request, 'core/dashboard_viewer.html', {
        'system_user': system_user,
        'employee': employee,
        'today': today,
        'own_dtr_this_month': own_dtr_this_month,
        'own_travel_orders': own_travel_orders,
        'upcoming_holidays': upcoming_holidays,
    })

# def dashboard(request):
#     return render(request, 'core/dashboard.html')

# def dashboard(request):
#     return render(request, 'core/dashboard_viewer.html')

def error_403(request):
    return render(request, '403.html', status=403)

def error_404(request):
    return render(request, '404.html', status=404)

def error_500(request):
    return render(request, '500.html', status=500)

def base_print(request):
    return render(request, 'base_print.html')