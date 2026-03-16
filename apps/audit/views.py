# apps/list/views.py
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
from .models import AuditLog
from django.contrib import messages

def _get_session_user(request):
    """Get the logged-in SystemUser from session."""
    from apps.accounts.models import SystemUser
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    
    try:
        return SystemUser.objects.select_related('employee').get(ph=user_id)
    except SystemUser.DoesNotExist:
        return None
    
def audit_list(request):
    """
    Read-only audit log viewer.

    Access:
        superadmin -> full log, all users, export button visible
        hr_admin   -> full log, users, export button visible
        hr_staff   -> full log, all users, no export button
        viewer     -> 403 forbidden — audit log is not a self-service feature
    """
    user = _get_session_user(request)

    # Not logged in
    if not user:
        from django.shortcuts import redirect
        messages.warning(request, "You don't have permssion on this page.")
        return redirect('accounts:login')

    # Viewer has no business here
    if user.role == 'viewer':
        return HttpResponseForbidden(
            "You do not have permission to view the audit log."
        )
    
    # Filters
    action_filter = request.GET.get('action', '')
    date_filter = request.GET.get('date', '')
    search_query = request.GET.get('q', '')

    logs = AuditLog.objects.select_related('performed_by').order_by('-performed_at')

    if action_filter:
        logs = logs.filter(action=action_filter)

    if date_filter:
        logs = logs.filter(performed_at__date=date_filter)

    if search_query:
        logs = logs.filter(
            Q(performed_by__username__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(table_affected__icontains=search_query)
        )

    # Stats
    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)

    stats = {
        'today': AuditLog.objects.filter(performed_at__date=today).count(),
        'unique_users_today': AuditLog.objects.filter(
            performed_at__date=today
        ).values('performed_by').distinct().count(),
        'logins_7d': AuditLog.objects.filter(
            performed_at__gte=week_ago,
            action='login'
        ).count(),
        'deletes_7d': AuditLog.objects.filter(
            performed_at__gte=week_ago,
            action='delete'
        ).count(),
    }

    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'audit/list.html', {
        'logs': page_obj,
        'stats': stats,
        'total_logs': paginator.count,
        'system_user': user,

        # Pass role flags - template uses these for conditional UI only
        'can_export': user.role in ('superadmin', 'hr_admin')
    })

def audit_detail(request, log_id):
    """
    Single audit log entry — shows before/after JSONB diff.
    Same access rules as audit_list.
    """
    user = _get_session_user(request)

    if not user:
        from django.shortcuts import redirect
        return redirect('accounts:login')
    
    if user.role == 'viewer':
        return HttpResponseForbidden()
    
    log = get_object_or_404(AuditLog, pk=log_id)

    return render(request, 'audit/detail.html', {
        'log': log,
        'diff': log.get_diff(),
        'system_user': user,
        'can_export': user.role in ('superadmin', 'hr_admin'),
    })

# def list(request):
#     return render(request, 'audit/list.html')