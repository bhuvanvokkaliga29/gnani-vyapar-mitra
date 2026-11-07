"""Execution boundary tool for MCP: request_checkout.

Contract: mcp-commerce/v1

FINANCIAL SAFETY INVARIANTS:
1. The external AI buyer agent can only REQUEST execution.
2. Only deterministic backend code (DecisionExecutionBoundaryService + ExecutionGate) AUTHORIZES execution.
3. NEVER directly calls Razorpay or mutates financial state.
4. Idempotent and replay-resistant via the execution boundary ledger.
5. Cross-tenant access is immediately blocked.
6. Re-resolves authoritative decision state from the database.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import AsyncSessionLocal
from domain.models import CanonicalDecisionRecord
from services.boundary.service import DecisionExecutionBoundaryService
from services.boundary.schemas import DecisionExecuteRequest, ExecutionBoundaryStatus
from services.boundary.errors import DecisionNotFoundError, DecisionTenantViolationError, DecisionStaleError
from services.mcp.schemas import McpCapability, BuyerSafeCheckoutResponse
from services.mcp.auth import check_capability, get_current_auth_context
from services.mcp.firewall import BuyerResponseFirewall
from services.mcp.errors import (
    McpInvalidOfferError,
    McpOfferExpiredError,
    McpTenantMismatchError,
    McpSafetyRejectionError
)

logger = structlog.get_logger()


def resolve_decision_id_from_offer(offer_id: str) -> str:
    """Derive internal decision_id from external offer_id."""
    clean = offer_id.strip()
    if clean.startswith("off_"):
        candidate = clean[4:]
        if candidate.startswith("dec_"):
            return candidate
        return f"dec_{candidate}"
    elif clean.startswith("dec_"):
        return clean
    return f"dec_{clean}"


async def request_checkout(
    offer_id: str,
    idempotency_key: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> BuyerSafeCheckoutResponse:
    """Submit a formal checkout request for an accepted commercial offer.
    
    Flow:
        request_checkout
        -> resolve decision_id
        -> verify caller tenant scope
        -> verify offer freshness TTL
        -> verify active policy
        -> run deterministic safety validation
        -> authorize execution (ExecutionGate)
        -> reserve inventory
        -> create Razorpay Test Mode order
        -> persist boundary execution record
        -> return BuyerSafeCheckoutResponse
    
    Args:
        offer_id: Authoritative offer identifier returned by get_offer (e.g. off_dec_...).
        idempotency_key: Optional client-provided idempotency key for safe retries.
        db: Optional database session for test execution.
        
    Returns:
        BuyerSafeCheckoutResponse with status, order ID, and test checkout link.
        
    Raises:
        McpInvalidOfferError: If offer is not found or has NO_OFFER strategy.
        McpTenantMismatchError: If offer belongs to another merchant.
        McpOfferExpiredError: If offer has exceeded freshness TTL.
    """
    check_capability(McpCapability.CHECKOUT_REQUEST)
    identity = get_current_auth_context()
    merchant_id = identity.merchant_id

    decision_id = resolve_decision_id_from_offer(offer_id)

    async def _execute(session: AsyncSession) -> BuyerSafeCheckoutResponse:
        # 1. Authoritative lookup of CanonicalDecisionRecord
        stmt = select(CanonicalDecisionRecord).where(CanonicalDecisionRecord.id == decision_id)
        decision_rec = (await session.execute(stmt)).scalar_one_or_none()

        if not decision_rec:
            logger.warn("mcp_checkout_decision_not_found", offer_id=offer_id, decision_id=decision_id)
            raise McpInvalidOfferError(
                f"Offer '{offer_id}' (decision: '{decision_id}') not found.",
                details={"offer_id": offer_id, "decision_id": decision_id}
            )

        # 2. Strict Tenant Scope Check
        if decision_rec.merchant_id != merchant_id:
            logger.error(
                "mcp_checkout_cross_tenant_attempt",
                offer_id=offer_id,
                decision_merchant=decision_rec.merchant_id,
                caller_merchant=merchant_id
            )
            raise McpTenantMismatchError(
                f"Access denied: Offer belongs to merchant '{decision_rec.merchant_id}', "
                f"caller is authorized for '{merchant_id}'.",
                details={
                    "offer_id": offer_id,
                    "decision_merchant": decision_rec.merchant_id,
                    "caller_merchant": merchant_id
                }
            )

        # 3. Reject non-executable NO_OFFER strategies immediately
        if (decision_rec.selected_strategy_type or "").upper() == "NO_OFFER":
            logger.warn("mcp_checkout_no_offer_rejected", offer_id=offer_id)
            raise McpInvalidOfferError(
                f"Offer '{offer_id}' has strategy 'NO_OFFER' and cannot be executed.",
                details={"offer_id": offer_id, "strategy": "NO_OFFER"}
            )

        # 4. Dispatch to authoritative Phase 9.2 Execution Boundary
        boundary_req = DecisionExecuteRequest(
            merchant_id=merchant_id,
            idempotency_key=idempotency_key or f"idem_{identity.buyer_agent_id}_{offer_id}"
        )

        try:
            exec_resp = await DecisionExecutionBoundaryService.execute_decision(
                session,
                decision_id=decision_id,
                request=boundary_req
            )
        except DecisionStaleError as exc:
            raise McpOfferExpiredError(str(exc))
        except DecisionTenantViolationError as exc:
            raise McpTenantMismatchError(str(exc))

        # Check if boundary rejected due to staleness
        if exec_resp.boundary_status == ExecutionBoundaryStatus.DECISION_STALE:
            raise McpOfferExpiredError(
                f"Offer '{offer_id}' has expired and can no longer be checked out.",
                details={"offer_id": offer_id, "rejection_reasons": exec_resp.rejection_reasons}
            )

        safe_checkout = BuyerResponseFirewall.sanitize_checkout(exec_resp)

        logger.info(
            "mcp_checkout_completed",
            offer_id=offer_id,
            status=safe_checkout.status,
            order_id=safe_checkout.order_id,
            is_duplicate=safe_checkout.is_duplicate
        )
        return safe_checkout

    if db is not None:
        return await _execute(db)
    async with AsyncSessionLocal() as session:
        return await _execute(session)
