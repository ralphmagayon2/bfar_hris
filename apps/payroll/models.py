"""
apps/payroll/models.py

BFAR Region III — HRIS
Payroll Models

Models:
    1. PayrollPeriod  → TABLE 14  (payroll_periods)
    2. PayrollRecord  → TABLE 15  (payroll_records)   — COS / JO employees
    3. SEDRecord      → TABLE 16  (sed_records)        — Permanent employees (input-only)

Payroll Rules (from schema):
    ── COS / JO ────────────────────────────────────────────────────────────────
    First Cutoff  (1st–15th, released on 20th):
        - First Half Salary      = basic_salary ÷ 2
        - Premiums (PERA)        = fixed ₱2,000
        - SSS                    = ₱760 minimum
        - PhilHealth             = 5% of basic_salary (NOT half salary)
        - Pag-IBIG               = ₱400 minimum
        - salary_with_premium    = first_half_salary + premiums (1st cutoff only)

    Second Cutoff (16th–31st, released on 10th of next month):
        - Rate Per Day           = basic_salary ÷ 22
        - Rate Per Hour          = rate_per_day ÷ 8
        - Rate Per Minute        = rate_per_hour ÷ 60
        - Absent Deduction       = days_absent × rate_per_day
        - Late (Hours) Deduction = hours_late × rate_per_hour
        - Late (Mins) Deduction  = minutes_late × rate_per_minute
        - Tax Threshold          = ₱20,833.33/month (₱250,000 ÷ 12)
        - Withholding Tax        = 5% + 3% of taxable income (if above threshold)

    ── Permanent ───────────────────────────────────────────────────────────────
    SED is INPUT ONLY — HR types all values.
    System only computes:
        total_income      = sum of all earnings
        total_deductions  = sum of all deduction fields
        total_net_pay     = total_income − total_deductions

    ── Overtime (All Types) ────────────────────────────────────────────────────
    OVERTIME THANK YOU — No additional pay. OT is recorded for reference only.

Cross-app imports:
    - apps.employees.models.Employee    (FK)
    - apps.employees.models.PayrollGroup (FK)
    - apps.accounts.models.SystemUser   (FK — approved_by)
"""

from django.db import models
from django.utils import timezone
import pytz
from decimal import Decimal


# ─────────────────────────────────────────────────────────────────────────────
# SHARED PH TIME MIXIN
# ─────────────────────────────────────────────────────────────────────────────

class PhilippinesTimeMixin:
    def _to_ph(self, dt):
        if dt:
            return dt.astimezone(pytz.timezone('Asia/Manila'))
        return None

    def get_formatted_ph_time(self, field_name):
        ph = self._to_ph(getattr(self, field_name, None))
        return ph.strftime('%B %d, %Y at %I:%M %p') if ph else None


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 14 — PayrollPeriod
# Defines each payroll cutoff period.
# 1st cutoff released on 20th, 2nd cutoff released on 10th of following month.
# ─────────────────────────────────────────────────────────────────────────────

class PayrollPeriod(PhilippinesTimeMixin, models.Model):

    CUTOFF_TYPE_CHOICES = [
        ('first',  '1st Cutoff (1st–15th, released 20th)'),
        ('second', '2nd Cutoff (16th–31st, released 10th next month)'),
    ]

    STATUS_CHOICES = [
        ('open',     'Open'),
        ('locked',   'Locked'),
        ('released', 'Released'),
    ]

    # ── Primary Key ───────────────────────────────────────────────────────────
    period_id = models.AutoField(primary_key=True)

    # ── Period Details ────────────────────────────────────────────────────────
    period_name = models.CharField(
        max_length=100,
        help_text="e.g. May 1–15 2026"
    )
    date_from = models.DateField(
        help_text="Start date of the payroll period"
    )
    date_to = models.DateField(
        help_text="End date of the payroll period"
    )
    salary_release_date = models.DateField(
        help_text="1st cutoff → 20th | 2nd cutoff → 10th of next month"
    )
    cutoff_type = models.CharField(
        max_length=10,
        choices=CUTOFF_TYPE_CHOICES,
        help_text=(
            "first  = 1st–15th, released on 20th | "
            "second = 16th–31st, released on 10th next month"
        )
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='open',
        help_text=(
            "open = editable | "
            "locked = being processed | "
            "released = payslips distributed"
        )
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Status Helpers ────────────────────────────────────────────────────────
    def is_open(self):
        return self.status == 'open'

    def is_locked(self):
        return self.status == 'locked'

    def is_released(self):
        return self.status == 'released'

    def is_first_cutoff(self):
        return self.cutoff_type == 'first'

    def is_second_cutoff(self):
        return self.cutoff_type == 'second'

    # ── PH Time Helpers ───────────────────────────────────────────────────────
    def get_created_at_ph(self):
        return self._to_ph(self.created_at)

    def get_formatted_created_at_ph(self):
        return self.get_formatted_ph_time('created_at')

    def __str__(self):
        return f"{self.period_name} [{self.get_status_display()}]"

    class Meta:
        db_table  = 'payroll_periods'
        ordering  = ['-date_from']
        verbose_name        = 'Payroll Period'
        verbose_name_plural = 'Payroll Periods'


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 15 — PayrollRecord
# Payroll computation for COS and JO employees.
# Computed by payroll/engine.py and stored here.
# ─────────────────────────────────────────────────────────────────────────────

class PayrollRecord(PhilippinesTimeMixin, models.Model):

    CUTOFF_TYPE_CHOICES = [
        ('first',  '1st Cutoff'),
        ('second', '2nd Cutoff'),
    ]

    STATUS_CHOICES = [
        ('draft',    'Draft'),
        ('approved', 'Approved'),
        ('released', 'Released'),
    ]

    # ── Primary Key ───────────────────────────────────────────────────────────
    payroll_id = models.AutoField(primary_key=True)

    # ── References ────────────────────────────────────────────────────────────
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.PROTECT,
        related_name='payroll_records',
        help_text="Employee reference (COS/JO only)"
    )
    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.PROTECT,
        related_name='payroll_records',
        help_text="Payroll period reference"
    )
    payroll_group = models.ForeignKey(
        'employees.PayrollGroup',
        on_delete=models.PROTECT,
        related_name='payroll_records',
        help_text="COS | JO | NSAP | FishCore | Adjudication"
    )

    # ── Cutoff Type ───────────────────────────────────────────────────────────
    cutoff_type = models.CharField(
        max_length=10,
        choices=CUTOFF_TYPE_CHOICES,
        help_text="Which half of the month this record covers"
    )

    # ── Salary Inputs ─────────────────────────────────────────────────────────
    basic_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Full monthly salary (from employee record at time of computation)"
    )

    # ── 1ST CUTOFF EARNINGS ───────────────────────────────────────────────────
    first_half_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED: basic_salary ÷ 2"
    )
    premiums = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('2000.00'),
        help_text="Fixed ₱2,000 PERA/premiums — added to 1st cutoff only"
    )
    salary_with_premium = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED (1st cutoff only): first_half_salary + premiums"
    )

    # ── 1ST CUTOFF DEDUCTIONS (Contributions) ─────────────────────────────────
    sss_contribution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('760.00'),
        help_text="COMPUTED (1st cutoff): ₱760 minimum — HR notified if increase needed"
    )
    philhealth_contribution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED (1st cutoff): 5% of basic_salary (NOT half salary)"
    )
    pagibig_contribution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('400.00'),
        help_text="COMPUTED (1st cutoff): ₱400 minimum"
    )
    total_premium_deductions = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED (1st cutoff): SSS + PhilHealth + Pag-IBIG"
    )

    # ── 2ND CUTOFF RATES ──────────────────────────────────────────────────────
    second_half_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED: basic_salary ÷ 2"
    )
    rate_per_day = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED (2nd cutoff): basic_salary ÷ 22 working days"
    )
    rate_per_hour = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED (2nd cutoff): rate_per_day ÷ 8"
    )
    rate_per_minute = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('0.0000'),
        help_text="COMPUTED (2nd cutoff): rate_per_hour ÷ 60"
    )

    # ── 2ND CUTOFF DEDUCTIONS (Late & Absent) ─────────────────────────────────
    days_absent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(2nd cutoff) Number of absent days from DTR"
    )
    deduction_absent = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED (2nd cutoff): days_absent × rate_per_day"
    )
    hours_late = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(2nd cutoff) Total full hours late from DTR"
    )
    deduction_hours_late = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED (2nd cutoff): hours_late × rate_per_hour"
    )
    minutes_late = models.IntegerField(
        default=0,
        help_text="(2nd cutoff) Remaining minutes late after full hours are counted"
    )
    deduction_minutes_late = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED (2nd cutoff): minutes_late × rate_per_minute"
    )
    total_late_absent_deduction = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED (2nd cutoff): sum of all late + absent deductions"
    )

    # ── Manual Adjustments ────────────────────────────────────────────────────
    other_adjustments = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Manual HR adjustments (positive = addition, negative = deduction)"
    )
    adjustment_remarks = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for manual adjustment"
    )

    # ── Tax Computation ───────────────────────────────────────────────────────
    net_income_before_tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=(
            "COMPUTED: salary after contributions and deductions, before tax"
        )
    )
    taxable_income = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=(
            "COMPUTED: net_income_before_tax − ₱20,833.33 "
            "(allowable deduction = ₱250,000 ÷ 12)"
        )
    )
    withholding_tax_5pct = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="5% of taxable income (if above threshold)"
    )
    withholding_tax_3pct = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="3% of taxable income (if above threshold)"
    )
    total_tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED: withholding_tax_5pct + withholding_tax_3pct"
    )

    # ── Final Net Pay ─────────────────────────────────────────────────────────
    net_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED: final take-home pay after all deductions and tax"
    )

    # ── Approval ──────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='draft',
        help_text="Payroll approval status"
    )
    approved_by = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.PROTECT,
        related_name='approved_payroll_records',
        null=True,
        blank=True,
        help_text="HR who approved this payroll record"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Approval timestamp"
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Engine Computation Methods ────────────────────────────────────────────
    # These are called by payroll/engine.py to populate computed fields.

    def compute_first_cutoff(self):
        """
        Populate all 1st cutoff computed fields from basic_salary.
        Call this from engine.py after setting basic_salary.
        """
        TAX_ALLOWABLE_MONTHLY = Decimal('20833.33')  # 250,000 ÷ 12

        self.first_half_salary       = (self.basic_salary / 2).quantize(Decimal('0.01'))
        self.salary_with_premium     = (self.first_half_salary + self.premiums).quantize(Decimal('0.01'))
        self.philhealth_contribution = (self.basic_salary * Decimal('0.05')).quantize(Decimal('0.01'))
        self.total_premium_deductions = (
            self.sss_contribution +
            self.philhealth_contribution +
            self.pagibig_contribution
        ).quantize(Decimal('0.01'))
        self.net_income_before_tax = (
            self.salary_with_premium - self.total_premium_deductions
        ).quantize(Decimal('0.01'))
        self.taxable_income = max(
            Decimal('0.00'),
            (self.net_income_before_tax - TAX_ALLOWABLE_MONTHLY).quantize(Decimal('0.01'))
        )
        if self.taxable_income > 0:
            self.withholding_tax_5pct = (self.taxable_income * Decimal('0.05')).quantize(Decimal('0.01'))
            self.withholding_tax_3pct = (self.taxable_income * Decimal('0.03')).quantize(Decimal('0.01'))
        self.total_tax = (self.withholding_tax_5pct + self.withholding_tax_3pct).quantize(Decimal('0.01'))
        self.net_pay   = (self.net_income_before_tax - self.total_tax).quantize(Decimal('0.01'))

    def compute_second_cutoff(self):
        """
        Populate all 2nd cutoff computed fields.
        Expects days_absent, hours_late, minutes_late to be set first
        (sourced from DTR records by engine.py).
        """
        WORKING_DAYS   = Decimal('22')
        HOURS_PER_DAY  = Decimal('8')
        MINS_PER_HOUR  = Decimal('60')

        self.second_half_salary      = (self.basic_salary / 2).quantize(Decimal('0.01'))
        self.rate_per_day            = (self.basic_salary / WORKING_DAYS).quantize(Decimal('0.01'))
        self.rate_per_hour           = (self.rate_per_day / HOURS_PER_DAY).quantize(Decimal('0.01'))
        self.rate_per_minute         = (self.rate_per_hour / MINS_PER_HOUR).quantize(Decimal('0.0001'))

        self.deduction_absent        = (self.days_absent * self.rate_per_day).quantize(Decimal('0.01'))
        self.deduction_hours_late    = (Decimal(str(self.hours_late)) * self.rate_per_hour).quantize(Decimal('0.01'))
        self.deduction_minutes_late  = (Decimal(str(self.minutes_late)) * self.rate_per_minute).quantize(Decimal('0.01'))
        self.total_late_absent_deduction = (
            self.deduction_absent +
            self.deduction_hours_late +
            self.deduction_minutes_late
        ).quantize(Decimal('0.01'))

        self.net_income_before_tax = (
            self.second_half_salary -
            self.total_late_absent_deduction +
            self.other_adjustments
        ).quantize(Decimal('0.01'))
        self.net_pay = self.net_income_before_tax  # No contributions on 2nd cutoff

    # ── Status Helpers ────────────────────────────────────────────────────────
    def is_draft(self):
        return self.status == 'draft'

    def is_approved(self):
        return self.status == 'approved'

    def is_released(self):
        return self.status == 'released'

    def is_first_cutoff(self):
        return self.cutoff_type == 'first'

    def is_second_cutoff(self):
        return self.cutoff_type == 'second'

    # ── PH Time Helpers ───────────────────────────────────────────────────────
    def get_created_at_ph(self):
        return self._to_ph(self.created_at)

    def get_updated_at_ph(self):
        return self._to_ph(self.updated_at)

    def get_approved_at_ph(self):
        return self._to_ph(self.approved_at)

    def get_formatted_created_at_ph(self):
        return self.get_formatted_ph_time('created_at')

    def get_formatted_approved_at_ph(self):
        ph = self.get_approved_at_ph()
        return ph.strftime('%B %d, %Y at %I:%M %p') if ph else None

    # ── Display Helpers ───────────────────────────────────────────────────────
    def get_net_pay_display(self):
        return f"₱{self.net_pay:,.2f}"

    def get_basic_salary_display(self):
        return f"₱{self.basic_salary:,.2f}"

    def __str__(self):
        return (
            f"{self.employee.get_full_name()} — "
            f"{self.period.period_name} "
            f"[{self.get_cutoff_type_display()}] "
            f"Net: ₱{self.net_pay:,.2f}"
        )

    class Meta:
        db_table  = 'payroll_records'
        ordering  = ['-period__date_from', 'employee__last_name']
        # One payroll record per employee per period per cutoff
        unique_together = ('employee', 'period', 'cutoff_type')
        verbose_name        = 'Payroll Record'
        verbose_name_plural = 'Payroll Records'


# ─────────────────────────────────────────────────────────────────────────────
# TABLE 16 — SEDRecord
# Statement of Earnings and Deductions — Permanent Employees ONLY.
# INPUT ONLY — HR types all values. System only computes totals.
# Based on sample payslips: Ms. Sherryl D. Millado and Mr. Nico Jose S. Leander.
# ─────────────────────────────────────────────────────────────────────────────

class SEDRecord(PhilippinesTimeMixin, models.Model):

    STATUS_CHOICES = [
        ('draft',    'Draft'),
        ('approved', 'Approved'),
        ('released', 'Released'),
    ]

    # ── Primary Key ───────────────────────────────────────────────────────────
    sed_id = models.AutoField(primary_key=True)

    # ── Employee Reference (Permanent only) ───────────────────────────────────
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.PROTECT,
        related_name='sed_records',
        help_text="Permanent employee reference only"
    )

    # ── Period ────────────────────────────────────────────────────────────────
    period_month = models.CharField(
        max_length=20,
        help_text="e.g. JULY 2023 | JANUARY 2026"
    )
    period_year = models.IntegerField(
        help_text="4-digit year e.g. 2026"
    )

    # ── EARNINGS (HR Input) ───────────────────────────────────────────────────
    basic_monthly_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="(HR input) Basic Monthly Pay — from plantilla"
    )
    pera = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('2000.00'),
        help_text="(HR input) Personnel Economic Relief Allowance"
    )
    aca = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) Additional Compensation Allowance — if applicable"
    )
    rata = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) Representation and Transportation Allowance — if applicable"
    )
    other_allowances = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) Any other allowances"
    )
    total_income = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED: sum of all earnings fields"
    )

    # ── DEDUCTIONS (HR Input) ─────────────────────────────────────────────────
    gsis_life_insurance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) GSIS Life Insurance premium"
    )
    withholding_tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) BIR Withholding Tax — computed by BIR, HR inputs result"
    )
    medicare_premiums = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) PhilHealth/Medicare premiums"
    )
    pagibig_premiums = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) Pag-IBIG/HDMF premiums"
    )
    gsis_cpl = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) GSIS Consolidated Premium Loan"
    )
    gsis_mpl = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) GSIS Multi-Purpose Loan"
    )
    pagibig_loan = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) Pag-IBIG Housing/Multi-Purpose Loan"
    )
    gsis_el = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) GSIS Emergency Loan"
    )
    gsis_policy_loan = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) GSIS Policy Loan"
    )
    kb_calamity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) Kabuhayan/Kalusugan Calamity Fund"
    )
    kb_premiums = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) KB Premiums"
    )
    kb_savings_deposits = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) KB Savings Deposits"
    )
    kb_educ_loan = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) KB Education Loan"
    )
    kb_regular_loan = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) KB Regular Loan"
    )
    kb_apl = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) KB APL (Additional Policy Loan)"
    )
    kb_crl = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) KB CRL (Credit Line)"
    )
    landbank_esl = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) Landbank Emergency/Salary Loan"
    )
    hmo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) HMO premium deduction"
    )
    kb_appliance_loan = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) KB Appliance Loan"
    )

    # ── Custom Deductions (2 flexible slots) ──────────────────────────────────
    other_deductions_1_label = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="(HR input) Custom deduction label #1"
    )
    other_deductions_1_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) Custom deduction amount #1"
    )
    other_deductions_2_label = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="(HR input) Custom deduction label #2"
    )
    other_deductions_2_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="(HR input) Custom deduction amount #2"
    )

    # ── Computed Totals ───────────────────────────────────────────────────────
    total_deductions = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED: sum of all deduction fields"
    )
    total_net_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="COMPUTED: total_income − total_deductions"
    )

    # ── Certifying Officer ────────────────────────────────────────────────────
    certified_by_name = models.CharField(
        max_length=200,
        default='ZENAIDA S. SIMON',
        help_text="Certifying officer name — printed on SED"
    )
    certified_by_title = models.CharField(
        max_length=200,
        default='Administrative Officer V',
        help_text="Certifying officer title"
    )

    # ── Issuance Details ──────────────────────────────────────────────────────
    issued_date = models.DateField(
        help_text="(HR input) Date SED was issued"
    )
    issued_purpose = models.TextField(
        null=True,
        blank=True,
        help_text="e.g. for whatever legal purposes it may serve"
    )
    has_no_advances = models.BooleanField(
        default=True,
        help_text="Certifies employee has no salary advances"
    )

    # ── Approval ──────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='draft',
        help_text="SED approval status"
    )
    approved_by = models.ForeignKey(
        'accounts.SystemUser',
        on_delete=models.PROTECT,
        related_name='approved_sed_records',
        null=True,
        blank=True,
        help_text="HR who approved this SED"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Approval timestamp"
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Compute Totals ────────────────────────────────────────────────────────
    def compute_totals(self):
        """
        Compute total_income, total_deductions, and total_net_pay
        from all HR-inputted fields. Call this before save() in the view.
        """
        self.total_income = (
            self.basic_monthly_pay +
            self.pera +
            self.aca +
            self.rata +
            self.other_allowances
        ).quantize(Decimal('0.01'))

        self.total_deductions = (
            self.gsis_life_insurance +
            self.withholding_tax +
            self.medicare_premiums +
            self.pagibig_premiums +
            self.gsis_cpl +
            self.gsis_mpl +
            self.pagibig_loan +
            self.gsis_el +
            self.gsis_policy_loan +
            self.kb_calamity +
            self.kb_premiums +
            self.kb_savings_deposits +
            self.kb_educ_loan +
            self.kb_regular_loan +
            self.kb_apl +
            self.kb_crl +
            self.landbank_esl +
            self.hmo +
            self.kb_appliance_loan +
            self.other_deductions_1_amount +
            self.other_deductions_2_amount
        ).quantize(Decimal('0.01'))

        self.total_net_pay = (
            self.total_income - self.total_deductions
        ).quantize(Decimal('0.01'))

    # ── Status Helpers ────────────────────────────────────────────────────────
    def is_draft(self):
        return self.status == 'draft'

    def is_approved(self):
        return self.status == 'approved'

    # ── PH Time Helpers ───────────────────────────────────────────────────────
    def get_created_at_ph(self):
        return self._to_ph(self.created_at)

    def get_updated_at_ph(self):
        return self._to_ph(self.updated_at)

    def get_approved_at_ph(self):
        return self._to_ph(self.approved_at)

    def get_formatted_created_at_ph(self):
        return self.get_formatted_ph_time('created_at')

    def get_formatted_approved_at_ph(self):
        ph = self.get_approved_at_ph()
        return ph.strftime('%B %d, %Y at %I:%M %p') if ph else None

    # ── Display Helpers ───────────────────────────────────────────────────────
    def get_net_pay_display(self):
        return f"₱{self.total_net_pay:,.2f}"

    def __str__(self):
        return (
            f"{self.employee.get_full_name()} — "
            f"SED {self.period_month} "
            f"Net: ₱{self.total_net_pay:,.2f}"
        )

    class Meta:
        db_table  = 'sed_records'
        ordering  = ['-period_year', 'employee__last_name']
        unique_together = ('employee', 'period_month', 'period_year')
        verbose_name        = 'SED Record'
        verbose_name_plural = 'SED Records'