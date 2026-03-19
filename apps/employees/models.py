# apps/employees/models.py

"""
BFAR REGION III - HRIS
Employee Registry, Organizational Stucture, and Schedule Models

These are the foundation tables - every other app (dtr, payroll, leaves, biometrics) has Foreignkey references pointing back to employee

Models:
    1. Division          → TABLE 1  (divisions)
    2. Unit              → TABLE 2  (units)
    3. PayrollGroup      → TABLE 3  (payroll_groups)
    4. Position          → TABLE 4  (positions)
    5. Employee          → TABLE 5  (employees)
    6. WorkSchedule      → TABLE 6  (work_schedules)
    7. EmployeeSchedule  → TABLE 7  (employee_schedules)
"""

from django.db import models
import pytz

# HELPER MIXIN - Philippine Timezone

class PhilippinesTimeMixin:
    """
    Reusable mixin that converts any DateTimeField to Asia/Manila timezone.
    Add to any model that has timestamp fields you want to display in PH time.
    """
    def get_ph_time(self, field_name):
        field_value = getattr(self, field_name, None)
        if field_value:
            ph_tz = pytz.timezone('Asia/Manila')
            return field_value.astimezone(ph_tz)
        return None
    
    def get_formatted_ph_time(self, field_name):
        ph_time = self.get_ph_time(field_name)
        return ph_time.strftime('%B %d, %Y at %I:%M %p') if ph_time else None
    

# TABLE 1 - DIVISION
# Stores the 5 main divisions of BFAR Region III

class Division(PhilippinesTimeMixin, models.Model):

    WORK_SCHEDULE_CHOICES = [
        ('fixed', 'Fixed (8AM-5Pm)'),
        ('flexible', 'Flexible (FishCore)'),
    ]

    division_id = models.AutoField(primary_key=True)
    division_code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Short code e.g., ORD, FPSSD, FMRED, PFO, TOSS"
    )
    
    division_name = models.CharField(
        max_length=200,
        help_text="Full name e.g., Office of the Regional Director"
    )

    work_schedule_type = models.CharField(
        max_length=10,
        choices=WORK_SCHEDULE_CHOICES,
        default='fixed',
        help_text="Fixed = 8AM-5PM | Flexible = FishCore type"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # ----- PH Time Helpers -----
    def get_created_at_ph(self):
        return self.get_ph_time('created_at')
    
    def get_formatted_created_at_ph(self):
        return self.get_formatted_ph_time('created_at')
    
    def __str__(self):
        return f"{self.division_code} — {self.division_name}"
    
    class Meta:
        db_table = 'divisions'
        ordering = ['division_code']
        verbose_name = 'Division'
        verbose_name_plural = 'Divisions'

     # ── Seed Data (for reference / fixtures) ─────────────────────────────────
    # ORD   → Office of the Regional Director           (fixed)
    # FPSSD → Fisheries Production and Support Services Division (fixed)
    # FMRED → Fisheries Management, Regulatory and Enforcement Division (fixed)
    # PFO   → Provincial Fisheries Office               (fixed)
    # TOSS  → Technology Outreach Stations/Satellite Stations (flexible)

# TABLE 2 - Unit
# Stores all Unit/Section/Sub-station under each Division
# Support parent-child relationship for satellite stations.

class Unit(PhilippinesTimeMixin, models.Model):

    unit_id = models.AutoField(primary_key=True)
    division = models.ForeignKey(
        Division,
        on_delete=models.PROTECT,
        related_name='units',
        help_text="Which division this unit belongs to"
    )
    
    unit_name = models.CharField(
        max_length=200,
        help_text="e.g., Planning Unit, Accounting Unit, Aurora Province"
    )

    parent_unit = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sub_units',
        help_text="For sub-station: Baler Satellite -> Aurora Brackishwater parent"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # ----- PH Time Helpers ------
    def get_created_at_ph(self):
        return self.get_ph_time('created_at')
    
    def get_formatted_created_at_ph(self):
        return self.get_formatted_ph_time('created_at')
    
    def get_full_path(self):
        """Return e.g.g, 'FPSDD' > Aurora Province > Baler Satellite """
        if self.parent_unit:
            return f"{self.parent_unit.get_full_path()} > {self.unit_name}"
        return f"{self.division.division_code} > {self.unit_name}"
    
    def __str__(self):
        return f"{self.division.division_code} — {self.unit_name}"
    
    class Meta:
        db_table = 'units'
        ordering = ['division__division_code', 'unit_name']
        verbose_name = 'Unit'
        verbose_name_plural = 'Units'

# TABLE 3 - Payroll Group
# The 7 district payroll groups
# Determines which contribution scheme (GSIS VS SSS) applies

class PayrollGroup(PhilippinesTimeMixin, models.Model):

    EMPLOYMENT_TYPE_CHOICES = [
        ('Permanent', 'Permanent'),
        ('COS', 'Contract of Service'),
        ('JO', 'Job Order'),
    ]

    CONTRIBUTION_SCHEME_CHOICES = [
        ('GSIS', 'GSIS (Permanent)'),
        ('SSS', 'SSS (All)'),
        ('PhilHealth', 'PhilHealth (All)'),
        ('Pag-Ibig', 'Pag-Ibig (All)'),
    ]

    group_id = models.AutoField(primary_key=True)
    group_name = models.CharField(
        max_length=100,
        help_text=(
            "e.g. Contract of Service | Job Order | NSAP Enumerator | NSAP Freshwater | FishCore | Adjudication | Permanent"
        )
    )

    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPE_CHOICES,
        help_text="Primary employment classification"
    )
    contribution_scheme = models.CharField(
        max_length=10,
        choices=CONTRIBUTION_SCHEME_CHOICES,
        help_text="GSIS for Permanent, SSS for all others"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # ------ PH Time Helpers ------
    def get_created_at_ph(self):
        return self.get_ph_time('created_at')
    
    def get_formatted_created_at_ph(self):
        return self.get_formatted_ph_time('created_at')
    
    def is_permanent(self):
        """True if this group uses GSIS (Permanent employees)"""
        return self.contribution_scheme == 'GSIS'

    def __str__(self):
        return f"{self.group_name} ({self.contribution_scheme})"
    
    class Meta:
        db_table = 'payroll_groups'
        ordering= ['group_name']
        verbose_name = 'Payroll Group'
        verbose_name_plural = 'Payroll Groups'

    # ── Seed Data (for reference / fixtures) ─────────────────────────────────
    # Permanent          → Permanent → GSIS
    # Contract of Service → COS      → SSS
    # Job Order          → JO        → SSS
    # NSAP Enumerator    → JO        → SSS
    # NSAP Freshwater    → JO        → SSS
    # FishCore           → COS       → SSS
    # Adjudication       → COS       → SSS

# TABLE 4 - Position
# Job positions. HR inputs these manually as they vary per employees.

class Position(PhilippinesTimeMixin, models.Model):

    EMPLOYMENT_TYPE_CHOICE = [
        ('Permanent', 'Permanent'),
        ('COS', 'Contract of Service'),
        ('JO', 'Job Order'),
    ]

    position_id = models.AutoField(primary_key=True)
    position_title = models.CharField(
        max_length=200,
        help_text=(
            "e.g. Fishery Technologist II,"
            "Administrative Aide IV, Driver II"
        )
    )

    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPE_CHOICE,
        help_text="Which employment type this position belongs to"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # ----- PH Time Helpers ------
    def get_created_at_ph(self):
        return self.get_ph_time('created_at')
    
    def get_formatted_created_at_ph(self):
        return self.get_formatted_ph_time('created_at')
    
    def __str__(self):
        return f"{self.position_title} ({self.employment_type})"
    
    class Meta:
        db_table = 'positions'
        ordering = ['employment_type', 'position_title']
        verbose_name = 'Position'
        verbose_name_plural = 'Positions'

# TABLE 5 - Employee
# Core enrollment table. Links to Division, Unit, Position, and PayrollGroup.
# Stores encrypted biometric templates (fingerprint + face)

class Employee(PhilippinesTimeMixin, models.Model):

    EMPLOYMENT_TYPE_CHOICES = [
        ('Permanent', 'Permanent'),
        ('COS', 'Contract of Service'),
        ('JO', 'Job Order'),
    ]

    # ----- Primary Key ------
    employee_id = models.AutoField(
        primary_key=True,
        help_text="Internal system ID (auto-generated)"
    )

    id_number = models.CharField(
        max_length=20,
        unique=True,
        help_text="Biometric device number e.g. 000000001"
    )

    # ----- Name Fields ------
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    suffix = models.CharField(
        max_length=10,
        blank=True,
        help_text="Jr., Sr., III, etc."
    )

    # ----- Organizational Assignment
    division = models.ForeignKey(
        Division,
        on_delete=models.PROTECT,
        related_name='employees',
        null=True,
        blank=True,
        help_text="Assigned division"
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Assigned unit/section"
    )
    payroll_group = models.ForeignKey(
        PayrollGroup,
        on_delete=models.PROTECT,
        related_name='employees',
        null=True,
        blank=True,
        help_text="Which payroll list they belong to"
    )

    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name='employees',
        null=True,
        blank=True,
        help_text="Job position"
    )

    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPE_CHOICES,
        help_text="Primary employment classificatin"
    )

    # ------ Salary -----
    monthly_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Basic monthly salary (HR inputs this)"
    )

    pera = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=2000.00,
        help_text="Personnel Economic Relief Allowance - fiexd ₱2,000 for Permanent"
    )

    # ----- Employment Date
    date_hired = models.DateField(
        help_text="Date of first day of service (used for leave proration)"
    )

    # ----- Status -----
    is_active = models.BooleanField(
        default=True,
        help_text="Active/Inactive status"
    )

    # ------ Biometrics Templates (Encrypted) -----
    fingerprint_template = models.BinaryField(
        blank=True,
        null=True,
        help_text="Encrypted fingerprint biometric template from device"
    )

    face_template = models.BinaryField(
        blank=True,
        null=True,
        help_text="Encrypted face recognition template from device"
    )

    # ------ Timestamps ------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)

    # ----- Display Helpers -----
    def get_full_name(self):
        """Returns: DELA CRUZ, Juan. M."""
        middle_initial = f" {self.middle_name[0].upper()}." if self.middle_name else ""
        suffix_str = f" {self.suffix}" if self.suffix else ""
        return f"{self.last_name.upper()}, {self.first_name}{middle_initial}{suffix_str}"
    
    def get_full_name_natural(self):
        """Returns: Juan M. Dela Cruz Jr."""
        middle_initial = f" {self.middle_name[0].upper()}." if self.middle_name else ""
        suffix_str = f" {self.suffix}" if self.suffix else ""
        return f" {self.first_name}{middle_initial} {self.last_name}{suffix_str}"
    
    def get_initials(self):
        """Returns initials for avatar display e.g. 'JD'."""
        return f"{self.first_name[0]}{self.last_name[0]}".upper()
    
    def is_permanent(self):
        return self.employment_type == 'Permanent'
    
    def is_cos(self):
        return self.employment_type == 'COS'
    
    def is_jo(self):
        return self.employment_type == 'JO'

    # ------ PH Time Helpers ------
    def get_created_at_ph(self):
        return self.get_ph_time('created_at')
    
    def get_updated_at_ph(self):
        return self.get_ph_time('updated_at')

    def get_formatted_created_at_ph(self):
        return self.get_formatted_ph_time('created_at')
    
    def get_formatted_updated_at_ph(self):
        return self.get_formatted_ph_time('updated_at')
    
    def __str__(self):
        return f"[{self.id_number}] {self.get_full_name()} ({self.employment_type})"

    class Meta:
        db_table = 'employees'
        ordering = ['last_name', 'first_name']
        verbose_name = 'Employees'
        verbose_name_plural = 'Employees'

# TABLE 6 - WorkSchedule
# Defines work time schedules.
# Currently two types: Regular 8AM-5Pm and FishCore Flexible. 

class WorkSchedule(PhilippinesTimeMixin, models.Model):

    schedule_id = models.AutoField(primary_key=True)
    schedule_name = models.CharField(
        max_length=100,
        help_text="e.g. Regular 8AM-5PM, FishCore Flexible"
    )

    # ----- Time Slots -----
    am_in = models.TimeField(
        default='08:00',
        help_text="Expected AM time-in"
    )

    am_out = models.TimeField(
        default='12:00',
        help_text="Expected AM time-out"
    )

    pm_in = models.TimeField(
        default='13:00',
        help_text="Expected PM time-in"
    )

    pm_out = models.TimeField(
        default='17:00',
        help_text="Expected PM time-out"
    )

    # ----- Schedule Type -----
    is_flexible = models.BooleanField(
        default=False,
        help_text="TRUE for FishCore flexible schedule"
    )

    working_hours_per_day = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=8.00,
        help_text="Total working hours per day (basis for undertime/OT computation)"
    )

     # ── PH Time Helpers ───────────────────────────────────────────────────────
    # NOTE: WorkSchedule has no timestamp fields in the schema,
    # but we add created_at for audit purposes (consistent with other models)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_schedule_display_str(self):
        """Returns e.g. '8:00 AM - 12:00 PM | 1:00 PM - 5:00 PM'"""
        def fmt(t):
            return t.strftime('%I %M %p').lstrip('0')
        return (
            f"{fmt(self.am_in)} - {fmt(self.am_out)}"
            f" | {fmt(self.pm_in)} - {fmt(self.pm_out)}"
        )
    
    def __str__(self):
        schedule_type = "Flexible" if self.is_flexible else "Fixed"
        return f"{self.schedule_name} ({schedule_type})"

    class Meta:
        db_table = 'work_schedules'
        ordering = ['schedule_name']
        verbose_name = 'Work Schedule'
        verbose_name_plural = 'Work Schedules'

    # ── Seed Data (for reference / fixtures) ─────────────────────────────────
    # Regular 8AM–5PM  → am_in=08:00 am_out=12:00 pm_in=13:00 pm_out=17:00 is_flexible=False
    # FishCore Flexible → is_flexible=True (same time slots, DTR engine handles flextime logic)

# TABLE 7 — EmployeeSchedule
# Links each Employee to their assigned WorkSchedule with an effective date.
# Multiple rows per employee allow schedule changes over time.
# The DTR engine always uses the row with the latest effective_date <= dtr_date.

class EmployeeSchedule(PhilippinesTimeMixin, models.Model):

    emp_schedule_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='schedules',
        help_text="Employee reference"
    )

    schedule = models.ForeignKey(
        WorkSchedule,
        on_delete=models.PROTECT,
        related_name='employee_schedules',
        help_text="Schedule reference"
    )

    effective_date = models.DateField(
        help_text="Date when this schedule assignment become active"
    )

    # ----- PH Time Helpers -----
    # NOTE: Schema has no created_at here, but adding it is good practice.
    created_at = models.DateTimeField(auto_now_add=True)

    def get_created_at_ph(self):
        return self.get_ph_time('created_at')

    def get_formatted_created_at_ph(self):
        return self.get_formatted_ph_time('created_at')
    
    def __str__(self):
        return (
            f"{self.employee.get_full_name()} -> "
            f"{self.schedule.schedule_name} "
            f"(effective {self.effective_date})"
        )
    
    class Meta:
        db_table = 'employee_schedules'
        ordering = ['employee__last_name', '-effective_date']
        # Prevent duplicate schedule assignment for the same employee on the same data
        unique_together = ('employee', 'effective_date')
        verbose_name = 'Employee Schedule'
        verbose_name_plural = 'Employee Schedules'