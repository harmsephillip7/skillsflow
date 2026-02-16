"""
Context Processors for Campus Selection
Provides campus data and selected campus to all templates
"""
from tenants.models import Campus


def get_selected_campus(request):
    """
    Helper function to get the selected campus from session.
    Can be called from views to filter querysets.
    Returns Campus instance or None (for 'all campuses').
    """
    selected_campus_id = request.session.get('selected_campus_id', 'all')
    
    if selected_campus_id != 'all':
        try:
            return Campus.objects.get(pk=selected_campus_id, is_active=True)
        except Campus.DoesNotExist:
            request.session['selected_campus_id'] = 'all'
    
    return None


def get_selected_campus_id(request):
    """
    Get the selected campus ID from session.
    Returns the campus ID or 'all'.
    """
    return request.session.get('selected_campus_id', 'all')


def campus_context(request):
    """
    Provides campus selection context to all templates.
    - all_campuses: List of all campuses for the switcher
    - selected_campus: Currently selected campus from session
    - selected_campus_id: ID of selected campus (or 'all')
    """
    campuses = Campus.objects.filter(is_active=True).order_by('name')
    
    # Get selected campus from session
    selected_campus_id = request.session.get('selected_campus_id', 'all')
    selected_campus = None
    
    if selected_campus_id != 'all':
        try:
            selected_campus = Campus.objects.get(pk=selected_campus_id, is_active=True)
        except Campus.DoesNotExist:
            # Reset to all if campus no longer exists
            request.session['selected_campus_id'] = 'all'
            selected_campus_id = 'all'
    
    return {
        'all_campuses': campuses,
        'selected_campus': selected_campus,
        'selected_campus_id': selected_campus_id,
    }
