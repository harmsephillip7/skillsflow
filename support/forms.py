from django import forms
from .models import SupportTicket, TicketMessage, ArticleFeedback


class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["subject", "category", "priority", "description"]
        widgets = {
            "subject": forms.TextInput(attrs={"class": "w-full px-4 py-2 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"}),
            "category": forms.Select(attrs={"class": "w-full px-4 py-2 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"}),
            "priority": forms.Select(attrs={"class": "w-full px-4 py-2 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"}),
            "description": forms.Textarea(attrs={"rows": 6, "class": "w-full px-4 py-2 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"}),
        }


class TicketMessageForm(forms.ModelForm):
    class Meta:
        model = TicketMessage
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4, "placeholder": "Write a reply…", "class": "w-full px-4 py-2 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"}),
        }


class ArticleFeedbackForm(forms.ModelForm):
    class Meta:
        model = ArticleFeedback
        fields = ["is_helpful", "comment"]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional: tell us what was missing…", "class": "w-full px-4 py-2 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"}),
        }
