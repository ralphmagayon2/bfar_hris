# apps/leaves/urls.py
from django.urls import path
from django.http import HttpResponse
from . import views

app_name = 'biometrics'

urlpatterns = [
    path('', views.devices, name='devices'),
    path('receive/', views.receive_push, name='receive'),
    path('status/', views.status, name='status'),
]
