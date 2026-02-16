"""
Custom loaddata command that disables signals during loading.
This is necessary for migrations between databases where signals 
may try to access related objects that haven't been loaded yet.
"""
from django.core.management.commands.loaddata import Command as LoadDataCommand
from django.db.models.signals import post_save, pre_save, post_delete, pre_delete, m2m_changed


class Command(LoadDataCommand):
    help = 'Load data with signals temporarily disabled'

    def handle(self, *args, **options):
        # Store all receivers
        receivers_post_save = post_save.receivers[:]
        receivers_pre_save = pre_save.receivers[:]
        receivers_post_delete = post_delete.receivers[:]
        receivers_pre_delete = pre_delete.receivers[:]
        receivers_m2m = m2m_changed.receivers[:]

        # Disconnect all signals
        post_save.receivers = []
        pre_save.receivers = []
        post_delete.receivers = []
        pre_delete.receivers = []
        m2m_changed.receivers = []

        try:
            self.stdout.write('Loading data with signals disabled...')
            super().handle(*args, **options)
            self.stdout.write(self.style.SUCCESS('Data loaded successfully!'))
        finally:
            # Restore all signals
            post_save.receivers = receivers_post_save
            pre_save.receivers = receivers_pre_save
            post_delete.receivers = receivers_post_delete
            pre_delete.receivers = receivers_pre_delete
            m2m_changed.receivers = receivers_m2m
            self.stdout.write('Signals restored.')
