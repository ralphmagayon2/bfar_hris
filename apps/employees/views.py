# apps/employees/views.py

from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.db.models import Count, Q
from apps.employees.models import Employee, Division

def detail(request):
    return render(request, 'employees/detail.html')

def add_form(request):
    return render(request, 'employees/form.html')

# CHANGED THE FUNCTION NAME HERE
def employee_list(request):
    # 1. optimized queryset with select_related to reduce DB kasi grabi if every row needs to access related fields in the template, mas efficient to fetch all related data in one query
    base_qs = Employee.objects.select_related('position', 'division', 'unit').all() 
    
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
        'filter_string': filter_string, # NEW: For pagination links
    }

    return render(request, 'employees/list.html', context)

def edit_form(request):
    return render(request, 'employees/form.html')

from django.shortcuts import render, redirect

def detail(request):
    return render(request, 'employees/detail.html')

def add_form(request):
    return render(request, 'employees/form.html')

def list(request):
    return render(request, 'employees/list.html')

def edit_form(request):
    return render(request, 'employees/form.html')

from django.http import JsonResponse
from apps.employees.models import Employee

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
    
from django.http import JsonResponse
# from apps.employees.models import Employee  <-- You can remove this duplicate import now

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






