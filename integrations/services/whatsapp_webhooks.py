# integrations/services/whatsapp_webhooks.py

import logging
from django.utils import timezone
from django.db import transaction

from integrations.models import IntegrationConnection
from integrations.connectors import WhatsAppConnector

logger = logging.getLogger(__name__)


class WhatsAppWebhookService:
    """
    Handles inbound WhatsApp webhook events.

    Responsibilities:
    - Signature verification
    - Payload parsing
    - Message persistence
    - Status updates
    """

    def __init__(self):
        self.connection = IntegrationConnection.objects.filter(
            provider='whatsapp',
            is_active=True
        ).first()

    def process_payload(self, payload, raw_body, signature):
        """
        Entry point called from CRM webhook view.
        """
        if not self.connection:
            logger.warning("No active WhatsApp integration connection")
            return

        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                if change.get('field') != 'messages':
                    continue

                value = change.get('value', {})
                metadata = value.get('metadata', {})
                phone_number_id = metadata.get('phone_number_id')

                from crm.communication_models import SocialChannel
                channel = SocialChannel.objects.filter(
                    platform='whatsapp',
                    external_id=phone_number_id,
                    is_active=True
                ).first()

                if not channel:
                    logger.warning(f"No WhatsApp SocialChannel for {phone_number_id}")
                    continue

                connector = WhatsAppConnector(self.connection, channel)

                # 🔐 Verify webhook signature
                if signature and not connector.verify_webhook(raw_body, signature):
                    logger.warning("WhatsApp webhook signature verification failed")
                    return

                # 📩 Handle inbound messages
                messages = connector.parse_webhook(payload)
                for inbound_msg in messages:
                    self._process_inbound_message(channel, inbound_msg)

                # 📦 Handle delivery/read status updates
                for status in value.get('statuses', []):
                    self._process_status_update(status)

    # ------------------------------------------------------------------
    # Inbound Messages
    # ------------------------------------------------------------------

    @transaction.atomic
    def _process_inbound_message(self, channel, inbound_msg):
        from crm.communication_models import Conversation, Message
        from crm.models import Lead

        conversation = Conversation.objects.filter(
            channel='whatsapp',
            social_channel=channel,
            contact_identifier=inbound_msg.sender_id
        ).first()

        lead = None
        if inbound_msg.sender_phone:
            lead = Lead.objects.filter(phone=inbound_msg.sender_phone).first()

        if not conversation:
            conversation = Conversation.objects.create(
                brand=channel.brand,
                campus=channel.campus,
                channel='whatsapp',
                social_channel=channel,
                contact_identifier=inbound_msg.sender_id,
                contact_name=inbound_msg.sender_name or '',
                contact_phone=inbound_msg.sender_phone,
                lead=lead,
                status='open',
                window_expires_at=timezone.now() + timezone.timedelta(hours=24)
            )
        else:
            conversation.contact_name = inbound_msg.sender_name or conversation.contact_name
            conversation.contact_phone = inbound_msg.sender_phone or conversation.contact_phone
            conversation.window_expires_at = timezone.now() + timezone.timedelta(hours=24)
            if conversation.status == 'closed':
                conversation.status = 'open'
            conversation.save()

        Message.objects.create(
            conversation=conversation,
            external_id=inbound_msg.external_id,
            direction='inbound',
            message_type=inbound_msg.message_type,
            content=inbound_msg.content,
            text=inbound_msg.text or '',
            sender_identifier=inbound_msg.sender_id,
            sender_name=inbound_msg.sender_name,
            media_url=inbound_msg.media_url,
            media_type=inbound_msg.media_mime_type,
            media_filename=inbound_msg.media_filename,
            status='delivered',
            delivered_at=timezone.now(),
            metadata=inbound_msg.metadata or {}
        )

        conversation.last_message_at = timezone.now()
        conversation.message_count = (conversation.message_count or 0) + 1
        conversation.unread_count = (conversation.unread_count or 0) + 1
        conversation.save()

        logger.info(f"WhatsApp inbound message saved: {inbound_msg.external_id}")

    # ------------------------------------------------------------------
    # Status Updates
    # ------------------------------------------------------------------

    def _process_status_update(self, status_data):
        from crm.communication_models import Message

        message_id = status_data.get('id')
        status = status_data.get('status', '').lower()

        message = Message.objects.filter(external_id=message_id).first()
        if not message:
            return

        status_map = {
            'sent': 'sent',
            'delivered': 'delivered',
            'read': 'read',
            'failed': 'failed',
        }

        new_status = status_map.get(status)
        if not new_status:
            return

        message.status = new_status

        if new_status == 'delivered':
            message.delivered_at = timezone.now()
        elif new_status == 'read':
            message.read_at = timezone.now()
        elif new_status == 'failed':
            errors = status_data.get('errors', [])
            if errors:
                message.error_code = errors[0].get('code')
                message.error_message = errors[0].get('title', 'Unknown error')
            message.failed_at = timezone.now()

        message.save()
        logger.info(f"WhatsApp message {message_id} updated → {new_status}")
