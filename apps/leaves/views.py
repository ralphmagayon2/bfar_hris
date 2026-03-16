# apps/leaves/views.py
from django.shortcuts import render, redirect

def elr(request):
    return render(request, 'leaves/elr.html')

def print_elr(request):
    return render(request, 'leaves/print_elr.html')

def list(request):
    return render(request, 'leaves/list.html')