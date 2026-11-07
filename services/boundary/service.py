"""Service implementation for Phase 9.2 Active Policy + Safety + Execution Boundary.

Contract: execution-boundary/v1

Orchestrates:
1. Decision existence & tenant scope verification.
2. Idempotency ledger lookup (single traversal per decision).
3. Decision staleness verification (TTL enforcement).
4. Authoritative active policy & lifecycle verification (Phase 8.8 authority).
5. Authoritative fresh commerce state retrieval (Phase 2 CommerceService).
6. Authoritative commercial safety re-evaluation (Phase 8.6 PolicySafetyService).
7. Server-generated, single-use execution authorization.
8. Safe handoff to Phase 5 ExecutionGate (inventory reservation & Razorpay Test Mode order).
9. Audit trail persistence in decision_executions (zero learning side effects).
"""

import uuid
import time
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models import (
    Merchant,
    CanonicalDecisionRecord,
    DecisionExecutionRecord,
    MerchantPolicyVersionRecord,
    MerchantActivePolicy,
    AuditEvent
)
from domain.intent_schemas import (
    BuyerIntent,
    BudgetConstraint,
    AttributeRequirement,
    OperatorType,
    ConfidenceLevel
)
from services.commerce_service import CommerceService, MerchantNotFoundError
from services.runtime.schemas import DecisionEnvelope, CANONICAL_DECISION_SCHEMA_VERSION
from services.boundary.schemas import (
    EXECUTION_BOUNDARY_SCHEMA_VERSION,
    ExecutionBoundaryStatus,
    DecisionExecuteRequest,
    DecisionExecuteResponse,
)
from services.boundary.errors import (
    DecisionNotFoundError,
    DecisionTenantViolationError,
    DecisionStaleError,
    PolicyLifecycleStateError,
    SafetyRejectionError,
    ExecutionConflictError,
)
from services.lifecycle.service import PolicyLifecycleService
from services.lifecycle.schemas import PolicyLifecycleState
from services.safety.service import PolicySafetyService
from services.safety.schemas import (
    PolicySafetyRequest,
    PolicySafetyStatus,
    SAFETY_SCHEMA_VERSION
)
from services.safety.validator import PolicySafetyValidator
from services.execution.gate import ExecutionGate
from services.execution.schemas import (
    PolicyExecuteRequest,
    PolicyExecuteResponse,
    ExecutionState
)
from services.policy.schemas import (
    PolicyProposal,
    ProposalStatus,
    PolicyCandidate,
    StrategyType,
    IncentiveProposal,
    CandidateValidationStatus
)
from services.selection.ranking import CANONICAL_BASELINE_POLICY_ID

logger = structlog.get_logger()

# Default decision freshness TTL: 15 minutes (900 seconds)
DEFAULT_DECISION_TTL_SECONDS = 900.0


class DecisionExecutionBoundaryService:
    """Authoritative execution boundary orchestrator for Phase 9.2."""

    @classmethod
    async def execute_decision(
        cls,
        db: AsyncSession,
        decision_id: str,
        request: DecisionExecuteRequest,
        ttl_seconds: float = DEFAULT_DECISION_TTL_SECONDS
    ) -> DecisionExecuteResponse:
        """Evaluate execution eligibility and safely dispatch authorized decision to Phase 5."""
        t_start = time.perf_counter()
        logger.info("execution_request_received", decision_id=decision_id, merchant_id=request.merchant_id)

        # 1. Merchant Tenant Verification
        merch_res = await db.execute(select(Merchant).where(Merchant.id == request.merchant_id))
        merchant = merch_res.scalar_one_or_none()
        if not merchant:
            raise MerchantNotFoundError(f"Merchant '{request.merchant_id}' not found.")
        if (merchant.status or "").upper() != "ACTIVE":
            logger.warning("merchant_inactive_execution_blocked", merchant_id=request.merchant_id, status=merchant.status)
            return cls._build_rejection_response(
                execution_id=f"dexec_{uuid.uuid4().hex[:12]}",
                decision_id=decision_id,
                merchant_id=request.merchant_id,
                opportunity_id="unknown",
                status=ExecutionBoundaryStatus.POLICY_NOT_ACTIVE,
                reasons=[f"Merchant status is '{merchant.status}'. Only ACTIVE merchants may execute."]
            )

        # 2. Idempotency Check (Boundary Execution Ledger)
        idemp_key = request.idempotency_key or f"idem_dexec_{request.merchant_id}_{decision_id}"
        stmt_existing = select(DecisionExecutionRecord).where(
            and_(
                DecisionExecutionRecord.merchant_id == request.merchant_id,
                DecisionExecutionRecord.decision_id == decision_id
            )
        )
        existing_exec = (await db.execute(stmt_existing)).scalars().first()
        if existing_exec:
            logger.info("idempotent_decision_execution_replayed", decision_id=decision_id, exec_id=existing_exec.id)
            return cls._record_to_response(existing_exec, is_duplicate=True)

        # 3. Load Immutable Decision Record
        stmt_dec = select(CanonicalDecisionRecord).where(CanonicalDecisionRecord.id == decision_id)
        decision_rec = (await db.execute(stmt_dec)).scalar_one_or_none()
        if not decision_rec:
            logger.warning("decision_not_found", decision_id=decision_id)
            raise DecisionNotFoundError(f"Decision '{decision_id}' not found.")

        # Verify Tenant Scope
        if decision_rec.merchant_id != request.merchant_id:
            logger.error("cross_tenant_execution_blocked", decision_merchant=decision_rec.merchant_id, req_merchant=request.merchant_id)
            raise DecisionTenantViolationError(
                f"Decision '{decision_id}' belongs to merchant '{decision_rec.merchant_id}', not '{request.merchant_id}'."
            )

        envelope_data = decision_rec.decision_envelope_json
        envelope = DecisionEnvelope.model_validate(envelope_data)
        logger.info("decision_loaded", decision_id=decision_id, opportunity_id=decision_rec.opportunity_id)

        # 4. Decision Staleness / Freshness Check (TTL)
        now_utc = datetime.now(timezone.utc)
        created_utc = decision_rec.created_at
        if created_utc.tzinfo is None:
            created_utc = created_utc.replace(tzinfo=timezone.utc)

        age_seconds = (now_utc - created_utc).total_seconds()
        if age_seconds > ttl_seconds:
            logger.warning("decision_stale_execution_rejected", decision_id=decision_id, age_seconds=age_seconds, ttl=ttl_seconds)
            dexec_id = f"dexec_{uuid.uuid4().hex[:12]}"
            auth_id = f"eauth_{uuid.uuid4().hex[:16]}"
            rec_stale = DecisionExecutionRecord(
                id=dexec_id,
                merchant_id=request.merchant_id,
                decision_id=decision_id,
                opportunity_id=decision_rec.opportunity_id,
                authorization_id=auth_id,
                policy_id=decision_rec.selected_policy_id,
                policy_version="merchant-policy/v1",
                state_fingerprint="stale",
                boundary_status=ExecutionBoundaryStatus.DECISION_STALE.value,
                rejection_reasons_json=[f"DECISION_STALE: Decision age ({age_seconds:.1f}s) exceeds TTL threshold ({ttl_seconds:.1f}s)."],
                idempotency_key=idemp_key,
                created_at=now_utc,
                updated_at=now_utc
            )
            db.add(rec_stale)
            await db.commit()
            return cls._record_to_response(rec_stale, is_duplicate=False)

        # 5. Authoritative Active Policy / Lifecycle Verification (Phase 8.8 Authority)
        selected_policy_id = decision_rec.selected_policy_id
        selected_policy_version = "merchant-policy/v1"

        # Check for explicitly retired or rolled back policy versions
        stmt_versions = select(MerchantPolicyVersionRecord).where(
            and_(
                MerchantPolicyVersionRecord.merchant_id == request.merchant_id,
                MerchantPolicyVersionRecord.policy_id == selected_policy_id
            )
        )
        version_rows = (await db.execute(stmt_versions)).scalars().all()

        retired = any(v.lifecycle_status == PolicyLifecycleState.RETIRED.value for v in version_rows)
        if retired:
            logger.warning("execution_blocked_policy_retired", policy_id=selected_policy_id)
            return await cls._persist_and_reject(
                db, request.merchant_id, decision_id, decision_rec.opportunity_id,
                selected_policy_id, ExecutionBoundaryStatus.POLICY_RETIRED,
                [f"POLICY_RETIRED: Policy '{selected_policy_id}' was retired by merchant."],
                idemp_key, now_utc
            )

        rolled_back = any(v.lifecycle_status == PolicyLifecycleState.ROLLED_BACK.value for v in version_rows)
        if rolled_back:
            logger.warning("execution_blocked_policy_rolled_back", policy_id=selected_policy_id)
            return await cls._persist_and_reject(
                db, request.merchant_id, decision_id, decision_rec.opportunity_id,
                selected_policy_id, ExecutionBoundaryStatus.POLICY_ROLLED_BACK,
                [f"POLICY_ROLLED_BACK: Policy '{selected_policy_id}' was rolled back."],
                idemp_key, now_utc
            )

        # Active Pointer Check: If merchant has an active policy set, ensure it aligns
        active_policy_resp = await PolicyLifecycleService.get_active_policy(db, request.merchant_id)
        if (
            active_policy_resp.promotion_id != "init_baseline"
            and active_policy_resp.policy_id != selected_policy_id
            and selected_policy_id != CANONICAL_BASELINE_POLICY_ID
            and envelope.decision_mode.value == "EXPLOIT"
        ):
            # Exploit decision no longer matches the active policy pointer
            logger.warning(
                "execution_blocked_policy_not_active",
                selected_policy_id=selected_policy_id,
                active_policy_id=active_policy_resp.policy_id
            )
            return await cls._persist_and_reject(
                db, request.merchant_id, decision_id, decision_rec.opportunity_id,
                selected_policy_id, ExecutionBoundaryStatus.POLICY_NOT_ACTIVE,
                [f"POLICY_NOT_ACTIVE: Policy '{selected_policy_id}' is no longer active policy (current: '{active_policy_resp.policy_id}')."],
                idemp_key, now_utc
            )

        logger.info("active_policy_verified", policy_id=selected_policy_id)

        # 6. Reconstruct Candidate & Intent for Fresh Evaluation
        cand = cls._reconstruct_candidate(envelope)
        intent = cls._reconstruct_intent(envelope)

        # 7. Reload Fresh Authoritative Commerce State (Phase 2)
        commerce_service = CommerceService()
        fresh_context = await commerce_service.get_merchant_commerce_context(db, request.merchant_id)
        logger.info("fresh_state_loaded", merchant_id=request.merchant_id, product_count=len(fresh_context.products))

        # Compute State Fingerprint
        state_fingerprint = PolicySafetyValidator.compute_state_fingerprint(
            candidate=cand,
            fresh_context=fresh_context,
            proposed_policy_version=selected_policy_version
        )

        # 8. Authoritative Safety / Admissibility Evaluation (Phase 8.6 Authority)
        safety_req = PolicySafetyRequest(
            merchant_id=request.merchant_id,
            opportunity_id=decision_rec.opportunity_id,
            buyer_context_key=decision_rec.buyer_context_key,
            proposed_policy=cand,
            proposed_policy_version=selected_policy_version,
            intent=intent,
            selection_id=decision_id,
            safety_version=SAFETY_SCHEMA_VERSION
        )
        safety_res = await PolicySafetyService.validate_policy(db, safety_req)

        if safety_res.status != PolicySafetyStatus.ADMISSIBLE:
            failure_reasons = [f.value for f in safety_res.failure_codes] or [safety_res.validation_reason]
            logger.warning("fresh_safety_rejection", decision_id=decision_id, reasons=failure_reasons)
            return await cls._persist_and_reject(
                db, request.merchant_id, decision_id, decision_rec.opportunity_id,
                selected_policy_id, ExecutionBoundaryStatus.SAFETY_REJECTED,
                failure_reasons, idemp_key, now_utc,
                safety_check_id=safety_res.safety_check_id,
                state_fingerprint=state_fingerprint
            )

        logger.info("safety_verified", safety_check_id=safety_res.safety_check_id)

        # 9. Server-Generated Single-Use Execution Authorization
        auth_id = f"eauth_{uuid.uuid4().hex[:16]}"
        dexec_id = f"dexec_{uuid.uuid4().hex[:12]}"

        # Derive exact authorized payable amount from fresh safety recalculated economics
        if safety_res.recalculated_economics:
            authorized_amount_paise = safety_res.recalculated_economics.net_revenue_paise
        else:
            authorized_amount_paise = envelope.selected_policy.proposed_price_paise

        logger.info("execution_authorized", auth_id=auth_id, amount_paise=authorized_amount_paise)

        # 10. Invoke Existing Phase 5 ExecutionGate
        # Construct PolicyProposal container for Phase 5 execution contract
        proposal = PolicyProposal(
            proposal_id=decision_id,
            merchant_id=request.merchant_id,
            status=ProposalStatus.VALID,
            candidates=[cand],
            selected_candidate=cand,
            total_candidates=1,
            valid_candidates_count=1,
            rejected_candidates_count=0
        )
        exec_req = PolicyExecuteRequest(
            merchant_id=request.merchant_id,
            proposal_id=decision_id,
            candidate_id=cand.candidate_id,
            proposal=proposal,
            intent=intent,
            idempotency_key=f"idem_p5_{request.merchant_id}_{decision_id}"
        )

        gate = ExecutionGate()
        logger.info("execution_submitted_to_phase5", decision_id=decision_id, auth_id=auth_id)
        p5_res = await gate.execute_policy(db, exec_req)

        # 11. Interpret Phase 5 Outcome
        if p5_res.status in (ExecutionState.ORDER_CREATED, ExecutionState.EXECUTION_AUTHORIZED):
            boundary_status = ExecutionBoundaryStatus.EXECUTION_COMPLETED
            rejection_reasons = []
        else:
            boundary_status = ExecutionBoundaryStatus.EXECUTION_REJECTED
            rejection_reasons = [f"PHASE5_REJECTED: Status '{p5_res.status.value}'"]

        # 12. Persist Boundary Audit Record
        exec_record = DecisionExecutionRecord(
            id=dexec_id,
            merchant_id=request.merchant_id,
            decision_id=decision_id,
            opportunity_id=decision_rec.opportunity_id,
            authorization_id=auth_id,
            policy_id=selected_policy_id,
            policy_version=selected_policy_version,
            state_fingerprint=state_fingerprint,
            safety_check_id=safety_res.safety_check_id,
            boundary_status=boundary_status.value,
            execution_record_id=p5_res.execution_id,
            order_id=p5_res.order_id,
            razorpay_order_id=p5_res.razorpay_order_id,
            authorized_amount_paise=authorized_amount_paise,
            currency=merchant.currency or "INR",
            rejection_reasons_json=rejection_reasons,
            idempotency_key=idemp_key,
            created_at=now_utc,
            updated_at=now_utc
        )
        db.add(exec_record)

        # Audit Event for Governance
        audit_event = AuditEvent(
            entity_type="DECISION_EXECUTION",
            entity_id=dexec_id,
            actor="EXECUTION_BOUNDARY",
            action="DECISION_EXECUTION_BOUNDARY_TRAVERSED",
            payload={
                "merchant_id": request.merchant_id,
                "decision_id": decision_id,
                "opportunity_id": decision_rec.opportunity_id,
                "authorization_id": auth_id,
                "boundary_status": boundary_status.value,
                "phase5_execution_id": p5_res.execution_id,
                "order_id": p5_res.order_id,
                "razorpay_order_id": p5_res.razorpay_order_id,
                "authorized_amount_paise": authorized_amount_paise
            }
        )
        db.add(audit_event)
        await db.commit()

        logger.info(
            "execution_reference_returned",
            dexec_id=dexec_id,
            status=boundary_status.value,
            order_id=p5_res.order_id
        )

        return cls._record_to_response(exec_record, is_duplicate=False)

    @classmethod
    async def get_execution(
        cls,
        db: AsyncSession,
        decision_id: str,
        merchant_id: str
    ) -> DecisionExecuteResponse:
        """Retrieve authoritative execution boundary record with strict tenant authorization."""
        stmt = select(DecisionExecutionRecord).where(
            and_(
                DecisionExecutionRecord.decision_id == decision_id,
                DecisionExecutionRecord.merchant_id == merchant_id
            )
        )
        rec = (await db.execute(stmt)).scalars().first()
        if not rec:
            raise DecisionNotFoundError(f"Execution record for decision '{decision_id}' not found.")
        return cls._record_to_response(rec, is_duplicate=False)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    @classmethod
    def _reconstruct_candidate(cls, envelope: DecisionEnvelope) -> PolicyCandidate:
        """Reconstruct strongly-typed PolicyCandidate from canonical DecisionEnvelope."""
        sel = envelope.selected_policy
        try:
            strat_type = StrategyType(sel.strategy_type)
        except ValueError:
            strat_type = StrategyType.NO_OFFER

        inc = None
        if sel.discount_percent > 0:
            inc = IncentiveProposal(
                incentive_type="discount",
                discount_percent=Decimal(str(sel.discount_percent)),
                description=sel.rationale
            )

        return PolicyCandidate(
            candidate_id=sel.candidate_id,
            strategy_type=strat_type,
            product_ids=list(sel.product_ids),
            incentive=inc,
            validation_status=CandidateValidationStatus.APPROVED,
            rationale=sel.rationale
        )

    @classmethod
    def _reconstruct_intent(cls, envelope: DecisionEnvelope) -> BuyerIntent:
        """Reconstruct strongly-typed BuyerIntent from canonical DecisionEnvelope summary."""
        intent_summary = envelope.intent_summary
        reqs = []
        for r in intent_summary.hard_requirements:
            parts = r.split(" ", 2)
            if len(parts) == 3:
                attr, op_str, val = parts
                try:
                    val_cast = float(val) if "." in val else int(val)
                except ValueError:
                    val_cast = val
                op = OperatorType(op_str) if op_str in OperatorType._value2member_map_ else OperatorType.EQUALS
                reqs.append(AttributeRequirement(attribute=attr, operator=op, value=val_cast))

        b_constraint = None
        if intent_summary.budget_paise:
            b_constraint = BudgetConstraint(
                amount_paise=intent_summary.budget_paise,
                max_amount_paise=intent_summary.budget_paise,
                currency="INR"
            )

        return BuyerIntent(
            category=intent_summary.category,
            use_case=intent_summary.use_case,
            quantity=intent_summary.quantity or 1,
            budget=b_constraint,
            requirements=reqs,
            confidence=ConfidenceLevel.HIGH
        )

    @classmethod
    async def _persist_and_reject(
        cls,
        db: AsyncSession,
        merchant_id: str,
        decision_id: str,
        opportunity_id: str,
        policy_id: str,
        status: ExecutionBoundaryStatus,
        reasons: List[str],
        idemp_key: str,
        now_utc: datetime,
        safety_check_id: Optional[str] = None,
        state_fingerprint: str = "unverified"
    ) -> DecisionExecuteResponse:
        """Persist a failed execution traversal to the boundary ledger and return response."""
        dexec_id = f"dexec_{uuid.uuid4().hex[:12]}"
        auth_id = f"eauth_{uuid.uuid4().hex[:16]}"
        rec = DecisionExecutionRecord(
            id=dexec_id,
            merchant_id=merchant_id,
            decision_id=decision_id,
            opportunity_id=opportunity_id,
            authorization_id=auth_id,
            policy_id=policy_id,
            policy_version="merchant-policy/v1",
            state_fingerprint=state_fingerprint,
            safety_check_id=safety_check_id,
            boundary_status=status.value,
            rejection_reasons_json=reasons,
            idempotency_key=idemp_key,
            created_at=now_utc,
            updated_at=now_utc
        )
        db.add(rec)
        await db.commit()
        return cls._record_to_response(rec, is_duplicate=False)

    @classmethod
    def _build_rejection_response(
        cls,
        execution_id: str,
        decision_id: str,
        merchant_id: str,
        opportunity_id: str,
        status: ExecutionBoundaryStatus,
        reasons: List[str]
    ) -> DecisionExecuteResponse:
        """Build an in-memory rejection response when persistence is impossible."""
        return DecisionExecuteResponse(
            execution_id=execution_id,
            decision_id=decision_id,
            merchant_id=merchant_id,
            opportunity_id=opportunity_id,
            boundary_status=status,
            execution_authorized=False,
            rejection_reasons=reasons,
            is_duplicate=False,
            executed_at=datetime.now(timezone.utc),
            boundary_version=EXECUTION_BOUNDARY_SCHEMA_VERSION
        )

    @classmethod
    def _record_to_response(
        cls,
        rec: DecisionExecutionRecord,
        is_duplicate: bool
    ) -> DecisionExecuteResponse:
        """Convert database DecisionExecutionRecord to clean DecisionExecuteResponse."""
        b_status = ExecutionBoundaryStatus(rec.boundary_status)
        is_authorized = (b_status == ExecutionBoundaryStatus.EXECUTION_COMPLETED)

        return DecisionExecuteResponse(
            execution_id=rec.id,
            decision_id=rec.decision_id,
            merchant_id=rec.merchant_id,
            opportunity_id=rec.opportunity_id,
            boundary_status=b_status,
            execution_authorized=is_authorized,
            authorization_id=rec.authorization_id,
            safety_check_id=rec.safety_check_id,
            phase5_execution_id=rec.execution_record_id,
            order_id=rec.order_id,
            razorpay_order_id=rec.razorpay_order_id,
            authorized_amount_paise=rec.authorized_amount_paise,
            currency=rec.currency or "INR",
            rejection_reasons=rec.rejection_reasons_json or [],
            is_duplicate=is_duplicate,
            executed_at=rec.created_at,
            boundary_version=EXECUTION_BOUNDARY_SCHEMA_VERSION
        )
