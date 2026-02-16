"""
Forms for LMS Sync app
"""
from django import forms
from .models import MoodleInstance, GradeThreshold


class MoodleInstanceForm(forms.ModelForm):
    """Form for Moodle instance setup"""
    
    class Meta:
        model = MoodleInstance
        fields = [
            'brand', 'name', 'base_url', 'ws_token',
            'sync_enabled'
        ]
        widgets = {
            'brand': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Main Moodle Instance'
            }),
            'base_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://moodle.yourcompany.com'
            }),
            'ws_token': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Paste your web services token here'
            }),
            'sync_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_sync_enabled'
            }),
        }


class GradeThresholdForm(forms.ModelForm):
    """Form for grade threshold configuration"""
    
    class Meta:
        model = GradeThreshold
        fields = ['pass_percentage']
        widgets = {
            'pass_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '0.1',
                'placeholder': '50.0'
            }),
        }
