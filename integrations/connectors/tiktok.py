"""
TikTok Business API Connector

Connector for TikTok Business API to fetch:
- Account insights and metrics
- Video performance data
- Audience demographics

Requires TikTok Business Account and API credentials.
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone

from .base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class TikTokConnector(BaseConnector):
    """
    TikTok Business API connector for analytics.
    
    Uses TikTok Business API v2 for fetching insights data.
    
    Required Scopes:
    - user.info.basic
    - user.info.stats
    - video.list
    - video.insights
    """
    
    API_BASE = 'https://open.tiktokapis.com/v2'
    
    def __init__(self, connection: 'IntegrationConnection', brand_account: 'BrandSocialAccount' = None):
        self.brand_account = brand_account
        self.business_id = brand_account.tiktok_business_id if brand_account else None
        super().__init__(connection)
    
    def _setup_session(self):
        """Set up session with TikTok access token."""
        access_token = self.connection.access_token
        if not access_token:
            access_token = self.connection.api_key
        
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        })
    
    @property
    def provider_name(self) -> str:
        return 'tiktok'
    
    def check_health(self) -> Dict[str, Any]:
        """Check TikTok API connectivity."""
        try:
            response = self._make_request(
                'GET',
                f'{self.API_BASE}/user/info/',
                params={'fields': 'open_id,display_name'}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('error', {}).get('code') == 'ok':
                    return {
                        'healthy': True,
                        'message': 'Connected to TikTok API',
                        'details': data.get('data', {})
                    }
            return {
                'healthy': False,
                'message': f'API returned error',
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
        Refresh TikTok access token.
        TikTok tokens expire and need to be refreshed using refresh_token.
        """
        try:
            client_key = self.connection.client_id
            client_secret = self.connection.client_secret
            refresh_token = self.connection.refresh_token
            
            if not refresh_token:
                logger.error("No refresh token available for TikTok")
                return False
            
            response = self._make_request(
                'POST',
                f'{self.API_BASE}/oauth/token/',
                json={
                    'client_key': client_key,
                    'client_secret': client_secret,
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('error', {}).get('code') == 'ok':
                    token_data = data.get('data', {})
                    self.connection.access_token = token_data['access_token']
                    self.connection.refresh_token = token_data.get('refresh_token', refresh_token)
                    expires_in = token_data.get('expires_in', 86400)
                    self.connection.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
                    self.connection.save()
                    
                    self.session.headers['Authorization'] = f"Bearer {token_data['access_token']}"
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to refresh TikTok token: {e}")
            return False
    
    # ========================================================================
    # ACCOUNT INSIGHTS
    # ========================================================================
    
    def get_user_info(self) -> Dict[str, Any]:
        """
        Get TikTok user profile information.
        
        Returns display name, avatar, follower/following counts.
        """
        fields = [
            'open_id', 'display_name', 'avatar_url', 'bio_description',
            'profile_deep_link', 'follower_count', 'following_count',
            'likes_count', 'video_count'
        ]
        
        try:
            response = self._make_request(
                'GET',
                f'{self.API_BASE}/user/info/',
                params={'fields': ','.join(fields)}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('error', {}).get('code') == 'ok':
                    return data.get('data', {}).get('user', {})
            
            logger.error(f"Failed to get user info: {response.text}")
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching user info: {e}")
            return {}
    
    def get_account_metrics(self) -> Dict[str, Any]:
        """
        Get current account metrics snapshot.
        
        Returns:
            Dict with followers, following, likes, video counts
        """
        user_info = self.get_user_info()
        
        return {
            'followers': user_info.get('follower_count', 0),
            'following': user_info.get('following_count', 0),
            'total_likes': user_info.get('likes_count', 0),
            'video_count': user_info.get('video_count', 0),
            'display_name': user_info.get('display_name', ''),
            'bio': user_info.get('bio_description', ''),
        }
    
    # ========================================================================
    # VIDEO INSIGHTS
    # ========================================================================
    
    def get_videos(self, max_count: int = 100) -> List[Dict]:
        """
        Get list of videos from the account.
        
        Args:
            max_count: Maximum number of videos to retrieve
            
        Returns:
            List of video dictionaries with basic info
        """
        fields = [
            'id', 'title', 'video_description', 'cover_image_url',
            'share_url', 'create_time', 'duration',
            'view_count', 'like_count', 'comment_count', 'share_count'
        ]
        
        videos = []
        cursor = 0
        has_more = True
        
        try:
            while has_more and len(videos) < max_count:
                response = self._make_request(
                    'POST',
                    f'{self.API_BASE}/video/list/',
                    json={
                        'fields': fields,
                        'max_count': min(20, max_count - len(videos)),
                        'cursor': cursor,
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('error', {}).get('code') == 'ok':
                        video_data = data.get('data', {})
                        videos.extend(video_data.get('videos', []))
                        has_more = video_data.get('has_more', False)
                        cursor = video_data.get('cursor', 0)
                    else:
                        break
                else:
                    break
            
            return self._parse_videos(videos)
            
        except Exception as e:
            logger.error(f"Error fetching videos: {e}")
            return []
    
    def get_video_insights(self, video_ids: List[str]) -> Dict[str, Dict]:
        """
        Get detailed insights for specific videos.
        
        Args:
            video_ids: List of video IDs to get insights for
            
        Returns:
            Dict mapping video_id to metrics
        """
        # TikTok requires batch queries - max 20 videos per request
        results = {}
        
        for i in range(0, len(video_ids), 20):
            batch = video_ids[i:i+20]
            
            try:
                response = self._make_request(
                    'POST',
                    f'{self.API_BASE}/video/query/',
                    json={
                        'filters': {'video_ids': batch},
                        'fields': [
                            'id', 'view_count', 'like_count', 'comment_count',
                            'share_count', 'average_watch_time', 'total_watch_time',
                            'reach', 'full_video_watched_rate'
                        ]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('error', {}).get('code') == 'ok':
                        for video in data.get('data', {}).get('videos', []):
                            results[video['id']] = {
                                'views': video.get('view_count', 0),
                                'likes': video.get('like_count', 0),
                                'comments': video.get('comment_count', 0),
                                'shares': video.get('share_count', 0),
                                'avg_watch_time': video.get('average_watch_time', 0),
                                'total_watch_time': video.get('total_watch_time', 0),
                                'reach': video.get('reach', 0),
                                'completion_rate': video.get('full_video_watched_rate', 0),
                            }
                            
            except Exception as e:
                logger.error(f"Error fetching video insights: {e}")
        
        return results
    
    def get_videos_since(self, since_date: datetime) -> List[Dict]:
        """
        Get videos published since a specific date.
        
        Args:
            since_date: Datetime to fetch videos from
            
        Returns:
            List of videos published after since_date
        """
        all_videos = self.get_videos(max_count=200)
        
        # Filter by date
        filtered = []
        for video in all_videos:
            published_at = video.get('published_at')
            if published_at and published_at >= since_date:
                filtered.append(video)
        
        return filtered
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _parse_videos(self, videos: List[Dict]) -> List[Dict]:
        """Parse TikTok videos into standardized format."""
        parsed = []
        
        for video in videos:
            create_time = video.get('create_time', 0)
            
            parsed.append({
                'platform': 'TIKTOK',
                'platform_post_id': video.get('id'),
                'post_type': 'VIDEO',
                'caption': video.get('video_description', video.get('title', '')),
                'media_url': '',  # TikTok doesn't provide direct video URL
                'thumbnail_url': video.get('cover_image_url', ''),
                'permalink': video.get('share_url', ''),
                'published_at': datetime.fromtimestamp(create_time, tz=timezone.utc) if create_time else None,
                'duration': video.get('duration', 0),
                'impressions': video.get('view_count', 0),
                'reach': video.get('view_count', 0),  # TikTok doesn't distinguish
                'likes': video.get('like_count', 0),
                'comments': video.get('comment_count', 0),
                'shares': video.get('share_count', 0),
                'video_views': video.get('view_count', 0),
                'engagement_total': (
                    video.get('like_count', 0) + 
                    video.get('comment_count', 0) + 
                    video.get('share_count', 0)
                ),
                'raw_data': video,
            })
        
        return parsed
    
    def calculate_daily_metrics(self, videos: List[Dict]) -> Dict[str, Any]:
        """
        Calculate aggregated metrics from video list.
        
        TikTok doesn't provide account-level daily insights,
        so we aggregate from video-level data.
        """
        total_views = 0
        total_likes = 0
        total_comments = 0
        total_shares = 0
        
        for video in videos:
            total_views += video.get('video_views', 0)
            total_likes += video.get('likes', 0)
            total_comments += video.get('comments', 0)
            total_shares += video.get('shares', 0)
        
        total_engagement = total_likes + total_comments + total_shares
        engagement_rate = (total_engagement / total_views * 100) if total_views > 0 else 0
        
        # Get current follower count
        account_metrics = self.get_account_metrics()
        
        return {
            'followers': account_metrics.get('followers', 0),
            'impressions': total_views,
            'reach': total_views,
            'likes': total_likes,
            'comments': total_comments,
            'shares': total_shares,
            'engagement_total': total_engagement,
            'engagement_rate': round(engagement_rate, 3),
            'video_views': total_views,
            'posts_published': len(videos),
        }
