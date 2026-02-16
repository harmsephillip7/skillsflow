"""
Signals for corporate app - auto-setup service infrastructure when subscriptions are activated.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import date, time

from .models import (
    ClientServiceSubscription, WSPATRServiceYear, TrainingCommittee,
    TrainingCommitteeMember, TrainingCommitteeMeeting, MeetingTemplate,
    TCMeetingAgendaItem, TCMeetingAttendance, MilestoneTask,
    # EE Models
    EEServiceYear, EEDocument
)


@receiver(post_save, sender=ClientServiceSubscription)
def setup_wspatr_service(sender, instance, created, **kwargs):
    """
    When a WSP/ATR subscription is activated, auto-create:
    - Training Committee (if not exists)
    - WSPATRServiceYear for current financial year
    - 4 quarterly meetings from templates
    """
    # Only process WSP/ATR services when status becomes ACTIVE
    if instance.service.service_type != 'WSP_ATR':
        return
    
    if instance.status != 'ACTIVE':
        return
    
    client = instance.client
    
    # 1. Create Training Committee if not exists
    # Use the subscription's campus for the committee
    committee, committee_created = TrainingCommittee.objects.get_or_create(
        client=client,
        defaults={
            'name': f'{client.company_name} Training Committee',
            'meeting_frequency': 'QUARTERLY',
            'send_calendar_invites': True,
            'is_active': True,
            'campus': instance.campus,  # Inherit campus from subscription
        }
    )
    
    # 2. Determine current financial year (May-Apr for WSP/ATR cycle)
    today = timezone.now().date()
    if today.month >= 5:
        financial_year = today.year
    else:
        financial_year = today.year - 1
    
    # 3. Create WSPATRServiceYear if not exists for this financial year
    service_year, sy_created = WSPATRServiceYear.objects.get_or_create(
        subscription=instance,
        financial_year=financial_year,
        defaults={
            'client': client,
            'campus': instance.campus,  # Inherit campus from subscription
            'status': 'DATA_COLLECTION',
            'submission_deadline': date(financial_year + 1, 4, 30),  # 30 April next year
            'seta': client.seta,
            'assigned_consultant': instance.assigned_consultant,
        }
    )
    
    # 4. Auto-schedule quarterly meetings if service year was just created
    if sy_created:
        schedule_quarterly_meetings(committee, service_year, financial_year)


def schedule_quarterly_meetings(committee, service_year, financial_year):
    """
    Create 4 quarterly meetings from templates for the financial year.
    Meetings are scheduled but invites are NOT sent automatically.
    """
    # Get meeting templates
    templates = MeetingTemplate.objects.filter(is_active=True).order_by('quarter')
    
    if not templates.exists():
        # No templates configured, skip meeting creation
        return
    
    # Default meeting time
    default_time = time(10, 0)  # 10:00 AM
    
    meeting_number = 1
    for template in templates:
        # Calculate meeting date based on suggested month
        month = template.suggested_month
        # Months 5-12 are in the financial year start year
        # Months 1-4 are in the next calendar year
        year = financial_year if month >= 5 else financial_year + 1
        
        # Default to 15th of the month (mid-month, typically a weekday)
        meeting_date = date(year, month, 15)
        
        # Adjust if 15th falls on weekend (simple adjustment)
        # Move to Monday if Saturday/Sunday
        weekday = meeting_date.weekday()
        if weekday == 5:  # Saturday
            meeting_date = date(year, month, 17)
        elif weekday == 6:  # Sunday
            meeting_date = date(year, month, 16)
        
        # Create meeting (status=SCHEDULED, not INVITES_SENT)
        meeting = TrainingCommitteeMeeting.objects.create(
            committee=committee,
            service_year=service_year,
            template=template,
            title=f"{template.name} - FY{financial_year}/{str(financial_year + 1)[-2:]}",
            meeting_number=meeting_number,
            scheduled_date=meeting_date,
            scheduled_time=default_time,
            duration_minutes=committee.default_meeting_duration_minutes,
            meeting_type='VIRTUAL',
            status='SCHEDULED',  # Scheduled but not sent
            campus=committee.campus,  # Inherit campus from committee
        )
        
        # Create agenda items from template's default_agenda JSON
        if template.default_agenda:
            for seq, agenda_data in enumerate(template.default_agenda, 1):
                TCMeetingAgendaItem.objects.create(
                    meeting=meeting,
                    sequence=seq,
                    title=agenda_data.get('title', ''),
                    description=agenda_data.get('description', ''),
                    duration_minutes=agenda_data.get('duration_minutes', 15),
                )
        
        # Create attendance records for all active committee members
        for member in committee.members.filter(is_active=True):
            TCMeetingAttendance.objects.create(
                meeting=meeting,
                member=member,
                status='INVITED',
                invite_sent=False,  # Not sent yet
            )
        
        meeting_number += 1


# =============================================================================
# EMPLOYMENT EQUITY (EE) SERVICE AUTO-SETUP
# =============================================================================

@receiver(post_save, sender=ClientServiceSubscription)
def setup_ee_service(sender, instance, created, **kwargs):
    """
    When an EE Consulting subscription is activated, auto-create:
    - EE Committee or Combined Committee (if not exists)
    - EEServiceYear for current EE reporting year
    - 4 quarterly EE meetings from templates
    - Standard EE document requirements
    """
    # Only process EE Consulting services when status becomes ACTIVE
    if instance.service.service_type != 'EE_CONSULTING':
        return
    
    if instance.status != 'ACTIVE':
        return
    
    client = instance.client
    
    # 1. Check if client already has a Training Committee
    # If so, upgrade it to combined function. Otherwise create EE Committee.
    existing_committee = TrainingCommittee.objects.filter(client=client).first()
    
    if existing_committee:
        # Check if client also has WSP/ATR subscription
        has_wspatr = ClientServiceSubscription.objects.filter(
            client=client,
            service__service_type='WSP_ATR',
            status='ACTIVE'
        ).exclude(pk=instance.pk).exists()
        
        if has_wspatr:
            # Upgrade to combined committee
            existing_committee.committee_function = 'COMBINED'
            existing_committee.is_ee_committee = True
            if not existing_committee.ee_constitution_date:
                existing_committee.ee_constitution_date = timezone.now().date()
            existing_committee.save()
            committee = existing_committee
        else:
            # Create separate EE committee
            committee, _ = TrainingCommittee.objects.get_or_create(
                client=client,
                is_ee_committee=True,
                defaults={
                    'name': f'{client.company_name} EE Committee',
                    'committee_function': 'EE_ONLY',
                    'meeting_frequency': 'QUARTERLY',
                    'ee_meeting_frequency': 'QUARTERLY',
                    'send_calendar_invites': True,
                    'is_active': True,
                    'ee_constitution_date': timezone.now().date(),
                    'campus': instance.campus,
                }
            )
    else:
        # No existing committee, create EE committee
        committee, _ = TrainingCommittee.objects.get_or_create(
            client=client,
            defaults={
                'name': f'{client.company_name} EE Committee',
                'committee_function': 'EE_ONLY',
                'is_ee_committee': True,
                'meeting_frequency': 'QUARTERLY',
                'ee_meeting_frequency': 'QUARTERLY',
                'send_calendar_invites': True,
                'is_active': True,
                'ee_constitution_date': timezone.now().date(),
                'campus': instance.campus,
            }
        )
    
    # 2. Determine current EE reporting year (Oct-Sept cycle)
    # EE year is named by the year of the September end date
    # If we're in Oct-Dec 2024, reporting year is 2025 (Oct 2024-Sept 2025)
    # If we're in Jan-Sept 2025, reporting year is 2025
    today = timezone.now().date()
    if today.month >= 10:
        reporting_year = today.year + 1
    else:
        reporting_year = today.year
    
    # 3. Create EEServiceYear if not exists for this reporting year
    ee_service_year, sy_created = EEServiceYear.objects.get_or_create(
        client=client,
        reporting_year=reporting_year,
        defaults={
            'subscription': instance,
            'campus': instance.campus,
            'status': 'NOT_STARTED',
            'period_start': date(reporting_year - 1, 10, 1),  # Oct 1 of previous year
            'period_end': date(reporting_year, 9, 30),  # Sept 30 of reporting year
            'submission_deadline': date(reporting_year, 1, 15),  # Jan 15 of reporting year
            'assigned_consultant': instance.assigned_consultant,
        }
    )
    
    # 4. Auto-schedule quarterly EE meetings if service year was just created
    if sy_created:
        schedule_ee_quarterly_meetings(committee, ee_service_year, reporting_year)
        create_ee_document_requirements(ee_service_year)


def schedule_ee_quarterly_meetings(committee, ee_service_year, reporting_year):
    """
    Create 4 quarterly EE committee meetings for the reporting year.
    EE year runs Oct-Sept, so:
    - Q1: Oct-Dec (previous calendar year)
    - Q2: Jan-Mar (reporting year)
    - Q3: Apr-Jun (reporting year)
    - Q4: Jul-Sept (reporting year)
    """
    # Get EE meeting templates
    templates = MeetingTemplate.objects.filter(
        is_active=True,
        meeting_purpose__in=['EE', 'COMBINED']
    ).order_by('pk')  # Use pk order as proxy for quarter
    
    if not templates.exists():
        # No templates configured, skip meeting creation
        return
    
    # Default meeting time
    default_time = time(10, 0)  # 10:00 AM
    
    # EE year quarterly schedule (Oct-Sept cycle)
    # reporting_year=2026 means Oct 2025 - Sept 2026
    ee_quarters = [
        # Q1: Nov (Oct 2025 - Dec 2025) -> meet in Nov 2025
        {'month': 11, 'year': reporting_year - 1, 'quarter': 1},
        # Q2: Feb (Jan 2026 - Mar 2026) -> meet in Feb 2026
        {'month': 2, 'year': reporting_year, 'quarter': 2},
        # Q3: May (Apr 2026 - Jun 2026) -> meet in May 2026
        {'month': 5, 'year': reporting_year, 'quarter': 3},
        # Q4: Aug (Jul 2026 - Sept 2026) -> meet in Aug 2026
        {'month': 8, 'year': reporting_year, 'quarter': 4},
    ]
    
    meeting_number = 1
    for i, quarter_info in enumerate(ee_quarters):
        # Get template (use quarterly templates if available, otherwise just use first 4)
        template = templates[i] if i < templates.count() else templates.first()
        
        year = quarter_info['year']
        month = quarter_info['month']
        
        # Default to 15th of the month
        meeting_date = date(year, month, 15)
        
        # Adjust if 15th falls on weekend
        weekday = meeting_date.weekday()
        if weekday == 5:  # Saturday
            meeting_date = date(year, month, 17)
        elif weekday == 6:  # Sunday
            meeting_date = date(year, month, 16)
        
        # Create meeting
        meeting = TrainingCommitteeMeeting.objects.create(
            committee=committee,
            ee_service_year=ee_service_year,
            template=template,
            title=f"EE Q{quarter_info['quarter']} Meeting - {reporting_year}",
            meeting_number=meeting_number,
            scheduled_date=meeting_date,
            scheduled_time=default_time,
            duration_minutes=committee.default_meeting_duration_minutes,
            meeting_type='VIRTUAL',
            meeting_purpose='EE',
            status='SCHEDULED',
            campus=committee.campus,
        )
        
        # Create agenda items from template
        if template and template.default_agenda:
            # Handle both text and JSON agenda formats
            if isinstance(template.default_agenda, str):
                # Text format - create single agenda item
                TCMeetingAgendaItem.objects.create(
                    meeting=meeting,
                    sequence=1,
                    title='Meeting Agenda',
                    description=template.default_agenda,
                    duration_minutes=60,
                )
            elif isinstance(template.default_agenda, list):
                # JSON format
                for seq, agenda_data in enumerate(template.default_agenda, 1):
                    TCMeetingAgendaItem.objects.create(
                        meeting=meeting,
                        sequence=seq,
                        title=agenda_data.get('title', ''),
                        description=agenda_data.get('description', ''),
                        duration_minutes=agenda_data.get('duration_minutes', 15),
                    )
        
        # Create attendance records for EE committee members
        for member in committee.members.filter(is_active=True, participates_in_ee=True):
            TCMeetingAttendance.objects.create(
                meeting=meeting,
                member=member,
                status='INVITED',
                invite_sent=False,
            )
        
        meeting_number += 1


def create_ee_document_requirements(ee_service_year):
    """
    Create standard EE document requirements for a service year.
    """
    # Standard EE documents
    ee_documents = [
        {'document_type': 'WORKFORCE_PROFILE', 'name': 'Workforce Profile (EEA2 Annexure)', 'is_required': True, 'sort_order': 1},
        {'document_type': 'EAP_DATA', 'name': 'Regional EAP Data', 'is_required': False, 'sort_order': 2},
        {'document_type': 'EE_PLAN', 'name': 'Employment Equity Plan', 'is_required': True, 'sort_order': 3},
        {'document_type': 'ANALYSIS_REPORT', 'name': 'Workforce Analysis Report', 'is_required': True, 'sort_order': 4},
        {'document_type': 'EEA2_FORM', 'name': 'EEA2 Online Report', 'is_required': True, 'sort_order': 5},
        {'document_type': 'EEA4_FORM', 'name': 'EEA4 Income Differential Statement', 'is_required': True, 'sort_order': 6},
        {'document_type': 'SUBMISSION_RECEIPT', 'name': 'DEL Submission Receipt', 'is_required': True, 'sort_order': 7},
    ]
    
    for doc_data in ee_documents:
        EEDocument.objects.get_or_create(
            ee_service_year=ee_service_year,
            document_type=doc_data['document_type'],
            defaults={
                'name': doc_data['name'],
                'is_required': doc_data['is_required'],
                'sort_order': doc_data['sort_order'],
                'status': 'PENDING',
            }
        )


# =============================================================================
# B-BBEE SERVICE AUTO-SETUP
# =============================================================================

@receiver(post_save, sender=ClientServiceSubscription)
def setup_bbbee_service(sender, instance, created, **kwargs):
    """
    When a B-BBEE Consulting subscription is activated, auto-create:
    - B-BBEE Transformation Committee (if not exists)
    - BBBEEServiceYear for current financial year
    - All B-BBEE element records
    - Standard B-BBEE document requirements
    """
    from .models import BBBEEServiceYear, BBBEEDocument
    from .services import BBBEESyncService
    
    # Only process B-BBEE Consulting services when status becomes ACTIVE
    if instance.service.service_type != 'BEE_CONSULTING':
        return
    
    if instance.status != 'ACTIVE':
        return
    
    client = instance.client
    
    # 1. Check if client already has a Training/EE Committee
    # If so, potentially upgrade to combined function that includes B-BBEE
    existing_committee = TrainingCommittee.objects.filter(client=client).first()
    
    if existing_committee:
        # Check existing service types
        has_wspatr = ClientServiceSubscription.objects.filter(
            client=client,
            service__service_type='WSP_ATR',
            status='ACTIVE'
        ).exclude(pk=instance.pk).exists()
        
        has_ee = ClientServiceSubscription.objects.filter(
            client=client,
            service__service_type='EE_CONSULTING',
            status='ACTIVE'
        ).exclude(pk=instance.pk).exists()
        
        if has_wspatr and has_ee:
            # Upgrade to ALL committee
            existing_committee.committee_function = 'ALL'
            existing_committee.is_bbbee_committee = True
            existing_committee.is_ee_committee = True
        elif has_wspatr:
            # Training + B-BBEE
            existing_committee.committee_function = 'TRAINING_BBBEE'
            existing_committee.is_bbbee_committee = True
        elif has_ee:
            # EE + B-BBEE
            existing_committee.committee_function = 'EE_BBBEE'
            existing_committee.is_bbbee_committee = True
            existing_committee.is_ee_committee = True
        else:
            # Just B-BBEE
            existing_committee.committee_function = 'BBBEE_ONLY'
            existing_committee.is_bbbee_committee = True
        
        if not existing_committee.bbbee_constitution_date:
            existing_committee.bbbee_constitution_date = timezone.now().date()
        existing_committee.save()
        committee = existing_committee
    else:
        # No existing committee, create B-BBEE committee
        committee, _ = TrainingCommittee.objects.get_or_create(
            client=client,
            defaults={
                'name': f'{client.company_name} B-BBEE Transformation Committee',
                'committee_function': 'BBBEE_ONLY',
                'is_bbbee_committee': True,
                'meeting_frequency': 'QUARTERLY',
                'send_calendar_invites': True,
                'is_active': True,
                'bbbee_constitution_date': timezone.now().date(),
                'campus': instance.campus,
            }
        )
    
    # 2. Determine current financial year
    # B-BBEE aligns with client's financial year-end
    today = timezone.now().date()
    year_end_month = getattr(client, 'financial_year_end_month', 2)  # Default Feb
    
    if today.month > year_end_month:
        financial_year = today.year + 1
    else:
        financial_year = today.year
    
    # 3. Create BBBEEServiceYear if not exists for this financial year
    bbbee_service_year, sy_created = BBBEEServiceYear.objects.get_or_create(
        subscription=instance,
        financial_year=financial_year,
        defaults={
            'client': client,
            'year_end_month': year_end_month,
            'enterprise_type': BBBEESyncService.determine_enterprise_type(
                getattr(client, 'annual_revenue', None)
            ),
            'annual_turnover': getattr(client, 'annual_revenue', None),
            'status': 'NOT_STARTED',
            'assigned_consultant': instance.assigned_consultant,
        }
    )
    
    # 4. Auto-create element records and documents if service year was just created
    if sy_created:
        # Create all element records
        BBBEESyncService.create_all_elements(bbbee_service_year)
        
        # Create document requirements
        create_bbbee_document_requirements(bbbee_service_year)
        
        # Try to auto-link to existing EE/WSP-ATR service years
        BBBEESyncService.link_service_years(
            bbbee_service_year,
            **BBBEESyncService.find_matching_service_years(bbbee_service_year)
        )


def create_bbbee_document_requirements(bbbee_service_year):
    """
    Create standard B-BBEE document requirements for a service year.
    """
    from .models import BBBEEDocument
    
    # Standard B-BBEE documents (organized by element)
    bbbee_documents = [
        # Company documents
        {'document_type': 'CIPC_REGISTRATION', 'name': 'CIPC Company Registration', 'is_required': True},
        {'document_type': 'ANNUAL_FINANCIAL_STATEMENTS', 'name': 'Annual Financial Statements', 'is_required': True},
        {'document_type': 'TAX_CLEARANCE', 'name': 'Tax Clearance Certificate', 'is_required': True},
        {'document_type': 'ORGANOGRAM', 'name': 'Company Organogram', 'is_required': False},
        # Ownership
        {'document_type': 'SHARE_CERTIFICATES', 'name': 'Share Certificates', 'is_required': True},
        {'document_type': 'SHAREHOLDERS_AGREEMENT', 'name': 'Shareholders Agreement', 'is_required': False},
        {'document_type': 'OWNERSHIP_PROOF', 'name': 'Ownership Proof Documentation', 'is_required': True},
        # Management Control
        {'document_type': 'BOARD_COMPOSITION', 'name': 'Board Composition Documentation', 'is_required': True},
        {'document_type': 'EXEC_DEMOGRAPHICS', 'name': 'Executive Demographics', 'is_required': True},
        {'document_type': 'PAYROLL_SUMMARY', 'name': 'Payroll Summary', 'is_required': False},
        # Skills Development
        {'document_type': 'SKILLS_DEV_SPEND', 'name': 'Skills Development Spend Evidence', 'is_required': True},
        {'document_type': 'LEARNERSHIPS_PROOF', 'name': 'Learnerships/Internships Proof', 'is_required': False},
        # ESD
        {'document_type': 'ESD_CONTRIBUTIONS', 'name': 'Enterprise/Supplier Development Evidence', 'is_required': True},
        {'document_type': 'PREFERENTIAL_PROCUREMENT', 'name': 'Preferential Procurement Records', 'is_required': True},
        {'document_type': 'SUPPLIER_DECLARATIONS', 'name': 'Supplier B-BBEE Declarations', 'is_required': True},
        # SED
        {'document_type': 'SED_CONTRIBUTIONS', 'name': 'Socio-Economic Development Evidence', 'is_required': True},
        # Verification
        {'document_type': 'BBBEE_CERTIFICATE', 'name': 'B-BBEE Certificate', 'is_required': False},
    ]
    
    for doc_data in bbbee_documents:
        BBBEEDocument.objects.get_or_create(
            service_year=bbbee_service_year,
            document_type=doc_data['document_type'],
            defaults={
                'name': doc_data['name'],
                'is_required': doc_data['is_required'],
                'status': 'PENDING',
            }
        )


def create_service_year_for_client(subscription, financial_year=None):
    """
    Utility function to manually create a service year for a subscription.
    Can be called from views or management commands.
    """
    if financial_year is None:
        today = timezone.now().date()
        if today.month >= 5:
            financial_year = today.year
        else:
            financial_year = today.year - 1
    
    client = subscription.client
    
    # Ensure committee exists
    committee, _ = TrainingCommittee.objects.get_or_create(
        client=client,
        defaults={
            'name': f'{client.company_name} Training Committee',
            'meeting_frequency': 'QUARTERLY',
            'is_active': True,
            'campus': subscription.campus,  # Inherit campus from subscription
        }
    )
    
    # Create service year
    service_year, created = WSPATRServiceYear.objects.get_or_create(
        subscription=subscription,
        financial_year=financial_year,
        defaults={
            'client': client,
            'status': 'NOT_STARTED',
            'submission_deadline': date(financial_year + 1, 4, 30),
            'seta': client.seta,
            'assigned_consultant': subscription.assigned_consultant,
        }
    )
    
    if created:
        schedule_quarterly_meetings(committee, service_year, financial_year)
    
    return service_year, created


# --------------------------------------------------
# Task Completion Notification Signal
# --------------------------------------------------

@receiver(pre_save, sender=MilestoneTask)
def track_task_status_change(sender, instance, **kwargs):
    """
    Track the previous status before save to detect status changes.
    """
    if instance.pk:
        try:
            old_instance = MilestoneTask.objects.get(pk=instance.pk)
            instance._previous_status = old_instance.status
        except MilestoneTask.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=MilestoneTask)
def notify_task_completion(sender, instance, created, **kwargs):
    """
    When a task status changes to DONE, notify:
    - The assigned user (if different from completer)
    - The project's account manager
    """
    # Only process when status changed to DONE
    previous_status = getattr(instance, '_previous_status', None)
    
    if instance.status != 'DONE':
        return
    
    # Skip if just created with DONE status or status unchanged
    if created or previous_status == 'DONE':
        return
    
    # Import here to avoid circular imports
    from core.services.notifications import get_notification_service
    
    try:
        service = get_notification_service()
    except Exception:
        # Notification service not available
        return
    
    project = instance.milestone.project
    client = project.client
    
    # Build link to project
    link = f'/corporate/projects/{project.pk}/'
    
    # Determine who completed the task
    completer = instance.completed_by
    completer_contact = instance.completed_by_contact
    
    if completer_contact:
        completer_name = completer_contact.full_name
    elif completer:
        completer_name = completer.get_full_name()
    else:
        completer_name = 'Someone'
    
    # Notify assigned user (if different from completer)
    if instance.assigned_to and instance.assigned_to != completer:
        service.send_notification(
            user=instance.assigned_to,
            notification_type='TASK_COMPLETED',
            title=f'Task Completed: {instance.title}',
            message=f'{completer_name} marked the task "{instance.title}" as complete for {client.company_name}.',
            link=link
        )
    
    # Notify account manager (if different from completer and assigned user)
    account_manager = project.account_manager or client.account_manager
    if account_manager and account_manager != completer and account_manager != instance.assigned_to:
        service.send_notification(
            user=account_manager,
            notification_type='TASK_COMPLETED',
            title=f'Task Completed: {instance.title}',
            message=f'{completer_name} completed task "{instance.title}" for {client.company_name} - {project.project_number}.',
            link=link
        )


# ==========================================
# ONBOARDING SIGNALS
# ==========================================

@receiver(post_save, sender=ClientServiceSubscription)
def create_service_onboarding(sender, instance, created, **kwargs):
    """
    When a new service subscription is activated, create a ServiceOnboarding record.
    """
    if not created:
        return
    
    if instance.status != 'ACTIVE':
        return
    
    # Import here to avoid circular imports
    from .models import ServiceOnboarding
    
    # Determine service type for onboarding
    service_type = instance.service.service_type if hasattr(instance.service, 'service_type') else None
    
    if not service_type or service_type not in ['WSP_ATR', 'EE', 'BBBEE']:
        return
    
    # Check if onboarding already exists
    if ServiceOnboarding.objects.filter(subscription=instance).exists():
        return
    
    # Create service onboarding
    ServiceOnboarding.objects.create(
        subscription=instance,
        client=instance.client,
        service_type=service_type,
        status='NOT_STARTED',
        current_step=1
    )


def auto_create_client_onboarding(client):
    """
    Helper function to create client onboarding if it doesn't exist.
    Called when first subscription is added.
    """
    from .models import ClientOnboarding
    
    # Check if onboarding already exists
    if ClientOnboarding.objects.filter(client=client).exists():
        return
    
    # Create client onboarding
    ClientOnboarding.objects.create(
        client=client,
        campus=client.campus,
        current_step='COMPANY_VERIFY'
    )


@receiver(post_save, sender=ClientServiceSubscription)
def trigger_client_onboarding(sender, instance, created, **kwargs):
    """
    When first subscription is created, trigger client onboarding wizard.
    """
    if not created:
        return
    
    # Only trigger for first subscription
    if ClientServiceSubscription.objects.filter(client=instance.client).count() > 1:
        return
    
    auto_create_client_onboarding(instance.client)

