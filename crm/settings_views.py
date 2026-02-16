"""
CRM Settings Views
User-friendly settings interface for CRM configuration.
Replaces Django admin for CRM settings management.
"""
import json
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Count
from django.utils import timezone

from .models import LeadSource
from core.models import RequiredDocumentConfig


class CRMAccessMixin(UserPassesTestMixin):
    """Mixin to check if user has CRM access"""
    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        # Check if user has CRM role
        if hasattr(user, 'user_roles'):
            return user.user_roles.filter(role__name__icontains='CRM').exists() or \
                   user.user_roles.filter(role__name__icontains='Sales').exists() or \
                   user.user_roles.filter(role__name__icontains='Marketing').exists() or \
                   user.user_roles.filter(role__name__icontains='Admin').exists()
        return False


class CRMSettingsView(LoginRequiredMixin, CRMAccessMixin, TemplateView):
    """
    Main CRM Settings page with tabs for different settings categories.
    """
    template_name = 'crm/settings/crm_settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get lead sources with lead counts
        lead_sources = LeadSource.objects.annotate(
            lead_count=Count('leads')
        ).order_by('name')
        
        # Serialize for JavaScript
        context['lead_sources'] = json.dumps([
            {
                'id': s.id,
                'name': s.name,
                'code': s.code,
                'description': s.description or '',
                'is_active': s.is_active,
                'lead_count': s.lead_count
            }
            for s in lead_sources
        ])
        
        # Get required document configs
        required_documents = RequiredDocumentConfig.objects.all().order_by('order', 'document_type')
        doc_type_dict = dict(RequiredDocumentConfig.DOCUMENT_TYPES)
        
        context['required_documents'] = json.dumps([
            {
                'id': d.id,
                'document_type': d.document_type,
                'display_name': doc_type_dict.get(d.document_type, d.document_type),
                'description': d.description or '',
                'is_required': d.is_required,
                'order': d.order
            }
            for d in required_documents
        ])
        
        # Get available document types for dropdown
        context['document_type_choices'] = json.dumps(list(RequiredDocumentConfig.DOCUMENT_TYPES))
        
        # Active tab
        context['active_tab'] = self.request.GET.get('tab', 'lead-sources')
        
        return context


class LeadSourceAPIView(LoginRequiredMixin, CRMAccessMixin, View):
    """
    API endpoint for CRUD operations on lead sources.
    """
    
    def post(self, request):
        """Create a new lead source"""
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            description = data.get('description', '').strip()
            is_active = data.get('is_active', True)
            
            if not name:
                return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)
            
            # Generate code from name
            code = name.upper().replace(' ', '_').replace('-', '_')[:20]
            
            # Check for duplicate code
            if LeadSource.objects.filter(code=code).exists():
                # Append number to make unique
                base_code = code[:17]
                counter = 1
                while LeadSource.objects.filter(code=f"{base_code}_{counter}").exists():
                    counter += 1
                code = f"{base_code}_{counter}"
            
            source = LeadSource.objects.create(
                name=name,
                code=code,
                description=description,
                is_active=is_active
            )
            
            return JsonResponse({
                'success': True,
                'source': {
                    'id': source.id,
                    'name': source.name,
                    'code': source.code,
                    'description': source.description,
                    'is_active': source.is_active,
                    'lead_count': 0
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    def put(self, request):
        """Update an existing lead source"""
        try:
            data = json.loads(request.body)
            source_id = data.get('id')
            
            if not source_id:
                return JsonResponse({'success': False, 'error': 'Source ID is required'}, status=400)
            
            source = get_object_or_404(LeadSource, id=source_id)
            
            if 'name' in data:
                source.name = data['name'].strip()
            if 'description' in data:
                source.description = data['description'].strip()
            if 'is_active' in data:
                source.is_active = data['is_active']
            
            source.save()
            
            lead_count = source.leads.count()
            
            return JsonResponse({
                'success': True,
                'source': {
                    'id': source.id,
                    'name': source.name,
                    'code': source.code,
                    'description': source.description,
                    'is_active': source.is_active,
                    'lead_count': lead_count
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    def delete(self, request):
        """Delete a lead source"""
        try:
            data = json.loads(request.body)
            source_id = data.get('id')
            
            if not source_id:
                return JsonResponse({'success': False, 'error': 'Source ID is required'}, status=400)
            
            source = get_object_or_404(LeadSource, id=source_id)
            
            # Check if source has leads
            lead_count = source.leads.count()
            if lead_count > 0:
                return JsonResponse({
                    'success': False, 
                    'error': f'Cannot delete source with {lead_count} leads. Deactivate it instead.'
                }, status=400)
            
            source.delete()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class RequiredDocumentAPIView(LoginRequiredMixin, CRMAccessMixin, View):
    """
    API endpoint for CRUD operations on required document configurations.
    """
    
    def post(self, request):
        """Create or enable a required document config"""
        try:
            data = json.loads(request.body)
            document_type = data.get('document_type', '').strip()
            description = data.get('description', '').strip()
            is_required = data.get('is_required', True)
            order = data.get('order', 0)
            
            if not document_type:
                return JsonResponse({'success': False, 'error': 'Document type is required'}, status=400)
            
            # Check if already exists
            config, created = RequiredDocumentConfig.objects.get_or_create(
                document_type=document_type,
                defaults={
                    'description': description,
                    'is_required': is_required,
                    'order': order
                }
            )
            
            if not created:
                # Update existing
                config.description = description
                config.is_required = is_required
                config.order = order
                config.save()
            
            # Get display name
            display_name = dict(RequiredDocumentConfig.DOCUMENT_TYPES).get(document_type, document_type)
            
            return JsonResponse({
                'success': True,
                'created': created,
                'config': {
                    'id': config.id,
                    'document_type': config.document_type,
                    'display_name': display_name,
                    'description': config.description,
                    'is_required': config.is_required,
                    'order': config.order
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    def put(self, request):
        """Update an existing required document config"""
        try:
            data = json.loads(request.body)
            config_id = data.get('id')
            
            if not config_id:
                return JsonResponse({'success': False, 'error': 'Config ID is required'}, status=400)
            
            config = get_object_or_404(RequiredDocumentConfig, id=config_id)
            
            if 'description' in data:
                config.description = data['description'].strip()
            if 'is_required' in data:
                config.is_required = data['is_required']
            if 'order' in data:
                config.order = data['order']
            
            config.save()
            
            display_name = dict(RequiredDocumentConfig.DOCUMENT_TYPES).get(config.document_type, config.document_type)
            
            return JsonResponse({
                'success': True,
                'config': {
                    'id': config.id,
                    'document_type': config.document_type,
                    'display_name': display_name,
                    'description': config.description,
                    'is_required': config.is_required,
                    'order': config.order
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    def delete(self, request):
        """Delete a required document config"""
        try:
            data = json.loads(request.body)
            config_id = data.get('id')
            
            if not config_id:
                return JsonResponse({'success': False, 'error': 'Config ID is required'}, status=400)
            
            config = get_object_or_404(RequiredDocumentConfig, id=config_id)
            config.delete()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class RequiredDocumentReorderView(LoginRequiredMixin, CRMAccessMixin, View):
    """
    API endpoint for reordering required document configs.
    """
    
    def post(self, request):
        """Reorder document configs"""
        try:
            data = json.loads(request.body)
            order_list = data.get('order', [])  # List of config IDs in desired order
            
            for index, config_id in enumerate(order_list):
                RequiredDocumentConfig.objects.filter(id=config_id).update(order=index)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
