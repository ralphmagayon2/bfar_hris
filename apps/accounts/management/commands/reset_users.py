"""
Management command: reset_users

Deletes ALL SystemUser records so you can re-test the bootstrap flow
from scratch. Also flushes Django sessions.

Usage:
    python manage.py reset_users
    python manage.py reset_users --yes   # skip confirmation prompt
"""

from django.core.management.base import BaseCommand
from django.contrib.sessions.backends.db import SessionStore
from django.db import connection


class Command(BaseCommand):
    help = (
        'Delete ALL SystemUser records and flush all sessions. '
        'Use this to re-test the bootstrap (first superadmin) flow.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            dest='confirmed',
            help='Skip the confirmation prompt.',
        )

    def handle(self, *args, **options):
        from apps.accounts.models import SystemUser

        count = SystemUser.objects.count()

        if count == 0:
            self.stdout.write(self.style.WARNING('No SystemUser records found — nothing to delete.'))
            return

        if not options['confirmed']:
            self.stdout.write(
                self.style.WARNING(
                    f'\nThis will permanently delete ALL {count} SystemUser record(s) '
                    f'and flush all active sessions.\n'
                    f'This cannot be undone.\n'
                )
            )
            confirm = input('Type YES to confirm: ').strip()
            if confirm != 'YES':
                self.stdout.write(self.style.ERROR('Aborted.'))
                return

        # Delete all users
        deleted_count, _ = SystemUser.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {deleted_count} SystemUser record(s).'))

        # Flush sessions (DB-backed)
        try:
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM django_session;')
            self.stdout.write(self.style.SUCCESS('✓ All sessions flushed.'))
        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(f'Session flush failed (may not use DB sessions): {exc}')
            )

        self.stdout.write(
            self.style.SUCCESS(
                '\nDone. Navigate to /accounts/admin/login/ — '
                'you will be redirected to the bootstrap setup page.'
            )
        )