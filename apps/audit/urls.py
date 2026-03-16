# apps/leaves/urls.py
from django.urls import path
from django.http import HttpResponse
from . import views

app_name = 'audit'

urlpatterns = [
    # path('', views.list, name="list")
    path('', views.audit_list, name='list'),
    path('<int:log_id>/', views.audit_detail, name='detail'),
]
