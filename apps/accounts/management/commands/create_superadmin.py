"""
apps/accounts/management/commands/create_superadmin.py

BFAR Region III — HRIS
Bootstrap management command to create the first superadmin account.

Usage:
    python manage.py create_superadmin
    python manage.py create_superadmin --username itadmin --email admin@gmail.com
    python manage.py create_superadmin --username itadmin --email admin@gmail.com --password MyPass@2025

File placement:
    apps/accounts/
    └── management/
        ├── __init__.py          (empty)
        └── commands/
            ├── __init__.py      (empty)
            └── create_superadmin.py   ← this file

Run this ONCE after the first migration to get into the system.
"""

import getpass
import sys

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import SystemUser
from apps.accounts.utils import validate_password_strength


class Command(BaseCommand):
    help = 'Bootstrap the first superadmin account for BFAR HRIS.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username', '-u',
            type=str,
            default='',
            help='Superadmin username (prompted if omitted)',
        )
        parser.add_argument(
            '--email', '-e',
            type=str,
            default='',
            help='Personal email for password recovery (prompted if omitted)',
        )
        parser.add_argument(
            '--password', '-p',
            type=str,
            default='',
            help='Password (prompted if omitted — use prompts in production)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== BFAR HRIS — Create Superadmin ===\n'))

        # ── Username ──────────────────────────────────────────────────────────
        username = options['username'].strip()
        while not username:
            username = input('Username: ').strip()
            if not username:
                self.stdout.write(self.style.ERROR('Username cannot be empty.'))

        if SystemUser.objects.filter(username=username).exists():
            raise CommandError(
                f'A user with username "{username}" already exists. '
                'To reset their password, use the forgot-password flow or Django shell.'
            )

        # ── Personal email ────────────────────────────────────────────────────
        email = options['email'].strip().lower()
        while not email or '@' not in email:
            email = input('Personal email (for password recovery): ').strip().lower()
            if not email or '@' not in email:
                self.stdout.write(self.style.ERROR('Please enter a valid email address.'))

        if SystemUser.objects.filter(personal_email__iexact=email).exists():
            raise CommandError(
                f'Email "{email}" is already registered to another account.'
            )

        # ── Password ──────────────────────────────────────────────────────────
        raw_password = options['password'].strip()
        if not raw_password:
            while True:
                raw_password = getpass.getpass('Password: ')
                confirm      = getpass.getpass('Confirm password: ')
                if raw_password != confirm:
                    self.stdout.write(self.style.ERROR('Passwords do not match. Try again.'))
                    continue
                errors = validate_password_strength(raw_password)
                if errors:
                    for e in errors:
                        self.stdout.write(self.style.ERROR(f'  • {e}'))
                    self.stdout.write('')
                    continue
                break
        else:
            errors = validate_password_strength(raw_password)
            if errors:
                for e in errors:
                    self.stdout.write(self.style.WARNING(f'  WARNING: {e}'))
                self.stdout.write(self.style.WARNING(
                    'Password does not meet strength requirements. Proceeding anyway (dev mode).'
                ))

        # ── Create ────────────────────────────────────────────────────────────
        user = SystemUser(
            username       = username,
            role           = 'superadmin',
            personal_email = email,
            is_active      = True,
            employee       = None,   # superadmin is an IT account, not a BFAR employee
        )
        user.set_password(raw_password)
        user.save()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✓ Superadmin account created successfully!'))
        self.stdout.write(f'  Username   : {username}')
        self.stdout.write(f'  Role       : superadmin')
        self.stdout.write(f'  Login URL  : http://<host>:8000/accounts/admin/login/')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            'IMPORTANT: Keep this username and password secure. '
            'Change the password after first login.'
        ))
        self.stdout.write('')