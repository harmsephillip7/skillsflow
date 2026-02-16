"""
Management command to load production data with signals disabled.
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from django.db.models.signals import post_save, pre_save
import json


class Command(BaseCommand):
    help = 'Load production data with signals disabled to prevent duplicate records'

    def add_arguments(self, parser):
        parser.add_argument('fixture', type=str, help='Path to the fixture file')

    def handle(self, *args, **options):
        fixture_path = options['fixture']
        
        self.stdout.write('Disconnecting all post_save and pre_save signals...')
        
        # Store original receivers
        post_save_receivers = post_save.receivers.copy()
        pre_save_receivers = pre_save.receivers.copy()
        
        # Disconnect all signals
        post_save.receivers = []
        pre_save.receivers = []
        
        try:
            self.stdout.write(f'Loading fixture: {fixture_path}')
            call_command('loaddata', fixture_path, verbosity=1)
            self.stdout.write(self.style.SUCCESS('Data loaded successfully!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error loading data: {e}'))
            raise
        finally:
            # Restore signals
            post_save.receivers = post_save_receivers
            pre_save.receivers = pre_save_receivers
            self.stdout.write('Signals reconnected.')
