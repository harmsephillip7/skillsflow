"""
Playwright-based scraper for JavaScript-heavy websites.
Handles dynamic content, SPAs, and sites requiring browser rendering.
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any

from .base_scraper import BaseScraper, ScrapedTender

logger = logging.getLogger(__name__)

# Playwright is optional - only import if available
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Install with: pip install playwright && playwright install chromium")


class PlaywrightScraper(BaseScraper):
    """
    Scraper using Playwright for JavaScript-heavy sites.
    
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
            - load_more: Selector for "load more" button (if infinite scroll)
        - wait_for: Selector to wait for before scraping
        - pagination:
            - type: 'page' | 'load_more' | 'scroll' | 'none'
            - max_pages: Maximum pages/clicks
        - browser:
            - headless: Boolean (default True)
            - viewport: {width, height}
            - timeout: Page timeout in ms
        - auth: Authentication config (if needed)
            - type: 'form' | 'cookie'
            - login_url: URL of login page
            - username_selector: CSS selector for username field
            - password_selector: CSS selector for password field
            - submit_selector: CSS selector for submit button
            - username: Username value
            - password: Password value
    """
    
    DEFAULT_TIMEOUT = 30000  # 30 seconds
    
    def __init__(self, source):
        super().__init__(source)
        self.browser = None
        self.context = None
    
    def test_connection(self) -> bool:
        """Test if we can connect to the source."""
        if not PLAYWRIGHT_AVAILABLE:
            self.log_error("Playwright not installed")
            return False
        
        try:
            # Run async connection test
            return asyncio.get_event_loop().run_until_complete(
                self._async_test_connection()
            )
        except Exception as e:
            self.log_error(f"Connection test failed: {str(e)}")
            return False
    
    async def _async_test_connection(self) -> bool:
        """Async connection test."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                list_url = self.config.get('list_url', self.base_url)
                
                await page.goto(list_url, timeout=self.DEFAULT_TIMEOUT)
                
                # Wait for content selector if configured
                wait_for = self.config.get('wait_for')
                if wait_for:
                    await page.wait_for_selector(wait_for, timeout=10000)
                
                return True
            finally:
                await browser.close()
    
    def scrape(self) -> List[ScrapedTender]:
        """
        Scrape tenders from the source.
        
        Returns:
            List of ScrapedTender objects
        """
        if not PLAYWRIGHT_AVAILABLE:
            self.log_error("Playwright not installed")
            return []
        
        try:
            # Run async scrape
            return asyncio.get_event_loop().run_until_complete(
                self._async_scrape()
            )
        except Exception as e:
            self.log_error(f"Scrape failed: {str(e)}")
            return []
    
    async def _async_scrape(self) -> List[ScrapedTender]:
        """Async scraping implementation."""
        tenders = []
        
        async with async_playwright() as p:
            # Launch browser
            browser_config = self.config.get('browser', {})
            browser = await p.chromium.launch(
                headless=browser_config.get('headless', True)
            )
            
            try:
                # Create context with viewport
                viewport = browser_config.get('viewport', {'width': 1920, 'height': 1080})
                context = await browser.new_context(
                    viewport=viewport,
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                page.set_default_timeout(browser_config.get('timeout', self.DEFAULT_TIMEOUT))
                
                # Handle authentication if needed
                auth_config = self.config.get('auth', {})
                if auth_config:
                    await self._handle_auth(page, auth_config)
                
                # Navigate to listing page
                list_url = self.config.get('list_url', self.base_url)
                await page.goto(list_url)
                
                # Wait for content to load
                wait_for = self.config.get('wait_for')
                if wait_for:
                    await page.wait_for_selector(wait_for, timeout=15000)
                
                # Handle pagination
                pagination = self.config.get('pagination', {'type': 'none'})
                
                if pagination.get('type') == 'none':
                    tenders.extend(await self._scrape_page(page))
                
                elif pagination.get('type') == 'load_more':
                    tenders.extend(await self._scrape_with_load_more(page, pagination))
                
                elif pagination.get('type') == 'scroll':
                    tenders.extend(await self._scrape_with_infinite_scroll(page, pagination))
                
                elif pagination.get('type') == 'page':
                    tenders.extend(await self._scrape_with_pagination(page, pagination))
                
                logger.info(f"Scraped {len(tenders)} tenders from {self.source.name}")
                
            finally:
                await browser.close()
        
        return tenders
    
    async def _handle_auth(self, page: 'Page', auth_config: Dict) -> None:
        """Handle form-based authentication."""
        if auth_config.get('type') == 'form':
            login_url = auth_config.get('login_url')
            if login_url:
                await page.goto(login_url)
                
                # Fill login form
                username_sel = auth_config.get('username_selector')
                password_sel = auth_config.get('password_selector')
                submit_sel = auth_config.get('submit_selector')
                
                if username_sel and password_sel:
                    await page.fill(username_sel, auth_config.get('username', ''))
                    await page.fill(password_sel, auth_config.get('password', ''))
                    
                    if submit_sel:
                        await page.click(submit_sel)
                        await page.wait_for_load_state('networkidle')
    
    async def _scrape_page(self, page: 'Page') -> List[ScrapedTender]:
        """Scrape tenders from current page."""
        tenders = []
        
        list_selector = self.get_selector('tender_list')
        if not list_selector:
            self.log_error("No tender_list selector configured")
            return tenders
        
        # Wait for items to load
        try:
            await page.wait_for_selector(list_selector, timeout=10000)
        except Exception:
            self.log_warning("No tender items found on page")
            return tenders
        
        # Get all tender items
        items = await page.query_selector_all(list_selector)
        logger.debug(f"Found {len(items)} tender items on page")
        
        for item in items:
            try:
                tender = await self._parse_tender_item(item, page.url)
                if tender:
                    tenders.append(tender)
            except Exception as e:
                self.log_warning(f"Failed to parse tender item: {str(e)}")
        
        return tenders
    
    async def _parse_tender_item(self, item, page_url: str) -> Optional[ScrapedTender]:
        """Parse a single tender item."""
        
        # Extract reference number (required)
        reference = await self._extract_text(item, 'reference')
        if not reference:
            return None
        
        # Extract title (required)
        title = await self._extract_text(item, 'title')
        if not title:
            title = reference
        
        # Extract detail link
        source_url = page_url
        detail_selector = self.get_selector('detail_link')
        if detail_selector:
            link_elem = await item.query_selector(detail_selector)
            if link_elem:
                href = await link_elem.get_attribute('href')
                if href:
                    source_url = self.build_url(href)
        
        # Build ScrapedTender
        tender = ScrapedTender(
            reference_number=reference,
            title=title,
            source_url=source_url,
        )
        
        # Extract optional fields
        tender.description = await self._extract_text(item, 'description')
        tender.funder = await self._extract_text(item, 'funder')
        tender.funder_type = await self._extract_text(item, 'funder_type')
        tender.region = await self._extract_text(item, 'region')
        
        # Parse dates
        tender.closing_date = self.parse_date(await self._extract_text(item, 'closing_date'))
        tender.published_date = self.parse_date(await self._extract_text(item, 'published_date'))
        tender.opening_date = self.parse_date(await self._extract_text(item, 'opening_date'))
        
        # Parse value
        tender.estimated_value = self.parse_currency(await self._extract_text(item, 'value'))
        
        return tender
    
    async def _extract_text(self, item, selector_key: str) -> str:
        """Extract text from element using configured selector."""
        selector = self.get_selector(selector_key)
        if not selector:
            return ""
        
        try:
            element = await item.query_selector(selector)
            if element:
                return (await element.inner_text()).strip()
        except Exception:
            pass
        
        return ""
    
    async def _scrape_with_load_more(self, page: 'Page', pagination: Dict) -> List[ScrapedTender]:
        """Scrape by clicking a 'Load More' button."""
        tenders = []
        max_clicks = pagination.get('max_pages', 5)
        load_more_selector = self.get_selector('load_more')
        
        if not load_more_selector:
            return await self._scrape_page(page)
        
        for click_num in range(max_clicks):
            # Scrape current items
            new_tenders = await self._scrape_page(page)
            tenders.extend(new_tenders)
            
            # Try to click load more
            try:
                load_more = await page.query_selector(load_more_selector)
                if not load_more or not await load_more.is_visible():
                    break
                
                await load_more.click()
                await page.wait_for_load_state('networkidle')
                await asyncio.sleep(1)  # Brief pause for content
                
            except Exception:
                break
        
        return tenders
    
    async def _scrape_with_infinite_scroll(self, page: 'Page', pagination: Dict) -> List[ScrapedTender]:
        """Scrape by scrolling down the page."""
        tenders = []
        max_scrolls = pagination.get('max_pages', 10)
        
        for scroll_num in range(max_scrolls):
            # Get current item count
            list_selector = self.get_selector('tender_list')
            items_before = len(await page.query_selector_all(list_selector))
            
            # Scroll to bottom
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(2)  # Wait for content to load
            
            # Check if new items loaded
            items_after = len(await page.query_selector_all(list_selector))
            if items_after == items_before:
                break
        
        # Scrape all items
        tenders = await self._scrape_page(page)
        return tenders
    
    async def _scrape_with_pagination(self, page: 'Page', pagination: Dict) -> List[ScrapedTender]:
        """Scrape using page navigation."""
        tenders = []
        max_pages = pagination.get('max_pages', 5)
        next_selector = self.get_selector('next_page')
        
        for page_num in range(max_pages):
            # Scrape current page
            page_tenders = await self._scrape_page(page)
            if not page_tenders:
                break
            
            tenders.extend(page_tenders)
            
            # Try to go to next page
            if next_selector:
                try:
                    next_btn = await page.query_selector(next_selector)
                    if not next_btn or not await next_btn.is_visible():
                        break
                    
                    await next_btn.click()
                    await page.wait_for_load_state('networkidle')
                    
                    wait_for = self.config.get('wait_for')
                    if wait_for:
                        await page.wait_for_selector(wait_for, timeout=10000)
                    
                except Exception:
                    break
        
        return tenders


def get_scraper(source):
    """
    Factory function to get the appropriate scraper for a source.
    
    Args:
        source: TenderSource model instance
        
    Returns:
        BaseScraper subclass instance
    """
    from .beautifulsoup_scraper import BeautifulSoupScraper
    
    scraper_type = source.scraper_type
    
    if scraper_type == 'PLAYWRIGHT':
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(f"Playwright not available, falling back to BeautifulSoup for {source.name}")
            return BeautifulSoupScraper(source)
        return PlaywrightScraper(source)
    
    elif scraper_type in ['BEAUTIFULSOUP', 'RSS', 'API']:
        return BeautifulSoupScraper(source)
    
    else:
        logger.warning(f"Unknown scraper type {scraper_type}, using BeautifulSoup")
        return BeautifulSoupScraper(source)
