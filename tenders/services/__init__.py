"""
Tender services package.
"""

from .base_scraper import BaseScraper, ScrapedTender
from .beautifulsoup_scraper import BeautifulSoupScraper
from .playwright_scraper import PlaywrightScraper, get_scraper
from .tender_service import TenderService

__all__ = [
    'BaseScraper',
    'ScrapedTender',
    'BeautifulSoupScraper',
    'PlaywrightScraper',
    'get_scraper',
    'TenderService',
]
