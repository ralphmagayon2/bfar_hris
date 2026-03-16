# bfar_hris/__init__.py
# This makes Celery start whenever Django starts.
from .celery import app as celery_app

__all__ = ('celery_app',)