# apps/employees/views.py

from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.db.models import Count, Q
from apps.employees.models import Employee, Division
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import Employee, Division, Unit, PayrollGroup, Position, WorkSchedule, EmployeeSchedule
from django.views.decorators.http import require_POST

# Update: Para lang makita ko yung format na dinesign ko
def detail(request, pk):
    employee = get_object_or_404(Employee, employee_id=pk)

    # Government IDs — build list of (label, vlaue) pairs
    gov_ids = [
        ('TIN', getattr(employee, 'tin', None)),
        ('GSIS Number', getattr(employee, 'gsis_number', None)),
        ('PhilHealth Number', getattr(employee, 'philhealth_number', None)),
        ('Pag-IBIG / HDMF', getattr(employee, 'pagibig_number', None)),
        ('SSS Number', getattr(employee, 'sss_number', None)),
        ('PhilSys / Nat. ID', getattr(employee, 'philsys_number', None)),
    ]

    # Only show rows that have a value - based on the data you provided
    gov_ids = [(label, val) for label, val in gov_ids if val]

    context = {
        'employee': employee,
        'gov_ids': gov_ids,

        # Placeholders — replace with real queries when those apps are ready
        'dtr_summary': {'present': 0, 'absent': 0, 'late_minutes': 0, 'undertime': 0},
        'recent_dtr': [],
        'leave_credits': {'vl_balance': 0, 'sl_balance': 0, 'vl_earned_ytd': 0, 'sl_earned_ytd': 0},
        'recent_payroll': [],
        'recent_travel': [],
    }
    return render(request, 'employees/detail.html', context)

def add_form(request):
    return render(request, 'employees/form.html')

# CHANGED THE FUNCTION NAME HERE
def employee_list(request):
    # 1. optimized queryset with select_related to reduce DB kasi grabi if every row needs to access related fields in the template, mas efficient to fetch all related data in one query
    base_qs = Employee.objects.select_related('position', 'division', 'unit', 'system_user').all() # added system_user so has_account doesn't hit the DB per row and filter is_deleted here so we don't have to keep filtering it out in the code below
    
    # 2. Get the totals BEFORE applying filters
    total_all = base_qs.count()
    total_active = base_qs.filter(status='active').count()
    type_stats = base_qs.values('employment_type').annotate(count=Count('employee_id')).order_by('employment_type')
    # group by employment_type and count how many employees in each type, ordered by employment_type wow
    divisions = Division.objects.all().order_by('division_code')

    # 3. Capture URL parameters
    search_query = request.GET.get('search', '').strip()
    emp_type = request.GET.get('type', '').strip()
    div_id = request.GET.get('division', '').strip()
    status_filter = request.GET.get('status', '').strip()
    account_filter = request.GET.get('account', '').strip()

    # 4. Apply Filters to the Queryset
    if search_query:
        base_qs = base_qs.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(employee_id__icontains=search_query)
        )
    if emp_type:
        base_qs = base_qs.filter(employment_type__iexact=emp_type)
    if div_id:
        base_qs = base_qs.filter(division_id=div_id)
    if status_filter:
        base_qs = base_qs.filter(status=status_filter)

    # Account Filter    
    if account_filter == 'has_account':
        base_qs = base_qs.filter(
            system_user__isnull=False,
            system_user__is_deleted=False
        )
    elif account_filter == 'no_account':
        base_qs = base_qs.filter(
            Q(system_user__isnull=True) |
            Q(system_user__is_deleted=True)
        )

    # 5. Pagination
    paginator = Paginator(base_qs, 25)
    page_number = request.GET.get('page')
    
    employees = paginator.get_page(page_number)
    # 6. Build a query string for the pagination buttons so they remember the filters
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page'] # Remove old page number
    filter_string = query_params.urlencode()
    filter_string = f"&{filter_string}" if filter_string else ""

    context = {
        'total_all': total_all,
        'total_active': total_active,
        'type_stats': type_stats,
        'divisions': divisions,
        'employees': employees,
        # Pass current filters to keep UI updated
        'current_search': search_query,
        'current_type': emp_type,
        'current_div': div_id,
        'current_status': status_filter,
        'current_account': account_filter, # NEW: for account filter if user has employee connect and create account
        'filter_string': filter_string, # NEW: For pagination links
    }

    return render(request, 'employees/list.html', context)

def process_employee_form(request, pk=None):
    """
    Handles CREATE and UPDATE logic.
    """
    if request.method == 'GET':
        # Load form context (combining your add_form and edit_form logic)
        employee = get_object_or_404(Employee, employee_id=pk) if pk else None
        context = {
            'employee': employee,
            'divisions': Division.objects.order_by('division_code'),
            'units': Unit.objects.order_by('unit_name'),
            'payroll_groups': PayrollGroup.objects.order_by('group_name'),
            'positions': Position.objects.order_by('employment_type', 'position_title'),
            'work_schedules': WorkSchedule.objects.order_by('schedule_name'),
        }
        return render(request, 'employees/form.html', context)

    if request.method == 'POST':
        # 1. Fetch or initialize the Employee object
        employee = get_object_or_404(Employee, employee_id=pk) if pk else Employee()

        # 2. Map POST data to standard fields
        # Step 1: Personal Info
        employee.last_name = request.POST.get('last_name')
        employee.first_name = request.POST.get('first_name')
        employee.middle_name = request.POST.get('middle_name')
        employee.suffix = request.POST.get('name_ext') # Mapped to suffix
        employee.date_of_birth = request.POST.get('date_of_birth') or None
        employee.sex = request.POST.get('sex')
        employee.civil_status = request.POST.get('civil_status')
        employee.contact_number = request.POST.get('contact_number')
        employee.email = request.POST.get('email')
        employee.address = request.POST.get('address')
        
        if 'profile_picture' in request.FILES:
            employee.profile_picture = request.FILES['profile_picture']

        # Step 2: Employment
        employee.id_number = request.POST.get('id_number')
        employee.employment_type = request.POST.get('employment_type')
        employee.date_hired = request.POST.get('date_hired') or None
        employee.contract_end_date = request.POST.get('contract_end_date') or None
        # FIXED: Save the exact status string from the dropdown, defaulting to 'active'
        employee.status = request.POST.get('status') or 'active'
        
        bio_id = request.POST.get('biometric_id')
        employee.biometric_id = int(bio_id) if bio_id else None

        # Foreign Keys
        employee.division_id = request.POST.get('division')
        employee.unit_id = request.POST.get('unit') or None
        employee.position_id = request.POST.get('position')
        employee.payroll_group_id = request.POST.get('payroll_group')

        # Step 3: Salary & Payroll
        employee.monthly_salary = request.POST.get('monthly_salary')
        employee.salary_grade = request.POST.get('salary_grade')
        
        # Deductions (Optional inputs, convert to None if empty)
        def clean_decimal(val):
            return val if val else None

        employee.gsis_monthly = clean_decimal(request.POST.get('gsis_monthly'))
        employee.philhealth_monthly = clean_decimal(request.POST.get('philhealth_monthly'))
        employee.pagibig_monthly = clean_decimal(request.POST.get('pagibig_monthly'))
        employee.tax_monthly = clean_decimal(request.POST.get('tax_monthly'))

        # IDs
        employee.tin = request.POST.get('tin')
        employee.gsis_number = request.POST.get('gsis_number')
        employee.philhealth_number = request.POST.get('philhealth_number')
        employee.pagibig_number = request.POST.get('pagibig_number')
        employee.sss_number = request.POST.get('sss_number')
        employee.philsys_number = request.POST.get('philsys_number')

        # Step 4: Schedule Notes
        employee.station = request.POST.get('station')
        employee.remarks = request.POST.get('remarks')

        # 3. Save the core employee record
        employee.save()

        # 4. Handle Work Schedule Assignment (Table 7)
        sched_id = request.POST.get('work_schedule')
        if sched_id:
            # Check if this schedule is already assigned as the latest to avoid duplicates
            latest_sched = employee.schedules.order_by('-effective_date').first()
            if not latest_sched or str(latest_sched.schedule_id) != str(sched_id):
                EmployeeSchedule.objects.create(
                    employee=employee,
                    schedule_id=sched_id,
                    effective_date=timezone.now().date() # Becomes effective immediately
                )

        # 5. Redirect and notify
        action = "updated" if pk else "added"
        messages.success(request, f"Employee {employee.get_full_name()} successfully {action}.")
        return redirect('employees:employee_list')
    
    from django.views.decorators.http import require_POST

@require_POST
def change_employee_status(request, pk):
    """Updates the employment status of an employee via the toast modal."""
    employee = get_object_or_404(Employee, employee_id=pk)
    new_status = request.POST.get('new_status')
    
    # Validate against our choices
    valid_statuses = [choice[0] for choice in Employee.STATUS_CHOICES]
    if new_status in valid_statuses:
        employee.status = new_status
        employee.save()
        messages.success(request, f"{employee.get_full_name()}'s status updated to {new_status.title()}.")
    else:
        messages.error(request, "Invalid status selected.")
        
    return redirect('employees:employee_list')

# Same din dito
def edit_form(request, pk):
    from apps.employees.models import Division, Unit, PayrollGroup, Position, WorkSchedule

    employee = get_object_or_404(Employee, employee_id=pk)

    context = {
        'employee': employee,
        'divisions': Division.objects.order_by('division_code'),
        'units': Unit.objects.select_related('division').order_by('unit_name'),
        'payroll_groups': PayrollGroup.objects.order_by('group_name'),
        'positions': Position.objects.order_by('employment_type', 'position_title'),
        'work_schedules': WorkSchedule.objects.order_by('schedule_name'),
    }
    return render(request, 'employees/form.html', context)

# def detail(request):
#     return render(request, 'employees/detail.html')

# def add_form(request):
#     return render(request, 'employees/form.html')

# def list(request):
#     return render(request, 'employees/list.html')

def employee_lookup(request):
    id_number = request.GET.get('id_number', '').strip()
    try:
        emp = Employee.objects.select_related('position', 'division').get(id_number=id_number)
        return JsonResponse({
            'found':       True,
            'employee_pk': emp.employee_id,
            'full_name':   emp.get_full_name(),
            'initials':    emp.get_initials(),
            'position':    emp.position.position_title if emp.position else '—',
            'division':    emp.division.division_name if emp.division else '—',
        })
    except Employee.DoesNotExist:
        return JsonResponse({'found': False, 'message': 'Employee ID not found.'})






