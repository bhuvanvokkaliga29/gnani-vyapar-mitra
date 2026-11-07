"""FastAPI Router for WhatsApp Business Platform Webhooks & Diagnostics.

Routes:
1. GET  /webhook/whatsapp           - Meta Hub challenge verification handshake
2. POST /webhook/whatsapp           - Inbound webhook processing & dispatch
3. GET  /api/v1/whatsapp/webhook    - Dual-path Meta verification
4. POST /api/v1/whatsapp/webhook    - Dual-path Inbound webhook processing
5. POST /api/v1/whatsapp/simulate   - Interactive test simulator for hackathon demo
6. GET  /api/v1/whatsapp/diagnostics- Operational telemetry & audit inspection
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request, Depends, Query, HTTPException, status
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
import structlog

from apps.api.core.config import get_settings
from apps.api.core.database import get_db
from domain.whatsapp_models import (
    WhatsAppWebhookLog,
    WhatsAppPendingConfirmation,
    WhatsAppOutboundMessage
)
from services.whatsapp.service import WhatsAppService
from services.whatsapp.security import normalize_phone_number
from services.whatsapp.twilio_adapter import TwilioWhatsAppAdapter

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter(tags=["WhatsApp Integration"])


def get_whatsapp_service() -> WhatsAppService:
    return WhatsAppService()


def get_twilio_adapter() -> TwilioWhatsAppAdapter:
    return TwilioWhatsAppAdapter()


class WhatsAppSimulateRequest(BaseModel):
    """Payload for simulating incoming WhatsApp messages from merchant's phone."""
    sender_phone: str = Field(default="+919113960498", description="Sender phone number in E.164")
    message_text: str = Field(..., description="Message body in Kannada, Hindi, or English")
    wamid: Optional[str] = Field(None, description="Optional custom WAMID to test deduplication")


class WhatsAppConnectorInboundRequest(BaseModel):
    """Payload sent by the local Node.js whatsapp-web.js connector."""
    sender_phone: str = Field(default="+919113960498", description="Sender phone number in E.164")
    message_text: str = Field(..., description="Message body text")
    message_id: Optional[str] = Field(None, description="WhatsApp message ID")


# =============================================================================
# 1. Meta Webhook Verification Handshake (GET)
# =============================================================================

@router.get("/webhook/whatsapp")
@router.get("/api/v1/whatsapp/webhook")
async def verify_whatsapp_webhook(
    mode: Optional[str] = Query(None, alias="hub.mode"),
    token: Optional[str] = Query(None, alias="hub.verify_token"),
    challenge: Optional[str] = Query(None, alias="hub.challenge"),
    whatsapp_svc: WhatsAppService = Depends(get_whatsapp_service)
):
    """
    Handles Meta's hub.challenge verification handshake.
    Must return plain text challenge when token matches WHATSAPP_VERIFY_TOKEN.
    """
    verified_challenge = whatsapp_svc.verify_webhook_token(mode, token, challenge)
    if verified_challenge is not None:
        return PlainTextResponse(content=verified_challenge, status_code=status.HTTP_200_OK)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Webhook verification failed: token mismatch or invalid mode"
    )


# =============================================================================
# 2. Meta Inbound Webhook Event Receiver (POST)
# =============================================================================

@router.post("/webhook/whatsapp", status_code=status.HTTP_200_OK)
@router.post("/api/v1/whatsapp/webhook", status_code=status.HTTP_200_OK)
async def receive_whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    whatsapp_svc: WhatsAppService = Depends(get_whatsapp_service)
):
    """
    Receives inbound WhatsApp Cloud API messages, verifies HMAC-SHA256,
    deduplicates WAMID, runs policy guardrails, and responds.
    """
    raw_body = await request.body()
    signature_header = (
        request.headers.get("X-Hub-Signature-256")
        or request.headers.get("x-hub-signature-256")
    )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    # Process payload idempotently
    result = await whatsapp_svc.process_inbound_payload(
        db=db,
        payload=payload,
        raw_body=raw_body,
        signature_header=signature_header
    )

    if result.get("status") == "error":
        # Meta expects 401 if HMAC signature is corrupted/forged
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.get("message", "HMAC verification failed")
        )

    # Always return 200 OK to Meta to acknowledge receipt
    return result


# =============================================================================
# 3. Twilio WhatsApp Sandbox Webhook Receiver (POST)
# =============================================================================

@router.post("/webhook/twilio", status_code=status.HTTP_200_OK)
@router.post("/api/v1/whatsapp/twilio", status_code=status.HTTP_200_OK)
async def receive_twilio_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    twilio_adapter: TwilioWhatsAppAdapter = Depends(get_twilio_adapter)
):
    """
    Receives inbound WhatsApp messages from Twilio Sandbox.
    Validates X-Twilio-Signature, processes merchant intent, enforces margin guardrails,
    and returns synchronous TwiML for instant WhatsApp delivery.
    """
    form_data = await request.form()
    payload = dict(form_data)
    signature = (
        request.headers.get("X-Twilio-Signature")
        or request.headers.get("x-twilio-signature")
    )

    try:
        twiml_xml, reply_text, meta = await twilio_adapter.process_inbound_webhook(
            db=db,
            form_data=payload,
            request_url=str(request.url),
            signature_header=signature
        )
        return Response(content=twiml_xml, media_type="application/xml")
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(val_err)
        )
    except Exception as exc:
        logger.error("twilio_webhook_error", error=str(exc))
        error_twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>⚠️ Internal error: {str(exc)}</Message></Response>'
        return Response(content=error_twiml, media_type="application/xml")


# =============================================================================
# 4. Hackathon Demo Simulator (POST)
# =============================================================================

@router.post("/api/v1/whatsapp/simulate", status_code=status.HTTP_200_OK)
async def simulate_whatsapp_message(
    req: WhatsAppSimulateRequest,
    db: AsyncSession = Depends(get_db),
    whatsapp_svc: WhatsAppService = Depends(get_whatsapp_service)
):
    """
    Simulates sending an incoming message from the merchant's personal phone.
    Enables instant hackathon testing of Kannada, Hindi, and English workflows.
    """
    norm_phone = normalize_phone_number(req.sender_phone)
    simulated_wamid = req.wamid or f"wamid.SIM_{uuid.uuid4().hex[:12]}"

    meta_mock_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": settings.WHATSAPP_BUSINESS_ACCOUNT_ID or "WHATSAPP_TEST_ACCOUNT",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15550269000",
                        "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID or "test_phone_id"
                    },
                    "contacts": [{
                        "profile": {"name": "Merchant Operator"},
                        "wa_id": norm_phone
                    }],
                    "messages": [{
                        "from": norm_phone,
                        "id": simulated_wamid,
                        "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                        "text": {"body": req.message_text},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    result = await whatsapp_svc.process_inbound_payload(
        db=db,
        payload=meta_mock_payload
    )

    return {
        "status": "success",
        "sender_phone": norm_phone,
        "input_text": req.message_text,
        "simulated_wamid": simulated_wamid,
        "result": result
    }


# =============================================================================
# 5. Local WhatsApp Connector Inbound Receiver (POST)
# =============================================================================

@router.post("/api/v1/whatsapp/connector-inbound", status_code=status.HTTP_200_OK)
async def receive_connector_inbound(
    req: WhatsAppConnectorInboundRequest,
    db: AsyncSession = Depends(get_db),
    whatsapp_svc: WhatsAppService = Depends(get_whatsapp_service)
):
    """
    Receives inbound messages forwarded by the local Node.js whatsapp-web.js connector.
    Processes intent, checks policy constraints, handles confirmation tokens,
    and returns synchronous reply text for instant dispatch back into WhatsApp.
    """
    result = await whatsapp_svc.process_connector_message(
        db=db,
        sender_phone=req.sender_phone,
        message_text=req.message_text,
        message_id=req.message_id
    )
    return result


# =============================================================================
# 6. Diagnostics & Live Integration Telemetry (GET)
# =============================================================================

@router.get("/api/v1/whatsapp/diagnostics", status_code=status.HTTP_200_OK)
async def get_whatsapp_diagnostics(
    db: AsyncSession = Depends(get_db)
):
    """
    Returns comprehensive operational telemetry for the WhatsApp Business integration:
    credentials status, live delivery mode, pending confirmations, and recent logs.
    """
    is_live_configured = bool(
        settings.WHATSAPP_ACCESS_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID
    )

    # 1. Total counts
    inbound_count_stmt = select(func.count(WhatsAppWebhookLog.id))
    inbound_count = (await db.execute(inbound_count_stmt)).scalar() or 0

    outbound_count_stmt = select(func.count(WhatsAppOutboundMessage.id))
    outbound_count = (await db.execute(outbound_count_stmt)).scalar() or 0

    pending_count_stmt = (
        select(func.count(WhatsAppPendingConfirmation.id))
        .where(WhatsAppPendingConfirmation.status == "PENDING")
    )
    pending_count = (await db.execute(pending_count_stmt)).scalar() or 0

    # 2. Recent Webhook Logs (last 5)
    recent_inbound_stmt = (
        select(WhatsAppWebhookLog)
        .order_by(desc(WhatsAppWebhookLog.created_at))
        .limit(5)
    )
    recent_inbound = (await db.execute(recent_inbound_stmt)).scalars().all()

    # 3. Recent Outbound Logs (last 5)
    recent_outbound_stmt = (
        select(WhatsAppOutboundMessage)
        .order_by(desc(WhatsAppOutboundMessage.created_at))
        .limit(5)
    )
    recent_outbound = (await db.execute(recent_outbound_stmt)).scalars().all()

    # 4. Active Pending Confirmations
    active_confirmations_stmt = (
        select(WhatsAppPendingConfirmation)
        .where(WhatsAppPendingConfirmation.status == "PENDING")
        .order_by(desc(WhatsAppPendingConfirmation.created_at))
        .limit(5)
    )
    active_confirmations = (await db.execute(active_confirmations_stmt)).scalars().all()

    return {
        "status": "healthy",
        "live_mode": is_live_configured,
        "delivery_mode": "META_CLOUD_API" if is_live_configured else "STRUCTURED_MOCK_FALLBACK",
        "configuration": {
            "phone_number_id_configured": bool(settings.WHATSAPP_PHONE_NUMBER_ID),
            "access_token_configured": bool(settings.WHATSAPP_ACCESS_TOKEN),
            "app_secret_configured": bool(settings.WHATSAPP_APP_SECRET),
            "verify_token_configured": bool(settings.WHATSAPP_VERIFY_TOKEN),
            "target_merchant_phone": settings.WHATSAPP_TEST_MERCHANT_PHONE,
            "default_merchant_id": settings.WHATSAPP_DEFAULT_MERCHANT_ID,
            "api_version": settings.WHATSAPP_API_VERSION
        },
        "metrics": {
            "total_inbound_webhooks": inbound_count,
            "total_outbound_messages": outbound_count,
            "active_pending_confirmations": pending_count
        },
        "recent_inbound": [
            {
                "id": log.id,
                "message_id": log.message_id,
                "sender_phone": log.sender_phone,
                "text": log.message_text,
                "status": log.status,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in recent_inbound
        ],
        "recent_outbound": [
            {
                "id": out.id,
                "recipient_phone": out.recipient_phone,
                "message_text": out.message_text,
                "delivery_status": out.delivery_status,
                "created_at": out.created_at.isoformat() if out.created_at else None
            }
            for out in recent_outbound
        ],
        "active_confirmations": [
            {
                "id": conf.id,
                "code": conf.confirmation_code,
                "operation_type": conf.operation_type,
                "product_name": conf.product_name,
                "proposed_values": conf.proposed_values,
                "expires_at": conf.expires_at.isoformat() if conf.expires_at else None
            }
            for conf in active_confirmations
        ]
    }
