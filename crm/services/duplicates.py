"""
Duplicate Detection Service

Provides functionality for:
- Detecting duplicate leads on create
- Finding potential duplicates for existing leads
- Merging duplicate leads
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class DuplicateDetectionService:
    """
    Service for detecting and managing duplicate leads.
    """
    
    @classmethod
    def find_duplicates(
        cls, 
        phone: str = None, 
        email: str = None, 
        first_name: str = None,
        last_name: str = None,
        exclude_lead_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Find potential duplicate leads based on phone, email, or name.
        Returns a list of potential duplicates with match details.
        """
        from crm.models import Lead
        
        if not phone and not email:
            return []
        
        duplicates = []
        
        # Clean phone number for comparison
        if phone:
            phone_clean = ''.join(c for c in phone if c.isdigit())
            # Check different phone formats
            phone_variants = [phone, phone_clean]
            if phone_clean.startswith('0') and len(phone_clean) >= 10:
                phone_variants.append('+27' + phone_clean[1:])  # South African format
            if phone_clean.startswith('27'):
                phone_variants.append('0' + phone_clean[2:])
        
        # Build query
        query = Q()
        
        if phone:
            for variant in phone_variants:
                query |= Q(phone__icontains=variant[-9:])  # Last 9 digits
                query |= Q(phone_secondary__icontains=variant[-9:])
                query |= Q(whatsapp_number__icontains=variant[-9:])
        
        if email:
            query |= Q(email__iexact=email)
        
        if not query:
            return []
        
        # Find matches
        leads = Lead.objects.filter(query)
        
        if exclude_lead_id:
            leads = leads.exclude(pk=exclude_lead_id)
        
        leads = leads.select_related('source', 'assigned_to')[:10]
        
        for lead in leads:
            match_reasons = []
            match_score = 0
            
            # Check phone match
            if phone:
                phone_clean = ''.join(c for c in phone if c.isdigit())
                lead_phone_clean = ''.join(c for c in (lead.phone or '') if c.isdigit())
                
                if phone_clean[-9:] == lead_phone_clean[-9:]:
                    match_reasons.append('Phone number matches')
                    match_score += 50
            
            # Check email match
            if email and lead.email and email.lower() == lead.email.lower():
                match_reasons.append('Email matches')
                match_score += 40
            
            # Check name similarity
            if first_name and last_name:
                if (first_name.lower() == (lead.first_name or '').lower() and 
                    last_name.lower() == (lead.last_name or '').lower()):
                    match_reasons.append('Name matches exactly')
                    match_score += 30
                elif first_name.lower() == (lead.first_name or '').lower():
                    match_reasons.append('First name matches')
                    match_score += 10
            
            duplicates.append({
                'lead': lead,
                'lead_id': lead.pk,
                'name': lead.get_full_name(),
                'phone': lead.phone,
                'email': lead.email,
                'status': lead.get_status_display(),
                'source': lead.source.name if lead.source else None,
                'assigned_to': lead.assigned_to.get_full_name() if lead.assigned_to else None,
                'created_at': lead.created_at,
                'match_reasons': match_reasons,
                'match_score': match_score,
            })
        
        # Sort by match score
        duplicates.sort(key=lambda x: x['match_score'], reverse=True)
        
        return duplicates
    
    @classmethod
    def check_duplicate_on_create(
        cls, 
        phone: str, 
        email: str = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Quick check for duplicates when creating a new lead.
        Returns (is_duplicate, best_match).
        """
        duplicates = cls.find_duplicates(phone=phone, email=email)
        
        if duplicates:
            # Return the best match
            best_match = duplicates[0]
            if best_match['match_score'] >= 40:
                return True, best_match
        
        return False, None
    
    @classmethod
    def merge_leads(
        cls, 
        primary_lead_id: int, 
        duplicate_lead_ids: List[int],
        user = None
    ) -> Dict[str, Any]:
        """
        Merge duplicate leads into a primary lead.
        
        Merges:
        - Activities (transferred to primary)
        - Documents (transferred to primary)
        - Notes combined
        - Keeps most complete profile data
        
        The duplicate leads are marked as merged (status = MERGED).
        """
        from crm.models import Lead, LeadActivity, LeadDocument
        from django.db import transaction
        
        with transaction.atomic():
            primary = Lead.objects.get(pk=primary_lead_id)
            duplicates = Lead.objects.filter(pk__in=duplicate_lead_ids)
            
            merged_count = 0
            activities_moved = 0
            documents_moved = 0
            
            for dup in duplicates:
                # Skip if same as primary
                if dup.pk == primary.pk:
                    continue
                
                # Merge profile data (fill in blanks on primary)
                if not primary.email and dup.email:
                    primary.email = dup.email
                if not primary.phone_secondary and dup.phone_secondary:
                    primary.phone_secondary = dup.phone_secondary
                if not primary.whatsapp_number and dup.whatsapp_number:
                    primary.whatsapp_number = dup.whatsapp_number
                if not primary.date_of_birth and dup.date_of_birth:
                    primary.date_of_birth = dup.date_of_birth
                if not primary.parent_name and dup.parent_name:
                    primary.parent_name = dup.parent_name
                if not primary.parent_phone and dup.parent_phone:
                    primary.parent_phone = dup.parent_phone
                if not primary.parent_email and dup.parent_email:
                    primary.parent_email = dup.parent_email
                if not primary.school_name and dup.school_name:
                    primary.school_name = dup.school_name
                if not primary.qualification_interest and dup.qualification_interest:
                    primary.qualification_interest = dup.qualification_interest
                
                # Combine notes
                if dup.notes:
                    separator = '\n---\n' if primary.notes else ''
                    primary.notes = f"{primary.notes or ''}{separator}[Merged from duplicate #{dup.pk}]: {dup.notes}"
                
                # Move activities to primary
                activities = dup.activities.all()
                for activity in activities:
                    activity.lead = primary
                    activity.description = f"[From merged lead #{dup.pk}] {activity.description}"
                    activity.save()
                    activities_moved += 1
                
                # Move documents to primary
                documents = dup.documents.all()
                for doc in documents:
                    doc.lead = primary
                    doc.save()
                    documents_moved += 1
                
                # Log the merge
                LeadActivity.objects.create(
                    lead=primary,
                    activity_type='NOTE',
                    description=f'Merged duplicate lead #{dup.pk} ({dup.get_full_name()}) into this lead',
                    created_by=user
                )
                
                # Mark duplicate as merged
                dup.status = 'MERGED'
                dup.merged_into = primary
                dup.merged_at = timezone.now()
                dup.merged_by = user
                dup.notes = f"[MERGED INTO LEAD #{primary.pk}]\n{dup.notes or ''}"
                dup.save()
                
                merged_count += 1
            
            # Save primary lead with merged data
            primary.save()
            
            return {
                'success': True,
                'primary_lead_id': primary.pk,
                'merged_count': merged_count,
                'activities_moved': activities_moved,
                'documents_moved': documents_moved
            }
    
    @classmethod
    def find_all_potential_duplicates(cls, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Scan the database for potential duplicate leads.
        Returns groups of potential duplicates.
        """
        from crm.models import Lead
        from collections import defaultdict
        
        # Group by phone suffix (last 9 digits)
        phone_groups = defaultdict(list)
        email_groups = defaultdict(list)
        
        leads = Lead.objects.exclude(
            status__in=['ENROLLED', 'LOST', 'MERGED']
        ).values('id', 'first_name', 'last_name', 'phone', 'email', 'status')[:5000]
        
        for lead in leads:
            if lead['phone']:
                phone_suffix = ''.join(c for c in lead['phone'] if c.isdigit())[-9:]
                if phone_suffix:
                    phone_groups[phone_suffix].append(lead)
            
            if lead['email']:
                email_groups[lead['email'].lower()].append(lead)
        
        # Find groups with duplicates
        duplicate_groups = []
        seen_leads = set()
        
        # Check phone duplicates
        for phone_suffix, group in phone_groups.items():
            if len(group) > 1:
                lead_ids = [l['id'] for l in group]
                if not any(lid in seen_leads for lid in lead_ids):
                    duplicate_groups.append({
                        'type': 'phone',
                        'match_value': phone_suffix,
                        'leads': group,
                        'count': len(group)
                    })
                    seen_leads.update(lead_ids)
        
        # Check email duplicates
        for email, group in email_groups.items():
            if len(group) > 1:
                lead_ids = [l['id'] for l in group]
                if not any(lid in seen_leads for lid in lead_ids):
                    duplicate_groups.append({
                        'type': 'email',
                        'match_value': email,
                        'leads': group,
                        'count': len(group)
                    })
                    seen_leads.update(lead_ids)
        
        # Sort by count
        duplicate_groups.sort(key=lambda x: x['count'], reverse=True)
        
        return duplicate_groups[:limit]
