# apps/payroll/views.py
from django.shortcuts import render, redirect

def payroll_list(request):
    return render(request, 'payroll/payroll_list.html')

def period_list(request):
    return render(request, 'payroll/period_list.html')

def print_payslip(request):
    return render(request, 'payroll/print_payslip.html')

def print_sed(request):
    return render(request, 'payroll/print_sed.html')

def sed_form(request):
    return render(request, 'payroll/sed_form.html')

def compute_payroll(request):
    return render(request, 'payroll/payroll_list.html')