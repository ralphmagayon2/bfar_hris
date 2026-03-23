# apps/leaves/urls.py
from django.urls import path
from django.http import HttpResponse
from . import views

app_name = 'employees'

urlpatterns = [
    path('', views.employee_list, name='employee_list'),
    path('form/', views.add_form, name='form'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/edit/', views.edit_form, name='edit'),
]


