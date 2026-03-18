"""
URL configuration for bfar_hris project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.core.exceptions import PermissionDenied

def trigger_403(request):
    return PermissionDenied

def trigger_404(request):
    from django.http import Http404
    raise Http404

def trigger_500(request):
    return 1 / 0

# Reordered URL patterns to ensure specific paths are checked before catch-all paths (nagkaproblem ako sa pag-access ng /employees/ dahil nauna yung accounts.urls na may catch-all pattern)
urlpatterns = [
    path('dj-admin/', admin.site.urls),
    
    # 1. SPECIFIC PATHS GO FIRST
    path('employees/', include('apps.employees.urls', namespace='employees')),
    path('biometrics/', include('apps.biometrics.urls', namespace='biometrics')),
    path('api/biometrics/', include('apps.biometrics.urls', namespace='biometrics_api')),
    path('dtr/', include('apps.dtr.urls', namespace='dtr')),
    path('travel-orders/', include('apps.travel_orders.urls', namespace='travel_orders')),
    path('leaves/', include('apps.leaves.urls', namespace='leaves')),
    path('payroll/', include('apps.payroll.urls', namespace='payroll')),
    path('holidays/', include('apps.holidays.urls', namespace='holidays')),
    path('audit/', include('apps.audit.urls', namespace='audit')),

    # 2. ROOT / CATCH-ALL PATHS GO LAST
    path('', include('apps.accounts.urls', namespace='accounts')),
    path('', include('apps.core.urls', namespace='core')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

"""""
urlpatterns = [
    path('dj-admin/', admin.site.urls),
    path('', include('apps.accounts.urls', namespace='accounts')),
    path('', include('apps.core.urls', namespace='core')),
    path('employees/', include('apps.employees.urls', namespace='employees')),
    path('biometrics/', include('apps.biometrics.urls', namespace='biometrics')),
    path('api/biometrics/', include('apps.biometrics.urls', namespace='biometrics_api')),
    path('dtr/', include('apps.dtr.urls', namespace='dtr')),
    path('travel-orders/', include('apps.travel_orders.urls', namespace='travel_orders')),
    path('leaves/', include('apps.leaves.urls', namespace='leaves')),
    path('payroll/', include('apps.payroll.urls', namespace='payroll')),
    path('holidays/', include('apps.holidays.urls', namespace='holidays')),
    path('audit/', include('apps.audit.urls', namespace='audit')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
"""
# ============================================
# MEDIA & STATIC FILES CONFIGURATION
# ============================================

# Development: Serve both static and media files locally
if settings.DEBUG:
    # Static files (CSS, JS, images)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Media urls (user uploads) - only in development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)