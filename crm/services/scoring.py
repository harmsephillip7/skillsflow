"""
Lead Scoring Service

Automatically calculates and updates lead engagement scores based on:
- Activity frequency and recency
- Response times
- Quote views and interactions
- Communication engagement
- Document submission status
"""
import logging
from typing import Dict, Any
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta

logger = logging.getLogger(__name__)


class LeadScoringService:
    """
    Service for calculating lead engagement scores.
    
    Scoring factors:
    - Base score based on lead type and status
    - Activity points (calls, emails, meetings)
    - Recency boost (more recent = higher score)
    - Response time points
    - Quote engagement points
    - Document submission points
    """
    
    # Scoring weights (configurable)
    WEIGHTS = {
        # Activity types
        'CALL': 10,
        'EMAIL': 5,
        'WHATSAPP': 8,
        'MEETING': 15,
        'NOTE': 2,
        'QUOTE_SENT': 10,
        'QUOTE_VIEWED': 20,
        'DOCUMENT_SUBMITTED': 15,
        'STATUS_CHANGE': 5,
        
        # Time-based modifiers
        'RECENCY_7_DAYS': 1.5,      # Activity in last 7 days
        'RECENCY_14_DAYS': 1.2,     # Activity in last 14 days
        'RECENCY_30_DAYS': 1.0,     # Activity in last 30 days
        'RECENCY_OLDER': 0.5,       # Older activity
        
        # Status modifiers
        'STATUS_NEW': 0.8,
        'STATUS_CONTACTED': 1.0,
        'STATUS_QUALIFIED': 1.2,
        'STATUS_PROPOSAL': 1.3,
        'STATUS_NEGOTIATION': 1.4,
        
        # Engagement indicators
        'HAS_EMAIL': 5,
        'HAS_WHATSAPP': 8,
        'HAS_QUALIFICATION_INTEREST': 10,
        'HAS_QUOTE': 15,
        'HAS_DOCUMENTS': 10,
        
        # Negative factors
        'NO_RESPONSE_7_DAYS': -10,
        'NO_RESPONSE_14_DAYS': -20,
        'UNSUBSCRIBED': -50,
    }
    
    @classmethod
    def calculate_engagement_score(cls, lead) -> int:
        """
        Calculate the overall engagement score for a lead.
        Returns a score from 0-100.
        """
        from crm.models import LeadActivity, LeadDocument, Quote
        
        score = 0
        now = timezone.now()
        
        # 1. Base score from profile completeness
        score += cls._calculate_profile_score(lead)
        
        # 2. Activity score
        score += cls._calculate_activity_score(lead, now)
        
        # 3. Quote engagement score
        score += cls._calculate_quote_score(lead)
        
        # 4. Document submission score
        score += cls._calculate_document_score(lead)
        
        # 5. Apply status modifier
        status_key = f'STATUS_{lead.status}'
        status_modifier = cls.WEIGHTS.get(status_key, 1.0)
        score = int(score * status_modifier)
        
        # 6. Apply negative factors
        score += cls._calculate_negative_factors(lead, now)
        
        # Normalize to 0-100 range
        score = max(0, min(100, score))
        
        return score
    
    @classmethod
    def _calculate_profile_score(cls, lead) -> int:
        """Score based on profile completeness."""
        score = 0
        
        if lead.email:
            score += cls.WEIGHTS['HAS_EMAIL']
        if lead.whatsapp_number:
            score += cls.WEIGHTS['HAS_WHATSAPP']
        if lead.qualification_interest:
            score += cls.WEIGHTS['HAS_QUALIFICATION_INTEREST']
        
        return score
    
    @classmethod
    def _calculate_activity_score(cls, lead, now) -> int:
        """Score based on activity history."""
        from crm.models import LeadActivity
        
        score = 0
        
        # Get activities grouped by recency
        seven_days_ago = now - timedelta(days=7)
        fourteen_days_ago = now - timedelta(days=14)
        thirty_days_ago = now - timedelta(days=30)
        
        activities = lead.activities.values('activity_type', 'created_at')
        
        for activity in activities:
            activity_type = activity['activity_type']
            created_at = activity['created_at']
            
            # Base points for activity type
            base_points = cls.WEIGHTS.get(activity_type, 2)
            
            # Apply recency modifier
            if created_at >= seven_days_ago:
                modifier = cls.WEIGHTS['RECENCY_7_DAYS']
            elif created_at >= fourteen_days_ago:
                modifier = cls.WEIGHTS['RECENCY_14_DAYS']
            elif created_at >= thirty_days_ago:
                modifier = cls.WEIGHTS['RECENCY_30_DAYS']
            else:
                modifier = cls.WEIGHTS['RECENCY_OLDER']
            
            score += int(base_points * modifier)
        
        return score
    
    @classmethod
    def _calculate_quote_score(cls, lead) -> int:
        """Score based on quote engagement."""
        score = 0
        
        # Check for quotes
        quotes = getattr(lead, 'quotes', None)
        if quotes:
            quote_count = quotes.count()
            if quote_count > 0:
                score += cls.WEIGHTS['HAS_QUOTE']
                
                # Check for viewed quotes
                viewed_quotes = quotes.filter(viewed_at__isnull=False).count()
                score += viewed_quotes * cls.WEIGHTS['QUOTE_VIEWED']
        
        return score
    
    @classmethod
    def _calculate_document_score(cls, lead) -> int:
        """Score based on document submissions."""
        score = 0
        
        # Check for submitted documents
        documents = getattr(lead, 'documents', None)
        if documents:
            doc_count = documents.filter(status='UPLOADED').count()
            if doc_count > 0:
                score += cls.WEIGHTS['HAS_DOCUMENTS']
                score += doc_count * 5  # 5 points per document
        
        return score
    
    @classmethod
    def _calculate_negative_factors(cls, lead, now) -> int:
        """Calculate negative score factors."""
        from crm.models import LeadActivity
        
        score = 0
        
        # Check for unsubscribed
        if lead.unsubscribed:
            score += cls.WEIGHTS['UNSUBSCRIBED']
            return score
        
        # Check for lack of response
        last_activity = lead.activities.filter(
            activity_type__in=['CALL', 'EMAIL', 'WHATSAPP', 'MEETING']
        ).order_by('-created_at').first()
        
        if last_activity:
            days_since = (now - last_activity.created_at).days
            if days_since > 14:
                score += cls.WEIGHTS['NO_RESPONSE_14_DAYS']
            elif days_since > 7:
                score += cls.WEIGHTS['NO_RESPONSE_7_DAYS']
        else:
            # No activity at all
            days_since_created = (now - lead.created_at).days
            if days_since_created > 14:
                score += cls.WEIGHTS['NO_RESPONSE_14_DAYS']
            elif days_since_created > 7:
                score += cls.WEIGHTS['NO_RESPONSE_7_DAYS']
        
        return score
    
    @classmethod
    def get_score_breakdown(cls, lead) -> Dict[str, Any]:
        """
        Get a detailed breakdown of the lead's score components.
        Useful for UI display and debugging.
        """
        now = timezone.now()
        
        profile_score = cls._calculate_profile_score(lead)
        activity_score = cls._calculate_activity_score(lead, now)
        quote_score = cls._calculate_quote_score(lead)
        document_score = cls._calculate_document_score(lead)
        negative_score = cls._calculate_negative_factors(lead, now)
        
        status_key = f'STATUS_{lead.status}'
        status_modifier = cls.WEIGHTS.get(status_key, 1.0)
        
        raw_score = profile_score + activity_score + quote_score + document_score
        modified_score = int(raw_score * status_modifier)
        final_score = max(0, min(100, modified_score + negative_score))
        
        return {
            'final_score': final_score,
            'breakdown': {
                'profile': profile_score,
                'activity': activity_score,
                'quotes': quote_score,
                'documents': document_score,
                'negative': negative_score,
            },
            'status_modifier': status_modifier,
            'raw_score': raw_score,
            'modified_score': modified_score,
            'engagement_level': cls._get_engagement_level(final_score)
        }
    
    @classmethod
    def _get_engagement_level(cls, score: int) -> str:
        """Categorize the engagement score."""
        if score >= 80:
            return 'HOT'
        elif score >= 60:
            return 'WARM'
        elif score >= 40:
            return 'COOL'
        else:
            return 'COLD'
    
    @classmethod
    def update_lead_score(cls, lead, save: bool = True) -> int:
        """
        Calculate and optionally save the lead's engagement score.
        """
        score = cls.calculate_engagement_score(lead)
        
        if save and lead.engagement_score != score:
            lead.engagement_score = score
            lead.save(update_fields=['engagement_score', 'updated_at'])
        
        return score
