# apps/travel_orders/urls.py
from django.urls import path
from . import views

app_name = 'travel_orders'

urlpatterns = [
    path('', views.to_list, name='to_list'),
    path('add/', views.to_create, name='create'),
    path('<int:to_id>/edit/', views.to_edit, name='edit'),
    path('<int:to_id>/delete/', views.to_delete, name='delete'),
]