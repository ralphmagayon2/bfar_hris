# apps/leaves/urls.py
from django.urls import path
from django.http import HttpResponse
from . import views

app_name = 'holidays'

urlpatterns = [
    path('', views.holidays, name="list"),
]
