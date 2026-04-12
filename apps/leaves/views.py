# apps/leaves/views.py
import calendar
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from apps.employees.models import Employee
from apps.leaves.models import LeaveCredit

def list(request):
    """Master list of permanent employees and their current leave balances."""
    today = timezone.localdate()
    current_year = today.year

    permanent_employees = Employee.objects.filter(
        employment_type__icontains='permanent', 
        status__icontains='active'
    ).select_related('position', 'division')

    leave_data = []
    
    for emp in permanent_employees:
        # Get latest balances separately since they are on different rows
        latest_vl = LeaveCredit.objects.filter(employee=emp, leave_type='VL').order_by('-year', '-month').first()
        latest_sl = LeaveCredit.objects.filter(employee=emp, leave_type='SL').order_by('-year', '-month').first()
        
        # Calculate YTD (Summing using Python for safety across multiple deduction fields)
        vl_records_ytd = LeaveCredit.objects.filter(employee=emp, year=current_year, leave_type='VL')
        sl_records_ytd = LeaveCredit.objects.filter(employee=emp, year=current_year, leave_type='SL')

        leave_data.append({
            'employee': emp,
            'vl_balance': latest_vl.balance if latest_vl else Decimal('0.000'),
            'sl_balance': latest_sl.balance if latest_sl else Decimal('0.000'),
            'vl_earned_ytd': sum(r.earned for r in vl_records_ytd),
            'sl_earned_ytd': sum(r.earned for r in sl_records_ytd),
            'vl_used_ytd': sum(r.abs_wp + r.undertime_days + r.special_leave_used for r in vl_records_ytd),
            'sl_used_ytd': sum(r.abs_wp + r.undertime_days + r.special_leave_used for r in sl_records_ytd),
        })

    return render(request, 'leaves/list.html', {
        'leave_data': leave_data,
        'today': today,
    })

def elr(request, pk):
    """Displays the Official Employee Leave Record (ELR) Ledger."""
    employee = get_object_or_404(Employee, employee_id=pk)
    today = timezone.localdate()
    selected_year = int(request.GET.get('year', today.year))

    available_years = LeaveCredit.objects.filter(employee=employee).values_list('year', flat=True).distinct().order_by('-year')
    if not available_years:
        available_years = [today.year]

    # Initialize a blank 12-month calendar structure
    months_data = []
    for m in range(1, 13):
        months_data.append({
            'month_num': m,
            'month_name': calendar.month_abbr[m].upper(), # JAN, FEB, MAR
            'vl_earned': None, 'vl_abs': None, 'vl_bal': None,
            'sl_earned': None, 'sl_abs': None, 'sl_bal': None,
            'remarks': []
        })

    ytd_vl_abs = Decimal('0.000')
    ytd_sl_abs = Decimal('0.000')

    # Fetch and pivot the normalized records into the flat calendar
    records = LeaveCredit.objects.filter(employee=employee, year=selected_year)
    for rec in records:
        md = months_data[rec.month - 1] # Index 0 is January
        
        # Total deduction = Absent W/P + Undertime + Special Leaves
        total_deduct = rec.abs_wp + rec.undertime_days + rec.special_leave_used

        if rec.leave_type == 'VL':
            md['vl_earned'] = rec.earned
            md['vl_abs'] = total_deduct if total_deduct > Decimal('0.000') else None
            md['vl_bal'] = rec.balance
            ytd_vl_abs += total_deduct
        elif rec.leave_type == 'SL':
            md['sl_earned'] = rec.earned
            md['sl_abs'] = total_deduct if total_deduct > Decimal('0.000') else None
            md['sl_bal'] = rec.balance
            ytd_sl_abs += total_deduct
        
        if rec.remarks:
            md['remarks'].append(rec.remarks)

    # Clean up remarks array into a single string
    for md in months_data:
        md['remarks'] = " | ".join(md['remarks'])

    # Get overall latest balances for the top hero cards
    latest_vl = LeaveCredit.objects.filter(employee=employee, leave_type='VL').order_by('-year', '-month').first()
    latest_sl = LeaveCredit.objects.filter(employee=employee, leave_type='SL').order_by('-year', '-month').first()

    context = {
        'employee': employee,
        'months_data': months_data,
        'selected_year': selected_year,
        'available_years': available_years,
        'current_vl': latest_vl.balance if latest_vl else Decimal('0.000'),
        'current_sl': latest_sl.balance if latest_sl else Decimal('0.000'),
        'ytd_vl_abs': ytd_vl_abs,
        'ytd_sl_abs': ytd_sl_abs,
    }
    return render(request, 'leaves/elr.html', context)

def print_elr(request, pk):
    response = elr(request, pk) 
    response.template_name = 'leaves/print_elr.html'
    return response