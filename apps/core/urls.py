# apps/core/urls.py
from django.urls import path
from django.http import HttpResponse
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    # Testing the error pages
    path("test-403/", views.error_403, name="test_403"),
    path("test-404/", views.error_404, name="test_404"),
    path("test-500/", views.error_500, name="test_500"),

    path('base-print/', views.base_print, name="base_print"),
]
