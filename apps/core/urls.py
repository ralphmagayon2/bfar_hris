# apps/core/urls.py
from django.urls import path
from django.http import HttpResponse
from . import views

app_name = 'core'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    # Testing the error pages
    path("test-403/", views.error_403, name="test_403"),
    path("test-404/", views.error_404, name="test_404"),
    path("test-500/", views.error_500, name="test_500"),

    path('base-print/', views.base_print, name="base_print"),
    path('base-email/', views.base_email, name="base_email"),

    path('account-created/', views.account_created_email, name="account_created"),
    path('leave-status/', views.leave_status_email, name="leave_status"),
    path('password-reset/', views.password_reset_email, name="password_reset"),
    path('payslip-ready/', views.payslip_ready, name="payslip_ready"),
    path('travel-order-encoded/', views.travel_order_encoded_email, name="travel_order_enocded"),
]
