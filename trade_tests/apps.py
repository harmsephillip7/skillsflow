from django.apps import AppConfig


class TradeTestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trade_tests'
    verbose_name = 'Trade Tests'

    def ready(self):
        import trade_tests.signals  # noqa
