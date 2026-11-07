"""Buyer Intent evaluation tool for MCP: evaluate_buyer_intent.

Contract: mcp-commerce/v1

INVARIANTS:
1. Reuses IntentExtractor (services/intent/extractor.py).
2. Neutralizes prompt injections before extraction.
3. Does not select products, price, or authorize transactions.
"""

from typing import Optional, Dict, Any
import structlog

from services.intent.extractor import IntentExtractor
from services.mcp.schemas import McpCapability, BuyerSafeIntentResponse
from services.mcp.auth import check_capability, get_current_auth_context

logger = structlog.get_logger()
_intent_extractor = IntentExtractor()


async def evaluate_buyer_intent(message: str) -> BuyerSafeIntentResponse:
    """Analyze natural language buyer text and extract structured commercial intent.
    
    Args:
        message: Natural language prompt (e.g. 'I need a travel backpack under ₹7,500').
        
    Returns:
        BuyerSafeIntentResponse containing normalized category, budget, and constraints.
    """
    check_capability(McpCapability.INTENT_EVALUATE)
    identity = get_current_auth_context()

    # 1. Sanitize prompt and check for adversarial injections
    sanitized_text, injection_detected = _intent_extractor.sanitize_and_check_injection(message)

    # 2. Extract structured BuyerIntent using authoritative Phase 3 extractor
    intent = _intent_extractor.parse_utterance(sanitized_text)

    # 3. Format hard requirements, preferences, and exclusions as readable strings
    req_strings = [f"{r.attribute} {r.operator.value} {r.value}" for r in (intent.requirements or [])]
    pref_strings = [f"{p.attribute}: {p.preferred_value}" for p in (intent.preferences or [])]
    excl_strings = [f"{e.excluded_type}: {e.value}" for e in (intent.exclusions or [])]

    budget_paise = None
    if intent.budget:
        budget_paise = intent.budget.max_amount_paise or intent.budget.amount_paise
    confidence_val = intent.confidence.value if hasattr(intent.confidence, "value") else str(intent.confidence)

    logger.info(
        "mcp_buyer_intent_evaluated",
        buyer_agent_id=identity.buyer_agent_id,
        category=intent.category,
        budget_paise=budget_paise,
        injection_neutralized=injection_detected
    )

    return BuyerSafeIntentResponse(
        category=intent.category,
        use_case=intent.use_case,
        budget_paise=budget_paise,
        quantity=intent.quantity or 1,
        requirements=req_strings,
        preferences=pref_strings,
        exclusions=excl_strings,
        confidence=confidence_val,
        prompt_injection_neutralized=injection_detected
    )
