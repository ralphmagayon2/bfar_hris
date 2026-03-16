# apps/holidays/views.py
from django.shortcuts import render

def holidays(request):
    return render(request, 'holidays/list.html')
