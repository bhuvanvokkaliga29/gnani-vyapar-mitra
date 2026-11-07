"""Order status tracking tool for MCP: get_order_status.

Contract: mcp-commerce/v1

INVARIANTS:
1. Reuses OrderService (services/order_service.py).
2. Verifies tenant scope by correlating order.decision_id to CanonicalDecisionRecord.merchant_id.
3. Output is filtered through BuyerResponseFirewall. Zero internal merchant data.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import AsyncSessionLocal
from domain.models import Order, CanonicalDecisionRecord
from services.order_service import OrderService
from services.mcp.schemas import McpCapability, BuyerSafeOrderStatusView
from services.mcp.auth import check_capability, get_current_auth_context
from services.mcp.firewall import BuyerResponseFirewall
from services.mcp.errors import McpOrderNotFoundError, McpTenantMismatchError

logger = structlog.get_logger()
_order_service = OrderService()


async def get_order_status(
    order_id: Optional[str] = None,
    razorpay_order_id: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> BuyerSafeOrderStatusView:
    """Retrieve the authoritative transaction and fulfillment status of an order.
    
    Args:
        order_id: Internal order identifier (e.g. ord_...).
        razorpay_order_id: Razorpay order identifier (e.g. order_...).
        db: Optional database session for test execution.
        
    Returns:
        BuyerSafeOrderStatusView with current status (e.g. ORDER_CREATED, PAID, FAILED).
        
    Raises:
        McpOrderNotFoundError: If the order cannot be found.
        McpTenantMismatchError: If the order belongs to a different merchant tenant.
    """
    check_capability(McpCapability.ORDER_STATUS_READ)
    identity = get_current_auth_context()
    merchant_id = identity.merchant_id

    if not order_id and not razorpay_order_id:
        raise ValueError("Either 'order_id' or 'razorpay_order_id' must be provided.")

    async def _execute(session: AsyncSession) -> BuyerSafeOrderStatusView:
        # 1. Fetch order record
        order = None
        if order_id:
            order = await _order_service.get_order_by_id(session, order_id)
        elif razorpay_order_id:
            order = await _order_service.get_order_by_razorpay_id(session, razorpay_order_id)

        if not order:
            logger.warn("mcp_order_not_found", order_id=order_id, razorpay_order_id=razorpay_order_id)
            raise McpOrderNotFoundError(
                f"Order not found (order_id='{order_id}', razorpay_order_id='{razorpay_order_id}').",
                details={"order_id": order_id, "razorpay_order_id": razorpay_order_id}
            )

        # 2. Authoritative Tenant Isolation Check via CanonicalDecisionRecord
        if order.decision_id:
            stmt = select(CanonicalDecisionRecord).where(CanonicalDecisionRecord.id == order.decision_id)
            decision_rec = (await session.execute(stmt)).scalar_one_or_none()
            if decision_rec and decision_rec.merchant_id != merchant_id:
                logger.error(
                    "mcp_order_cross_tenant_access_blocked",
                    order_id=order.id,
                    order_merchant=decision_rec.merchant_id,
                    caller_merchant=merchant_id
                )
                raise McpTenantMismatchError(
                    f"Access denied: Order '{order.id}' belongs to merchant '{decision_rec.merchant_id}', "
                    f"not '{merchant_id}'.",
                    details={
                        "order_id": order.id,
                        "order_merchant": decision_rec.merchant_id,
                        "caller_merchant": merchant_id
                    }
                )

        return BuyerResponseFirewall.sanitize_order_status(order)

    if db is not None:
        return await _execute(db)
    async with AsyncSessionLocal() as session:
        return await _execute(session)
