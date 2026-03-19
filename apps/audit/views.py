from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import AuditLog
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

from apps.accounts.decorators import login_required, admin_required, role_required


@admin_required
def audit_list(request):
    """
    Read-only audit log viewer.
    superadmin / hr_admin / hr_staff can view.
    Only superadmin + hr_admin see the export button.
    """
    actor = request.current_user

    # Filters
    action_filter = request.GET.get('action', '').strip()
    date_filter   = request.GET.get('date',   '').strip()
    search_query  = request.GET.get('q',      '').strip()

    logs = AuditLog.objects.select_related('performed_by').order_by('-performed_at')

    if action_filter:
        logs = logs.filter(action=action_filter)

    if date_filter:
        logs = logs.filter(performed_at__date=date_filter)

    if search_query:
        logs = logs.filter(
            Q(performed_by__username__icontains=search_query) |
            Q(description__icontains=search_query)            |
            Q(table_affected__icontains=search_query)
        )

    # Stats
    now      = timezone.now()
    today    = now.date()
    week_ago = now - timedelta(days=7)

    stats = {
        'today': AuditLog.objects.filter(performed_at__date=today).count(),
        'unique_users_today': AuditLog.objects.filter(
            performed_at__date=today
        ).values('performed_by').distinct().count(),
        'logins_7d': AuditLog.objects.filter(
            performed_at__gte=week_ago, action='login'
        ).count(),
        'deletes_7d': AuditLog.objects.filter(
            performed_at__gte=week_ago, action='delete'
        ).count(),
    }

    paginator   = Paginator(logs, 50)
    page_obj    = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'audit/list.html', {
        'logs':       page_obj,
        'stats':      stats,
        'total_logs': paginator.count,
        'can_export': actor.role in ('superadmin', 'hr_admin'),
    })


@admin_required
def audit_detail(request, log_id):
    """Single audit log entry — shows before/after JSONB diff."""
    actor = request.current_user
    log   = get_object_or_404(AuditLog, pk=log_id)

    return render(request, 'audit/detail.html', {
        'log':        log,
        'diff':       log.get_diff(),
        'can_export': actor.role in ('superadmin', 'hr_admin'),
    })