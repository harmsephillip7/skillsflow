"""
Reusable mixins for views across the application.
"""
from core.context_processors import get_selected_campus


class CampusFilterMixin:
    """
    Mixin that provides campus filtering based on session selection.
    
    Usage in ListView:
        class MyListView(CampusFilterMixin, ListView):
            campus_field = 'campus'  # The field name on the model (default: 'campus')
            
    The mixin will automatically filter the queryset by the selected campus
    from session if one is selected. If 'All Campuses' is selected, no filter is applied.
    
    For function-based views, use get_selected_campus() directly:
        from core.context_processors import get_selected_campus
        
        def my_view(request):
            campus = get_selected_campus(request)
            if campus:
                queryset = Model.objects.filter(campus=campus)
            else:
                queryset = Model.objects.all()
    """
    campus_field = 'campus'  # Override this if your model uses a different field name
    
    def get_selected_campus(self):
        """Get the currently selected campus from session."""
        return get_selected_campus(self.request)
    
    def filter_by_campus(self, queryset):
        """
        Filter queryset by selected campus.
        Returns filtered queryset if campus is selected, otherwise original queryset.
        """
        campus = self.get_selected_campus()
        if campus:
            filter_kwargs = {self.campus_field: campus}
            return queryset.filter(**filter_kwargs)
        return queryset
    
    def get_queryset(self):
        """Override to apply campus filter to queryset."""
        queryset = super().get_queryset()
        return self.filter_by_campus(queryset)


class CampusFilterByBrandMixin(CampusFilterMixin):
    """
    Mixin for filtering by campus's brand instead of direct campus.
    Useful for brand-level data like marketing analytics.
    """
    campus_field = 'brand'
    
    def filter_by_campus(self, queryset):
        """Filter by brand of selected campus."""
        campus = self.get_selected_campus()
        if campus and hasattr(campus, 'brand'):
            filter_kwargs = {self.campus_field: campus.brand}
            return queryset.filter(**filter_kwargs)
        return queryset
