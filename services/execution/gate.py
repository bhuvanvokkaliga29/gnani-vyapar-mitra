"""ExecutionGate: The authoritative boundary between AI proposals and financial execution."""

import uuid
import time
from typing import Optional, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from domain.models import ExecutionRecord, Order, AuditEvent
from services.commerce_service import CommerceService, MerchantNotFoundError
from services.order_service import OrderService
from services.execution.schemas import (
    PolicyExecuteRequest,
    PolicyExecuteResponse,
    ExecutionAuthorization,
    ExecutionState,
    ExecutionRejectionReason
)
from services.execution.validator import ExecutionValidator
from services.execution.concurrency import InventoryReservationManager

logger = structlog.get_logger()


class ExecutionGate:
    """Orchestrates deterministic revalidation, atomic inventory reservation,
    and safe Razorpay Test Mode order execution."""

    def __init__(
        self,
        commerce_service: Optional[CommerceService] = None,
        order_service: Optional[OrderService] = None,
        validator: Optional[ExecutionValidator] = None,
        reservation_mgr: Optional[InventoryReservationManager] = None
    ):
        self.commerce_service = commerce_service or CommerceService()
        self.order_service = order_service or OrderService()
        self.validator = validator or ExecutionValidator()
        self.reservation_mgr = reservation_mgr or InventoryReservationManager()

    async def execute_policy(
        self,
        db: AsyncSession,
        request: PolicyExecuteRequest
    ) -> PolicyExecuteResponse:
        """Execute a validated commercial policy proposal against fresh merchant state."""
        start_time = time.perf_counter()
        auth_id = f"auth_{uuid.uuid4().hex[:12]}"
        exec_id = f"exec_{uuid.uuid4().hex[:16]}"

        # 1. Determine Candidate ID and Idempotency Key
        selected_cand_id = request.candidate_id
        if not selected_cand_id and request.proposal and request.proposal.selected_candidate:
            selected_cand_id = request.proposal.selected_candidate.candidate_id

        if not selected_cand_id:
            selected_cand_id = "unknown_candidate"

        idempotency_key = request.idempotency_key or f"idem_{request.merchant_id}_{request.proposal_id}_{selected_cand_id}"

        # 2. Check for Duplicate Execution (Idempotency Ledger)
        existing_stmt = select(ExecutionRecord).where(ExecutionRecord.idempotency_key == idempotency_key)
        existing_exec = (await db.execute(existing_stmt)).scalar_one_or_none()

        if existing_exec:
            logger.info("idempotent_execution_replayed", idempotency_key=idempotency_key, exec_id=existing_exec.id)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            auth_dto = ExecutionAuthorization(
                authorization_id=f"auth_{existing_exec.id[:12]}",
                proposal_id=existing_exec.proposal_id,
                merchant_id=existing_exec.merchant_id,
                candidate_id=existing_exec.candidate_id,
                authorized_amount_paise=existing_exec.authorized_amount_paise,
                currency=existing_exec.currency,
                status=existing_exec.status,
                rejection_reasons=existing_exec.rejection_reasons or [],
                recalculated_economics=existing_exec.recalculated_economics,
                receipt=existing_exec.receipt,
                idempotency_key=existing_exec.idempotency_key,
                authorized_at=existing_exec.created_at
            )
            return PolicyExecuteResponse(
                execution_id=existing_exec.id,
                status=ExecutionState(existing_exec.status) if existing_exec.status in ExecutionState._value2member_map_ else ExecutionState.ORDER_CREATED,
                authorization=auth_dto,
                order_id=existing_exec.order_id,
                razorpay_order_id=existing_exec.razorpay_order_id,
                authorized_amount_paise=existing_exec.authorized_amount_paise,
                currency=existing_exec.currency,
                is_duplicate=True,
                latency_ms=elapsed_ms
            )

        # Single-Use Invariant: An execution authorization may authorize exactly one business execution.
        # Check if proposal has already been executed to ORDER_CREATED or PAID under a prior key.
        prior_stmt = select(ExecutionRecord).where(
            and_(
                ExecutionRecord.proposal_id == request.proposal_id,
                ExecutionRecord.merchant_id == request.merchant_id,
                ExecutionRecord.status.in_([
                    ExecutionState.ORDER_CREATED.value,
                    ExecutionState.AWAITING_PAYMENT.value,
                    ExecutionState.PAID.value
                ])
            )
        )
        prior_exec = (await db.execute(prior_stmt)).scalar_one_or_none()
        if prior_exec and prior_exec.idempotency_key != idempotency_key:
            logger.warn(
                "proposal_already_executed_single_use_violation",
                proposal_id=request.proposal_id,
                prior_exec_id=prior_exec.id
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            rejection = ExecutionAuthorization(
                authorization_id=auth_id,
                proposal_id=request.proposal_id,
                merchant_id=request.merchant_id,
                candidate_id=selected_cand_id,
                authorized_amount_paise=0,
                status=ExecutionState.EXECUTION_REJECTED.value,
                rejection_reasons=[ExecutionRejectionReason.EXECUTION_ALREADY_COMPLETED.value],
                receipt=f"rcpt_{uuid.uuid4().hex[:12]}"[:40],
                idempotency_key=idempotency_key
            )
            return PolicyExecuteResponse(
                execution_id=exec_id,
                status=ExecutionState.EXECUTION_REJECTED,
                authorization=rejection,
                authorized_amount_paise=0,
                latency_ms=elapsed_ms
            )

        # 3. Fetch Fresh Merchant Commerce Context
        try:
            fresh_context = await self.commerce_service.get_merchant_commerce_context(db, request.merchant_id)
        except MerchantNotFoundError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            rejection = ExecutionAuthorization(
                authorization_id=auth_id,
                proposal_id=request.proposal_id,
                merchant_id=request.merchant_id,
                candidate_id=selected_cand_id,
                authorized_amount_paise=0,
                status=ExecutionState.EXECUTION_REJECTED.value,
                rejection_reasons=[ExecutionRejectionReason.MERCHANT_MISMATCH.value],
                receipt=f"rcpt_{uuid.uuid4().hex[:12]}"[:40],
                idempotency_key=idempotency_key
            )
            return PolicyExecuteResponse(
                execution_id=exec_id,
                status=ExecutionState.EXECUTION_REJECTED,
                authorization=rejection,
                authorized_amount_paise=0,
                latency_ms=elapsed_ms
            )

        # 4. Resolve Candidate to Validate
        candidate = None
        if request.proposal:
            for c in request.proposal.candidates:
                if c.candidate_id == selected_cand_id:
                    candidate = c
                    break

        if not candidate and request.proposal and request.proposal.selected_candidate:
            candidate = request.proposal.selected_candidate

        if not candidate or not request.proposal:
            # Proposal or candidate missing
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            rejection = ExecutionAuthorization(
                authorization_id=auth_id,
                proposal_id=request.proposal_id,
                merchant_id=request.merchant_id,
                candidate_id=selected_cand_id,
                authorized_amount_paise=0,
                status=ExecutionState.EXECUTION_REJECTED.value,
                rejection_reasons=[ExecutionRejectionReason.PROPOSAL_NOT_FOUND.value],
                receipt=f"rcpt_{uuid.uuid4().hex[:12]}"[:40],
                idempotency_key=idempotency_key
            )
            return PolicyExecuteResponse(
                execution_id=exec_id,
                status=ExecutionState.EXECUTION_REJECTED,
                authorization=rejection,
                authorized_amount_paise=0,
                latency_ms=elapsed_ms
            )

        # 5. Deterministic Fresh-State Revalidation
        (
            is_valid,
            reasons,
            recalculated_economics,
            authorized_amount_paise
        ) = self.validator.revalidate_candidate(
            candidate=candidate,
            proposal=request.proposal,
            fresh_context=fresh_context,
            intent=request.intent
        )

        receipt = f"rcpt_{uuid.uuid4().hex[:10]}_{selected_cand_id[:8]}"[:40]

        # 6. Handle Revalidation Failure (EXECUTION_REJECTED)
        if not is_valid:
            rejection_codes = [r.value for r in reasons]
            auth_record = ExecutionRecord(
                id=exec_id,
                idempotency_key=idempotency_key,
                proposal_id=request.proposal_id,
                candidate_id=selected_cand_id,
                merchant_id=request.merchant_id,
                receipt=receipt,
                authorized_amount_paise=0,
                currency=fresh_context.currency,
                status=ExecutionState.EXECUTION_REJECTED.value,
                rejection_reasons=rejection_codes,
                recalculated_economics=recalculated_economics.model_dump(mode="json") if recalculated_economics else None,
                audit_metadata={"rejected_at": "validation_gate"}
            )
            db.add(auth_record)
            await db.commit()

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            auth_dto = ExecutionAuthorization(
                authorization_id=auth_id,
                proposal_id=request.proposal_id,
                merchant_id=request.merchant_id,
                candidate_id=selected_cand_id,
                authorized_amount_paise=0,
                currency=fresh_context.currency,
                status=ExecutionState.EXECUTION_REJECTED.value,
                rejection_reasons=rejection_codes,
                recalculated_economics=recalculated_economics,
                receipt=receipt,
                idempotency_key=idempotency_key,
                context_snapshot_timestamp=request.proposal.context_snapshot_at
            )
            return PolicyExecuteResponse(
                execution_id=exec_id,
                status=ExecutionState.EXECUTION_REJECTED,
                authorization=auth_dto,
                authorized_amount_paise=0,
                currency=fresh_context.currency,
                latency_ms=elapsed_ms
            )

        # 7. Atomic Inventory Reservation
        quantities: Dict[str, int] = {}
        if candidate.bundle_components:
            for comp in candidate.bundle_components:
                pid = comp.get("product_id")
                qty = comp.get("quantity", 1)
                if pid:
                    quantities[pid] = quantities.get(pid, 0) + qty
        else:
            for pid in candidate.product_ids:
                quantities[pid] = 1

        reservation_success = await self.reservation_mgr.reserve_inventory(db, quantities)
        if not reservation_success:
            # Concurrency race: item was claimed between read and reserve
            auth_record = ExecutionRecord(
                id=exec_id,
                idempotency_key=idempotency_key,
                proposal_id=request.proposal_id,
                candidate_id=selected_cand_id,
                merchant_id=request.merchant_id,
                receipt=receipt,
                authorized_amount_paise=0,
                currency=fresh_context.currency,
                status=ExecutionState.EXECUTION_REJECTED.value,
                rejection_reasons=[ExecutionRejectionReason.CONCURRENCY_CONFLICT.value],
                recalculated_economics=recalculated_economics.model_dump(mode="json") if recalculated_economics else None,
                audit_metadata={"conflict_type": "atomic_reservation_race"}
            )
            db.add(auth_record)
            await db.commit()

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            auth_dto = ExecutionAuthorization(
                authorization_id=auth_id,
                proposal_id=request.proposal_id,
                merchant_id=request.merchant_id,
                candidate_id=selected_cand_id,
                authorized_amount_paise=0,
                currency=fresh_context.currency,
                status=ExecutionState.EXECUTION_REJECTED.value,
                rejection_reasons=[ExecutionRejectionReason.CONCURRENCY_CONFLICT.value],
                recalculated_economics=recalculated_economics,
                receipt=receipt,
                idempotency_key=idempotency_key
            )
            return PolicyExecuteResponse(
                execution_id=exec_id,
                status=ExecutionState.EXECUTION_REJECTED,
                authorization=auth_dto,
                authorized_amount_paise=0,
                currency=fresh_context.currency,
                latency_ms=elapsed_ms
            )

        # 8. Persist Authorized Execution Record
        exec_record = ExecutionRecord(
            id=exec_id,
            idempotency_key=idempotency_key,
            proposal_id=request.proposal_id,
            candidate_id=selected_cand_id,
            merchant_id=request.merchant_id,
            receipt=receipt,
            authorized_amount_paise=authorized_amount_paise,
            currency=fresh_context.currency,
            status=ExecutionState.EXECUTION_AUTHORIZED.value,
            rejection_reasons=[],
            recalculated_economics=recalculated_economics.model_dump(mode="json") if recalculated_economics else None,
            audit_metadata={
                "strategy_type": candidate.strategy_type.value,
                "product_ids": candidate.product_ids,
                "quantities": quantities
            }
        )
        db.add(exec_record)
        await db.commit()

        # 9. Create Razorpay Test-Mode Order via Existing OrderService
        try:
            order = await self.order_service.create_order(
                db=db,
                amount_paise=authorized_amount_paise,
                currency=fresh_context.currency,
                notes={
                    "execution_id": exec_id,
                    "proposal_id": request.proposal_id,
                    "candidate_id": selected_cand_id,
                    "merchant_id": request.merchant_id,
                    "strategy_type": candidate.strategy_type.value,
                    "system": "merchant-policy-agent-execution-gate"
                },
                decision_id=exec_id
            )

            exec_record.order_id = order.id
            exec_record.razorpay_order_id = order.razorpay_order_id
            exec_record.status = ExecutionState.ORDER_CREATED.value
            await db.commit()
            await db.refresh(exec_record)

            final_state = ExecutionState.ORDER_CREATED
            order_id = order.id
            rzp_order_id = order.razorpay_order_id

        except Exception as exc:
            logger.error("razorpay_order_creation_failed_in_gate", error=str(exc))
            # Safe failure: release reserved inventory
            await self.reservation_mgr.release_inventory(db, quantities)
            exec_record.status = ExecutionState.ORDER_CREATE_FAILED.value
            exec_record.rejection_reasons = [ExecutionRejectionReason.RAZORPAY_ORDER_CREATION_FAILED.value]
            await db.commit()

            final_state = ExecutionState.ORDER_CREATE_FAILED
            order_id = None
            rzp_order_id = None

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        auth_dto = ExecutionAuthorization(
            authorization_id=auth_id,
            proposal_id=request.proposal_id,
            merchant_id=request.merchant_id,
            candidate_id=selected_cand_id,
            authorized_amount_paise=authorized_amount_paise,
            currency=fresh_context.currency,
            status=exec_record.status,
            rejection_reasons=exec_record.rejection_reasons or [],
            recalculated_economics=recalculated_economics,
            receipt=receipt,
            idempotency_key=idempotency_key,
            context_snapshot_timestamp=request.proposal.context_snapshot_at
        )

        return PolicyExecuteResponse(
            execution_id=exec_id,
            status=final_state,
            authorization=auth_dto,
            order_id=order_id,
            razorpay_order_id=rzp_order_id,
            authorized_amount_paise=authorized_amount_paise,
            currency=fresh_context.currency,
            latency_ms=elapsed_ms
        )

    async def expire_or_cancel_execution(
        self,
        db: AsyncSession,
        execution_id: str,
        target_state: ExecutionState = ExecutionState.EXPIRED
    ) -> Optional[ExecutionRecord]:
        """Explicitly expire or cancel an execution record and release any reserved inventory."""
        stmt = select(ExecutionRecord).where(ExecutionRecord.id == execution_id)
        rec = (await db.execute(stmt)).scalar_one_or_none()
        if not rec:
            return None

        if rec.status not in (ExecutionState.PAID.value, ExecutionState.CANCELLED.value, ExecutionState.EXPIRED.value):
            rec.status = target_state.value
            quantities = rec.audit_metadata.get("quantities", {}) if rec.audit_metadata else {}
            if quantities:
                await self.reservation_mgr.release_inventory(db, quantities)
            await db.commit()
            await db.refresh(rec)
            logger.info("execution_expired_or_cancelled", execution_id=execution_id, final_status=rec.status)

        return rec

