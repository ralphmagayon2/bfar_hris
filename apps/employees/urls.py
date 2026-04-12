# apps/employees/urls.py
from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    path('', views.employee_list, name='employee_list'),
    
    # Point  creation and edit routes to new processing view
    path('form/', views.process_employee_form, name='form'),
    path('<int:pk>/edit/', views.process_employee_form, name='edit'),
    path('<int:pk>/status/', views.change_employee_status, name='change_status'),
    
    path('<int:pk>/', views.detail, name='detail'),

    # Schedule Management
    path('schedules/', views.schedule_list, name='schedule_list'),
    path('schedules/create/', views.schedule_form_view, name='schedule_create'),
    path('schedules/<int:pk>/edit/', views.schedule_form_view, name='schedule_edit'),
    path('schedules/<int:pk>/delete/', views.schedule_delete, name='schedule_delete'),
    path('schedules/assign-division/', views.assign_division_schedule, name='assign_division_sched'),
    path('schedules/assign-unit/', views.assign_unit_schedule, name='assign_unit_sched'),

    # Division and Units Management
    path('org/',  views.org_structure, name='org_structure'),
    path('org/divisions/create/', views.division_form_view, name='division_create'),
    path('org/divisions/<int:pk>/edit/', views.division_form_view,  name='division_edit'),
    path('org/units/create/', views.unit_form_view,  name='unit_create'),
    path('org/units/<int:pk>/edit/', views.unit_form_view, name='unit_edit'),

    # Division/Unit History Schedule Management
    path('schedules/division-history/', views.division_schedule_history, name='division_schedule_history'),
    path('schedules/delete-pushed/',    views.delete_pushed_schedule,     name='delete_pushed_schedule'),
    path('schedules/update-pushed-date/', views.update_pushed_schedule_date, name='update_pushed_date'),

    # API
    path('api/units/', views.api_units_by_division, name='api_units'),
]