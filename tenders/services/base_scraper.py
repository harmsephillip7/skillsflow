"""
Base scraper interface and utilities for tender scraping.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


@dataclass
class ScrapedTender:
    """
    Data class representing a tender scraped from a source.
    """
    reference_number: str
    title: str
    source_url: str
    
    # Optional fields
    description: str = ""
    funder: str = ""
    funder_type: str = ""
    region: str = ""
    
    # Dates (as strings initially, will be parsed)
    published_date: Optional[date] = None
    opening_date: Optional[date] = None
    closing_date: Optional[date] = None
    
    # Value
    estimated_value: Optional[Decimal] = None
    currency: str = "ZAR"
    
    # Requirements
    requirements_summary: str = ""
    eligibility_notes: str = ""
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for model creation."""
        return {
            'reference_number': self.reference_number,
            'title': self.title,
            'source_url': self.source_url,
            'description': self.description,
            'funder': self.funder,
            'funder_type': self.funder_type,
            'region': self.region,
            'published_date': self.published_date,
            'opening_date': self.opening_date,
            'closing_date': self.closing_date,
            'estimated_value': self.estimated_value,
            'currency': self.currency,
            'requirements_summary': self.requirements_summary,
            'eligibility_notes': self.eligibility_notes,
            'tags': self.tags,
        }


class BaseScraper(ABC):
    """
    Abstract base class for all tender scrapers.
    Implement this for each tender source type.
    """
    
    def __init__(self, source):
        """
        Initialize scraper with a TenderSource instance.
        
        Args:
            source: TenderSource model instance with configuration
        """
        self.source = source
        self.config = source.scrape_config or {}
        self.base_url = source.base_url
        self.errors = []
        self.warnings = []
    
    @abstractmethod
    def scrape(self) -> List[ScrapedTender]:
        """
        Execute the scraping operation.
        
        Returns:
            List of ScrapedTender objects
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the source is accessible.
        
        Returns:
            True if source is accessible, False otherwise
        """
        pass
    
    def get_selector(self, key: str, default: str = "") -> str:
        """Get a CSS selector from config."""
        selectors = self.config.get('selectors', {})
        return selectors.get(key, default)
    
    def build_url(self, path: str) -> str:
        """Build full URL from relative path."""
        return urljoin(self.base_url, path)
    
    def parse_date(self, date_str: str, formats: List[str] = None) -> Optional[date]:
        """
        Parse date string using multiple format attempts.
        
        Args:
            date_str: Date string to parse
            formats: List of date format strings to try
            
        Returns:
            Parsed date or None
        """
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # Default South African date formats
        if formats is None:
            formats = [
                '%Y-%m-%d',
                '%d/%m/%Y',
                '%d-%m-%Y',
                '%d %B %Y',
                '%d %b %Y',
                '%Y/%m/%d',
                '%B %d, %Y',
            ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        self.warnings.append(f"Could not parse date: {date_str}")
        return None
    
    def parse_currency(self, value_str: str) -> Optional[Decimal]:
        """
        Parse currency string to Decimal.
        
        Args:
            value_str: Currency string like "R 1,234,567.89"
            
        Returns:
            Decimal value or None
        """
        if not value_str:
            return None
        
        try:
            # Remove currency symbols and spaces
            cleaned = value_str.strip()
            for char in ['R', '$', '€', '£', 'ZAR', ',', ' ']:
                cleaned = cleaned.replace(char, '')
            
            return Decimal(cleaned)
        except (ValueError, decimal.InvalidOperation):
            self.warnings.append(f"Could not parse value: {value_str}")
            return None
    
    def log_error(self, message: str):
        """Log and store an error."""
        logger.error(f"[{self.source.name}] {message}")
        self.errors.append(message)
    
    def log_warning(self, message: str):
        """Log and store a warning."""
        logger.warning(f"[{self.source.name}] {message}")
        self.warnings.append(message)
    
    def get_status_message(self) -> str:
        """Get status message from scrape attempt."""
        if self.errors:
            return f"Errors: {'; '.join(self.errors[:3])}"
        elif self.warnings:
            return f"Completed with warnings: {len(self.warnings)}"
        return "Completed successfully"


import decimal
