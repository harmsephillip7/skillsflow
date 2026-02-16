from django.apps import AppConfig


class HrConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hr'
    verbose_name = 'Human Resources'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            from . import signals  # noqa
        except ImportError:
            pass
