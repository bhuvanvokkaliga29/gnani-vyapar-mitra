"""Application Order Service managing safe creation and lifecycle transitions."""

import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models import Order, AuditEvent
from apps.api.core.state_machine import TransactionState
from services.razorpay.orders import RazorpayOrderService
from services.razorpay.reconciliation import ReconciliationService
from services.razorpay.errors import RazorpayTimeoutError, RazorpayNetworkError, RazorpayError


class OrderService:
    """Coordinates local order persistence, Razorpay order creation, and timeout safety."""

    def __init__(
        self,
        razorpay_orders: Optional[RazorpayOrderService] = None,
        reconciler: Optional[ReconciliationService] = None
    ):
        self.razorpay_orders = razorpay_orders or RazorpayOrderService()
        self.reconciler = reconciler or ReconciliationService(order_service=self.razorpay_orders)

    async def create_order(
        self,
        db: AsyncSession,
        amount_paise: int,
        currency: str = "INR",
        notes: Optional[Dict[str, Any]] = None,
        decision_id: Optional[str] = None
    ) -> Order:
        """Create an order with guaranteed pre-allocation and timeout reconciliation."""
        if amount_paise <= 0:
            raise ValueError("Order amount in paise must be strictly positive.")

        # 1. Generate internal identifiers
        order_id = f"ord_{uuid.uuid4().hex[:16]}"
        dec_id = decision_id or f"dec_{uuid.uuid4().hex[:20]}"
        receipt_id = dec_id[:40]  # Max 40 chars per Razorpay spec

        # 2. Persist local CREATION_PENDING state before outbound call
        order = Order(
            id=order_id,
            decision_id=dec_id,
            amount_paise=amount_paise,
            currency=currency.upper(),
            receipt=receipt_id,
            status=TransactionState.CREATION_PENDING.value,
            notes=notes or {}
        )
        db.add(order)

        audit_req = AuditEvent(
            entity_type="ORDER",
            entity_id=order_id,
            actor="ORDER_SERVICE",
            action="order_creation_requested",
            payload={"amount_paise": amount_paise, "receipt": receipt_id}
        )
        db.add(audit_req)
        await db.commit()
        await db.refresh(order)

        # 3. Call Razorpay API
        try:
            rzp_response = await self.razorpay_orders.create_order(
                amount_paise=amount_paise,
                receipt=receipt_id,
                currency=currency,
                notes=notes
            )
            order.razorpay_order_id = rzp_response.id
            order.status = TransactionState.ORDER_CREATED.value

            audit_success = AuditEvent(
                entity_type="ORDER",
                entity_id=order_id,
                actor="ORDER_SERVICE",
                action="order_creation_succeeded",
                payload={"razorpay_order_id": rzp_response.id, "status": order.status}
            )
            db.add(audit_success)
            await db.commit()
            await db.refresh(order)
            return order

        except (RazorpayTimeoutError, RazorpayNetworkError) as exc:
            # 4. Mandatory Failure Case: Indeterminate state -> Reconcile
            order.status = TransactionState.UNCERTAIN.value
            audit_timeout = AuditEvent(
                entity_type="ORDER",
                entity_id=order_id,
                actor="ORDER_SERVICE",
                action="order_creation_timeout",
                payload={"error": str(exc), "status": "UNCERTAIN"}
            )
            db.add(audit_timeout)
            await db.commit()

            # Attempt immediate reconciliation
            reconciled = await self.reconciler.reconcile_order(order_id, db)
            return reconciled

        except RazorpayError as exc:
            # 5. Definitive API failure
            order.status = TransactionState.FAILED.value
            audit_fail = AuditEvent(
                entity_type="ORDER",
                entity_id=order_id,
                actor="ORDER_SERVICE",
                action="order_creation_failed",
                payload={"error": str(exc), "status": "FAILED"}
            )
            db.add(audit_fail)
            await db.commit()
            raise

    async def get_order_by_id(self, db: AsyncSession, order_id: str) -> Optional[Order]:
        """Fetch internal order with its associated payments."""
        stmt = select(Order).where(Order.id == order_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_order_by_razorpay_id(self, db: AsyncSession, razorpay_order_id: str) -> Optional[Order]:
        """Fetch internal order by Razorpay order ID."""
        stmt = select(Order).where(Order.razorpay_order_id == razorpay_order_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_orders(self, db: AsyncSession, limit: int = 50, offset: int = 0) -> List[Order]:
        """Fetch list of orders with pagination."""
        stmt = select(Order).order_by(Order.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())
