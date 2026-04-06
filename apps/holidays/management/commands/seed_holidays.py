# apps/holidays/management/commands/seed_holidays.py
from django.core.management.base import BaseCommand
from apps.holidays.models import Holiday

class Command(BaseCommand):
    help = 'Seeds standard Philippine and Pampanga local holidays for 2026'

    def handle(self, *args, **kwargs):
        holidays_2026 = [
            # Regular Holidays
            ("New Year's Day", '2026-01-01', 'regular'),
            ("Araw ng Kagitingan", '2026-04-09', 'regular'),
            ("Maundy Thursday", '2026-04-02', 'regular'), 
            ("Good Friday", '2026-04-03', 'regular'),     
            ("Labor Day", '2026-05-01', 'regular'),
            ("Independence Day", '2026-06-12', 'regular'),
            ("National Heroes Day", '2026-08-31', 'regular'), 
            ("Bonifacio Day", '2026-11-30', 'regular'),
            ("Christmas Day", '2026-12-25', 'regular'),
            ("Rizal Day", '2026-12-30', 'regular'),
            
            # Special Non-Working Holidays
            ("Ninoy Aquino Day", '2026-08-21', 'special'),
            ("All Saints' Day", '2026-11-01', 'special'),
            ("Feast of the Immaculate Conception", '2026-12-08', 'special'),
            ("Last Day of the Year", '2026-12-31', 'special'),
            
            # Local Holidays (Pampanga / San Fernando)
            ("San Fernando Cityhood Day", '2026-02-04', 'local'),
            ("Pampanga Day", '2026-12-11', 'local'),
        ]

        count = 0
        for name, date, h_type in holidays_2026:
            # get_or_create prevents duplicates if you run the script twice
            obj, created = Holiday.objects.get_or_create(
                holiday_date=date,
                defaults={'holiday_name': name, 'holiday_type': h_type}
            )
            if created:
                count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully added {count} standard holidays.'))