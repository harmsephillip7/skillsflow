"""
Tender service for orchestrating scraping and tender management.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from django.db import transaction
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone

from ..models import (
    TenderSource, Tender, TenderApplication, TenderSegment,
    TenderNote
)
from .playwright_scraper import get_scraper
from .base_scraper import ScrapedTender

logger = logging.getLogger(__name__)


class TenderService:
    """
    Service class for managing tenders and scraping operations.
    """
    
    @staticmethod
    def run_scrape(source: TenderSource, campus=None) -> Tuple[int, int, str]:
        """
        Run a scrape operation for a tender source.
        
        Args:
            source: TenderSource to scrape
            campus: Optional campus for tenant-aware tenders
            
        Returns:
            Tuple of (new_tenders_count, updated_tenders_count, status_message)
        """
        logger.info(f"Starting scrape for source: {source.name}")
        
        scraper = get_scraper(source)
        
        # Test connection first
        if not scraper.test_connection():
            source.mark_scraped(0, success=False, message=scraper.get_status_message())
            return 0, 0, scraper.get_status_message()
        
        # Run scrape
        scraped_tenders = scraper.scrape()
        
        if scraper.errors:
            source.mark_scraped(0, success=False, message=scraper.get_status_message())
            return 0, 0, scraper.get_status_message()
        
        # Process scraped tenders
        new_count, updated_count = TenderService._process_scraped_tenders(
            source, scraped_tenders, campus
        )
        
        # Mark source as scraped
        source.mark_scraped(
            tenders_found=len(scraped_tenders),
            success=True,
            message=f"Found {len(scraped_tenders)}, {new_count} new, {updated_count} updated"
        )
        
        logger.info(f"Completed scrape for {source.name}: {new_count} new, {updated_count} updated")
        
        return new_count, updated_count, scraper.get_status_message()
    
    @staticmethod
    def _process_scraped_tenders(
        source: TenderSource,
        scraped: List[ScrapedTender],
        campus=None
    ) -> Tuple[int, int]:
        """
        Process scraped tenders into the database.
        
        Args:
            source: TenderSource these came from
            scraped: List of ScrapedTender objects
            campus: Optional campus for tenant-aware tenders
            
        Returns:
            Tuple of (new_count, updated_count)
        """
        new_count = 0
        updated_count = 0
        
        for tender_data in scraped:
            try:
                with transaction.atomic():
                    # Check if tender already exists
                    existing = Tender.objects.filter(
                        reference_number=tender_data.reference_number,
                        source=source
                    ).first()
                    
                    if existing:
                        # Update existing tender
                        updated = TenderService._update_tender(existing, tender_data)
                        if updated:
                            updated_count += 1
                    else:
                        # Create new tender
                        TenderService._create_tender(source, tender_data, campus)
                        new_count += 1
                        
            except Exception as e:
                logger.error(f"Failed to process tender {tender_data.reference_number}: {str(e)}")
        
        return new_count, updated_count
    
    @staticmethod
    def _create_tender(source: TenderSource, data: ScrapedTender, campus=None) -> Tender:
        """Create a new tender from scraped data."""
        tender = Tender(
            source=source,
            segment=source.default_segment,
            campus=campus,
            **data.to_dict()
        )
        tender.save()
        
        # Create discovery note
        TenderNote.objects.create(
            tender=tender,
            note_type='SYSTEM',
            content=f"Tender discovered from {source.name}",
            new_status='DISCOVERED'
        )
        
        return tender
    
    @staticmethod
    def _update_tender(tender: Tender, data: ScrapedTender) -> bool:
        """
        Update an existing tender with new scraped data.
        Returns True if any fields were updated.
        """
        updated = False
        update_fields = []
        
        # Update fields that might have changed
        field_mappings = [
            ('title', 'title'),
            ('description', 'description'),
            ('closing_date', 'closing_date'),
            ('published_date', 'published_date'),
            ('opening_date', 'opening_date'),
            ('estimated_value', 'estimated_value'),
            ('funder', 'funder'),
            ('region', 'region'),
        ]
        
        for model_field, data_field in field_mappings:
            new_value = getattr(data, data_field)
            if new_value and getattr(tender, model_field) != new_value:
                setattr(tender, model_field, new_value)
                update_fields.append(model_field)
                updated = True
        
        if updated:
            tender.save(update_fields=update_fields)
        
        return updated
    
    @staticmethod
    def update_all_probabilities():
        """
        Update probability and expected revenue for all pending applications.
        Should be run daily via Celery task.
        """
        pending_statuses = [
            'SUBMITTED', 'ACKNOWLEDGED', 'UNDER_EVALUATION', 'SHORTLISTED'
        ]
        
        applications = TenderApplication.objects.filter(
            status__in=pending_statuses
        ).select_related('tender__segment')
        
        updated = 0
        for app in applications:
            app.update_probability()
            updated += 1
        
        logger.info(f"Updated probability for {updated} tender applications")
        return updated
    
    @staticmethod
    def get_pipeline_summary(segment=None, funder=None, region=None, date_range=None):
        """
        Get summary statistics for the tender pipeline.
        
        Args:
            segment: Filter by segment
            funder: Filter by funder
            region: Filter by region
            date_range: Tuple of (start_date, end_date)
            
        Returns:
            Dictionary of pipeline statistics
        """
        filters = Q()
        
        if segment:
            filters &= Q(segment=segment)
        if funder:
            filters &= Q(funder__icontains=funder)
        if region:
            filters &= Q(region__icontains=region)
        if date_range:
            start, end = date_range
            filters &= Q(closing_date__range=(start, end))
        
        # Tender status breakdown
        status_counts = (
            Tender.objects.filter(filters)
            .values('status')
            .annotate(count=Count('id'), total_value=Sum('estimated_value'))
        )
        
        # Application pipeline
        app_stats = TenderApplication.objects.filter(
            tender__in=Tender.objects.filter(filters)
        ).aggregate(
            total_applications=Count('id'),
            total_applied=Sum('total_amount'),
            expected_revenue=Sum('expected_revenue'),
            approved_count=Count('id', filter=Q(status='APPROVED')),
            approved_value=Sum('approved_amount', filter=Q(status='APPROVED')),
            pending_count=Count('id', filter=Q(status__in=[
                'SUBMITTED', 'ACKNOWLEDGED', 'UNDER_EVALUATION', 'SHORTLISTED'
            ])),
        )
        
        # Closing soon
        today = date.today()
        closing_soon = Tender.objects.filter(
            filters,
            status__in=['DISCOVERED', 'REVIEWING', 'APPLICABLE'],
            closing_date__gte=today,
            closing_date__lte=today + timezone.timedelta(days=7)
        ).count()
        
        return {
            'status_breakdown': list(status_counts),
            'applications': app_stats,
            'closing_soon': closing_soon,
        }
    
    @staticmethod
    def get_revenue_forecast(
        months_ahead: int = 6,
        segment=None,
        min_probability: float = 0.0
    ):
        """
        Generate revenue forecast based on pending applications.
        
        Args:
            months_ahead: Number of months to forecast
            segment: Filter by segment
            min_probability: Minimum probability threshold
            
        Returns:
            List of monthly forecast data
        """
        from django.db.models.functions import TruncMonth
        
        filters = Q(
            status__in=['SUBMITTED', 'ACKNOWLEDGED', 'UNDER_EVALUATION', 'SHORTLISTED'],
            current_probability__gte=Decimal(str(min_probability))
        )
        
        if segment:
            filters &= Q(tender__segment=segment)
        
        # Get applications with expected award dates
        applications = TenderApplication.objects.filter(filters).select_related('tender')
        
        # Group by expected month
        forecast = {}
        today = date.today()
        
        for app in applications:
            # Estimate award date if not set
            award_date = app.tender.expected_award_date
            if not award_date and app.tender.closing_date:
                # Assume 90 days after closing if not specified
                segment_days = (
                    app.tender.segment.expected_response_days
                    if app.tender.segment
                    else 90
                )
                award_date = app.tender.closing_date + timezone.timedelta(days=segment_days)
            
            if not award_date:
                award_date = today + timezone.timedelta(days=90)
            
            # Get month key
            month_key = award_date.strftime('%Y-%m')
            
            if month_key not in forecast:
                forecast[month_key] = {
                    'month': month_key,
                    'expected_revenue': Decimal('0.00'),
                    'application_count': 0,
                    'avg_probability': Decimal('0.00'),
                }
            
            forecast[month_key]['expected_revenue'] += app.expected_revenue
            forecast[month_key]['application_count'] += 1
            forecast[month_key]['avg_probability'] += app.effective_probability
        
        # Calculate averages
        for month_key in forecast:
            count = forecast[month_key]['application_count']
            if count > 0:
                forecast[month_key]['avg_probability'] /= count
        
        # Sort and limit
        sorted_forecast = sorted(forecast.values(), key=lambda x: x['month'])
        return sorted_forecast[:months_ahead]
    
    @staticmethod
    def get_segment_performance():
        """
        Get performance metrics for each segment.
        
        Returns:
            List of segment performance data
        """
        segments = TenderSegment.objects.annotate(
            tender_count=Count('tenders'),
            application_count=Count('tenders__applications'),
            pending_value=Sum(
                'tenders__applications__total_amount',
                filter=Q(tenders__applications__status__in=[
                    'SUBMITTED', 'ACKNOWLEDGED', 'UNDER_EVALUATION', 'SHORTLISTED'
                ])
            ),
            expected_value=Sum(
                'tenders__applications__expected_revenue',
                filter=Q(tenders__applications__status__in=[
                    'SUBMITTED', 'ACKNOWLEDGED', 'UNDER_EVALUATION', 'SHORTLISTED'
                ])
            ),
        )
        
        return [
            {
                'id': s.id,
                'name': s.name,
                'segment_type': s.segment_type,
                'tender_count': s.tender_count,
                'application_count': s.application_count,
                'historical_success_rate': s.historical_success_rate,
                'pending_value': s.pending_value or Decimal('0.00'),
                'expected_value': s.expected_value or Decimal('0.00'),
                'total_won': s.total_value_won,
            }
            for s in segments
        ]
