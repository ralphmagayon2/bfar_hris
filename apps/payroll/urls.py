# apps/payroll/urls.py
from django.urls import path
from django.http import HttpResponse
from . import views

app_name = 'payroll'

urlpatterns = [
    path('', views.period_list, name='periods'),
    path('<int:period_id>/compute/', views.compute_payroll, name='compute'),
    path('<int:record_id>/payslip/', views.print_payslip, name='print_payslip'),
    path('sed/<int:emp_id>', views.sed_form, name='sed_form'),
    path('sed/<int:emp_id>/print/', views.print_sed, name='print_sed'),
]
