"""
apps/core/content_processors.py

BFAR Region III — HRIS
Registered in settins.TEMPLATES[0]['OPTIONS']['context_processors'].

inject_current_user
    - Read request.current_user (set by InjectCurrentUserMiddleware)
    and makes it available in every template as `current_user`.

    Usage in any template:
    {% if current_user %}
        Hello, {{ current_user.get_display_name }}
        {% if current_user.is_superadmin %}...{% endif %}
    {% endif %}

    No extra DB query — InjectCurrentUserMiddleware already did the
    SELECT and cached the object on `request`.
"""

def inject_current_user(request):
    """
    Returns `current_user` (System or None) for every template render.
    Also returns a set of permission flags so templates don't need to
    call methods inside {% if %} tags.
    """
    user = getattr(request, 'current_user', None)

    if user is None:
        return {
            'current_user': None,
            'user_can_approve': False,
            'user_can_encode': False,
            'user_is_superadmin': False,
        }
    
    return {
        'current_user': user,
        'user_can_approve': user.can_approve(),
        'user_can_encode': user.can_encode(),
        'user_is_superadmin': user.is_superadmin(),
    }