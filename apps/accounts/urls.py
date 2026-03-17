# apps/accounts/urls.py
from django.urls import path
from django.http import HttpResponse
from . import views

app_name = 'accounts'

urlpatterns = [

    # Employee Login and Signup and Logout
    path('login/',                          views.employee_login,       name='login'),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.logout, name='logout'),

    # Employee Forgot Password and Reset Password
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password, name='reset_password'),

    # Admin Portal
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/signup/', views.admin_signup, name='admin_signup'),
    path('admin/forgot-password/', views.admin_forgot_password, name='admin_forgot_password'),

    # Employee and HR Employees Profile
    path('profile/', views.profile, name='profile'),

    # User Management (Superadmin only)
    path('employees/create/', views.create_employee, name='create_employee'),
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_system_user, name='create_system_user'),
    path('users/<int:user_id>/toggle/', views.toggle_user_active, name='toggle_user_active'),
    
    # AJAX (authenticated)
    path('api/employee-lookup/', views.employee_lookup, name='employee_lookup'),
 
    # AJAX (public — used by signup wizard pane 1)
    path('api/employee-lookup-public/', views.employee_lookup_public, name='employee_lookup_public'),
]
