"""Offer discovery tool for MCP: get_offer.

Contract: mcp-commerce/v1

INVARIANTS:
1. Reuses CanonicalDecisionRuntime (services/runtime/service.py).
2. Generates canonical offer using authoritative Merchant Policy Agent.
3. Every response is filtered through BuyerResponseFirewall. Zero internal economics leak.
"""

from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import AsyncSessionLocal
from domain.intent_schemas import BuyerIntent
from services.commerce_service import CommerceService
from services.runtime.service import CanonicalDecisionRuntime
from services.runtime.schemas import CanonicalDecisionRequest
from services.mcp.schemas import McpCapability, BuyerSafeOfferView
from services.mcp.auth import check_capability, get_current_auth_context
from services.mcp.firewall import BuyerResponseFirewall

logger = structlog.get_logger()
_commerce_service = CommerceService()


async def get_offer(
    message: Optional[str] = None,
    buyer_intent: Optional[Dict[str, Any]] = None,
    opportunity_id: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> BuyerSafeOfferView:
    """Generate a commercial offer tailored to the buyer's intent.
    
    Flow:
        BuyerIntent -> MerchantCommerceContext -> Policy Agent -> Safety Validator -> DecisionEnvelope -> BuyerSafeOfferView
    
    Args:
        message: Natural language intent text (e.g. 'Looking for a travel backpack under 7500').
        buyer_intent: Optional pre-parsed structured buyer intent dictionary.
        opportunity_id: Optional opportunity correlation identifier.
        db: Optional database session for test execution.
        
    Returns:
        BuyerSafeOfferView with authoritative terms and offer_id for checkout.
    """
    check_capability(McpCapability.OFFER_READ)
    identity = get_current_auth_context()
    merchant_id = identity.merchant_id

    # Parse structured BuyerIntent if dictionary provided
    parsed_intent = None
    if buyer_intent:
        try:
            parsed_intent = BuyerIntent.model_validate(buyer_intent)
        except Exception as exc:
            logger.warn("mcp_intent_dict_parse_failed", error=str(exc))

    decision_req = CanonicalDecisionRequest(
        merchant_id=merchant_id,
        opportunity_id=opportunity_id,
        buyer_intent=parsed_intent,
        raw_prompt=message if not parsed_intent else None,
        request_id=f"mcp_req_{identity.buyer_agent_id}"
    )

    async def _execute(session: AsyncSession) -> BuyerSafeOfferView:
        # 1. Execute canonical decision runtime
        envelope = await CanonicalDecisionRuntime.decide(session, decision_req)

        # 2. Build product catalog map for item details
        products = await _commerce_service.list_products(session, merchant_id, active_only=False)
        catalog_map = {p.id: p for p in products}

        # 3. Route through Buyer Response Firewall
        safe_offer = BuyerResponseFirewall.sanitize_offer(envelope, product_catalog_map=catalog_map)

        logger.info(
            "mcp_offer_generated",
            merchant_id=merchant_id,
            decision_id=envelope.decision_id,
            offer_id=safe_offer.offer_id,
            strategy_type=safe_offer.strategy_type,
            price_paise=safe_offer.offered_price_paise,
            is_executable=safe_offer.is_executable
        )
        return safe_offer

    if db is not None:
        return await _execute(db)
    async with AsyncSessionLocal() as session:
        return await _execute(session)
