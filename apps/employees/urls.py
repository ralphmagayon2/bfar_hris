# apps/employees/urls.py
from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    path('', views.employee_list, name='employee_list'),
    
    # Point  creation and edit routes to new processing view
    path('form/', views.process_employee_form, name='form'),
    path('<int:pk>/edit/', views.process_employee_form, name='edit'),
    
    path('<int:pk>/', views.detail, name='detail'),
]