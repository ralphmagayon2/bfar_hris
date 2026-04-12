from django.contrib import admin
from .models import WorkSchedule, Division, Unit

@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ['schedule_name', 'is_flexible', 'working_hours_per_day', 'flex_start_earliest', 'flex_start_latest']

@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ['division_code', 'division_name', 'default_schedule']

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['unit_name', 'division', 'default_schedule']
