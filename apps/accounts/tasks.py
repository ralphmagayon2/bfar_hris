"""
apps/accounts/tasks.py
 
BFAR Region III — HRIS
Email tasks for the accounts app.
 
Tasks:
    send_account_created_email    — new employee/user account creation
    send_password_reset_email     — password reset link (employee & admin)
 
Queue: emails
"""

import logging
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


def _send(subject: str, html_body: str, plain_body: str, to: list) -> bool:
    """Send HTML email using Django's configured email backend."""
    msg = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)
    return True


@shared_task(
    bind=True, max_retries=3, default_retry_delay=60,
    queue='emails',
    name='apps.accounts.tasks.send_account_created_email',
)
def send_account_created_email(self, user_id: int, temp_password: str):
    try:
        from apps.accounts.models import SystemUser
        user = SystemUser.objects.select_related(
            'employee__division', 'employee__position'
        ).get(user_id=user_id)

        emp = user.employee
        ctx = {
            'employee_name': emp.get_full_name()              if emp else user.username,
            'id_number':     emp.id_number                    if emp else '—',
            'division':      emp.division.division_name        if (emp and emp.division) else '—',
            'position':      emp.position.position_title       if (emp and emp.position) else '—',
            'username':      user.username,
            'temp_password': temp_password,
        }

        html_body  = render_to_string('emails/account_created.html', ctx)
        plain_body = (
            f"Welcome to BFAR Region III HRIS, {ctx['employee_name']}!\n\n"
            f"Username: {user.username}\n"
            f"Temporary Password: {temp_password}\n\n"
            f"Please change your password on first login."
        )

        recipient = user.personal_email or f'{user.username}@bfar.gov.ph'

        logger.info(
            '[accounts.tasks] Sending account created email to %s (user_id=%s)',
            recipient, user_id,
        )

        _send(
            subject='Your BFAR Region III HRIS Account Has Been Created',
            html_body=html_body,
            plain_body=plain_body,
            to=[recipient],
        )

        logger.info('[accounts.tasks] Account created email sent — %s', recipient)
        return {'success': True, 'recipient': recipient}

    except Exception as exc:
        logger.error(
            '[accounts.tasks] send_account_created_email failed: %s',
            exc,
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(
    bind=True, max_retries=3, default_retry_delay=60,
    queue='emails',
    name='apps.accounts.tasks.send_password_reset_email',
)
def send_password_reset_email(self, user_id: int, reset_url: str, is_admin: bool = False):
    try:
        from apps.accounts.models import SystemUser
        user = SystemUser.objects.select_related('employee').get(user_id=user_id)

        emp          = user.employee
        display_name = emp.get_full_name() if emp else user.username

        ctx = {
            'display_name': display_name,
            'username':     user.username,
            'reset_url':    reset_url,
            'is_admin':     is_admin,
            'expiry_hours': 1,
        }

        html_body  = render_to_string('emails/password_reset.html', ctx)
        plain_body = (
            f"Hello {display_name},\n\n"
            f"A password reset was requested for your BFAR HRIS account.\n\n"
            f"Reset link (valid 1 hour):\n{reset_url}\n\n"
            f"If you did not request this, ignore this email."
        )

        recipient = user.personal_email
        if not recipient:
            logger.error(
                '[accounts.tasks] user_id=%s has no personal_email — skipping reset email.',
                user_id,
            )
            return {'success': False, 'reason': 'no_personal_email'}

        logger.info(
            '[accounts.tasks] Sending password reset email to %s (user_id=%s is_admin=%s)',
            recipient, user_id, is_admin,
        )

        _send(
            subject='BFAR HRIS — Password Reset Request',
            html_body=html_body,
            plain_body=plain_body,
            to=[recipient],
        )

        logger.info('[accounts.tasks] Password reset email sent — %s', recipient)
        return {'success': True, 'recipient': recipient}

    except SystemUser.DoesNotExist:
        logger.error(
            '[accounts.tasks] user_id=%s not found — cannot send reset email.',
            user_id,
        )
        return {'success': False, 'reason': 'user_not_found'}

    except Exception as exc:
        logger.error(
            '[accounts.tasks] send_password_reset_email failed: %s',
            exc,
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))