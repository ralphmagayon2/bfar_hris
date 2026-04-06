# apps/holidays/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db import IntegrityError # <-- NEW: Import the error handler
from datetime import timedelta
from .models import Holiday

def holidays_list(request):
    # ─── POST: Handle Form Submissions (Add, Edit, Delete) ──────────
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_holiday':
            name = request.POST.get('name')
            date = request.POST.get('date') # Format: YYYY-MM-DD
            h_type = request.POST.get('holiday_type')
            
            # Extract the year from the submitted date string (first 4 characters)
            submitted_year = date[:4] 
            
            # SMART CHECK: Does a holiday with this exact name already exist in this year?
            if Holiday.objects.filter(holiday_name__iexact=name, holiday_date__year=submitted_year).exists():
                messages.error(request, f"Failed: '{name}' already exists in {submitted_year}.")
                return redirect('holidays:holiday_list')
            
            try:
                Holiday.objects.create(
                    holiday_name=name,
                    holiday_date=date,
                    holiday_type=h_type
                )
                messages.success(request, f"Holiday '{name}' added successfully.")
            except IntegrityError:
                messages.error(request, f"Failed: A holiday already exists on {date}.")
                
            return redirect('holidays:holiday_list')
            
        elif action == 'edit_holiday':
            h_id = request.POST.get('holiday_id')
            name = request.POST.get('name')
            date = request.POST.get('date')
            h_type = request.POST.get('holiday_type')
            
            holiday = get_object_or_404(Holiday, pk=h_id)
            submitted_year = date[:4]
            
            # SMART CHECK: Does it exist in this year, AND is it NOT the holiday we are currently editing?
            if Holiday.objects.filter(holiday_name__iexact=name, holiday_date__year=submitted_year).exclude(pk=h_id).exists():
                messages.error(request, f"Failed: '{name}' already exists in {submitted_year}.")
                return redirect('holidays:holiday_list')
            
            holiday.holiday_name = name
            holiday.holiday_date = date
            holiday.holiday_type = h_type
            
            try:
                holiday.save()
                messages.success(request, f"Holiday '{name}' updated successfully.")
            except IntegrityError:
                messages.error(request, f"Failed: Cannot move to {date}. Another holiday already exists there.")
                
            return redirect('holidays:holiday_list')
            
        elif action == 'delete':
            h_id = request.POST.get('holiday_id')
            holiday = get_object_or_404(Holiday, pk=h_id)
            name = holiday.holiday_name
            holiday.delete()
            
            messages.success(request, f"Holiday '{name}' has been deleted.")
            return redirect('holidays:holiday_list')

# ───────── GET: Read ─────────
    
    today = timezone.localdate()
    thirty_days_from_now = today + timedelta(days=30)
    
    all_holidays = Holiday.objects.all().order_by('holiday_date')
    
    # NEW: Extract distinct years from the database, sorted newest to oldest
    available_years = sorted(list(set(h.holiday_date.year for h in all_holidays)), reverse=True)
    
    # If the database is completely empty, default to current year so the UI doesn't break
    if not available_years:
        available_years = [today.year]

    summary = {
        'regular': all_holidays.filter(holiday_type='regular').count(),
        'special': all_holidays.filter(holiday_type__in=['special', 'local']).count(), 
        'upcoming': all_holidays.filter(holiday_date__gte=today, holiday_date__lte=thirty_days_from_now).count()
    }

    context = {
        'holidays': all_holidays,
        'summary': summary,
        'today': today,
        'available_years': available_years, # NEW: Pass the years to the template
    }
    return render(request, 'holidays/list.html', context)