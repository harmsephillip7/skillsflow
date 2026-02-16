import json
import hmac
import hashlib
import logging
from typing import Any, Dict, List, Optional

from django.utils import timezone
from django.conf import settings

from integrations.connectors.base import (
    BaseConnector,
    ConnectorError,
    MessageResult,
    MessageStatus,
    InboundMessage,
)

logger = logging.getLogger(__name__)


class WhatsAppConnector(BaseConnector):
    """
    WhatsApp Cloud API Connector.

    Required credentials on IntegrationConnection:
      - access_token (or api_key) -> bearer token
      - api_secret (optional but recommended) -> used for webhook signature verify
    Required config keys on IntegrationConnection.config:
      - phone_number_id -> Meta Phone Number ID (used for /{phone_number_id}/messages)
      - waba_id (optional) -> WhatsApp Business Account ID
    """

    DEFAULT_BASE_URL = "https://graph.facebook.com/v18.0"

    @property
    def provider_name(self) -> str:
        return "whatsapp"

    # -------------------------
    # Session / Auth
    # -------------------------
    def _setup_session(self):
        token = self.connection.access_token or self.connection.api_key
        if not token:
            raise ConnectorError("WhatsApp access token not configured", code="MISSING_TOKEN")

        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

    # -------------------------
    # Helpers
    # -------------------------
    def _get_base_url(self) -> str:
        return (self.connection.base_url or self.DEFAULT_BASE_URL).rstrip("/")

    def _get_phone_number_id(self) -> str:
        cfg = self.connection.config or {}
        phone_number_id = cfg.get("phone_number_id")
        if not phone_number_id:
            raise ConnectorError(
                "WhatsApp phone_number_id missing in connection.config",
                code="MISSING_PHONE_NUMBER_ID",
                details={"expected_config_key": "phone_number_id"},
            )
        return str(phone_number_id)

    def _clean_phone(self, recipient: str) -> str:
        # Expect E.164 digits only, no "+"
        digits = "".join(ch for ch in recipient if ch.isdigit())
        return digits

    # -------------------------
    # Health
    # -------------------------
    def check_health(self) -> Dict[str, Any]:
        """
        Quick health check: hit phone number endpoint.
        """
        phone_number_id = self._get_phone_number_id()
        url = f"{self._get_base_url()}/{phone_number_id}"
        try:
            resp = self._make_request("GET", url, timeout=10)
            ok = resp.status_code == 200
            return {
                "healthy": ok,
                "message": "OK" if ok else f"HTTP {resp.status_code}",
                "details": {"status_code": resp.status_code, "body": resp.json() if ok else resp.text},
            }
        except Exception as e:
            return {"healthy": False, "message": str(e), "details": {}}

    # -------------------------
    # Outbound messaging
    # -------------------------
    def send_text(self, recipient: str, text: str, **kwargs) -> MessageResult:
        phone_number_id = self._get_phone_number_id()
        url = f"{self._get_base_url()}/{phone_number_id}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "to": self._clean_phone(recipient),
            "type": "text",
            "text": {"body": text},
        }

        try:
            resp = self._make_request("POST", url, json=payload, timeout=15)
            if not resp.ok:
                return MessageResult.failure_result(
                    error_code="SEND_FAILED",
                    error_message=f"WhatsApp API error: {resp.status_code} {resp.text}",
                    metadata={"payload": payload},
                )

            data = resp.json()
            message_id = (data.get("messages") or [{}])[0].get("id")
            result = MessageResult.success_result(external_id=message_id, status=MessageStatus.SENT, metadata=data)
            self._log_send(recipient, "text", result)
            return result

        except Exception as e:
            result = MessageResult.failure_result("SEND_EXCEPTION", f"Request failed: {str(e)}")
            self._log_send(recipient, "text", result)
            return result

    def send_media(
        self,
        recipient: str,
        media_type: str,
        media_url: str,
        caption: str = None,
        **kwargs,
    ) -> MessageResult:
        """
        Send a media message using a public URL.
        media_type should be one of: image, video, audio, document
        """
        phone_number_id = self._get_phone_number_id()
        url = f"{self._get_base_url()}/{phone_number_id}/messages"

        media_type = (media_type or "").lower().strip()
        if media_type not in ("image", "video", "audio", "document"):
            return MessageResult.failure_result("INVALID_MEDIA_TYPE", f"Unsupported media_type: {media_type}")

        media_obj = {"link": media_url}
        if caption and media_type in ("image", "video", "document"):
            media_obj["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "to": self._clean_phone(recipient),
            "type": media_type,
            media_type: media_obj,
        }

        try:
            resp = self._make_request("POST", url, json=payload, timeout=20)
            if not resp.ok:
                return MessageResult.failure_result(
                    error_code="SEND_FAILED",
                    error_message=f"WhatsApp API error: {resp.status_code} {resp.text}",
                    metadata={"payload": payload},
                )

            data = resp.json()
            message_id = (data.get("messages") or [{}])[0].get("id")
            result = MessageResult.success_result(external_id=message_id, status=MessageStatus.SENT, metadata=data)
            self._log_send(recipient, media_type, result)
            return result

        except Exception as e:
            result = MessageResult.failure_result("SEND_EXCEPTION", f"Request failed: {str(e)}")
            self._log_send(recipient, media_type, result)
            return result

    # -------------------------
    # Webhooks
    # -------------------------
    def verify_webhook(self, request_data: Dict, signature: str) -> bool:
        """
        Meta sends X-Hub-Signature-256: 'sha256=...'
        We validate with app secret (connection.api_secret or settings.WHATSAPP_APP_SECRET)
        """
        secret = self.connection.api_secret or getattr(settings, "WHATSAPP_APP_SECRET", None)
        if not secret:
            # If secret not configured, do not fail hard in dev;
            # but for production you SHOULD require this.
            logger.warning("WhatsApp app secret not configured; skipping signature verification")
            return True

        raw = request_data.get("_raw")
        if raw is None:
            try:
                raw = json.dumps(request_data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            except Exception:
                return False

        sig = signature or ""
        if sig.startswith("sha256="):
            sig = sig.split("sha256=", 1)[1]

        expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig)

    def parse_webhook(self, payload: Dict) -> List[InboundMessage]:
        """
        Parse WhatsApp webhooks into InboundMessage list.
        Supports:
          - inbound text messages
          - status updates are handled elsewhere (CRM view usually)
        """
        messages: List[InboundMessage] = []

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value") or {}
                incoming = value.get("messages") or []
                contacts = value.get("contacts") or []

                contact_by_wa_id = {}
                for c in contacts:
                    wa_id = c.get("wa_id")
                    profile = (c.get("profile") or {})
                    contact_by_wa_id[wa_id] = profile.get("name")

                for msg in incoming:
                    msg_type = msg.get("type", "text")
                    from_wa = msg.get("from")
                    msg_id = msg.get("id")
                    timestamp = msg.get("timestamp")

                    text = None
                    content: Dict[str, Any] = {}
                    media_url = None
                    media_mime = None
                    media_filename = None

                    if msg_type == "text":
                        text = (msg.get("text") or {}).get("body")
                        content = {"text": text}

                    elif msg_type in ("image", "video", "audio", "document"):
                        media_obj = msg.get(msg_type) or {}
                        content = media_obj
                        media_filename = media_obj.get("filename")
                        media_mime = media_obj.get("mime_type")

                    sender_name = contact_by_wa_id.get(from_wa)

                    try:
                        ts = timezone.datetime.fromtimestamp(int(timestamp), tz=timezone.get_current_timezone())
                    except Exception:
                        ts = timezone.now()

                    messages.append(
                        InboundMessage(
                            external_id=msg_id,
                            sender_id=from_wa,
                            sender_name=sender_name,
                            sender_phone=from_wa,
                            message_type=msg_type,
                            content=content,
                            text=text,
                            timestamp=ts,
                            metadata={"raw": msg},
                            media_url=media_url,
                            media_mime_type=media_mime,
                            media_filename=media_filename,
                        )
                    )

        return messages
