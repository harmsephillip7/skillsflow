"""
Marketing Analytics Dashboard Views

Provides comprehensive analytics for:
- Social media performance (Facebook, Instagram, TikTok)
- Website traffic (Google Analytics)
- Content performance
- Trend analysis
"""

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, List, Any

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.db.models import Sum, Avg, Count, F, Q
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth

from crm.models import SocialMetricsSnapshot, WebTrafficSnapshot, ContentPost
from tenants.models import Brand, BrandSocialAccount, Campus
from integrations.models import IntegrationConnection
from core.context_processors import get_selected_campus

logger = logging.getLogger(__name__)


def _get_current_brand(request):
    """Get the current brand for the logged-in user or from campus filter."""
    # First check global campus filter
    selected_campus = get_selected_campus(request)
    if selected_campus and hasattr(selected_campus, 'brand'):
        return selected_campus.brand
    
    try:
        profile = getattr(request.user, 'profile', None)
        if profile and getattr(profile, 'brand', None):
            return profile.brand
    except Exception:
        pass
    
    brand_id = request.session.get('brand_id')
    if brand_id:
        return Brand.objects.filter(id=brand_id, is_active=True).first()
    
    # Fallback for dev/superuser
    return Brand.objects.filter(is_active=True).first()


def _parse_date_range(request):
    """Parse date range from request parameters."""
    today = timezone.now().date()
    
    # Default to last 30 days
    default_start = today - timedelta(days=30)
    default_end = today - timedelta(days=1)
    
    range_type = request.GET.get('range', '30d')
    
    if range_type == '7d':
        start = today - timedelta(days=7)
        end = today - timedelta(days=1)
    elif range_type == '30d':
        start = today - timedelta(days=30)
        end = today - timedelta(days=1)
    elif range_type == '90d':
        start = today - timedelta(days=90)
        end = today - timedelta(days=1)
    elif range_type == 'ytd':
        start = date(today.year, 1, 1)
        end = today - timedelta(days=1)
    elif range_type == 'custom':
        try:
            start = datetime.strptime(request.GET.get('start', ''), '%Y-%m-%d').date()
            end = datetime.strptime(request.GET.get('end', ''), '%Y-%m-%d').date()
        except ValueError:
            start, end = default_start, default_end
    else:
        start, end = default_start, default_end
    
    return start, end, range_type


# ============================================================================
# MAIN DASHBOARD
# ============================================================================

@login_required
def marketing_dashboard(request):
    """
    Main marketing analytics dashboard.
    
    Shows:
    - Brand selector (if user has access to multiple brands)
    - Overview metrics across all platforms
    - Social media performance summary
    - Website traffic summary
    - Top performing content
    """
    # Get brand from request or user's default
    brand_id = request.GET.get('brand')
    if brand_id:
        brand = get_object_or_404(Brand, id=brand_id, is_active=True)
    else:
        brand = _get_current_brand(request)
    
    if not brand:
        messages.warning(request, "No brand configured. Please contact your administrator.")
        return redirect('dashboard')
    
    # Parse date range
    start_date, end_date, range_type = _parse_date_range(request)
    
    # Get all brands for brand selector (for admin users)
    if request.user.is_superuser or request.user.has_perm('crm.view_all_brands'):
        available_brands = Brand.objects.filter(is_active=True).order_by('name')
    else:
        available_brands = [brand]
    
    # Get social accounts status
    social_accounts = BrandSocialAccount.objects.filter(
        brand=brand
    ).select_related('connection')
    
    # Calculate overview metrics
    social_metrics = _get_social_overview(brand, start_date, end_date)
    web_metrics = _get_web_overview(brand, start_date, end_date)
    top_content = _get_top_content(brand, start_date, end_date, limit=5)
    
    # Calculate period comparison
    comparison = _calculate_comparison(brand, start_date, end_date)
    
    context = {
        'brand': brand,
        'available_brands': available_brands,
        'start_date': start_date,
        'end_date': end_date,
        'range_type': range_type,
        'social_accounts': social_accounts,
        'social_metrics': social_metrics,
        'web_metrics': web_metrics,
        'top_content': top_content,
        'comparison': comparison,
        'page_title': f'Marketing Analytics - {brand.name}',
    }
    
    return render(request, 'crm/marketing_dashboard.html', context)


# ============================================================================
# SOCIAL MEDIA VIEWS
# ============================================================================

@login_required
def social_analytics(request):
    """
    Detailed social media analytics view.
    
    Shows platform-specific breakdowns and comparisons.
    """
    brand_id = request.GET.get('brand')
    brand = get_object_or_404(Brand, id=brand_id) if brand_id else _get_current_brand(request)
    
    if not brand:
        return redirect('marketing_dashboard')
    
    start_date, end_date, range_type = _parse_date_range(request)
    platform = request.GET.get('platform', 'all')
    
    # Get metrics by platform
    platforms = ['FACEBOOK', 'INSTAGRAM', 'TIKTOK']
    platform_data = {}
    
    for plat in platforms:
        platform_data[plat] = _get_platform_metrics(brand, plat, start_date, end_date)
    
    # Get daily trend data
    daily_data = _get_social_daily_trend(brand, start_date, end_date, platform)
    
    # Get engagement breakdown
    engagement_data = _get_engagement_breakdown(brand, start_date, end_date)
    
    context = {
        'brand': brand,
        'start_date': start_date,
        'end_date': end_date,
        'range_type': range_type,
        'platform': platform,
        'platform_data': platform_data,
        'daily_data': daily_data,
        'engagement_data': engagement_data,
        'page_title': f'Social Analytics - {brand.name}',
    }
    
    return render(request, 'crm/social_analytics.html', context)


@login_required
def content_analytics(request):
    """
    Content performance analytics.
    
    Shows individual post performance with filtering and sorting.
    """
    brand_id = request.GET.get('brand')
    brand = get_object_or_404(Brand, id=brand_id) if brand_id else _get_current_brand(request)
    
    if not brand:
        return redirect('marketing_dashboard')
    
    start_date, end_date, range_type = _parse_date_range(request)
    platform = request.GET.get('platform', 'all')
    sort_by = request.GET.get('sort', '-engagement_rate')
    
    # Get content posts
    posts = ContentPost.objects.filter(
        brand=brand,
        published_at__date__gte=start_date,
        published_at__date__lte=end_date,
    )
    
    if platform != 'all':
        posts = posts.filter(platform=platform.upper())
    
    posts = posts.order_by(sort_by)[:50]
    
    # Calculate content stats
    content_stats = ContentPost.objects.filter(
        brand=brand,
        published_at__date__gte=start_date,
        published_at__date__lte=end_date,
    ).aggregate(
        total_posts=Count('id'),
        total_reach=Sum('reach'),
        total_engagement=Sum('engagement_total'),
        avg_engagement_rate=Avg('engagement_rate'),
    )
    
    context = {
        'brand': brand,
        'start_date': start_date,
        'end_date': end_date,
        'range_type': range_type,
        'platform': platform,
        'posts': posts,
        'content_stats': content_stats,
        'page_title': f'Content Analytics - {brand.name}',
    }
    
    return render(request, 'crm/content_analytics.html', context)


# ============================================================================
# WEB TRAFFIC VIEWS
# ============================================================================

@login_required
def web_analytics(request):
    """
    Website traffic analytics from Google Analytics.
    """
    brand_id = request.GET.get('brand')
    brand = get_object_or_404(Brand, id=brand_id) if brand_id else _get_current_brand(request)
    
    if not brand:
        return redirect('marketing_dashboard')
    
    start_date, end_date, range_type = _parse_date_range(request)
    
    # Get web metrics overview
    web_metrics = _get_web_overview(brand, start_date, end_date)
    
    # Get traffic source breakdown
    source_data = _get_traffic_sources(brand, start_date, end_date)
    
    # Get daily trend
    daily_data = _get_web_daily_trend(brand, start_date, end_date)
    
    # Get top pages
    top_pages = _get_top_pages(brand, start_date, end_date)
    
    # Get device breakdown
    device_data = _get_device_breakdown(brand, start_date, end_date)
    
    context = {
        'brand': brand,
        'start_date': start_date,
        'end_date': end_date,
        'range_type': range_type,
        'web_metrics': web_metrics,
        'source_data': source_data,
        'daily_data': daily_data,
        'top_pages': top_pages,
        'device_data': device_data,
        'page_title': f'Web Analytics - {brand.name}',
    }
    
    return render(request, 'crm/web_analytics.html', context)


# ============================================================================
# API ENDPOINTS (for Chart.js)
# ============================================================================

@login_required
@require_GET
def api_social_trend(request):
    """API endpoint for social metrics trend chart data."""
    brand_id = request.GET.get('brand')
    brand = get_object_or_404(Brand, id=brand_id) if brand_id else _get_current_brand(request)
    
    start_date, end_date, _ = _parse_date_range(request)
    platform = request.GET.get('platform', 'all')
    metric = request.GET.get('metric', 'reach')
    
    data = _get_social_daily_trend(brand, start_date, end_date, platform)
    
    # Format for Chart.js
    chart_data = {
        'labels': [d['date'].strftime('%Y-%m-%d') for d in data],
        'datasets': [],
    }
    
    platforms = ['FACEBOOK', 'INSTAGRAM', 'TIKTOK'] if platform == 'all' else [platform.upper()]
    colors = {'FACEBOOK': '#1877f2', 'INSTAGRAM': '#e4405f', 'TIKTOK': '#000000'}
    
    for plat in platforms:
        chart_data['datasets'].append({
            'label': plat.title(),
            'data': [d.get(f'{plat.lower()}_{metric}', 0) for d in data],
            'borderColor': colors.get(plat, '#6b7280'),
            'backgroundColor': colors.get(plat, '#6b7280') + '20',
            'fill': True,
        })
    
    return JsonResponse(chart_data)


@login_required
@require_GET
def api_web_trend(request):
    """API endpoint for web traffic trend chart data."""
    brand_id = request.GET.get('brand')
    brand = get_object_or_404(Brand, id=brand_id) if brand_id else _get_current_brand(request)
    
    start_date, end_date, _ = _parse_date_range(request)
    metric = request.GET.get('metric', 'sessions')
    
    data = _get_web_daily_trend(brand, start_date, end_date)
    
    chart_data = {
        'labels': [d['date'].strftime('%Y-%m-%d') for d in data],
        'datasets': [{
            'label': metric.replace('_', ' ').title(),
            'data': [d.get(metric, 0) for d in data],
            'borderColor': '#3b82f6',
            'backgroundColor': '#3b82f620',
            'fill': True,
        }]
    }
    
    return JsonResponse(chart_data)


@login_required
@require_GET
def api_engagement_breakdown(request):
    """API endpoint for engagement type breakdown (pie chart)."""
    brand_id = request.GET.get('brand')
    brand = get_object_or_404(Brand, id=brand_id) if brand_id else _get_current_brand(request)
    
    start_date, end_date, _ = _parse_date_range(request)
    
    data = _get_engagement_breakdown(brand, start_date, end_date)
    
    chart_data = {
        'labels': ['Likes', 'Comments', 'Shares', 'Saves'],
        'datasets': [{
            'data': [
                data.get('likes', 0),
                data.get('comments', 0),
                data.get('shares', 0),
                data.get('saves', 0),
            ],
            'backgroundColor': ['#ef4444', '#3b82f6', '#10b981', '#f59e0b'],
        }]
    }
    
    return JsonResponse(chart_data)


@login_required
@require_GET
def api_traffic_sources(request):
    """API endpoint for traffic source breakdown."""
    brand_id = request.GET.get('brand')
    brand = get_object_or_404(Brand, id=brand_id) if brand_id else _get_current_brand(request)
    
    start_date, end_date, _ = _parse_date_range(request)
    
    data = _get_traffic_sources(brand, start_date, end_date)
    
    chart_data = {
        'labels': list(data.get('by_medium', {}).keys()),
        'datasets': [{
            'data': list(data.get('by_medium', {}).values()),
            'backgroundColor': ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'],
        }]
    }
    
    return JsonResponse(chart_data)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_social_overview(brand: Brand, start_date: date, end_date: date) -> Dict[str, Any]:
    """Get aggregated social metrics for date range."""
    metrics = SocialMetricsSnapshot.objects.filter(
        brand=brand,
        date__gte=start_date,
        date__lte=end_date,
    ).aggregate(
        total_reach=Sum('reach'),
        total_impressions=Sum('impressions'),
        total_engagement=Sum('engagement_total'),
        total_followers_gained=Sum('followers_net_change'),
        avg_engagement_rate=Avg('engagement_rate'),
        total_link_clicks=Sum('link_clicks'),
        total_video_views=Sum('video_views'),
    )
    
    # Get latest follower counts per platform
    latest_followers = {}
    for platform in ['FACEBOOK', 'INSTAGRAM', 'TIKTOK']:
        latest = SocialMetricsSnapshot.objects.filter(
            brand=brand,
            platform=platform,
            date__lte=end_date,
        ).order_by('-date').first()
        if latest:
            latest_followers[platform.lower()] = latest.followers
    
    metrics['followers_by_platform'] = latest_followers
    metrics['total_followers'] = sum(latest_followers.values())
    
    return metrics


def _get_web_overview(brand: Brand, start_date: date, end_date: date) -> Dict[str, Any]:
    """Get aggregated web traffic metrics for date range."""
    metrics = WebTrafficSnapshot.objects.filter(
        brand=brand,
        date__gte=start_date,
        date__lte=end_date,
    ).aggregate(
        total_sessions=Sum('sessions'),
        total_users=Sum('users'),
        total_new_users=Sum('new_users'),
        total_pageviews=Sum('pageviews'),
        avg_bounce_rate=Avg('bounce_rate'),
        avg_session_duration=Avg('avg_session_duration'),
        avg_engagement_rate=Avg('engagement_rate'),
        total_conversions=Sum('goal_completions'),
    )
    
    return metrics


def _get_platform_metrics(brand: Brand, platform: str, start_date: date, end_date: date) -> Dict[str, Any]:
    """Get metrics for a specific platform."""
    metrics = SocialMetricsSnapshot.objects.filter(
        brand=brand,
        platform=platform,
        date__gte=start_date,
        date__lte=end_date,
    ).aggregate(
        total_reach=Sum('reach'),
        total_impressions=Sum('impressions'),
        total_engagement=Sum('engagement_total'),
        total_likes=Sum('likes'),
        total_comments=Sum('comments'),
        total_shares=Sum('shares'),
        avg_engagement_rate=Avg('engagement_rate'),
        follower_change=Sum('followers_net_change'),
    )
    
    # Get latest follower count
    latest = SocialMetricsSnapshot.objects.filter(
        brand=brand,
        platform=platform,
        date__lte=end_date,
    ).order_by('-date').first()
    
    metrics['followers'] = latest.followers if latest else 0
    
    return metrics


def _get_social_daily_trend(brand: Brand, start_date: date, end_date: date, platform: str = 'all') -> List[Dict]:
    """Get daily social metrics for trend charts."""
    queryset = SocialMetricsSnapshot.objects.filter(
        brand=brand,
        date__gte=start_date,
        date__lte=end_date,
    )
    
    if platform != 'all':
        queryset = queryset.filter(platform=platform.upper())
    
    # Group by date
    daily = queryset.values('date').annotate(
        total_reach=Sum('reach'),
        total_impressions=Sum('impressions'),
        total_engagement=Sum('engagement_total'),
        avg_engagement_rate=Avg('engagement_rate'),
    ).order_by('date')
    
    # Also get per-platform data
    if platform == 'all':
        result = []
        for row in daily:
            entry = {
                'date': row['date'],
                'total_reach': row['total_reach'],
                'total_engagement': row['total_engagement'],
            }
            
            # Add platform breakdowns
            for plat in ['FACEBOOK', 'INSTAGRAM', 'TIKTOK']:
                plat_data = SocialMetricsSnapshot.objects.filter(
                    brand=brand,
                    platform=plat,
                    date=row['date'],
                ).aggregate(
                    reach=Sum('reach'),
                    engagement=Sum('engagement_total'),
                )
                entry[f'{plat.lower()}_reach'] = plat_data['reach'] or 0
                entry[f'{plat.lower()}_engagement'] = plat_data['engagement'] or 0
            
            result.append(entry)
        
        return result
    
    return list(daily)


def _get_web_daily_trend(brand: Brand, start_date: date, end_date: date) -> List[Dict]:
    """Get daily web traffic for trend charts."""
    daily = WebTrafficSnapshot.objects.filter(
        brand=brand,
        date__gte=start_date,
        date__lte=end_date,
    ).values('date').annotate(
        sessions=Sum('sessions'),
        users=Sum('users'),
        pageviews=Sum('pageviews'),
        bounce_rate=Avg('bounce_rate'),
    ).order_by('date')
    
    return list(daily)


def _get_engagement_breakdown(brand: Brand, start_date: date, end_date: date) -> Dict[str, int]:
    """Get engagement breakdown by type."""
    totals = SocialMetricsSnapshot.objects.filter(
        brand=brand,
        date__gte=start_date,
        date__lte=end_date,
    ).aggregate(
        likes=Sum('likes'),
        comments=Sum('comments'),
        shares=Sum('shares'),
        saves=Sum('saves'),
    )
    
    return {k: v or 0 for k, v in totals.items()}


def _get_traffic_sources(brand: Brand, start_date: date, end_date: date) -> Dict[str, Dict]:
    """Get traffic source breakdown from GA data."""
    snapshots = WebTrafficSnapshot.objects.filter(
        brand=brand,
        date__gte=start_date,
        date__lte=end_date,
    )
    
    # Aggregate JSON fields
    by_source = {}
    by_medium = {}
    by_social = {}
    
    for snapshot in snapshots:
        for source, count in snapshot.traffic_by_source.items():
            by_source[source] = by_source.get(source, 0) + count
        for medium, count in snapshot.traffic_by_medium.items():
            by_medium[medium] = by_medium.get(medium, 0) + count
        for social, count in snapshot.traffic_by_social.items():
            by_social[social] = by_social.get(social, 0) + count
    
    return {
        'by_source': dict(sorted(by_source.items(), key=lambda x: x[1], reverse=True)[:10]),
        'by_medium': dict(sorted(by_medium.items(), key=lambda x: x[1], reverse=True)),
        'by_social': dict(sorted(by_social.items(), key=lambda x: x[1], reverse=True)),
    }


def _get_top_pages(brand: Brand, start_date: date, end_date: date, limit: int = 10) -> List[Dict]:
    """Get top pages from GA data."""
    snapshots = WebTrafficSnapshot.objects.filter(
        brand=brand,
        date__gte=start_date,
        date__lte=end_date,
    )
    
    # Aggregate page views
    pages = {}
    for snapshot in snapshots:
        for page in snapshot.top_pages:
            path = page.get('path', '/')
            views = page.get('views', 0)
            pages[path] = pages.get(path, 0) + views
    
    # Sort and limit
    sorted_pages = sorted(pages.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    return [{'path': p[0], 'views': p[1]} for p in sorted_pages]


def _get_device_breakdown(brand: Brand, start_date: date, end_date: date) -> Dict[str, int]:
    """Get device category breakdown."""
    snapshots = WebTrafficSnapshot.objects.filter(
        brand=brand,
        date__gte=start_date,
        date__lte=end_date,
    )
    
    devices = {}
    for snapshot in snapshots:
        for device, count in snapshot.traffic_by_device.items():
            devices[device] = devices.get(device, 0) + count
    
    return devices


def _get_top_content(brand: Brand, start_date: date, end_date: date, limit: int = 5) -> List:
    """Get top performing content posts."""
    return ContentPost.objects.filter(
        brand=brand,
        published_at__date__gte=start_date,
        published_at__date__lte=end_date,
    ).order_by('-engagement_rate')[:limit]


def _calculate_comparison(brand: Brand, start_date: date, end_date: date) -> Dict[str, Any]:
    """Calculate period-over-period comparison."""
    days = (end_date - start_date).days
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days)
    
    # Current period
    current_social = _get_social_overview(brand, start_date, end_date)
    current_web = _get_web_overview(brand, start_date, end_date)
    
    # Previous period
    prev_social = _get_social_overview(brand, prev_start, prev_end)
    prev_web = _get_web_overview(brand, prev_start, prev_end)
    
    def calc_change(current, previous):
        if not previous or previous == 0:
            return 0
        return round(((current or 0) - previous) / previous * 100, 1)
    
    return {
        'reach_change': calc_change(
            current_social.get('total_reach'),
            prev_social.get('total_reach')
        ),
        'engagement_change': calc_change(
            current_social.get('total_engagement'),
            prev_social.get('total_engagement')
        ),
        'sessions_change': calc_change(
            current_web.get('total_sessions'),
            prev_web.get('total_sessions')
        ),
        'followers_change': calc_change(
            current_social.get('total_followers'),
            prev_social.get('total_followers')
        ),
        'prev_period': f"{prev_start.strftime('%b %d')} - {prev_end.strftime('%b %d')}",
    }
