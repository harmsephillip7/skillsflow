"""
QCTO Sync Service
Scrapes QCTO website for qualification data updates
Runs monthly on 15th via cron + max 2 manual triggers per month
"""
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class QCTOSyncService:
    """
    Service to sync qualification data from QCTO website
    """
    
    BASE_URL = "https://www.qcto.org.za"
    QUALIFICATION_SEARCH_URL = f"{BASE_URL}/occupational-qualifications"
    
    # Fields we track for changes
    TRACKED_FIELDS = [
        'title',
        'nqf_level',
        'credits',
        'registration_start',
        'registration_end',
        'last_enrollment_date',
        'qcto_code',
    ]
    
    def __init__(self, sync_log):
        self.sync_log = sync_log
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SkillsFlow ERP QCTO Sync/1.0 (Educational Purpose)'
        })
    
    def run_sync(self):
        """Run the full sync process"""
        from academics.models import Qualification, QCTOQualificationChange
        
        self.sync_log.status = 'RUNNING'
        self.sync_log.started_at = timezone.now()
        self.sync_log.save()
        
        try:
            # Get all active qualifications with SAQA IDs
            qualifications = Qualification.objects.filter(is_active=True)
            self.sync_log.qualifications_checked = qualifications.count()
            
            changes_detected = []
            updated_count = 0
            
            for qual in qualifications:
                try:
                    # Fetch QCTO data for this qualification
                    qcto_data = self.fetch_qualification_data(qual.saqa_id)
                    
                    if qcto_data:
                        # Compare and detect changes
                        qual_changes = self.compare_qualification(qual, qcto_data)
                        
                        if qual_changes:
                            updated_count += 1
                            for change in qual_changes:
                                # Create change record
                                QCTOQualificationChange.objects.create(
                                    sync_log=self.sync_log,
                                    qualification=qual,
                                    field_name=change['field'],
                                    old_value=str(change['old_value']),
                                    new_value=str(change['new_value']),
                                    change_description=change.get('description', ''),
                                )
                                changes_detected.append({
                                    'saqa_id': qual.saqa_id,
                                    'field': change['field'],
                                    'old_value': str(change['old_value']),
                                    'new_value': str(change['new_value']),
                                })
                
                except Exception as e:
                    logger.warning(f"Failed to sync qualification {qual.saqa_id}: {str(e)}")
                    continue
            
            # Update sync log
            self.sync_log.qualifications_updated = updated_count
            self.sync_log.changes_detected = changes_detected
            self.sync_log.status = 'COMPLETED'
            self.sync_log.completed_at = timezone.now()
            self.sync_log.save()
            
            logger.info(f"QCTO sync completed: {self.sync_log.qualifications_checked} checked, {updated_count} with changes")
            
        except Exception as e:
            self.sync_log.status = 'FAILED'
            self.sync_log.error_message = str(e)
            self.sync_log.completed_at = timezone.now()
            self.sync_log.save()
            logger.error(f"QCTO sync failed: {str(e)}")
            raise
    
    def fetch_qualification_data(self, saqa_id):
        """
        Fetch qualification data from QCTO website
        Returns dict with qualification details or None if not found
        """
        try:
            # Try to fetch from QCTO qualification database
            # Note: QCTO's actual URL structure may vary - this is a template
            search_url = f"{self.BASE_URL}/qualification/{saqa_id}"
            
            response = self.session.get(search_url, timeout=30)
            
            if response.status_code == 404:
                # Try alternative search
                return self._search_qualification(saqa_id)
            
            if response.status_code != 200:
                logger.warning(f"QCTO returned status {response.status_code} for SAQA {saqa_id}")
                return None
            
            return self._parse_qualification_page(response.text, saqa_id)
            
        except requests.RequestException as e:
            logger.error(f"Request failed for SAQA {saqa_id}: {str(e)}")
            return None
    
    def _search_qualification(self, saqa_id):
        """Search for qualification by SAQA ID"""
        try:
            # Search endpoint (structure may vary)
            search_url = f"{self.QUALIFICATION_SEARCH_URL}?saqa_id={saqa_id}"
            response = self.session.get(search_url, timeout=30)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for qualification link in search results
            # This is a template - actual selectors depend on QCTO's HTML structure
            result_links = soup.select('.qualification-result a, .search-result a')
            
            for link in result_links:
                if saqa_id in link.get('href', ''):
                    detail_url = link['href']
                    if not detail_url.startswith('http'):
                        detail_url = f"{self.BASE_URL}{detail_url}"
                    
                    detail_response = self.session.get(detail_url, timeout=30)
                    if detail_response.status_code == 200:
                        return self._parse_qualification_page(detail_response.text, saqa_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Search failed for SAQA {saqa_id}: {str(e)}")
            return None
    
    def _parse_qualification_page(self, html_content, saqa_id):
        """
        Parse qualification details from QCTO HTML page
        Returns dict with parsed data
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        data = {
            'saqa_id': saqa_id,
            'title': None,
            'nqf_level': None,
            'credits': None,
            'registration_start': None,
            'registration_end': None,
            'last_enrollment_date': None,
            'qcto_code': None,
            'status': None,
        }
        
        try:
            # Extract title - look for common patterns
            title_elem = soup.select_one('h1.qualification-title, .qual-title, h1')
            if title_elem:
                data['title'] = title_elem.get_text(strip=True)
            
            # Extract details from definition lists or tables
            # Common pattern: <dt>Label</dt><dd>Value</dd>
            for dt in soup.find_all('dt'):
                label = dt.get_text(strip=True).lower()
                dd = dt.find_next_sibling('dd')
                if dd:
                    value = dd.get_text(strip=True)
                    
                    if 'nqf level' in label:
                        try:
                            data['nqf_level'] = int(re.search(r'\d+', value).group())
                        except:
                            pass
                    elif 'credits' in label:
                        try:
                            data['credits'] = int(re.search(r'\d+', value).group())
                        except:
                            pass
                    elif 'registration start' in label or 'start date' in label:
                        data['registration_start'] = self._parse_date(value)
                    elif 'registration end' in label or 'end date' in label:
                        data['registration_end'] = self._parse_date(value)
                    elif 'last enrolment' in label or 'last enrollment' in label:
                        data['last_enrollment_date'] = self._parse_date(value)
                    elif 'qcto code' in label or 'qualification code' in label:
                        data['qcto_code'] = value
                    elif 'status' in label:
                        data['status'] = value
            
            # Also check table rows
            for tr in soup.find_all('tr'):
                cells = tr.find_all(['th', 'td'])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    
                    # Same extraction logic as above
                    if 'nqf level' in label and not data['nqf_level']:
                        try:
                            data['nqf_level'] = int(re.search(r'\d+', value).group())
                        except:
                            pass
                    elif 'credits' in label and not data['credits']:
                        try:
                            data['credits'] = int(re.search(r'\d+', value).group())
                        except:
                            pass
            
        except Exception as e:
            logger.error(f"Error parsing qualification page for SAQA {saqa_id}: {str(e)}")
        
        # Only return data if we got at least the title
        if data['title']:
            return data
        return None
    
    def _parse_date(self, date_string):
        """Parse date string to date object"""
        if not date_string:
            return None
        
        # Common date formats
        formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%Y/%m/%d',
            '%d %B %Y',
            '%d %b %Y',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string.strip(), fmt).date()
            except ValueError:
                continue
        
        return None
    
    def compare_qualification(self, qualification, qcto_data):
        """
        Compare local qualification with QCTO data
        Returns list of detected changes
        """
        changes = []
        
        for field in self.TRACKED_FIELDS:
            local_value = getattr(qualification, field, None)
            qcto_value = qcto_data.get(field)
            
            # Skip if QCTO didn't return this field
            if qcto_value is None:
                continue
            
            # Compare values
            if str(local_value) != str(qcto_value):
                changes.append({
                    'field': field,
                    'old_value': local_value,
                    'new_value': qcto_value,
                    'description': f'{field.replace("_", " ").title()} changed from "{local_value}" to "{qcto_value}"'
                })
        
        return changes


def run_scheduled_sync():
    """
    Function to be called by cron/celery for scheduled sync on 15th
    """
    from academics.models import QCTOSyncLog
    
    logger.info("Starting scheduled QCTO sync")
    
    sync_log = QCTOSyncLog.objects.create(
        trigger_type='SCHEDULED',
        status='PENDING'
    )
    
    try:
        service = QCTOSyncService(sync_log)
        service.run_sync()
        logger.info(f"Scheduled sync completed: {sync_log.qualifications_updated} changes detected")
    except Exception as e:
        logger.error(f"Scheduled sync failed: {str(e)}")
        raise
