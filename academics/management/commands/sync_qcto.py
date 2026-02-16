"""
Management command to sync qualification data from QCTO website
Scheduled to run on the 15th of each month via cron

Usage:
    python manage.py sync_qcto
    python manage.py sync_qcto --dry-run
    python manage.py sync_qcto --qualification SAQA123

Cron setup (run on 15th of each month at 6 AM):
    0 6 15 * * cd /path/to/skillsflow && python manage.py sync_qcto
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from academics.models import Qualification, QCTOSyncLog, QCTOQualificationChange
from academics.services.qcto_sync import QCTOScraper


class Command(BaseCommand):
    help = 'Sync qualification data from QCTO website'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what changes would be detected without saving to database',
        )
        parser.add_argument(
            '--qualification',
            type=str,
            help='Sync only a specific qualification by SAQA ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        specific_saqa_id = options.get('qualification')
        
        self.stdout.write(self.style.NOTICE(
            f'Starting QCTO sync at {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
        ))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be saved'))
        
        # Create sync log entry
        sync_log = None
        if not dry_run:
            sync_log = QCTOSyncLog.objects.create(
                trigger_type='SCHEDULED',
                status='RUNNING',
                started_at=timezone.now()
            )
        
        try:
            scraper = QCTOScraper()
            
            # Get qualifications to sync
            if specific_saqa_id:
                qualifications = Qualification.objects.filter(
                    saqa_id=specific_saqa_id, 
                    is_active=True
                )
            else:
                qualifications = Qualification.objects.filter(is_active=True)
            
            total_checked = 0
            total_changes = 0
            changes_list = []
            
            self.stdout.write(f'\nSyncing {qualifications.count()} qualifications...\n')
            
            for qualification in qualifications:
                total_checked += 1
                self.stdout.write(f'Checking: {qualification.saqa_id} - {qualification.short_title}')
                
                try:
                    # Fetch data from QCTO
                    qcto_data = scraper.fetch_qualification_details(qualification.saqa_id)
                    
                    if not qcto_data:
                        self.stdout.write(self.style.WARNING(f'  No data found for {qualification.saqa_id}'))
                        continue
                    
                    # Compare fields
                    changes = self._compare_fields(qualification, qcto_data)
                    
                    if changes:
                        total_changes += len(changes)
                        for field_name, old_val, new_val in changes:
                            self.stdout.write(self.style.SUCCESS(
                                f'  CHANGE: {field_name}: "{old_val}" -> "{new_val}"'
                            ))
                            
                            if not dry_run and sync_log:
                                QCTOQualificationChange.objects.create(
                                    sync_log=sync_log,
                                    qualification=qualification,
                                    field_name=field_name,
                                    old_value=str(old_val),
                                    new_value=str(new_val),
                                    status='PENDING'
                                )
                                
                            changes_list.append({
                                'saqa_id': qualification.saqa_id,
                                'field': field_name,
                                'old_value': str(old_val),
                                'new_value': str(new_val)
                            })
                    else:
                        self.stdout.write(self.style.NOTICE('  No changes detected'))
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Error: {str(e)}'))
                    continue
            
            # Update sync log
            if sync_log:
                sync_log.qualifications_checked = total_checked
                sync_log.qualifications_updated = total_changes
                sync_log.changes_detected = changes_list
                sync_log.status = 'COMPLETED'
                sync_log.completed_at = timezone.now()
                sync_log.save()
            
            # Summary
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 50))
            self.stdout.write(self.style.SUCCESS(f'QCTO Sync Complete'))
            self.stdout.write(f'  Qualifications checked: {total_checked}')
            self.stdout.write(f'  Changes detected: {total_changes}')
            if total_changes > 0:
                self.stdout.write(self.style.WARNING(
                    f'  Review pending changes at /academics/qcto-sync/'
                ))
            self.stdout.write(self.style.SUCCESS('=' * 50))
            
        except Exception as e:
            if sync_log:
                sync_log.status = 'FAILED'
                sync_log.error_message = str(e)
                sync_log.completed_at = timezone.now()
                sync_log.save()
            
            self.stdout.write(self.style.ERROR(f'\nSync failed: {str(e)}'))
            raise
    
    def _compare_fields(self, qualification, qcto_data):
        """
        Compare qualification fields with QCTO data
        Returns list of (field_name, old_value, new_value) tuples
        """
        changes = []
        
        # Fields to compare
        field_mapping = {
            'title': 'title',
            'nqf_level': 'nqf_level',
            'credits': 'credits',
            'registration_end': 'registration_end_date',
            'last_enrollment_date': 'last_enrolment_date',
            'minimum_duration_months': 'minimum_duration',
        }
        
        for model_field, qcto_field in field_mapping.items():
            if qcto_field not in qcto_data:
                continue
                
            current_value = getattr(qualification, model_field, None)
            new_value = qcto_data.get(qcto_field)
            
            # Skip if new value is None/empty
            if new_value is None or new_value == '':
                continue
            
            # Normalize values for comparison
            if isinstance(current_value, int):
                try:
                    new_value = int(new_value)
                except (ValueError, TypeError):
                    continue
            
            # Compare
            if str(current_value) != str(new_value):
                changes.append((model_field, current_value, new_value))
        
        return changes
