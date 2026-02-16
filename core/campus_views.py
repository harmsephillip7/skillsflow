"""
Views for handling campus selection
"""
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin


class SetCampusView(LoginRequiredMixin, View):
    """
    API view to set the selected campus in session.
    Called via AJAX from the campus switcher dropdown.
    """
    
    def post(self, request):
        campus_id = request.POST.get('campus_id', 'all')
        
        if campus_id == 'all':
            request.session['selected_campus_id'] = 'all'
        else:
            try:
                from tenants.models import Campus
                # Validate campus exists
                campus = Campus.objects.get(pk=campus_id, is_active=True)
                request.session['selected_campus_id'] = str(campus.pk)
            except (Campus.DoesNotExist, ValueError):
                request.session['selected_campus_id'] = 'all'
        
        # Return the new selection
        return JsonResponse({
            'success': True,
            'campus_id': request.session['selected_campus_id'],
        })
