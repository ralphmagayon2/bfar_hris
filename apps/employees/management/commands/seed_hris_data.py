"""
RUN WITH: python manage.py seed_hris_data
"""

import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

# Import your models
from apps.employees.models import (
    Division, Unit, PayrollGroup, Position, Employee,
    WorkSchedule, EmployeeSchedule
)
from apps.payroll.models import PayrollPeriod, PayrollRecord, SEDRecord

fake = Faker('en_PH') # Use Philippine locale for realistic names

class Command(BaseCommand):
    help = 'Seeds the database with dozens of realistic HRIS records for dashboard testing.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Clearing old test data...")
        # Optional: Clear existing data to prevent clutter during multiple test runs
        SEDRecord.objects.all().delete()
        PayrollRecord.objects.all().delete()
        PayrollPeriod.objects.all().delete()
        EmployeeSchedule.objects.all().delete()
        Employee.objects.all().delete()
        Position.objects.all().delete()
        WorkSchedule.objects.all().delete()
        PayrollGroup.objects.all().delete()
        Unit.objects.all().delete()
        Division.objects.all().delete()

        self.stdout.write("Seeding Reference Tables (Divisions, Groups, Schedules)...")
        
        # ── 1. Divisions [cite: 53, 54] ──
        divisions_data = [
            {'code': 'ORD', 'name': 'Office of the Regional Director', 'sched': 'fixed'},
            {'code': 'FPSSD', 'name': 'Fisheries Production and Support Services Division', 'sched': 'fixed'},
            {'code': 'FMRED', 'name': 'Fisheries Management, Regulatory and Enforcement Division', 'sched': 'fixed'},
            {'code': 'PFO', 'name': 'Provincial Fisheries Office', 'sched': 'fixed'},
            {'code': 'TOSS', 'name': 'Technology Outreach Stations/Satellite Stations', 'sched': 'flexible'},
        ]
        divisions = {}
        for d in divisions_data:
            div, _ = Division.objects.get_or_create(
                division_code=d['code'],
                defaults={'division_name': d['name'], 'work_schedule_type': d['sched']}
            )
            divisions[d['code']] = div

        # ── 2. Units (Simplified) [cite: 55, 57] ──
        units = []
        for code, div in divisions.items():
            for unit_name in [f"{code} Admin Unit", f"{code} Operations Section"]:
                u, _ = Unit.objects.get_or_create(division=div, unit_name=unit_name)
                units.append(u)

        # ── 3. Payroll Groups [cite: 63, 64] ──
        pg_data = [
            ('Permanent', 'Permanent', 'GSIS'),
            ('Contract of Service', 'COS', 'SSS'),
            ('Job Order', 'JO', 'SSS'),
            ('NSAP Enumerator', 'JO', 'SSS'),
            ('NSAP Freshwater', 'JO', 'SSS'),
            ('FishCore', 'COS', 'SSS'),
            ('Adjudication', 'COS', 'SSS'),
        ]
        pgs = {}
        for name, emp_type, scheme in pg_data:
            pg, _ = PayrollGroup.objects.get_or_create(
                group_name=name,
                defaults={'employment_type': emp_type, 'contribution_scheme': scheme}
            )
            pgs[name] = pg

        # ── 4. Positions [cite: 65, 66] ──
        pos_data = [
            ('Administrative Aide IV', 'Permanent'), ('Fishery Technologist II', 'Permanent'),
            ('Aquaculturist I', 'COS'), ('Data Encoder', 'COS'),
            ('Driver II', 'JO'), ('Utility Worker', 'JO')
        ]
        positions = []
        for title, emp_type in pos_data:
            p, _ = Position.objects.get_or_create(position_title=title, employment_type=emp_type)
            positions.append(p)

        # ── 5. Work Schedules [cite: 86] ──
        sched_fixed, _ = WorkSchedule.objects.get_or_create(
            schedule_name='Regular 8AM-5PM',
            defaults={'is_flexible': False}
        )
        sched_flex, _ = WorkSchedule.objects.get_or_create(
            schedule_name='FishCore Flexible',
            defaults={'is_flexible': True}
        )

        self.stdout.write("Generating 100 Employees and Schedules...")
        employees = []
        
        # ── 6. Employees [cite: 68-75] ──
        for i in range(1, 101):
            emp_type = random.choices(['Permanent', 'COS', 'JO'], weights=[40, 40, 20])[0]
            
            # Match position and payroll group to employment type
            valid_positions = [p for p in positions if p.employment_type == emp_type]
            if emp_type == 'Permanent':
                valid_pgs = [pgs['Permanent']]
            elif emp_type == 'COS':
                valid_pgs = [pgs['Contract of Service'], pgs['FishCore'], pgs['Adjudication']]
            else:
                valid_pgs = [pgs['Job Order'], pgs['NSAP Enumerator'], pgs['NSAP Freshwater']]

            div = random.choice(list(divisions.values()))
            salary = Decimal(random.randint(15000, 65000))

            emp = Employee.objects.create(
                id_number=f"{i:09d}",
                last_name=fake.last_name(),
                first_name=fake.first_name(),
                middle_name=fake.last_name(),
                division=div,
                unit=random.choice([u for u in units if u.division == div]),
                payroll_group=random.choice(valid_pgs),
                position=random.choice(valid_positions),
                employment_type=emp_type,
                montly_salary=salary,
                pera=Decimal('2000.00'),
                date_hired=fake.date_between(start_date='-5y', end_date='today'),
                is_active=True
                # Note: Biometric templates omitted as they are raw binary data from devices 
            )
            employees.append(emp)

            # Assign Schedule [cite: 89, 86]
            assigned_sched = sched_flex if emp.payroll_group.group_name == 'FishCore' else sched_fixed
            EmployeeSchedule.objects.create(
                employee=emp,
                schedule=assigned_sched,
                effective_date=emp.date_hired
            )

        self.stdout.write("Generating Payroll Periods and Records...")
        
        # ── 7. Payroll Period [cite: 101, 102] ──
        period = PayrollPeriod.objects.create(
            period_name="March 1-15 2026",
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 15),
            salary_release_date=date(2026, 3, 20),
            cutoff_type='first',
            status='released'
        )

        for emp in employees:
            if emp.is_permanent():
                # Permanent -> SED Record (Input Only) [cite: 140, 142]
                SEDRecord.objects.create(
                    employee=emp,
                    period_month="MARCH",
                    period_year=2026,
                    basic_monthly_pay=emp.montly_salary,
                    pera=emp.pera,
                    gsis_life_insurance=Decimal('1200.00'),
                    medicare_premiums=Decimal('500.00'),
                    pagibig_premiums=Decimal('200.00'),
                    issued_date=date.today(),
                    status='released'
                ).compute_totals() # Compute total_income, total_deductions, and total_net_pay [cite: 162]
            else:
                # COS / JO -> Payroll Record [cite: 107, 108]
                pr = PayrollRecord(
                    employee=emp,
                    period=period,
                    payroll_group=emp.payroll_group,
                    cutoff_type='first',
                    basic_salary=emp.montly_salary,
                    status='released'
                )
                pr.compute_first_cutoff() # Compute 1st cutoff fields [cite: 128]
                pr.save()

        self.stdout.write(self.style.SUCCESS('Successfully seeded HRIS database with 100 employees and related payroll data!'))