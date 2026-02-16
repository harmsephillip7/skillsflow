"""
BeautifulSoup-based scraper for simple HTML pages.
Suitable for static HTML sites without heavy JavaScript.
"""

import logging
from typing import List, Optional, Dict, Any

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, ScrapedTender

logger = logging.getLogger(__name__)


class BeautifulSoupScraper(BaseScraper):
    """
    Scraper using requests + BeautifulSoup for simple HTML pages.
    
    Config options:
        - list_url: URL for tender listing page
        - selectors: CSS selectors for extracting data
            - tender_list: Selector for each tender item
            - reference: Selector for reference number
            - title: Selector for title
            - funder: Selector for funder name
            - closing_date: Selector for closing date
            - value: Selector for tender value
            - detail_link: Selector for link to details page
        - pagination:
            - type: 'page' | 'offset' | 'none'
            - param: Query parameter name (e.g., 'page')
            - max_pages: Maximum pages to scrape
        - headers: Custom HTTP headers
        - auth: Authentication config (if needed)
    """
    
    DEFAULT_TIMEOUT = 30
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    def __init__(self, source):
        super().__init__(source)
        self.session = requests.Session()
        
        # Setup headers
        headers = {**self.DEFAULT_HEADERS}
        headers.update(self.config.get('headers', {}))
        self.session.headers.update(headers)
        
        # Setup authentication if configured
        auth_config = self.config.get('auth', {})
        if auth_config.get('type') == 'basic':
            self.session.auth = (
                auth_config.get('username', ''),
                auth_config.get('password', '')
            )
    
    def test_connection(self) -> bool:
        """Test if we can connect to the source."""
        try:
            list_url = self.config.get('list_url', self.base_url)
            response = self.session.get(
                list_url,
                timeout=self.DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            self.log_error(f"Connection test failed: {str(e)}")
            return False
    
    def scrape(self) -> List[ScrapedTender]:
        """
        Scrape tenders from the source.
        
        Returns:
            List of ScrapedTender objects
        """
        tenders = []
        
        try:
            # Get pagination config
            pagination = self.config.get('pagination', {'type': 'none'})
            max_pages = pagination.get('max_pages', 5)
            
            if pagination.get('type') == 'none':
                # Single page scrape
                page_tenders = self._scrape_page(self.config.get('list_url', self.base_url))
                tenders.extend(page_tenders)
            else:
                # Paginated scrape
                for page_num in range(1, max_pages + 1):
                    page_url = self._build_page_url(page_num, pagination)
                    logger.info(f"Scraping page {page_num}: {page_url}")
                    
                    page_tenders = self._scrape_page(page_url)
                    if not page_tenders:
                        logger.info(f"No tenders on page {page_num}, stopping pagination")
                        break
                    
                    tenders.extend(page_tenders)
            
            logger.info(f"Scraped {len(tenders)} tenders from {self.source.name}")
            
        except Exception as e:
            self.log_error(f"Scrape failed: {str(e)}")
        
        return tenders
    
    def _build_page_url(self, page_num: int, pagination: Dict) -> str:
        """Build URL for a specific page number."""
        list_url = self.config.get('list_url', self.base_url)
        param = pagination.get('param', 'page')
        
        if pagination.get('type') == 'offset':
            offset = (page_num - 1) * pagination.get('page_size', 20)
            separator = '&' if '?' in list_url else '?'
            return f"{list_url}{separator}{param}={offset}"
        else:
            separator = '&' if '?' in list_url else '?'
            return f"{list_url}{separator}{param}={page_num}"
    
    def _scrape_page(self, url: str) -> List[ScrapedTender]:
        """Scrape a single page of tender listings."""
        tenders = []
        
        try:
            response = self.session.get(url, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Get tender list items
            list_selector = self.get_selector('tender_list')
            if not list_selector:
                self.log_error("No tender_list selector configured")
                return tenders
            
            items = soup.select(list_selector)
            logger.debug(f"Found {len(items)} tender items on page")
            
            for item in items:
                try:
                    tender = self._parse_tender_item(item, url)
                    if tender:
                        tenders.append(tender)
                except Exception as e:
                    self.log_warning(f"Failed to parse tender item: {str(e)}")
            
        except requests.RequestException as e:
            self.log_error(f"Failed to fetch page {url}: {str(e)}")
        
        return tenders
    
    def _parse_tender_item(self, item, page_url: str) -> Optional[ScrapedTender]:
        """Parse a single tender item from the listing."""
        
        # Extract reference number (required)
        reference = self._extract_text(item, 'reference')
        if not reference:
            return None
        
        # Extract title (required)
        title = self._extract_text(item, 'title')
        if not title:
            title = reference  # Fallback to reference if no title
        
        # Extract detail link for source URL
        source_url = page_url
        detail_selector = self.get_selector('detail_link')
        if detail_selector:
            link_elem = item.select_one(detail_selector)
            if link_elem and link_elem.get('href'):
                source_url = self.build_url(link_elem['href'])
        
        # Build ScrapedTender
        tender = ScrapedTender(
            reference_number=reference,
            title=title,
            source_url=source_url,
        )
        
        # Extract optional fields
        tender.description = self._extract_text(item, 'description')
        tender.funder = self._extract_text(item, 'funder')
        tender.funder_type = self._extract_text(item, 'funder_type')
        tender.region = self._extract_text(item, 'region')
        
        # Parse dates
        tender.closing_date = self.parse_date(self._extract_text(item, 'closing_date'))
        tender.published_date = self.parse_date(self._extract_text(item, 'published_date'))
        tender.opening_date = self.parse_date(self._extract_text(item, 'opening_date'))
        
        # Parse value
        tender.estimated_value = self.parse_currency(self._extract_text(item, 'value'))
        
        return tender
    
    def _extract_text(self, item, selector_key: str) -> str:
        """Extract text from an element using configured selector."""
        selector = self.get_selector(selector_key)
        if not selector:
            return ""
        
        try:
            element = item.select_one(selector)
            if element:
                return element.get_text(strip=True)
        except Exception:
            pass
        
        return ""
    
    def scrape_detail_page(self, url: str) -> Dict[str, Any]:
        """
        Scrape additional details from a tender detail page.
        
        Args:
            url: URL of the detail page
            
        Returns:
            Dictionary of additional details
        """
        details = {}
        
        try:
            response = self.session.get(url, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract details using configured selectors
            detail_selectors = self.config.get('detail_selectors', {})
            for key, selector in detail_selectors.items():
                element = soup.select_one(selector)
                if element:
                    details[key] = element.get_text(strip=True)
            
            # Look for document links
            doc_selector = detail_selectors.get('documents')
            if doc_selector:
                doc_links = []
                for link in soup.select(doc_selector):
                    href = link.get('href')
                    if href:
                        doc_links.append({
                            'name': link.get_text(strip=True),
                            'url': self.build_url(href)
                        })
                details['documents'] = doc_links
            
        except requests.RequestException as e:
            self.log_warning(f"Failed to fetch detail page {url}: {str(e)}")
        
        return details
