"""Tenants app admin configuration"""
from django.contrib import admin
from .models import Brand, Campus


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """Admin for Brand model with autocomplete support"""
    list_display = ['code', 'name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'legal_name']
    ordering = ['name']


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    """Admin for Campus model with autocomplete support"""
    list_display = ['name', 'brand', 'city', 'province', 'is_active']
    list_filter = ['brand', 'province', 'is_active']
    search_fields = ['name', 'city', 'province', 'address']
    ordering = ['name']
