"""Webhook Ingestion Service with Cryptographic Verification and Atomic Deduplication."""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import settings
from domain.models import Order, Payment, ProcessedWebhookEvent, AuditEvent, ExecutionRecord
from apps.api.core.state_machine import TransactionState, StateMachine
from services.razorpay.webhooks import verify_webhook_signature, parse_webhook_payload
from services.razorpay.errors import RazorpaySignatureVerificationError
from services.execution.concurrency import InventoryReservationManager


class WebhookService:
    """Handles verification, atomic deduplication, and transactional persistence of webhooks."""

    def __init__(
        self,
        webhook_secret: Optional[str] = None,
        reservation_mgr: Optional[InventoryReservationManager] = None
    ):
        self.webhook_secret = webhook_secret or settings.RAZORPAY_WEBHOOK_SECRET
        self.reservation_mgr = reservation_mgr or InventoryReservationManager()

    async def process_webhook(
        self,
        raw_body: bytes,
        signature: Optional[str],
        event_id: Optional[str],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Process inbound webhook with HMAC verification and idempotency."""
        # 1. Cryptographic Signature Verification
        is_valid = verify_webhook_signature(
            raw_body=raw_body,
            signature_header=signature,
            webhook_secret=self.webhook_secret
        )

        if not is_valid:
            # Audit signature failure
            audit_rej = AuditEvent(
                entity_type="WEBHOOK",
                entity_id=event_id or "unknown",
                actor="WEBHOOK_SERVICE",
                action="webhook_rejected",
                payload={"reason": "Invalid or missing HMAC SHA-256 signature"}
            )
            db.add(audit_rej)
            await db.commit()
            raise RazorpaySignatureVerificationError("Invalid webhook signature.")

        # 2. Parse Payload
        parsed = parse_webhook_payload(raw_body)
        raw_dict = json.loads(raw_body.decode("utf-8"))
        effective_event_id = event_id or raw_dict.get("event_id") or f"evt_derived_{hash(raw_body)}"

        # 3. Deduplication Check via Database
        stmt = select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == effective_event_id)
        result = await db.execute(stmt)
        existing_event = result.scalar_one_or_none()

        if existing_event:
            # Event has already been processed idempotently
            audit_dup = AuditEvent(
                entity_type="WEBHOOK",
                entity_id=effective_event_id,
                actor="WEBHOOK_SERVICE",
                action="webhook_duplicate",
                payload={"event_type": parsed.event, "status": "skipped"}
            )
            db.add(audit_dup)
            await db.commit()
            return {"status": "already_processed", "event_id": effective_event_id}

        # 4. Atomic Transaction: Record event and transition order/payment
        try:
            # Mark event processed
            processed_record = ProcessedWebhookEvent(
                event_id=effective_event_id,
                event_type=parsed.event,
                payload=raw_dict
            )
            db.add(processed_record)

            # Audit verified arrival
            audit_ver = AuditEvent(
                entity_type="WEBHOOK",
                entity_id=effective_event_id,
                actor="WEBHOOK_SERVICE",
                action="webhook_verified",
                payload={"event_type": parsed.event}
            )
            db.add(audit_ver)

            # Handle Event Specific Logic
            payload_data = parsed.payload
            event_type = parsed.event

            # Extract order and payment entities where present
            order_payload = payload_data.get("order", {}).get("entity", {})
            payment_payload = payload_data.get("payment", {}).get("entity", {})

            target_order_id = order_payload.get("id") or payment_payload.get("order_id")

            if target_order_id:
                # Find matching internal order
                order_stmt = select(Order).where(Order.razorpay_order_id == target_order_id)
                order_res = await db.execute(order_stmt)
                internal_order = order_res.scalar_one_or_none()

                if internal_order:
                    current_state = TransactionState(internal_order.status)

                    if event_type in ("order.paid", "payment.captured"):
                        # Ensure we do not regress or violate state machine
                        if current_state != TransactionState.PAID and current_state != TransactionState.FINALIZED:
                            internal_order.status = TransactionState.PAID.value

                        # Upsert payment record if present
                        pmt_id = payment_payload.get("id")
                        if pmt_id:
                            pmt_stmt = select(Payment).where(Payment.id == pmt_id)
                            pmt_res = await db.execute(pmt_stmt)
                            existing_payment = pmt_res.scalar_one_or_none()

                            if not existing_payment:
                                new_payment = Payment(
                                    id=pmt_id,
                                    order_id=internal_order.id,
                                    amount_paise=payment_payload.get("amount", internal_order.amount_paise),
                                    currency=payment_payload.get("currency", "INR"),
                                    status="captured",
                                    method=payment_payload.get("method"),
                                    captured_at=datetime.now(timezone.utc)
                                )
                                db.add(new_payment)
                            else:
                                existing_payment.status = "captured"

                        # Audit transaction finalization
                        audit_final = AuditEvent(
                            entity_type="ORDER",
                            entity_id=internal_order.id,
                            actor="WEBHOOK_SERVICE",
                            action="transaction_finalized",
                            payload={
                                "razorpay_order_id": target_order_id,
                                "event_id": effective_event_id,
                                "event_type": event_type,
                                "final_status": "PAID"
                            }
                        )
                        db.add(audit_final)

                    elif event_type == "payment.failed":
                        # Only mark failed if not already in paid/terminal state
                        if current_state != TransactionState.PAID and current_state != TransactionState.FINALIZED:
                            internal_order.status = TransactionState.FAILED.value

                        pmt_id = payment_payload.get("id")
                        if pmt_id:
                            fail_payment = Payment(
                                id=pmt_id,
                                order_id=internal_order.id,
                                amount_paise=payment_payload.get("amount", internal_order.amount_paise),
                                currency=payment_payload.get("currency", "INR"),
                                status="failed",
                                error_code=payment_payload.get("error_code"),
                                error_description=payment_payload.get("error_description"),
                                method=payment_payload.get("method")
                            )
                            db.add(fail_payment)

                        audit_fail = AuditEvent(
                            entity_type="ORDER",
                            entity_id=internal_order.id,
                            actor="WEBHOOK_SERVICE",
                            action="payment_failed",
                            payload={
                                "razorpay_order_id": target_order_id,
                                "event_id": effective_event_id,
                                "error_code": payment_payload.get("error_code")
                            }
                        )
                        db.add(audit_fail)

                # Inventory Reservation Lifecycle Integration
                exec_stmt = select(ExecutionRecord).where(ExecutionRecord.order_id == internal_order.id)
                exec_res = await db.execute(exec_stmt)
                exec_record = exec_res.scalar_one_or_none()

                if exec_record:
                    quantities = exec_record.audit_metadata.get("quantities", {}) if exec_record.audit_metadata else {}
                    if event_type in ("order.paid", "payment.captured"):
                        if exec_record.status != "PAID":
                            exec_record.status = "PAID"
                            if quantities:
                                await self.reservation_mgr.commit_inventory_deduction(db, quantities)
                    elif event_type == "payment.failed":
                        if exec_record.status not in ("PAID", "PAYMENT_FAILED"):
                            exec_record.status = "PAYMENT_FAILED"
                            if quantities:
                                await self.reservation_mgr.release_inventory(db, quantities)

                    # Phase 9.3: Outcome, Feedback & Recovery Loop Progression
                    try:
                        from services.outcome.service import OutcomeFeedbackService
                        await OutcomeFeedbackService.process_webhook_outcome(
                            db=db,
                            order_id=internal_order.id,
                            event_type=event_type,
                            payment_id=payment_payload.get("id")
                        )
                    except Exception as exc:
                        structlog.get_logger().warning("webhook_outcome_processing_deferred", order_id=internal_order.id, error=str(exc))

            # Commit all changes atomically
            await db.commit()
            return {"status": "processed", "event_id": effective_event_id, "event_type": event_type}

        except Exception:
            await db.rollback()
            raise
