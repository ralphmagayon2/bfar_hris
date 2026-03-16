"""
apps/accounts/tasks.py
 
BFAR Region III — HRIS
Email tasks for the accounts app.
 
Tasks:
    send_account_created_email    → new employee/user account creation
    send_password_reset_email     → password reset link (employee & admin)
 
Queue: emails
"""

import logging
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


# ------ BASE SEND HELPER ------

def _send(subject: str, html_body: str, plain_body: str, to: list) -> bool:
    from django.core.mail import get_connection 
    conn = get_connection(
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        fail_silently=False,
    )

    conn.open()
    msg = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
        connection=conn,
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)
    conn.close()
    return True



# ----- TASK 1 — Account Created -----

@shared_task(
    bind=True, max_retries=3, default_retry_delay=60,
    queue='emails',
    name='apps.accounts.tasks.send_account_created_email',
)
def send_account_created_email(self, user_id: int, temp_password: str, login_url: str):
    """
    Send "your account has been created" email to a newly enrolled user.

    Usage:
        send_account_created_email.delay(
            user_id=user.user_id,
            temp_password=raw_pw,
            login_url='http://192.168.x.x:8000/accounts/login/',
        )
    """
    try:
        from apps.accounts.models import SystemUser
        user = SystemUser.objects.select_related(
            'employee__division', 'employee__position'
        ).get(user_id=user_id)

        emp = user.employee
        ctx = {
            'employee_name': emp.get_full_name()             if emp else user.username,
            'id_number':     emp.id_number                   if emp else '—',
            'division':      emp.division.division_name       if (emp and emp.division)  else '—',
            'position':      emp.position.position_title      if (emp and emp.position)  else '—',
            'username':      user.username,
            'temp_password': temp_password,
            'login_url':     login_url,
        }

        html_body = render_to_string('emails/account_created.html', ctx)
        plain_body = (
            f"Welcome to BFAR Region III HRIS, {ctx['employee_name']}!\n\n"
            f"Username: {user.username}\n"
            f"Temporary Password: {temp_password}\n\n"
            f"Login at: {login_url}\n"
            f"Please change your password on first login."
        )

        # Send to personal email if available, otherwise fall back to work email
        recipient = user.personal_email or f'{user.username}@bfar.gov.ph'

        _send(
            subject='Your BFAR Region III HRIS Account Has Been Created.',
            html_body=html_body,
            plain_body=plain_body,
            to=[recipient],
        )
        logger.info('[accounts.tasks] Account created email -> %s', recipient)
        return {'success': True, 'recipient': recipient}
    
    except Exception as exc:
        logger.error('[accounts.tasks] send_account_created_email failed: %s', exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ----- TASKS 2 — Password Reset ------

@shared_task(
    bind=True, max_retries=3, default_retry_delay=60,
    queue='emails',
    name='apps.accounts.tasks.send_password_reset_email',
)
def send_password_reset_email(self, user_id: int, reset_url: str, is_admin: bool = False):
    """
    Send a password reset link to the user's personal_email.
 
    Usage:
        send_password_reset_email.delay(
            user_id=user.user_id,
            reset_url='http://192.168.x.x:8000/accounts/reset-password/<token>/',
            is_admin=False,
        )
    """
    try:
        from apps.accounts.models import SystemUser
        user = SystemUser.objects.select_related('employee').get(user_id=user_id)

        emp = user.employee
        display_name = emp.get_full_name() if emp else user.username

        ctx = {
            'display_name': display_name,
            'username': user.username,
            'reset_url': reset_url,
            'is_admin': is_admin,
            'expiry_hours': 1,
        }

        # Reuse the base email template with a password-reset block
        html_body = render_to_string('emails/password_reset.html', ctx)
        plain_body = (
            f"Hello {display_name},\n\n"
            f"A password reset was requested for your BFAR HRIS account.\n\n"
            f"Reset link (valid 1 hour):\n{reset_url}\n\n"
            f"If you did not request this, ignore this email.\n"
            f"Your password will not change unless you click the link above."
        )

        recipient = user.personal_email
        if not recipient:
            logger.error(
                '[accounts.tasks] send_password_reset_email: user_id=%s has no personal email.',
                user_id,
            )
            return {'success': False, 'reason': 'no_personal_email'}
        
        _send(
            subject='BFAR HRIS — Password Reset Request',
            html_body=html_body,
            plain_body=plain_body,
            to=[recipient],
        )
        logger.info('[accounts.tasks] Password reset email → %s', recipient)
        return {'success': True, 'recipient': recipient}

    except Exception as exc:
        logger.error('[accounts.tasks] send_password_reset_email failed %s', exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))