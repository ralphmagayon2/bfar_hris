from django.shortcuts import render, get_object_or_404, redirect
from .models import AuditLog, SystemUserActivityLog
from django.core.paginator import Paginator
from django.core.cache import cache
from django.utils import timezone
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import AuditLog
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

from apps.accounts.decorators import login_required, admin_required, role_required

# Cache key constants
_STATS_CACHE_KEY = 'audit:stats'
_STATS_CACHE_TTL = 60 * 5 # 5 minutes - stats don't need to be real-time
_COUNT_CACHE_KEY = 'audit:total_count'
_COUNT_CACHE_TTL = 60 * 2 # 2 minutes

def _get_audit_stats() -> dict:
    """
    Return audit stat counts. Cache for 5 minutes
    then called on every audit_list page load — caching avoids 4 DB count
    queries on every request when logs grow large.
    """
    stats = cache.get(_STATS_CACHE_KEY)
    if stats:
        return stats
    
    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)

    stats = {
        'today': AuditLog.objects.filter(
            performed_at__date=today
        ).count(),
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

    cache.set(_STATS_CACHE_KEY, stats, _STATS_CACHE_TTL)
    return stats

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

    # Cache total count only when no filters are active
    # (filtered counts change per-request so can't be cached)
    is_filtered = any([action_filter, date_filter, search_query])
    if not is_filtered:
        total_logs = cache.get(_COUNT_CACHE_KEY)
        if total_logs is None:
            total_logs = AuditLog.objects.count()
            cache.set(_COUNT_CACHE_KEY, total_logs, _COUNT_CACHE_TTL)
    else:
        total_logs = None # will be set from paginator below

    paginator   = Paginator(logs, 50)
    page_obj    = paginator.get_page(request.GET.get('page', 1))

    if total_logs is None:
        total_logs = paginator.count

    return render(request, 'audit/list.html', {
        'logs':       page_obj,
        'stats':      _get_audit_stats(),
        'total_logs': paginator.count,
        'can_export': actor.role in ('superadmin', 'hr_admin'),
    })


@admin_required
def audit_detail(request, log_id):
    """Single audit log entry — shows before/after JSONB diff."""
    actor = request.current_user
    log   = get_object_or_404(AuditLog, pk=log_id)
    diff  = log.get_diff()

    # If called from the drawer (AJAX), return a lightweight partial
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' \
       or request.GET.get('partial') == '1':
        return render(request, 'audit/detail_partial.html', {
            'log':  log,
            'diff': diff,
        })
    
    return render(request, 'audit/detail.html', {
        'log':        log,
        'diff':       log.get_diff(),
        'can_export': actor.role in ('superadmin', 'hr_admin'),
    })

# Activity log

@admin_required
def activity_list(request):
    """
    System user activity log — login, logout, password changes, lockouts.
    Superadmin + hr_admin see all. hr_staff sees their own only.
    """
    actor = request.current_user

    qs = SystemUserActivityLog.objects.select_related('user').order_by('-performed_at')

    # hr_staff only sees their own activity
    if actor.role == 'hr_staff':
        qs = qs.filter(user=actor)

    # Filters
    action_filter = request.GET.get('action', '').strip()
    search_query  = request.GET.get('q',      '').strip()
    date_filter   = request.GET.get('date',   '').strip()

    if action_filter:
        qs = qs.filter(action=action_filter)
    if date_filter:
        qs = qs.filter(performed_at__date=date_filter)
    if search_query:
        from django.db.models import Q
        qs = qs.filter(
            Q(user__username__icontains=search_query)       |
            Q(attempted_username__icontains=search_query)   |
            Q(description__icontains=search_query)          |
            Q(ip_address__icontains=search_query)
        )

    # Stats
    from django.utils import timezone
    from datetime import timedelta
    now      = timezone.now()
    today    = now.date()
    week_ago = now - timedelta(days=7)

    stats = {
        'logins_today':   qs.filter(performed_at__date=today, action='login').count(),
        'logouts_today':  qs.filter(performed_at__date=today, action='logout').count(),
        'failures_today': qs.filter(performed_at__date=today, action='login_failed').count(),
        'locked_7d':      qs.filter(performed_at__gte=week_ago, action='account_locked').count(),
    }

    paginator = Paginator(qs, 50)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'audit/activity_list.html', {
        'logs':         page_obj,
        'stats':        stats,
        'total_logs':   paginator.count,
        'can_export':   actor.role in ('superadmin', 'hr_admin'),
        'action_filter': action_filter,
        'search_query':  search_query,
        'date_filter':   date_filter,
    })