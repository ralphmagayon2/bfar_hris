# apps/employees/views.py

from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.db.models import Count, Q
from apps.employees.models import Employee, Division
from django.shortcuts import get_object_or_404
from django.http import JsonResponse

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
    base_qs = Employee.objects.select_related('position', 'division', 'unit', 'system_user').all() # added system_user so has_account doesn't hit the DB per row
    
    # 2. Get the totals BEFORE applying filters
    total_all = base_qs.count()
    total_active = base_qs.filter(is_active=True).count()
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
    if status_filter == 'active':
        base_qs = base_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        base_qs = base_qs.filter(is_active=False)

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






