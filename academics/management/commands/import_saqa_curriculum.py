"""
Management command to import Workplace Module Outcomes from SAQA curriculum documents.
Imports WM outcomes for all qualifications in the system or a specific qualification.

Usage:
    python manage.py import_saqa_curriculum
    python manage.py import_saqa_curriculum --qualification SAQA123
    python manage.py import_saqa_curriculum --dry-run
    python manage.py import_saqa_curriculum --from-file curriculum.json

This is typically run once to populate the WorkplaceModuleOutcome model,
then run again when new qualifications are added.
"""
import json
import re
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from academics.models import Qualification, Module, WorkplaceModuleOutcome

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_SCRAPING = True
except ImportError:
    HAS_SCRAPING = False


class SAQACurriculumScraper:
    """
    Scraper for SAQA/QCTO curriculum documents.
    Note: SAQA website structure may change - this may need updates.
    """
    
    SAQA_BASE_URL = "https://regqs.saqa.org.za/viewQualification.php"
    QCTO_BASE_URL = "https://www.qcto.org.za/qualifications"
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_qualification_page(self, saqa_id):
        """Fetch the SAQA qualification page"""
        url = f"{self.SAQA_BASE_URL}?id={saqa_id}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    
    def parse_workplace_outcomes(self, soup, module_code):
        """
        Parse workplace module outcomes from SAQA page HTML.
        
        Expected structure (example - actual structure varies):
        - Workplace Module outcomes typically listed under each WM section
        - May include outcome code, title, range statement, assessment criteria
        """
        outcomes = []
        
        # Look for sections containing workplace module information
        # This pattern may need adjustment based on actual SAQA page structure
        wm_sections = soup.find_all(['div', 'section', 'table'], 
                                    string=re.compile(r'workplace|WM|work.integrated', re.I))
        
        for section in wm_sections:
            # Extract outcome items - common patterns
            outcome_items = section.find_all(['li', 'tr', 'p'], 
                                             string=re.compile(r'^\s*\d+\.|\bWM\d+', re.I))
            
            for idx, item in enumerate(outcome_items, 1):
                text = item.get_text(strip=True)
                
                # Try to extract structured outcome data
                outcome = {
                    'outcome_code': f'WM{idx:02d}',
                    'outcome_number': idx,
                    'title': text[:500],
                    'description': '',
                    'range_statement': '',
                    'assessment_criteria': '',
                }
                
                # Look for associated range/criteria in sibling elements
                next_elem = item.find_next_sibling()
                while next_elem:
                    next_text = next_elem.get_text(strip=True).lower()
                    if 'range' in next_text:
                        outcome['range_statement'] = next_elem.get_text(strip=True)
                    elif 'criteria' in next_text or 'assessment' in next_text:
                        outcome['assessment_criteria'] = next_elem.get_text(strip=True)
                    else:
                        break
                    next_elem = next_elem.find_next_sibling()
                
                outcomes.append(outcome)
        
        return outcomes
    
    def fetch_curriculum_outcomes(self, saqa_id):
        """
        Fetch and parse all workplace module outcomes for a qualification.
        Returns dict: {module_code: [outcomes]}
        """
        try:
            soup = self.fetch_qualification_page(saqa_id)
            
            # This is a simplified implementation
            # Real SAQA pages have complex structure that varies by qualification
            # You may need to customize parsing based on actual page structure
            
            results = {}
            
            # Find all workplace module references
            wm_pattern = re.compile(r'(WM\d+|Workplace Module \d+)', re.I)
            wm_elements = soup.find_all(string=wm_pattern)
            
            for elem in wm_elements:
                match = wm_pattern.search(elem)
                if match:
                    module_code = match.group(1).upper().replace(' ', '')
                    
                    # Get outcomes for this module section
                    parent = elem.find_parent(['div', 'section', 'table'])
                    if parent:
                        outcomes = self.parse_workplace_outcomes(parent, module_code)
                        if outcomes:
                            results[module_code] = outcomes
            
            return results
            
        except Exception as e:
            if self.verbose:
                print(f"Error fetching curriculum for SAQA {saqa_id}: {e}")
            return {}


class Command(BaseCommand):
    help = 'Import Workplace Module Outcomes from SAQA curriculum documents'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without saving to database',
        )
        parser.add_argument(
            '--qualification',
            type=str,
            help='Import only a specific qualification by SAQA ID',
        )
        parser.add_argument(
            '--from-file',
            type=str,
            help='Import from a JSON file instead of scraping SAQA website',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing outcomes (default is skip)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        specific_saqa_id = options.get('qualification')
        from_file = options.get('from_file')
        update_existing = options.get('update_existing', False)
        
        self.stdout.write(self.style.NOTICE(
            f'Starting SAQA curriculum import at {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
        ))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be saved'))
        
        # Get qualifications to process
        if specific_saqa_id:
            qualifications = Qualification.objects.filter(
                saqa_id=specific_saqa_id, 
                is_active=True
            )
        else:
            qualifications = Qualification.objects.filter(is_active=True)
        
        if not qualifications.exists():
            self.stdout.write(self.style.ERROR('No qualifications found to process'))
            return
        
        self.stdout.write(f'\nProcessing {qualifications.count()} qualifications...\n')
        
        total_outcomes_created = 0
        total_outcomes_updated = 0
        total_outcomes_skipped = 0
        
        if from_file:
            # Import from JSON file
            total_created, total_updated, total_skipped = self.import_from_file(
                from_file, qualifications, dry_run, update_existing
            )
            total_outcomes_created = total_created
            total_outcomes_updated = total_updated
            total_outcomes_skipped = total_skipped
        else:
            # Scrape from SAQA website
            if not HAS_SCRAPING:
                self.stdout.write(self.style.ERROR(
                    'Scraping libraries not available. Install requests and beautifulsoup4, '
                    'or use --from-file with a JSON file.'
                ))
                return
            
            scraper = SAQACurriculumScraper(verbose=True)
            
            for qualification in qualifications:
                self.stdout.write(f'\nProcessing: {qualification.saqa_id} - {qualification.short_title}')
                
                try:
                    created, updated, skipped = self.process_qualification(
                        qualification, scraper, dry_run, update_existing
                    )
                    total_outcomes_created += created
                    total_outcomes_updated += updated
                    total_outcomes_skipped += skipped
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Error: {e}'))
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('Import Complete!'))
        self.stdout.write(f'  Outcomes created: {total_outcomes_created}')
        self.stdout.write(f'  Outcomes updated: {total_outcomes_updated}')
        self.stdout.write(f'  Outcomes skipped: {total_outcomes_skipped}')
    
    def import_from_file(self, file_path, qualifications, dry_run, update_existing):
        """
        Import outcomes from a JSON file.
        
        Expected JSON format:
        {
            "SAQA_ID": {
                "WM01": [
                    {
                        "outcome_code": "WM01.1",
                        "outcome_number": 1,
                        "title": "Outcome title",
                        "description": "...",
                        "range_statement": "...",
                        "assessment_criteria": "..."
                    }
                ]
            }
        }
        """
        total_created = 0
        total_updated = 0
        total_skipped = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading file: {e}'))
            return 0, 0, 0
        
        qual_ids = {q.saqa_id: q for q in qualifications}
        
        for saqa_id, modules_data in data.items():
            if saqa_id not in qual_ids:
                self.stdout.write(self.style.WARNING(f'  Skipping SAQA {saqa_id} - not in database'))
                continue
            
            qualification = qual_ids[saqa_id]
            self.stdout.write(f'\nProcessing: {saqa_id} - {qualification.short_title}')
            
            # Get workplace modules for this qualification
            wm_modules = {
                m.code.upper(): m 
                for m in Module.objects.filter(
                    qualification=qualification,
                    module_type='W',
                    is_active=True
                )
            }
            
            for module_code, outcomes in modules_data.items():
                module_code_upper = module_code.upper()
                
                if module_code_upper not in wm_modules:
                    self.stdout.write(self.style.WARNING(
                        f'  Module {module_code} not found for {saqa_id}'
                    ))
                    continue
                
                module = wm_modules[module_code_upper]
                
                for outcome_data in outcomes:
                    created, updated, skipped = self.create_or_update_outcome(
                        module, outcome_data, saqa_id, dry_run, update_existing
                    )
                    total_created += created
                    total_updated += updated
                    total_skipped += skipped
        
        return total_created, total_updated, total_skipped
    
    def process_qualification(self, qualification, scraper, dry_run, update_existing):
        """Process a single qualification - scrape and import outcomes"""
        total_created = 0
        total_updated = 0
        total_skipped = 0
        
        # Fetch outcomes from SAQA
        curriculum_data = scraper.fetch_curriculum_outcomes(qualification.saqa_id)
        
        if not curriculum_data:
            self.stdout.write(self.style.WARNING(
                f'  No workplace outcomes found for {qualification.saqa_id}'
            ))
            return 0, 0, 0
        
        # Get workplace modules for this qualification
        wm_modules = {
            m.code.upper(): m 
            for m in Module.objects.filter(
                qualification=qualification,
                module_type='W',
                is_active=True
            )
        }
        
        for module_code, outcomes in curriculum_data.items():
            # Try to match module code
            module_code_normalized = module_code.upper().replace('WORKPLACE MODULE ', 'WM')
            
            if module_code_normalized not in wm_modules:
                # Try partial match
                matched = None
                for code, mod in wm_modules.items():
                    if module_code_normalized in code or code in module_code_normalized:
                        matched = mod
                        break
                
                if not matched:
                    self.stdout.write(self.style.WARNING(
                        f'  Module {module_code} not found in database'
                    ))
                    continue
                module = matched
            else:
                module = wm_modules[module_code_normalized]
            
            self.stdout.write(f'  Importing {len(outcomes)} outcomes for {module.code}')
            
            for outcome_data in outcomes:
                created, updated, skipped = self.create_or_update_outcome(
                    module, outcome_data, qualification.saqa_id, dry_run, update_existing
                )
                total_created += created
                total_updated += updated
                total_skipped += skipped
        
        return total_created, total_updated, total_skipped
    
    def create_or_update_outcome(self, module, outcome_data, saqa_id, dry_run, update_existing):
        """Create or update a single outcome"""
        outcome_code = outcome_data.get('outcome_code', f'O{outcome_data.get("outcome_number", 1)}')
        
        existing = WorkplaceModuleOutcome.objects.filter(
            module=module,
            outcome_code=outcome_code
        ).first()
        
        if existing:
            if update_existing:
                if dry_run:
                    self.stdout.write(f'    Would update: {outcome_code}')
                    return 0, 1, 0
                
                # Update existing
                existing.title = outcome_data.get('title', existing.title)
                existing.description = outcome_data.get('description', existing.description)
                existing.range_statement = outcome_data.get('range_statement', existing.range_statement)
                existing.assessment_criteria = outcome_data.get('assessment_criteria', existing.assessment_criteria)
                existing.outcome_number = outcome_data.get('outcome_number', existing.outcome_number)
                existing.saqa_source = f"SAQA {saqa_id}"
                existing.imported_at = timezone.now()
                existing.save()
                
                self.stdout.write(f'    Updated: {outcome_code}')
                return 0, 1, 0
            else:
                self.stdout.write(f'    Skipped (exists): {outcome_code}')
                return 0, 0, 1
        
        # Create new
        if dry_run:
            self.stdout.write(f'    Would create: {outcome_code} - {outcome_data.get("title", "")[:50]}')
            return 1, 0, 0
        
        WorkplaceModuleOutcome.objects.create(
            module=module,
            outcome_code=outcome_code,
            outcome_number=outcome_data.get('outcome_number', 1),
            title=outcome_data.get('title', '')[:500],
            description=outcome_data.get('description', ''),
            range_statement=outcome_data.get('range_statement', ''),
            assessment_criteria=outcome_data.get('assessment_criteria', ''),
            estimated_hours=outcome_data.get('estimated_hours'),
            outcome_group=outcome_data.get('outcome_group', ''),
            saqa_source=f"SAQA {saqa_id}",
            imported_at=timezone.now(),
            is_active=True,
        )
        
        self.stdout.write(self.style.SUCCESS(f'    Created: {outcome_code}'))
        return 1, 0, 0
    
    def generate_sample_json(self):
        """
        Generate a sample JSON structure for manual curriculum entry.
        Useful when SAQA scraping doesn't work for specific qualifications.
        """
        sample = {
            "SAQA_ID_HERE": {
                "WM01": [
                    {
                        "outcome_code": "WM01.1",
                        "outcome_number": 1,
                        "title": "Demonstrate understanding of workplace health and safety",
                        "description": "The learner must demonstrate...",
                        "range_statement": "This outcome applies to...",
                        "assessment_criteria": "Evidence should include...",
                        "estimated_hours": 10.0,
                        "outcome_group": "Safety"
                    },
                    {
                        "outcome_code": "WM01.2",
                        "outcome_number": 2,
                        "title": "Apply safety procedures in the workplace",
                        "description": "",
                        "range_statement": "",
                        "assessment_criteria": "",
                        "estimated_hours": 15.0,
                        "outcome_group": "Safety"
                    }
                ],
                "WM02": [
                    # More outcomes...
                ]
            }
        }
        return json.dumps(sample, indent=2)
