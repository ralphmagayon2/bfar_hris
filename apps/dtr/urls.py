# apps/dtr/urls.py
from django.urls import path
from . import views

app_name = 'dtr'

urlpatterns = [
    path('', views.dtr_list, name='dtr_list'),
    path('<int:emp_id>/', views.dtr_detail, name='detail'),
    path('edit/<int:dtr_id>/', views.dtr_edit, name='edit'),
    path('<int:emp_id>/print/', views.dtr_print, name='print_dtr'),
    # path('print/', views.dtr_print, name='print_dtr'),
]