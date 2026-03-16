# apps/employees/views.py
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