import os
from celery import Celery
from django.conf import settings

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bfar_hris.settings')

# Create Celery app
app = Celery('bfar_hris')

# Load config from Django settings with 'CELERY' prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

@app.task(bind=True)
def debug_task(self):
    """Smoke-test task — run with: celery -A bfar_hris call bfar_hris.celery.debug_task"""
    print(f'Request: {self.request!r}')