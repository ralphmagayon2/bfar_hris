# apps/accounts/apps.py
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    # Must add always 'apps.' because apps is inside apps/ folder
    default_auto_field = 'django.db.models.BigAutoField' # Add this for migration
    name = 'apps.accounts'
