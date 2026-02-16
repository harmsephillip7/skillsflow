"""
Management command to migrate legacy clients to the new onboarding system.
This command creates completed ClientOnboarding and ServiceOnboarding records
for existing clients that were set up before the onboarding system was introduced.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from corporate.models import (
    CorporateClient, ClientOnboarding, ServiceOnboarding,
    ClientServiceSubscription
)


class Command(BaseCommand):
    help = 'Migrate legacy clients to the new onboarding system with completed status'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually creating records',
        )
        parser.add_argument(
            '--client-id',
            type=int,
            help='Migrate only a specific client by ID',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        client_id = options.get('client_id')
        
        self.stdout.write(self.style.NOTICE('Starting legacy client onboarding migration...'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No records will be created'))
        
        # Get clients to migrate
        clients = CorporateClient.objects.filter(status='ACTIVE')
        if client_id:
            clients = clients.filter(pk=client_id)
        
        # Track stats
        clients_migrated = 0
        client_onboardings_created = 0
        service_onboardings_created = 0
        skipped = 0
        
        for client in clients:
            self.stdout.write(f'\nProcessing: {client.company_name} (ID: {client.pk})')
            
            # Check if client onboarding already exists
            if ClientOnboarding.objects.filter(client=client).exists():
                self.stdout.write(self.style.NOTICE(f'  - Client onboarding already exists, skipping'))
                skipped += 1
                continue
            
            # Get active subscriptions
            subscriptions = ClientServiceSubscription.objects.filter(
                client=client,
                status='ACTIVE'
            )
            
            if not subscriptions.exists():
                self.stdout.write(self.style.NOTICE(f'  - No active subscriptions, skipping'))
                skipped += 1
                continue
            
            # Create completed ClientOnboarding
            if not dry_run:
                onboarding = ClientOnboarding.objects.create(
                    client=client,
                    status='COMPLETED',
                    current_step=5,  # Final step
                    step_statuses={
                        '1': {'completed': True, 'completed_at': timezone.now().isoformat()},
                        '2': {'completed': True, 'completed_at': timezone.now().isoformat()},
                        '3': {'completed': True, 'completed_at': timezone.now().isoformat()},
                        '4': {'completed': True, 'completed_at': timezone.now().isoformat()},
                        '5': {'completed': True, 'completed_at': timezone.now().isoformat()},
                    },
                    assigned_to=client.account_manager,
                    started_at=client.created,
                    completed_at=timezone.now()
                )
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created ClientOnboarding (completed)'))
            else:
                self.stdout.write(f'  Would create ClientOnboarding (completed)')
            
            client_onboardings_created += 1
            
            # Create ServiceOnboarding for each subscription
            for sub in subscriptions:
                service_type = sub.service.service_type if hasattr(sub.service, 'service_type') else None
                
                if not service_type or service_type not in ['WSP_ATR', 'EE', 'BBBEE']:
                    self.stdout.write(f'  - Skipping subscription {sub.pk}: unsupported service type')
                    continue
                
                if ServiceOnboarding.objects.filter(subscription=sub).exists():
                    self.stdout.write(f'  - Service onboarding for {sub.service.name} already exists')
                    continue
                
                # Determine total steps based on service type
                if service_type == 'WSP_ATR':
                    total_steps = 8
                elif service_type == 'EE':
                    total_steps = 7
                elif service_type == 'BBBEE':
                    total_steps = 6
                else:
                    total_steps = 5
                
                if not dry_run:
                    ServiceOnboarding.objects.create(
                        subscription=sub,
                        client=client,
                        service_type=service_type,
                        status='COMPLETED',
                        current_step=total_steps,
                        total_steps=total_steps,
                        started_at=sub.start_date,
                        completed_at=timezone.now()
                    )
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created ServiceOnboarding for {sub.service.name} (completed)'))
                else:
                    self.stdout.write(f'  Would create ServiceOnboarding for {sub.service.name} (completed)')
                
                service_onboardings_created += 1
            
            clients_migrated += 1
        
        # Summary
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('Migration Summary:'))
        self.stdout.write(f'  Clients processed: {clients_migrated}')
        self.stdout.write(f'  Client onboardings created: {client_onboardings_created}')
        self.stdout.write(f'  Service onboardings created: {service_onboardings_created}')
        self.stdout.write(f'  Clients skipped: {skipped}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - Run without --dry-run to create records'))
        else:
            self.stdout.write(self.style.SUCCESS('\nMigration completed successfully!'))
