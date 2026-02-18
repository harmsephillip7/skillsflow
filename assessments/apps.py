from django.apps import AppConfig


class AssessmentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assessments'
    
    def ready(self):
        # Import signals to register them
        from . import signals  # noqa
