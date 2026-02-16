from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            from . import task_signals  # noqa
        except ImportError:
            pass
