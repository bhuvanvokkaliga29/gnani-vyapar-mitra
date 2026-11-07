"""Official Twilio WhatsApp Sandbox Adapter.

Provides:
1. Immediate, zero-friction WhatsApp integration without Meta App review or device blocks.
2. Cryptographic signature validation via Twilio RequestValidator (X-Twilio-Signature).
3. Synchronous TwiML messaging response for zero-latency direct replies.
4. Seamless reuse of core WhatsAppIntentParser, PolicyGuard, and ConfirmationManager.
5. Inbound deduplication via Twilio MessageSid in WhatsAppWebhookLog.
6. Outbound dispatch via official Twilio REST Client SDK.
"""

import uuid
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient

from apps.api.core.config import get_settings
from domain.models import Merchant
from domain.whatsapp_models import WhatsAppWebhookLog, WhatsAppOutboundMessage
from services.whatsapp.security import normalize_phone_number
from services.whatsapp.intent import WhatsAppIntentParser
from services.whatsapp.service import WhatsAppService

logger = structlog.get_logger()
settings = get_settings()


class TwilioWhatsAppAdapter:
    """Production-grade Twilio WhatsApp adapter for instant merchant connectivity."""

    def __init__(self, whatsapp_service: Optional[WhatsAppService] = None):
        self.service = whatsapp_service or WhatsAppService()
        self.auth_token = settings.TWILIO_AUTH_TOKEN.strip()
        self.account_sid = settings.TWILIO_ACCOUNT_SID.strip()
        self.from_number = settings.TWILIO_WHATSAPP_NUMBER.strip() or "whatsapp:+14155238886"

    @property
    def is_configured(self) -> bool:
        """True if real Twilio credentials are configured."""
        return (
            bool(self.account_sid)
            and bool(self.auth_token)
            and not self.account_sid.startswith("your_")
            and not self.auth_token.startswith("your_")
        )

    def validate_signature(self, url: str, form_data: Dict[str, Any], signature_header: Optional[str]) -> bool:
        """
        Validates X-Twilio-Signature using Twilio's official RequestValidator.
        Skips validation only if TWILIO_AUTH_TOKEN is not configured (local dev/test mode).
        """
        if not self.auth_token:
            logger.debug("twilio_signature_skipped_no_token")
            return True

        if not signature_header:
            logger.warning("twilio_signature_missing_header")
            return False

        try:
            validator = RequestValidator(self.auth_token)
            return validator.validate(url, form_data, signature_header)
        except Exception as e:
            logger.error("twilio_signature_validation_error", error=str(e))
            return False

    async def process_inbound_webhook(
        self,
        db: AsyncSession,
        form_data: Dict[str, Any],
        request_url: str = "",
        signature_header: Optional[str] = None
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Processes Twilio WhatsApp form payload.
        Returns: (twiml_xml_string, reply_plain_text, status_metadata)
        """
        # 1. Signature Validation
        if self.auth_token and not self.validate_signature(request_url, form_data, signature_header):
            logger.warning("twilio_invalid_signature", url=request_url)
            raise ValueError("Invalid Twilio request signature")

        # 2. Extract Twilio fields
        raw_from = form_data.get("From", "")
        clean_phone = raw_from.replace("whatsapp:", "").strip()
        sender_phone = normalize_phone_number(clean_phone)
        message_body = (form_data.get("Body") or "").strip()
        message_sid = form_data.get("MessageSid") or f"SM_{uuid.uuid4().hex[:16]}"
        recipient_number = form_data.get("To", self.from_number)

        # 3. Message Idempotency & Deduplication
        existing_log_stmt = select(WhatsAppWebhookLog).where(WhatsAppWebhookLog.message_id == message_sid)
        existing_log = (await db.execute(existing_log_stmt)).scalar_one_or_none()
        if existing_log:
            logger.info("twilio_duplicate_message_ignored", sid=message_sid)
            # Empty TwiML instructs Twilio not to send repeated responses
            return "<Response/>", "", {"status": "duplicate", "message_sid": message_sid}

        # 4. Resolve Merchant Tenant
        merchant = await self.service.resolve_merchant_for_phone(db, sender_phone)
        merchant_id = merchant.id if merchant else settings.WHATSAPP_DEFAULT_MERCHANT_ID

        # 5. Record Inbound Webhook Audit
        log_entry = WhatsAppWebhookLog(
            id=f"walog_{uuid.uuid4().hex[:12]}",
            message_id=message_sid,
            sender_phone=sender_phone,
            recipient_phone_id=recipient_number,
            merchant_id=merchant_id,
            message_text=message_body,
            raw_payload=form_data,
            status="RECEIVED"
        )
        db.add(log_entry)
        await db.commit()

        if not message_body:
            log_entry.status = "PROCESSED"
            await db.commit()
            return "<Response/>", "", {"status": "empty_body", "message_sid": message_sid}

        # 6. Intent Extraction & Business Logic Routing
        intent = WhatsAppIntentParser.parse(message_body)
        logger.info(
            "twilio_whatsapp_intent_extracted",
            intent=intent.intent_type.value,
            product=intent.product_name,
            lang=intent.language,
            sender=sender_phone
        )

        reply_text = await self.service._route_intent(
            db=db,
            merchant=merchant,
            sender_phone=sender_phone,
            intent=intent,
            raw_text=message_body,
            wamid=message_sid
        )

        # 7. Construct Synchronous TwiML Response
        twiml = MessagingResponse()
        twiml.message(reply_text)
        twiml_xml = str(twiml)

        # 8. Record Outbound Dispatch Audit
        outbound_log = WhatsAppOutboundMessage(
            id=f"wamsg_{uuid.uuid4().hex[:12]}",
            recipient_phone=sender_phone,
            merchant_id=merchant_id,
            reply_to_message_id=message_sid,
            message_text=reply_text,
            delivery_status="TWIML_SYNCHRONOUS_REPLY",
            meta_response_payload={"format": "twiml", "message_sid": message_sid}
        )
        db.add(outbound_log)
        log_entry.status = "PROCESSED"
        await db.commit()

        logger.info("twilio_whatsapp_reply_generated", sid=message_sid, reply_len=len(reply_text))
        return twiml_xml, reply_text, {
            "status": "success",
            "message_sid": message_sid,
            "sender_phone": sender_phone,
            "intent": intent.intent_type.value
        }

    async def send_direct_outbound_message(
        self,
        to_phone: str,
        message_text: str
    ) -> Dict[str, Any]:
        """Sends an active outbound WhatsApp message using the Twilio REST SDK."""
        clean_to = normalize_phone_number(to_phone)
        dest_formatted = f"whatsapp:+{clean_to}"

        if not self.is_configured:
            mock_sid = f"SM_MOCK_{uuid.uuid4().hex[:16]}"
            logger.info(
                "twilio_mock_outbound_dispatched",
                to=dest_formatted,
                text_len=len(message_text),
                mock_sid=mock_sid
            )
            return {"status": "mock_sent", "sid": mock_sid, "is_mock": True}

        try:
            client = TwilioClient(self.account_sid, self.auth_token)
            msg = client.messages.create(
                from_=self.from_number,
                to=dest_formatted,
                body=message_text
            )
            logger.info("twilio_live_outbound_sent", sid=msg.sid, to=dest_formatted)
            return {"status": "sent", "sid": msg.sid, "is_mock": False}
        except Exception as e:
            logger.error("twilio_outbound_failed", error=str(e), to=dest_formatted)
            return {"status": "error", "error": str(e)}
