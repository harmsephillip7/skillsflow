"""
Management command to bulk-assign year_level to existing modules.
Supports interactive assignment or JSON config file input.

Usage:
    # Interactive mode - prompts for each qualification
    python manage.py assign_module_years
    
    # Auto-assign based on sequence_order ranges (default: 1-10=Year1, 11-20=Year2, 21+=Year3)
    python manage.py assign_module_years --auto
    
    # Use custom ranges for auto-assignment
    python manage.py assign_module_years --auto --year1-max 8 --year2-max 16
    
    # Load from JSON config file
    python manage.py assign_module_years --config /path/to/config.json
    
    # Preview changes without applying
    python manage.py assign_module_years --auto --dry-run
    
    # Filter by specific qualification
    python manage.py assign_module_years --qualification-id 123

Config file format (config.json):
{
    "qualifications": [
        {
            "id": 123,
            "modules": [
                {"id": 1, "year_level": 1},
                {"id": 2, "year_level": 1},
                {"id": 3, "year_level": 2}
            ]
        }
    ]
}

Or by sequence_order ranges:
{
    "qualifications": [
        {
            "id": 123,
            "year_ranges": {
                "1": [1, 10],
                "2": [11, 20],
                "3": [21, 999]
            }
        }
    ]
}
"""
import json
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from academics.models import Qualification, Module


class Command(BaseCommand):
    help = 'Bulk-assign year_level to existing modules based on sequence_order or manual mapping'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Auto-assign based on sequence_order ranges',
        )
        parser.add_argument(
            '--year1-max',
            type=int,
            default=10,
            help='Maximum sequence_order for Year 1 (default: 10)',
        )
        parser.add_argument(
            '--year2-max',
            type=int,
            default=20,
            help='Maximum sequence_order for Year 2 (default: 20)',
        )
        parser.add_argument(
            '--config',
            type=str,
            help='Path to JSON config file for custom year assignments',
        )
        parser.add_argument(
            '--qualification-id',
            type=int,
            help='Only process a specific qualification by ID',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        auto_mode = options['auto']
        config_path = options.get('config')
        qualification_id = options.get('qualification_id')
        year1_max = options['year1_max']
        year2_max = options['year2_max']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be saved'))

        # Get qualifications to process
        qualifications = Qualification.objects.all()
        if qualification_id:
            qualifications = qualifications.filter(id=qualification_id)
            if not qualifications.exists():
                self.stdout.write(self.style.ERROR(f'Qualification with ID {qualification_id} not found'))
                return

        # Annotate with module count
        qualifications = qualifications.annotate(
            module_count=Count('modules')
        ).filter(module_count__gt=0).order_by('code')

        if not qualifications.exists():
            self.stdout.write(self.style.WARNING('No qualifications with modules found'))
            return

        self.stdout.write(self.style.NOTICE(f'Found {qualifications.count()} qualification(s) with modules'))

        if config_path:
            self._process_config_file(config_path, dry_run)
        elif auto_mode:
            self._auto_assign(qualifications, year1_max, year2_max, dry_run)
        else:
            self._interactive_assign(qualifications, dry_run)

    def _get_year_from_sequence(self, sequence_order, year1_max, year2_max):
        """Determine year level from sequence order."""
        if sequence_order is None:
            return 1
        if sequence_order <= year1_max:
            return 1
        elif sequence_order <= year2_max:
            return 2
        else:
            return 3

    def _auto_assign(self, qualifications, year1_max, year2_max, dry_run):
        """Auto-assign year levels based on sequence_order ranges."""
        self.stdout.write(f'\nAuto-assigning with ranges: Year1 ≤{year1_max}, Year2 ≤{year2_max}, Year3 >{year2_max}')
        
        total_updated = 0
        
        for qual in qualifications:
            self.stdout.write(f'\n{self.style.MIGRATE_HEADING(qual.code)} - {qual.title}')
            
            modules = Module.objects.filter(qualification=qual).order_by('sequence_order', 'code')
            year_counts = {1: 0, 2: 0, 3: 0}
            updates = []
            
            for module in modules:
                new_year = self._get_year_from_sequence(module.sequence_order, year1_max, year2_max)
                year_counts[new_year] += 1
                
                if module.year_level != new_year:
                    updates.append((module, module.year_level, new_year))
            
            # Display summary
            self.stdout.write(f'  Distribution: Year1={year_counts[1]}, Year2={year_counts[2]}, Year3={year_counts[3]}')
            
            if updates:
                self.stdout.write(f'  Changes required: {len(updates)} modules')
                for module, old_year, new_year in updates[:5]:  # Show first 5
                    self.stdout.write(f'    - {module.code}: Year {old_year} → Year {new_year}')
                if len(updates) > 5:
                    self.stdout.write(f'    ... and {len(updates) - 5} more')
                
                if not dry_run:
                    with transaction.atomic():
                        for module, old_year, new_year in updates:
                            module.year_level = new_year
                            module.save(update_fields=['year_level'])
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Updated {len(updates)} modules'))
                    total_updated += len(updates)
            else:
                self.stdout.write(self.style.SUCCESS('  ✓ No changes needed'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\nDRY RUN complete. Would update {sum(len([u for u in self._get_updates(q, year1_max, year2_max) for q in qualifications])} modules'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nTotal modules updated: {total_updated}'))

    def _get_updates(self, qual, year1_max, year2_max):
        """Helper to get pending updates for a qualification."""
        modules = Module.objects.filter(qualification=qual)
        updates = []
        for module in modules:
            new_year = self._get_year_from_sequence(module.sequence_order, year1_max, year2_max)
            if module.year_level != new_year:
                updates.append(module)
        return updates

    def _interactive_assign(self, qualifications, dry_run):
        """Interactive mode - prompt for each qualification."""
        self.stdout.write('\nInteractive mode - press Enter to skip, or enter year assignments')
        self.stdout.write('Options: auto, skip, or comma-separated list like "1-5:1,6-10:2,11+:3"\n')
        
        for qual in qualifications:
            self.stdout.write(f'\n{self.style.MIGRATE_HEADING(qual.code)} - {qual.title}')
            
            modules = Module.objects.filter(qualification=qual).order_by('sequence_order', 'code')
            
            # Show current distribution
            current_counts = {1: 0, 2: 0, 3: 0}
            for module in modules:
                current_counts[module.year_level] += 1
            self.stdout.write(f'  Current: Year1={current_counts[1]}, Year2={current_counts[2]}, Year3={current_counts[3]}')
            
            # Show modules list
            self.stdout.write('  Modules:')
            for i, module in enumerate(modules[:15], 1):
                seq = module.sequence_order if module.sequence_order else '-'
                self.stdout.write(f'    {i}. [{seq}] {module.code} (Year {module.year_level})')
            if modules.count() > 15:
                self.stdout.write(f'    ... and {modules.count() - 15} more modules')
            
            try:
                user_input = input('  Assignment (auto/skip/ranges): ').strip().lower()
            except (EOFError, KeyboardInterrupt):
                self.stdout.write('\nAborted.')
                return
            
            if not user_input or user_input == 'skip':
                self.stdout.write('  Skipped')
                continue
            
            if user_input == 'auto':
                # Auto-assign with default ranges
                self._auto_assign_qualification(qual, 10, 20, dry_run)
                continue
            
            # Parse custom ranges like "1-5:1,6-10:2,11+:3"
            try:
                self._parse_and_apply_ranges(qual, user_input, dry_run)
            except ValueError as e:
                self.stdout.write(self.style.ERROR(f'  Invalid format: {e}'))
                continue

    def _auto_assign_qualification(self, qual, year1_max, year2_max, dry_run):
        """Auto-assign year levels for a single qualification."""
        modules = Module.objects.filter(qualification=qual)
        updated = 0
        
        with transaction.atomic():
            for module in modules:
                new_year = self._get_year_from_sequence(module.sequence_order, year1_max, year2_max)
                if module.year_level != new_year:
                    if not dry_run:
                        module.year_level = new_year
                        module.save(update_fields=['year_level'])
                    updated += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Updated {updated} modules'))

    def _parse_and_apply_ranges(self, qual, range_string, dry_run):
        """Parse range string like '1-5:1,6-10:2,11+:3' and apply."""
        modules = list(Module.objects.filter(qualification=qual).order_by('sequence_order', 'code'))
        module_count = len(modules)
        
        ranges = []
        for part in range_string.split(','):
            part = part.strip()
            if ':' not in part:
                raise ValueError(f"Missing ':' in '{part}'")
            
            range_part, year_str = part.rsplit(':', 1)
            year = int(year_str)
            if year not in [1, 2, 3]:
                raise ValueError(f"Year must be 1, 2, or 3, got {year}")
            
            if '+' in range_part:
                # Handle "11+" format
                start = int(range_part.replace('+', ''))
                end = module_count
            elif '-' in range_part:
                # Handle "1-5" format
                start_str, end_str = range_part.split('-')
                start = int(start_str)
                end = int(end_str)
            else:
                # Single number
                start = end = int(range_part)
            
            ranges.append((start, end, year))
        
        # Apply ranges
        updated = 0
        with transaction.atomic():
            for i, module in enumerate(modules, 1):
                for start, end, year in ranges:
                    if start <= i <= end:
                        if module.year_level != year:
                            if not dry_run:
                                module.year_level = year
                                module.save(update_fields=['year_level'])
                            updated += 1
                        break
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Updated {updated} modules'))

    def _process_config_file(self, config_path, dry_run):
        """Process a JSON config file for year assignments."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'Config file not found: {config_path}'))
            return
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f'Invalid JSON in config file: {e}'))
            return
        
        self.stdout.write(f'Loading config from: {config_path}')
        
        total_updated = 0
        qualifications_config = config.get('qualifications', [])
        
        for qual_config in qualifications_config:
            qual_id = qual_config.get('id')
            if not qual_id:
                self.stdout.write(self.style.WARNING('Skipping qualification config without ID'))
                continue
            
            try:
                qual = Qualification.objects.get(id=qual_id)
            except Qualification.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Qualification {qual_id} not found, skipping'))
                continue
            
            self.stdout.write(f'\n{self.style.MIGRATE_HEADING(qual.code)} - {qual.title}')
            
            if 'modules' in qual_config:
                # Direct module ID to year mapping
                updated = self._apply_module_mapping(qual, qual_config['modules'], dry_run)
            elif 'year_ranges' in qual_config:
                # Sequence order ranges
                updated = self._apply_year_ranges(qual, qual_config['year_ranges'], dry_run)
            else:
                self.stdout.write(self.style.WARNING('  No modules or year_ranges specified'))
                continue
            
            total_updated += updated
        
        self.stdout.write(self.style.SUCCESS(f'\nTotal modules updated: {total_updated}'))

    def _apply_module_mapping(self, qual, modules_config, dry_run):
        """Apply direct module ID to year level mapping."""
        updated = 0
        
        with transaction.atomic():
            for module_config in modules_config:
                module_id = module_config.get('id')
                year_level = module_config.get('year_level')
                
                if not module_id or not year_level:
                    continue
                
                try:
                    module = Module.objects.get(id=module_id, qualification=qual)
                    if module.year_level != year_level:
                        if not dry_run:
                            module.year_level = year_level
                            module.save(update_fields=['year_level'])
                        updated += 1
                        self.stdout.write(f'  {module.code}: Year {module.year_level} → Year {year_level}')
                except Module.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'  Module {module_id} not found in qualification'))
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Updated {updated} modules'))
        return updated

    def _apply_year_ranges(self, qual, year_ranges, dry_run):
        """Apply year level based on sequence_order ranges from config."""
        updated = 0
        modules = Module.objects.filter(qualification=qual)
        
        # Convert string keys to int and parse ranges
        parsed_ranges = []
        for year_str, range_vals in year_ranges.items():
            year = int(year_str)
            start, end = range_vals
            parsed_ranges.append((start, end, year))
        
        with transaction.atomic():
            for module in modules:
                seq = module.sequence_order or 0
                for start, end, year in parsed_ranges:
                    if start <= seq <= end:
                        if module.year_level != year:
                            if not dry_run:
                                module.year_level = year
                                module.save(update_fields=['year_level'])
                            updated += 1
                        break
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Updated {updated} modules'))
        return updated
