# apps/leaves/engine.py
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from apps.employees.models import Employee
from apps.dtr.models import DTRRecord
from apps.leaves.models import LeaveCredit
from apps.leaves.csc_conversion import get_deduction_days 

@transaction.atomic
def process_monthly_leave_accrual(year: int, month: int):
    print(f"\n--- Processing Leaves for {month}/{year} ---")

    permanent_employees = Employee.objects.filter(
        employment_type__icontains='permanent', 
        status__icontains='active'
    )

    print(f"Found {permanent_employees.count()} active permanent employees.")
    records_created = 0

    for emp in permanent_employees:
        print(f" -> Calculating for: {emp.get_full_name()}")
        
        # --- 1. Fetch DTR Totals ---
        dtr_summary = DTRRecord.objects.filter(
            employee=emp,
            dtr_date__year=year,
            dtr_date__month=month
        ).aggregate(
            total_late=Sum('minutes_late'),
            total_ut_hours=Sum('hours_undertime')
        )

        late_mins = dtr_summary['total_late'] or 0
        ut_hours = dtr_summary['total_ut_hours'] or Decimal('0.000')
        ut_mins = int(ut_hours * 60)
        total_deduction_minutes = late_mins + ut_mins

        # Convert to fractional days using our CSC mapping
        undertime_fraction = get_deduction_days(total_deduction_minutes)

        # --- 2. Process VL (Vacation Leave) ---
        prev_vl = LeaveCredit.get_previous_balance(emp, 'VL', year, month)
        earned_vl = Decimal('1.250')
        
        # Pre-compute balance to satisfy NOT NULL database constraint
        vl_balance = prev_vl + earned_vl - undertime_fraction
        if vl_balance < Decimal('0.000'): 
            vl_balance = Decimal('0.000')
        
        LeaveCredit.objects.update_or_create(
            employee=emp, leave_type='VL', year=year, month=month,
            defaults={
                'earned': earned_vl,
                'undertime_days': undertime_fraction,
                'abs_wp': Decimal('0.000'),
                'special_leave_used': Decimal('0.000'),
                'balance': vl_balance,  # <-- Pass pre-computed balance here!
                'remarks': f"UT/Late: {total_deduction_minutes} mins" if total_deduction_minutes > 0 else ""
            }
        )

        # --- 3. Process SL (Sick Leave) ---
        prev_sl = LeaveCredit.get_previous_balance(emp, 'SL', year, month)
        earned_sl = Decimal('1.250')
        
        # Pre-compute SL balance
        sl_balance = prev_sl + earned_sl
        if sl_balance < Decimal('0.000'): 
            sl_balance = Decimal('0.000')
        
        LeaveCredit.objects.update_or_create(
            employee=emp, leave_type='SL', year=year, month=month,
            defaults={
                'earned': earned_sl,
                'undertime_days': Decimal('0.000'),
                'abs_wp': Decimal('0.000'),
                'special_leave_used': Decimal('0.000'),
                'balance': sl_balance,  # <-- Pass pre-computed balance here!
                'remarks': ""
            }
        )

        records_created += 2

    print(f"--- Finished! Created/Updated {records_created} normalized records. ---\n")
    return records_created