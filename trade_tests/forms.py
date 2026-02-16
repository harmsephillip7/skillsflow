"""
Trade Tests Forms
"""
from django import forms
from django.utils import timezone

from .models import (
    Trade,
    TradeTestCentre,
    TradeTestCentreCapability,
    TradeTestApplication,
    ARPLToolkitAssessment,
    TradeTestBooking,
    TradeTestResult,
)


class TradeTestApplicationForm(forms.ModelForm):
    """Form for creating/editing trade test applications"""
    
    class Meta:
        model = TradeTestApplication
        fields = [
            'candidate_source', 'learner', 'enrollment', 'trade', 'centre',
            'previous_training_provider', 'years_experience', 'notes'
        ]
        widgets = {
            'candidate_source': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'handleSourceChange(this.value)'
            }),
            'learner': forms.Select(attrs={'class': 'form-select select2'}),
            'enrollment': forms.Select(attrs={'class': 'form-select select2'}),
            'trade': forms.Select(attrs={'class': 'form-select select2'}),
            'centre': forms.Select(attrs={'class': 'form-select select2'}),
            'previous_training_provider': forms.TextInput(attrs={'class': 'form-input'}),
            'years_experience': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make enrollment optional
        self.fields['enrollment'].required = False
        
        # External candidate fields optional by default
        self.fields['previous_training_provider'].required = False
        self.fields['years_experience'].required = False
        
        # Filter active centres
        self.fields['centre'].queryset = TradeTestCentre.objects.filter(is_active=True)
        
        # Filter active trades
        self.fields['trade'].queryset = Trade.objects.filter(is_active=True)
    
    def clean(self):
        cleaned_data = super().clean()
        candidate_source = cleaned_data.get('candidate_source')
        enrollment = cleaned_data.get('enrollment')
        
        # Internal candidates must have enrollment
        if candidate_source == 'INTERNAL' and not enrollment:
            self.add_error('enrollment', 'Enrollment is required for internal candidates')
        
        return cleaned_data


class InternalApplicationForm(forms.ModelForm):
    """Simplified form for internal learner applications"""
    
    enrollment = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select select2'}),
        help_text='Select the enrollment to apply for trade test'
    )
    
    class Meta:
        model = TradeTestApplication
        fields = ['enrollment', 'centre', 'notes']
        widgets = {
            'centre': forms.Select(attrs={'class': 'form-select select2'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active centres
        self.fields['centre'].queryset = TradeTestCentre.objects.filter(is_active=True)
        
        # Will be set in view based on user/campus
        self.fields['enrollment'].queryset = None


class ExternalApplicationForm(forms.ModelForm):
    """Form for external/ARPL candidates"""
    
    class Meta:
        model = TradeTestApplication
        fields = [
            'learner', 'trade', 'centre',
            'previous_training_provider', 'years_experience', 'notes'
        ]
        widgets = {
            'learner': forms.Select(attrs={'class': 'form-select select2'}),
            'trade': forms.Select(attrs={'class': 'form-select select2'}),
            'centre': forms.Select(attrs={'class': 'form-select select2'}),
            'previous_training_provider': forms.TextInput(attrs={'class': 'form-input'}),
            'years_experience': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['centre'].queryset = TradeTestCentre.objects.filter(is_active=True)
        self.fields['trade'].queryset = Trade.objects.filter(is_active=True)


class ScheduleBookingForm(forms.ModelForm):
    """Form for entering NAMB schedule date"""
    
    class Meta:
        model = TradeTestBooking
        fields = ['scheduled_date', 'scheduled_time', 'centre', 'namb_reference']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'scheduled_time': forms.TimeInput(attrs={
                'class': 'form-input',
                'type': 'time'
            }),
            'centre': forms.Select(attrs={'class': 'form-select select2'}),
            'namb_reference': forms.TextInput(attrs={'class': 'form-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['centre'].queryset = TradeTestCentre.objects.filter(is_active=True)
        self.fields['centre'].required = False  # Can override, defaults to application centre


class BulkScheduleForm(forms.Form):
    """Form for bulk schedule entry"""
    
    bookings = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    scheduled_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )
    scheduled_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
        required=False
    )
    namb_reference = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    
    def __init__(self, *args, pending_bookings=None, **kwargs):
        super().__init__(*args, **kwargs)
        if pending_bookings:
            self.fields['bookings'].choices = [
                (b.pk, f"{b.learner} - {b.trade.name} (Attempt {b.attempt_number})")
                for b in pending_bookings
            ]


class TradeTestResultForm(forms.ModelForm):
    """Form for recording trade test results"""
    
    class Meta:
        model = TradeTestResult
        fields = [
            'section', 'result', 'score', 'test_date', 'result_date',
            'report_reference', 'report_date', 'report_file',
            'assessor_name', 'assessor_registration', 'assessor_comments'
        ]
        widgets = {
            'section': forms.Select(attrs={'class': 'form-select'}),
            'result': forms.Select(attrs={'class': 'form-select'}),
            'score': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': 0,
                'max': 100,
                'step': '0.01'
            }),
            'test_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'result_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'report_reference': forms.TextInput(attrs={'class': 'form-input'}),
            'report_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'report_file': forms.FileInput(attrs={'class': 'form-input'}),
            'assessor_name': forms.TextInput(attrs={'class': 'form-input'}),
            'assessor_registration': forms.TextInput(attrs={'class': 'form-input'}),
            'assessor_comments': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.booking = kwargs.pop('booking', None)
        super().__init__(*args, **kwargs)
        
        # Set default test_date to booking's scheduled_date
        if self.booking and self.booking.scheduled_date:
            self.fields['test_date'].initial = self.booking.scheduled_date


class ARPLAssessmentForm(forms.ModelForm):
    """Form for ARPL toolkit assessment"""
    
    class Meta:
        model = ARPLToolkitAssessment
        fields = [
            'scheduled_date', 'scheduled_time', 'centre',
            'status', 'result', 'result_date',
            'assessor_notes', 'training_recommendations'
        ]
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'scheduled_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'centre': forms.Select(attrs={'class': 'form-select select2'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'result': forms.Select(attrs={'class': 'form-select'}),
            'result_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'assessor_notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'training_recommendations': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['centre'].queryset = TradeTestCentre.objects.filter(is_active=True)


class TradeTestCentreForm(forms.ModelForm):
    """Form for trade test centre management"""
    
    class Meta:
        model = TradeTestCentre
        fields = [
            'name', 'code', 'address', 'city', 'province', 'postal_code',
            'latitude', 'longitude',
            'contact_person', 'contact_email', 'contact_phone',
            'accreditation_number', 'accreditation_expiry',
            'max_daily_capacity', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'code': forms.TextInput(attrs={'class': 'form-input'}),
            'address': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'form-input'}),
            'province': forms.Select(attrs={'class': 'form-select'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-input'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.000001'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-input'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-input'}),
            'accreditation_number': forms.TextInput(attrs={'class': 'form-input'}),
            'accreditation_expiry': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'max_daily_capacity': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
