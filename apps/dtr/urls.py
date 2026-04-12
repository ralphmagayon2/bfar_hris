# apps/dtr/urls.py
from django.urls import path
from . import views

app_name = 'dtr'

urlpatterns = [
    path('', views.dtr_list, name='dtr_list'),

    # Employee DTR detail - monthly view per employee
    path('employee/<int:emp_id>/', views.dtr_detail,  name='detail'),
    # path('edit/<int:dtr_id>/',  views.dtr_edit, name='edit'),
    # Manual entry — HR adds or overwrites DTR for one employee/day
    path('employee/<int:emp_id>/add/', views.dtr_manual_entry, name='manual_entry'),
    # Print ready dtr
    path('print/<int:emp_id>/', views.dtr_print, name='print_dtr'),

    # Viewer self-services — read-only
    path('my/', views.my_dtr, name='my_dtr'),
    path('my/print/', views.my_dtr_print, name='my_dtr_print'),

    # API
    path('api/<int:emp_id>/by-date/', views.get_dtr_by_date, name='dtr_by_date'),
]