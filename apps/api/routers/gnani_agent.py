"""FastAPI Router for Gnani Agent Builder Integration.

Endpoints:
1. GET  /api/v1/gnani-agent/status          - Check integration status and probe Gnani Platform API
2. GET  /api/v1/gnani-agent/config          - Retrieve agent configuration from Gnani
3. PUT  /api/v1/gnani-agent/config          - Update agent configuration (prompt, greeting, voice)
4. GET  /api/v1/gnani-agent/chat-widget     - Retrieve Chat SDK widget configuration
5. PUT  /api/v1/gnani-agent/chat-widget     - Update Chat SDK widget configuration
6. POST /api/v1/gnani-agent/trigger-call    - Trigger outbound test call to a whitelisted phone
7. GET  /api/v1/gnani-agent/conversations   - Retrieve past conversation logs
8. GET  /api/v1/gnani-agent/conversations/{id} - Retrieve conversation statistics and transcript
9. POST /api/v1/gnani-agent/sync-knowledge  - Sync Vastram store catalog & policies into Agent FAQs
10. POST /api/v1/gnani-agent/action         - Custom Action Webhook (called by Gnani Agent during conversation)
11. POST /api/v1/gnani-agent/webhook        - Post-call webhook receiver for session memory persistence
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from apps.api.core.config import settings
from apps.api.core.database import get_db
from domain.models import Merchant, Product
from domain.session_models import VoiceConversationSession
from services.voice.gnani_agent_client import GnaniAgentBuilderClient
from services.commerce.business_intelligence import BusinessIntelligenceService
from services.conversation.session_manager import SessionManager

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/gnani-agent", tags=["Gnani Agent Builder Platform"])


def verify_gnani_webhook_auth(
    x_gnani_secret: Optional[str] = Header(None, alias="X-Gnani-Secret"),
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> bool:
    """Validate webhook authentication secret configured for Gnani integrations."""
    expected_secret = getattr(settings, "GNANI_WEBHOOK_SECRET", None)
    
    # If no secret is configured at all in settings, warn and require configuration in production
    if not expected_secret:
        if getattr(settings, "ENVIRONMENT", "development") != "development":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GNANI_WEBHOOK_SECRET is not configured on this server."
            )
        logger.warning("gnani_webhook_secret_not_configured_in_dev")
        return True

    # 1. Check custom header X-Gnani-Secret
    if x_gnani_secret and x_gnani_secret.strip() == expected_secret:
        return True
    
    # 2. Check standard Authorization: Bearer <secret>
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == expected_secret:
            return True

    # Reject explicitly invalid secret
    if x_gnani_secret or authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized webhook request: invalid authentication secret."
        )

    # In development mode, allow header-less calls with explicit warning
    if getattr(settings, "ENVIRONMENT", "development") == "development":
        logger.warning("gnani_webhook_auth_header_omitted_in_development")
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized webhook request: missing authentication secret header."
    )


class TriggerCallRequest(BaseModel):
    phone_number: str = Field(..., description="Target phone number (must be whitelisted in dev)")
    client_reference_id: Optional[str] = Field(default=None, description="Optional tracking reference")
    environment: str = Field(default="development", description="development | staging | production")


class UpdateAgentConfigRequest(BaseModel):
    botName: Optional[str] = None
    description: Optional[str] = None
    greetingMessage: Optional[str] = None
    endMessage: Optional[str] = None
    systemPrompt: Optional[str] = None
    botDetails: Optional[Dict[str, Any]] = None
    asrParams: Optional[Dict[str, Any]] = None
    llmParams: Optional[Dict[str, Any]] = None
    ttsParams: Optional[Dict[str, Any]] = None
    advanceSettings: Optional[Dict[str, Any]] = None
    languageSwitch: Optional[bool] = None


class CustomActionPayload(BaseModel):
    action: str = Field(..., description="Action name: get_daily_sales | get_top_products | get_product_stock | get_profit_summary")
    merchant_id: str = Field(default="merch_atlas_travel")
    sku: Optional[str] = Field(default=None)
    limit: Optional[int] = Field(default=3)


@router.get("/status")
async def get_gnani_agent_status():
    """Probe Gnani Agent Builder configuration and verify platform connection."""
    client = GnaniAgentBuilderClient()
    bot_id = client.agent_id
    base_url = client.base_url

    probe_result = await client.get_agent()
    status_code = probe_result.get("status_code", 500)
    payload = probe_result.get("payload", {})

    is_valid = status_code == 200
    permission_issue = status_code in (401, 403)

    return {
        "configured": client.is_configured,
        "bot_id": bot_id,
        "platform_base_url": base_url,
        "api_key_configured": bool(client.api_key),
        "probe_status_code": status_code,
        "probe_response": payload,
        "is_healthy": is_valid,
        "diagnostics": (
            "Connected successfully to Gnani Agent Builder."
            if is_valid
            else (
                "The current GNANI_API_KEY is configured for Gnani Speech APIs (Prisma STT & Timbre TTS on api.vachana.ai). "
                "The Agent Builder Platform API (api.inya.ai) requires an API key generated from the Gnani Agent Builder console with 'agents' permission."
                if permission_issue
                else f"Platform probe returned HTTP {status_code}."
            )
        )
    }


@router.get("/config")
async def get_agent_config(environment: str = "development"):
    """Fetch complete agent configuration from Gnani Agent Builder (GET /v1/agents/{botId})."""
    client = GnaniAgentBuilderClient()
    res = await client.get_agent(environment=environment)
    return res


@router.put("/config")
async def update_agent_config(request: UpdateAgentConfigRequest):
    """Update agent configuration in Gnani Agent Builder (PUT /v1/agents/{botId})."""
    client = GnaniAgentBuilderClient()
    payload = {k: v for k, v in request.dict().items() if v is not None}
    res = await client.update_agent(payload)
    return res


@router.get("/chat-widget")
async def get_chat_widget_config(environment: str = "development"):
    """Retrieve Chat Widget / SDK configuration (GET /v1/agents/{botId}/chat-sdk-config)."""
    client = GnaniAgentBuilderClient()
    res = await client.get_chat_sdk_config(environment=environment)
    return res


@router.put("/chat-widget")
async def update_chat_widget_config(payload: Dict[str, Any]):
    """Update Chat Widget visual customizations and settings (PUT /v1/agents/{botId}/chat-sdk-config)."""
    client = GnaniAgentBuilderClient()
    res = await client.update_chat_sdk_config(payload)
    return res


@router.post("/trigger-call")
async def trigger_test_call(request: TriggerCallRequest):
    """Place an outbound test call to a whitelisted phone number (POST /v1/agents/{botId}/trigger_call)."""
    client = GnaniAgentBuilderClient()
    res = await client.trigger_call(
        phone_number=request.phone_number,
        client_reference_id=request.client_reference_id,
        environment=request.environment
    )
    return res


@router.get("/conversations")
async def get_conversation_logs(page_no: int = 1, page_size: int = 10, environment: str = "development"):
    """Retrieve past calls for this agent (POST /v1/conversations/logs)."""
    client = GnaniAgentBuilderClient()
    res = await client.get_conversation_logs(
        environment=environment,
        filters={"pageNo": page_no, "pageSize": page_size}
    )
    return res


@router.get("/conversations/{conversation_id}")
async def get_conversation_stats(conversation_id: str):
    """Get call outcome, disposition, and transcript (GET /v1/conversations/{id}/stats)."""
    client = GnaniAgentBuilderClient()
    res = await client.get_conversation_stats(conversation_id=conversation_id)
    return res


@router.post("/sync-knowledge")
async def sync_knowledge(
    merchant_id: str = "merch_atlas_travel",
    db: AsyncSession = Depends(get_db)
):
    """Sync Vastram boutique catalog, pricing, and policies into Gnani Agent FAQs."""
    client = GnaniAgentBuilderClient()
    res = await client.sync_store_knowledge_faqs(db=db, merchant_id=merchant_id)
    return res


@router.post("/action")
async def handle_custom_action(
    payload: CustomActionPayload,
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(verify_gnani_webhook_auth)
):
    """Execute live commercial business intelligence tools for Gnani Agent Builder Custom Actions.
    
    Per official docs (https://docs.gnani.ai/D05_Custom.md), Gnani Agent Builder
    calls this endpoint when executing Custom Actions during conversations.
    """
    action = payload.action
    merchant_id = payload.merchant_id

    logger.info("gnani_custom_action_received", action=action, merchant_id=merchant_id)

    # 1. Enforce Merchant Isolation & Existence Check
    m_stmt = select(Merchant).where(Merchant.id == merchant_id)
    merchant = (await db.execute(m_stmt)).scalars().first()
    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Merchant '{merchant_id}' not found in database."
        )

    # 2. Action Routing & Execution
    if action == "get_daily_sales":
        data = await BusinessIntelligenceService.get_daily_sales(db, merchant_id)
        return {
            "status": "success",
            "action": action,
            "merchant_id": merchant_id,
            "data": {
                "revenue": data.get("revenue_formatted"),
                "total_orders": data.get("total_orders"),
                "gross_margin_percent": data.get("gross_margin_percent"),
                "aov": data.get("aov_formatted")
            }
        }

    elif action == "get_top_products":
        limit = min(max(payload.limit or 3, 1), 20)
        products = await BusinessIntelligenceService.get_top_selling_products(db, merchant_id, limit=limit)
        return {
            "status": "success",
            "action": action,
            "merchant_id": merchant_id,
            "data": {
                "top_products": products,
                "count": len(products)
            }
        }

    elif action == "get_product_stock":
        sku = (payload.sku or "VAST-SH-03").strip()
        p_stmt = select(Product).where(Product.merchant_id == merchant_id, Product.sku == sku)
        product = (await db.execute(p_stmt)).scalars().first()
        if not product:
            return {
                "status": "failure",
                "action": action,
                "merchant_id": merchant_id,
                "message": f"Product with SKU '{sku}' not found for merchant '{merchant_id}'."
            }

        from services.agent.doctor_tools import execute_doctor_tool
        stock_data = await execute_doctor_tool(db, merchant_id, "get_product_stock", {"sku_or_name": sku})
        return {
            "status": "success",
            "action": action,
            "merchant_id": merchant_id,
            "data": stock_data
        }

    elif action == "get_profit_summary":
        summary = await BusinessIntelligenceService.get_profit_summary(db, merchant_id)
        return {
            "status": "success",
            "action": action,
            "merchant_id": merchant_id,
            "data": {
                "gross_profit_formatted": summary.get("gross_profit_formatted"),
                "gross_margin_percent": summary.get("gross_margin_percent"),
                "total_revenue_formatted": summary.get("total_revenue_formatted"),
                "policy_margin_floor_percent": summary.get("policy_margin_floor_percent"),
                "is_above_policy_floor": summary.get("is_above_policy_floor"),
                "hero_products_count": len(summary.get("hero_products", []))
            }
        }

    else:
        return {
            "status": "failure",
            "action": action,
            "merchant_id": merchant_id,
            "message": f"Unknown action: {action}. Supported actions: get_daily_sales, get_top_products, get_product_stock, get_profit_summary"
        }


@router.post("/webhook")
async def handle_gnani_post_call_webhook(
    event: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    _auth: bool = Depends(verify_gnani_webhook_auth)
):
    """Receive post-call webhook from Gnani Agent Builder to preserve session continuity."""
    logger.info("gnani_post_call_webhook_received", event_keys=list(event.keys()))

    conversation_id = str(event.get("conversation_id") or event.get("conversationId") or event.get("call_id") or "").strip()
    transcript = event.get("transcript") or event.get("utteranceAnalytics") or []
    merchant_id = event.get("merchant_id", "merch_atlas_travel")

    # 1. Enforce Merchant Isolation
    m_stmt = select(Merchant).where(Merchant.id == merchant_id)
    merchant = (await db.execute(m_stmt)).scalars().first()
    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Merchant '{merchant_id}' not found."
        )

    # 2. Duplicate Webhook Protection
    if conversation_id:
        existing_session_stmt = select(VoiceConversationSession).where(
            VoiceConversationSession.merchant_id == merchant_id,
            VoiceConversationSession.title.contains(conversation_id[:8])
        )
        existing = (await db.execute(existing_session_stmt)).scalars().first()
        if existing:
            logger.info("gnani_webhook_duplicate_ignored", conversation_id=conversation_id, existing_session_id=existing.id)
            return {
                "status": "duplicate_ignored",
                "session_id": existing.id,
                "message": "Conversation was already processed."
            }

    # 3. If transcript is provided, record into session memory
    if conversation_id and transcript:
        try:
            session = await SessionManager.create_session(
                db=db,
                merchant_id=merchant_id,
                title=f"Gnani Agent Call ({conversation_id[:8]})"
            )
            for turn in transcript:
                role = "user" if turn.get("role") in ("user", "caller") else "assistant"
                content = turn.get("content") or turn.get("text") or ""
                if content:
                    await SessionManager.add_turn(
                        db=db,
                        session_id=session.id,
                        merchant_id=merchant_id,
                        role=role,
                        content=content
                    )
            return {"status": "success", "session_id": session.id, "turns_saved": len(transcript)}
        except Exception as e:
            logger.warning("webhook_session_save_error", error=str(e))

    return {"status": "received", "conversation_id": conversation_id}
