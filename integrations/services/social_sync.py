"""
Social Media Analytics Sync Service

Orchestrates the weekly synchronization of social media metrics
from Meta (Facebook/Instagram), TikTok, and Google Analytics.

Supports:
- Scheduled weekly sync via Celery
- Historical data backfill
- Per-brand synchronization
"""
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class SocialSyncService:
    """
    Service for synchronizing social media analytics data.
    
    Handles:
    - Fetching daily metrics from all platforms
    - Storing snapshots in the database
    - Backfilling historical data
    - Error handling and retry logic
    """
    
    def __init__(self, brand: 'Brand' = None):
        """
        Initialize sync service.
        
        Args:
            brand: Optional Brand instance to sync for. If None, syncs all brands.
        """
        self.brand = brand
        self.errors = []
        self.synced_count = 0
    
    def sync_all_brands(self, date_from: date = None, date_to: date = None) -> Dict[str, Any]:
        """
        Sync analytics for all brands with active social accounts.
        
        Args:
            date_from: Start date (defaults to yesterday)
            date_to: End date (defaults to yesterday)
            
        Returns:
            Dict with sync results
        """
        from tenants.models import Brand, BrandSocialAccount
        
        if date_to is None:
            date_to = timezone.now().date() - timedelta(days=1)
        if date_from is None:
            date_from = date_to
        
        results = {
            'brands_processed': 0,
            'brands_successful': 0,
            'brands_failed': 0,
            'metrics_created': 0,
            'errors': [],
        }
        
        # Get all brands with active social accounts
        brands_with_accounts = Brand.objects.filter(
            social_accounts__is_active=True
        ).distinct()
        
        for brand in brands_with_accounts:
            try:
                brand_result = self.sync_brand(brand, date_from, date_to)
                results['brands_processed'] += 1
                
                if brand_result.get('success'):
                    results['brands_successful'] += 1
                    results['metrics_created'] += brand_result.get('metrics_created', 0)
                else:
                    results['brands_failed'] += 1
                    results['errors'].extend(brand_result.get('errors', []))
                    
            except Exception as e:
                logger.error(f"Error syncing brand {brand.name}: {e}")
                results['brands_failed'] += 1
                results['errors'].append(f"{brand.name}: {str(e)}")
        
        return results
    
    def sync_brand(
        self,
        brand: 'Brand',
        date_from: date,
        date_to: date
    ) -> Dict[str, Any]:
        """
        Sync all platform metrics for a single brand.
        
        Args:
            brand: Brand instance to sync
            date_from: Start date
            date_to: End date
            
        Returns:
            Dict with sync results
        """
        from tenants.models import BrandSocialAccount
        
        result = {
            'brand': brand.name,
            'success': True,
            'metrics_created': 0,
            'errors': [],
        }
        
        # Get all active social accounts for this brand
        accounts = BrandSocialAccount.objects.filter(
            brand=brand,
            is_active=True
        ).select_related('connection')
        
        for account in accounts:
            try:
                if account.platform == 'META' and account.has_analytics_permission:
                    meta_result = self._sync_meta_account(account, date_from, date_to)
                    result['metrics_created'] += meta_result.get('created', 0)
                    if meta_result.get('errors'):
                        result['errors'].extend(meta_result['errors'])
                        
                elif account.platform == 'TIKTOK':
                    tiktok_result = self._sync_tiktok_account(account, date_from, date_to)
                    result['metrics_created'] += tiktok_result.get('created', 0)
                    if tiktok_result.get('errors'):
                        result['errors'].extend(tiktok_result['errors'])
                        
                elif account.platform == 'GOOGLE_ANALYTICS':
                    ga_result = self._sync_ga_account(account, date_from, date_to)
                    result['metrics_created'] += ga_result.get('created', 0)
                    if ga_result.get('errors'):
                        result['errors'].extend(ga_result['errors'])
                        
            except Exception as e:
                logger.error(f"Error syncing account {account.platform} for {brand.name}: {e}")
                result['errors'].append(f"{account.platform}: {str(e)}")
        
        if result['errors']:
            result['success'] = False
        
        return result
    
    def _sync_meta_account(
        self,
        account: 'BrandSocialAccount',
        date_from: date,
        date_to: date
    ) -> Dict[str, Any]:
        """Sync Facebook and Instagram metrics."""
        from integrations.connectors.meta import MetaAnalyticsConnector
        from crm.models import SocialMetricsSnapshot, ContentPost
        
        result = {'created': 0, 'errors': []}
        
        if not account.connection:
            result['errors'].append("No connection configured for Meta account")
            return result
        
        try:
            connector = MetaAnalyticsConnector(account.connection, account)
            
            # Iterate through each day
            current_date = date_from
            while current_date <= date_to:
                date_str = current_date.strftime('%Y-%m-%d')
                
                # Sync Facebook Page metrics
                if account.facebook_page_id:
                    try:
                        fb_metrics = connector.get_page_daily_metrics(date_str)
                        if 'error' not in fb_metrics:
                            self._save_social_metrics(
                                account.brand, 'FACEBOOK', current_date, fb_metrics
                            )
                            result['created'] += 1
                    except Exception as e:
                        result['errors'].append(f"Facebook {date_str}: {str(e)}")
                
                # Sync Instagram metrics
                if account.instagram_business_id:
                    try:
                        ig_metrics = connector.get_instagram_daily_metrics(date_str)
                        if 'error' not in ig_metrics:
                            self._save_social_metrics(
                                account.brand, 'INSTAGRAM', current_date, ig_metrics
                            )
                            result['created'] += 1
                    except Exception as e:
                        result['errors'].append(f"Instagram {date_str}: {str(e)}")
                
                current_date += timedelta(days=1)
            
            # Sync content posts (once per sync, not daily)
            self._sync_meta_posts(connector, account)
            
        except Exception as e:
            result['errors'].append(f"Meta sync error: {str(e)}")
        
        return result
    
    def _sync_tiktok_account(
        self,
        account: 'BrandSocialAccount',
        date_from: date,
        date_to: date
    ) -> Dict[str, Any]:
        """Sync TikTok metrics."""
        from integrations.connectors.tiktok import TikTokConnector
        from crm.models import SocialMetricsSnapshot, ContentPost
        
        result = {'created': 0, 'errors': []}
        
        if not account.connection:
            result['errors'].append("No connection configured for TikTok account")
            return result
        
        try:
            connector = TikTokConnector(account.connection, account)
            
            # Get account metrics and videos
            videos = connector.get_videos(max_count=100)
            account_metrics = connector.calculate_daily_metrics(videos)
            
            # TikTok doesn't provide historical daily metrics,
            # so we store current snapshot for today
            self._save_social_metrics(
                account.brand, 'TIKTOK', timezone.now().date(), account_metrics
            )
            result['created'] += 1
            
            # Sync individual video posts
            self._sync_tiktok_posts(videos, account)
            
        except Exception as e:
            result['errors'].append(f"TikTok sync error: {str(e)}")
        
        return result
    
    def _sync_ga_account(
        self,
        account: 'BrandSocialAccount',
        date_from: date,
        date_to: date
    ) -> Dict[str, Any]:
        """Sync Google Analytics metrics."""
        from integrations.connectors.google_analytics import GoogleAnalyticsConnector
        from crm.models import WebTrafficSnapshot
        
        result = {'created': 0, 'errors': []}
        
        if not account.connection:
            result['errors'].append("No connection configured for GA4 account")
            return result
        
        try:
            connector = GoogleAnalyticsConnector(account.connection, account)
            
            # Iterate through each day
            current_date = date_from
            while current_date <= date_to:
                date_str = current_date.strftime('%Y-%m-%d')
                
                try:
                    snapshot_data = connector.get_full_daily_snapshot(date_str)
                    if 'error' not in snapshot_data:
                        self._save_web_traffic(account.brand, current_date, snapshot_data)
                        result['created'] += 1
                except Exception as e:
                    result['errors'].append(f"GA4 {date_str}: {str(e)}")
                
                current_date += timedelta(days=1)
            
        except Exception as e:
            result['errors'].append(f"GA4 sync error: {str(e)}")
        
        return result
    
    @transaction.atomic
    def _save_social_metrics(
        self,
        brand: 'Brand',
        platform: str,
        date_obj: date,
        metrics: Dict[str, Any]
    ):
        """Save or update social metrics snapshot."""
        from crm.models import SocialMetricsSnapshot
        
        defaults = {
            'followers': metrics.get('followers', 0),
            'followers_gained': metrics.get('page_fan_adds', metrics.get('followers_gained', 0)),
            'followers_lost': metrics.get('page_fan_removes', metrics.get('followers_lost', 0)),
            'reach': metrics.get('reach', metrics.get('page_impressions_unique', 0)),
            'impressions': metrics.get('impressions', metrics.get('page_impressions', 0)),
            'likes': metrics.get('likes', 0),
            'comments': metrics.get('comments', 0),
            'shares': metrics.get('shares', 0),
            'engagement_total': metrics.get('engagement_total', metrics.get('page_post_engagements', 0)),
            'engagement_rate': metrics.get('engagement_rate', 0),
            'link_clicks': metrics.get('link_clicks', metrics.get('page_website_clicks_logged_in_unique', 0)),
            'profile_visits': metrics.get('profile_views', metrics.get('page_views_total', 0)),
            'website_clicks': metrics.get('website_clicks', 0),
            'email_contacts': metrics.get('email_contacts', 0),
            'video_views': metrics.get('video_views', 0),
            'posts_published': metrics.get('posts_published', 0),
            'raw_data': metrics,
        }
        
        # Calculate net follower change
        defaults['followers_net_change'] = defaults['followers_gained'] - defaults['followers_lost']
        
        SocialMetricsSnapshot.objects.update_or_create(
            brand=brand,
            platform=platform,
            date=date_obj,
            defaults=defaults
        )
    
    @transaction.atomic
    def _save_web_traffic(
        self,
        brand: 'Brand',
        date_obj: date,
        data: Dict[str, Any]
    ):
        """Save or update web traffic snapshot."""
        from crm.models import WebTrafficSnapshot
        
        defaults = {
            'sessions': data.get('sessions', 0),
            'users': data.get('users', 0),
            'new_users': data.get('new_users', 0),
            'returning_users': data.get('returning_users', 0),
            'pageviews': data.get('pageviews', 0),
            'pages_per_session': data.get('pages_per_session', 0),
            'avg_session_duration': data.get('avg_session_duration', 0),
            'bounce_rate': data.get('bounce_rate', 0),
            'engagement_rate': data.get('engagement_rate', 0),
            'traffic_by_source': data.get('traffic_by_source', {}),
            'traffic_by_medium': data.get('traffic_by_medium', {}),
            'traffic_by_social': data.get('traffic_by_social', {}),
            'traffic_by_country': data.get('traffic_by_country', {}),
            'traffic_by_city': data.get('traffic_by_city', {}),
            'traffic_by_device': data.get('traffic_by_device', {}),
            'top_pages': data.get('top_pages', []),
            'goal_completions': data.get('goal_completions', 0),
            'raw_data': data,
        }
        
        WebTrafficSnapshot.objects.update_or_create(
            brand=brand,
            date=date_obj,
            defaults=defaults
        )
    
    def _sync_meta_posts(self, connector, account: 'BrandSocialAccount'):
        """Sync Facebook and Instagram posts."""
        from crm.models import ContentPost
        from dateutil.parser import parse as parse_date
        
        # Sync Facebook posts
        if account.facebook_page_id:
            try:
                posts = connector.get_page_posts(limit=50)
                for post_data in posts:
                    self._save_content_post(account.brand, post_data)
            except Exception as e:
                logger.error(f"Error syncing FB posts: {e}")
        
        # Sync Instagram media
        if account.instagram_business_id:
            try:
                media = connector.get_instagram_media(limit=50)
                for post_data in media:
                    self._save_content_post(account.brand, post_data)
            except Exception as e:
                logger.error(f"Error syncing IG posts: {e}")
    
    def _sync_tiktok_posts(self, videos: List[Dict], account: 'BrandSocialAccount'):
        """Sync TikTok video posts."""
        for video_data in videos:
            self._save_content_post(account.brand, video_data)
    
    @transaction.atomic
    def _save_content_post(self, brand: 'Brand', post_data: Dict):
        """Save or update content post."""
        from crm.models import ContentPost
        from dateutil.parser import parse as parse_date
        
        platform = post_data.get('platform')
        platform_post_id = post_data.get('platform_post_id')
        
        if not platform or not platform_post_id:
            return
        
        published_at = post_data.get('published_at')
        if isinstance(published_at, str):
            published_at = parse_date(published_at)
        
        # Extract hashtags from caption
        caption = post_data.get('caption', '')
        hashtags = [word for word in caption.split() if word.startswith('#')]
        
        defaults = {
            'post_type': post_data.get('post_type', 'POST'),
            'caption': caption,
            'hashtags': hashtags,
            'media_url': post_data.get('media_url', ''),
            'thumbnail_url': post_data.get('thumbnail_url', ''),
            'permalink': post_data.get('permalink', ''),
            'published_at': published_at or timezone.now(),
            'reach': post_data.get('reach', 0),
            'impressions': post_data.get('impressions', 0),
            'likes': post_data.get('likes', 0),
            'comments': post_data.get('comments', 0),
            'shares': post_data.get('shares', 0),
            'saves': post_data.get('saves', 0),
            'engagement_total': post_data.get('engagement_total', 0),
            'video_views': post_data.get('video_views', 0),
            'link_clicks': post_data.get('link_clicks', 0),
            'raw_data': post_data.get('raw_data', {}),
        }
        
        # Calculate engagement rate
        reach = defaults['reach'] or defaults['impressions']
        if reach > 0:
            engagement = defaults['likes'] + defaults['comments'] + defaults['shares'] + defaults['saves']
            defaults['engagement_rate'] = round((engagement / reach) * 100, 3)
        
        ContentPost.objects.update_or_create(
            brand=brand,
            platform=platform,
            platform_post_id=platform_post_id,
            defaults=defaults
        )
    
    # ========================================================================
    # BACKFILL METHODS
    # ========================================================================
    
    def backfill_brand(
        self,
        brand: 'Brand',
        platform: str,
        start_date: date = None
    ) -> Dict[str, Any]:
        """
        Backfill historical data for a brand.
        
        Args:
            brand: Brand to backfill
            platform: Platform to backfill ('META', 'TIKTOK', 'GOOGLE_ANALYTICS')
            start_date: Date to start backfill from (defaults per platform)
            
        Returns:
            Dict with backfill results
        """
        from tenants.models import BrandSocialAccount
        
        # Default start dates based on user requirements
        if start_date is None:
            if platform == 'META':
                start_date = date(2025, 1, 1)  # Jan 2025
            elif platform == 'TIKTOK':
                start_date = timezone.now().date() - timedelta(days=60)  # 60 days
            else:
                start_date = date(2025, 1, 1)  # Jan 2025
        
        end_date = timezone.now().date() - timedelta(days=1)  # Yesterday
        
        result = {
            'brand': brand.name,
            'platform': platform,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'success': True,
            'days_processed': 0,
            'errors': [],
        }
        
        # Get the account
        try:
            account = BrandSocialAccount.objects.get(
                brand=brand,
                platform=platform,
                is_active=True
            )
        except BrandSocialAccount.DoesNotExist:
            result['success'] = False
            result['errors'].append(f"No active {platform} account found for {brand.name}")
            return result
        
        # Update backfill status
        account.backfill_status = 'in_progress'
        account.save()
        
        try:
            sync_result = self.sync_brand(brand, start_date, end_date)
            result['days_processed'] = sync_result.get('metrics_created', 0)
            result['errors'] = sync_result.get('errors', [])
            
            if result['errors']:
                result['success'] = False
                account.backfill_status = 'failed'
            else:
                account.backfill_status = 'completed'
                account.last_backfill_date = start_date
            
            account.save()
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(str(e))
            account.backfill_status = 'failed'
            account.save()
        
        return result


# ============================================================================
# CELERY TASKS
# ============================================================================

def sync_social_analytics_task():
    """
    Celery task for weekly social analytics sync.
    
    Syncs all active brand accounts for yesterday's data.
    """
    from celery import shared_task
    
    @shared_task(name='sync_social_analytics')
    def _task():
        service = SocialSyncService()
        result = service.sync_all_brands()
        
        logger.info(
            f"Social sync complete: {result['brands_successful']}/{result['brands_processed']} "
            f"brands, {result['metrics_created']} metrics created"
        )
        
        if result['errors']:
            logger.warning(f"Sync errors: {result['errors']}")
        
        return result
    
    return _task


def backfill_brand_analytics_task(brand_id: str, platform: str, start_date_str: str = None):
    """
    Celery task for backfilling historical data.
    
    Args:
        brand_id: UUID of the brand
        platform: Platform to backfill
        start_date_str: Optional start date (YYYY-MM-DD)
    """
    from celery import shared_task
    
    @shared_task(name='backfill_brand_analytics')
    def _task(brand_id, platform, start_date_str):
        from tenants.models import Brand
        
        brand = Brand.objects.get(id=brand_id)
        
        start_date = None
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        service = SocialSyncService()
        result = service.backfill_brand(brand, platform, start_date)
        
        logger.info(f"Backfill complete for {brand.name} {platform}: {result}")
        
        return result
    
    return _task(brand_id, platform, start_date_str)
