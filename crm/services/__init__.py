"""
CRM Services Package

Provides business logic for:
- Messaging across channels
- Campaign management
- Lead/Opportunity management
- Pipeline management
- Nurture automation
- Pre-approval letter generation and sending
"""

from crm.services.messaging import (
    MessagingService,
    BulkMessagingService,
    send_template_message,
)
from crm.services.pipeline import PipelineService
from crm.services.nurture import NurtureService
from crm.services.pre_approval import PreApprovalService

__all__ = [
    'MessagingService',
    'BulkMessagingService',
    'send_template_message',
    'PipelineService',
    'NurtureService',
    'PreApprovalService',
]
