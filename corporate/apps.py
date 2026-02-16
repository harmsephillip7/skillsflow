from django.apps import AppConfig


class CorporateConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'corporate'

    def ready(self):
        import corporate.service_signals  # noqa: F401
