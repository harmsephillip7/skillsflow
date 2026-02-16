"""
Pipeline Service

Handles stage transitions, blueprint execution, and pipeline management.
"""
from typing import Optional, List, Dict, Any
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, F
from datetime import timedelta

from crm.models import (
    Lead, LeadActivity, Pipeline, PipelineStage, StageBlueprint,
    CommunicationCycle, LeadEngagement, AgentNotification
)
from core.models import User


class PipelineService:
    """
    Service for managing lead pipeline transitions and stage blueprints.
    """
    
    @classmethod
    def assign_pipeline(cls, lead: Lead, pipeline: Pipeline = None, user: User = None) -> Pipeline:
        """
        Assign a lead to a pipeline based on their learner type.
        If no pipeline specified, auto-select the default pipeline for the lead type.
        """
        if not pipeline:
            # Map lead_type to pipeline learner_type
            type_mapping = {
                'SCHOOL_LEAVER': cls._get_school_leaver_pipeline_type(lead),
                'ADULT': 'ADULT',
                'CORPORATE': 'CORPORATE',
                'REFERRAL': 'REFERRAL',
            }
            pipeline_type = type_mapping.get(lead.lead_type, 'ADULT')
            
            # Find default pipeline for this type in the lead's campus
            pipeline = Pipeline.objects.filter(
                campus=lead.campus,
                learner_type=pipeline_type,
                is_default=True,
                is_active=True
            ).first()
            
            if not pipeline:
                # Fallback to any active pipeline for this type
                pipeline = Pipeline.objects.filter(
                    campus=lead.campus,
                    learner_type=pipeline_type,
                    is_active=True
                ).first()
        
        if pipeline:
            lead.pipeline = pipeline
            
            # Set entry stage
            entry_stage = pipeline.stages.filter(is_entry_stage=True).first()
            if not entry_stage:
                entry_stage = pipeline.stages.order_by('order').first()
            
            if entry_stage:
                lead.current_stage = entry_stage
                lead.stage_entered_at = timezone.now()
            
            lead.save()
            
            # Log activity
            LeadActivity.objects.create(
                lead=lead,
                activity_type='STATUS_CHANGE',
                description=f'Assigned to pipeline: {pipeline.name}',
                is_automated=True,
                automation_source='pipeline_service',
                created_by=user
            )
            
            # Execute entry stage blueprint
            if entry_stage:
                cls.execute_stage_blueprint(lead, entry_stage, user)
        
        return pipeline
    
    @classmethod
    def _get_school_leaver_pipeline_type(cls, lead: Lead) -> str:
        """
        Determine which school leaver pipeline type based on expected matric year.
        """
        current_year = timezone.now().year
        
        if lead.expected_matric_year:
            years_until_matric = lead.expected_matric_year - current_year
            if years_until_matric <= 1:
                return 'SCHOOL_LEAVER_READY'
            else:
                return 'SCHOOL_LEAVER_FUTURE'
        
        # Check grade
        if lead.grade:
            grade_lower = lead.grade.lower()
            if '12' in grade_lower or 'matric' in grade_lower:
                return 'SCHOOL_LEAVER_READY'
            elif any(g in grade_lower for g in ['9', '10', '11']):
                return 'SCHOOL_LEAVER_FUTURE'
        
        # Default to ready
        return 'SCHOOL_LEAVER_READY'
    
    @classmethod
    @transaction.atomic
    def move_to_stage(
        cls, 
        lead: Lead, 
        new_stage: PipelineStage, 
        user: User = None,
        notes: str = ''
    ) -> Dict[str, Any]:
        """
        Move a lead to a new pipeline stage.
        Returns result with status and any triggered actions.
        """
        old_stage = lead.current_stage
        result = {
            'success': True,
            'old_stage': old_stage,
            'new_stage': new_stage,
            'actions_triggered': []
        }
        
        # Validate the stage belongs to the same pipeline
        if lead.pipeline and new_stage.pipeline_id != lead.pipeline_id:
            result['success'] = False
            result['error'] = 'Stage does not belong to lead pipeline'
            return result
        
        # Update lead
        lead.current_stage = new_stage
        lead.stage_entered_at = timezone.now()
        
        # Map stage to legacy status
        if new_stage.is_entry_stage:
            lead.status = 'NEW'
        elif new_stage.is_won_stage:
            lead.status = 'ENROLLED'
            lead.converted_at = timezone.now()
        elif new_stage.is_lost_stage:
            lead.status = 'LOST'
        elif new_stage.is_nurture_stage:
            lead.status = 'CONTACTED'
        else:
            # Map based on stage code
            status_mapping = {
                'CONTACTED': 'CONTACTED',
                'QUALIFIED': 'QUALIFIED', 
                'PROPOSAL': 'PROPOSAL',
                'NEGOTIATION': 'NEGOTIATION',
                'REGISTERED': 'REGISTERED',
            }
            for code, status in status_mapping.items():
                if code.lower() in new_stage.code.lower():
                    lead.status = status
                    break
        
        lead.save()
        
        # Log activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type='STAGE_CHANGE',
            description=f'Stage changed: {old_stage.name if old_stage else "None"} → {new_stage.name}' + (f' - {notes}' if notes else ''),
            from_status=old_stage.code if old_stage else '',
            to_status=new_stage.code,
            created_by=user
        )
        result['actions_triggered'].append('activity_logged')
        
        # Execute stage blueprint
        blueprint_result = cls.execute_stage_blueprint(lead, new_stage, user)
        result['actions_triggered'].extend(blueprint_result.get('actions', []))
        
        # Handle Pre-Approval stage special automation
        if new_stage.code == 'PRE_APPROVED':
            preapproval_result = cls.handle_pre_approval(lead, user)
            result['actions_triggered'].extend(preapproval_result.get('actions', []))
            result['pre_approval_letter'] = preapproval_result.get('letter')
        
        # Handle Application stage - create Application record
        if new_stage.code == 'APPLICATION':
            application_result = cls.handle_application_stage(lead, user)
            result['actions_triggered'].extend(application_result.get('actions', []))
            result['application'] = application_result.get('application')
        
        # Create agent notification if needed
        if lead.assigned_to:
            AgentNotification.objects.create(
                agent=lead.assigned_to,
                notification_type='STAGE_CHANGE',
                title=f'Lead moved to {new_stage.name}',
                message=f'{lead.get_full_name()} moved from {old_stage.name if old_stage else "entry"} to {new_stage.name}',
                lead=lead,
                action_url=f'/crm/leads/{lead.pk}/',
                action_label='View Lead'
            )
            result['actions_triggered'].append('agent_notified')
        
        return result
    
    @classmethod
    def handle_pre_approval(cls, lead: Lead, user: User = None) -> Dict[str, Any]:
        """
        Handle pre-approval stage:
        1. Create PreApprovalLetter
        2. Generate PDF
        3. Send via preferred channel (WhatsApp/Email/SMS)
        4. If minor, also notify parent/guardian
        5. Notify agent
        6. Return next_step_required for UI to show choice modal
        """
        from crm.services.pre_approval import PreApprovalService
        
        result = {
            'actions': [],
            'next_step_required': True,  # Always show choice modal after pre-approval
            'is_minor': getattr(lead, 'is_minor', False),
        }
        
        # Must have a qualification interest
        if not lead.qualification_interest:
            result['error'] = 'No qualification interest set'
            return result
        
        try:
            # Create pre-approval letter using the service
            letter = PreApprovalService.create_pre_approval_letter(
                lead=lead,
                qualification=lead.qualification_interest,
                campus=lead.campus,
                entry_requirements_notes=f'Pre-approved by {user.get_full_name() if user else "system"}',
                confirmed_by=user,
                valid_days=30  # 30-day validity per user decision
            )
            result['letter'] = letter
            result['letter_number'] = letter.letter_number
            result['letter_id'] = str(letter.id)
            result['portal_url'] = letter.get_portal_url()
            result['actions'].append('pre_approval_letter_created')
            
            # Log activity
            LeadActivity.objects.create(
                lead=lead,
                activity_type='STATUS_CHANGE',
                description=f'Pre-approval letter {letter.letter_number} created for {lead.qualification_interest.name}',
                is_automated=True,
                automation_source='pipeline_service',
                created_by=user
            )
            
            # Generate PDF and send via preferred channel to learner
            send_result = PreApprovalService.send_letter(letter)
            
            if send_result.get('success'):
                result['actions'].append('pre_approval_letter_sent')
                result['sent_via'] = send_result.get('channel')
            else:
                # Log the error but don't fail the stage move
                result['send_error'] = send_result.get('error')
                result['actions'].append('pre_approval_send_attempted')
            
            # Handle parent notification for minors
            if lead.is_minor and (lead.parent_email or lead.parent_phone):
                parent_result = PreApprovalService.send_parent_notification(letter)
                if parent_result.get('success'):
                    result['actions'].append('parent_notified')
                    result['parent_sent_via'] = parent_result.get('channel')
                else:
                    result['parent_send_error'] = parent_result.get('error')
                    result['actions'].append('parent_notification_attempted')
            
            # Notify agent
            if lead.assigned_to:
                minor_note = " (Minor - parent also notified)" if lead.is_minor else ""
                AgentNotification.objects.create(
                    agent=lead.assigned_to,
                    notification_type='ACTION_REQUIRED',
                    title=f'Pre-approval letter {"sent" if send_result.get("success") else "created"}{minor_note}',
                    message=f'Pre-approval letter {letter.letter_number} {"sent to" if send_result.get("success") else "ready for"} {lead.get_full_name()} for {lead.qualification_interest.name}. Choose next step: Continue nurture or guide to application.',
                    lead=lead,
                    action_url=f'/crm/leads/{lead.pk}/',
                    action_label='View Lead'
                )
            
        except Exception as e:
            logger.error(f"Pre-approval error for lead {lead.pk}: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    @classmethod
    def handle_application_stage(cls, lead: Lead, user: User = None) -> Dict[str, Any]:
        """
        Handle application stage:
        1. Create Opportunity if needed
        2. Create Application record
        3. Link to pre-approval letter
        """
        from crm.models import Opportunity, Application
        
        result = {'actions': []}
        
        if not lead.qualification_interest:
            result['error'] = 'No qualification interest set'
            return result
        
        # Get or create opportunity
        opportunity, opp_created = Opportunity.objects.get_or_create(
            lead=lead,
            qualification=lead.qualification_interest,
            defaults={
                'name': f"{lead.get_full_name()} - {lead.qualification_interest.name}",
                'campus': lead.campus,
                'stage': 'COMMITTED',
                'probability': 85,
            }
        )
        if opp_created:
            result['actions'].append('opportunity_created')
        
        # Check if application already exists
        if hasattr(opportunity, 'application') and opportunity.application:
            result['application'] = opportunity.application
            return result
        
        # Create application
        application = Application.objects.create(
            opportunity=opportunity,
            status='DRAFT',
        )
        result['application'] = application
        result['actions'].append('application_created')
        
        # Link pre-approval letter if exists
        latest_letter = lead.pre_approval_letters.filter(
            qualification=lead.qualification_interest,
            status__in=['SENT', 'VIEWED']
        ).order_by('-issued_date').first()
        
        if latest_letter:
            latest_letter.application = application
            latest_letter.status = 'ACCEPTED'
            latest_letter.save()
            result['actions'].append('pre_approval_linked')
        
        # Log activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type='STATUS_CHANGE',
            description=f'Application created for {lead.qualification_interest.name}',
            is_automated=True,
            automation_source='pipeline_service',
            created_by=user
        )
        
        return result
    
    @classmethod
    def execute_stage_blueprint(
        cls, 
        lead: Lead, 
        stage: PipelineStage, 
        user: User = None
    ) -> Dict[str, Any]:
        """
        Execute the blueprint actions when a lead enters a stage.
        Creates tasks, schedules communications, etc.
        """
        result = {'actions': []}
        
        try:
            blueprint = stage.blueprint
        except StageBlueprint.DoesNotExist:
            return result
        
        # Auto-schedule communication if enabled
        if blueprint.auto_schedule_follow_up:
            from crm.services.nurture import NurtureService
            scheduled = NurtureService.schedule_next_communication(lead, stage)
            if scheduled:
                result['actions'].append('communication_scheduled')
        
        # Auto-send initial communication if enabled
        if blueprint.auto_send_initial_communication and blueprint.default_template:
            from crm.services.nurture import NurtureService
            sent = NurtureService.send_communication(lead, blueprint.default_template)
            if sent:
                result['actions'].append('initial_communication_sent')
        
        # Create auto-tasks
        if blueprint.auto_tasks:
            from core.models import Task
            for task_config in blueprint.auto_tasks:
                due_days = task_config.get('due_days', 1)
                Task.objects.create(
                    title=task_config.get('title', f'Follow up with {lead.get_full_name()}'),
                    description=task_config.get('description', ''),
                    assigned_to=lead.assigned_to,
                    due_date=timezone.now() + timedelta(days=due_days),
                    status='PENDING',
                    created_by=user
                )
            result['actions'].append(f'{len(blueprint.auto_tasks)}_tasks_created')
        
        return result
    
    @classmethod
    def get_stage_recommendations(cls, lead: Lead) -> List[Dict[str, Any]]:
        """
        Get recommended actions for a lead in their current stage.
        """
        recommendations = []
        
        if not lead.current_stage:
            return recommendations
        
        try:
            blueprint = lead.current_stage.blueprint
        except StageBlueprint.DoesNotExist:
            return recommendations
        
        # Add blueprint recommended actions
        for action in blueprint.recommended_actions or []:
            recommendations.append({
                'type': 'blueprint_action',
                'action': action.get('action', ''),
                'description': action.get('description', ''),
                'priority': action.get('priority', 'normal')
            })
        
        # Add stage-specific recommendations
        if lead.is_overdue_in_stage:
            recommendations.insert(0, {
                'type': 'overdue',
                'action': 'Follow up immediately',
                'description': f'Lead has been in {lead.current_stage.name} for {lead.days_in_stage} days (expected: {lead.current_stage.expected_duration_days})',
                'priority': 'high'
            })
        
        # Check if quote should be sent
        if 'proposal' in lead.current_stage.code.lower() and lead.qualification_interest:
            has_recent_quote = lead.quotes.filter(
                created_at__gte=timezone.now() - timedelta(days=30)
            ).exists()
            if not has_recent_quote:
                recommendations.append({
                    'type': 'quote',
                    'action': 'Send quote',
                    'description': f'No quote sent for {lead.qualification_interest.name}',
                    'priority': 'high'
                })
        
        return recommendations
    
    @classmethod
    def get_overdue_leads(cls, pipeline: Pipeline = None, agent: User = None) -> List[Lead]:
        """
        Get leads that have exceeded their expected time in current stage.
        """
        query = Lead.objects.filter(
            current_stage__isnull=False,
            stage_entered_at__isnull=False,
            nurture_active=True
        ).exclude(
            current_stage__is_won_stage=True
        ).exclude(
            current_stage__is_lost_stage=True
        )
        
        if pipeline:
            query = query.filter(pipeline=pipeline)
        
        if agent:
            query = query.filter(assigned_to=agent)
        
        # Filter for overdue leads
        overdue_leads = []
        for lead in query.select_related('current_stage'):
            if lead.is_overdue_in_stage:
                overdue_leads.append(lead)
        
        return overdue_leads
    
    @classmethod
    def get_pipeline_stats(cls, pipeline: Pipeline) -> Dict[str, Any]:
        """
        Get statistics for a pipeline.
        """
        stages = pipeline.stages.all()
        stats = {
            'total_leads': 0,
            'stages': [],
            'conversion_rate': 0,
            'avg_days_to_convert': 0
        }
        
        for stage in stages:
            lead_count = Lead.objects.filter(current_stage=stage).count()
            stats['total_leads'] += lead_count
            stats['stages'].append({
                'id': stage.pk,
                'name': stage.name,
                'code': stage.code,
                'color': stage.color,
                'lead_count': lead_count,
                'order': stage.order,
                'is_won_stage': stage.is_won_stage,
                'is_lost_stage': stage.is_lost_stage,
            })
        
        # Calculate conversion rate
        won_stage = stages.filter(is_won_stage=True).first()
        if won_stage and stats['total_leads'] > 0:
            won_count = Lead.objects.filter(current_stage=won_stage).count()
            stats['conversion_rate'] = round((won_count / stats['total_leads']) * 100, 1)
        
        return stats
    
    @classmethod
    def get_agent_dashboard_data(cls, agent: User, campus=None) -> Dict[str, Any]:
        """
        Get dashboard data for a sales agent.
        """
        from django.db.models import Count
        
        base_query = Lead.objects.filter(assigned_to=agent, nurture_active=True)
        if campus:
            base_query = base_query.filter(campus=campus)
        
        # Get leads by stage
        leads_by_stage = base_query.values(
            'current_stage__name', 'current_stage__color', 'current_stage__order'
        ).annotate(count=Count('id')).order_by('current_stage__order')
        
        # Get overdue leads
        overdue_leads = cls.get_overdue_leads(agent=agent)
        
        # Get recent engagements
        recent_engagements = LeadEngagement.objects.filter(
            lead__assigned_to=agent,
            event_timestamp__gte=timezone.now() - timedelta(days=7),
            agent_notified=False
        ).select_related('lead').order_by('-event_timestamp')[:10]
        
        # Get unread notifications
        unread_notifications = AgentNotification.objects.filter(
            agent=agent,
            is_read=False
        ).count()
        
        # Get upcoming scheduled communications
        upcoming_comms = CommunicationCycle.objects.filter(
            lead__assigned_to=agent,
            status='SCHEDULED',
            scheduled_at__lte=timezone.now() + timedelta(days=7)
        ).select_related('lead').order_by('scheduled_at')[:10]
        
        return {
            'leads_by_stage': list(leads_by_stage),
            'overdue_leads': overdue_leads,
            'overdue_count': len(overdue_leads),
            'recent_engagements': recent_engagements,
            'unread_notifications': unread_notifications,
            'upcoming_communications': upcoming_comms,
            'total_leads': base_query.count(),
        }
