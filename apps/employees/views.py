# apps/employees/views.py

from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.db.models import Count, Q
from apps.employees.models import Employee, Division
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import Employee, Division, Unit, PayrollGroup, Position, WorkSchedule, EmployeeSchedule
from apps.dtr.models import DTRRecord
from django.views.decorators.http import require_POST
from apps.accounts.views import login_required, role_required
from datetime import date as _date
from apps.audit.models import create_audit_log
from apps.accounts.utils import get_client_ip
import json
from apps.accounts.utils import clean_input, validate_phone
import re

# HELPER FUNCTIONS
def _get_schedule_name_from_ctx(sched_ctx: dict) -> str:
    """Try to find a WorkSchedule name matching the effective schedule context."""
    try:
        am_out = sched_ctx.get('am_out_expected')
        pm_out = sched_ctx.get('pm_out_expected')
        ws = WorkSchedule.objects.filter(
            am_out=am_out, pm_out=pm_out,
            is_flexible=sched_ctx.get('is_flexible', False),
        ).first()
        return ws.schedule_name if ws else 'Inherited from division/unit'
    except Exception:
        return 'Inherited from division/unit'

# Update: Para lang makita ko yung format na dinesign ko
def detail(request, pk):
    employee = get_object_or_404(Employee, employee_id=pk)

    # Government IDs — build list of (label, vlaue) pairs
    gov_ids = [
        ('TIN', getattr(employee, 'tin', None)),
        ('GSIS Number', getattr(employee, 'gsis_number', None)),
        ('PhilHealth Number', getattr(employee, 'philhealth_number', None)),
        ('Pag-IBIG / HDMF', getattr(employee, 'pagibig_number', None)),
        ('SSS Number', getattr(employee, 'sss_number', None)),
        ('PhilSys / Nat. ID', getattr(employee, 'philsys_number', None)),
    ]

    # Only show rows that have a value - based on the data you provided
    gov_ids = [(label, val) for label, val in gov_ids if val]

    context = {
        'employee': employee,
        'gov_ids': gov_ids,

        # Placeholders — replace with real queries when those apps are ready
        'dtr_summary': {'present': 0, 'absent': 0, 'late_minutes': 0, 'undertime': 0},
        'recent_dtr': [],
        'leave_credits': {'vl_balance': 0, 'sl_balance': 0, 'vl_earned_ytd': 0, 'sl_earned_ytd': 0},
        'recent_payroll': [],
        'recent_travel': [],
    }
    return render(request, 'employees/detail.html', context)

def add_form(request):
    return render(request, 'employees/form.html')

# CHANGED THE FUNCTION NAME HERE
def employee_list(request):
    # 1. optimized queryset with select_related to reduce DB kasi grabi if every row needs to access related fields in the template, mas efficient to fetch all related data in one query
    base_qs = Employee.objects.select_related('position', 'division', 'unit', 'system_user').all() # added system_user so has_account doesn't hit the DB per row and filter is_deleted here so we don't have to keep filtering it out in the code below
    
    # 2. Get the totals BEFORE applying filters
    total_all = base_qs.count()
    total_active = base_qs.filter(status='active').count()
    type_stats = base_qs.values('employment_type').annotate(count=Count('employee_id')).order_by('employment_type')
    # group by employment_type and count how many employees in each type, ordered by employment_type wow
    divisions = Division.objects.all().order_by('division_code')

    # 3. Capture URL parameters
    search_query = request.GET.get('search', '').strip()
    emp_type = request.GET.get('type', '').strip()
    div_id = request.GET.get('division', '').strip()
    status_filter = request.GET.get('status', '').strip()
    account_filter = request.GET.get('account', '').strip()

    # 4. Apply Filters to the Queryset
    if search_query:
        base_qs = base_qs.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(employee_id__icontains=search_query)
        )
    if emp_type:
        base_qs = base_qs.filter(employment_type__iexact=emp_type)
    if div_id:
        base_qs = base_qs.filter(division_id=div_id)
    if status_filter:
        base_qs = base_qs.filter(status=status_filter)

    # Account Filter    
    if account_filter == 'has_account':
        base_qs = base_qs.filter(
            system_user__isnull=False,
            system_user__is_deleted=False
        )
    elif account_filter == 'no_account':
        base_qs = base_qs.filter(
            Q(system_user__isnull=True) |
            Q(system_user__is_deleted=True)
        )

    # 5. Pagination
    paginator = Paginator(base_qs, 25)
    page_number = request.GET.get('page')
    
    employees = paginator.get_page(page_number)
    # 6. Build a query string for the pagination buttons so they remember the filters
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page'] # Remove old page number
    filter_string = query_params.urlencode()
    filter_string = f"&{filter_string}" if filter_string else ""

    context = {
        'total_all': total_all,
        'total_active': total_active,
        'type_stats': type_stats,
        'divisions': divisions,
        'employees': employees,
        # Pass current filters to keep UI updated
        'current_search': search_query,
        'current_type': emp_type,
        'current_div': div_id,
        'current_status': status_filter,
        'current_account': account_filter, # NEW: for account filter if user has employee connect and create account
        'filter_string': filter_string, # NEW: For pagination links
    }

    return render(request, 'employees/list.html', context)


def process_employee_form(request, pk=None):
    """
    Handles CREATE and UPDATE logic.
    """
    if request.method == 'GET':
        employee = get_object_or_404(Employee, employee_id=pk) if pk else None

        # Initialize defaults BEFORE the if employee: block
        current_schedule_id     = None
        current_effective_date  = None
        inherited_schedule_name = None
        next_sched              = None

        if employee:
            from apps.dtr.engine import get_effective_schedule

            latest = (EmployeeSchedule.objects
                      .filter(employee=employee)
                      .order_by('-effective_date', '-emp_schedule_id')
                      .first())

            if latest:
                current_schedule_id    = latest.schedule_id
                current_effective_date = latest.effective_date

                next_sched = (EmployeeSchedule.objects
                              .select_related('schedule')
                              .filter(
                                  employee=employee,
                                  effective_date__gt=latest.effective_date
                              )
                              .order_by('effective_date')
                              .first())
            else:
                # No personal/pushed schedule — resolve inherited for the hint
                effective = get_effective_schedule(employee, _date.today())
                inherited_schedule_name = _get_schedule_name_from_ctx(effective)
                # current_effective_date stays None — inheriting

        context = {
            'employee':              employee,
            'linked_account':        employee.linked_account if employee else None,
            'divisions':             Division.objects.order_by('division_code'),
            'units':                 Unit.objects.order_by('unit_name'),
            'payroll_groups':        PayrollGroup.objects.order_by('group_name'),
            'positions':             Position.objects.order_by('employment_type', 'position_title'),
            'work_schedules':        WorkSchedule.objects.order_by('schedule_name'),
            'current_schedule_id':   current_schedule_id,
            'current_effective_date': current_effective_date,
            'inherited_schedule_name': inherited_schedule_name,
            'next_sched':            next_sched,
            'today':                 _date.today(),
        }
        return render(request, 'employees/form.html', context)

    if request.method == 'POST':
        # 1. Fetch or initialize the Employee object
        employee = get_object_or_404(Employee, employee_id=pk) if pk else Employee()

        # 2. Map POST data to model fields

        # Step 1: Personal Info
        employee.last_name      = clean_input(request.POST.get('last_name', ''), 100)
        employee.first_name     = clean_input(request.POST.get('first_name', ''), 100)
        employee.middle_name    = clean_input(request.POST.get('middle_name', ''), 100) or None
        employee.suffix         = clean_input(request.POST.get('name_ext', ''), 10) or ''
        employee.date_of_birth  = request.POST.get('date_of_birth') or None
        employee.sex            = request.POST.get('sex')
        employee.civil_status   = request.POST.get('civil_status')
        employee.contact_number = clean_input(request.POST.get('contact_number', ''), 50) or None
        employee.email          = request.POST.get('email')
        employee.address        = clean_input(request.POST.get('address', ''), 500) or None

        # Step 2: Employment
        employee.id_number         = clean_input(request.POST.get('id_number', ''), 20)

        employment_type   = request.POST.get('employment_type')

        employment_map = {
            'Permanent': 'Permanent',
            'COS': 'COS',
            'JO': 'JO',

            # optional special dropdown values
            'nsap': 'JO',
            'nsap_fw': 'JO',
            'fishcore': 'COS',
            'adjudication': 'COS',
        }

        employee.employment_type = employment_map.get(
            employment_type,
            employment_type
        )

        employee.employment_type = employment_map.get(employment_type)

        employee.date_hired        = request.POST.get('date_hired') or None
        employee.contract_end_date = request.POST.get('contract_end_date') or None
        employee.status            = request.POST.get('status') or 'active'

        bio_id = request.POST.get('biometric_id')
        employee.biometric_id = int(bio_id) if bio_id else None

        # Foreign Keys
        employee.division_id      = request.POST.get('division')
        employee.unit_id          = request.POST.get('unit') or None
        employee.position_id      = request.POST.get('position')
        
        payroll_group_id = request.POST.get('payroll_group')
        if payroll_group_id:
            employee.payroll_group_id = payroll_group_id

        # Step 3: Salary & Payroll
        employee.monthly_salary = request.POST.get('monthly_salary')
        employee.salary_grade   = clean_input(request.POST.get('salary_grade', ''), 50) or None

        def clean_decimal(val):
            return val if val else None

        employee.gsis_monthly       = clean_decimal(request.POST.get('gsis_monthly'))
        employee.philhealth_monthly = clean_decimal(request.POST.get('philhealth_monthly'))
        employee.pagibig_monthly    = clean_decimal(request.POST.get('pagibig_monthly'))
        employee.tax_monthly        = clean_decimal(request.POST.get('tax_monthly'))

        # Government IDs
        employee.tin               = clean_input(request.POST.get('tin', ''), 50) or None
        employee.gsis_number       = clean_input(request.POST.get('gsis_number', ''), 50) or None
        employee.philhealth_number = clean_input(request.POST.get('philhealth_number', ''), 50) or None
        employee.pagibig_number    = clean_input(request.POST.get('pagibig_number', ''), 50) or None
        employee.sss_number        = clean_input(request.POST.get('sss_number', ''), 50) or None
        employee.philsys_number    = clean_input(request.POST.get('philsys_number', ''), 50) or None

        # Step 4: Schedule & Station
        employee.station = clean_input(request.POST.get('station', ''), 200) or None
        employee.remarks = clean_input(request.POST.get('remarks', ''), 1000) or None

        # Server-side field validation
        validation_errors = []

        # Required fields
        if not employee.last_name or len(employee.last_name.strip()) < 2:
            validation_errors.append('Last name must be at least 2 characters.')

        if not employee.first_name or len(employee.first_name.strip()) < 2:
            validation_errors.append('First name must be at least 2 characters.')

        if not employee.id_number:
            validation_errors.append('Biometric ID number is required.')
        elif not re.match(r'^\d+$', employee.id_number):
            validation_errors.append('Biometric ID number must contain digits only.')

        if not employee.employment_type:
            validation_errors.append('Employment type is required.')
        if not employee.date_hired:
            validation_errors.append('Date hired is required.')

        # Date of birth — must be at least 18 years old for government employees
        if employee.date_of_birth:
            from datetime import date as _date_cls
            try:
                if isinstance(employee.date_of_birth, str):
                    dob = _date_cls.fromisoformat(employee.date_of_birth)
                else:
                    dob = employee.date_of_birth
                today = _date.today()
                age = (today - dob).days // 365
                if dob >= today:
                    validation_errors.append('Date of birth cannot be today or in the future.')
                elif age < 18:
                    validation_errors.append('Employee must be at least 18 years old.')
                elif dob.year < 1900:
                    validation_errors.append('Please enter a valid date of birth.')
            except (ValueError, TypeError):
                validation_errors.append('Invalid date of birth format.')

        # Phone number — validate if provided
        if employee.contact_number:
            digits_only = re.sub(r'\D', '', employee.contact_number)
            is_valid_phone, phone_error = validate_phone(digits_only)
            if not is_valid_phone:
                validation_errors.append(f'Contact number: {phone_error}')
            else:
                # Normalize to XXXX-XXX-XXXX format
                employee.contact_number = (
                    f'{digits_only[:4]}-{digits_only[4:7]}-{digits_only[7:]}'
                )

        # Monthly salary — required, positive, within DB bounds (max_digits=10, scale=2)
        if not employee.monthly_salary:
            validation_errors.append('Monthly salary is required.')
        else:
            try:
                salary_val = float(str(employee.monthly_salary).replace(',', ''))
                if salary_val <= 0:
                    validation_errors.append('Monthly salary must be a positive number.')
                elif salary_val >= 100_000_000:
                    validation_errors.append('Monthly salary value is too large (max ₱99,999,999.99).')
                else:
                    employee.monthly_salary = round(salary_val, 2)
            except (ValueError, TypeError):
                validation_errors.append('Invalid monthly salary value.')

        # Deduction fields — optional but must be within DB bounds if provided
        # DecimalField(max_digits=10, decimal_places=2) → max value is 99,999,999.99
        _deduction_fields = [
            ('gsis_monthly',       'GSIS'),
            ('philhealth_monthly', 'PhilHealth'),
            ('pagibig_monthly',    'Pag-IBIG'),
            ('tax_monthly',        'Withholding Tax'),
        ]
        for _field_name, _label in _deduction_fields:
            _val = getattr(employee, _field_name)
            if _val:
                try:
                    _fval = float(str(_val).replace(',', ''))
                    if _fval < 0:
                        validation_errors.append(f'{_label} cannot be negative.')
                    elif _fval >= 100_000_000:
                        validation_errors.append(f'{_label} value is too large (max ₱99,999,999.99).')
                    else:
                        setattr(employee, _field_name, round(_fval, 2))
                except (ValueError, TypeError):
                    validation_errors.append(f'Invalid {_label} value.')

        # Email — basic format check if provided
        if employee.email:
            from apps.accounts.utils import is_valid_email
            if not is_valid_email(employee.email):
                validation_errors.append('Please enter a valid email address.')

        # If validation failed — rebuild context and re-render form
        if validation_errors:
            for err in validation_errors:
                messages.error(request, err)

            # Rebuild context same as GET (reuse the same variables)
            current_schedule_id     = None
            current_effective_date  = None
            inherited_schedule_name = None
            next_sched              = None

            if pk:
                latest = (employee.schedules
                        .order_by('-effective_date', '-emp_schedule_id')
                        .first())
                if latest:
                    current_schedule_id    = latest.schedule_id
                    current_effective_date = latest.effective_date
                    next_sched = (EmployeeSchedule.objects
                                .select_related('schedule')
                                .filter(employee=employee,
                                        effective_date__gt=latest.effective_date)
                                .order_by('effective_date')
                                .first())
                else:
                    from apps.dtr.engine import get_effective_schedule
                    eff = get_effective_schedule(employee, _date.today())
                    inherited_schedule_name = _get_schedule_name_from_ctx(eff)

            context = {
                'employee':               employee,
                'linked_account':         employee.linked_account if employee else None,
                'divisions':              Division.objects.order_by('division_code'),
                'units':                  Unit.objects.order_by('unit_name'),
                'payroll_groups':         PayrollGroup.objects.order_by('group_name'),
                'positions':              Position.objects.order_by('employment_type', 'position_title'),
                'work_schedules':         WorkSchedule.objects.order_by('schedule_name'),
                'current_schedule_id':    current_schedule_id,
                'current_effective_date': current_effective_date,
                'inherited_schedule_name': inherited_schedule_name,
                'next_sched':             next_sched,
                'today':                  _date.today(),
            }
            return render(request, 'employees/form.html', context)

        # 3. Save the core employee record (only if reached if validation passed)
        employee.save()

        # 4. Handle profile picture — validated and compressed
        if 'profile_picture' in request.FILES:
            profile_pic = request.FILES['profile_picture']

            # Size check — 2MB limit for employee photos
            if profile_pic.size > 5 * 1024 * 1024:
                messages.error(request, 'Profile picture is too large. Maximum size is 5 MB.')
                # Re-render form with error (rebuild context same as GET)
                # Fall through to redirect — employee record already saved above
                # so we redirect back to edit. For add, employee.pk now exists.
                if pk:
                    return redirect('employees:edit', pk=employee.employee_id)
                return redirect('employees:form')

            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
            if profile_pic.content_type not in allowed_types:
                messages.error(request, 'Invalid file type. Please upload a JPEG, PNG, or WebP image.')
                if pk:
                    return redirect('employees:edit', pk=employee.employee_id)
                return redirect('employees:form')

            try:
                from PIL import Image
                from io import BytesIO
                from django.core.files.base import ContentFile
                from django.core.files.storage import default_storage

                img = Image.open(profile_pic)

                # Convert transparency modes to RGB for JPEG output
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')

                # Resize to max 600×600 preserving aspect ratio
                if img.width > 600 or img.height > 600:
                    img.thumbnail((600, 600), Image.Resampling.LANCZOS)

                output = BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                output.seek(0)

                # Delete old picture before saving new one
                if employee.profile_picture:
                    old_name = employee.profile_picture.name
                    try:
                        if default_storage.exists(old_name):
                            default_storage.delete(old_name)
                    except Exception as del_exc:
                        import logging
                        logging.getLogger(__name__).warning(
                            '[employees] Failed to delete old profile pic: %s', del_exc
                        )

                filename = (
                    f"employee_profiles/"
                    f"emp_{employee.employee_id}_"
                    f"{timezone.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                )

                file_content = ContentFile(output.getvalue())
                saved_path   = default_storage.save(filename, file_content)
                employee.profile_picture = saved_path
                employee.save(update_fields=['profile_picture'])

            except Exception as exc:
                import logging
                logging.getLogger(__name__).error('[employees] Avatar upload error: %s', exc)
                messages.error(request, 'Error processing image. Please try a different file.')
                return redirect('employees:edit', pk=employee.employee_id)

        # 4. Handle Work Schedule Assignment (EmployeeSchedule / Table 7)
        sched_id = request.POST.get('work_schedule')

        # Parse HR-chosen effective date — fall back to today if blank/invalid
        raw_effective = request.POST.get('schedule_effective_date', '').strip()
        try:
            effective_date = _date.fromisoformat(raw_effective)
        except (ValueError, TypeError):
            effective_date = _date.today()

        # FIFO guard: clamp to today - never let a schedule be backdated
        # (past DTR records already computed with the old schedule stay correct)
        if effective_date < _date.today():
            effective_date = _date.today()
            messages.info(
                request,
                'Schedule effective date was in the past — adjusted to today to preserve existing DTR records.'
            )

        if sched_id:
            # Guard: block if this employee already has a DTR scan on the chosen date
            from apps.dtr.models import DTRRecord
            has_dtr_scan = DTRRecord.objects.filter(
                employee=employee,
                dtr_date=effective_date,
                am_in__isnull=False,
            ).exists()

            if has_dtr_scan:
                messages.error(
                    request,
                    f'Cannot set schedule effective {effective_date} — '
                    f'{employee.get_full_name()} already has a DTR scan on that date. '
                    f'Choose a different effective date.'
                )
                # Rebuild GET context and re-render form with the error
                current_schedule_id     = None
                current_effective_date  = None
                inherited_schedule_name = None
                next_sched              = None

                latest = (employee.schedules
                          .order_by('-effective_date', '-emp_schedule_id')
                          .first())

                if latest:
                    current_schedule_id    = latest.schedule_id
                    current_effective_date = latest.effective_date
                    next_sched = (EmployeeSchedule.objects
                                  .select_related('schedule')
                                  .filter(
                                      employee=employee,
                                      effective_date__gt=latest.effective_date
                                  )
                                  .order_by('effective_date')
                                  .first())
                else:
                    from apps.dtr.engine import get_effective_schedule
                    eff = get_effective_schedule(employee, _date.today())
                    inherited_schedule_name = _get_schedule_name_from_ctx(eff)

                context = {
                    'employee':               employee,
                    'linked_account':         employee.linked_account if employee else None,
                    'divisions':              Division.objects.order_by('division_code'),
                    'units':                  Unit.objects.order_by('unit_name'),
                    'payroll_groups':         PayrollGroup.objects.order_by('group_name'),
                    'positions':              Position.objects.order_by('employment_type', 'position_title'),
                    'work_schedules':         WorkSchedule.objects.order_by('schedule_name'),
                    'current_schedule_id':    current_schedule_id,
                    'current_effective_date': current_effective_date,
                    'inherited_schedule_name': inherited_schedule_name,
                    'next_sched':             next_sched,
                    'today':                  _date.today(),
                }
                return render(request, 'employees/form.html', context)

            # No DTR conflict — check for true duplicate before saving
            latest_sched = (employee.schedules
                            .order_by('-effective_date', '-emp_schedule_id')
                            .first())

            is_duplicate = (
                latest_sched and
                str(latest_sched.schedule_id) == str(sched_id) and
                latest_sched.effective_date == effective_date
            )

            if not is_duplicate:
                EmployeeSchedule.objects.update_or_create(
                    employee=employee,
                    effective_date=effective_date,
                    defaults={
                        'schedule_id': sched_id,
                        'source': 'personal',
                    }
                )

        else:
            # "Inherit from Division/Unit" selected
            # Only remove the latest personal override — never touch pushed rows
            latest_sched = (employee.schedules
                            .order_by('-effective_date', '-emp_schedule_id')
                            .first())

            if latest_sched and latest_sched.source == 'personal':
                latest_sched.delete()

        # 5. Redirect and notify
        action = "updated" if pk else "added"
        messages.success(
            request,
            f"Employee {employee.get_full_name()} successfully {action}."
        )
        return redirect('employees:employee_list')


@require_POST
def change_employee_status(request, pk):
    """Updates the employment status of an employee via the toast modal."""
    employee = get_object_or_404(Employee, employee_id=pk)
    new_status = request.POST.get('new_status')
    
    # Validate against our choices
    valid_statuses = [choice[0] for choice in Employee.STATUS_CHOICES]
    if new_status in valid_statuses:
        employee.status = new_status
        employee.save()
        messages.success(request, f"{employee.get_full_name()}'s status updated to {new_status.title()}.")
    else:
        messages.error(request, "Invalid status selected.")
        
    return redirect('employees:employee_list')

# Same din dito
def edit_form(request, pk):
    from apps.employees.models import (
        Division, Unit, PayrollGroup, Position,
        WorkSchedule, EmployeeSchedule
    )

    employee = get_object_or_404(Employee, employee_id=pk)

    latest_sched = employee.schedules.order_by(
        '-effective_date',
        '-emp_schedule_id'
    ).first()

    current_schedule_id = None
    inherited_schedule_name = None

    # Personal override exists
    if latest_sched and latest_sched.source == 'personal':
        current_schedule_id = latest_sched.schedule_id

    else:
        # Resolve inherited schedule priority:
        # Sub-unit / Unit -> Division -> Default
        if employee.unit and employee.unit.default_schedule:
            inherited_schedule_name = employee.unit.default_schedule.schedule_name

        elif employee.division and employee.division.default_schedule:
            inherited_schedule_name = employee.division.default_schedule.schedule_name

    context = {
        'employee': employee,
        'divisions': Division.objects.order_by('division_code'),
        'units': Unit.objects.select_related('division').order_by('unit_name'),
        'payroll_groups': PayrollGroup.objects.order_by('group_name'),
        'positions': Position.objects.order_by('employment_type', 'position_title'),
        'work_schedules': WorkSchedule.objects.order_by('schedule_name'),
        'current_schedule_id': current_schedule_id,
        'inherited_schedule_name': inherited_schedule_name,
    }

    return render(request, 'employees/form.html', context)

def employee_lookup(request):
    id_number = request.GET.get('id_number', '').strip()
    try:
        emp = Employee.objects.select_related('position', 'division').get(id_number=id_number)
        return JsonResponse({
            'found':       True,
            'employee_pk': emp.employee_id,
            'full_name':   emp.get_full_name(),
            'initials':    emp.get_initials(),
            'position':    emp.position.position_title if emp.position else '—',
            'division':    emp.division.division_name if emp.division else '—',
        })
    except Employee.DoesNotExist:
        return JsonResponse({'found': False, 'message': 'Employee ID not found.'})
    

# =============================== SCHEDULE MANAGEMENT SECTION ===============================
    
@login_required
@role_required('superadmin', 'hr_admin', 'hr_staff')
def schedule_list(request):
    """
    Master schedule management page.
    Shows all WorkSchedule definitions, Division defaults, and Unit defaults
    in one place so HR can assign and override without touching individual
    employee records.
    """
    schedules = WorkSchedule.objects.all().order_by('schedule_name')
    divisions = Division.objects.select_related(
        'default_schedule'
    ).order_by('division_code')
    units = Unit.objects.select_related(
        'default_schedule', 'division'
    ).order_by('division__division_code', 'unit_name')

    return render(request, 'employees/schedule_list.html', {
        'schedules': schedules,
        'divisions': divisions,
        'units':     units,
    })


@login_required
@role_required('superadmin', 'hr_admin', 'hr_staff')
def schedule_form_view(request, pk=None):
    """
    Create or edit a WorkSchedule definition.
    All time fields are configurable so HR can handle any
    compressed week, crisis hours, or special event schedule.
    """
    instance = get_object_or_404(WorkSchedule, pk=pk) if pk else None

    if request.method == 'POST':
        p = request.POST

        if instance is None:
            instance = WorkSchedule()

        instance.schedule_name         = p.get('schedule_name', '').strip()
        instance.am_in                 = p.get('am_in',  '08:00') or '08:00'
        instance.am_out                = p.get('am_out', '12:00') or '12:00'
        instance.pm_in                 = p.get('pm_in',  '13:00') or '13:00'
        instance.pm_out                = p.get('pm_out', '17:00') or '17:00'
        instance.is_flexible           = p.get('is_flexible') == '1'
        instance.is_free               = p.get('is_free') == '1' # New
        instance.working_hours_per_day = p.get('working_hours_per_day') or 8.0
        instance.flex_start_earliest   = p.get('flex_start_earliest', '07:00') or '07:00'
        instance.flex_start_latest     = p.get('flex_start_latest',   '08:00') or '08:00'

        if not instance.schedule_name:
            messages.error(request, 'Schedule name is required.')
            return render(request, 'employees/schedule_form.html', {
                'schedule': instance,
            })

        instance.save()
        action_word = 'updated' if pk else 'created'

        # AUDIT LOG
        try:
            create_audit_log(
                table_affected='work_schedules',
                record_id=instance.schedule_id,
                action='update' if pk else 'create',
                performed_by=request.current_user,
                new_value={'schedule_name': instance.schedule_name, 'is_flexible': instance.is_flexible},
                ip_address=get_client_ip(request),
                description=f'{request.current_user.username} {action_word} schedule. "{instance.schedule_name}".'
            )
        except Exception:
            pass

        messages.success(
            request,
            f'Schedule "{instance.schedule_name}" {action_word} successfully.'
        )
        return redirect('employees:schedule_list')

    return render(request, 'employees/schedule_form.html', {
        'schedule': instance,
    })


@login_required
@role_required('superadmin', 'hr_admin')
def schedule_delete(request, pk):
    """
    Delete a WorkSchedule. POST only.
    Prevents deletion if it's assigned to any division, unit,
    or employee schedule to avoid orphaned references.
    """
    if request.method == 'POST':
        sched = get_object_or_404(WorkSchedule, pk=pk)

        # Safety check — block deletion if in use
        div_count  = Division.objects.filter(default_schedule=sched).count()
        unit_count = Unit.objects.filter(default_schedule=sched).count()
        emp_count  = EmployeeSchedule.objects.filter(schedule=sched).count()

        if div_count or unit_count or emp_count:
            messages.error(
                request,
                f'Cannot delete "{sched.schedule_name}" — it is assigned to '
                f'{div_count} division(s), {unit_count} unit(s), '
                f'and {emp_count} employee(s). Remove those assignments first.'
            )
        else:
            name = sched.schedule_name
            # AUDIT LOG
            try:
                create_audit_log(
                    table_affected='work_schedules',
                    record_id=pk,
                    action='delete',
                    performed_by=request.current_user,
                    old_value={'schedule_name': name},
                    ip_address=get_client_ip(request),
                    description=f'{request.current_user.username} deleted schedule "{name}".'
                )
            except Exception:
                pass
                
            sched.delete()
            messages.success(request, f'Schedule "{name}" deleted.')

    return redirect('employees:schedule_list')


def _push_schedule_to_employees(employee_qs, schedule, force=False, effective_date=None):
    today = timezone.now().date()
    push_date = effective_date or today

    # FIFO guard: never allow effective date in the past
    # Past dates would silently change schedule resolution for existing DTR records
    if push_date < today:
        push_date = today

    pushed = 0

    for emp in employee_qs:
        latest_sched = emp.schedules.order_by(
            '-effective_date', '-emp_schedule_id'
        ).first()

        # Skip personal override UNLESS force=True
        if not force and latest_sched and latest_sched.source == 'personal':
            continue
            
        # Avoid duplicate pushed schedule (same schedule, same source, regarless of date)
        if (not force and latest_sched and
            latest_sched.schedule_id == schedule.schedule_id and
            latest_sched.source == 'pushed' and
            latest_sched.effective_date == today):
            continue

        EmployeeSchedule.objects.update_or_create(
            employee=emp,
            effective_date=push_date,
            defaults={
                'schedule': schedule,
                'source': 'pushed',
            }
        )
        pushed += 1

    return pushed

def assign_division_schedule(request):
    if request.method == 'POST':
        div_id   = request.POST.get('division_id')
        sched_id = request.POST.get('schedule_id') or None
        push     = request.POST.get('push_to_employees') == '1'
        force    = request.POST.get('force_push') == '1'

        # Parse effective date
        raw_eff = request.POST.get('push_effective_date', '').strip()
        try:
            push_effective = _date.fromisoformat(raw_eff)
        except (ValueError, TypeError):
            push_effective = None

        div = get_object_or_404(Division, pk=div_id)
        div.default_schedule_id = sched_id
        div.save()

        pushed = 0
        if push and sched_id:
            sched  = WorkSchedule.objects.get(pk=sched_id)
            emp_qs = Employee.objects.filter(division=div, status='active')
            pushed = _push_schedule_to_employees(emp_qs, sched, force=force, effective_date=push_effective)

        sched_name = WorkSchedule.objects.get(pk=sched_id).schedule_name if sched_id else 'cleared'

        # AUDIT LOG
        try:
            create_audit_log(
                table_affected='divisions',
                record_id=div.division_id,
                action='update',
                performed_by=request.current_user,
                new_value={'default_schedule_id': sched_id, 'pushed': pushed},
                ip_address=get_client_ip(request),
                description=f'{request.current_user.username} set division "{div.division_name}" schedule to "{sched_name}" (Pushed to {pushed} employees).'
            )
        except Exception:
            pass

        msg = f'{div.division_name} schedule set to: {sched_name}.'
        if pushed:
            msg += f' Pushed to {pushed} employee(s).'
        messages.success(request, msg)

    return redirect('employees:schedule_list')


def assign_unit_schedule(request):
    if request.method == 'POST':
        unit_id  = request.POST.get('unit_id')
        sched_id = request.POST.get('schedule_id') or None
        push     = request.POST.get('push_to_employees') == '1'
        force    = request.POST.get('force_push') == '1'

        raw_eff = request.POST.get('push_effective_date', '').strip()
        try:
            push_effective = _date.fromisoformat(raw_eff)
        except (ValueError, TypeError):
            push_effective = None

        unit = get_object_or_404(Unit, pk=unit_id)
        unit.default_schedule_id = sched_id
        unit.save()

        pushed = 0
        if push and sched_id:
            sched = WorkSchedule.objects.get(pk=sched_id)

            def _collect_unit_ids(u):
                ids = [u.unit_id]
                for sub in Unit.objects.filter(parent_unit=u):
                    ids.extend(_collect_unit_ids(sub))
                return ids

            all_unit_ids = _collect_unit_ids(unit)
            emp_qs = Employee.objects.filter(unit_id__in=all_unit_ids, status='active')
            pushed = _push_schedule_to_employees(emp_qs, sched, force=force, effective_date=push_effective)

        sched_name = WorkSchedule.objects.get(pk=sched_id).schedule_name if sched_id else 'cleared'

        # AUDIT LOG
        try:
            create_audit_log(
                table_affected='units',
                record_id=unit.unit_id,
                action='update',
                performed_by=request.current_user,
                new_value={'default_schedule_id': sched_id, 'pushed': pushed},
                ip_address=get_client_ip(request),
                description=f'{request.current_user.username} set unit "{unit.unit_name}" schedule to "{sched_name}" (Pushed to {pushed} employees).'
            )
        except Exception:
            pass

        msg = f'{unit.unit_name} schedule set to: {sched_name}.'
        if pushed:
            msg += f' Pushed to {pushed} employee(s).'
        messages.success(request, msg)

    return redirect('employees:schedule_list')

# ----- DIVISION & UNIT MANAGEMENT VIEWS -----
@login_required
@role_required('superadmin', 'hr_admin')
def org_structure(request):
    """
    Master org structure page.
    Lists all divisions with their units and sub-units.
    HR can create/edit/deactivate from here.
    """
    divisions = Division.objects.prefetch_related(
        'units',
        'units__sub_units',
        'units__default_schedule',
        'units__sub_units__default_schedule',
        'default_schedule',
    ).order_by('division_code')

    work_schedules = WorkSchedule.objects.order_by('schedule_name')

    return render(request, 'employees/org_structure.html', {
        'divisions':      divisions,
        'work_schedules': work_schedules,
    })


@login_required
@role_required('superadmin', 'hr_admin')
def division_form_view(request, pk=None):
    instance = get_object_or_404(Division, pk=pk) if pk else None

    if request.method == 'POST':
        p = request.POST
        if not instance:
            instance = Division()

        instance.division_code = p.get('division_code', '').strip().upper()
        instance.division_name = p.get('division_name', '').strip()
        instance.work_schedule_type = p.get('work_schedule_type', 'fixed')
        sched_id = p.get('default_schedule') or None
        instance.default_schedule_id = sched_id

        if not instance.division_code or not instance.division_name:
            messages.error(request, 'Division code and name are required.')
        else:
            instance.save()
            action = 'updated' if pk else 'created'
            messages.success(
                request,
                f'Division "{instance.division_name}" {action}.'
            )
            return redirect('employees:org_structure')

    work_schedules = WorkSchedule.objects.order_by('schedule_name')
    return render(request, 'employees/division_form.html', {
        'division':      instance,
        'work_schedules': work_schedules,
    })


@login_required
@role_required('superadmin', 'hr_admin')
def unit_form_view(request, pk=None):
    instance = get_object_or_404(Unit, pk=pk) if pk else None

    if request.method == 'POST':
        p = request.POST
        if not instance:
            instance = Unit()

        instance.unit_name   = p.get('unit_name', '').strip()
        div_id               = p.get('division_id') or None
        instance.division_id = div_id
        parent_id            = p.get('parent_unit_id') or None
        instance.parent_unit_id = parent_id
        sched_id             = p.get('default_schedule') or None
        instance.default_schedule_id = sched_id

        if not instance.unit_name or not div_id:
            messages.error(request, 'Unit name and division are required.')
        else:
            instance.save()
            action = 'updated' if pk else 'created'
            messages.success(request, f'Unit "{instance.unit_name}" {action}.')
            return redirect('employees:org_structure')

    divisions      = Division.objects.order_by('division_code')
    # Only top-level units can be parents (no grandparent chains)
    parent_units   = Unit.objects.filter(
        parent_unit__isnull=True
    ).select_related('division').order_by('division__division_code', 'unit_name')
    work_schedules = WorkSchedule.objects.order_by('schedule_name')

    return render(request, 'employees/unit_form.html', {
        'unit':          instance,
        'divisions':     divisions,
        'parent_units':  parent_units,
        'work_schedules': work_schedules,
    })

# API that return filtered units by division including sub-units
# group under their parents

def api_units_by_division(request):
    """
    Returns units (and sub-units) for a given division_id.
    Used by the employee form to filter the unit dropdown.
    Response format:
    [
        {"id": 1, "name": "Aurora", "parent_id": null},
        {"id": 5, "name": "Baler Satellite", "parent_id": 1},
    ]
    """
    div_id = request.GET.get('division_id')
    if not div_id:
        return JsonResponse({'units': []})

    units = Unit.objects.filter(
        division_id=div_id
    ).select_related('parent_unit').order_by('parent_unit__unit_name', 'unit_name')

    data = []
    for u in units:
        data.append({
            'id': u.unit_id,
            'name': u.unit_name,
            'parent_id': u.parent_unit_id,
        })
    
    return JsonResponse({'units': data})

# ===== DIVISION/UNIT HISTORY PANEL VIEWS ======
@login_required
@role_required('superadmin', 'hr_admin', 'hr_staff')
def division_schedule_history(request):
    """
    Returns all EmployeeSchedule rows pushed to a division's employees,
    grouped by effective_date + schedule, as JSON for the schedule_list page.
    """
    div_id = request.GET.get('division_id')
    if not div_id:
        return JsonResponse({'rows': []})

    rows = (EmployeeSchedule.objects
            .select_related('schedule', 'employee')
            .filter(
                employee__division_id=div_id,
                source='pushed'
            )
            .order_by('-effective_date', 'schedule__schedule_name'))

    # Group: effective_date + schedule_id → count of employees
    from collections import defaultdict
    groups = defaultdict(lambda: {'count': 0, 'emp_ids': [], 'emp_schedule_ids': []})
    for row in rows:
        key = f"{row.effective_date}|{row.schedule_id}"
        groups[key]['schedule_name']      = row.schedule.schedule_name
        groups[key]['effective_date']     = row.effective_date.strftime('%Y-%m-%d')
        groups[key]['effective_date_disp']= row.effective_date.strftime('%b %d, %Y')
        groups[key]['schedule_id']        = row.schedule_id
        groups[key]['count']             += 1
        groups[key]['emp_schedule_ids'].append(row.emp_schedule_id)

    return JsonResponse({'rows': list(groups.values())})


@login_required
@role_required('superadmin', 'hr_admin')
def delete_pushed_schedule(request):
    """
    Delete a batch of EmployeeSchedule rows (pushed) by emp_schedule_ids.
    POST: { emp_schedule_ids: [1, 2, 3] }
    """
    if request.method == 'POST':
        import json
        try:
            body = json.loads(request.body)
            ids  = body.get('emp_schedule_ids', [])
        except Exception:
            ids = request.POST.getlist('emp_schedule_ids')

        deleted, _ = EmployeeSchedule.objects.filter(
            emp_schedule_id__in=ids,
            source='pushed'   # safety — never delete personal overrides here
        ).delete()

        # AUDIT LOG
        if deleted:
            try:
                create_audit_log(
                    table_affected='employee_schedules',
                    record_id=0, # 0 indicates bulk action
                    action='delete',
                    performed_by=request.current_user,
                    old_value={'emp_schedule_ids_deleted': ids},
                    ip_address=get_client_ip(request),
                    description=f'{request.current_user.username} bulk removed {deleted} pushed schedule assignments.'
                )
            except Exception:
                pass

        return JsonResponse({'deleted': deleted})

    return JsonResponse({'error': 'POST required'}, status=405)


@login_required
@role_required('superadmin', 'hr_admin')
def update_pushed_schedule_date(request):
    """
    Update the effective_date for a batch of pushed EmployeeSchedule rows.
    POST: { emp_schedule_ids: [1,2,3], new_date: '2026-04-15' }
    Guards against dates that already have DTR data for those employees.
    """
    if request.method == 'POST':
        import json
        try:
            body     = json.loads(request.body)
            ids      = body.get('emp_schedule_ids', [])
            new_date = _date.fromisoformat(body.get('new_date', ''))
        except Exception:
            return JsonResponse({'error': 'Invalid payload'}, status=400)

        # FIFO guard
        from datetime import date as _date_cls
        if new_date < _date_cls.today():
            return JsonResponse({
                'error': 'Effective date cannot in the past. Choose today or a future date to preserve existing DTR records.'
            }, status=400)

        # Check for existing DTR records on the new date for affected employees
        emp_ids = list(
            EmployeeSchedule.objects
            .filter(emp_schedule_id__in=ids)
            .values_list('employee_id', flat=True)
        )
        conflicts = DTRRecord.objects.filter(
            employee_id__in=emp_ids,
            dtr_date=new_date,
            am_in__isnull=False   # only block if actual scan exists
        ).count()

        if conflicts:
            return JsonResponse({
                'error': f'{conflicts} employee(s) already have DTR scans on {new_date}. Choose a different date.'
            }, status=400)

        # Safe to update
        updated = EmployeeSchedule.objects.filter(
            emp_schedule_id__in=ids,
            source='pushed'
        ).update(effective_date=new_date)

        # AUDIT LOG
        if updated:
            try:
                create_audit_log(
                    table_affected='employee_schedules',
                    record_id=0, # 0 indicates bulk action
                    action='update',
                    performed_by=request.current_user,
                    new_value={'new_effective_date': str(new_date), 'records_updated': updated},
                    ip_address=get_client_ip(request),
                    description=f'{request.current_user.username} bulk updated effective date to {new_date} for {updated} pushed schedules.'
                )
            except Exception:
                pass

        return JsonResponse({'updated': updated})

    return JsonResponse({'error': 'POST required'}, status=405)