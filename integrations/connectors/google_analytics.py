"""
Google Analytics 4 Connector

Connector for Google Analytics Data API to fetch:
- Website traffic metrics
- User behavior data
- Traffic sources
- Goal completions

Uses GA4 Data API v1 (not Universal Analytics).
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone

from .base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class GoogleAnalyticsConnector(BaseConnector):
    """
    Google Analytics 4 Data API connector.
    
    Uses Google Analytics Data API v1 for fetching reporting data.
    
    Required Scopes:
    - https://www.googleapis.com/auth/analytics.readonly
    """
    
    API_BASE = 'https://analyticsdata.googleapis.com/v1beta'
    
    def __init__(self, connection: 'IntegrationConnection', brand_account: 'BrandSocialAccount' = None):
        self.brand_account = brand_account
        self.property_id = brand_account.ga4_property_id if brand_account else None
        super().__init__(connection)
    
    def _setup_session(self):
        """Set up session with Google access token."""
        access_token = self.connection.access_token
        if not access_token:
            access_token = self.connection.api_key
        
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        })
    
    @property
    def provider_name(self) -> str:
        return 'google_analytics'
    
    @property
    def property_path(self) -> str:
        """Full property path for API requests."""
        return f'properties/{self.property_id}'
    
    def check_health(self) -> Dict[str, Any]:
        """Check Google Analytics API connectivity."""
        if not self.property_id:
            return {
                'healthy': False,
                'message': 'No GA4 Property ID configured',
                'details': {}
            }
        
        try:
            # Try to get property metadata
            response = self._make_request(
                'GET',
                f'https://analyticsadmin.googleapis.com/v1alpha/{self.property_path}'
            )
            if response.status_code == 200:
                return {
                    'healthy': True,
                    'message': 'Connected to Google Analytics',
                    'details': response.json()
                }
            return {
                'healthy': False,
                'message': f'API returned {response.status_code}',
                'details': response.json()
            }
        except Exception as e:
            return {
                'healthy': False,
                'message': str(e),
                'details': {}
            }
    
    def refresh_token(self) -> bool:
        """
        Refresh Google access token using refresh token.
        """
        try:
            client_id = self.connection.client_id
            client_secret = self.connection.client_secret
            refresh_token = self.connection.refresh_token
            
            if not refresh_token:
                logger.error("No refresh token available for Google")
                return False
            
            response = self._make_request(
                'POST',
                'https://oauth2.googleapis.com/token',
                data={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'refresh_token': refresh_token,
                    'grant_type': 'refresh_token',
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.connection.access_token = data['access_token']
                expires_in = data.get('expires_in', 3600)
                self.connection.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
                self.connection.save()
                
                self.session.headers['Authorization'] = f"Bearer {data['access_token']}"
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to refresh Google token: {e}")
            return False
    
    # ========================================================================
    # REPORT METHODS
    # ========================================================================
    
    def run_report(
        self,
        date_from: str,
        date_to: str,
        metrics: List[str],
        dimensions: List[str] = None
    ) -> Dict[str, Any]:
        """
        Run a GA4 Data API report.
        
        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            metrics: List of metric names (e.g., ['sessions', 'activeUsers'])
            dimensions: Optional list of dimensions (e.g., ['date', 'country'])
            
        Returns:
            Dict with rows of data
        """
        if not self.property_id:
            return {'error': 'No GA4 Property ID configured'}
        
        request_body = {
            'dateRanges': [{'startDate': date_from, 'endDate': date_to}],
            'metrics': [{'name': m} for m in metrics],
        }
        
        if dimensions:
            request_body['dimensions'] = [{'name': d} for d in dimensions]
        
        try:
            response = self._make_request(
                'POST',
                f'{self.API_BASE}/{self.property_path}:runReport',
                json=request_body
            )
            
            if response.status_code == 200:
                return self._parse_report_response(response.json(), metrics, dimensions)
            else:
                logger.error(f"GA4 report failed: {response.text}")
                return {'error': response.json()}
                
        except Exception as e:
            logger.error(f"Error running GA4 report: {e}")
            return {'error': str(e)}
    
    def get_daily_metrics(self, date: str) -> Dict[str, Any]:
        """
        Get core metrics for a single day.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Dict with session, user, and engagement metrics
        """
        metrics = [
            'sessions',
            'activeUsers',
            'newUsers',
            'screenPageViews',
            'screenPageViewsPerSession',
            'averageSessionDuration',
            'bounceRate',
            'engagementRate',
            'eventCount',
            'conversions',
        ]
        
        result = self.run_report(date, date, metrics)
        
        if 'error' not in result:
            # Flatten the result for daily snapshot
            row = result.get('rows', [{}])[0] if result.get('rows') else {}
            return {
                'sessions': int(row.get('sessions', 0)),
                'users': int(row.get('activeUsers', 0)),
                'new_users': int(row.get('newUsers', 0)),
                'pageviews': int(row.get('screenPageViews', 0)),
                'pages_per_session': float(row.get('screenPageViewsPerSession', 0)),
                'avg_session_duration': int(float(row.get('averageSessionDuration', 0))),
                'bounce_rate': round(float(row.get('bounceRate', 0)) * 100, 2),
                'engagement_rate': round(float(row.get('engagementRate', 0)) * 100, 2),
                'goal_completions': int(row.get('conversions', 0)),
            }
        
        return result
    
    def get_traffic_by_source(self, date: str) -> Dict[str, int]:
        """
        Get sessions breakdown by traffic source.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Dict mapping source names to session counts
        """
        result = self.run_report(
            date, date,
            metrics=['sessions'],
            dimensions=['sessionSource']
        )
        
        sources = {}
        for row in result.get('rows', []):
            source = row.get('sessionSource', 'unknown')
            sessions = int(row.get('sessions', 0))
            sources[source] = sessions
        
        return sources
    
    def get_traffic_by_medium(self, date: str) -> Dict[str, int]:
        """
        Get sessions breakdown by traffic medium.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Dict mapping medium names to session counts
        """
        result = self.run_report(
            date, date,
            metrics=['sessions'],
            dimensions=['sessionMedium']
        )
        
        mediums = {}
        for row in result.get('rows', []):
            medium = row.get('sessionMedium', 'unknown')
            sessions = int(row.get('sessions', 0))
            mediums[medium] = sessions
        
        return mediums
    
    def get_traffic_from_social(self, date: str) -> Dict[str, int]:
        """
        Get sessions from social media platforms.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Dict mapping social network names to session counts
        """
        # Filter to social traffic using sessionDefaultChannelGroup
        request_body = {
            'dateRanges': [{'startDate': date, 'endDate': date}],
            'metrics': [{'name': 'sessions'}],
            'dimensions': [{'name': 'sessionSource'}],
            'dimensionFilter': {
                'filter': {
                    'fieldName': 'sessionDefaultChannelGroup',
                    'stringFilter': {
                        'matchType': 'EXACT',
                        'value': 'Organic Social'
                    }
                }
            }
        }
        
        try:
            response = self._make_request(
                'POST',
                f'{self.API_BASE}/{self.property_path}:runReport',
                json=request_body
            )
            
            if response.status_code == 200:
                data = response.json()
                social = {}
                for row in data.get('rows', []):
                    dims = row.get('dimensionValues', [])
                    metrics = row.get('metricValues', [])
                    if dims and metrics:
                        source = dims[0].get('value', 'unknown')
                        sessions = int(metrics[0].get('value', 0))
                        social[source] = sessions
                return social
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting social traffic: {e}")
            return {}
    
    def get_traffic_by_country(self, date: str, limit: int = 10) -> Dict[str, int]:
        """Get sessions breakdown by country."""
        result = self.run_report(
            date, date,
            metrics=['sessions'],
            dimensions=['country']
        )
        
        countries = {}
        for row in result.get('rows', [])[:limit]:
            country = row.get('country', 'unknown')
            sessions = int(row.get('sessions', 0))
            countries[country] = sessions
        
        return countries
    
    def get_traffic_by_city(self, date: str, limit: int = 10) -> Dict[str, int]:
        """Get sessions breakdown by city."""
        result = self.run_report(
            date, date,
            metrics=['sessions'],
            dimensions=['city']
        )
        
        cities = {}
        for row in result.get('rows', [])[:limit]:
            city = row.get('city', 'unknown')
            sessions = int(row.get('sessions', 0))
            cities[city] = sessions
        
        return cities
    
    def get_traffic_by_device(self, date: str) -> Dict[str, int]:
        """Get sessions breakdown by device category."""
        result = self.run_report(
            date, date,
            metrics=['sessions'],
            dimensions=['deviceCategory']
        )
        
        devices = {}
        for row in result.get('rows', []):
            device = row.get('deviceCategory', 'unknown')
            sessions = int(row.get('sessions', 0))
            devices[device] = sessions
        
        return devices
    
    def get_top_pages(self, date: str, limit: int = 20) -> List[Dict]:
        """
        Get top pages by pageviews.
        
        Args:
            date: Date in YYYY-MM-DD format
            limit: Maximum number of pages to return
            
        Returns:
            List of dicts with path and pageview count
        """
        result = self.run_report(
            date, date,
            metrics=['screenPageViews', 'activeUsers', 'engagementRate'],
            dimensions=['pagePath']
        )
        
        pages = []
        for row in result.get('rows', [])[:limit]:
            pages.append({
                'path': row.get('pagePath', '/'),
                'views': int(row.get('screenPageViews', 0)),
                'users': int(row.get('activeUsers', 0)),
                'engagement_rate': round(float(row.get('engagementRate', 0)) * 100, 2),
            })
        
        return pages
    
    def get_full_daily_snapshot(self, date: str) -> Dict[str, Any]:
        """
        Get complete daily snapshot with all metrics for WebTrafficSnapshot.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Complete dict ready for WebTrafficSnapshot model
        """
        # Get core metrics
        metrics = self.get_daily_metrics(date)
        
        if 'error' in metrics:
            return metrics
        
        # Get breakdowns
        traffic_by_source = self.get_traffic_by_source(date)
        traffic_by_medium = self.get_traffic_by_medium(date)
        traffic_by_social = self.get_traffic_from_social(date)
        traffic_by_country = self.get_traffic_by_country(date)
        traffic_by_city = self.get_traffic_by_city(date)
        traffic_by_device = self.get_traffic_by_device(date)
        top_pages = self.get_top_pages(date)
        
        return {
            **metrics,
            'returning_users': max(0, metrics.get('users', 0) - metrics.get('new_users', 0)),
            'traffic_by_source': traffic_by_source,
            'traffic_by_medium': traffic_by_medium,
            'traffic_by_social': traffic_by_social,
            'traffic_by_country': traffic_by_country,
            'traffic_by_city': traffic_by_city,
            'traffic_by_device': traffic_by_device,
            'top_pages': top_pages,
        }
    
    # ========================================================================
    # DATE RANGE REPORTS
    # ========================================================================
    
    def get_metrics_for_range(self, date_from: str, date_to: str) -> List[Dict]:
        """
        Get daily metrics for a date range.
        
        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            
        Returns:
            List of daily metric dicts
        """
        metrics = [
            'sessions',
            'activeUsers',
            'newUsers',
            'screenPageViews',
            'averageSessionDuration',
            'bounceRate',
            'engagementRate',
            'conversions',
        ]
        
        result = self.run_report(
            date_from, date_to,
            metrics=metrics,
            dimensions=['date']
        )
        
        daily_data = []
        for row in result.get('rows', []):
            daily_data.append({
                'date': row.get('date', ''),
                'sessions': int(row.get('sessions', 0)),
                'users': int(row.get('activeUsers', 0)),
                'new_users': int(row.get('newUsers', 0)),
                'pageviews': int(row.get('screenPageViews', 0)),
                'avg_session_duration': int(float(row.get('averageSessionDuration', 0))),
                'bounce_rate': round(float(row.get('bounceRate', 0)) * 100, 2),
                'engagement_rate': round(float(row.get('engagementRate', 0)) * 100, 2),
                'goal_completions': int(row.get('conversions', 0)),
            })
        
        return daily_data
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _parse_report_response(
        self,
        data: Dict,
        metrics: List[str],
        dimensions: List[str] = None
    ) -> Dict[str, Any]:
        """
        Parse GA4 report response into friendly format.
        
        Args:
            data: Raw API response
            metrics: List of requested metric names
            dimensions: List of requested dimension names
            
        Returns:
            Dict with parsed rows
        """
        rows = []
        dimensions = dimensions or []
        
        for row in data.get('rows', []):
            parsed_row = {}
            
            # Parse dimensions
            dim_values = row.get('dimensionValues', [])
            for i, dim in enumerate(dimensions):
                if i < len(dim_values):
                    parsed_row[dim] = dim_values[i].get('value', '')
            
            # Parse metrics
            metric_values = row.get('metricValues', [])
            for i, metric in enumerate(metrics):
                if i < len(metric_values):
                    parsed_row[metric] = metric_values[i].get('value', '0')
            
            rows.append(parsed_row)
        
        return {
            'rows': rows,
            'row_count': data.get('rowCount', len(rows)),
            'metadata': data.get('metadata', {}),
        }
