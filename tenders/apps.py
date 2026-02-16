from django.apps import AppConfig


class TendersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenders'
    verbose_name = 'Tender Management'

    def ready(self):
        # Import signals when app is ready
        try:
            import tenders.signals  # noqa
        except ImportError:
            pass
