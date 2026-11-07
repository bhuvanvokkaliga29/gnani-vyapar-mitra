"""Reconciliation Service for Resolving Uncertain Order and Payment States."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import structlog
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models import Order, Payment, AuditEvent, ExecutionRecord
from apps.api.core.state_machine import TransactionState, StateMachine
from services.razorpay.orders import RazorpayOrderService

logger = structlog.get_logger()


class ReconciliationService:
    """Resolves indeterminate transaction states by reconciling against Razorpay APIs."""

    def __init__(self, order_service: Optional[RazorpayOrderService] = None):
        self.order_service = order_service or RazorpayOrderService()

    async def reconcile_order(self, order_id: str, db: AsyncSession) -> Order:
        """Reconcile the state of an internal order against Razorpay."""
        # 1. Fetch internal order by internal ID or Razorpay order ID
        stmt = select(Order).where(or_(Order.id == order_id, Order.razorpay_order_id == order_id))
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            raise ValueError(f"Order '{order_id}' not found for reconciliation.")

        # Record start of reconciliation
        audit_start = AuditEvent(
            entity_type="ORDER",
            entity_id=order.id,
            actor="RECONCILIATION_SERVICE",
            action="order_reconciliation_started",
            payload={"current_status": order.status, "receipt": order.receipt}
        )
        db.add(audit_start)

        # 2. Case A: Order timed out before obtaining razorpay_order_id
        if not order.razorpay_order_id or order.status == TransactionState.UNCERTAIN.value:
            matched = await self.order_service.find_order_by_receipt(order.receipt)
            if matched:
                order.razorpay_order_id = matched.id
                order.status = TransactionState.ORDER_CREATED.value
                audit_success = AuditEvent(
                    entity_type="ORDER",
                    entity_id=order.id,
                    actor="RECONCILIATION_SERVICE",
                    action="order_reconciliation_completed",
                    payload={"razorpay_order_id": matched.id, "resolved_status": order.status}
                )
                db.add(audit_success)
            else:
                # Confirmed order was never registered on Razorpay
                order.status = TransactionState.FAILED.value
                audit_fail = AuditEvent(
                    entity_type="ORDER",
                    entity_id=order.id,
                    actor="RECONCILIATION_SERVICE",
                    action="order_reconciliation_failed",
                    payload={"reason": "Order verified absent on Razorpay"}
                )
                db.add(audit_fail)

            await db.commit()
            await db.refresh(order)
            return order

        # 3. Case B: Order has razorpay_order_id, check for missing/delayed payment webhook
        if order.status in (TransactionState.ORDER_CREATED.value, TransactionState.PAYMENT_PENDING.value):
            payments_coll = await self.order_service.get_order_payments(order.razorpay_order_id)
            captured_payment = None
            for p in payments_coll.items:
                if p.status == "captured" or p.captured:
                    captured_payment = p
                    break

            if captured_payment:
                order.status = TransactionState.PAID.value

                # Persist payment entity
                pmt_stmt = select(Payment).where(Payment.id == captured_payment.id)
                pmt_res = await db.execute(pmt_stmt)
                existing_pmt = pmt_res.scalar_one_or_none()

                if not existing_pmt:
                    new_pmt = Payment(
                        id=captured_payment.id,
                        order_id=order.id,
                        amount_paise=captured_payment.amount,
                        currency=captured_payment.currency,
                        status="captured",
                        method=captured_payment.method,
                        captured_at=datetime.now(timezone.utc)
                    )
                    db.add(new_pmt)
                else:
                    existing_pmt.status = "captured"

                audit_paid = AuditEvent(
                    entity_type="ORDER",
                    entity_id=order.id,
                    actor="RECONCILIATION_SERVICE",
                    action="order_reconciled_via_api",
                    payload={"payment_id": captured_payment.id, "new_status": "PAID"}
                )
                db.add(audit_paid)

                # Inventory Reservation Lifecycle Integration
                exec_stmt = select(ExecutionRecord).where(ExecutionRecord.order_id == order.id)
                exec_res = await db.execute(exec_stmt)
                exec_record = exec_res.scalar_one_or_none()

                if exec_record:
                    quantities = exec_record.audit_metadata.get("quantities", {}) if exec_record.audit_metadata else {}
                    if exec_record.status != "PAID":
                        exec_record.status = "PAID"
                        if quantities:
                            from services.execution.concurrency import InventoryReservationManager
                            reservation_mgr = InventoryReservationManager()
                            await reservation_mgr.commit_inventory_deduction(db, quantities)

                # Phase 9.3: Outcome, Feedback & Recovery Loop Progression
                try:
                    from services.outcome.service import OutcomeFeedbackService
                    await OutcomeFeedbackService.process_webhook_outcome(
                        db=db,
                        order_id=order.id,
                        event_type="payment.captured",
                        payment_id=captured_payment.id
                    )
                except Exception as exc:
                    logger.warning("reconciliation_outcome_processing_deferred", order_id=order.id, error=str(exc))

                await db.commit()
                await db.refresh(order)

        return order
