"""
Django Admin configuration for Integration Hub.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    IntegrationProvider,
    IntegrationConnection,
    IntegrationSyncLog,
    IntegrationWebhook,
    IntegrationWebhookLog,
    IntegrationFieldMapping,
    IntegrationEntityMapping,
)


@admin.register(IntegrationProvider)
class IntegrationProviderAdmin(admin.ModelAdmin):
    """Admin for integration provider registry."""
    
    list_display = [
        'name', 'slug', 'category', 'auth_type', 
        'is_active', 'is_beta', 'connection_count'
    ]
    list_filter = ['category', 'auth_type', 'is_active', 'is_beta']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'description')
        }),
        ('Classification', {
            'fields': ('category', 'auth_type')
        }),
        ('Branding', {
            'fields': ('logo', 'icon_class', 'color')
        }),
        ('OAuth Configuration', {
            'fields': ('oauth_auth_url', 'oauth_token_url', 'oauth_scopes'),
            'classes': ('collapse',)
        }),
        ('Rate Limiting', {
            'fields': ('rate_limit_requests', 'rate_limit_window_seconds')
        }),
        ('Features', {
            'fields': ('supports_sync', 'supports_webhooks', 'supports_realtime')
        }),
        ('Status', {
            'fields': ('is_active', 'is_beta', 'connector_class')
        }),
        ('Documentation', {
            'fields': ('docs_url', 'setup_instructions'),
            'classes': ('collapse',)
        }),
    )
    
    def connection_count(self, obj):
        """Count of active connections for this provider."""
        return obj.connections.filter(status='ACTIVE').count()
    connection_count.short_description = 'Active Connections'


class IntegrationWebhookInline(admin.TabularInline):
    """Inline for webhooks on connection page."""
    model = IntegrationWebhook
    extra = 0
    fields = ['name', 'is_active', 'is_verified', 'total_received', 'last_received_at']
    readonly_fields = ['total_received', 'last_received_at']


class IntegrationFieldMappingInline(admin.TabularInline):
    """Inline for field mappings on connection page."""
    model = IntegrationFieldMapping
    extra = 0
    fields = ['entity_type', 'internal_field', 'external_field', 'transform_type', 'is_active']


@admin.register(IntegrationConnection)
class IntegrationConnectionAdmin(admin.ModelAdmin):
    """Admin for integration connections."""
    
    list_display = [
        'display_name', 'provider', 'brand', 'status_badge', 
        'health_badge', 'last_sync_display', 'rate_limit_display'
    ]
    list_filter = ['provider', 'brand', 'status', 'health_status', 'sync_enabled']
    search_fields = ['name', 'provider__name', 'brand__name']
    readonly_fields = [
        'id', 'status', 'health_status', 'last_health_check',
        'last_sync_at', 'last_sync_status', 'next_sync_at',
        'rate_limit_remaining', 'rate_limit_resets_at',
        'connected_at', 'disconnected_at',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    
    inlines = [IntegrationWebhookInline, IntegrationFieldMappingInline]
    
    fieldsets = (
        ('Connection', {
            'fields': ('id', 'provider', 'brand', 'name')
        }),
        ('Status', {
            'fields': ('status', 'health_status', 'last_health_check', 'status_message')
        }),
        ('Credentials', {
            'fields': ('api_key', 'api_secret', 'client_id', 'client_secret'),
            'classes': ('collapse',),
            'description': 'Credentials are stored encrypted. Leave blank to keep existing values.'
        }),
        ('OAuth Tokens', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at'),
            'classes': ('collapse',)
        }),
        ('Configuration', {
            'fields': ('base_url', 'webhook_url', 'config')
        }),
        ('Sync Settings', {
            'fields': ('sync_enabled', 'sync_interval_minutes', 'last_sync_at', 'last_sync_status', 'next_sync_at')
        }),
        ('Rate Limiting', {
            'fields': ('rate_limit_remaining', 'rate_limit_resets_at')
        }),
        ('Timestamps', {
            'fields': ('connected_at', 'disconnected_at', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def display_name(self, obj):
        return obj.name or obj.provider.name
    display_name.short_description = 'Name'
    
    def status_badge(self, obj):
        colors = {
            'ACTIVE': 'green',
            'PENDING': 'orange',
            'ERROR': 'red',
            'DISCONNECTED': 'gray',
            'EXPIRED': 'red',
            'RATE_LIMITED': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def health_badge(self, obj):
        colors = {
            'HEALTHY': 'green',
            'DEGRADED': 'orange',
            'UNHEALTHY': 'red',
            'UNKNOWN': 'gray',
        }
        color = colors.get(obj.health_status, 'gray')
        return format_html(
            '<span style="color: {};">●</span> {}',
            color, obj.get_health_status_display()
        )
    health_badge.short_description = 'Health'
    
    def last_sync_display(self, obj):
        if obj.last_sync_at:
            return format_html(
                '{}<br><small style="color: gray;">{}</small>',
                obj.last_sync_at.strftime('%Y-%m-%d %H:%M'),
                obj.last_sync_status or 'Unknown'
            )
        return '-'
    last_sync_display.short_description = 'Last Sync'
    
    def rate_limit_display(self, obj):
        if obj.rate_limit_remaining is not None:
            pct = obj.rate_limit_percentage or 0
            color = 'green' if pct < 50 else 'orange' if pct < 80 else 'red'
            return format_html(
                '<span style="color: {};">{} remaining</span>',
                color, obj.rate_limit_remaining
            )
        return '-'
    rate_limit_display.short_description = 'Rate Limit'


@admin.register(IntegrationSyncLog)
class IntegrationSyncLogAdmin(admin.ModelAdmin):
    """Admin for sync logs."""
    
    list_display = [
        'short_id', 'connection', 'entity_type', 'direction',
        'status_badge', 'records_display', 'duration_display', 'started_at'
    ]
    list_filter = ['status', 'direction', 'entity_type', 'connection__provider', 'is_scheduled']
    search_fields = ['connection__name', 'entity_type', 'error_message']
    readonly_fields = [
        'id', 'connection', 'started_at', 'completed_at', 'duration_ms',
        'records_total', 'records_processed', 'records_failed', 'records_skipped',
        'request_payload', 'response_payload', 'error_message', 'error_details',
        'triggered_by', 'is_scheduled'
    ]
    date_hierarchy = 'started_at'
    
    fieldsets = (
        ('Operation', {
            'fields': ('id', 'connection', 'entity_type', 'operation', 'direction')
        }),
        ('Status', {
            'fields': ('status', 'error_message', 'error_details')
        }),
        ('Metrics', {
            'fields': ('records_total', 'records_processed', 'records_failed', 'records_skipped')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'duration_ms')
        }),
        ('Debug Data', {
            'fields': ('request_payload', 'response_payload'),
            'classes': ('collapse',)
        }),
        ('Trigger', {
            'fields': ('triggered_by', 'is_scheduled')
        }),
    )
    
    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = 'ID'
    
    def status_badge(self, obj):
        colors = {
            'SUCCESS': 'green',
            'PARTIAL': 'orange',
            'FAILED': 'red',
            'PENDING': 'gray',
            'IN_PROGRESS': 'blue',
            'CANCELLED': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def records_display(self, obj):
        if obj.records_total:
            return format_html(
                '{}/{} <small style="color: gray;">({} failed)</small>',
                obj.records_processed, obj.records_total, obj.records_failed
            )
        return '-'
    records_display.short_description = 'Records'
    
    def duration_display(self, obj):
        if obj.duration_ms:
            if obj.duration_ms > 60000:
                return f"{obj.duration_ms / 60000:.1f}m"
            elif obj.duration_ms > 1000:
                return f"{obj.duration_ms / 1000:.1f}s"
            return f"{obj.duration_ms}ms"
        return '-'
    duration_display.short_description = 'Duration'


@admin.register(IntegrationWebhook)
class IntegrationWebhookAdmin(admin.ModelAdmin):
    """Admin for webhooks."""
    
    list_display = [
        'name', 'connection', 'is_active', 'is_verified',
        'event_types_display', 'stats_display', 'last_received_at'
    ]
    list_filter = ['is_active', 'is_verified', 'connection__provider']
    search_fields = ['name', 'connection__name']
    readonly_fields = ['id', 'endpoint_url', 'total_received', 'total_processed', 'total_failed', 'last_received_at']
    
    fieldsets = (
        ('Configuration', {
            'fields': ('id', 'connection', 'name', 'event_types')
        }),
        ('Security', {
            'fields': ('secret_key', 'allowed_ips'),
            'description': 'Secret key is stored encrypted.'
        }),
        ('Status', {
            'fields': ('is_active', 'is_verified')
        }),
        ('Endpoint', {
            'fields': ('endpoint_url',),
            'description': 'Share this URL with the external service.'
        }),
        ('Statistics', {
            'fields': ('total_received', 'total_processed', 'total_failed', 'last_received_at')
        }),
    )
    
    def event_types_display(self, obj):
        if obj.event_types:
            return ', '.join(obj.event_types[:3]) + ('...' if len(obj.event_types) > 3 else '')
        return '-'
    event_types_display.short_description = 'Events'
    
    def stats_display(self, obj):
        return format_html(
            '{} <span style="color: green;">✓</span> / {} <span style="color: red;">✗</span>',
            obj.total_processed, obj.total_failed
        )
    stats_display.short_description = 'Processed/Failed'


@admin.register(IntegrationWebhookLog)
class IntegrationWebhookLogAdmin(admin.ModelAdmin):
    """Admin for webhook logs."""
    
    list_display = ['short_id', 'webhook', 'event_type', 'status', 'ip_address', 'received_at']
    list_filter = ['status', 'webhook__connection__provider']
    search_fields = ['event_type', 'webhook__name']
    readonly_fields = ['id', 'webhook', 'event_type', 'headers', 'payload', 'ip_address', 'status', 'error_message', 'received_at', 'processed_at']
    date_hierarchy = 'received_at'
    
    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = 'ID'


@admin.register(IntegrationFieldMapping)
class IntegrationFieldMappingAdmin(admin.ModelAdmin):
    """Admin for field mappings."""
    
    list_display = ['connection', 'entity_type', 'internal_field', 'external_field', 'transform_type', 'is_active']
    list_filter = ['entity_type', 'transform_type', 'is_active', 'connection__provider']
    search_fields = ['internal_field', 'external_field']


@admin.register(IntegrationEntityMapping)
class IntegrationEntityMappingAdmin(admin.ModelAdmin):
    """Admin for entity ID mappings."""
    
    list_display = ['connection', 'entity_type', 'internal_id', 'external_id', 'sync_status', 'last_synced_at']
    list_filter = ['entity_type', 'sync_status', 'connection__provider']
    search_fields = ['internal_id', 'external_id']
    readonly_fields = ['last_synced_at']
