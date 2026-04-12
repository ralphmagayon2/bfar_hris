# apps/leaves/urls.py
from django.urls import path
from django.http import HttpResponse
from . import views

app_name = 'leaves'

urlpatterns = [
    path('', views.list, name='leave_list'),
    path('<int:pk>/elr/', views.elr, name='elr'),
    path('<int:pk>/elr/print/', views.print_elr, name='print_elr'),
]
"""
urlpatterns = [
    path('', views.list, name='leave_list'),
    path('<int:emp_id>/', views.elr, name="elr"),
    path('<int:emp_id>/print/', views.print_elr, name="print_elr"),
]
"""