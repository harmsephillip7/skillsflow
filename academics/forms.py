"""
Academics app forms
Forms for Qualifications, Modules, Learning Materials, and Personnel Registration
"""
from django import forms
from django.utils import timezone
from .models import (
    Qualification, Module, LearningMaterial, PersonnelRegistration,
    AccreditationChecklistItem, AccreditationChecklistProgress,
    QualificationCampusAccreditation
)
from learners.models import SETA
from tenants.models import Campus


class QualificationForm(forms.ModelForm):
    """Form for creating and editing qualifications"""
    
    class Meta:
        model = Qualification
        fields = [
            'saqa_id', 'title', 'short_title', 'nqf_level', 'credits',
            'qualification_type', 'seta', 'minimum_duration_months', 'maximum_duration_months',
            'registration_start', 'registration_end', 'last_enrollment_date',
            'qcto_code', 'accreditation_number', 'accreditation_start_date', 'accreditation_expiry',
            'accreditation_certificate', 'ready_in_person', 'ready_online', 'ready_hybrid',
            'delivery_notes', 'is_active'
        ]
        widgets = {
            'saqa_id': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': '123456'
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'Full qualification title'
            }),
            'short_title': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'Short name for display'
            }),
            'nqf_level': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'min': 1, 'max': 10
            }),
            'credits': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'min': 0
            }),
            'qualification_type': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'seta': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'minimum_duration_months': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'min': 1
            }),
            'maximum_duration_months': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'min': 1
            }),
            'registration_start': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
            'registration_end': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
            'last_enrollment_date': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
            'qcto_code': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'QCTO qualification code (optional)'
            }),
            'accreditation_number': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'Provider accreditation number'
            }),
            'accreditation_start_date': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
            'accreditation_expiry': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
            'accreditation_certificate': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100'
            }),
            'delivery_notes': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'rows': 3,
                'placeholder': 'Notes about delivery readiness...'
            }),
            'ready_in_person': forms.CheckboxInput(attrs={
                'class': 'rounded text-purple-600'
            }),
            'ready_online': forms.CheckboxInput(attrs={
                'class': 'rounded text-purple-600'
            }),
            'ready_hybrid': forms.CheckboxInput(attrs={
                'class': 'rounded text-purple-600'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'rounded text-purple-600'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['seta'].queryset = SETA.objects.all().order_by('name')
        self.fields['accreditation_certificate'].required = False
        
        # Group fields for template rendering
        self.fieldsets = {
            'basic': ['saqa_id', 'title', 'short_title', 'qualification_type', 'seta'],
            'classification': ['nqf_level', 'credits', 'minimum_duration_months', 'maximum_duration_months'],
            'registration': ['registration_start', 'registration_end', 'last_enrollment_date'],
            'accreditation': ['qcto_code', 'accreditation_number', 'accreditation_start_date', 'accreditation_expiry', 'accreditation_certificate'],
            'delivery': ['ready_in_person', 'ready_online', 'ready_hybrid', 'delivery_notes'],
            'status': ['is_active'],
        }
    
    def clean(self):
        cleaned_data = super().clean()
        # All date validation rules removed to allow flexible data entry
        # Users can enter dates in any order as needed for their specific requirements
        return cleaned_data


class ModuleForm(forms.ModelForm):
    """Form for creating and editing modules"""
    
    class Meta:
        model = Module
        fields = [
            'code', 'title', 'description', 'module_type', 'credits',
            'notional_hours', 'year_level', 'sequence_order', 'is_compulsory',
            'prerequisites', 'is_active'
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'MOD001'
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'Module title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'rows': 3
            }),
            'module_type': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'credits': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'min': 0
            }),
            'notional_hours': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'min': 0
            }),
            'year_level': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'sequence_order': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'min': 1
            }),
            'is_compulsory': forms.CheckboxInput(attrs={
                'class': 'rounded text-purple-600'
            }),
            'prerequisites': forms.SelectMultiple(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'size': 5
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'rounded text-purple-600'
            }),
        }
    
    def __init__(self, *args, qualification=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.qualification = qualification
        
        # Limit prerequisites to modules in the same qualification
        if qualification:
            self.fields['prerequisites'].queryset = Module.objects.filter(
                qualification=qualification,
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance.pk else None)
        else:
            self.fields['prerequisites'].queryset = Module.objects.none()


class LearningMaterialForm(forms.ModelForm):
    """Form for uploading learning materials with explicit archive option"""
    
    archive_previous = forms.BooleanField(
        required=False,
        initial=False,
        label='Archive previous version',
        help_text='Check this to archive the current version before uploading the new one',
        widget=forms.CheckboxInput(attrs={
            'class': 'rounded text-purple-600'
        })
    )
    
    version_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full rounded-lg border-gray-300',
            'rows': 2,
            'placeholder': 'What changed in this version?'
        }),
        label='Version Notes'
    )
    
    class Meta:
        model = LearningMaterial
        fields = [
            'title', 'material_type', 'description', 'file', 'external_url',
            'version', 'is_current', 'approved', 'next_review_date'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'Material title'
            }),
            'material_type': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'rows': 3
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100',
                'accept': '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.zip'
            }),
            'external_url': forms.URLInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'https://...'
            }),
            'version': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': '1.0'
            }),
            'is_current': forms.CheckboxInput(attrs={
                'class': 'rounded text-purple-600'
            }),
            'approved': forms.CheckboxInput(attrs={
                'class': 'rounded text-green-600'
            }),
            'next_review_date': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
        }
    
    def __init__(self, *args, qualification=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.qualification = qualification
        
        # Show archive option only when editing existing material
        if not self.instance.pk:
            self.fields['archive_previous'].widget = forms.HiddenInput()
            self.fields['archive_previous'].initial = False


class PersonnelRegistrationForm(forms.ModelForm):
    """Form for adding personnel registrations (stored for manual verification only)"""
    
    class Meta:
        model = PersonnelRegistration
        fields = [
            'user', 'personnel_type', 'registration_number', 'seta',
            'registration_date', 'expiry_date', 'certificate', 'is_active'
        ]
        widgets = {
            'user': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'personnel_type': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'registration_number': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'SETA registration number'
            }),
            'seta': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'registration_date': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
            'expiry_date': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
            'certificate': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'rounded text-purple-600'
            }),
        }
        help_texts = {
            'registration_number': 'This number will be stored for manual verification. We do not validate against SETA systems automatically.',
        }
    
    def __init__(self, *args, qualification=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.qualification = qualification
        
        # Pre-select SETA if qualification is provided
        if qualification and qualification.seta:
            self.fields['seta'].initial = qualification.seta


class StandalonePersonnelRegistrationForm(PersonnelRegistrationForm):
    """Form for adding personnel registrations with qualification and campus selection"""
    
    qualifications = forms.ModelMultipleChoiceField(
        queryset=Qualification.objects.all().order_by('title'),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'space-y-2'
        }),
        required=True,
        label='Qualifications',
        help_text='Select one or more qualifications this personnel is registered for'
    )
    
    campuses = forms.ModelMultipleChoiceField(
        queryset=None,  # Set in __init__
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'space-y-2'
        }),
        required=True,
        label='Campuses',
        help_text='Select the campuses where this person will be allocated to work'
    )
    
    class Meta(PersonnelRegistrationForm.Meta):
        fields = PersonnelRegistrationForm.Meta.fields + ['qualifications', 'campuses']
    
    def __init__(self, *args, **kwargs):
        # Don't pass qualification to parent
        kwargs.pop('qualification', None)
        super().__init__(*args, **kwargs)
        self.qualification = None
        
        # Set campus queryset
        from tenants.models import Campus
        self.fields['campuses'].queryset = Campus.objects.filter(is_active=True).order_by('name')


class MaterialArchiveForm(forms.Form):
    """Form for explicitly archiving a learning material"""
    
    archive_reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'w-full rounded-lg border-gray-300',
            'rows': 2,
            'placeholder': 'Reason for archiving this material...'
        }),
        label='Archive Reason'
    )
    
    confirm_archive = forms.BooleanField(
        required=True,
        label='I confirm I want to archive this material',
        widget=forms.CheckboxInput(attrs={
            'class': 'rounded text-red-600'
        })
    )


class ChecklistItemForm(forms.ModelForm):
    """Form for editing checklist items"""
    
    class Meta:
        model = AccreditationChecklistItem
        fields = ['title', 'category', 'description', 'is_required', 'sequence_order']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'rows': 2
            }),
            'is_required': forms.CheckboxInput(attrs={
                'class': 'rounded text-purple-600'
            }),
            'sequence_order': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'min': 1
            }),
        }


class CampusAccreditationForm(forms.ModelForm):
    """Form for adding/editing campus accreditations with document upload"""
    
    class Meta:
        model = QualificationCampusAccreditation
        fields = [
            'campus', 'letter_reference', 'letter_date',
            'accredited_from', 'accredited_until', 'learner_capacity',
            'accreditation_reference', 'accreditation_document',
            'status', 'notes'
        ]
        widgets = {
            'campus': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'letter_reference': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'e.g., ACC/2026/001'
            }),
            'letter_date': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
            'accredited_from': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
            'accredited_until': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'type': 'date'
            }),
            'learner_capacity': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'Max learners (optional)',
                'min': 1
            }),
            'accreditation_reference': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'placeholder': 'Additional reference (optional)'
            }),
            'accreditation_document': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border-gray-300',
                'rows': 3,
                'placeholder': 'Additional notes about this accreditation...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active campuses
        self.fields['campus'].queryset = Campus.objects.filter(is_active=True).select_related('brand').order_by('brand__name', 'name')
        # Format campus choices to show brand
        self.fields['campus'].label_from_instance = lambda obj: f"{obj.brand.name} - {obj.name}"
    
    def clean(self):
        cleaned_data = super().clean()
        accredited_from = cleaned_data.get('accredited_from')
        accredited_until = cleaned_data.get('accredited_until')
        
        if accredited_from and accredited_until:
            if accredited_until <= accredited_from:
                raise forms.ValidationError(
                    "Accreditation end date must be after the start date."
                )
        
        return cleaned_data
